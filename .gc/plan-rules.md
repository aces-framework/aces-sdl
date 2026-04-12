# aces-sdl plan rules

Mandatory constraints the `/implement` skill applies during plan phase.
These encode the hard rules previously in `AGENTS.md` prose.

- Plans MUST run `implementations/python/.venv/bin/python tools/check_repo_policy.py`
  before declaring completion.
- Plans MUST run `implementations/python/.venv/bin/python tools/check_requirement_governance.py`
  before declaring completion.
- Plans MUST run `implementations/python/.venv/bin/python tools/verify_all.py`
  before declaring completion.
- Plans MUST set `ACES_REQUIREMENT_UID` when the branch name does not
  already contain a UID such as `GOV-918`.
- Plans MUST NOT add new authority-bearing artifacts outside `specs/`,
  `contracts/`, `docs/`, and `implementations/`.
- Plans MUST NOT edit `contracts/schemas/` directly; change generator
  inputs and regenerate.
- Plans MUST NOT add new implementation logic to
  `implementations/python/src/aces/`; that tree is compatibility-only
  wrappers.
- Plans MUST NOT import `aces.*` from owning packages under
  `implementations/python/packages/`.
- Plans MUST keep concept-authority artifacts in the approved
  concept-authority surfaces.
- Plans MUST keep IMPLEMENTS and TESTS traceability in Ground Control
  aligned with changed code and tests.
