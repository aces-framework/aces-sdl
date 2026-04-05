# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the ACES SDL
ecosystem. ADRs capture significant architectural decisions along with their
context, rationale, and consequences.

## Format

We use [MADR](https://adr.github.io/madr/) (Markdown Any Decision Records).
Each ADR includes:

- **Status**: `proposed`, `accepted`, `deprecated`, or `superseded by ADR-XXX`
- **Context**: The problem or situation driving the decision
- **Decision**: What we chose and why
- **Consequences**: Trade-offs (positive, negative, risks)

## Principles

- ADRs are **immutable** once accepted. To reverse a decision, create a new ADR
  that supersedes it.
- ADRs are **numbered sequentially** and never reused.
- ADRs are **versioned with code** and live in the repo.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [000](adr-000-use-adrs.md) | Use Architecture Decision Records | accepted | 2026-03-20 |
| [001](adr-001-scenario-description-language.md) | Scenario Description Language (SDL) | accepted | 2026-03-29 |
| [002](adr-002-declarative-sdl-objectives.md) | Declarative Experiment Objectives in the SDL | accepted | 2026-03-29 |
| [003](adr-003-workflows-targetable-subobjects-and-enum-variables.md) | Workflows, Targetable Sub-Objects, and Leaf Enum Variables in the SDL | accepted | 2026-03-29 |
| [004](adr-004-sdl-runtime-layer.md) | SDL Runtime Layer | accepted | 2026-03-30 |
| [005](adr-005-control-flow-primitives.md) | Control Flow Primitives in the SDL | superseded by ADR-006 | 2026-04-01 |
| [006](adr-006-workflow-control-language-redesign.md) | Workflow Control-Language Redesign | accepted | 2026-04-01 |
| [007](adr-007-lightweight-formal-methods-policy.md) | Lightweight Formal Methods Policy for Semantic Systems | accepted | 2026-04-01 |
| [008](adr-008-processor-layer-and-execution-artifact-boundaries.md) | Processor Layer and Execution Artifact Boundaries | accepted | 2026-04-04 |
| [009](adr-009-normative-artifact-authority-and-repository-structure.md) | Normative Artifact Authority and Repository Structure | accepted | 2026-04-04 |
| [010](adr-010-repository-realignment-order-and-compatibility-policy.md) | Repository Realignment Order and Compatibility Policy | accepted | 2026-04-04 |
| [011](adr-011-narrow-end-to-end-mvp-validation.md) | Narrow End-to-End MVP Validation | accepted | 2026-04-04 |
