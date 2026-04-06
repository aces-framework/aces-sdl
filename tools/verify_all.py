#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repo policy and requirement governance checks.")
    parser.add_argument("--staged", action="store_true", help="Check staged changes.")
    parser.add_argument("--base-rev", help="Compare against a specific git revision.")
    parser.add_argument("--requirement-uid", help="Explicit requirement UID override.")
    parser.add_argument("--skip-requirement", action="store_true", help="Skip Ground Control-backed requirement governance.")
    return parser.parse_args()


def run(args: list[str]) -> int:
    proc = subprocess.run(args)
    return proc.returncode


def main() -> int:
    args = parse_args()
    shared_args: list[str] = []
    if args.staged:
        shared_args.append("--staged")
    if args.base_rev:
        shared_args.extend(["--base-rev", args.base_rev])

    if run([sys.executable, "tools/check_repo_policy.py", *shared_args]) != 0:
        return 1

    if not args.skip_requirement:
        requirement_args = [sys.executable, "tools/check_requirement_governance.py", *shared_args]
        if args.requirement_uid:
            requirement_args.extend(["--requirement-uid", args.requirement_uid])
        if run(requirement_args) != 0:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
