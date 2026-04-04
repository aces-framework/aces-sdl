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

| Level | Scope | Artifacts |
|-------|-------|-----------|
| FM0 | Structural (parsing, models) | Unit tests only |
| FM1 | Static semantic rules | Invariant lists + unit tests |
| FM2 | Dynamic semantic rules | Formal specs + property-based tests |
| FM3 | Cross-system contracts | Formal specs + conformance tests |
