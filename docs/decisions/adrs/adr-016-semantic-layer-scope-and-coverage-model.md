# ADR-016: Semantic Layer Scope and Coverage Model (SEM-200)

## Status

accepted

## Date

2026-05-10

## Context

`SEM-200` ("Shared Semantic Integrity") is a system-level umbrella requirement.
In the Ground Control graph it is a child of `SYS-001` ("ACES SDL Ecosystem"),
it `DEPENDS_ON` `DSL-100` ("Author-Facing Scenario Language"), and it is the
**parent** of roughly twenty-eight `SEM-2xx` child requirements — the construct
families. A number of other requirements (across the experiment `EXP-*`,
autonomy `AUT-*`, governance `GOV-*`, assurance `ASR-*`, and a few API/runtime
requirements) `DEPENDS_ON` `SEM-200`: they are downstream consumers of the
shared semantic layer, not prerequisites for it, and they do **not** gate
`SEM-200`'s transition. Its statement —
*"the ecosystem shall provide a shared semantic layer that gives scenario
constructs explicit, consistent meaning across validation, instantiation,
compilation, planning, execution, live observation, and experiment
interpretation"* — is satisfied only when its `SEM-2xx` children are satisfied
and the cross-stage agreement that ties them together is checkable. It is
therefore not a single-pull-request deliverable.

