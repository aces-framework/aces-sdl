# ADR-014: nox as the Canonical Verification Graph

## Status

accepted

## Date

2026-05-09

## Context

The repository has multiple verification layers — Python tests (pytest +
hypothesis), repo-policy enforcement (Conftest/OPA + Python scripts under
`tools/policy/`), JSON-schema contract validation (`check-jsonschema`),
secret scanning (gitleaks), formatter/linter (ruff), file-hygiene gates
(trailing whitespace, EOF newline, large-file detection, merge-conflict
markers, private-key detection), Sphinx documentation builds, and
property-based fuzz tests. Each gate has its own native invocation. The
same gates need to run in three places:

1. **Local pre-commit hooks** — fast, scoped to staged files.
2. **Local pre-push hooks** — slower, full-repo validation before push.
3. **CI (`ci.yml`)** — the same set as pre-push, plus coverage upload
   and SonarCloud.

Before this ADR, the only mechanism to keep these three invocations in
agreement was discipline: hand-maintained command lists in
`.pre-commit-config.yaml` and `.github/workflows/ci.yml`, plus prose in
`AGENTS.md` and CONTRIBUTING-style docs. The failure mode of that
arrangement is well known: the three command lists drift, "verified
locally" stops meaning the same thing as "passed in CI," and a
contributor passing the local hook can still find a CI failure that was
preventable with a slightly different local command.

The repository also has policy and contract tooling written in Python
that consumes structured artifacts (the requirement order, ownership
maps, traceability links, ADR index, etc.). A pure-shell orchestrator
(Make, just, plain scripts) has to re-implement Python-aware
composition every time it wants to call into that tooling. A
Python-native orchestrator can call the tooling in-process or via
explicit subprocess and still share the rest of the verification graph
with non-Python checks (gitleaks, OPA, sphinx-build).

## Decision

### 1. nox is the single canonical verification graph

`noxfile.py` at the repository root defines every verification stage as
a session with explicit substages, run sequentially through a
`SessionReporter` that emits structured `START` / `PASS` / `FAIL` /
`SKIP` events. The canonical sessions are:

- `hygiene` — text/YAML/JSON/secret/large-file/merge-conflict checks
- `policy` — Conftest self-verify, repo policy, requirement governance
- `lint` — ruff format + check, project and tooling
- `contracts` — generated-schema drift, JSON-artifact validation
- `tests` — pytest with coverage
- `fuzz` — pytest with `-m fuzz`
- `docs` — sphinx-build (added by AUT-805)
- `verify` — composes hygiene + policy + lint + contracts + tests + docs
- `hook-pre-commit` — staged-file hygiene + policy + scoped lint +
  conditional contracts + scoped tests
- `hook-pre-push` — full hygiene + policy + lint + contracts + tests +
  fuzz

`verify` is the canonical "passed locally" state. CI invokes
`nox -s verify`; the pre-push hook invokes `nox -s hook-pre-push`; the
pre-commit hook invokes `nox -s hook-pre-commit`. All three resolve
their work through the same per-gate helpers (`_run_hygiene`,
`_run_policy`, `_run_lint`, `_run_contracts`, `_run_tests`,
`_run_fuzz`, `_run_docs`).

### 2. `.pre-commit-config.yaml` is a thin trigger layer, not a parallel definition

Pre-commit's repo-side configuration declares one hook per nox session
that pre-commit needs to invoke (currently `hook-pre-commit` and
`hook-pre-push`). The substantive command list lives in `noxfile.py`,
not in `.pre-commit-config.yaml`. This mirrors a common pattern in
modern Python projects (e.g., calling `pytest` from a single hook
rather than re-listing pytest options in YAML) and removes the
multi-source-of-truth failure mode that the previous configuration had
when pre-commit and CI maintained their own command lists.

### 3. CI consumes the same graph

`.github/workflows/ci.yml` runs `uv tool run --from 'nox[uv]==…' nox
-s verify` for the blocking gate, plus `nox -s fuzz` as a separate job
(fuzz is excluded from `verify` because it is property-based and slow,
not because it is optional). SonarCloud consumes the coverage XML that
the `tests` substage produces; it is not a parallel test-runner.

The `.ground-control.yaml` workflow block declares each command nox
exposes:

```yaml
workflow:
  test_command:       nox -s verify   # full canonical gate
  completion_command: nox -s verify
  lint_command:       nox -s lint
  format_command:     nox -s hygiene
```

