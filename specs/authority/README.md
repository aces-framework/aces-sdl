# Authority Boundary

This directory contains the canonical machine-readable manifest of the
normative-artifact authority boundary that
[ADR-009](../../docs/decisions/adrs/adr-009-normative-artifact-authority-and-repository-structure.md)
decided in prose.

## Files

- [`authority-boundary.yaml`](authority-boundary.yaml) — canonical manifest
  for ASR-517. Enumerates each normative authority root (`specs/`,
  `contracts/schemas/`, `contracts/fixtures/`, `contracts/profiles/`,
  `contracts/concept-authority/`), each non-normative root
  (`implementations/`, `docs/`, `examples/`, `research/`, `notes/`,
  `tools/`, `changelog.d/`), the legacy top-level directories ADR-009
  transitioned out (`schemas/`, `conformance/`, `src/`), and the
  schema-authority direction (no published schema may live under
  `implementations/`).

## Governance

- [ADR-009](../../docs/decisions/adrs/adr-009-normative-artifact-authority-and-repository-structure.md)
  — authority decision (immutable)
- [ADR-019](../../docs/decisions/adrs/adr-019-normative-authority-boundary-manifest.md)
  — canonical-seam decision that governs the YAML
- [`tools/check_authority_boundary.py`](../../tools/check_authority_boundary.py)
  — structural gate; wired into `nox -s policy`
- [`docs/explain/reference/normative-artifact-authority.md`](../../docs/explain/reference/normative-artifact-authority.md)
  — contributor-facing guardrails note
