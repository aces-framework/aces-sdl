#!/usr/bin/env python3
"""Generate checked-in JSON Schema bundles for ACES external contracts."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def _schema_output_path(schemas_dir: Path, name: str) -> Path:
    if name in {
        "sdl-authoring-input-v1",
        "instantiated-scenario-v1",
        "scenario-instantiation-request-v1",
    }:
        return schemas_dir / "sdl" / f"{name}.json"
    if name == "backend-manifest-v1":
        return schemas_dir / "backend-manifest" / f"{name}.json"
    if name == "processor-manifest-v1":
        return schemas_dir / "processor-manifest" / f"{name}.json"
    if name == "concept-families-v1":
        return schemas_dir / "concept-authority" / f"{name}.json"
    if name.endswith("-plan-v1"):
        return schemas_dir / "plans" / f"{name}.json"
    if name == "runtime-snapshot-v1":
        return schemas_dir / "snapshots" / f"{name}.json"
    return schemas_dir / "control-plane" / f"{name}.json"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    python_root = repo_root / "implementations" / "python"
    sys.path.insert(0, str(python_root / "src"))
    sys.path.insert(0, str(python_root / "packages"))

    from aces_contracts.contracts import schema_bundle

    schemas_dir = repo_root / "contracts" / "schemas"
    bundle = schema_bundle()
    for name, schema in bundle.items():
        output_path = _schema_output_path(schemas_dir, name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
