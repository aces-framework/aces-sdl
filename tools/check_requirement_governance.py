#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from policy.common import REPO_ROOT, apply_exceptions, changed_paths, failures_to_json, load_exceptions
from policy.requirement_governance import (
    GroundControlHttpClient,
    evaluate_requirement_governance,
    requirement_uid_from_context,
)

GOVERNED_ROOTS = ("implementations/", "contracts/", "specs/", "docs/")
REQUIREMENT_CONTEXT_EXEMPT_PATHS = {
    ".claude/agents/completion-verifier.md",
    ".claude/hooks/check_policy_after_edit.sh",
    ".claude/hooks/protect_files.sh",
    ".claude/hooks/verify-extra.sh",
    ".claude/settings.json",
    ".claude/skills/implement/SKILL.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/ci.yml",
    ".pre-commit-config.yaml",
    ".codex",
    "AGENTS.md",
    "CHANGELOG.md",
    "implementations/python/tests/test_repo_policy_tools.py",
    "implementations/python/tests/test_requirement_governance.py",
}
REQUIREMENT_CONTEXT_EXEMPT_PREFIXES = ("tools/",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate requirement order and traceability against Ground Control.")
    parser.add_argument("--staged", action="store_true", help="Check staged changes instead of working tree changes.")
    parser.add_argument("--base-rev", help="Compare against a specific git revision.")
    parser.add_argument("--json", action="store_true", help="Emit JSON failures.")
    parser.add_argument("--requirement-uid", help="Explicit requirement UID override.")
    parser.add_argument("paths", nargs="*", help="Explicit repo-relative paths to check.")
    return parser.parse_args()


def current_branch(repo_root: Path) -> str | None:
    # In CI PR checkouts the repo is in detached HEAD, so
    # git branch --show-current returns empty.  Fall back to
    # GITHUB_HEAD_REF (set by GitHub Actions for pull_request events).
    branch = os.environ.get("GITHUB_HEAD_REF", "").strip()
    if not branch:
        proc = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=True,
        )
        branch = proc.stdout.strip()
    return branch or None


def requires_requirement_context(paths: list[str]) -> bool:
    for path in paths:
        if path in REQUIREMENT_CONTEXT_EXEMPT_PATHS:
            continue
        if path.startswith(REQUIREMENT_CONTEXT_EXEMPT_PREFIXES):
            continue
        if path.startswith(GOVERNED_ROOTS):
            return True
    return False


def main() -> int:
    args = parse_args()
    paths = [Path(path).as_posix() for path in args.paths] if args.paths else changed_paths(REPO_ROOT, staged=args.staged, base_rev=args.base_rev)
    uid = requirement_uid_from_context(current_branch(REPO_ROOT), args.requirement_uid)
    if not requires_requirement_context(paths):
        return 0
    if not uid:
        failure = [
            {
                "rule_id": "requirement-context-missing",
                "message": "requirement UID is missing; set ACES_REQUIREMENT_UID or include a UID like GOV-918 in the branch name",
                "path": None,
            }
        ]
        if args.json:
            print(json.dumps(failure, indent=2))
        else:
            print("[requirement-context-missing] requirement UID is missing; set ACES_REQUIREMENT_UID or include a UID like GOV-918 in the branch name", file=sys.stderr)
        return 1

    client = GroundControlHttpClient(base_url=(os.environ.get("GC_BASE_URL") or "http://gc-dev:8000"))
    try:
        failures = evaluate_requirement_governance(REPO_ROOT, paths, client=client, requirement_uid=uid)
    except RuntimeError as exc:
        print(f"[ground-control-unavailable] {exc}", file=sys.stderr)
        return 1

    failures = apply_exceptions(failures, load_exceptions(REPO_ROOT), requirement_uid=uid)
    if failures:
        if args.json:
            print(failures_to_json(failures))
        else:
            for failure in failures:
                print(failure.render(), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
