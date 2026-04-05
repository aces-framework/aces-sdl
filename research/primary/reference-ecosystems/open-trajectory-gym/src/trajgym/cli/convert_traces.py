#!/usr/bin/env python3
"""CLI for converting BoxPwnr traces to OpenAI-compatible training format.

Usage:
    trajgym convert --input <traces_dir> --output <output.jsonl> \\
        [--success-only] [--dedup] [--output-failure <failures.jsonl>]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from trajgym.data.converter import BoxPwnrConverter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert BoxPwnr traces to training format (lossless)."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Root directory containing BoxPwnr traces.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output JSONL file for successful traces.",
    )
    parser.add_argument(
        "--success-only",
        action="store_true",
        help="Only output successful traces.",
    )
    parser.add_argument(
        "--dedup",
        action="store_true",
        help="Keep only the shortest successful trace per challenge.",
    )
    parser.add_argument(
        "--output-failure",
        type=Path,
        default=None,
        help="Output JSONL file for failed traces.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.input.is_dir():
        print(f"Error: {args.input} is not a directory", file=sys.stderr)
        sys.exit(1)

    converter = BoxPwnrConverter()
    successes, failures = converter.convert_directory(
        args.input,
        success_only=args.success_only,
        dedup=args.dedup,
    )

    # Write successes
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        for trace in successes:
            f.write(json.dumps(trace) + "\n")
    print(f"Wrote {len(successes)} successful traces to {args.output}")

    # Write failures
    if args.output_failure and failures:
        args.output_failure.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_failure, "w") as f:
            for trace in failures:
                f.write(json.dumps(trace) + "\n")
        print(f"Wrote {len(failures)} failed traces to {args.output_failure}")
    elif failures and not args.output_failure:
        print(f"Skipped {len(failures)} failed traces (use --output-failure to save)")

    # Summary stats
    total = len(successes) + len(failures)
    if total > 0:
        print("\nSummary:")
        print(f"  Total traces found:  {total}")
        print(f"  Successes:           {len(successes)}")
        print(f"  Failures:            {len(failures)}")

        # Platform breakdown
        platforms: dict[str, int] = {}
        for t in successes + failures:
            p = t["metadata"].get("platform", "unknown")
            platforms[p] = platforms.get(p, 0) + 1
        if platforms:
            print(f"  Platforms:           {platforms}")


if __name__ == "__main__":
    main()
