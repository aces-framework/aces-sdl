"""
Generate Harbor-format task datasets from nvidia/Nemotron-Terminal-Corpus.

Reads the downloaded corpus parquet files, extracts task descriptions from
conversation traces, and produces Harbor task directories. Each subset is
then converted to parquet and uploaded to HuggingFace.

Usage:
    python -m data.nemotron_terminal_corpus.generate \
        --corpus-dir /path/to/nemotron-terminal-corpus \
        --out-dir /path/to/output
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from data.nemotron_terminal_corpus.task_templates import (
    PLAIN_DOCKERFILE,
    render_instruction_md,
    render_task_toml,
)
from data.nemotron_terminal_corpus.utils import (
    SUBSET_CONFIGS,
    extract_task_description,
    get_category_from_parquet_path,
    iter_parquet_rows,
)


def create_task_dir(
    row: dict,
    out_root: Path,
    idx: int,
    difficulty: str,
    category: str,
    prefix: str = "nemotron",
) -> bool:
    """Create one Harbor task directory from a conversation row.

    Returns True if task was created, False if skipped.
    """
    conversations = row.get("conversations", [])
    if not conversations:
        return False

    first_msg = conversations[0].get("content", "")
    task_desc = extract_task_description(first_msg)
    if not task_desc:
        return False

    d = out_root / f"{prefix}-{idx:06d}"
    (d / "environment").mkdir(parents=True, exist_ok=True)

    # task.toml
    (d / "task.toml").write_text(render_task_toml(difficulty, category), encoding="utf-8")

    # instruction.md
    (d / "instruction.md").write_text(render_instruction_md(task_desc), encoding="utf-8")

    # environment/Dockerfile
    (d / "environment" / "Dockerfile").write_text(PLAIN_DOCKERFILE, encoding="utf-8")

    return True


def generate_subset(
    name: str,
    config: dict,
    corpus_dir: Path,
    out_dir: Path,
) -> Path | None:
    """Generate task directories for one subset.

    Returns the subset output directory, or None if no tasks produced.
    """
    subset_dir = out_dir / name
    if subset_dir.exists():
        shutil.rmtree(subset_dir)
    subset_dir.mkdir(parents=True, exist_ok=True)

    difficulty = config["difficulty"]
    default_category = config["category"]
    num_produced = 0
    num_skipped = 0

    for parquet_rel in config["parquets"]:
        parquet_path = corpus_dir / parquet_rel
        if not parquet_path.exists():
            print(f"  WARNING: {parquet_path} not found, skipping", file=sys.stderr)
            continue

        # For skill-based subsets, derive category from the directory name
        if "skill_based" in parquet_rel:
            category = get_category_from_parquet_path(parquet_rel)
        else:
            category = default_category

        for row in iter_parquet_rows(parquet_path):
            ok = create_task_dir(
                row, subset_dir, num_produced,
                difficulty=difficulty, category=category,
            )
            if ok:
                num_produced += 1
                if num_produced % 5000 == 0:
                    print(f"    ... {num_produced} tasks generated")
            else:
                num_skipped += 1

    print(f"  {name}: {num_produced} tasks generated, {num_skipped} skipped")
    return subset_dir if num_produced > 0 else None


def convert_and_upload(
    subset_dir: Path,
    repo_id: str,
    out_dir: Path,
) -> None:
    """Convert task directory to parquet and upload to HuggingFace."""
    from scripts.harbor import tasks_parquet_converter as tpc
    from huggingface_hub import HfApi

    tasks = tpc.find_tasks(subset_dir, recursive=True)
    if not tasks:
        print(f"  No tasks found in {subset_dir}, skipping upload")
        return

    parquet_path = out_dir / f"{subset_dir.name}.parquet"
    print(f"  Converting {len(tasks)} tasks to {parquet_path}")
    tpc.to_parquet(subset_dir, parquet_path, tasks, compression="gz")
    print(f"  Parquet: {parquet_path.stat().st_size / 1e6:.1f} MB")

    api = HfApi()
    api.create_repo(repo_id, repo_type="dataset", exist_ok=True)
    api.upload_file(
        path_or_fileobj=str(parquet_path),
        path_in_repo="data/train-00000-of-00001.parquet",
        repo_id=repo_id,
        repo_type="dataset",
    )
    print(f"  Uploaded to https://huggingface.co/datasets/{repo_id}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate Harbor tasks from Nemotron-Terminal-Corpus"
    )
    p.add_argument(
        "--corpus-dir", type=Path, required=True,
        help="Path to downloaded nvidia/Nemotron-Terminal-Corpus",
    )
    p.add_argument(
        "--out-dir", type=Path, required=True,
        help="Output directory for generated task dirs and parquets",
    )
    p.add_argument(
        "--hf-org", type=str, default="penfever",
        help="HuggingFace organization for uploads",
    )
    p.add_argument(
        "--no-upload", action="store_true",
        help="Skip the HF upload step",
    )
    p.add_argument(
        "--subsets", nargs="*", default=None,
        help="Only process these subsets (default: all)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    configs = SUBSET_CONFIGS
    if args.subsets:
        configs = {k: v for k, v in configs.items() if k in args.subsets}

    for name, config in configs.items():
        repo_id = f"{args.hf_org}/nemotron-tc-{name}-sandboxes"
        print(f"\n[{name}] Generating tasks...")

        subset_dir = generate_subset(name, config, args.corpus_dir, args.out_dir)
        if subset_dir is None:
            continue

        if not args.no_upload:
            print(f"[{name}] Converting and uploading to {repo_id}...")
            convert_and_upload(subset_dir, repo_id, args.out_dir)
        else:
            print(f"[{name}] Skipping upload (--no-upload)")

    print("\nDone.")


if __name__ == "__main__":
    main()
