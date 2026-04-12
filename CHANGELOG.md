# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.10.0] - 2026-04-11

### Added

- Participant episode lifecycle contract surface for `RUN-311`
  ("Participant Episode Lifecycle And Reset"):
  `ParticipantEpisodeStatus`, `ParticipantEpisodeTerminalReason`,
  `ParticipantEpisodeControlAction`, `ParticipantEpisodeHistoryEventType`,
  `ParticipantEpisodeExecutionState`, and `ParticipantEpisodeHistoryEvent`
  in `implementations/python/packages/aces_processor/models.py`; closed-world
  `ParticipantEpisodeStateModel` and `ParticipantEpisodeHistoryEventModel`
  with `participant-episode-state-envelope-v1` and
  `participant-episode-history-event-stream-v1` `schema_bundle()` entries
  in `implementations/python/packages/aces_contracts/contracts.py`; the
  `participant-episode-state/v1` schema-version constant in
  `implementations/python/packages/aces_contracts/versions.py`; generated
  JSON Schemas under `contracts/schemas/control-plane/`; valid/invalid
  fixture corpora under `contracts/fixtures/control-plane/`; ADR-013
  ("Participant Episode Lifecycle Boundaries") in
  `docs/decisions/adrs/`; and end-to-end coverage in
  `implementations/python/tests/test_run_311_participant_episode_lifecycle.py`
  satisfying every clause of the requirement (initialization, reset,
  completion, timeout, truncation, interruption, and restart) while
  preserving stable participant identity across resets and restarts.
- Ground Control IMPLEMENTS and TESTS traceability links from `RUN-311`
  to the new processor models, contract models, schema-version constant,
  ADR-013, and the lifecycle test.

### Changed

- `tools/policy/requirement_order.yaml`: `RUN-311` added to the
  `runtime-core` phase (it is the next runtime/control-plane sibling
  after `RUN-300`), and `docs/decisions/adrs` added to the
  `runtime-core` ownership block so ADR-013 clears
  `check_requirement_governance.py` path-ownership review.

## [0.9.0] - 2026-04-11

### Added

- RUN-300 lifecycle integrity test
  (`implementations/python/tests/test_run_300_lifecycle.py`) that threads
  a parameterized scenario through instantiation, compilation, planning,
  execution, and live observation, asserting substituted parameter values
  survive unchanged through instantiation, compilation, planning, and
  apply; canonical addresses survive unchanged across all five stages;
  and provenance drift (a stale plan base snapshot) is rejected rather
  than silently reconciled.
- Ground Control IMPLEMENTS and TESTS traceability links from RUN-300
  (Processing Model and Lifecycle) to the processor/compiler/planner/
  manager/control-plane stack and its per-stage tests.

## [0.8.0] - 2026-04-11

### Added

- `.ground-control.yaml` declaring workflow commands (nox verify),
  sonarcloud key (`aces-framework_aces-sdl` in `keplerops` org), and
  plan rules reference.
- `.gc/plan-rules.md` containing the ACES SDL hard rules and required
  checks (previously in AGENTS.md prose), rewritten as "plans MUST..."
  bullets for the `/implement` skill plan phase.

### Changed

- `AGENTS.md` Ground Control Context block replaced with a pointer to
  `.ground-control.yaml`. Hard rules and required checks now live in
  `.gc/plan-rules.md`.
- `.mcp.json` `GH_REPO` corrected from `KeplerOps/Ground-Control` to
  `aces-framework/aces-sdl`.

## [0.7.0] - 2026-04-11

### Changed

- API-413 no longer publishes, generates, or tests a `backend-manifest-v1`
  compatibility surface. The backend manifest authority is now `v2` only.
- Backend `v2` manifests now use a backend-specific compatibility surface that
  declares compatible processors only, and they validate declared supported
  contract ids against the shared backend manifest authority set on both the
  contract-model path and the runtime dataclass path.
