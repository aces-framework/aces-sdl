# SEM-213 Temporal Participant Preflight

Issue: #190
Requirement: SEM-213
Date: 2026-05-21

This note records the architecture preflight guardrails for implementing
temporal participant semantics. It is guidance for the implementation and does
not itself implement SEM-213.

## Binding Sources

- ADR-022 separates timestamps from ordering, causality, pacing,
  synchronization, and clock authority.
- `specs/formal/participant-semantics/README.md` states that episode step,
  scenario time, simulation time, backend time, and wall-clock time are
  distinct time domains.
- The SEM-213 formal section requires schedules, cadence, deadlines, dwell,
  latency, time windows, reset and replay boundaries, and backend pacing /
  synchronization limitation disclosure.
- SEM-211 already owns controlled failure classes, including timeout. SEM-212
  already owns causality and attribution support. SEM-213 must link to those
  surfaces without collapsing into them.

## Guardrails

- Add typed temporal contract fields to governed participant action contracts.
  Raw `agents.*.actions` names must remain an authoring affordance only.
- Every temporal contract must name a time domain and clock authority. A raw
  timestamp alone must not be accepted as schedule, cadence, deadline, dwell,
  latency, or time-window semantics.
- Carry temporal contract metadata into compiled runtime action contracts and
  published behavior-history schemas so backend adapters and conformance tools
  can inspect the same fields.
- Runtime participant behavior history may report realized temporal context,
  but it must match the compiled action contract's temporal id, domain, clock
  authority, event points, and backend disclosure references.
- Deadline, dwell, timeout, cadence, reset, and replay interactions need an
  explicit state-machine check. Terminal missed-deadline / timeout states must
  not be silently reused across reset or replay boundaries.
- Backend pacing, dilation, synchronization, serialization, and unsupported
  timing guarantees must be represented as disclosure objects, not prose-only
  caveats.

## Reuse

- Reuse the existing participant behavior contract module for the authoring
  surface and the existing compiler path that already carries SEM-208 through
  SEM-212 metadata into `ParticipantActionContractRuntime`.
- Reuse `ParticipantPreconditionClass.TEMPORAL` and
  `ParticipantFailureClass.TIMEOUT`; do not create duplicate vocabularies for
  action applicability or failure.
- Reuse `ParticipantAttributionOrderingBasis` for causal and attribution
  claims; SEM-213 should not make timestamp adjacency causal.
- Reuse `iter_participant_behavior_history_violations` for runtime conformance
  so participant-local temporal context is checked next to visibility,
  attribution, and action-result checks.

## Non-Goals

- Do not implement the broader SEM-227 / SEM-228 / SEM-229 ACES time model.
- Do not add new schema files under `contracts/schemas/` by hand; change the
  Python contract models and regenerate.
- Do not add compatibility implementation under `implementations/python/src/aces`.
