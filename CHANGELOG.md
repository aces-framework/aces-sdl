# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.17.0] - 2026-05-10

### Added

- `implementations/python/packages/aces_sdl/semantics/objective_semantics.py` —
  the pure, name-level source of truth for declarative-objective semantics
  (`SEM-207`): actor binding (an authored `agent` xor `entity`), target
  resolution through the targetable named-reference index, success
  interpretation (`mode` over referenced conditions/metrics/evaluations/TLOs/
  goals), the optional window (delegated to `analyze_objective_window`), and the
  acyclic `depends_on` ordering relation. `analyze_objective_semantics` resolves
  those references into a normalized typed IR (`ObjectiveReference` /
  `ObjectiveResourceDependencies` / `ObjectiveSemanticAnalysis`) and reports
  machine-readable issues callers translate into their own envelope. The
  "success and `depends_on` edges order *and* refresh; window edges only
  refresh; actor and target references are normalized but carry no runtime
  dependency role today" fact lives in one place
  (`partition_objective_dependencies` plus the `OBJECTIVE_*_DEPENDENCY_ROLES`
  constants, each gated independently so a future role change to one category
  lands in exactly one place). Derived ordering/refresh names are kind-qualified
  (`condition.<n>`, `metric.<n>`, `objective.<n>`, `workflow.<n>`, …) so
  cross-namespace SDL names cannot collapse. Per ADR-015 it lives with the SDL
  package and has no processor-runtime dependencies; mirrored as a compatibility
  re-export at `aces.core.semantics.objective_semantics`.
- `specs/formal/objectives/declarative-objective-semantics.md` — the formal
  artifact for the declarative-objective semantic boundary (`SEM-207`): canonical
  inputs, the required actor/target/success/window/dependency semantics, the
  cross-cutting gates, the extensibility seam, anti-patterns, and the
  implementation/test mapping.
- `docs/explain/reference/objective-semantics.md` — the implementer-facing
  reference note for `SEM-207` (governed by ADR-016), linked from the reference
  index and the docs toctree.
- A `TestObjectiveSemantics` / `TestObjectiveDependencyPartition` suite in
  `implementations/python/tests/test_semantics_objectives.py` and a
  `TestObjectiveSemanticAgreement` suite in
  `implementations/python/tests/test_fm2_semantics.py` — unit tests for the
  helper plus cross-stage agreement tests (validator and compiler agree on the
  objective reference errors; compiler and planner agree that a condition change
  cascades a refresh through `objective -> depends_on -> objective`).

### Changed

- `aces_sdl.validator` now routes `_verify_objectives` through
  `analyze_objective_semantics` (rendering the machine-readable issue codes back
  onto the existing authoring-error strings via `_OBJECTIVE_ISSUE_RENDERERS`);
  `aces_processor`'s compiler derives `ObjectiveRuntime` ordering/refresh
  dependencies via `partition_objective_dependencies`. Behavior-preserving —
  every authoring error string and compiler diagnostic code is unchanged.
- `docs/explain/reference/shared-semantic-integrity.md` — the `SEM-200` Coverage
  Model row for declarative objectives moves to `active`, covering `authoring,
  validation, instantiation, compilation, planning`, with the new helper, spec,
  and tests as realizing artifacts.
- `specs/formal/objectives/README.md` — the implementation mapping and test
  lists name the new helper, the `_verify_objectives` pass, and
  `partition_objective_dependencies`.
- `SEM-207` ("Declarative Objective Semantics") transitions `DRAFT -> ACTIVE` in
  Ground Control.

### Refactor

- `analyze_objective_semantics` is split into five private resolvers
  (`_analyze_actor_binding`, `_analyze_targets`, `_analyze_success`,
  `_analyze_window`, `_analyze_dependencies`) and the new
  `AssessmentResourceCatalog` / `WindowResourceCatalog` dataclasses bundle the
  nine SDL section maps into two structured inputs, dropping the analyzer's
  signature from 14 parameters to 7 and removing the high cognitive-complexity
  hot spot SonarCloud flagged on the first run. `_analyze_actor_binding` itself
  is decomposed further into `_check_agent` / `_check_agent_actions` /
  `_check_entity` so each helper stays under the cognitive-complexity threshold.
  Behavior-preserving — every authoring error string and compiler diagnostic
  code is unchanged.

