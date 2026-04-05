"""Fetch HF datasets and plot context length distributions."""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from datasets import load_dataset
from transformers import AutoTokenizer
from concurrent.futures import ThreadPoolExecutor

DATASETS = [
    # --- penfever 131k ---
    "penfever/GLM-4.7-bash_textbook_tasks-maxeps-131k",
    "penfever/GLM-4.7-ling-coder-sft-sandboxes-1-maxeps-131k",
    "penfever/glm46-neulab-agenttuning-alfworld-sandboxes-maxeps-131k",
    "penfever/glm46-swesmith-maxeps-131k",
    "penfever/glm46-qasper-maxeps-131k",
    "penfever/glm46-code-feedback-maxeps-131k",
    "penfever/glm-4.6-all-puzzles-32ep-131k",
    "penfever/kimi-k2t-neulab-synatra-32ep-131k",
    "penfever/glm46-neulab-synatra-32ep-131k",
    "penfever/glm46-defects4j-32ep-131k",
    "penfever/glm-4.6-freelancer-32ep-131k-torch",
    "penfever/minimax-m2-stack-overflow-32ep-131k-summtrc",
    "penfever/gpt-oss-120B-stack-overflow-32ep-131k-summtrc-fixthink1",
    "penfever/GLM-4.6-dclm-baseline-terminal-32ep-131k",
    "penfever/glm-4.6-dclm-baseline-terminal-traces-32ep-131k",
    "penfever/glm-4.6-stackexchange-tezos-32ep-131k",
    "penfever/Kimi-K2T-swesmith-32ep-131k",
    "penfever/GLM-4.6-inferred-bugs-32ep-131k-nosumm",
    "penfever/glm-4.6-staqc-32ep-131k",
    "penfever/GLM-4.6-swesmith-32ep-131k-nosumm-reasoning",
    "penfever/GLM-4.6-swesmith-32ep-131k-nosumm",
    "penfever/GLM-4.6-freelancer-32eps-131k",
    # --- DCAgent2 131k ---
    "DCAgent2/GLM-4.7-swesmith-sandboxes-with_tests-oracle_verified_120s-maxeps-131k",
    "DCAgent2/GLM-4.7-stackexchange-overflow-sandboxes-maxeps-131k",
    "DCAgent2/GLM-4.7-openhands-stackexchange-tezos-sandboxes-maxeps-131k",
    "DCAgent2/GLM-4.7-r2egym_sandboxes-maxeps-131k",
    "DCAgent2/GLM-4.7-inferredbugs-sandboxes-maxeps-131k",
    "DCAgent2/GLM-4.7-ling-coder-sft-sandboxes-1-maxeps-131k",
    "DCAgent2/GLM-4.7-neulab-bash_textbook_tasks-maxeps-131k",
    "DCAgent2/GLM-4.7-stackexchange-tezos-sandboxes-maxeps-131k",
    "DCAgent2/glm46-swegym-tasks-maxeps-131k",
    "DCAgent2/glm46-stackexchange-tezos-maxeps-131k",
    "DCAgent2/nemotron-prism-math-32ep-131k",
    "DCAgent2/glm46-neulab-mind2web-sandboxes-maxeps-131k",
    "DCAgent2/glm46-r2egym_sandboxes-maxeps-131k",
    "DCAgent2/glm46-glaive-code-assistant-sandboxes-maxeps-131k",
    "DCAgent2/glm46-ling-coder-sft-sandboxes-1-maxeps-131k",
    "DCAgent2/glm-4.6-stack-overflow-32ep-131k-summtrc",
    "DCAgent2/qwen3-coder-480B-stack-overflow-32ep-131k-summtrc",
    "DCAgent2/gpt-oss-120B-stack-overflow-32ep-131k-summtrc",
    "DCAgent2/minimax-m2-stack-overflow-32ep-131k-summtrc",
    # --- penfever 65k ---
    "penfever/GLM-4.6-inferredbugs-32ep-65k-reasoning",
    "penfever/GLM-4.6-stackexchange-overflow-sandboxes-32eps-65k-reasoning",
    "penfever/GLM-4.6-stackexchange-overflow-sandboxes-32eps-65k",
    "penfever/GLM-4.6-inferredbugs-32eps-65k",
    "penfever/inferredbugs-GLM-4.6-32ep-65k",
]


