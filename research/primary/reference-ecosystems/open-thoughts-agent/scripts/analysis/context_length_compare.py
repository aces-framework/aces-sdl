"""Compare context length statistics across HuggingFace datasets.

Usage:
    python -m scripts.analysis.context_length_compare \
        DCAgent2/dataset-a DCAgent2/dataset-b \
        --tokenizer Qwen/Qwen3-8B \
        --filter 'trace_source==main'
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

import numpy as np
from datasets import load_dataset

from scripts.analysis.utils import extract_conversation_text


def tokenize_dataset(
    ds,
    tokenizer,
    *,
    batch_size: int = 512,
) -> np.ndarray:
    """Return an array of per-row token counts for *ds*."""
    texts = [extract_conversation_text(row) for row in ds]
    counts: list[int] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        encoded = tokenizer(batch, add_special_tokens=False, return_length=True)
        counts.extend(encoded["length"])
    return np.array(counts)


def print_stats(name: str, counts: np.ndarray) -> None:
    """Print a summary table for *counts*."""
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")
    print(f"  rows   = {len(counts):,}")
    print(f"  mean   = {np.mean(counts):,.0f} tokens")
    print(f"  median = {np.median(counts):,.0f}")
    print(f"  std    = {np.std(counts):,.0f}")
    print(f"  min    = {np.min(counts):,.0f}")
    print(f"  p10    = {np.percentile(counts, 10):,.0f}")
    print(f"  p25    = {np.percentile(counts, 25):,.0f}")
    print(f"  p75    = {np.percentile(counts, 75):,.0f}")
    print(f"  p90    = {np.percentile(counts, 90):,.0f}")
    print(f"  p95    = {np.percentile(counts, 95):,.0f}")
    print(f"  max    = {np.max(counts):,.0f}")


def parse_filter(filter_str: str) -> tuple[str, str]:
    """Parse 'column==value' into (column, value)."""
    if "==" not in filter_str:
        raise ValueError(
            f"Filter must be in 'column==value' format, got: {filter_str!r}"
        )
    col, val = filter_str.split("==", 1)
    return col.strip(), val.strip()


def load_and_filter(
    repo_id: str,
    split: str,
    filter_spec: Optional[str],
) -> tuple:
    """Load a dataset and optionally filter rows. Returns (dataset, n_dropped)."""
    print(f"Loading {repo_id} (split={split})...")
    try:
        ds = load_dataset(repo_id, split=split)
    except Exception:
        # Try without specifying split
        ds_dict = load_dataset(repo_id)
        available = list(ds_dict.keys())
        print(f"  Available splits: {available}")
        ds = ds_dict[available[0]]

    n_original = len(ds)
    print(f"  Columns: {ds.column_names}")
    print(f"  Rows: {n_original:,}")

    if filter_spec:
        col, val = parse_filter(filter_spec)
        if col in ds.column_names:
            ds = ds.filter(lambda row: row.get(col) == val)
            n_dropped = n_original - len(ds)
            print(f"  Filter '{col}=={val}': kept {len(ds):,}, dropped {n_dropped:,}")
        else:
            print(f"  Warning: column '{col}' not found, skipping filter")
            n_dropped = 0
    else:
        n_dropped = 0

    return ds, n_dropped


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Compare context length statistics across HF datasets.",
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
    args = parser.parse_args(argv)

    from transformers import AutoTokenizer

    print(f"Loading tokenizer: {args.tokenizer}")
    tokenizer = AutoTokenizer.from_pretrained(
        args.tokenizer, trust_remote_code=True
    )

    all_results: list[tuple[str, np.ndarray]] = []

    for repo_id in args.datasets:
        ds, _ = load_and_filter(repo_id, args.split, args.filter_spec)
        print(f"  Tokenizing {len(ds):,} rows...")
        counts = tokenize_dataset(ds, tokenizer)
        print_stats(repo_id, counts)
        all_results.append((repo_id, counts))

    # Print comparison table if multiple datasets
    if len(all_results) > 1:
        print(f"\n{'=' * 80}")
        print("  COMPARISON SUMMARY")
        print(f"{'=' * 80}")
        header = f"{'Dataset':<65} {'Rows':>6} {'Mean':>8} {'Median':>8} {'P90':>8} {'Max':>8}"
        print(header)
        print("-" * len(header))
        for name, counts in all_results:
            short = name.split("/")[-1][:62]
            print(
                f"{short:<65} {len(counts):>6,} "
                f"{np.mean(counts):>8,.0f} {np.median(counts):>8,.0f} "
                f"{np.percentile(counts, 90):>8,.0f} {np.max(counts):>8,.0f}"
            )


if __name__ == "__main__":
    main()
