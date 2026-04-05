# Schemas

`contracts/schemas/` publishes versioned JSON Schema documents for
language-neutral ACES external contracts.

This directory is now the contract bucket in the repo layout. It is intended to
be the home of the authoritative machine-readable artifacts, independent of any
single implementation language or package layout.

Current published schemas cover:
- SDL authoring input
- instantiated scenarios
- backend manifests
- processor manifests
- live-execution snapshots
- workflow result envelopes
- workflow history streams
- evaluation result envelopes
- evaluation history streams
- operation receipts and statuses

Current filenames still use `runtime` for some live-execution artifacts. That
naming is preserved for compatibility while the repository migrates toward the
processor/runtime boundary described in
[ADR-008](../../docs/decisions/adrs/adr-008-processor-layer-and-execution-artifact-boundaries.md).

Generation or sync helpers may exist under `tools/`, but those helpers are
supporting repo machinery, not the authority boundary.
