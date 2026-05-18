# Specs

`specs/` is the home for normative prose under the
[ACES SDL authority boundary](authority/authority-boundary.yaml). Every
document under this directory is authoritative independent of any reference
implementation or code-generation pipeline.

## Authority Manifest

The canonical machine-readable manifest of which roots carry which authority
lives at:

- [`specs/authority/authority-boundary.yaml`](authority/authority-boundary.yaml)
  — canonical authority manifest (ASR-517)

The decisions that govern this manifest:

- [ADR-009](../docs/decisions/adrs/adr-009-normative-artifact-authority-and-repository-structure.md)
  — the authority decision (immutable)
- [ADR-019](../docs/decisions/adrs/adr-019-normative-authority-boundary-manifest.md)
  — the canonical-seam decision that governs the manifest YAML

Drift between the YAML, ADR-009, ADR-019, and this README is guarded by
[`tools/check_authority_boundary.py`](../tools/check_authority_boundary.py),
which runs in `nox -s policy` (and therefore in `verify` and the pre-push
hook).

## Subdirectories

- `authority/` — the canonical authority-boundary manifest
- `concept-authority/` — concept-family and controlled-vocabulary
  authority artifacts (governed by ADR-012)
- `formal/` — optional formal-methods artifacts for semantic and
  stateful subsystems (governed by ADR-007 and ADR-018)
