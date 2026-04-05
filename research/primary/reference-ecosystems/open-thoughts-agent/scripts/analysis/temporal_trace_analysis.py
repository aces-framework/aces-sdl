#!/usr/bin/env python3
"""Temporal analysis of RL trace datasets from HuggingFace.

Fetches a trace dataset, bins rows by timestamp, and computes comparative
statistics across time bins to track agent improvement over training.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.analysis.utils import (
    count_turns,
    extract_conversation_text,
    extract_date,
    extract_error_type,
    extract_reward,
    get_tiktoken_encoder,
    load_hf_trace_dataset,
)

SCRIPT_DIR = Path(__file__).resolve().parent

PARSING_ERROR_MARKER = "Previous response had parsing errors"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch a HuggingFace trace dataset, bin rows by timestamp, and "
            "compute comparative statistics across time bins."
        )
    )
    parser.add_argument(
        "repo",
        help="HuggingFace dataset repo ID (e.g., DCAgent/my-trace-dataset).",
    )
    parser.add_argument(
        "--bin-hours",
        type=float,
        default=1.0,
        help="Bin size in hours (default: 1.0).",
    )
    parser.add_argument(
        "--split",
        default="train",
        help="Dataset split to load (default: train).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path for JSON report (default: <script_dir>/temporal_report.json).",
    )
    parser.add_argument(
        "--plot",
        type=Path,
        default=None,
        help="Path for plot image (default: <script_dir>/temporal_report.png).",
    )
    parser.add_argument(
        "--main-only",
        action="store_true",
        default=False,
        help="Filter to trace_source=='main' rows only (drop summarization sub-traces).",
    )
    return parser.parse_args()


def _floor_datetime(dt: datetime, bin_hours: float) -> datetime:
    """Floor *dt* to the nearest bin boundary."""
    bin_seconds = int(bin_hours * 3600)
    # Strip timezone to keep arithmetic naive
    dt = dt.replace(tzinfo=None)
    epoch = datetime(2000, 1, 1)
    delta = dt - epoch
    total_seconds = int(delta.total_seconds())
    floored_seconds = (total_seconds // bin_seconds) * bin_seconds
    return epoch + timedelta(seconds=floored_seconds)


# ---------------------------------------------------------------------------
# Pre-computed row: holds all expensive-to-derive fields so bin aggregation
# only touches cheap Python ints/floats/strings.
# ---------------------------------------------------------------------------

def _precompute_rows(dataset, encoder, max_text_chars: int = 500_000) -> List[Dict[str, Any]]:
    """Extract text, tokenize in batch, and derive all per-row fields.

    Args:
        max_text_chars: Truncate texts longer than this before tokenizing.
            For truncated texts the token count is estimated as:
            ``actual_tokens_of_truncated + (remaining_chars / chars_per_token)``.
            Default 500k chars (~125k tokens) covers 131k-context traces.
    """
    n = len(dataset)
    chars_per_token_estimate = 4  # conservative for English/code

    # --- Phase 1: cheap per-row extraction (no tokenisation) ---------------
    print(f"  Extracting text from {n} rows...", flush=True)
    texts: List[str] = []
    full_lengths: List[int] = []
    records: List[Dict[str, Any]] = []
    for row in dataset:
        row_dict = dict(row)
        text = extract_conversation_text(row_dict)
        full_lengths.append(len(text))
        # Truncate for tokenizer; we'll estimate the remainder below
        texts.append(text[:max_text_chars])
        records.append({
            "turns": count_turns(row_dict),
            "task": row_dict.get("task"),
            "episode": row_dict.get("episode"),
            "reward": extract_reward(row_dict),
            "error_type": extract_error_type(row_dict),
            "date": extract_date(row_dict),
            "has_parsing_error": PARSING_ERROR_MARKER in text,
        })

    n_truncated = sum(1 for fl in full_lengths if fl > max_text_chars)
    if n_truncated:
        print(f"  Note: {n_truncated} texts truncated from >{max_text_chars} chars "
              f"(token counts estimated for overflow portion).", flush=True)

    # --- Phase 2: batch tokenisation (parallelised in Rust by tiktoken) ----
    #     Small chunks with a per-chunk timeout so one bad sample can't block.
    import concurrent.futures

    BATCH_CHUNK = 256
    CHUNK_TIMEOUT = 120  # seconds per chunk
    token_counts: List[int] = [0] * n
    n_timed_out = 0
    try:
        from tqdm import tqdm
        pbar = tqdm(total=n, desc="  Tokenizing", unit="row")
    except ImportError:
        pbar = None
        print(f"  Batch-tokenizing {n} texts...", flush=True)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    for i in range(0, n, BATCH_CHUNK):
        chunk = texts[i : i + BATCH_CHUNK]
        chunk_len = len(chunk)
        if encoder is not None:
            future = executor.submit(encoder.encode_batch, chunk, disallowed_special=())
            try:
                encoded = future.result(timeout=CHUNK_TIMEOUT)
                for j, tokens in enumerate(encoded):
                    token_counts[i + j] = len(tokens)
            except concurrent.futures.TimeoutError:
                n_timed_out += chunk_len
                for j, t in enumerate(chunk):
                    token_counts[i + j] = len(t) // chars_per_token_estimate
        else:
            for j, t in enumerate(chunk):
                token_counts[i + j] = len(t.split())
        if pbar is not None:
            pbar.update(chunk_len)
    executor.shutdown(wait=False)

    if pbar is not None:
        pbar.close()
    if n_timed_out:
        print(f"  Warning: {n_timed_out} rows in timed-out chunks "
              f"(token counts estimated from char length).", flush=True)

    # Adjust token counts for truncated texts
    for idx in range(n):
        overflow = full_lengths[idx] - max_text_chars
        if overflow > 0:
            token_counts[idx] += overflow // chars_per_token_estimate

    for rec, tc in zip(records, token_counts):
        rec["token_count"] = tc

    return records


# ---------------------------------------------------------------------------
# Aggregate stats from pre-computed rows (cheap — no text / tokenisation)
# ---------------------------------------------------------------------------

def _aggregate_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate statistics over pre-computed row dicts."""
    n = len(rows)
    if n == 0:
        return {
            "count": 0,
            "unique_tasks": 0,
            "unique_episodes": 0,
            "turns": {"min": None, "max": None, "avg": None},
            "trace_tokens": {"min": None, "max": None, "avg": None},
            "reward": {"min": None, "max": None, "avg": None},
            "reward_rate": 0.0,
            "reward_count": 0,
            "error_rate": 0.0,
            "error_counts": {},
            "null_result_count": 0,
            "parsing_error_count": 0,
            "parsing_error_rate": 0.0,
        }

    turns_list: List[int] = []
    token_list: List[int] = []
    rewards: List[float] = []
    error_counts: Dict[str, int] = defaultdict(int)
    n_errors = 0
    n_null_result = 0
    n_parsing_errors = 0
    tasks: set = set()
    episodes: set = set()

    for r in rows:
        turns_list.append(r["turns"])
        token_list.append(r["token_count"])

        if r["has_parsing_error"]:
            n_parsing_errors += 1

        task = r["task"]
        if task is not None:
            tasks.add(task)
        ep = r["episode"]
        if ep is not None:
            episodes.add(ep)

        reward = r["reward"]
        if reward is not None:
            rewards.append(reward)
        else:
            error_type = r["error_type"]
            if error_type is not None:
                error_counts[error_type] += 1
                n_errors += 1
            else:
                n_null_result += 1

    def _safe_stats(vals: List) -> Dict[str, Optional[float]]:
        if not vals:
            return {"min": None, "max": None, "avg": None}
        return {"min": min(vals), "max": max(vals), "avg": sum(vals) / len(vals)}

    reward_stats = _safe_stats(rewards)
    reward_rate = sum(1 for r in rewards if r > 0) / n if n else 0.0

    return {
        "count": n,
        "unique_tasks": len(tasks),
        "unique_episodes": len(episodes),
        "turns": _safe_stats(turns_list),
        "trace_tokens": _safe_stats(token_list),
        "reward": reward_stats,
        "reward_rate": reward_rate,
        "reward_count": len(rewards),
        "error_rate": n_errors / n if n else 0.0,
        "error_counts": dict(error_counts),
        "null_result_count": n_null_result,
        "parsing_error_count": n_parsing_errors,
        "parsing_error_rate": n_parsing_errors / n if n else 0.0,
    }


