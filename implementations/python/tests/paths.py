"""Repository-root and validation-corpus paths for the Python tests directory.

This module is a normal test-support module, not a pytest conftest. It is
importable as `from paths import EXAMPLES_DIR` because the tests directory is
on `pythonpath` per the project pyproject.toml.

The repo root is located by walking up from this file until a
`.ground-control.yaml` marker is found, rather than by counting fixed parent
depth. That makes the helper resilient to relocation, symlinks, or repackaged
checkouts of the tests directory.
"""

from pathlib import Path

_REPO_ROOT_MARKER = ".ground-control.yaml"


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / _REPO_ROOT_MARKER).exists():
            return parent
    raise RuntimeError(
        f"Could not find {_REPO_ROOT_MARKER} walking up from {here}; tests cannot locate the validation-corpus root"
    )


REPO_ROOT = _find_repo_root()
EXAMPLES_DIR = REPO_ROOT / "examples" / "scenarios"
