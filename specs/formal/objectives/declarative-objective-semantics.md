# Declarative Objective Semantics

## Scope

This note defines the shared semantic boundary for `SEM-207`.

Objective semantics are declarative SDL meaning. They answer:

- which declared actor owns the objective
- which declared scenario elements the objective names as targets
- which assessment resources define success
- which window bounds when the objective matters
- which other objectives must precede it

They do not choose participant implementations, backend probes, evaluator
queries, execution adapters, prompts, credentials, polling loops, or live
control-plane behavior.

## Canonical Inputs

The implementation must build on these existing authorities:

- SDL structure: `aces_sdl.objectives.Objective`,
  `ObjectiveSuccess`, and `ObjectiveWindow`
- parser/model gates: `SDLModel`, parser key normalization, variable-key
  rejection, and `SDLParseError`
- static validation: `SemanticValidator` and `SDLValidationError`
- objective-window analysis: `aces_sdl.semantics.objectives`
- assessment pipeline semantics: `aces_sdl.semantics.assessment`
- runtime compilation: `compile_runtime_model()` and
  `aces_processor.models.ObjectiveRuntime`
- dependency graph semantics: `aces_processor.semantics.planner`
- runtime diagnostics: `aces_processor.models.Diagnostic`
- contract/schema authority: `aces_contracts.contracts.ContractModel`,
  generated `contracts/schemas/`, and fixture validation
- concept/profile authority: `contracts/concept-authority/`,
  `specs/concept-authority/`, controlled vocabularies, reference models, and
  semantic profiles

## Required Semantics

Actor binding:

- an objective has exactly one actor binding: `agent` or `entity`
- `agent` resolves only to the SDL `agents` section
- `entity` resolves only to flattened SDL entities
- an actor binding is not a participant implementation binding
- agent action checks reuse the declaring agent's `actions` list

Target resolution:

- targets resolve through the existing targetable named-reference index
- target resolution remains fail-closed for missing or ambiguous references
- target meaning does not create runtime deployment dependencies unless a
  separately defined runtime contract says so
- targets must not include objectives, workflows, variables, secrets, or
  backend-private objects through a side channel

Success interpretation:

- success references only declared conditions, metrics, evaluations, TLOs, and
  goals
- the assessment pipeline remains the authority for upstream ordering and
  refresh dependencies among those resources
- objective success mode describes interpretation of referenced success
  resources; it must not encode evaluator implementation mechanics
- runtime result and execution contracts remain the portable observation
  boundary for evaluated success

Windows:

- window reference parsing, reachability, consistency, and refresh dependency
  derivation come from `aces_sdl.semantics.objectives`
- implementation must not duplicate window rules in validator, compiler,
  planner, or tests

Dependency ordering:

- `depends_on` is an objective-to-objective ordering relation
- the relation is acyclic and fail-closed
- compiled objective dependencies use canonical runtime addresses
- planner ordering and refresh behavior reuse
  `aces_processor.semantics.planner`

Dependency roles (which references propagate through the planner):

- success and `depends_on` references carry both ordering and refresh roles
- window references carry only refresh
- actor and target references are normalized for fail-closed validation but
  carry no runtime dependency role today: the compiler does not propagate
  ordering or refresh through actor or target identity, so the analyzer must
  not advertise a role that the planner will never see. A future change that
  compiles actor or target into runtime addresses lifts the role constant in
  lockstep
- the derived per-objective `ordering_names` / `refresh_names` tuples are
  kind-qualified (`condition.<n>`, `metric.<n>`, `evaluation.<n>`, `tlo.<n>`,
  `goal.<n>`, `objective.<n>`, `story.<n>`, `script.<n>`, `event.<n>`,
  `workflow.<n>`) so a metric and a condition with the same SDL name remain
  distinguishable

## Cross-Cutting Gates

The design must satisfy every layer it passes through:

- Parser gate: variable substitution may not create or rename objective,
  actor, target, success, or dependency identities.
- SDL model gate: new objective shape belongs in closed SDL models, not in
  untyped dictionaries.
- Validation gate: missing, ambiguous, cyclic, or out-of-scope references are
  collected through `SDLValidationError`.
- Instantiation gate: concrete scenarios rerun semantic validation after
  substitution/defaulting.
- Compiler gate: canonical addresses and diagnostics are emitted through
  existing compiler helpers and `Diagnostic`.
