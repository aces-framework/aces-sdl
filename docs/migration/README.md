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

The authoritative locations listed above are the intended home for current
work. Remaining inconsistencies should be recorded as issues, ADR amendments,
or contract/spec changes rather than described here as open-ended migration
work.

The working order for reconciling the current implementation to that layout is
captured in [ADR-010](../decisions/adrs/adr-010-repository-realignment-order-and-compatibility-policy.md).
