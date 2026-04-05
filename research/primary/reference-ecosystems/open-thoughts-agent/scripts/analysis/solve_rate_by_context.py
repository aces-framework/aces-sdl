"""Solve / timeout / error rates binned by conversation context length.

Usage:
    python -m scripts.analysis.solve_rate_by_context \
        DCAgent2/dataset-a DCAgent2/dataset-b \
        --filter 'trace_source==main' \
        --plot solve_rate_by_context.png

    # Custom bins (comma-separated token thresholds)
    python -m scripts.analysis.solve_rate_by_context \
        DCAgent2/dataset-a \
        --bins 0,8192,16384,32768,65536,131072
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from scripts.analysis.utils import extract_reward, extract_error_type
from scripts.analysis.context_length_compare import (
    load_and_filter,
    tokenize_dataset,
)

# ── Default context-length bin thresholds ────────────────────────────────────

DEFAULT_BINS = [0, 16_384, 32_768, 65_536, 131_072]

BIN_LABELS = {
    0: "all",
    8_192: "8k+",
    16_384: "16k+",
    32_768: "32k+",
    65_536: "65k+",
    131_072: "131k+",
}


def _bin_label(threshold: int) -> str:
    if threshold in BIN_LABELS:
        return BIN_LABELS[threshold]
    if threshold >= 1024:
        return f"{threshold // 1024}k+"
    return f"{threshold}+"


# ── Per-bin statistics ───────────────────────────────────────────────────────

@dataclass
class BinStats:
    label: str
    threshold: int
    n: int = 0
    n_solved: int = 0
    n_zero: int = 0
    n_timeout: int = 0
    n_ctx_exceeded: int = 0
    n_other_error: int = 0
    n_null: int = 0

    @property
    def solve_rate(self) -> float:
        return self.n_solved / self.n if self.n else 0.0

    @property
    def timeout_rate(self) -> float:
        return self.n_timeout / self.n if self.n else 0.0

    @property
    def ctx_exceeded_rate(self) -> float:
        return self.n_ctx_exceeded / self.n if self.n else 0.0

    @property
    def error_rate(self) -> float:
        return (self.n_timeout + self.n_ctx_exceeded + self.n_other_error) / self.n if self.n else 0.0


@dataclass
class DatasetResult:
    name: str
    short_name: str
    token_counts: np.ndarray
    bin_stats: list[BinStats] = field(default_factory=list)


# ── Analysis ─────────────────────────────────────────────────────────────────

def compute_bin_stats(
    ds,
    token_counts: np.ndarray,
    thresholds: list[int],
) -> list[BinStats]:
    """Compute solve/timeout/error rates for each context-length bin."""
    rewards = [extract_reward(row) for row in ds]
    errors = [extract_error_type(row) for row in ds]

    stats: list[BinStats] = []
    for threshold in thresholds:
        mask = token_counts >= threshold
        n = int(mask.sum())
        bs = BinStats(label=_bin_label(threshold), threshold=threshold, n=n)

        for i in range(len(rewards)):
            if not mask[i]:
                continue
            r, e = rewards[i], errors[i]
            if r is not None and r > 0:
                bs.n_solved += 1
            elif e is not None:
                if "Timeout" in e:
                    bs.n_timeout += 1
                elif "ContextLength" in e:
                    bs.n_ctx_exceeded += 1
                else:
                    bs.n_other_error += 1
            elif r is not None and r == 0:
                bs.n_zero += 1
            else:
                bs.n_null += 1

        stats.append(bs)
    return stats


def print_table(result: DatasetResult) -> None:
    """Print a formatted table for one dataset."""
    print(f"\n{'=' * 95}")
    print(f"  {result.name}")
    print(f"{'=' * 95}")
    hdr = (
        f"  {'Bin':<8} {'Rows':>6}  {'Solved':>6} {'Solve%':>7}  "
        f"{'Timeout':>7} {'TO%':>7}  {'CtxExc':>6} {'CE%':>6}  "
        f"{'Zero':>6} {'OthErr':>6} {'Null':>5}"
    )
    print(hdr)
    print(f"  {'-' * (len(hdr) - 2)}")
    for bs in result.bin_stats:
        if bs.n == 0:
            print(f"  {bs.label:<8} {0:>6}")
            continue
        print(
            f"  {bs.label:<8} {bs.n:>6}  "
            f"{bs.n_solved:>6} {bs.solve_rate:>6.1%}  "
            f"{bs.n_timeout:>7} {bs.timeout_rate:>6.1%}  "
            f"{bs.n_ctx_exceeded:>6} {bs.ctx_exceeded_rate:>5.1%}  "
            f"{bs.n_zero:>6} {bs.n_other_error:>6} {bs.n_null:>5}"
        )


# ── Plotting ─────────────────────────────────────────────────────────────────

def plot_results(
    results: list[DatasetResult],
    output_path: str,
) -> None:
    """Generate a multi-panel comparison plot."""
    import matplotlib.pyplot as plt

    n_datasets = len(results)
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    metrics = [
        ("Solve Rate", lambda bs: bs.solve_rate),
        ("Timeout Rate", lambda bs: bs.timeout_rate),
        ("Zero-Reward Rate", lambda bs: bs.n_zero / bs.n if bs.n else 0.0),
    ]

    # Consistent x positions and colors
    colors = plt.cm.tab10.colors
    bar_width = 0.8 / n_datasets

    for ax, (metric_name, metric_fn) in zip(axes, metrics):
        # Use only bins that have data in at least one dataset
        all_labels = []
        for r in results:
            for bs in r.bin_stats:
                if bs.label not in all_labels:
                    all_labels.append(bs.label)

        x = np.arange(len(all_labels))

        for di, result in enumerate(results):
            label_to_stats = {bs.label: bs for bs in result.bin_stats}
            values = []
            for lbl in all_labels:
                bs = label_to_stats.get(lbl)
                if bs and bs.n > 0:
                    values.append(metric_fn(bs))
                else:
                    values.append(0.0)

            offset = (di - n_datasets / 2 + 0.5) * bar_width
            bars = ax.bar(
                x + offset,
                [v * 100 for v in values],
                bar_width,
                label=result.short_name,
                color=colors[di % len(colors)],
                alpha=0.85,
            )
            # Add count annotations on bars
            for xi, bar, lbl in zip(x, bars, all_labels):
                bs = label_to_stats.get(lbl)
                if bs and bs.n > 0:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.8,
                        f"n={bs.n}",
                        ha="center",
                        va="bottom",
                        fontsize=7,
                        rotation=45,
                    )

        ax.set_xticks(x)
        ax.set_xticklabels(all_labels)
        ax.set_ylabel("Percentage (%)")
        ax.set_title(metric_name, fontsize=13, fontweight="bold")
        ax.set_ylim(0, 105)
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle(
        "Solve / Timeout / Zero-Reward Rates by Context Length",
        fontsize=15,
        fontweight="bold",
    )
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\nPlot saved to {output_path}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Solve/timeout/error rates binned by context length.",
    )
    parser.add_argument(
        "datasets",
        nargs="+",
        help="HuggingFace dataset repo IDs to compare",
    )
    parser.add_argument(
        "--tokenizer",
        default="Qwen/Qwen3-8B",
        help="HF tokenizer to use (default: Qwen/Qwen3-8B)",
    )
    parser.add_argument(
        "--split",
        default="train",
        help="Dataset split (default: train)",
    )
    parser.add_argument(
        "--filter",
        dest="filter_spec",
        default=None,
        help="Row filter in 'column==value' format (e.g. 'trace_source==main')",
    )
    parser.add_argument(
        "--bins",
        default=None,
        help="Comma-separated bin thresholds (default: 0,16384,32768,65536,131072)",
    )
    parser.add_argument(
        "--plot",
        default=None,
        help="Output path for plot image (default: <script_dir>/solve_rate_by_context.png)",
    )
    args = parser.parse_args(argv)

    thresholds = DEFAULT_BINS
    if args.bins:
        thresholds = sorted(int(x.strip()) for x in args.bins.split(","))

    plot_path = args.plot or os.path.join(
        os.path.dirname(__file__), "solve_rate_by_context.png"
    )

    from transformers import AutoTokenizer

    print(f"Loading tokenizer: {args.tokenizer}")
    tokenizer = AutoTokenizer.from_pretrained(
        args.tokenizer, trust_remote_code=True
    )

    all_results: list[DatasetResult] = []

    for repo_id in args.datasets:
        ds, _ = load_and_filter(repo_id, args.split, args.filter_spec)
        print(f"  Tokenizing {len(ds):,} rows...")
        counts = tokenize_dataset(ds, tokenizer)
        bin_stats = compute_bin_stats(ds, counts, thresholds)

        short = repo_id.split("/")[-1]
        result = DatasetResult(
            name=repo_id,
            short_name=short,
            token_counts=counts,
            bin_stats=bin_stats,
        )
        print_table(result)
        all_results.append(result)

    # Comparison summary
    if len(all_results) > 1:
        print(f"\n{'=' * 95}")
        print("  COMPARISON SUMMARY")
        print(f"{'=' * 95}")
        for bs_idx in range(len(thresholds)):
            lbl = _bin_label(thresholds[bs_idx])
            print(f"\n  {lbl}:")
            for r in all_results:
                bs = r.bin_stats[bs_idx]
                if bs.n == 0:
                    print(f"    {r.short_name}: no data")
                else:
                    print(
                        f"    {r.short_name}: "
                        f"n={bs.n}, solve={bs.solve_rate:.1%}, "
                        f"timeout={bs.timeout_rate:.1%}, "
                        f"zero={bs.n_zero / bs.n:.1%}"
                    )

    plot_results(all_results, plot_path)


if __name__ == "__main__":
    main()
