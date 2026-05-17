# ADR-018: Canonical Mapping for the Classification-Based Assurance Policy

## Status

accepted

## Date

2026-05-17

## Context

[ADR-007](adr-007-lightweight-formal-methods-policy.md) adopted the
classification-based assurance policy: structural changes get unit tests; static
semantic changes add invariants; graph/constraint changes add typed IR/contract
coverage; stateful/control changes add an abstract state-machine model. The
ladder is named `FM0`/`FM1`/`FM2`/`FM3`.

ASR-505 in the requirement inventory says the ecosystem **shall** define this
policy and map structural, semantic, graph, and stateful changes to
proportionate verification artifacts. The policy itself is defined in ADR-007
and the contributor-facing
[coding standards](../../explain/reference/coding-standards.md). The mapping is
satisfied in prose.

However, the same ladder is also described in
[docs/specs/formal.md](../../specs/formal.md), and the prose has already
drifted: that overview page labels `FM2` "dynamic semantic rules" and `FM3`
"cross-system contracts" rather than ADR-007's
"Semantic Graph / Constraint" and "Stateful / Control Semantics". Adding a new
artifact type, a new `FM4`, or a new in-repo consumer today requires updating
three independent prose surfaces and hoping none drift again. The architecture
preflight on this work specifically called out the seam: keep the mapping
data-driven or table-like so a future extension is a single-file edit.

## Decision

Establish a single canonical machine-readable surface for the classification-
based assurance policy, alongside (not replacing) ADR-007's prose policy
decision:

1. **Canonical YAML.** `specs/formal/assurance-policy.yaml` enumerates each
   `FM` level with `id`, `name`, `scope`, `change_categories`,
   `required_artifacts`, and (for `FM0`) `prohibited_artifacts`. It names
   ASR-505 in `requirement_refs` and ADR-007 / ADR-018 in `adr_refs`.

2. **Structural gate.** `tools/check_assurance_policy.py` validates the YAML's
   shape (every canonical level present, in canonical order, with the required
   fields), enforces proportionality (`FM2`'s required artifacts are a
   superset of `FM1`'s; `FM3`'s of `FM2`'s), enforces `FM0`'s prohibition on
   TLA+ and Alloy, requires the change-category union to cover every word in
   the ASR-505 statement (`structural`, `semantic`, `graph`, `stateful`), and
   guards against drift by confirming ADR-007, `coding-standards.md`, and
   `docs/specs/formal.md` each still mention every canonical level id. The
   checker is wired into the `policy` nox session and into `verify`, so it
   runs in every CI invocation.

3. **ADR-007 remains the policy decision.** ADRs are immutable. ADR-018 does
   not supersede ADR-007; it codifies the canonical seam that satisfies
   ASR-505 against an already-decided policy. Downstream documents now point
   at the canonical YAML as the source of truth and at ADR-007 as the policy
   origin.

4. **Doc realignment as part of this ADR's landing PR.** The drift between
   `docs/specs/formal.md` and ADR-007 is fixed (the overview now uses ADR-007's
   level names) so the new drift guard does not flag a pre-existing issue.

## Consequences

### Positive

- A future `FM4` or a new artifact type is a single edit to the canonical YAML
  plus a brief mention in each downstream doc; the drift guard catches any
  consumer that forgets to update.
- The policy is consumable by tooling (CI, code generators, future requirement
  governance) without screen-scraping prose.
- The structural gate runs in every CI pipeline, so the policy cannot rot
  silently.
- ASR-505 has a concrete artifact of record (the YAML plus the validator) and
  can transition out of DRAFT.

### Negative

- One more policy gate in the `policy` nox session and the pre-push hook.
- Editors of ADR-007, the coding standards, or the formal-specs overview must
  remember to keep the level ids referenced verbatim (the drift guard fires
  otherwise).

### Risks

- If a future change relabels the levels in ADR-007 (which is immutable but
  conceivably superseded), the YAML and the drift guard must be updated in
  lockstep. The drift guard fails loudly when this happens; it is a feature.
- The proportionality invariant (`FM1` ⊆ `FM2` ⊆ `FM3`) assumes the ladder
  remains monotonically additive. A future policy that introduces an
  alternative branch instead of an inheritance chain will need to revisit the
  validator's superset check.