- Planner gate: ordering and refresh semantics use typed dependency helpers,
  not a local topological-sort variant.
- Contract gate: externally visible payload changes go through contract model
  inputs, generated schemas, and fixtures; generated schemas are not edited
  directly.
- Manifest/profile gate: capability, binding-scope, controlled-vocabulary, and
  semantic-profile checks stay in the existing authority helpers.
- Control-plane gate: live operations stay authenticated, authorized,
  idempotent, audited, size-limited, and redacted by existing control-plane
  surfaces.
- Persistence and host/OS gate: objective metadata, diagnostics, audit events,
  snapshots, process arguments, and logs must not carry bearer tokens, secrets,
  raw credentials, backend-private payloads, or full tracebacks.

## Extensibility Seam

The extensibility seam is the pure objective-semantics helper
`aces_sdl.semantics.objective_semantics.analyze_objective_semantics`: it produces
a normalized objective analysis (`ObjectiveReference` /
`ObjectiveResourceDependencies` / `ObjectiveSemanticAnalysis`) reused by
validation, compilation, planning, and agreement tests, parameterized by the
existing authorities it needs — the agent/entity indexes, the
targetable-reference index, the assessment-resource indexes, the objective
index, and the window-analysis inputs. The ordering/refresh-role decision is the
companion `partition_objective_dependencies` plus the `OBJECTIVE_*_DEPENDENCY_ROLES`
constants, so a future role change lands in one place.

Each normalized `ObjectiveReference` carries a `namespace_path` slot reserved for
later module/import expansion: namespacing may extend a reference's identity but
must not change its reference kind, its dependency-role set, or the
acyclicity/fail-closed rules above.

## Anti-Patterns

Avoid:

- a second objective schema beside `aces_sdl.objectives`
- a second reference resolver beside `SemanticValidator`'s named-reference
  index or the compiler's canonical address helpers
- a second assessment pipeline or objective-dependency graph implementation
- mixing objective actor binding with participant episode lifecycle or
  apparatus realization
- treating objective targets as backend execution targets
- encoding evaluator query language, probe commands, credentials, or polling
  behavior in objective success
- changing generated schemas without changing their contract inputs and
  regenerating
- adding SEM-207-specific exception, logging, persistence, or audit stacks

## Implementation Mapping

- shared name-level semantic source of truth:
  `implementations/python/packages/aces_sdl/semantics/objective_semantics.py`
  (`analyze_objective_semantics`, `partition_objective_dependencies`,
  `OBJECTIVE_*_DEPENDENCY_ROLES`)
- objective-window analysis (reused, not re-implemented):
  `implementations/python/packages/aces_sdl/semantics/objectives.py`
- authoring models (closed Pydantic shape; `agent` xor `entity`; non-empty
  `success`): `implementations/python/packages/aces_sdl/objectives.py`
- semantic validation:
  `implementations/python/packages/aces_sdl/validator.py` (`_verify_objectives`,
  rendering the issue codes back onto the authoring-error strings)
- compiled runtime objective resource, canonical addresses, diagnostics, and
  ordering/refresh derivation:
  - `implementations/python/packages/aces_processor/compiler.py`
  - `implementations/python/packages/aces_processor/models.py` (`ObjectiveRuntime`,
    `Diagnostic`)
- planner ordering/refresh reconciliation over the compiled edges:
  - `implementations/python/packages/aces_processor/planner.py`
  - `implementations/python/packages/aces_processor/semantics/planner.py`
- implementation-facing reference note:
  `docs/explain/reference/objective-semantics.md` (governed by ADR-016)

## Tests

- `implementations/python/tests/test_semantics_objectives.py`
  (`TestObjectiveSemantics`, `TestObjectiveDependencyPartition`)
- `implementations/python/tests/test_fm2_semantics.py`
  (`TestObjectiveSemanticAgreement`, `TestObjectiveWindowAgreement`)
- `implementations/python/tests/test_sdl_validator.py` (`TestVerifyObjectives`)
- `implementations/python/tests/test_runtime_models.py`

## Non-Goals

This note does not introduce new SDL syntax, add runtime adapters, or define
participant behavior semantics; those are governed elsewhere (the runtime
result/execution contracts, the participant-episode and participant-behavior
requirements). It fixes the semantic boundary and the repo-wide guardrails for
the declarative-objective construct family under `SEM-207`.