## [0.16.0] - 2026-05-10

### Added

- `implementations/python/packages/aces_sdl/semantics/assessment.py` — the
  pure, name-level source of truth for the assessment-pipeline semantics
  (`SEM-206`): the scoring chain
  `condition bindings -> metrics -> evaluations -> TLOs -> goals`. It resolves
  the cross-resource references along the chain into a normalized typed IR
  (`AssessmentReference` / `AssessmentResourceDependencies` /
  `AssessmentPipelineAnalysis`), derives each evaluation's metric-max-score
  total, enforces the "at most one metric per condition" rule and the
  absolute-`min-score`-vs-total rule, and reports machine-readable issues
  callers translate into their own envelope. The "every scoring-chain edge is
  both an ordering edge and a refresh edge" fact lives in one place
  (`ASSESSMENT_DEPENDENCY_ROLES` / `partition_assessment_dependencies`). Per
  ADR-015 it lives with the SDL package and has no processor-runtime
  dependencies; mirrored as a compatibility re-export at
  `aces.core.semantics.assessment`.
- `specs/formal/assessment/` — the formal artifacts for the assessment-pipeline
  semantics (`README.md` scope/implementation mapping; `pipeline-consistency.md`
  reference model, consistency rules, aggregation and dependency/refresh
  semantics, fail-closed cases, composition-ready invariants).
- `docs/explain/reference/assessment-semantics.md` — the architecture-preflight
  guardrails note for `SEM-206` (governed by ADR-016), linked from the
  reference index and the docs toctree.
- `implementations/python/tests/test_semantics_assessment.py` and a
  `TestAssessmentPipelineAgreement` suite in
  `implementations/python/tests/test_fm2_semantics.py` — unit tests for the
  helper plus cross-stage agreement tests (validator and compiler agree on the
  pipeline reference errors; compiler and planner agree that a condition change
  cascades a refresh through `metric -> evaluation -> TLO -> goal`).

### Changed

- `aces_sdl.validator` now routes the metric/evaluation/TLO/goal reference and
  `min-score` checks through `analyze_assessment_pipeline` (the four
  `_verify_metrics` / `_verify_evaluations` / `_verify_tlos` / `_verify_goals`
  passes collapse into one `_verify_assessment_pipeline`); `aces_processor`'s
  compiler derives `MetricRuntime` / `EvaluationRuntime` / `TLORuntime` /
  `GoalRuntime` ordering/refresh dependencies via
  `partition_assessment_dependencies`. Behavior-preserving — every authoring
  error string and compiler diagnostic code is unchanged.
- `docs/explain/reference/shared-semantic-integrity.md` — the `SEM-200`
  Coverage Model row for the assessment construct family moves to `active`,
  covering `authoring, validation, compilation, planning, execution,
  observation`, with the new helper, spec, and tests as realizing artifacts.
- `SEM-206` ("Assessment Semantics") transitions `DRAFT -> ACTIVE` in Ground
  Control.

## [0.15.0] - 2026-05-10

### Added

- ADR-016 ("Semantic Layer Scope and Coverage Model (SEM-200)") under
  `docs/decisions/adrs/`: `SEM-200` is recorded as a system-level umbrella
  requirement that is the *parent* of its ~28 `SEM-2xx` children (the construct
  families) and `DEPENDS_ON` `DSL-100`; a number of `EXP-*` / `AUT-*` / `GOV-*` /
  `ASR-*` / API/runtime requirements `DEPENDS_ON` it as downstream consumers and
  do not gate it. ADR-016 fixes the *model* — the seven canonical lifecycle
  phases (authoring, validation, instantiation, compilation, planning, execution,
  observation), the construct-family concept, the `active` / `partial` /
  `planned` status vocabulary, and `SEM-200`'s definition of done (every
  `SEM-2xx` child `ACTIVE`; no `partial`/`planned` rows in the coverage table;
  cross-stage agreement tests extended construct-wide; the unassigned-wave
  `SEM-2xx` children assigned to a wave). `SEM-200` stays `DRAFT` until then.