- The reference backend stub and backend conformance path now consume the
  shared backend manifest authority directly, reducing drift between authority
  sets, emitted manifests, fixtures, and conformance validation.

### Fixed

- API-413 backend conformance now fails when a backend under-declares the
  contract ids required by its inferred runtime capability profile, instead of
  trusting capability shape alone.
- Published schema checks now reject stale extra schema files that are no
  longer generated from the live contract bundle, closing the hole where a dead
  `backend-manifest-v1` file could silently creep back into `contracts/schemas`.
- Backend manifest regression tests now keep valid `concept_bindings` in place
  and assert the intended failure causes for empty compatibility,
  under-specified realization support, and hollow capability blocks.

## [0.6.0] - 2026-04-11

### Added

- Canonical `nox` verification graph for repo policy, lint, contract/schema
  validation, tests, and fuzz checks, with local hooks and CI calling the same
  sessions instead of maintaining separate command lists.
- Standard-tooling enforcement for repo structure and JSON contracts through
  Conftest/OPA and `check-jsonschema`, plus repo-local bootstrap helpers for
  those tools so the policy and contract gates fail locally before CI.
- Repo-local `gitleaks` bootstrap and `nox` hygiene session covering generic
  file/security checks inside the same canonical verification graph as lint,
  policy, contracts, and tests.

### Changed
- API-412 no longer publishes, generates, or tests a `processor-manifest-v1`
  compatibility surface. The processor manifest authority is now `v2` only.
- Local pre-commit and pre-push hooks now use the canonical verification graph,
  with commit-time policy/lint/contract/test gating and push-time full verify
  plus fuzz coverage to match CI semantics.
- `nox` now emits explicit start/pass/fail/skip status for each check stage and
  each session summary, while `.pre-commit-config.yaml` is now a thin trigger
  layer instead of a second source of substantive check logic.

### Fixed

- Fix `_run_changed_lint` in noxfile crashing on repo-relative paths passed to
  `Path.relative_to()` with an absolute `PROJECT_ROOT`.

## [0.5.0] - 2026-04-10

### Changed

- API-412 processor manifests now keep `v2` focused on processor identity,
  contract support, backend compatibility, processor capabilities, and concept
  bindings. `realization_support` is no longer part of the processor manifest
  contract surface, and processor `compatibility` is now backend-only instead
  of the generic apparatus compatibility shape. Declared SDL versions and
  supported contract versions are now validated against the repo-published
  processor/runtime contract ids instead of remaining open string fields.

## [0.4.0] - 2026-04-10

### Added

- GOV-922 controlled-vocabulary catalog, schema, fixtures, and validation
  helpers for portable enumerations and governed-extension vocabularies.

### Changed

- Backend capability declarations now validate governed vocabulary values on
  both the contract-model path and the runtime dataclass path.

## [0.3.1] - 2026-04-10

### Fixed

- CI workflow now triggers on pull requests targeting `dev` branch, not just `main`.
- Rename `UID` variable to `REQ_UID` in CI policy job to avoid collision with
  the readonly shell builtin.
- Add `fetch-depth: 0` to policy job checkout so the PR base SHA is available
  for `git diff`.
- Pass branch name via `env:` in CI UID-extraction step instead of relying on
  shell variable expansion of `GITHUB_HEAD_REF`.
- `current_branch()` in `check_requirement_governance.py` now falls back to
  `GITHUB_HEAD_REF` when `git branch --show-current` returns empty (detached
  HEAD in CI PR checkouts).
- Requirement governance check now warns and exits 0 when Ground Control is
  unreachable, instead of failing the build.

## [0.3.0] - 2026-04-05

### Added

- Cross-artifact concept binding for v2 apparatus manifests (GOV-918).
  Backend and processor manifests now require a `concept_bindings` section
  that binds vocabulary fields to canonical concept families from the
  concept-authority catalog.
- Repo-owned ADR enforcement tooling under `tools/policy/`, including
  repo-boundary checks, requirement-order gating, exception handling, and a
  unified verification entrypoint.
