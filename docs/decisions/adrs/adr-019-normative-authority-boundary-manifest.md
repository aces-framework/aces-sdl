# ADR-019: Canonical Manifest for the Normative Artifact Authority Boundary

## Status

accepted

## Date

2026-05-17

## Context

[ADR-009](adr-009-normative-artifact-authority-and-repository-structure.md)
decided that the ecosystem's authority boundary separates normative artifacts
(prose under `specs/`, schemas under `contracts/schemas/`, fixtures under
`contracts/fixtures/`, profiles under `contracts/profiles/`, and the shared
concept-authority artifacts under `contracts/concept-authority/`) from
reference implementations (`implementations/`), explanatory docs (`docs/`),
worked examples (`examples/`), research material (`research/`), and tooling
(`tools/`).

ASR-517 in the requirement inventory says the ecosystem **shall** define this
authority boundary **explicitly**. ADR-009 defined the boundary in prose. Per
the architecture preflight on this work, the implementation must not create a
second authority model — instead, codify ADR-009's decision in a single
machine-readable seam so future drift fails the gate instead of compounding
silently across the doc tree.

The same canonical-seam pattern that ADR-018 introduced for ASR-505 applies
here: a single canonical YAML, a structural gate, and the original prose ADR
remains the authority decision.

## Decision

Establish a single canonical machine-readable surface for the normative-
artifact authority boundary, alongside (not replacing) ADR-009's prose
decision:

1. **Canonical YAML.** `specs/authority/authority-boundary.yaml` enumerates
   each normative authority root with `id`, `root`, `authority`, and
   `family`. It pins the five canonical families ADR-009 names:

   - `prose` under `specs/`
   - `schemas` under `contracts/schemas/`
   - `fixtures` under `contracts/fixtures/`
   - `profiles` under `contracts/profiles/`
   - `concept-authority` under `contracts/concept-authority/`

   It also enumerates each non-normative root (`implementations/`, `docs/`,
   `examples/`, `research/`, `notes/`, `tools/`, `changelog.d/`), the
   legacy top-level directories ADR-009 transitioned out (`schemas`,
   `conformance`, `src`), and a `schema_authority` block that pins the
   normative schema root, the publication manifest path, and the codegen
   direction (reference implementations may not own published schemas).

2. **Structural gate.** `tools/check_authority_boundary.py` validates the
   YAML's shape (every canonical family present; every entry well-formed),
   confirms that every declared root exists on disk, refuses any legacy
   top-level directory that has reappeared at the repo root, refuses any
   unclassified top-level directory (closing the "new bucket appeared and
   nobody updated the manifest" gap), refuses any `*.schema.json` file under
   `implementations/` (closing the codegen-direction loophole at the
   file-system layer), and guards against drift by confirming ADR-009 (or
   this ADR, ADR-019) still mentions every family token, and that
   `contracts/README.md` and `specs/README.md` still reference the canonical
   YAML and this ADR. The checker is wired into the `policy` nox session and
   into `verify`, so it runs in every CI invocation.

3. **ADR-009 remains the authority decision.** ADRs are immutable. ADR-019
   does not supersede ADR-009; it codifies the canonical seam that satisfies
   ASR-517 against an already-decided authority model. Downstream documents
   now point at the canonical YAML as the source of truth and at ADR-009 as
   the authority decision.

4. **Drift guard's union of ADR-009 and ADR-019.** The structural gate
   checks each authority family's token against the union of ADR-009 and
   ADR-019. ADR-009 names the four authority families it introduced
   (`prose`, `schemas`, `fixtures`, `profiles`); ADR-012 introduced the
   `concept-authority` family later. To keep the drift guard self-contained
   without requiring an edit to ADR-012 every time the manifest changes,
   this ADR-019 explicitly names the `concept-authority` family in its
   decision text (above) so the union covers all five.

## Consequences

### Positive

- Adding a future normative family (e.g. canonical run-provenance artifacts)
  is a single edit to the canonical YAML plus a brief mention in ADR-009 or
  ADR-019; the drift guard catches any downstream doc that forgets to update.
- The boundary is consumable by tooling (CI, requirement governance, future
  authority-tracking analyzers) without screen-scraping prose.
- The structural gate runs in every CI pipeline, so the boundary cannot rot
  silently — a new top-level directory appears unclassified, a schema appears
  in `implementations/`, or a legacy `schemas/` directory reappears at the
  repo root, and the gate fails the PR.
- ASR-517 has a concrete artifact of record (the YAML plus the validator)
  and can transition out of DRAFT.

### Negative

- One more policy gate in the `policy` nox session and the pre-push hook.
- Future contributors who introduce a new top-level directory must classify
  it (authority, non-normative, or legacy) in the canonical YAML and update
  ADR-009 or ADR-019 (the immutable ADR pair) if they introduce a new
  authority family.

### Risks

- If a future repository reorganization moves a normative family to a new
  root, both this YAML and the cross-referencing READMEs must be updated in
  lockstep. The drift guard fails loudly when this happens; it is a feature.
- The structural gate enforces today's family set. A future supersedure of
  ADR-009 must update `CANONICAL_AUTHORITY_ROOT_IDS` in
  `tools/check_authority_boundary.py` alongside the YAML edit. This is the
  same pattern ADR-018's gate uses, and it surfaces in test coverage.
