---
name: implement
description: End-to-end ACES SDL requirement implementation with repo policy and Ground Control gates
argument-hint: <requirement-uid>
disable-model-invocation: true
---

# Implement Requirement: $ARGUMENTS

This skill handles the repo-local implementation loop for a single ACES SDL
requirement. Use it to stay inside ADR-009, ADR-010, and ADR-012 while keeping
Ground Control traceability aligned with code and tests.

## Phase A: Load Context

### Step 1: Resolve Requirement Context

1. Fetch the requirement with `gc_get_requirement` using uid `$ARGUMENTS`.
2. Fetch its traceability with `gc_get_traceability`.
3. Read the applicable ADRs before editing:
   - ADR-009 normative artifact authority and repo structure
   - ADR-010 repository realignment order and compatibility policy
   - ADR-012 shared concept authority and ACES extension discipline
4. Export `ACES_REQUIREMENT_UID=$ARGUMENTS` for local verification commands if
   the branch name does not already contain the requirement UID.

### Step 2: Confirm Order and Ownership

1. Run
   `implementations/python/.venv/bin/python tools/check_requirement_governance.py --requirement-uid $ARGUMENTS`.
2. Treat failures as blockers:
   - out-of-order requirement work
   - ownership-root mismatches
   - missing Ground Control connectivity
3. Before writing code, identify the allowed roots for this requirement from
   `tools/policy/requirement_order.yaml`.

## Phase B: Implement

### Step 3: Implement Inside The Allowed Boundaries

Respect these hard rules while editing:

- do not add authority-bearing artifacts outside `specs/`, `contracts/`, `docs/`,
  and `implementations/`
- do not edit `contracts/schemas/` directly; update generator inputs and
  regenerate
- do not add substantive implementation logic under
  `implementations/python/src/aces/`; that tree is compatibility-only wrappers
- do not import `aces.*` from owning packages under
  `implementations/python/packages/`
- keep concept-authority artifacts in the approved authority surfaces only

### Step 4: Keep Traceability In Sync

When code or tests change, ensure Ground Control has:

- `IMPLEMENTS` links for changed implementation files
- `TESTS` links for changed test files

If the requirement is still `DRAFT` and the implementation is complete,
transition it to `ACTIVE` as part of the close-out.

## Phase C: Verify

### Step 5: Run Repo Policy Checks

Run these before stopping:

- `implementations/python/.venv/bin/python tools/check_repo_policy.py`
- `implementations/python/.venv/bin/python tools/check_requirement_governance.py --requirement-uid $ARGUMENTS`
- `implementations/python/.venv/bin/python tools/verify_all.py --requirement-uid $ARGUMENTS`
- relevant focused tests for the changed Python packages
- `pre-commit run --all-files` before commit when the task includes code changes

### Step 6: Completion Gate

Implementation is not complete until all of these are true:

1. `CHANGELOG.md` is updated when source files changed.
2. Ground Control traceability reflects changed code and test files.
3. The requirement status is appropriate for the completed work.
4. Repo policy and requirement governance checks are both green.
5. Any ADR changes are reflected in `docs/decisions/adrs/README.md`.
