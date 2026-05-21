# Assessment Semantics Preflight

This note records architecture guardrails for `SEM-206`. It is not an
implementation plan.

## Scope Boundary

`SEM-206` covers the assessment pipeline semantics for SDL conditions, metrics,
evaluations, TLOs, goals, and their relationship to declarative objectives. The
pipeline is:

```text
condition bindings -> metrics -> evaluations -> TLOs -> goals -> objectives
```

The SDL authoring layer owns section shape and static reference rules. The
processor layer owns compiled evaluation resources, dependency semantics,
capability checks, and runtime result contracts. The backend/evaluator boundary
owns only portable evaluator result envelopes and history streams, not
backend-native scoring state.

## Incumbents To Reuse

- SDL shape: `aces_sdl.conditions`, `aces_sdl.scoring`, and
  `aces_sdl.objectives`.
- Static validation: `SemanticValidator._verify_conditions()`,
  `_verify_metrics()`, `_verify_evaluations()`, `_verify_tlos()`,
  `_verify_goals()`, and `_verify_objectives()`.
- Instantiation: `instantiate_scenario()` must rerun semantic validation after
  parameter substitution.
- Compilation: `compile_runtime_model()` must remain the source of canonical
  `evaluation.*` addresses and compiled `EvaluationResultContract` /
  `EvaluationExecutionContract` payloads.
- Planning: `aces_processor.semantics.planner` owns ordering and refresh
  dependency interpretation for compiled evaluation resources.
- Runtime boundary: `EvaluationExecutionState`, `EvaluationHistoryEvent`,
  `validate_evaluation_result()`, and
  `RuntimeManager`'s evaluation result contract diagnostics are the shared
  enforcement path for evaluator payloads.
- Contracts: `aces_contracts.contracts.ContractModel`, `schema_bundle()`, and
  generated `contracts/schemas/control-plane/evaluation-*-v1.json` remain the
  external shape authority.
- Capability authority: evaluator support must flow through
  `EvaluatorCapabilities`, `EvaluatorCapabilitiesModel`, controlled vocabulary
  terms for `capabilities.evaluator.supported_sections`, and the existing
  `supports_scoring` / `supports_objectives` split.

## Guardrails

- Keep condition templates distinct from condition bindings. Authoring names a
  reusable condition; runtime scoring works against node-bound
  `evaluation.condition.<node>.<condition>` addresses.
- Keep scoring resources distinct from objectives. Metrics, evaluations, TLOs,
  and goals define assessment structure; objectives bind actors, targets,
  success criteria, dependencies, and optional windows.
- Keep ordering dependencies and refresh dependencies separate. Assessment
  aggregation uses ordering edges from prerequisite assessment resources;
  objective windows and condition-driven changes create refresh edges where
  appropriate.
- Use the existing fail-closed reference behavior for missing, ambiguous, or
  out-of-scope references. Do not add local string parsing in compiler,
  planner, runtime manager, or backend adapters when a model/helper already
  resolves the reference.
- Preserve the existing evaluator payload contract: `metric` reports score
  fields, while `condition-binding`, `evaluation`, `tlo`, `goal`, and
  `objective` report `passed`. Any additional portable aggregation rule must compile into
  the contract or a governed contract version, not into backend-private
  convention.
- Treat `detail`, `details`, and `evidence_refs` as observation metadata, not
  as hidden scoring authority. They must not contain secrets, tokens, raw
  credentials, backend-private object dumps, or full tracebacks.
- Extend controlled vocabulary, semantic profile, or contract authority only
  when portable comparison requires it. A local evaluator implementation detail
  does not belong in those surfaces.

## Required Gates

- Parser/model gate: assessment fields stay closed Pydantic models derived from
  `SDLModel`; `${var}` placeholders may parameterize values but may not create
  mapping keys or semantic identities.
- Validation gate: `SemanticValidator` remains the static semantic choke point
  and raises `SDLValidationError` with collected authoring errors.
- Instantiation gate: concrete scenarios pass `instantiate_scenario()` and
  concrete semantic revalidation before compilation.
- Compiler/planner gate: compiled evaluation resources use canonical
  `evaluation.*` addresses and shared planner dependency helpers.
- Manifest/profile gate: evaluator sections and scoring/objective capability
  declarations resolve through the existing apparatus-manifest and controlled
  vocabulary helpers.
- Runtime contract gate: evaluator payloads pass `EvaluationExecutionState`,
  `EvaluationHistoryEvent`, `EvaluationResultContract`,
  `EvaluationExecutionContract`, and `validate_evaluation_result()` before
  entering snapshots.
- HTTP/control-plane gate: any API exposure uses the existing control-plane
  request-size, authentication, authorization, idempotency, audit, response
  model, and redacted-error behavior.
- Persistence/OS exposure gate: snapshots, operation records, audit details,
  diagnostics, history `details`, and evidence references stay plain-data and
  non-secret; bearer tokens and credentials must not appear in command-line
  arguments, logs, diagnostics, fixtures, or persisted envelopes.

## Extension Boundary

The extension seam is a pure assessment semantic helper under
`aces_sdl.semantics` when the same aggregation or reference rule must be used
by validation, compilation, planning, runtime contract checks, and tests. The
helper should operate on structured inputs and return normalized references,
derived dependency roles, and machine-readable issues; callers may translate
those issues into their local error or diagnostic envelope.

Portable assessment variations belong in versioned contract/profile or
controlled-vocabulary authority only when external implementations need to
compare them. They should not be hard-coded as evaluator-specific strings.

## Anti-Patterns

- Duplicating scoring schemas outside `aces_sdl.scoring` or external contract
  schemas.
- Creating a second assessment registry beside the scenario model, semantic
  profile, and concept-authority stack.
- Recomputing aggregation semantics independently in validator, compiler,
  planner, manager, and backend stubs.
- Letting backend-native evaluator payloads become the observation contract.
- Treating objectives as just another aggregation node, or treating goals/TLOs
  as actor-bound objectives.
- Editing generated schemas under `contracts/schemas/` directly.
- Introducing SEM-206-specific exception, logging, persistence, audit, or
  error-envelope stacks.

## Non-Goals

This note does not implement new assessment rules, change the current scoring
pipeline, publish a new contract version, add evaluator capabilities, define
evidence/provenance semantics, or transition `SEM-206`. Those belong to the
implementation run that follows.
