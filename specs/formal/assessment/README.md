# Assessment Pipeline Semantics

This directory holds the formal artifacts for the SDL assessment-pipeline
semantics — the scoring chain
`condition bindings -> metrics -> evaluations -> TLOs -> goals` and its
relationship to declarative objectives — under `SEM-206`.

## Scope

- normalized reference resolution along the scoring chain (each metric's
  condition, each evaluation's metrics, each TLO's evaluation, each goal's
  TLOs), and the cross-resource reference constraints they must satisfy
- score aggregation: an evaluation's metric-max-score total and the
  absolute-min-score-vs-total consistency rule
- the "at most one metric per condition" exclusivity rule for conditional
  metrics
- dependency-role derivation: every scoring-chain edge is both an ordering
  edge (the downstream resource is computed after its inputs) and a refresh
  edge (the downstream resource recomputes when any input changes), so a
  single source of truth feeds the validator, the compiler's
  `ordering_dependencies` / `refresh_dependencies`, and the planner's
  ordering/refresh reconciliation
- fail-closed behavior for missing, ambiguous (binding-level), or
  out-of-scope references
- composition-ready invariants: normalized references are independent of
  source-file layout; module/import expansion must run before this analysis

`SEM-206` does not define a scoring algorithm, publish a new contract version,
add evaluator capabilities, or define evidence/provenance semantics — those are
governed elsewhere (the runtime result/execution contracts, evaluator
capabilities, the concept-authority stack).

## Implementation Mapping

- shared name-level semantic source of truth:
  `implementations/python/packages/aces_sdl/semantics/assessment.py`
- authoring models (closed Pydantic shape; manual/conditional metric rules;
  `min-score` shorthand; `Condition` command-xor-source):
  - `implementations/python/packages/aces_sdl/scoring.py`
  - `implementations/python/packages/aces_sdl/conditions.py`
- semantic validation: `implementations/python/packages/aces_sdl/validator.py`
  (`_verify_assessment_pipeline`)
- compiled runtime addresses, contracts, and ordering/refresh derivation:
  - `implementations/python/packages/aces_processor/compiler.py`
  - `implementations/python/packages/aces_processor/models.py`
- planner ordering/refresh reconciliation over the compiled edges:
  - `implementations/python/packages/aces_processor/planner.py`
  - `implementations/python/packages/aces_processor/semantics/planner.py`
- runtime evaluator-result and execution contracts (the execution/observation
  realization): `EvaluationResultContract`, `EvaluationExecutionContract`,
  `EvaluationExecutionState`, `EvaluationHistoryEvent`,
  `validate_evaluation_result()` in
  `implementations/python/packages/aces_processor/models.py`;
  evaluator-result / history-event schemas in
  `implementations/python/packages/aces_contracts/contracts.py`
- implementation-facing guardrails note (preflight):
  `docs/explain/reference/assessment-semantics.md` (governed by ADR-016)

## Tests

- `implementations/python/tests/test_semantics_assessment.py`
- `implementations/python/tests/test_fm2_semantics.py`
  (`TestAssessmentPipelineAgreement`)
- `implementations/python/tests/test_sdl_validator.py`
- `implementations/python/tests/test_sdl_models.py`
- `implementations/python/tests/test_runtime_models.py`
- `implementations/python/tests/test_runtime_planner.py`
