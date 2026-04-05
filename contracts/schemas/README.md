# Schemas

`contracts/schemas/` publishes versioned JSON Schema documents for
language-neutral ACES external contracts.

This directory is now the contract bucket in the repo layout. It is intended to
be the home of the authoritative machine-readable artifacts, independent of any
single implementation language or package layout.

Current published schemas cover:
- SDL authoring input
- instantiated scenarios
- backend manifests (`v1` compatibility plus shared-apparatus `v2`)
- processor manifests (`v1` compatibility plus shared-apparatus `v2`)
- concept-authority catalogs
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

For apparatus manifests, `v2` is now the authoritative shared envelope:

- `identity`
- `supported_contract_versions`
- `compatibility`
- `realization_support`
- `constraints`
- `capabilities`

`v1` backend and processor manifests remain published as compatibility contracts
for the current migration window.

Generation or sync helpers may exist under `tools/`, but those helpers are
supporting repo machinery, not the authority boundary.