def _print_summary_table(bin_stats: Dict[str, Dict[str, Any]]) -> None:
    """Print a compact summary table to stdout."""
    header = (
        f"{'Bin':<22s} {'Count':>6s} {'Tasks':>6s} {'AvgTurns':>9s} "
        f"{'AvgTokens':>10s} {'Reward':>7s} {'RwdRate':>8s} "
        f"{'ErrRate':>8s} {'Parse':>6s} {'Null':>5s}"
    )
    print(header)
    print("-" * len(header))
    for bin_key in sorted(bin_stats):
        s = bin_stats[bin_key]
        avg_turns = s["turns"]["avg"]
        avg_tokens = s["trace_tokens"]["avg"]
        avg_reward = s["reward"]["avg"]
        print(
            f"{bin_key:<22s} {s['count']:>6d} {s['unique_tasks']:>6d} "
            f"{avg_turns:>9.1f} {avg_tokens:>10.0f} "
            f"{avg_reward if avg_reward is not None else float('nan'):>7.3f} "
            f"{s['reward_rate']:>8.3f} {s['error_rate']:>8.3f} "
            f"{s['parsing_error_count']:>6d} {s['null_result_count']:>5d}"
        )


def _generate_plot(bin_stats: Dict[str, Dict[str, Any]], output_path: Path) -> None:
    """Generate a 4-panel plot of key metrics over time."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available; skipping plot generation.", file=sys.stderr)
        return

    sorted_keys = sorted(bin_stats)
    if len(sorted_keys) < 2:
        print("Too few bins for a meaningful plot; skipping.", file=sys.stderr)
        return

    x_labels = sorted_keys
    x = range(len(x_labels))

    reward_rates = [bin_stats[k]["reward_rate"] for k in sorted_keys]
    avg_turns = [bin_stats[k]["turns"]["avg"] or 0 for k in sorted_keys]
    error_rates = [bin_stats[k]["error_rate"] for k in sorted_keys]
    parse_err_rates = [bin_stats[k]["parsing_error_rate"] for k in sorted_keys]

    fig, axes = plt.subplots(4, 1, figsize=(14, 13), sharex=True)

    axes[0].plot(x, reward_rates, marker="o", markersize=3, linewidth=1.2)
    axes[0].set_ylabel("Reward Rate")
    axes[0].set_title("Reward Rate Over Time")
    axes[0].set_ylim(-0.05, 1.05)
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(x, avg_turns, marker="o", markersize=3, linewidth=1.2, color="tab:orange")
    axes[1].set_ylabel("Avg Turns")
    axes[1].set_title("Average Conversation Turns Over Time")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(x, error_rates, marker="o", markersize=3, linewidth=1.2, color="tab:red")
    axes[2].set_ylabel("Error Rate")
    axes[2].set_title("Error Rate Over Time")
    axes[2].set_ylim(-0.05, 1.05)
    axes[2].grid(True, alpha=0.3)

    axes[3].plot(x, parse_err_rates, marker="o", markersize=3, linewidth=1.2, color="tab:purple")
    axes[3].set_ylabel("Parse Error Rate")
    axes[3].set_title("Parsing Error Rate Over Time")
    axes[3].set_ylim(-0.05, 1.05)
    axes[3].grid(True, alpha=0.3)

    # Show a subset of x-tick labels to avoid crowding
    n_ticks = min(len(x_labels), 15)
    step = max(len(x_labels) // n_ticks, 1)
    tick_positions = list(range(0, len(x_labels), step))
    tick_labels = [x_labels[i] for i in tick_positions]
    axes[3].set_xticks(tick_positions)
    axes[3].set_xticklabels(tick_labels, rotation=45, ha="right", fontsize=7)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"Saved plot to {output_path}")


def main() -> None:
    args = _parse_args()
    encoder = get_tiktoken_encoder()
    if encoder is None:
        print(
            "tiktoken not available; falling back to whitespace token counts.",
            file=sys.stderr,
        )

    print(f"Loading dataset {args.repo} (split={args.split})...")
    dataset = load_hf_trace_dataset(args.repo, split=args.split)
    print(f"Loaded {len(dataset)} rows.")

    if args.main_only and "trace_source" in dataset.column_names:
        before = len(dataset)
        dataset = dataset.filter(lambda row: row.get("trace_source") == "main")
        print(f"Filtered to trace_source=='main': {before} -> {len(dataset)} rows.")

    # --- Pre-compute all expensive fields in one pass ----------------------
    all_records = _precompute_rows(dataset, encoder)

    # --- Bin pre-computed records by timestamp -----------------------------
    print("Binning by timestamp...", flush=True)
    bins: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    n_unparseable = 0
    for rec in all_records:
        dt = rec["date"]
        if dt is None:
            n_unparseable += 1
            bins["unknown"].append(rec)
        else:
            floored = _floor_datetime(dt, args.bin_hours)
            bin_key = floored.strftime("%Y-%m-%d %H:%M")
            bins[bin_key].append(rec)

    if n_unparseable:
        print(
            f"Warning: {n_unparseable} rows with unparseable dates placed in 'unknown' bin.",
            file=sys.stderr,
        )

    # Drop the last (most recent) dated bin — it likely has partial traces
    dated_keys = sorted(k for k in bins if k != "unknown")
    if len(dated_keys) > 1:
        dropped_key = dated_keys[-1]
        dropped_rows = bins.pop(dropped_key)
        print(f"Dropped last bin '{dropped_key}' ({len(dropped_rows)} rows, likely partial).",
              flush=True)

    print(f"Computing statistics for {len(bins)} bins...", flush=True)
    bin_stats: Dict[str, Dict[str, Any]] = {}
    for bin_key, rows in bins.items():
        bin_stats[bin_key] = _aggregate_stats(rows)

    # Global summary from all pre-computed records (single pass, no re-tokenisation)
    global_stats = _aggregate_stats(all_records)

    # Aggregate error counts across all bins
    all_error_counts: Dict[str, int] = defaultdict(int)
    for s in bin_stats.values():
        for err_type, cnt in s["error_counts"].items():
            all_error_counts[err_type] += cnt

    # Print table
    _print_summary_table(bin_stats)
    print()
    print(f"Global: {global_stats['count']} rows, "
          f"reward_rate={global_stats['reward_rate']:.3f}, "
          f"error_rate={global_stats['error_rate']:.3f}, "
          f"parsing_errors={global_stats['parsing_error_count']} "
          f"({global_stats['parsing_error_rate']:.3f})")
    if all_error_counts:
        print("Error breakdown:")
        for err_type, cnt in sorted(all_error_counts.items(), key=lambda x: -x[1]):
            print(f"  {err_type}: {cnt}")

    # Write JSON report
    output_path = args.output or SCRIPT_DIR / "temporal_report.json"
    report = {
        "repo": args.repo,
        "split": args.split,
        "bin_hours": args.bin_hours,
        "total_rows": len(all_records),
        "num_bins": len(bin_stats),
        "global_stats": global_stats,
        "all_error_counts": dict(all_error_counts),
        "bins": {k: bin_stats[k] for k in sorted(bin_stats)},
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Wrote JSON report to {output_path}")

    # Generate plot
    plot_path = args.plot or SCRIPT_DIR / "temporal_report.png"
    # Exclude 'unknown' bin from plot
    plot_stats = {k: v for k, v in bin_stats.items() if k != "unknown"}
    if plot_stats:
        _generate_plot(plot_stats, plot_path)
    else:
        print("No dated bins to plot.", file=sys.stderr)


if __name__ == "__main__":
    main()
