# Formal Specifications

Optional formal artifacts for ACES SDL semantic and stateful subsystems.

These specifications live under `specs/formal/<domain>/` in the repository and
cover the formally-verified properties of key subsystems. See
[ADR-007](../adrs/adr-007-lightweight-formal-methods-policy.md) and the
[coding standards](../reference/coding-standards.md) for the policy on when
formal artifacts are warranted.

## Domains

- **Workflows** (`specs/formal/workflows/`) -- Workflow state machine properties
- **Objectives** (`specs/formal/objectives/`) -- Objective/window consistency
- **Planner** (`specs/formal/planner/`) -- Dependency ordering and reachability
- **Runtime Contracts** (`specs/formal/runtime-contracts/`) -- Result/evaluation contracts

## FM Classification

The canonical mapping is
[`specs/formal/assurance-policy.yaml`](../../specs/formal/assurance-policy.yaml)
(see [ADR-018](../decisions/adrs/adr-018-classification-based-assurance-policy.md)),
which is the structural source of truth and gates CI via
`tools/check_assurance_policy.py`.

| Level | Scope | Required artifacts |
|-------|-------|--------------------|
| FM0 | Structural (parsing, schema, local validation) | Unit tests |
| FM1 | Static Semantic (cross-references, ambiguity, fail-closed) | Invariants + unit tests |
| FM2 | Semantic Graph / Constraint (reachability, dependencies, portability) | FM1 + typed IR/contract coverage + targeted property-based or differential tests |
| FM3 | Stateful / Control Semantics (state machines, branching, lifecycle) | FM2 + abstract state-machine model |
