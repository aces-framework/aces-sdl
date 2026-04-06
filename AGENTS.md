# ACES SDL Agent Rules

Use the repo policy tooling before and after implementation work.

## Required checks

- `implementations/python/.venv/bin/python tools/check_repo_policy.py`
- `implementations/python/.venv/bin/python tools/check_requirement_governance.py`
- `implementations/python/.venv/bin/python tools/verify_all.py`

Set `ACES_REQUIREMENT_UID` when the branch name does not already contain a UID
such as `GOV-918`.

## Hard rules

- Do not add new authority-bearing artifacts outside `specs/`, `contracts/`,
  `docs/`, and `implementations/`.
- Do not edit `contracts/schemas/` directly; change generator inputs and
  regenerate.
- Do not add new implementation logic to `implementations/python/src/aces/`;
  that tree is compatibility-only wrappers.
- Do not import `aces.*` from owning packages under
  `implementations/python/packages/`.
- Keep concept-authority artifacts in the approved concept-authority surfaces.
- Keep IMPLEMENTS and TESTS traceability in Ground Control aligned with changed
  code and tests.
