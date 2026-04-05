# ADR-008: Processor Layer and Execution Artifact Boundaries

## Status

accepted

## Date

2026-04-04

## Context

[ADR-004](adr-004-sdl-runtime-layer.md) established the current compile -> plan
-> execute architecture and correctly treated the middle layer as a semantic
surface rather than a thin transport shim.

Since then, two boundary problems have become clearer.

First, the repository uses the term `runtime` for multiple different things:

- the semantics-bearing middle layer between SDL authoring and backend
  realization
- live execution and control-plane state
- archival experiment/run artifacts

That terminology collision now obscures a real reproducibility concern. The
middle layer is not experimentally neutral. Instantiation, compilation,
planning, lifecycle handling, capability checks, and failure behavior can all
shape outcomes just as backend choice can.

Second, the current artifact boundaries are too soft. Mutable live execution
state and archival experiment records are both discussed as "runtime"
artifacts, even though they serve different purposes:

- live execution state is operational and mutable
- archival run provenance is evidentiary and reviewable

The requirements architecture now makes these concerns explicit:

- processing lifecycle is a separate pillar from portable contracts
- processor and backend both need explicit identity/capability declarations
- canonical run provenance must be distinct from live execution state
- optional compatibility declarations must not silently become mandatory SDL
  meaning

The repository needs an architectural decision that sharpens these boundaries
without discarding the core compile/plan/execute design from ADR-004.

## Decision

Keep the existing SDL-native compile/plan/execute architecture, but refine the
ecosystem boundary model around the term `processor` and around explicit
artifact classes.

### 1. Use `processor` for the semantics-bearing middle layer

At the architecture and ecosystem-contract level, the layer between SDL
authoring and backend realization is the **processor**.

Its responsibilities include:

- validating and instantiating SDL inputs
- compiling author-facing scenario structures into typed execution
  representations
- planning against declared backend capabilities and current state
- coordinating execution and lifecycle transitions
- producing portable live-state and archival execution artifacts

This term is used because the layer is not just "runtime" in the narrow sense
of currently running processes; it is the semantic processor of scenario intent
into executable behavior.

### 2. Reserve `runtime` for live execution surfaces

Within the processor boundary, `runtime` is reserved for **live execution
surfaces** such as:

- control-plane APIs
- mutable execution snapshots
- operation status/history
- workflow and evaluation lifecycle state

This preserves a useful term for operational state while removing it as the
name for the whole middle layer.

### 3. Treat processors and backends as symmetric experimental apparatus

Processors and backends are both part of the experimental apparatus.

Therefore:

- backends publish backend manifests
- processors publish processor manifests
- runs preserve the identity and manifest context of both

The architecture must not treat the backend as observable and accountable while
leaving the processor implicit.

### 4. Distinguish live execution state from archival run provenance

The ecosystem uses two distinct artifact classes:

- **live execution state** for mutable operational observation and control
- **archival run provenance** for durable evidentiary records of what actually
  executed

Live state is allowed to change during execution. Archival provenance exists so
comparison, review, replay claims, and reproducibility arguments do not depend
on reconstructing facts from mutable control-plane state.

### 5. Keep apparatus constraints optional at the authoring boundary

The SDL remains the author-facing specification of scenario meaning.

Processor/backend compatibility or capability constraints are supported as
optional task- or run-level apparatus declarations. They are not required SDL
syntax and they do not become part of mandatory scenario meaning merely because
some experimental uses need tighter apparatus control.

### 6. Relationship to ADR-004

This ADR preserves ADR-004's core architecture:

- compile -> typed model
- plan against declared capabilities and current state
- execute through explicit backend/domain protocols

It refines the terminology and artifact boundaries around that architecture.
ADR-004 remains the source decision for the compile/plan/execute model itself.

## Consequences

### Positive

- The architecture now names the semantics-bearing middle layer honestly.
- Reproducibility work can treat processor choice as part of the apparatus
  rather than invisible plumbing.
- Live operational state and archival provenance are no longer conceptually
  blended.
- Processor and backend contracts become structurally symmetric.
- The SDL can remain author-friendly without forcing every user to bind to a
  specific apparatus stack.

### Negative

- Existing documentation and code still use `runtime` broadly, so a terminology
  migration is required.
- Some current files and schemas will look misnamed until the repository
  structure catches up.
- Contributors must learn the narrower meaning of `runtime` versus the broader
  meaning of `processor`.

### Risks

- If the terminology is applied inconsistently, the repository could end up
  with two overlapping vocabularies instead of one cleaner model.
- If processor manifests are treated as mere metadata instead of capability and
  compatibility declarations, the symmetry with backend manifests will remain
  superficial.
- If archival run provenance is implemented as just another field on mutable
  live-state artifacts, this decision will not actually improve reviewability
  or reproducibility.