The `/implement` skill consumes those values verbatim; ground-control
agents and CI agree on what "verified" means by reading the same
`.ground-control.yaml`.

### 4. Per-session venvs via uv

`nox.options.default_venv_backend = "none"` plus per-session
`uv sync --project implementations/python --all-extras --frozen`
delegates dependency resolution to uv. The `--frozen` flag rejects any
session that would require a lockfile change at run time, so a session
either runs against the locked dependency set or fails fast.

### 5. nox is preferred over the alternatives evaluated

**Make.** Not Python-aware; can drive Python tooling but cannot
compose with our existing Python `tools/policy/` modules without
shelling out. Targets are not first-class composable units in the way
sessions are — there is no native concept of "run subset A on staged
files, subset B on the full tree." Rejected.

**just.** A more ergonomic Make. Same compositional limitations. Adds a
non-standard binary to the contributor toolchain. Rejected.

**Pre-commit only.** Pre-commit's per-hook isolation is a feature for
the staged-file path but a barrier for the full-repo path: there is no
shared state between hooks, no DAG, and no clean way to run the
"pre-commit set" outside of pre-commit's own invocation harness (which
makes the CI invocation differ from the local one, the very failure
mode this ADR is closing). Rejected as the canonical orchestrator;
retained as the trigger layer (Decision #2).

**Plain scripts.** A `scripts/verify.sh` would work but loses session
reuse, structured reporting, the per-stage `SessionReporter` summary
that current contributors and CI logs depend on, and Python-native
composition with `tools/policy/`. Rejected.

**nox.** Python-native. Per-session uv-managed venvs. Sessions
compose. Reuses our policy/contract tooling in-process. Already
familiar to Python contributors. Has a maintained `nox[uv]` integration
that pins the uv version we use elsewhere. Selected.

## Consequences

### Positive

- A single source of truth: a failure on a contributor's machine
  reproduces in CI verbatim, and vice versa.
- The verification surface is discoverable via `nox -l`; new
  contributors do not have to search across YAML files to learn what
  "verified" requires.
- Pre-commit and CI cannot drift apart on what a "passed" state
  means, because both invocations resolve through the same `_run_*`
  helpers.
- Adding a new gate is a one-place change in `noxfile.py`; CI and
  pre-commit pick it up automatically through `verify` /
  `hook-pre-push` / `hook-pre-commit`.
- The `.ground-control.yaml` workflow block is the single point where
  agents (Codex, Claude Code, the `/implement` skill) read these
  commands; they do not have to parse `.pre-commit-config.yaml` or
  `.github/workflows/ci.yml`.

### Negative

- Contributors must learn the nox session names. Mitigated by `nox -l`
  and by the principle that the names describe what they verify
  (`hygiene`, `policy`, `lint`, `contracts`, `tests`, `fuzz`, `docs`,
  `verify`).
- nox session startup is not free. Mitigated by
  `nox.options.reuse_existing_virtualenvs = True` and by the uv-backed
  install path, which is fast on a warm cache.
- A bug in `noxfile.py` itself can break every gate at once. Mitigated
  by the `tooling` lint targets that include `noxfile.py` and by tests
  under `implementations/python/tests/test_repo_policy_tools.py` and
  `test_requirement_governance.py` that exercise the underlying
  helpers independently.

### Risks

- Drift between the `nox` graph and the policy expectations (e.g., the
  `documentation-surfaces` phase ownership) is possible if a new
  session is added without extending policy ownership. This is a
  process risk, not an architectural one; it is the same risk the
  policy gate is designed to surface.
- nox's plugin surface (custom backends, alternative venv managers)
  expands the failure surface compared to plain scripts. We restrict
  ourselves to `default_venv_backend = "none"` plus uv-managed
  installs to keep the surface narrow.

## Notes

The decision codified here is what the repository already does in
practice — it was first introduced by commit `115ea24` (2026-04-11)
without an accompanying ADR. ADR-014 captures the rationale so that
future contributors do not have to reconstruct it from CHANGELOG
entries and tooling code. Sibling repositories in the same ecosystem
make different choices appropriate to their stacks (`aptl` is
multi-language and uses native runners per ecosystem with a
pre-commit-driven gate; `pulsar` is a pnpm monorepo and uses pnpm
workspaces; `shifter` has no top-level runner and documents its
absence). nox is the right answer for this repository specifically
because the verification surface is broad, polyglot at the gate level
(Python + OPA + gitleaks + Sphinx), and consumed identically from
local hooks, CI, and ground-control automation.
