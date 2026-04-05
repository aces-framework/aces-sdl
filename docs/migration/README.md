# Migration Notes

The repository is in the middle of a structural reorganization.

This pass moved existing material into the intended long-term buckets:

- root `schemas/` -> `contracts/schemas/`
- root `conformance/fixtures` and `conformance/profiles` -> `contracts/`
- `docs/adrs/` -> `docs/decisions/adrs/`
- `docs/sdl/` -> `docs/explain/sdl/`
- Python implementation code and tests -> `implementations/python/`

Breakage is expected during this phase. Follow-on passes will reconcile imports,
tooling, packaging, and individual contract/spec requirements against the new
layout.
