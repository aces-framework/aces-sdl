# ADR-000: Use Architecture Decision Records

## Status

accepted

## Date

2026-03-20

## Context

The ACES SDL and runtime stack is being maintained as its own repository, with
language, semantics, runtime contracts, and assurance surfaces all evolving
under one codebase. Significant architectural decisions need durable, local
context so contributors can understand *why* the system is shaped the way it is
instead of reconstructing intent from code archaeology.

As the project grows, newcomers (and future-us) need to understand *why* the
system is shaped the way it is — not just *what* it does. Without structured
decision records, context is lost and the same debates resurface.

## Decision

Adopt Architecture Decision Records (ADRs) using a lightweight MADR (Markdown
Any Decision Records) format. All ADRs live in
`docs/decisions/adrs/` and are versioned with the codebase.

Each ADR follows this template:

```markdown
# ADR-NNN: [Title]

## Status

[proposed | accepted | deprecated | superseded by ADR-XXX]

## Date

YYYY-MM-DD

## Context

What is the issue that we're seeing that is motivating this decision or change?

## Decision

What is the change that we're proposing and/or doing?

## Consequences

What becomes easier or more difficult to do because of this change?

### Positive

-

### Negative

-

### Risks

-
```

### Governance

- ADRs are **immutable** once accepted. To reverse a decision, create a new ADR that supersedes it.
- ADRs are **numbered sequentially** (000, 001, 002, ...) and numbers are never reused.
- ADRs are **versioned with code** — they live in
  `docs/decisions/adrs/`, not a wiki or external tool.
- Status transitions: `proposed` → `accepted` or `rejected`. Accepted ADRs can later be `deprecated` or `superseded by ADR-XXX`.
- The `docs/decisions/adrs/README.md` index must be updated when an ADR is
  added or its status changes.

## Consequences

### Positive

- New contributors can understand *why* the system is built this way without archaeology through git history
- Decisions are discoverable and searchable within the documentation site
- The immutability principle prevents silent decision drift
- Retroactive ADRs capture institutional knowledge before it's lost

### Negative

- Overhead of writing and maintaining ADRs for each significant decision
- Retroactive ADRs may not perfectly capture the original reasoning

### Risks

- ADRs become stale if the team forgets to update statuses when decisions are reversed
- Disagreement about what constitutes a "significant" decision worth an ADR
