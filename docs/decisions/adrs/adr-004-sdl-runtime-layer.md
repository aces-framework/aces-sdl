# ADR-004: SDL Runtime Layer

**Status:** Accepted
**Date:** 2026-03-30
**Deciders:** Brad Edwards

## Context

The SDL is now the authoritative scenario specification surface. The next layer
must execute *that* model directly while keeping reusable definitions, bound
runtime instances, and execution contracts distinct.

The first runtime attempt introduced the right package boundary but the wrong
core abstraction: it treated raw SDL section entries as generic executable
steps. That collapsed reusable definitions and bound runtime instances into the
same concept, made reconciliation incomplete, and pushed too much meaning into a
single cross-domain interface.

The runtime therefore uses a clean package boundary:

```text
aces.core.sdl      -> specification and validation
aces.core.runtime  -> compile, plan, execute contracts
aces.backends.*    -> target-specific implementations
```

## Decision

Adopt a three-stage SDL-native runtime architecture:

1. **Compile** `Scenario -> RuntimeModel`
2. **Plan** `RuntimeModel + BackendManifest + RuntimeSnapshot -> ExecutionPlan`
3. **Execute** domain plans through explicit runtime target protocols

### Compiler

`compile_runtime_model()` is a pure normalization pass that separates reusable
SDL definitions from bound runtime instances.

Examples:

- top-level `features` remain templates, while `node.features` become
  node-scoped `FeatureBinding`s
- top-level `conditions` remain templates, while `node.conditions` become
  node-scoped `ConditionBinding`s
- top-level `injects` become first-class orchestration resources, while
  `node.injects` become optional node-scoped `InjectBinding`s that target those
  resources
- `nodes` + `infrastructure` become deployable network/node resources
- events, scripts, stories, workflows, metrics, evaluations, TLOs, goals, and
  objectives become resolved runtime graph nodes with canonical addresses

Bound condition refs fail closed. Unqualified condition refs must resolve to
exactly one binding; zero or multiple matches produce diagnostics instead of
implicit fan-out. Event inject refs resolve directly to top-level inject
resources and produce diagnostics when the named inject is missing.

### Planner

The planner no longer emits a flat step DAG. `ExecutionPlan` is composite:

- `ProvisioningPlan`
- `OrchestrationPlan`
- `EvaluationPlan`

Each plan operates on canonical runtime resources inside its own temporal model.
Reconciliation is explicit and complete:

- desired-only -> `CREATE`
- changed -> `UPDATE`
- snapshot-only -> `DELETE`
- identical -> `UNCHANGED`

Plans are provenance-bound to an optional target name, backend manifest, and
base runtime snapshot they were reconciled against. Direct planner output is
unbound by default; only manager-generated plans or plans with an explicit
`target_name` are applyable.

Runtime resources carry two dependency sets:

- `ordering_dependencies` for same-domain create/start ordering and reverse
  delete ordering
- `refresh_dependencies` for downstream refresh propagation when upstream state
  changes

Cross-domain refs participate only in refresh propagation. Fixed phase order
remains `provisioning -> evaluation -> orchestration`.
If any same-domain ordering graph is cyclic, planning fails closed with runtime
diagnostics rather than guessing an execution order.

### Capability Model

Capabilities are domain-specific rather than a single overloaded bag:

- `ProvisionerCapabilities`
- `OrchestratorCapabilities`
- `EvaluatorCapabilities`

The planner validates semantic requirements from the compiled model, including
node types, OS families, scaling limits, ACL usage, content types, account
features, orchestration usage, workflows, workflow predicate condition refs,
scoring, and objectives. Capability-relevant variable refs consumed by the
planner must still resolve soundly even when SDL semantic cross-reference
validation was skipped earlier:

- undeclared capability-relevant `${var}` refs are planner errors
- finite `allowed_values` domains are first revalidated against the SDL field
  being parameterized before backend capability checks run
- only field-valid finite domains are checked against backend capabilities
- declared variables without a finite field-valid pre-instantiation domain
  produce warning diagnostics and defer exact capability validation until
  instantiation rather than guessing from defaults

### Runtime Target And Registry

Backends must provide an explicit `BackendManifest`. Runtime targets are created
through a registry that separates:

- `manifest()` for capability introspection
- `create()` for backend instantiation

There is no fallback capability inference from a provisioner instance, and
`create()` must instantiate components against the same manifest returned during
introspection. The current runtime surface intentionally supports at most one evaluator per target;
explicit evaluator partitioning is deferred until the runtime has a real routing
model.

`RuntimeTarget` is self-validating: manifest presence, component shape, and the
required invokable protocol surface must all match both for registry-created
targets and direct construction. Validation is signature-aware: methods must be
callable with the runtime's actual lifecycle call shapes, not merely present by
name.
At execution time, backend exceptions and invalid lifecycle return payloads are
treated as structured runtime failures rather than bubbling up as uncaught
manager crashes.

### Protocols

Protocols consume domain plans, not generic steps:

- `Provisioner.apply(provisioning_plan, snapshot)`
- `Orchestrator.start(orchestration_plan, snapshot)`
- `Evaluator.start(evaluation_plan, snapshot)`

Orchestrators and the current evaluator surface are lifecycle services with `status()`
and `stop()`. Failed runtime-service startup triggers best-effort rollback of
started services while preserving any provisioning state already applied.
Services are only started when their domain plan has actionable operations, but
delete-only reconciliation still runs through the same lifecycle entrypoint.

Objective `window` refs remain declarative scope/refresh inputs. They do not
create cross-domain executor ordering semantics. `depends_on` remains the only
objective ordering relation.

## Consequences

### Positive

- The runtime now matches SDL semantics instead of forcing them through a flat
  step abstraction.
- Reconciliation is honest and supports deletes as well as updates.
- Capability validation can fail fast on real backend mismatches.
- Ambiguous or unbound runtime refs are rejected instead of being guessed.
- The reference stubs exercise the correct contracts for future real backends.

### Negative

- The compiler/planner split adds more explicit types and indirection.
- Future backends must implement manifests and domain protocols from day one.
- Real scenarios must bind orchestration/evaluation refs unambiguously.

## Scope Boundaries

- This decision focuses on SDL-native runtime contracts rather than on
  product-specific deployment or execution surfaces.
- The current runtime scope centers on compiler, planner, manager, registry,
  reference stubs, and supporting tests/docs.
- Real target implementations follow on top of these contracts.
