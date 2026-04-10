# Schemas

`contracts/schemas/` publishes versioned JSON Schema documents for
language-neutral ACES external contracts.

This directory is now the contract bucket in the repo layout. It is intended to
be the home of the authoritative machine-readable artifacts, independent of any
single implementation language or package layout.

Current published schemas cover:
- SDL authoring input
- instantiated scenarios
- backend manifests (`v1` legacy plus shared-apparatus `v2`)
- processor manifests (`v1` legacy plus shared-apparatus `v2`)
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

These sections are intended to be concrete declarations, not placeholders. In
particular:

- `supported_contract_versions` must declare at least one contract
- `compatibility` must declare at least one compatible apparatus surface
- `realization_support` entries must declare non-empty disclosure kinds and at
  least one exact or constraint support kind
- processor capability blocks must declare non-empty SDL and feature support
- backend capability blocks must declare concrete provisioning and orchestration
  surfaces rather than empty shells

`v1` backend and processor manifests remain checked in as deprecated legacy
schema artifacts. The reference stack, contract tests, and conformance profiles
use `v2`.

## Concept Authority Catalog

The `concept-families-v1` schema publishes the machine-readable shared concept
authority catalog. Catalog entries distinguish adopted, adapted, and
ACES-native concept families.

Adopted and adapted families must declare `authority` and
`authority_reference`. Native families must not declare those authority fields;
instead they must declare non-empty `extension_scope`, `relation_rules`, and
`non_ambiguity_constraints`. This keeps ACES experiment, runtime, apparatus,
provenance, and governance concepts explicit without letting them silently fork
shared cyber-domain concepts.

## Cross-Artifact Concept Binding

Apparatus manifests (`v2`) require a `concept_bindings` section that binds
vocabulary fields to canonical concept families from the concept-authority
catalog. Each binding entry declares:

- `scope`: a dot-delimited field path identifying the bound vocabulary surface
  (e.g. `capabilities.provisioner.supported_node_types`)
- `family`: a concept family identifier from the authoritative catalog
  (e.g. `assets`, `identities`, `tools-and-artifacts`)

This is the "artifact binding layer" described in ADR-012. It prevents
artifact-local strings from becoming de facto semantics by explicitly declaring
which concept family each vocabulary surface belongs to.

The field is required with at least one binding entry. Duplicate scopes within a
single manifest are rejected. Family identifiers must resolve against the
authoritative `concept-families-v1` catalog, and scope paths must resolve to a
governed vocabulary field that is actually declared in the manifest.

Generation or sync helpers may exist under `tools/`, but those helpers are
supporting repo machinery, not the authority boundary.