- `docs/explain/reference/shared-semantic-integrity.md` (the architecture-preflight
  guardrails note for `SEM-200`) gains the live, ADR-016-governed `## Coverage
  Model` table mapping every semantic construct family to its owning
  requirement(s), realizing artifacts, covered lifecycle phases, and status. The
  table lives in this mutable reference note — not in the immutable ADR — so
  routine `SEM-2xx` implementation PRs can update their construct family's row
  without an ADR amendment; ADR-016 governs it and is linked from it. For
  `planned` rows the table records the owning requirement(s) only; the intended
  scope and wave come from those requirements' Ground Control records, not from a
  duplicated table column. Higher-level capabilities that consume the semantic
  layer (cross-run comparability, federation/standards profiles, …) are tracked
  by their own requirements, not in this table.
- `tools/check_semantic_coverage.py` — a filesystem-only structural gate that
  parses that Coverage Model table and fails if a row is malformed, a status or
  lifecycle-phase token is unrecognised, an owning-requirement token is not
  UID-shaped, an artifact-cell token that looks like a path is missing, escapes
  the repo root, or is not under a supported root, an `active`/`partial` row
  names no lifecycle phase or no existing *non-test* realizing artifact, an
  `active` row names no existing `implementations/python/tests/test_*.py` test, a
  `planned` row claims phases or artifacts, or ADR-016 stops referencing the note
  by path. Row diagnostics report the real source-line number. Failures use
  `tools.policy.common.PolicyFailure`, and the CLI honours `--json` and the
  shared `tools/policy/exceptions.yaml` waiver mechanism, like the other `policy`
  nox-stage entry points. Wired into the `policy` step of the nox verification
  graph (`_run_policy` in `noxfile.py`) for working-tree runs only (skipped on
  the `--staged` pre-commit invocation, since it validates files on disk), added
  to `TARGETED_POLICY_TESTS`, and the new tooling test is exempted in
  `check_requirement_governance.py`'s `REQUIREMENT_CONTEXT_EXEMPT_PATHS`
  alongside the other policy-tooling tests; covered by
  `implementations/python/tests/test_semantic_coverage.py`.

## [0.14.0] - 2026-05-10

### Added

- `MOD-001` ("Codebase Modularity And Layering") requirement in Ground
  Control as the initiative anchor for the modularity work tracked by
  issue #3 (the cycle break + size-cap gate + the 14 file-split child
  PRs). Added to `tools/policy/requirement_order.yaml` as the sole
  requirement of a new `modularity-initiative` phase.
- ADR-015 ("SDL-Processor Layering and Source-File Size Cap") under
  `docs/decisions/adrs/`: SDL is the lower layer, circular imports
  between SDL and processor are forbidden, and non-test source files
  under `implementations/python/packages/` cap at 600 lines with a
  draining allowlist.
- `layering_rules` block in `tools/policy/adr_policy.yaml` and
  `_check_layering` in `tools/policy/repo_policy.py`: rejects any
  `import aces_processor` / `from aces_processor … import …` line in a
  changed `.py` file under `implementations/python/packages/aces_sdl/`.
  New `layering-rule-violation` rule id.
- `oversized_source_files` block in `tools/policy/adr_policy.yaml` and
  `_check_oversized` in `tools/policy/repo_policy.py`: rejects a changed
  non-test `.py` file under `implementations/python/packages/` that
  exceeds 600 lines and isn't in the allowlist. New
  `oversized-source-file` rule id.
