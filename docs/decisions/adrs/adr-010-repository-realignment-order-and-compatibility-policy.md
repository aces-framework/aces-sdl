# ADR-010: Repository Realignment Order and Compatibility Policy

## Status

accepted

## Date

2026-04-04

## Context

ADR-009 established the target authority model and repository structure for the
ACES SDL ecosystem. The repository has now been moved far enough toward that
shape that the intended boundaries are visible on disk:

- normative artifacts live under `specs/` and `contracts/`
- reference implementations live under `implementations/`
- the Python implementation has been split into concern-specific packages such
  as `aces_sdl`, `aces_processor`, `aces_backend_protocols`,
  `aces_backend_stubs`, `aces_conformance`, and `aces_cli`

However, the codebase is still transitional in practice.

Even after the reorganization:

- compatibility imports may still be needed to preserve existing callers
- tests, docs, and tooling may still reference legacy paths
- contributors can easily slide back into the old single-package mental model
- requirement work can accidentally blur the new boundaries unless it is taken
  in a deliberate order

Without an explicit sequencing decision, the repository risks either:

- attempting a large cleanup sprint that stalls requirement progress, or
- continuing requirement work in an order that keeps reintroducing
  cross-concern coupling

The repo therefore needs one explicit decision that says both:

- how transitional compatibility is to be treated, and
- in what order realignment work should proceed while requirements continue

## Decision

Adopt an explicit compatibility policy and a requirement-aligned realignment
order for post-reorganization implementation work.

### 1. Treat the legacy `aces.*` namespace as compatibility-only

The package tree under:

- `implementations/python/src/aces/`

exists to preserve existing tests, CLI entrypoints, and external callers while
the implementation settles into its new structure.

This namespace is transitional and compatibility-oriented. It is not the
intended long-term home for new implementation work.

### 2. Do not add new legacy imports inside owning packages

New code under:

- `implementations/python/packages/aces_sdl/`
- `implementations/python/packages/aces_processor/`
- `implementations/python/packages/aces_backend_protocols/`
- `implementations/python/packages/aces_backend_stubs/`
- `implementations/python/packages/aces_conformance/`
- `implementations/python/packages/aces_cli/`

must import the real owning packages rather than `aces.*`.

This keeps the compatibility layer one-directional:

- internal code depends on real package ownership
- compatibility wrappers depend on internal code

not the reverse.

### 3. Use the new package ownership model as the implementation boundary

The intended ownership model is:

- `aces_sdl`: SDL authoring, models, parsing, composition, instantiation, validation
- `aces_processor`: compilation, planning, runtime/control-plane behavior
- `aces_backend_protocols`: backend-facing capability and protocol declarations
- `aces_backend_stubs`: fake/test backends
- `aces_conformance`: conformance runners and reports
- `aces_cli`: CLI entrypoints only
- `contracts/`: schemas, fixtures, profiles, and related machine-readable artifacts

When a requirement touches multiple areas, work should still be organized so
the owning package for each concern becomes clearer, not blurrier.

### 4. Realign in requirement order, not as a separate cleanup project

Realignment work should happen through requirement slices, in this order:

1. The processor/backend core of `API-400`
   - Start with `API-404`, `API-412`, and `API-413`.
   - After that slice, re-audit any directly affected requirements such as
     `ASR-501`, `ASR-502`, `ASR-526`, and `API-400` itself.
   - Treat `API-400` itself as an umbrella and keep it `DRAFT` until its
     broader child surface is honestly covered.
2. Processor and runtime lifecycle
   - Continue with `RUN-300` and related runtime/control-plane requirements.
3. Reference implementations
   - Continue with `RUN-313`, `RUN-314`, and `RUN-315`.
4. Remaining semantic expansion
   - Continue with unfinished `SEM-*` work after the processor/backend seams
     are stable.
5. Deferred `API-400` expansion surfaces
   - Return later to the broader participant/time contract children under
     `API-400` such as `API-405` through `API-421`.

## Consequences

### Positive

- The repository has one clear statement of how to continue from the
  reorganization without losing momentum.
- Requirement work can now be chosen in an order that makes the new package
  boundaries stronger instead of weaker.
- The compatibility layer becomes a controlled transition mechanism rather than
  an accidental second architecture.
- Contributors have a concrete test for whether a change is helping the new
  structure: it should reduce ambiguity about which package owns which concern.

### Negative

- Some compatibility code and duplicated import surfaces will remain for a
  while.
- Contributors must be more disciplined about import direction and ownership
  boundaries than they had to be before the split.
- Some numerically adjacent requirements may still be deferred if they do not
  support the chosen realignment order.

### Risks

- If the compatibility layer remains in place for too long, people may keep
  treating it as the real architecture.
- If requirement work is resumed in a purely numeric order, the new package
  boundaries may blur again.
- If the repo waits for a perfect refactor before resuming requirement work,
  progress on actual ecosystem commitments will stall unnecessarily.
