# ADR-013: Participant Episode Lifecycle Boundaries

## Status

accepted

## Date

2026-04-11

## Context

`RUN-311` requires explicit participant episode initialization, reset,
completion, timeout, truncation, interruption, and restart handling.

The processor already has multiple lifecycle surfaces:

- workflow execution state/history
- evaluation execution state/history
- control-plane operation receipt/status
- live runtime snapshot persistence

Those surfaces already solve real problems, but they do **not** currently model
participant episodes. If `RUN-311` is implemented by overloading one of them,
the architecture will blur distinct concerns:

- workflow control semantics vs participant execution semantics
- control-plane request lifecycle vs participant episode lifecycle
- backend service/process restart vs explicit participant reset/restart
- mutable live state vs durable episode history
- backend apparatus vs participant-implementation apparatus

The repository also already has explicit guidance from ADR-004, ADR-008, and
ADR-009 that processor/runtime contracts must stay schema-first, portable, and
separate from backend- or SDL-only meaning.

## Decision

### 1. Model participant episodes as their own processor/runtime contract surface

Participant episode state is a first-class execution artifact. It must not be
encoded as:

- `WorkflowExecutionState`
- `EvaluationExecutionState`
- `OperationReceipt` or `OperationStatus`
- ad hoc `RuntimeSnapshot.metadata` blobs

Participant execution therefore extends the existing processor/runtime
architecture with a dedicated participant-episode contract surface rather than
reusing a neighboring lifecycle type with different semantics.

### 2. Reuse the existing schema-first boundary pattern

Participant episode support must follow the same boundary discipline already
used for workflows and evaluations:

- plain-data external envelopes
- versioned schema-first contracts
- typed in-process normalization helpers behind the boundary
- validation against compiled/runtime contracts rather than backend-native
  object identity

Portable contract shape remains authored in the contract-model source and then
published to `contracts/schemas/`; schema files are generated artifacts and
must not become hand-maintained side channels.

### 3. Keep lifecycle state, terminal reason, and control actions separate

`RUN-311` mixes several different categories of lifecycle concern. They must
not be flattened into one overloaded enum.

- initialization, reset, and restart are control actions/transitions
- completion, timeout, truncation, and interruption are terminal outcomes or
  terminal reasons
- current episode state is a separate concern from both of the above

This mirrors the repository's current workflow discipline, where live status
and terminal reason are already distinct fields.

### 4. Preserve explicit episode identity across resets and restarts

A participant implementation may stay bound to one stable participant address
or apparatus identity across multiple episodes, but each episode instance must
remain distinguishable in state and history.

Reset or restart handling must therefore create explicit new episode state
rather than mutating prior episode history in place and pretending that the run
was uninterrupted.

### 5. Reuse existing processor cross-cutting concerns

Participant episode work must reuse the processor's existing cross-cutting
concerns instead of introducing parallel stacks:

- structured `Diagnostic` reporting for validation and execution failures
- control-plane audit, idempotency, and request fingerprint handling
- existing control-plane security roles and request-size/error-redaction
  behavior
- existing snapshot/store durability patterns for live state
- existing manifest/apparatus discipline that keeps processor, backend, and
  participant-implementation surfaces distinct

This work must not add a separate exception hierarchy, logging/audit mechanism,
or out-of-band persistence path for participant episodes.

### 6. Scope boundaries

This decision does **not**:

- add new SDL authoring syntax for episode semantics
- collapse participant episode control into workflow-step semantics
- treat backend process restarts as equivalent to participant episode restarts
- redesign the full archival run-provenance model

`RUN-311` is processor/runtime control semantics. It should extend processor
contracts and live execution surfaces first, while preserving the existing
boundary between authored SDL meaning and apparatus/runtime realization.

## Consequences

### Positive

- Participant episode lifecycle work now has a clear home in the architecture.
- Existing workflow/evaluation/control-plane patterns can be reused directly
  instead of re-invented.
- Reset, truncation, interruption, and restart semantics can remain explicit
  and reviewable.

### Negative

- The processor gains another explicit execution-contract family rather than
  hiding episode behavior inside existing lifecycle types.
- Implementors cannot shortcut the work by reusing workflow status enums or
  control-plane operation states wholesale.

### Risks

- If episode identity is not preserved across resets/restarts, replay and
  provenance claims will remain ambiguous.
- If participant episode data is stored as metadata without contracts,
  validation and portability will degrade quickly.
- If participant lifecycle logic is split between backend internals and
  processor contracts, the repo will end up with duplicate semantics and
  inconsistent failure handling.