- `tools/policy/oversized_allowlist.yaml` listing the 14 source files
  over the cap when ADR-015 landed, and `_ADR015_INITIAL_OVERSIZED_FILES`
  in `tools/policy/repo_policy.py` — a *code constant*, not config —
  holding that same fixed set as the locked reference. `_check_drain`
  (new `oversized-allowlist-locked` rule id) requires the allowlist to be
  a subset of that constant, so entries can be drained (split PRs) but
  not added; pinning the reference in code rather than `adr_policy.yaml`
  stops a single PR from relaxing the rule by editing both lists.
  `_check_allowlist_entries_still_oversized` (new
  `oversized-allowlist-stale-entry` rule id) requires every allowlist
  entry from the initial set to still resolve to a regular file over the
  cap, so a split PR that drops a file below 600 lines but forgets to
  drain its entry is flagged on the next policy run.
- Schema validation for the policy YAML: malformed config surfaces as
  `policy-config-malformed` instead of a traceback — `adr_policy.yaml`
  itself failing to parse or not having a mapping root (loaded through a
  guard before any checker runs), the `layering_rules` /
  `oversized_source_files` blocks having wrong types or empty required
  lists, and an unparseable / non-mapping `oversized_allowlist.yaml`.
  Both ADR-015 blocks are *required* — an absent block is a malformation,
  not an opt-out, so the gates cannot be silently disabled. Path safety
  is enforced at a
  single chokepoint: `evaluate_repo_policy` drops any changed path that
  resolves outside the repository root (absolute, parent-traversal, or a
  planted symlink) *before any checker reads a file*, so the layering
  scan, the size cap, and the pre-existing import-direction and
  compat-wrapper checks all run on an already-validated list. The
  allowlist file path and each allowlist entry the drain check inspects
  are validated the same way. An out-of-tree path surfaces as the new
  `policy-path-unsafe` rule id and the target is never opened.
- `docs/api/sdl-semantics.rst` documenting the moved
  `aces_sdl.semantics.{objectives,workflow}` modules; `docs/index.md`
  toctree updated (ADR list + the new API page).
- Unit tests in `implementations/python/tests/test_repo_policy_tools.py`
  for the layering rule (all four import shapes + the prefix-boundary
  case), the cap (over/under/allowlisted/test-excluded), the drain rule
  (subset of the code constant; config cannot grow the locked set;
  premature drain rejected; legitimate drain passes), the
  stale-allowlist-entry rule (file below cap / missing / replaced by an
  out-of-tree symlink), the required-block and malformed-config paths
  (including a non-mapping/parse-broken `adr_policy.yaml`), the
  unsafe-path chokepoint, and the config-wide checks running on an empty
  changed list (deletion-only PRs).

### Changed

- Moved `aces_processor/semantics/{objectives,workflow}.py` to
  `aces_sdl/semantics/{objectives,workflow}.py`. These are SDL-language
  semantics — objective-window analysis, the workflow step-type contract,
  branch closure, and the (pure, stdlib-only) workflow step-result
  validator — needed by `aces_sdl/validator.py`. The move breaks the
  `aces_sdl ↔ aces_processor` circular import that ran through
  `aces_sdl/validator.py` →
  `aces_processor.semantics.{objectives,workflow}`. The whole module
  contents moved as a unit; `validate_workflow_step_result` stays with
  the rest of `workflow.py` (it is pure and has no import-time coupling
  to `aces_processor`, so moving it does not violate the layering rule
  and keeping it grouped avoids fragmenting `aces.core.semantics.workflow`).
  **Breaking change to the owning-package surface:** the import paths
  `aces_processor.semantics.objectives` and
  `aces_processor.semantics.workflow` no longer exist. Per ADR-009/010
  the *stable* public surface is the `aces.*` namespace, not the owning
  packages, so this follows the documented compatibility model: code
  that imported the owning-package paths directly must move to
  `aces_sdl.semantics.*`, and consumers of the stable API are
  unaffected — `aces.core.semantics.{objectives,workflow}` keep working,
  retargeted to re-export from `aces_sdl.semantics.*`.
- `aces_processor/semantics/planner.py` is **not** moved — it is
  processor-runtime reconciliation logic over a processor artifact
  (resource-action reconciliation between compiled resources and runtime
  snapshots, dependency graphs over compiled-resource addresses),
  consumed only by `aces_processor`, and stays there. After this PR
  `aces_processor.semantics` contains only `planner`.
