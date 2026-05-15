#!/usr/bin/env python3
"""Verify the authoritative schema publication manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path("contracts/schema-publication-manifest.json")
SCHEMAS_PREFIX = "contracts/schemas/"
SCHEMA_VERSION = "schema-publication-manifest/v1"


def _published_schema_paths(repo_root: Path) -> set[str]:
    schemas_root = repo_root / "contracts" / "schemas"
    return {path.relative_to(repo_root).as_posix() for path in sorted(schemas_root.rglob("*.json"))}


def _load_manifest(repo_root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    manifest_file = repo_root / MANIFEST_PATH
    if not manifest_file.exists():
        return None, [f"schema publication manifest is missing: {MANIFEST_PATH.as_posix()}"]
    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"schema publication manifest is not valid JSON: {exc.msg}"]
    if not isinstance(payload, dict):
        return None, ["schema publication manifest must be a JSON object"]
    return payload, []


def validate_schema_publication_manifest(repo_root: Path = REPO_ROOT) -> list[str]:
    """Return validation failures for the checked-in schema publication manifest."""

    payload, failures = _load_manifest(repo_root)
    if payload is None:
        return failures

    if payload.get("schema_version") != SCHEMA_VERSION:
        failures.append(f"schema manifest schema_version must be {SCHEMA_VERSION!r}")

    entries = payload.get("schemas")
    if not isinstance(entries, list) or not entries:
        failures.append("schema manifest must define a non-empty schemas array")
        return failures

    manifest_paths: set[str] = set()
    manifest_ids: set[str] = set()
    previous_id = ""
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            failures.append(f"schema manifest entry {index} must be an object")
            continue

        contract_id = entry.get("contract_id")
        schema_path = entry.get("schema_path")
        if not isinstance(contract_id, str) or not contract_id:
            failures.append(f"schema manifest entry {index} contract_id must be a non-empty string")
            continue
        if not isinstance(schema_path, str) or not schema_path:
            failures.append(f"schema manifest entry {contract_id} schema_path must be a non-empty string")
            continue

        if contract_id <= previous_id:
            failures.append("schema manifest entries must be sorted by contract_id")
        previous_id = contract_id

        if contract_id in manifest_ids:
            failures.append(f"schema manifest contains duplicate contract_id: {contract_id}")
        manifest_ids.add(contract_id)

        if schema_path in manifest_paths:
            failures.append(f"schema manifest contains duplicate schema_path: {schema_path}")
        manifest_paths.add(schema_path)

        if schema_path != Path(schema_path).as_posix() or schema_path.startswith(("/", "../")):
            failures.append(f"schema manifest path must be a normalized repo-relative path: {schema_path}")
            continue
        if not schema_path.startswith(SCHEMAS_PREFIX):
            failures.append(f"schema manifest path must be under contracts/schemas/: {schema_path}")
            continue
        if not schema_path.endswith(".json"):
            failures.append(f"schema manifest path must point to a JSON schema file: {schema_path}")
            continue

        path = repo_root / schema_path
        if not path.is_file():
            failures.append(f"schema manifest path does not exist: {schema_path}")
            continue
        if path.stem != contract_id:
            failures.append(f"schema manifest contract_id {contract_id!r} must match schema filename {path.stem!r}")

    published_paths = _published_schema_paths(repo_root)
    for path in sorted(published_paths - manifest_paths):
        failures.append(f"schema manifest is missing published schema: {path}")
    for path in sorted(manifest_paths - published_paths):
        if path.startswith(SCHEMAS_PREFIX):
            failures.append(f"schema manifest references unpublished schema: {path}")

    return failures


def main() -> int:
    failures = validate_schema_publication_manifest(REPO_ROOT)
    if failures:
        for failure in failures:
            print(f"[schema-publication] {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
