# Contracts

`contracts/` contains the machine-readable contract side of the repository.

The goal of this bucket is organizational clarity:

- `schemas/` contains published contract schemas
- `fixtures/` contains valid and invalid payload corpora for those contracts
- `profiles/` contains capability profile declarations

`schema-publication-manifest.json` is the authoritative publication inventory
for the current machine-readable schema set. The contracts verification gate
checks that every entry points at `contracts/schemas/`, that every listed schema
exists, and that every JSON Schema file under `contracts/schemas/` is listed.

These assets are intentionally language-neutral. Any conformance runners or
implementation-specific validation helpers belong under `implementations/`,
not here.

At the architecture level, the contract space spans more than just backend I/O.
It includes:

- processor-facing contracts and manifests
- backend-facing contracts and manifests
- participant-implementation declaration surfaces
- live runtime/control-plane contracts
- experiment, evidence, and provenance artifact boundaries

Not every one of those surfaces is fully materialized in published schemas yet,
but they share the same language-neutral contract discipline.

This split follows the repository-structure decision captured in
[ADR-009](../docs/decisions/adrs/adr-009-normative-artifact-authority-and-repository-structure.md).

The canonical machine-readable manifest of the authority boundary
(ASR-517) lives at
[`specs/authority/authority-boundary.yaml`](../specs/authority/authority-boundary.yaml),
governed by
[ADR-019](../docs/decisions/adrs/adr-019-normative-authority-boundary-manifest.md)
and enforced by `tools/check_authority_boundary.py`.