- Hard policy integration for local agents and automation through
  pre-commit, GitHub Actions, Claude hooks, `AGENTS.md`, and repo-local
  Codex instructions.
- Targeted policy unit tests covering generated-schema edits, compatibility
  boundaries, requirement ordering, path ownership, and traceability failures.
- `ConceptBindingEntryModel` Pydantic contract with pattern-validated
  `scope` and `family` fields.
- `ConceptFamilyId` pattern-constrained type for concept family identifiers.
- `ConceptBinding` frozen dataclass for runtime concept binding declarations.
- Invalid fixtures for missing, duplicate, and malformed concept bindings.
- Contract-level validation ensuring `concept_bindings` resolve to the
  authoritative concept-families-v1 catalog and to governed manifest
  vocabulary surfaces.
- GOV-919 native extension discipline metadata in the concept-family catalog,
  including extension scope, relation rules, and non-ambiguity constraints.
- Invalid fixtures covering native concept families that omit extension
  discipline fields.
- GOV-920 semantic profile contract, schema, fixtures, and the initial
  `reference-stack-v1` shared semantic profile.
- GOV-921 shared reference model catalog, schema, fixtures, and initial
  recurrent SDL reference models for nodes, accounts, relationships,
  conditions, events, and content.

### Changed

- `BackendManifestV2Model` and `ProcessorManifestV2Model` now require
  `concept_bindings` with at least one entry.
- `BackendManifest` and `ProcessorManifest` frozen dataclasses now require
  `concept_bindings` tuple.
- Backend and processor manifest emission functions emit concept bindings.
- Updated all v2 manifest fixtures with concept binding declarations.
- Updated all v2 invalid fixtures to include concept bindings for single-concern testing.
- Regenerated backend-manifest-v2 and processor-manifest-v2 JSON Schemas.
- `ConceptFamilyDefinitionModel` and the `concept-families-v1` schema now
  reject native families that do not declare GOV-919 extension discipline.
- Documented and validated shared semantic assumptions for authoring, exchange,
  processing, and execution through the new semantic profile surface.
- Documented and validated shared reusable structure anchors for recurrent
  federation-relevant objects through the new reference-model catalog surface.

## [0.2.0] - 2026-04-04

### Added

- Processor manifest declaration surface (`ProcessorFeature` enum,
  `ProcessorManifest` frozen dataclass, `ProcessorManifestModel` Pydantic
  contract) for declaring processor identity, supported language and contract
  versions, processing features, backend compatibility, and constraints
  (API-412).
- Reference processor manifest helpers and `aces processor manifest` CLI output
  for emitting the repo-owned processor declaration.
- JSON Schema `processor-manifest-v1` published to
  `contracts/schemas/processor-manifest/`.
- Valid and invalid processor manifest fixtures in
  `contracts/fixtures/processor-manifest/`.
- Schema generation routing for processor manifest in
  `tools/generate_contract_schemas.py`.
- Pre-commit hooks with ruff (lint + format), gitleaks (secrets), trailing
  whitespace, YAML/JSON checks, and pytest gate.
- GitHub Actions CI workflow with lint, test (coverage), fuzz, contract schema
  drift detection, and SonarCloud analysis.
- SonarCloud project configuration (`sonar-project.properties`).
- GitHub PR template and issue templates (bug report, feature request).
- Ruff linter and formatter configuration in `pyproject.toml`.

## [0.1.0] - 2026-04-03

### Added

- Initial ACES SDL ecosystem extraction from APTL with SDL authoring layer,
  processor layer, backend protocols, conformance infrastructure, and CLI.

[0.6.0]: https://github.com/aces-framework/aces-sdl/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/aces-framework/aces-sdl/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/aces-framework/aces-sdl/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/aces-framework/aces-sdl/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/aces-framework/aces-sdl/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/aces-framework/aces-sdl/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/aces-framework/aces-sdl/releases/tag/v0.1.0
