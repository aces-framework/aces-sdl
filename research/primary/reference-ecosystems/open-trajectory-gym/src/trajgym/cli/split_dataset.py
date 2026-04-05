#!/usr/bin/env python3
"""Split converted BoxPwnr traces into SFT and online RL datasets.

Usage:
    trajgym split --input data/converted.jsonl
    trajgym split --input data/converted.jsonl \\
        --sft-output data/sft.jsonl \\
        --online-rl-output data/online_rl.jsonl \\
        --max-online-rl-tokens 32768
"""

import argparse
import logging
import sys
from pathlib import Path

from trajgym.data.splitter import DatasetSplitter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split converted BoxPwnr traces into SFT and online RL datasets"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input JSONL from the converter",
    )
    parser.add_argument(
        "--sft-output",
        default="data/sft.jsonl",
        help="Output path for SFT dataset (default: data/sft.jsonl)",
    )
    parser.add_argument(
        "--online-rl-output",
        default="data/online_rl.jsonl",
        help="Output path for online RL dataset (default: data/online_rl.jsonl)",
    )
    parser.add_argument(
        "--max-online-rl-tokens",
        type=int,
        default=32768,
        help="Max estimated tokens per online RL trace (default: 32768)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not Path(args.input).exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    splitter = DatasetSplitter(max_online_rl_tokens=args.max_online_rl_tokens)
    stats = splitter.split(args.input, args.sft_output, args.online_rl_output)

    # Print summary
    print("\n=== Dataset Split Summary ===\n")
    print(f"  Input traces:              {stats['total_input']}")
    print(f"  SFT output:                {stats['sft_count']}")
    print(f"  Online RL output:          {stats['online_rl_count']}")
    print(f"  Online RL filtered:        {stats['online_rl_filtered']}")
    print(f"  Online RL missing flag:    {stats['online_rl_missing_flag']}")
    print(f"  Avg turns (SFT):           {stats['avg_turns_sft']}")
    print(f"  Avg turns (Online RL):     {stats['avg_turns_online_rl']}")

    print("\n  Tool distribution:")
    for tool, count in stats["tool_distribution"].items():
        print(f"    {tool:<25s} {count:>6d}")

    print("\n  Platform distribution:")
    for platform, count in stats["platform_distribution"].items():
        print(f"    {platform:<25s} {count:>6d}")

    print(f"\n  Written: {args.sft_output}")
    print(f"  Written: {args.online_rl_output}")
    print()


if __name__ == "__main__":
    main()
