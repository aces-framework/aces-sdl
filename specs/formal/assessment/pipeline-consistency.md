# Assessment Pipeline Consistency

## Reference Model

The assessment pipeline is the scoring chain

```text
condition bindings -> metrics -> evaluations -> TLOs -> goals
```

with declarative objectives binding actors/targets/success criteria onto any of
those resources (objective and predicate references into the chain are governed
together with objective-window semantics, not restated here).

Every cross-resource reference along the chain is resolved into a single
normalized internal shape (`AssessmentReference`) before compiler/planner
semantics run. Each resolved reference carries:

- raw author-facing text and the canonical source/target names
- the source and target resource kinds (`metric -> condition`,
  `evaluation -> metric`, `tlo -> evaluation`, `goal -> tlo`)
- the dependency-role set the edge carries
- a namespace-extensible path slot reserved for future module/import work

The analysis is name-level. *Which* condition addresses a metric binds to —
i.e. which VM nodes realize the condition — is resolved at compilation; an
undeclared metric/evaluation/TLO is reported here, while an unbound or
ambiguous *condition binding* is reported by the compiler against the resolved
addresses.

## Consistency Rules

- a conditional metric's `condition` must name a declared condition
- at most one metric may be scored by a given condition (no two conditional
  metrics share a `condition`)
- each evaluation's `metrics` entries must name declared metrics
- an evaluation whose `min-score` is given as an absolute value must not exceed
  the sum of its referenced metrics' `max-score` values, when every
  contributing `max-score` is a known integer (a percentage `min-score`, an
  unresolved `${var}` `max-score`, or a non-integer `max-score` makes the total
  unknown and the check is skipped, fail-open on the *aggregate* but never on
  the *references*)
- each TLO's `evaluation` must name a declared evaluation
- each goal's `tlos` entries must name declared TLOs
- `${var}` placeholders only ever substitute values; a reference that is still
  an unresolved placeholder is skipped (re-checked after instantiation), never
  treated as a literal name

## Aggregation Semantics

- `evaluation_metric_totals[e]` is the sum of the integer `max-score` values of
  `e`'s resolvable referenced metrics, or `None` if any contributing
  `max-score` is unknown
- the metric-result contract reports a `score` against a `fixed_max_score`
  (when the metric declares an integer `max-score`); condition-binding,
  evaluation, TLO, goal, and objective result contracts report `passed`. The
  runtime evaluator-result/execution contracts
  (`EvaluationResultContract` / `EvaluationExecutionContract` /
  `validate_evaluation_result()`) are the fail-closed boundary that enforces
  this — a future aggregation rule compiles into the contract or a governed
  contract version, not into backend-private convention

## Dependency and Refresh Semantics

- every scoring-chain edge carries both an **ordering** role and a **refresh**
  role: a resource is computed after its inputs, and recomputed when any input
  changes. This single fact (`ASSESSMENT_DEPENDENCY_ROLES`) feeds:
  - the validator (the reference checks above)
  - the compiler's `ordering_dependencies` / `refresh_dependencies` for
    `MetricRuntime` / `EvaluationRuntime` / `TLORuntime` / `GoalRuntime`
    (derived via `partition_assessment_dependencies`)
  - the planner's generic ordering/refresh reconciliation
    (`reconcile_resource_actions` / `refresh_impacted_nodes`)
- consequently a change to a condition binding propagates as a refresh through
  `metric -> evaluation -> TLO -> goal`; the validator, the compiler, and the
  planner derive that propagation from one shared model rather than separate
  per-stage logic

## Fail-Closed Cases

- a conditional metric referencing an undeclared condition
- two conditional metrics scoring the same condition
- an evaluation referencing an undeclared metric
- an absolute evaluation `min-score` above the known metric-max-score total
- a TLO referencing an undeclared evaluation
- a goal referencing an undeclared TLO
- (at compilation) a metric whose condition resolves to no bound node, or to
  more than one — emitted as `evaluation.condition-ref-unbound` /
  `evaluation.condition-ref-ambiguous` against the resolved addresses

## Composition-Ready Invariants

- normalized references are independent of source-file layout
- future module/import expansion must occur before this analysis runs
- namespacing may extend a reference's identity, but must not change:
  - source/target resource kinds
  - dependency-role semantics
  - the aggregation rule

## Implementation Mapping

- shared semantic source of truth:
  `implementations/python/packages/aces_sdl/semantics/assessment.py`
- validator checks: `implementations/python/packages/aces_sdl/validator.py`
- compiled runtime references, contracts, and ordering/refresh derivation:
  - `implementations/python/packages/aces_processor/compiler.py`
  - `implementations/python/packages/aces_processor/models.py`
- planner reconciliation:
  - `implementations/python/packages/aces_processor/planner.py`
  - `implementations/python/packages/aces_processor/semantics/planner.py`
- differential and cross-stage tests:
  - `implementations/python/tests/test_semantics_assessment.py`
  - `implementations/python/tests/test_fm2_semantics.py`