def get_text(example):
    """Extract full text from a dataset row.

    Delegates to :func:`scripts.analysis.utils.extract_conversation_text`.
    """
    from scripts.analysis.utils import extract_conversation_text
    return extract_conversation_text(example)


def process_dataset(ds_name, tokenizer):
    """Load dataset and compute token counts."""
    short = ds_name.split("/")[-1]
    print(f"  Loading {short}...", flush=True)
    try:
        ds = load_dataset(ds_name, split="train")
    except Exception as e:
        print(f"  FAILED {short}: {e}", flush=True)
        return short, []

    print(f"  Tokenizing {short} ({len(ds)} rows)...", flush=True)
    texts = [get_text(row) for row in ds]

    # Batch tokenize for speed
    counts = []
    batch_size = 512
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        encoded = tokenizer(batch, add_special_tokens=False, return_length=True)
        counts.extend(encoded["length"])

    print(f"  Done {short}: {len(counts)} samples, "
          f"median={np.median(counts):.0f}, p90={np.percentile(counts, 90):.0f}, "
          f"max={np.max(counts):.0f} tokens",
          flush=True)
    return short, counts


def main():
    print("Loading Qwen3-8B tokenizer...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(
        "Qwen/Qwen3-8B", trust_remote_code=True
    )

    results = {}
    for ds_name in DATASETS:
        short, counts = process_dataset(ds_name, tokenizer)
        if counts:
            results[short] = np.array(counts)

    n_datasets = len(results)
    print(f"\nPlotting {n_datasets} datasets...", flush=True)

    # Sort by median token count for legend readability
    sorted_names = sorted(results.keys(), key=lambda n: np.median(results[n]))

    # Generate enough distinct colors for all datasets
    cmap = plt.colormaps["tab20"]
    extra_cmap = plt.colormaps["Set1"]
    tab20b = plt.colormaps["tab20b"]
    tab20c = plt.colormaps["tab20c"]
    colors = (
        [cmap(i / 20) for i in range(20)]
        + [extra_cmap(i / 9) for i in range(9)]
        + [tab20b(i / 20) for i in range(20)]
        + [tab20c(i / 20) for i in range(20)]
    )

    fig, ax = plt.subplots(figsize=(28, 18))

    # Log-scale x-axis bins for better spread
    all_counts = np.concatenate(list(results.values()))
    bins = np.logspace(
        np.log10(max(100, all_counts.min())),
        np.log10(all_counts.max()),
        80,
    )

    for i, name in enumerate(sorted_names):
        counts = results[name]
        med = np.median(counts)
        p90 = np.percentile(counts, 90)
        label = f"{name}  (n={len(counts):,}, med={med:,.0f}, p90={p90:,.0f})"
        ax.hist(
            counts,
            bins=bins,
            alpha=0.7,
            label=label,
            histtype="step",
            linewidth=1.8,
            color=colors[i % len(colors)],
        )

    ax.set_xscale("log")
    ax.set_xlabel("Token Count (log scale)", fontsize=14)
    ax.set_ylabel("Frequency", fontsize=14)
    ax.set_title(f"Context Length Distribution Across {n_datasets} SFT Datasets", fontsize=18)

    # Reference lines at common cutoffs
    for cutoff, lbl in [(8192, "8k"), (16384, "16k"), (32768, "32k"), (65536, "64k"), (131072, "131k")]:
        ax.axvline(cutoff, color="gray", linestyle="--", alpha=0.4, linewidth=1)
        ax.text(cutoff, ax.get_ylim()[1] * 0.95, f" {lbl}", fontsize=9, color="gray", va="top")

    ax.legend(
        loc="upper left",
        fontsize=8,
        ncol=1,
        framealpha=0.9,
        bbox_to_anchor=(1.01, 1),
        borderaxespad=0,
    )

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(__file__), "context_length_distribution.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