`SEM-201`–`SEM-205` are `ACTIVE` (fail-closed semantic validation, objective
windows, workflow control, workflow compensation, canonical identities) — the
"pilot domains" the originating issue (#4) names. The remaining `SEM-2xx`
children and several adjacent requirements are `DRAFT`, spread across Waves 1,
2, 3, and unassigned. Issue #4 itself records this state and asks, as follow-up,
to "define the target semantic-layer scope across all relevant construct
families", "identify uncovered construct domains and lifecycle phases", extend
the shared semantic sources of truth "where needed", add construct-spanning
cross-stage agreement tests, and "only transition `SEM-200` once the umbrella
behavior is explicitly covered beyond the current pilot domains".

This ADR does the first two of those follow-up items — by fixing the *model*
below — and records the rest as the requirement's definition of done. It is the
decision layer; the implementation-facing guardrails (which incumbents to
extend, which gates a change must pass, which anti-patterns to avoid) live in
[`docs/explain/reference/shared-semantic-integrity.md`](../../explain/reference/shared-semantic-integrity.md),
which this ADR governs. It builds on, and does not restate, ADR-007 (lightweight
formal-methods policy and FM0–FM3 classification), ADR-012 (shared concept
authority and ACES extension discipline), ADR-013 (participant-episode lifecycle
boundaries), and ADR-015 (SDL → processor layering).

## Decision

### Lifecycle phases

The shared semantic layer spans seven canonical lifecycle phases, in order.
Every construct family is evaluated against this fixed set; a downstream phase
may *add* structure but must not *reinterpret* an upstream construct by local
convention.

1. **authoring** — authored SDL YAML parsed into closed SDL models (key
   normalization, variable-key rejection, shorthand expansion).
2. **validation** — `SemanticValidator` enforces static SDL semantics
   (references, uniqueness, ambiguity, acyclicity, fail-closed resolution) and
   collects all authoring errors.
3. **instantiation** — `instantiate_scenario()` resolves parameters and
   defaults, rejects unresolved placeholders, rebuilds a concrete
   `InstantiatedScenario`, and reruns semantic validation.
4. **compilation** — `compile_runtime_model()` emits canonical runtime
   addresses, typed runtime resources, and compiled result/execution contracts.
5. **planning** — `plan()` validates backend/processor capability semantics and
   derives typed provisioning, orchestration, and evaluation plans (ordering,
   dependency, refresh, applicability).
6. **execution** — `RuntimeManager` / `RuntimeControlPlane` accept only
   plan/result/snapshot data that passes the published contract and compiled
   semantic gates; control-plane access is authenticated, authorized, durable,
   idempotent, and audited.
7. **observation** — live observation and (later) experiment interpretation
   consume runtime snapshot, result, history, participant-episode, evidence,
   provenance, and semantic-profile surfaces rather than backend-native objects.

### Construct families and the coverage table

`SEM-200`'s scope is a set of *construct families* — the scenario constructs
whose cross-stage *meaning* can drift, and which therefore need shared semantic
treatment. Pure SDL data-modeling constructs (topology, features, content,
exercise timeline, …) are **not** construct families in this sense: their
cross-stage integrity is provided by fail-closed validation (`SEM-201`),
canonical identities (`SEM-205`), and the compiled representation (`RUN-302`),
so they have no entry of their own unless a construct-specific semantic gap is
later identified and a `SEM-*` requirement opened for it.

Each construct family is owned by one or more requirements accountable for its
cross-stage semantics — a `SEM-2xx` child for construct-specific semantics, a
`DSL-*` requirement where the language model is the accountable artifact, or one
of the cross-cutting/peer requirements (`SEM-201`, `SEM-205`, `RUN-301/302/303/304`,
`API-401/402/403/404/412`, `ASR-503`, `GOV-920`, `RUN-311`, …) whose own work
already realizes that family. A peer owner appearing on a row documents that the
construct family is realized; it is not part of `SEM-200`'s transition gate —
only the `SEM-2xx` children are (see the definition of done). Each row is
realized by named artifacts (formal specs under `specs/formal/<domain>/`,
semantic helpers under `aces_sdl.semantics` / `aces_processor.semantics`, the
concept-authority stack under `aces_contracts`, runtime contracts, and the
owning tests), and carries a status of `active` (owning requirement `ACTIVE` in
Ground Control, semantics realized, named tests present), `partial` (some
realization exists but the owning requirement or the coverage is incomplete), or
`planned` (no realization yet; owned by a `DRAFT` requirement; future work). The
structural gate enforces the *artifact-and-test-and-phase existence* implied by
each status (`active` needs an existing test, `active`/`partial` need an existing
non-test artifact and a phase, `planned` needs neither); whether a row's status
truthfully matches the owning requirement's Ground Control state is a governance
fact verified by requirement-governance review, not by the gate.

The **live coverage table** is the `## Coverage Model` section of
[`docs/explain/reference/shared-semantic-integrity.md`](../../explain/reference/shared-semantic-integrity.md),
not this ADR: per `docs/decisions/adrs/README.md`, ADRs are immutable once
accepted, whereas the coverage table is updated by every `SEM-2xx`
implementation PR (it moves that construct family's row from `planned`/`partial`
toward `active`). Keeping the mutable inventory in a governed reference note,
and the fixed model and governance rules here, lets routine implementation work
proceed without an ADR amendment. The structural gate
`tools/check_semantic_coverage.py` validates that table's shape and that every
repository path it names exists, and confirms this ADR still references the
note.

### How per-construct semantics land

Per the guardrails note, future `SEM-200` work *extends the existing semantic
authority stack* rather than introducing a parallel semantic registry: shared
pure helpers, concept families, reference models, controlled vocabularies,
semantic profiles, and runtime/provenance contracts are the extension surfaces.
Each uncovered or partially covered construct family becomes its own
`/implement <child-UID>` run, classified under ADR-007 (typically FM1–FM3), and
ships its formal artifact, semantic helper, validator/compiler/planner wiring,
tests, and the cross-stage agreement coverage for that family, and updates the
coverage table. No `/implement` run claims `SEM-200` itself.

### Definition of done for `SEM-200`

`SEM-200` may transition `DRAFT → ACTIVE` only when **all** of the following
hold:

1. every `SEM-2xx` child requirement of `SEM-200` is `ACTIVE` in Ground Control
   (or explicitly `DEPRECATED` / re-scoped with a recorded decision). The
   `SEM-2xx` children are the umbrella's constituent requirements; the
   cross-cutting/peer requirements that merely *own* a coverage-table row are not
   gating — their being `ACTIVE` is already reflected in that row's status, not
   in this rule. This avoids the circularity that gating on *every* row owner
   would create (some peer owners themselves `DEPENDS_ON` `SEM-200`);
2. no `partial` or `planned` rows remain in the coverage table — every construct
   family is `active`. (A `SEM-2xx` child that is still `DRAFT` shows up as a
   `partial`/`planned` row owned by it, so clauses 1 and 2 reinforce each
   other.);
3. the cross-stage agreement tests (today `implementations/python/tests/test_fm2_semantics.py`,
   which exercises objective-window validator/compiler/planner agreement) are
   extended to cover the other semantic construct families — workflow control,
   compensation, planner ordering, runtime-result contracts, the participant
   families, and so on — end to end across `authoring → validation →
   instantiation → compilation → planning → execution → observation`;
4. the unassigned-wave `SEM-2xx` children (`SEM-219`…`SEM-229`) have been
   assigned to a wave (see Open Questions).

Until then `SEM-200` stays `DRAFT` and is linked to its issue and documents
with `DOCUMENTS` traceability, never `IMPLEMENTS`.

## Consequences

### Positive

- The umbrella becomes tractable: every uncovered construct family has a named
  owning requirement, whose Ground Control record (its statement and `wave`
  field) is the authoritative scope and schedule for closing it — the coverage
  table tracks realization status and does not duplicate the requirement
  database into a column. Progress on `SEM-200` is the sum of bounded
  `/implement <child-UID>` runs rather than an unbounded epic.
- The transition rule is explicit: `SEM-200` is gated by its own `SEM-2xx`
  children plus the no-`partial`/no-`planned`-rows condition, not by an
  open-ended prose dependency list and not by peer requirements that are
  themselves downstream of `SEM-200`.
- The structural part of the coverage claims is machine-checked.
  `tools/check_semantic_coverage.py` fails if a covered row points at an artifact
  that no longer exists or escapes the repo root, if a covered row has no real
  repository artifact behind it, if an `active` row names no existing test, if a
  `planned` row starts claiming realization without an upgraded status, if a
  lifecycle-phase or status token drifts, or if this ADR stops referencing the
  coverage note by path. (The owning requirement's Ground Control status is a
  governance fact reviewed by `check_requirement_governance.py` for the branch's
  own requirement and by review for the rest, not enforced by this gate.) It
  reuses `tools.policy.common.PolicyFailure`, `--json` output, and the shared
  `tools/policy/exceptions.yaml` waiver mechanism, like the other `policy`
  nox-stage entry points.
- ADR immutability is preserved: the fixed model and governance rules are here;
  the mutable inventory is in a reference note this ADR governs.
- It is consistent with ADR-007 (each child is classified and carries the
  proportionate formal artifact) and ADR-012 (work extends the concept-authority
  stack, not a parallel registry).

### Negative

- The coverage table is a living artifact that every `SEM-2xx` implementation
  PR must update (move a row from `planned`/`partial` toward `active`, add the
  new spec/helper/test paths). That is intentional overhead — it is the
  mechanism that keeps the umbrella honest — but it is overhead, and it lives in
  a second file from this ADR.
- The construct-family taxonomy in the note is a snapshot. New primary-source
  review may add families or split existing ones; doing so updates the note, and
  a change to the *model* (phases, statuses, the definition of done) is a new
  ADR superseding this one.

### Risks

- If contributors update a child requirement's prose but not the coverage table,
  the structural gate catches dangling artifact paths and unbacked covered rows
  but not a *missing* row. Definition-of-done clause 1 (every `SEM-2xx` child
  `ACTIVE`) plus requirement-governance review are the backstop.
- The `planned` rows reference `DRAFT` requirements; if a child is later
  re-scoped or merged, the corresponding row must be reconciled. Clause 1's
  "or explicitly `DEPRECATED` / re-scoped with a recorded decision" covers that,
  but it depends on the reconciliation actually happening.

## Open Questions

- `SEM-219`…`SEM-229` (the unassigned-wave `SEM-2xx` children of `SEM-200`)
  currently have no wave assignment in Ground Control. Assigning them is a
  requirement-governance decision (it changes the work order) and is
  intentionally **not** done by the PR that introduced this ADR; it is flagged
  for the maintainers. The coverage rows owned by those requirements are
  `planned` regardless of wave.

## References

- Issue #4 — `SEM-200: Shared Semantic Integrity`
- `docs/explain/reference/shared-semantic-integrity.md` — implementation-facing
  guardrails this ADR governs, and home of the live `## Coverage Model` table
- ADR-007 — Lightweight Formal Methods Policy for Semantic Systems
- ADR-012 — Shared Concept Authority and ACES Extension Discipline
- ADR-013 — Participant Episode Lifecycle Boundaries
- ADR-015 — SDL-Processor Layering and Source-File Size Cap
- `tools/check_semantic_coverage.py` — the structural gate for the coverage
  table and the ADR↔note linkage
