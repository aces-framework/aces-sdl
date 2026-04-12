#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from hashlib import sha256
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_ROOT = REPO_ROOT / "contracts" / "schemas"
PYTHON_ROOT = REPO_ROOT / "implementations" / "python"


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(
        description="Check that schema generation does not change the current working tree."
    ).parse_args()


def _snapshot_schema_tree(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*.json")):
        snapshot[path.relative_to(root).as_posix()] = sha256(path.read_bytes()).hexdigest()
    return snapshot


def _diff_snapshots(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed = sorted(set(before) ^ set(after))
    for path, checksum in before.items():
        if path in after and after[path] != checksum:
            changed.append(path)
    return sorted(set(changed))


def _extra_published_schema_paths(root: Path, *, expected_relative_paths: set[str]) -> list[str]:
    published = {path.relative_to(root).as_posix() for path in sorted(root.rglob("*.json"))}
    return sorted(published - expected_relative_paths)


def main() -> int:
    parse_args()
    before = _snapshot_schema_tree(SCHEMAS_ROOT)

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for python_path in (PYTHON_ROOT / "src", PYTHON_ROOT / "packages"):
        python_path_str = str(python_path)
        if python_path_str not in sys.path:
            sys.path.insert(0, python_path_str)
    from aces_contracts.contracts import schema_bundle

    from tools.generate_contract_schemas import _schema_output_path
    from tools.generate_contract_schemas import main as generate_contract_schemas

    generate_contract_schemas()
    after = _snapshot_schema_tree(SCHEMAS_ROOT)
    changed = _diff_snapshots(before, after)
    expected_relative_paths = {
        _schema_output_path(SCHEMAS_ROOT, name).relative_to(SCHEMAS_ROOT).as_posix() for name in schema_bundle()
    }
    extra_paths = _extra_published_schema_paths(SCHEMAS_ROOT, expected_relative_paths=expected_relative_paths)
    if changed:
        print("Published JSON schemas are out of date. Regeneration changed:", file=sys.stderr)
        for path in changed:
            print(f"  - contracts/schemas/{path}", file=sys.stderr)
        return 1
    if extra_paths:
        print(
            "Published JSON schemas contain stale files not generated from the current schema bundle:", file=sys.stderr
        )
        for path in extra_paths:
            print(f"  - contracts/schemas/{path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
