# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.10.0] - 2026-04-11

### Added

- `RUN-311` ("Participant Episode Lifecycle And Reset") participant
  episode contract surface: `ParticipantEpisodeStatus`,
  `ParticipantEpisodeTerminalReason`, `ParticipantEpisodeControlAction`,
  `ParticipantEpisodeHistoryEventType`,
  `ParticipantEpisodeExecutionState`, and
  `ParticipantEpisodeHistoryEvent` in
  `implementations/python/packages/aces_processor/models.py`, modelling
  current lifecycle state, terminal reasons, and control actions as
  three distinct categories per ADR-013.
- Closed-world contract models `ParticipantEpisodeStateModel` and
  `ParticipantEpisodeHistoryEventModel` plus matching
  `participant-episode-state-envelope-v1` /
  `participant-episode-history-event-stream-v1` entries in
  `schema_bundle()`, with the new `participant-episode-state/v1`
  schema-version constant in
  `implementations/python/packages/aces_contracts/versions.py`.
- Generated JSON Schemas in `contracts/schemas/control-plane/` and
  minimal valid/invalid fixture pairs in
  `contracts/fixtures/control-plane/`.
- ADR-013 ("Participant Episode Lifecycle Boundaries") in
  `docs/decisions/adrs/` defining the contract-surface boundary
  discipline that drives this work.
- End-to-end coverage in
  `implementations/python/tests/test_run_311_participant_episode_lifecycle.py`
  satisfying every clause of the requirement (initialization, reset,
  completion, timeout, truncation, interruption, restart) while
  preserving stable participant identity across resets and restarts.
- `RuntimeSnapshot` and `RuntimeSnapshotEnvelopeModel` now carry
  `participant_episode_results` and `participant_episode_history`
  alongside the existing `orchestration_*` and `evaluation_*` surfaces.
  Both are keyed by the stable `participant_address`. Matching
  serialization in `aces_processor/control_plane_api.py::_snapshot_model`,
  `aces_processor/control_plane_store.py::_snapshot_payload`, and
  `aces_conformance/conformance.py` routes the new data through
  `/snapshot` responses and durable snapshot state instead of forcing
  it into `RuntimeSnapshot.metadata`.
- Stream-level invariants on `ParticipantEpisodeHistoryEvent`:
  `episode_initialized` must carry `sequence_number=0`, and
  `episode_reset` / `episode_restarted` must carry `sequence_number>0`,
  matching the `ParticipantEpisodeExecutionState` invariants so a valid
  history stream can always be reconstructed into a valid state chain.
- Manifest-authority registration: the new
  `participant-episode-state-envelope-v1` and
  `participant-episode-history-event-stream-v1` contract ids are now
  members of `BACKEND_SUPPORTED_CONTRACT_IDS` and
  `PROCESSOR_SUPPORTED_CONTRACT_IDS`, added to the conformance
  `FULL_REMOTE_CONTROL_PLANE` profile requirements, and wired into
  `aces_conformance.conformance._validate_payload` and
  `_semantic_diagnostics`. The reference backend stub fixture at
  `contracts/fixtures/backend-manifest/backend-manifest-v2/valid/stub.json`
  is updated to match the widened authority list.
- `_live_target_cases()` live conformance probe now serializes
  `participant_episode_results` / `participant_episode_history` so a
  backend advertising the full-remote profile cannot pass conformance
  with malformed RUN-311 data.
- Shared snapshot invariant iterator
  `aces_processor.models.iter_participant_episode_snapshot_violations`,
  consumed by both the runtime-manager apply path
  (`_participant_episode_contract_diagnostics`) and the conformance
  semantic-check path (`_participant_episode_snapshot_diagnostics`) so
  both callers use one source of truth for per-entry validation and
  stream-level consistency (outer-key/inner-address match, monotonic
  `sequence_number`, stable `episode_id` per sequence, and `RESET` /
  `RESTARTED` gating on cross-sequence transitions).
- Ground Control IMPLEMENTS and TESTS traceability links from `RUN-311`
  to the new processor models, contract models, schema-version constant,
  ADR-013, the conformance wiring, and the lifecycle test.

### Fixed

- Production-readiness review finding 1: RUN-311 now ships an actual
  runtime capability, not just contracts and validators. New
  ``ParticipantRuntime`` backend protocol on
  ``aces_backend_protocols/protocols.py`` defines ``initialize`` /
  ``reset`` / ``restart`` / ``terminate`` plus the standard
  ``status`` / ``results`` / ``history`` observation methods. New
  ``ParticipantRuntimeCapabilities`` capability block on
  ``BackendCapabilitySet`` plus a ``has_participant_runtime`` property
  on ``BackendManifest`` let backends advertise the surface and let
  ``RuntimeTarget`` shape validation reject targets whose component
  presence does not match the manifest. ``RuntimeControlPlane``
  exposes ``initialize_participant_episode``,
  ``reset_participant_episode``, ``restart_participant_episode``, and
  ``terminate_participant_episode``, each routing through the existing
  idempotency / persistence / audit pipeline and emitting an
  ``OperationReceipt`` / ``OperationStatus`` under a new
  ``RuntimeDomain.PARTICIPANT`` domain. ``control_plane_api.py``
  publishes the four matching POST routes under
  ``/participants/{participant_address}/episodes/*`` with closed-world
  request bodies. The reference stub backend gains a new
  ``StubParticipantRuntime`` that implements every transition with
  RUN-311-correct sequence/episode_id/previous_episode_id semantics
  and updates the snapshot in lockstep with the published contract.
  Tests cover the in-process control plane lifecycle, the HTTP API,
  the rejection paths (no participant runtime, already terminated,
  duplicate initialize, etc.), idempotency replay, and a full
  end-to-end ``initialize → reset → terminate → restart`` chain that
  must satisfy ``iter_participant_episode_snapshot_violations``.
- `iter_participant_episode_snapshot_violations` now cross-checks each
  ``participant_episode_results`` entry against the head of the
  corresponding ``participant_episode_history`` chain. A stale result
  that still points at an earlier episode than the history shows — the
  specific scenario raised as production-readiness review finding 2 —
  fails validation with ``does not match head of history chain``.
  Identity (``episode_id`` + ``sequence_number``), status category, and
  ``terminal_reason`` must all agree with the last valid history event
  for the same participant. Apply-path and conformance semantic-check
  paths both pick this up automatically via the shared helper.
- `iter_participant_episode_snapshot_violations` no longer produces
  cascading duplicate violations when a stream-level rule fires. Both
  the sequence-transition gate and the per-sequence ``episode_id``
  stability check now advance stream state after every yielded
  violation except strict backward movement, so an ungated sequence
  transition reports one error per transition and an ``episode_id``
  mismatch reports each distinct transition (e.g. ``A -> B`` then
  ``B -> C``) instead of repeating the same comparison against the
  first-observed id.

### Changed

- `tools/policy/requirement_order.yaml`: `RUN-311` added to the
  `runtime-core` phase (it is the next runtime/control-plane sibling
  after `RUN-300`). Phase ownership widened to cover
  `docs/decisions/adrs`, `contracts/schemas/snapshots`,
  `contracts/schemas/backend-manifest`,
  `contracts/schemas/processor-manifest`,
  `contracts/fixtures/backend-manifest`,
  `contracts/fixtures/processor-manifest`, and
  `implementations/python/packages/aces_conformance` so the ADR and the
  conformance/schema wiring clear `check_requirement_governance.py`.
- `aces_conformance.conformance._validate_event_stream` extracted from
  the repeated history-stream validation blocks so workflow, evaluation,
  and participant-episode history streams share one helper.

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
