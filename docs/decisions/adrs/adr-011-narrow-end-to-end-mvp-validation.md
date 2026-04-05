# ADR-011: Narrow End-to-End MVP Validation

## Status

accepted

## Date

2026-04-04

## Context

The repository has now been restructured far enough that the intended package
and artifact boundaries are visible, but structure alone does not yet prove the
ecosystem works.

The purpose of the ecosystem is not just to define SDL syntax or isolated
contracts. It is to support agentic experiments through an honest end-to-end
stack:

- authored SDL
- processor behavior
- backend realization
- participant behavior as first-class apparatus
- comparable execution across more than one backend

Without an explicit decision, post-restructure work can drift into broad
horizontal coverage without demonstrating that even a narrow slice of the
ecosystem works coherently.

The repository therefore needs one explicit near-term decision about what kind
of proof to optimize for first.

## Decision

Prioritize a narrow end-to-end MVP that validates and stress-tests the SDL
ecosystem as a working vertical slice.

This MVP must be honest rather than broad. It should demonstrate, for a narrow
supported subset, that:

- SDL can be processed through the reference processor
- participant behavior is part of the declared apparatus rather than implicit
- the same authored scenario shape can be carried across at least two backends
- manifests, disclosures, and reporting are sufficient to explain what the
  slice supports and where it is constrained

Near-term requirement and implementation ordering may therefore be pulled
toward the minimum set needed to make that slice real, even when that means not
following the broadest possible inventory order.

Broader ecosystem surfaces remain important, but they are secondary to first
proving that one honest, narrow, participant-capable vertical slice works.

## Consequences

### Positive

- The repository gets an explicit proof target instead of only a reorganization
  target.
- Requirement prioritization can be judged against whether it helps complete a
  real participant-capable slice.
- The post-restructure architecture will be stress-tested through actual use
  across more than one backend rather than only through abstract boundary work.

### Negative

- Some broader requirement families may be deferred while the MVP slice is
  completed.
- Early artifact and manifest work may be narrower than the final ecosystem
  surface.

### Risks

- The project could overfit to one narrow slice and mistake it for full
  ecosystem coverage.
- If the MVP boundaries are described loosely, the repo may still claim more
  portability than it has actually demonstrated.
