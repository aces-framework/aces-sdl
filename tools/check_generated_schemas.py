#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from hashlib import sha256
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_ROOT = REPO_ROOT / "contracts" / "schemas"


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


def main() -> int:
    parse_args()
    before = _snapshot_schema_tree(SCHEMAS_ROOT)

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tools.generate_contract_schemas import main as generate_contract_schemas

    generate_contract_schemas()
    after = _snapshot_schema_tree(SCHEMAS_ROOT)
    changed = _diff_snapshots(before, after)
    if changed:
        print("Published JSON schemas are out of date. Regeneration changed:", file=sys.stderr)
        for path in changed:
            print(f"  - contracts/schemas/{path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