- Updated import sites in `aces_processor/{compiler,manager,models}.py`
  and `aces_sdl/validator.py` to reach the moved modules via
  `aces_sdl.semantics.{objectives,workflow}`. `aces_processor/manager.py`
  keeps `.semantics.planner` for the planner helpers.
- Retargeted the `aces.core.semantics.{objectives,workflow}`
  compatibility wrappers to `aces_sdl.semantics.*`.
  `aces.core.semantics.planner` is unchanged. Tests that import via the
  `aces.core.semantics.*` namespace work without modification.
- `docs/api/sdl-semantics.rst` (new) documents the moved
  `aces_sdl.semantics.{objectives,workflow}` modules;
  `docs/api/processor-semantics.rst` is rescoped to
  `aces_processor.semantics.planner` only.

## [0.13.0] - 2026-05-09

### Added

- `AUT-807` ("Machine-Readable Guidance And Discovery Surfaces") MCP
  server at `implementations/python/packages/aces_mcp/`, exposing 14
  tools for SDL understanding, authoring, and inspection to any agent
  speaking the Model Context Protocol. Tools split across three
  modules:
  - `aces_mcp.tools.reference` — `sdl_overview`,
    `sdl_section_reference`, `sdl_get_example`, `sdl_parser_reference`,
    `sdl_validation_reference`.
  - `aces_mcp.tools.authoring` — `sdl_validate`, `sdl_scaffold`,
    `sdl_instantiate`, `sdl_compose`, `sdl_minimal_example`.
  - `aces_mcp.tools.inspection` — `sdl_list_elements`,
    `sdl_get_element`, `sdl_check_references`, `sdl_diagram`.
  Recreates PR #2 on top of the post-realignment dev branch with all
  imports retargeted from `aces.core.sdl.*` to the canonical
  `aces_sdl.*` packages, plus the original entry-point bug fixed
  (`aces-mcp = "aces_mcp.server:main"` rather than the broken
  `aces.mcp.__main__:server.run` form that re-imported the module
  during entry-point resolution and triggered a double-run).
- `mcp>=1.0.0` runtime dependency in
  `implementations/python/pyproject.toml`. The aces_mcp package and
  test file are added to the `documentation-surfaces` policy phase
  ownership.
- 45 unit tests covering all 14 tools, all three scaffold templates
  (verified to produce valid SDL), and the three example scenarios.

### Changed

- `AUT-807` and `AUT-809` transitioned from DRAFT to ACTIVE in Ground
  Control. The MCP server materially implements AUT-807 (machine-
  readable discovery) and contributes to AUT-809 (semantic parity
  across agent / CLI / docs surfaces). Traceability IMPLEMENTS / TESTS
  links recorded against AUT-807 for every aces_mcp file and the test
  file.

## [0.12.0] - 2026-05-09

### Added

- ADR-014 ("nox as the Canonical Verification Graph") capturing the
  rationale for nox-as-canonical-gate that was introduced in 0.10.0
  without an accompanying ADR. The decision codifies what the
  repository already does: one verification graph in `noxfile.py`, with
  pre-commit, pre-push, and CI all resolving through the same `_run_*`
  helpers, and `.ground-control.yaml` exposing the same commands to
  ecosystem agents.
- `.ground-control.yaml` now declares `workflow.format_command`
  (`nox -s hygiene`) and tightens `workflow.lint_command` from the
  full `verify` graph to the dedicated `lint` session. Optional
  `docs.adr_dir`, `example_paths.{source,test}`, and
  `requirements.uid_examples` blocks are populated so the
  ground-control context the `/implement` skill consumes points at
  this repository's actual paths and UID style instead of generic
  fallbacks.

## [0.11.0] - 2026-05-09

### Added

- `AUT-805` ("Canonical Documentation, Glossary, And Reference Material")
  Sphinx documentation site under `docs/` with `furo` theme, MyST markdown
  support, copy-button, and autodoc against the canonical packages
  (`aces_cli`, `aces_sdl`, `aces_processor`, `aces_processor.semantics`).
  Recreates the original PR #1 work on top of the post-realignment layout
  per ADR-009/010. API reference pages target the canonical `aces_*`
  packages rather than the `aces.*` compatibility shims.
