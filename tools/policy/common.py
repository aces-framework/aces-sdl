from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import fnmatch
import json
import subprocess
from typing import Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PolicyFailure:
    rule_id: str
    message: str
    path: str | None = None

    def render(self) -> str:
        if self.path:
            return f"[{self.rule_id}] {self.path}: {self.message}"
        return f"[{self.rule_id}] {self.message}"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data or {}


def repo_path(value: str | Path) -> str:
    return Path(value).as_posix().strip("/")


def run_git(args: list[str], repo_root: Path = REPO_ROOT) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    return proc.stdout


def changed_paths(
    repo_root: Path = REPO_ROOT,
    *,
    staged: bool = False,
    base_rev: str | None = None,
) -> list[str]:
    if staged:
        output = run_git(["diff", "--name-only", "--diff-filter=d", "--cached"], repo_root=repo_root)
    elif base_rev:
        output = run_git(["diff", "--name-only", "--diff-filter=d", base_rev, "HEAD"], repo_root=repo_root)
    else:
        output = run_git(["diff", "--name-only", "--diff-filter=d", "HEAD"], repo_root=repo_root)
    return [line.strip() for line in output.splitlines() if line.strip()]


def path_matches_prefix(path: str, prefix: str) -> bool:
    norm = repo_path(path)
    pref = repo_path(prefix)
    return norm == pref or norm.startswith(f"{pref}/")


def path_matches_any(path: str, prefixes: Iterable[str]) -> bool:
    return any(path_matches_prefix(path, prefix) for prefix in prefixes)


def glob_matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def load_exceptions(repo_root: Path = REPO_ROOT) -> list[dict]:
    raw = load_yaml(repo_root / "tools" / "policy" / "exceptions.yaml")
    return raw.get("exceptions", [])


def exception_active(entry: dict, *, today: date | None = None) -> bool:
    if today is None:
        today = date.today()
    expires_at = entry.get("expires_at")
    if not expires_at:
        return True
    return today <= date.fromisoformat(str(expires_at))


def apply_exceptions(
    failures: list[PolicyFailure],
    exceptions: list[dict],
    *,
    requirement_uid: str | None = None,
) -> list[PolicyFailure]:
    if not failures or not exceptions:
        return failures

    remaining: list[PolicyFailure] = []
    for failure in failures:
        waived = False
        for entry in exceptions:
            if not exception_active(entry):
                continue
            if entry.get("rule_id") != failure.rule_id:
                continue
            if requirement_uid and entry.get("requirement_uid") not in {None, requirement_uid}:
                continue
            match_paths = entry.get("paths") or []
            if failure.path and match_paths and not path_matches_any(failure.path, match_paths):
                continue
            waived = True
            break
        if not waived:
            remaining.append(failure)
    return remaining


def failures_to_json(failures: list[PolicyFailure]) -> str:
    return json.dumps(
        [
            {"rule_id": failure.rule_id, "message": failure.message, "path": failure.path}
            for failure in failures
        ],
        indent=2,
        sort_keys=True,
    )
