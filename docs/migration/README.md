# Migration Notes

This note records the major documentation and repository-structure moves that
established the current layout. The paths below describe historical moves, not
current uncertainty about where authoritative material lives.

The reorganization moved existing material into the current long-term buckets:

- root `schemas/` -> `contracts/schemas/`
- root `conformance/fixtures` and `conformance/profiles` -> `contracts/`
- `docs/adrs/` -> `docs/decisions/adrs/`
- `docs/sdl/` -> `docs/explain/sdl/`
- Python implementation code and tests -> `implementations/python/`

Most of this re-homing is now complete. Follow-on passes may still refine
individual imports, tooling, or contract/spec details, but the authoritative
locations listed above are the intended home for current work.