- `nox -s docs` session that runs `sphinx-build`, joining the canonical
  verification graph alongside hygiene, policy, lint, contracts, and
  tests. Local hooks and CI invoke the same session.
- `docs` extras in `implementations/python/pyproject.toml` covering
  `sphinx`, `furo`, `myst-parser`, `sphinx-copybutton`, and
  `sphinx-autobuild`.
- New `documentation-surfaces` phase in
  `tools/policy/requirement_order.yaml` covering `AUT-805`, `AUT-807`,
  `AUT-809`, and `ASR-516`. Phase is blocked on `gov-concept-authority`
  (canonical concepts must exist before they can be documented) and
  owns `docs/`, `implementations/python/pyproject.toml`, and
  `implementations/python/uv.lock`.

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
- Contract-surface coverage in
  `implementations/python/tests/test_run_311_participant_episode_lifecycle.py`
  exercising every clause of the requirement (initialization, reset,
  completion, timeout, truncation, interruption, restart) at the
  ``ParticipantEpisodeExecutionState`` /
  ``ParticipantEpisodeHistoryEvent`` boundary, plus the per-clause
  invariants on stable participant identity across resets/restarts.
  End-to-end coverage of the runtime + HTTP control surfaces lives
  alongside the participant runtime added under finding 1 below
  (``test_runtime_control_plane.py::TestParticipantEpisodeControlPlane``
  and
  ``test_runtime_control_plane_api.py::TestParticipantEpisodeHttpRoutes``).
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
  `participant_episode_results` / `participant_episode_history` from
  the live ``RuntimeControlPlane.snapshot``. Note: the original drop
  of this entry overstated coverage by implying serialization alone
  rejected malformed data; the *active* lifecycle drive that actually
  produces and validates participant data lives under finding 4 below.
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

- Production-readiness review finding 5: tighten the original 0.10.0
  release notes that overstated RUN-311 completeness relative to the
  contract-only code that initially landed. The
  ``test_run_311_participant_episode_lifecycle.py`` entry is now
  scoped to "contract-surface coverage" with an explicit pointer to
  the runtime/HTTP test classes added under finding 1, and the
  ``_live_target_cases`` entry now distinguishes the original
  serialization-only behavior from the active lifecycle drive added
  under finding 4. Findings 1-4 below independently document the
  runtime, conformance, and validation gaps the original wording
  understated; this entry exists so the historical Added section
  describes only what shipped at each point in time.
- Production-readiness review finding 4: ``aces_conformance.conformance``
  now actively drives a full participant episode lifecycle whenever the
  target advertises a participant runtime. ``_live_target_cases`` calls
  the new ``_drive_participant_episode_probe`` which submits
  ``initialize`` / ``reset`` / ``terminate`` / ``restart`` through the
  control plane, then adds a ``participant-snapshot-consistent``
  conformance case that fails when ``participant_episode_results`` or
  ``participant_episode_history`` is empty after the lifecycle, or when
  the resulting snapshot violates ``iter_participant_episode_snapshot_violations``.
  Backends that register a participant runtime but never publish
  state/history through the snapshot now fail conformance instead of
  silently certifying clean. Regression coverage in
  ``test_live_probe_catches_participant_runtime_that_does_not_populate_snapshot``.
- Production-readiness review finding 3: ``profile_for_manifest`` now
  promotes a manifest that declares orchestrator, evaluator, AND
  participant runtime to ``BackendCapabilityProfile.FULL_REMOTE_CONTROL_PLANE``
  so the default ``run_target_conformance`` path automatically validates
  the live target against the participant-episode contract family
  (RUN-311) without callers having to override the profile.
  ``_capability_gaps`` now requires a ``participant_runtime`` component
  for that profile, and ``test_runtime_conformance`` covers both the
  promotion path and the orchestration-evaluation fallback for backends
  that omit the participant runtime block.
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
