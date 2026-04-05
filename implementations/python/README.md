# Python Reference Implementation

This directory contains the current Python reference implementation after the
monorepo reorganization.

Current contents:

- `packages/`: Python implementation packages split by concern
- `tests/`: Python implementation tests moved out of the repo root
- `pyproject.toml` and `uv.lock`: Python-local build and dependency files

This directory is transitional. The code has been moved into the right buckets
first; imports, packaging, and other implementation details will be reconciled
in later passes.
