# Shared Semantic Integrity

This note is the implementation-facing architecture preflight for `SEM-200`.
The guardrails below are guidance, not an implementation plan.

[ADR-016](../../decisions/adrs/adr-016-semantic-layer-scope-and-coverage-model.md)
fixes the *model* for `SEM-200` — the seven canonical lifecycle phases, the
construct-family concept, the status vocabulary, and `SEM-200`'s definition of
done — and is immutable once accepted. The *live* coverage table is the
[`## Coverage Model`](#coverage-model) section at the end of this note, which
ADR-016 governs; every `SEM-2xx` implementation PR moves its construct family's
row toward `active` there. The structural gate `tools/check_semantic_coverage.py`
validates that table on every `nox` policy run.

`SEM-200` is broader than concept authority alone. It covers whether scenario
constructs keep the same meaning across authoring, validation, instantiation,
compilation, planning, execution, live observation, and later experiment
interpretation. The implementation should extend the existing semantic
authority stack rather than introduce another one.

## Lifecycle Boundary

The current canonical lifecycle is:

1. authored SDL YAML is parsed into closed SDL models
2. `SemanticValidator` enforces static SDL semantics and collects all authoring
   errors
3. `instantiate_scenario()` applies parameters/defaults, rejects unresolved
   placeholders, rebuilds a concrete `InstantiatedScenario`, and reruns
   semantic validation
4. `compile_runtime_model()` emits canonical runtime addresses, typed runtime
   resources, and compiled result/execution contracts
5. `plan()` validates backend capability semantics and derives typed
   provisioning, orchestration, and evaluation plans
6. `RuntimeManager` and `RuntimeControlPlane` accept only plan/result/snapshot
   data that passes the published contract and compiled semantic gates
7. live observation and interpretation consume runtime snapshot, result,
   history, participant-episode, evidence, provenance, and profile surfaces
   rather than backend-native objects

Each phase may add structure, but it must not reinterpret an upstream
construct by local convention.

## Canonical Incumbents

Use these existing surfaces before adding anything new:

- SDL shape and local parsing: `aces_sdl.SDLModel`, parser key normalization,
  variable-key rejection, and `SDLParseError`
- static SDL validation: `SemanticValidator` and `SDLValidationError`
- instantiation: `instantiate_scenario()` and `SDLInstantiationError`
- shared SDL semantics: `aces_sdl.semantics.objectives` and
  `aces_sdl.semantics.workflow`
- runtime graph semantics: `aces_processor.semantics.planner`
- runtime diagnostics: `aces_processor.models.Diagnostic`
- contract boundaries: `aces_contracts.contracts.ContractModel`,
  `schema_bundle()`, generated `contracts/schemas/`, and fixture validation
- concept authority: `contracts/concept-authority/`,
  `specs/concept-authority/`, `aces_contracts.vocabulary`,
  `manifest_authority`, `controlled_vocabularies`, `reference_models`, and
  `semantic_profiles`
- backend and processor declarations: shared `v2` apparatus manifests with
  required `concept_bindings`, controlled vocabulary checks, supported contract
  authority checks, and realization-support disclosures
- live control plane: `control_plane_security`, `control_plane_api`,
  `RuntimeControlPlane`, and `ControlPlaneStore`
- formal-methods policy: ADR-007, the coding standards, and the existing
  `specs/formal/<domain>/` artifacts

## Cross-Cutting Gates

A SEM-200 implementation must pass every gate it touches:

- SDL parser gate: user-defined symbol keys stay concrete; `${var}` may only
  substitute values, not create or rename semantic identities.
- SDL model gate: Pydantic models remain closed where the repo already uses
  `extra="forbid"`; new construct shape belongs in owning SDL models, not
  untyped `dict` side channels.
- semantic validation gate: fail closed on missing, ambiguous, cyclic, or
  out-of-scope references; collect errors through the existing validation
  exception instead of adding a new hierarchy.
- instantiation gate: concrete scenarios must rerun semantic validation after
  parameter/default substitution.
- contract gate: external payloads use `ContractModel`, published schema
  generation, fixtures, and `tools/check_json_artifacts.py`; do not edit
  `contracts/schemas/` directly.
- manifest/profile gate: supported contract versions, SDL versions, concept
  families, binding scopes, controlled vocabulary terms, and semantic profile
  phases must resolve through the existing authority helpers.
- compiler/planner gate: canonical addresses, objective-window semantics,
  workflow state contracts, and planner dependency semantics must come from the
  shared helpers, not copied local algorithms.
- backend boundary gate: backend exceptions and invalid payloads become
  structured `Diagnostic` values; live results are validated against compiled
  contracts before they enter snapshots.
- HTTP/control-plane gate: request bodies are size-limited, authenticated,
  authorized by role, audited, idempotency-fingerprinted, and returned through
  published response models; internal errors stay redacted.
- persistence gate: snapshots, operation records, and audit events are
  plain-data envelopes. Do not store bearer tokens, secrets, raw credentials,
  or backend-private objects in metadata, details, diagnostics, or evidence
  references.
- host/OS exposure gate: secrets and bearer tokens must not be passed in
  command-line arguments, tracebacks, logs, audit `details`, semantic profile
  artifacts, or scenario text. Runtime adapters should receive them through
  headers or process-local configuration that is not echoed into diagnostics.

## Extension Point

The primary extension point is the governed semantic surface, not a new
parallel model:

- add a pure shared helper when the same rule must be consumed by validation,
  compilation, planning, runtime validation, or tests
- add concept families only when meaning must be shared across artifacts
- add reference models only for recurrent shared structure
- add controlled vocabularies only when portable value comparison matters
- add semantic profile declarations when existing concept, contract, binding,
  and behavior assumptions must be composed for an interoperable stack
- add new profile phases or governed binding scopes only at the profile/schema
  authority layer, not as hard-coded one-off checks in a caller

Live observation and experiment interpretation should extend from runtime
snapshot/result/history, participant-episode, evidence, provenance, and
semantic-profile contracts. They should not overload evaluator `detail`,
backend manifest strings, or profile selectors as hidden authority surfaces.

## Guardrails

- Keep concept authority, reference structure, controlled vocabulary values,
  semantic profiles, SDL syntax, runtime contracts, and backend capability
  profiles separate.
- Treat `scenario-instantiation-request-v1.profile` as a selector until a
  governed semantic profile contract gives it stronger meaning.
- Preserve canonical identity semantics through composition/import expansion;
  downstream phases should see resolved identities, not source-file layout.
- Keep authoring, processing, execution, live observation, and interpretation
  meanings aligned through tests that compare the same construct across stages.
- Use the smallest adequate formal-methods artifact for the changed surface.
  FM2/FM3 changes need explicit invariants and typed IR/contract coverage.

## Anti-Patterns

Avoid:

- a second semantic registry beside concept authority and semantic profiles
- direct edits to generated schemas under `contracts/schemas/`
- duplicating SDL validation logic inside compiler, planner, conformance, or
  backend adapters
- raw string parsing where an existing structured model or helper exists
- treating backend-native payloads as the portable observation contract
- treating semantic profiles as backend capability profiles
- treating controlled vocabularies as concept definitions
- treating UCO or another ontology as the authoring syntax
- adding SEM-200-specific exception, logging, audit, persistence, or schema
  stacks
- writing raw secrets, tokens, credentials, or full backend tracebacks into
  diagnostics, audit records, snapshots, or JSON fixtures
- solving the requirement by creating one universal scenario super-model

## Non-Goals

The preflight guardrails above do not implement the missing `SEM-200` coverage,
add new schemas, add new construct-specific tests, or transition the requirement
status. They only fix the architectural guardrails for the implementation that
follows. The Coverage Model below is the inventory and tracker; closing each
`planned`/`partial` row is its own `/implement <child-UID>` run.

## Coverage Model

This is the live, ADR-016-governed coverage table for `SEM-200`. It is mutable
— each `SEM-2xx` implementation PR updates the affected row — and validated by
the structural gate `tools/check_semantic_coverage.py`.

Lifecycle phases (canonical, fixed, per ADR-016): `authoring`, `validation`,
`instantiation`, `compilation`, `planning`, `execution`, `observation`.

Status is one of:

- `active` — the owning requirement is `ACTIVE` in Ground Control; the
  construct's semantics are realized in a shared helper/spec; named tests cover
  it. The structural gate enforces that the row names at least one lifecycle
  phase, at least one *existing* non-test repository artifact, and at least one
  *existing* test under `implementations/python/tests/test_*.py`; whether the
  owning requirement is actually `ACTIVE` is a Ground Control fact verified by
  requirement-governance review, not by the gate.
- `partial` — some realization exists (a spec, a helper) but the owning
  requirement is still `DRAFT` or the coverage is incomplete. The gate enforces
  at least one phase and at least one existing non-test repository artifact.
- `planned` — no realization yet; owned by a `DRAFT` requirement; future work.
  Phases and artifacts are left as `—`; the gate enforces that they stay empty.
  For a `planned` row, the construct family's intended lifecycle scope, future
  artifact, and wave are defined by the owning requirement's record in Ground
  Control (its statement and `wave` field) — this table tracks realization
  status, not the requirement database, and deliberately carries no wave column.

A construct family appears here only if its cross-stage *meaning* can drift, and
only if a `SEM-2xx` child of `SEM-200` (or, for a foundational/peer concern such
as the concept-authority meta-layer or the runtime/contract layers, an owning
peer requirement that is already `ACTIVE`) accounts for it. Pure SDL
data-modeling constructs (topology, features, content, exercise timeline, …) get
their cross-stage integrity from fail-closed validation (`SEM-201`), canonical
identities (`SEM-205`), and the compiled representation (`RUN-302`), so they have
no row of their own unless a construct-specific semantic gap is later identified
and a `SEM-*` requirement opened for it. Higher-level capabilities that *consume*
the semantic layer (cross-run comparability, semantic diff, federation/standards
profiles, …) are downstream of `SEM-200` rather than construct families of it,
so they are tracked by their own requirements, not here.

| Construct family | Owning requirement(s) | Phases covered | Realizing artifacts | Status |
| --- | --- | --- | --- | --- |
| Fail-closed semantic validation (cross-cutting gate) | SEM-201 | validation, instantiation | `implementations/python/packages/aces_sdl/validator.py`, `implementations/python/packages/aces_sdl/instantiate.py`, `implementations/python/tests/test_sdl_validator.py` | active |
| Stable identifiers, parameterized values, and qualified references | DSL-101, DSL-102, SEM-205 | authoring, validation, instantiation, compilation, planning, observation | `implementations/python/packages/aces_sdl/parser.py`, `implementations/python/packages/aces_sdl/variables.py`, `implementations/python/packages/aces_sdl/validator.py`, `implementations/python/tests/test_sdl_parser.py`, `implementations/python/tests/test_sdl_validator.py` | active |
| Deterministic module composition and canonical-identity stability across expansion | DSL-103, SEM-205 | authoring, validation, compilation | `implementations/python/packages/aces_sdl/composition.py`, `implementations/python/packages/aces_sdl/module_registry.py`, `specs/formal/composition-readiness.md`, `implementations/python/tests/test_sdl_module_registry.py` | active |
| Instantiation and revalidation of concrete scenarios | RUN-301 | instantiation, validation | `implementations/python/packages/aces_sdl/instantiate.py`, `implementations/python/tests/test_sdl_validator.py`, `implementations/python/tests/test_run_300_lifecycle.py` | active |
| Objective windows, referenced scopes, reachability, and refresh | SEM-202 | validation, compilation, planning | `implementations/python/packages/aces_sdl/semantics/objectives.py`, `specs/formal/objectives/README.md`, `specs/formal/objectives/window-consistency.md`, `implementations/python/tests/test_semantics_objectives.py`, `implementations/python/tests/test_fm2_semantics.py` | active |
| Declarative objective actor binding, target resolution, success interpretation, and dependency ordering | DSL-112, SEM-207 | authoring, validation, instantiation, compilation, planning | `implementations/python/packages/aces_sdl/objectives.py`, `implementations/python/packages/aces_sdl/semantics/objective_semantics.py`, `implementations/python/packages/aces_sdl/validator.py`, `implementations/python/packages/aces_processor/compiler.py`, `implementations/python/packages/aces_processor/models.py`, `specs/formal/objectives/README.md`, `specs/formal/objectives/declarative-objective-semantics.md`, `implementations/python/tests/test_semantics_objectives.py`, `implementations/python/tests/test_fm2_semantics.py`, `implementations/python/tests/test_sdl_validator.py` | active |
| Workflow control semantics (branching, joins, calling, retry, completion, history) | DSL-113, SEM-203 | authoring, validation, compilation, planning, execution, observation | `implementations/python/packages/aces_sdl/orchestration.py`, `implementations/python/packages/aces_sdl/semantics/workflow.py`, `specs/formal/workflows/README.md`, `specs/formal/workflows/state-machine.md`, `implementations/python/tests/test_sdl_validator.py`, `implementations/python/tests/test_runtime_models.py` | active |
| Workflow compensation semantics (registration, triggering, ordering, observation) | SEM-204 | validation, compilation, execution, observation | `implementations/python/packages/aces_sdl/semantics/workflow.py`, `specs/formal/workflows/compensation.md`, `implementations/python/tests/test_sdl_validator.py`, `implementations/python/tests/test_runtime_manager.py` | active |
| Assessment model and pipeline semantics (conditions, metrics, evaluations, TLOs, goals) | DSL-110, SEM-206 | authoring, validation, compilation, planning, execution, observation | `implementations/python/packages/aces_sdl/scoring.py`, `implementations/python/packages/aces_sdl/conditions.py`, `implementations/python/packages/aces_sdl/semantics/assessment.py`, `implementations/python/packages/aces_processor/compiler.py`, `implementations/python/packages/aces_processor/models.py`, `specs/formal/assessment/README.md`, `specs/formal/assessment/pipeline-consistency.md`, `implementations/python/tests/test_semantics_assessment.py`, `implementations/python/tests/test_sdl_models.py`, `implementations/python/tests/test_fm2_semantics.py` | active |
| Runtime compiled representation and canonical addresses | RUN-302 | compilation | `implementations/python/packages/aces_processor/compiler.py`, `implementations/python/tests/test_runtime_models.py`, `implementations/python/tests/test_fm2_semantics.py` | active |
| Planner dependency, ordering, refresh, and applicability semantics | RUN-303 | planning | `implementations/python/packages/aces_processor/semantics/planner.py`, `implementations/python/packages/aces_processor/planner.py`, `specs/formal/planner/README.md`, `specs/formal/planner/dependency-ordering.md`, `implementations/python/tests/test_semantics_planner.py`, `implementations/python/tests/test_runtime_planner.py` | active |
| Live execution state and lifecycle (snapshots, results, history) | RUN-304, API-402 | execution, observation | `implementations/python/packages/aces_processor/manager.py`, `implementations/python/packages/aces_processor/models.py`, `implementations/python/tests/test_runtime_manager.py`, `implementations/python/tests/test_runtime_models.py` | active |
| Runtime result and evaluator-result contracts | ASR-503, API-402 | execution, observation | `specs/formal/runtime-contracts/README.md`, `specs/formal/runtime-contracts/workflow-results.md`, `specs/formal/runtime-contracts/evaluator-results.md`, `implementations/python/tests/test_runtime_contracts.py` | active |
| Control-plane semantics (auth, durable state, idempotency, audit) | API-403, API-404 | execution, observation | `implementations/python/packages/aces_processor/control_plane_api.py`, `implementations/python/packages/aces_processor/control_plane_security.py`, `implementations/python/packages/aces_processor/control_plane_store.py`, `implementations/python/tests/test_runtime_control_plane.py`, `implementations/python/tests/test_runtime_control_plane_api.py` | active |
| Backend and processor identity, capability, and compatibility manifests | API-401, API-412 | planning, execution | `implementations/python/packages/aces_processor/manifest.py`, `implementations/python/packages/aces_processor/capabilities.py`, `implementations/python/packages/aces_contracts/apparatus.py`, `implementations/python/packages/aces_contracts/manifest_authority.py`, `implementations/python/tests/test_backend_manifest.py`, `implementations/python/tests/test_processor_manifest.py` | active |
| Concept authority, controlled vocabularies, reference models, and semantic profiles (meta-layer) | GOV-920 | authoring, validation, compilation, planning, execution | `specs/concept-authority/concept-authority.md`, `specs/concept-authority/semantic-profiles.md`, `implementations/python/packages/aces_contracts/semantic_profiles.py`, `implementations/python/packages/aces_contracts/controlled_vocabularies.py`, `implementations/python/packages/aces_contracts/reference_models.py`, `docs/explain/reference/shared-concept-model.md`, `implementations/python/tests/test_concept_authority.py`, `implementations/python/tests/test_semantic_profiles.py` | active |
| Participant episode lifecycle boundaries (initialization, reset, completion, timeout, truncation, interruption) | RUN-311, SEM-222 | execution, observation | `docs/decisions/adrs/adr-013-participant-episode-lifecycle-boundaries.md`, `implementations/python/tests/test_run_311_participant_episode_lifecycle.py` | partial |
| Declarative participant framing (identity, role, starting conditions, authority anchors, operating scope) | ACT-601 | authoring, validation | `implementations/python/packages/aces_sdl/agents.py`, `implementations/python/packages/aces_sdl/validator.py`, `docs/decisions/adrs/adr-020-declarative-participant-framing-boundaries.md`, `implementations/python/tests/test_sdl_models.py`, `implementations/python/tests/test_sdl_validator.py` | active |
| Participant behavior semantics (actions, observations, state transitions) | ACT-602, SEM-208 | authoring, validation, compilation, planning, execution, observation | `specs/formal/participant-semantics/README.md`, `docs/decisions/adrs/adr-022-participant-behavior-and-interaction-semantics.md` | partial |
| Multi-participant interaction, visibility, and information-boundary semantics | SEM-209, SEM-210, SEM-226 | authoring, validation, compilation, planning, execution, observation | `specs/formal/participant-semantics/README.md`, `docs/decisions/adrs/adr-022-participant-behavior-and-interaction-semantics.md` | partial |
| Participant preconditions, effects, failure, causality, and attribution semantics | SEM-211, SEM-212 | authoring, validation, compilation, planning, execution, observation | `specs/formal/participant-semantics/README.md`, `docs/decisions/adrs/adr-022-participant-behavior-and-interaction-semantics.md` | partial |
| Participant temporal, tool/affordance, and decision-surface semantics | SEM-213, SEM-219, SEM-220 | authoring, validation, compilation, planning, execution, observation | `specs/formal/participant-semantics/README.md`, `docs/decisions/adrs/adr-022-participant-behavior-and-interaction-semantics.md` | partial |
| Participant reference trajectories, demonstrations, budgets, and quota/exhaustion semantics | SEM-221, SEM-223 | — | — | planned |
| Participant outcome interpretation and derived operational context views | SEM-214, SEM-215 | authoring, validation, compilation, planning, execution, observation | `specs/formal/participant-semantics/README.md`, `docs/decisions/adrs/adr-022-participant-behavior-and-interaction-semantics.md` | partial |
| Evidence, evaluation, view-boundary, and observability-plane semantics | SEM-216, SEM-224, SEM-225 | — | — | planned |
| External knowledge bindings semantics | SEM-217 | — | — | planned |
| Explicitness and realization semantics (binding declarations vs processor/backend realization) | SEM-218 | validation | `specs/formal/realization/explicitness-and-realization.md`, `specs/formal/realization/README.md`, `docs/explain/reference/explicitness-realization-semantics.md`, `implementations/python/packages/aces_contracts/apparatus.py`, `implementations/python/packages/aces_contracts/vocabulary.py`, `implementations/python/packages/aces_contracts/contracts.py`, `implementations/python/packages/aces_backend_protocols/manifest.py`, `implementations/python/tests/test_backend_manifest.py`, `implementations/python/tests/test_processor_manifest.py`, `implementations/python/tests/test_runtime_contracts.py` | partial |
| Clock, time-domain, advancement/pacing/synchronization, and temporal ordering/causality semantics | SEM-227, SEM-228, SEM-229 | — | — | planned |
