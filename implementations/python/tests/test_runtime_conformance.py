"""Backend conformance tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aces_backend_protocols.capabilities import BackendManifest
from aces_conformance.conformance import _semantic_diagnostics

from aces.backends.stubs import create_stub_components, create_stub_manifest, create_stub_target
from aces.core.runtime.conformance import (
    BackendCapabilityProfile,
    profile_for_manifest,
    required_contracts,
    run_fixture_suite,
    run_target_conformance,
)
from aces.core.runtime.registry import RuntimeTarget


def test_fixture_suite_passes_for_orchestration_evaluation_profile():
    report = run_fixture_suite(profile=BackendCapabilityProfile.ORCHESTRATION_EVALUATION)

    assert report.passed is True
    assert report.cases
    assert not report.diagnostics
    assert required_contracts(report.profile)


def test_target_conformance_passes_for_stub_target():
    report = run_target_conformance(create_stub_target())

    assert report.profile == BackendCapabilityProfile.FULL_REMOTE_CONTROL_PLANE
    assert report.passed is True
    assert not report.unsupported_contract_gaps
    assert not report.unsupported_capability_gaps
    # RUN-311 finding 4: the live probe must actually drive every
    # participant episode control action and end with a non-empty,
    # consistent snapshot for the conformance participant.
    case_names = {case.name for case in report.cases}
    assert {
        "participant-initialize",
        "participant-reset",
        "participant-terminate",
        "participant-restart",
        "participant-snapshot-consistent",
    }.issubset(case_names)
    for case in report.cases:
        if case.name in {
            "participant-initialize",
            "participant-reset",
            "participant-terminate",
            "participant-restart",
            "participant-snapshot-consistent",
        }:
            assert case.passed, (
                f"Live participant probe case {case.name!r} must succeed for the stub backend; "
                f"diagnostics: {[diag.message for diag in case.diagnostics]}"
            )


def test_profile_is_inferred_as_full_when_manifest_declares_participant_runtime():
    """RUN-311 — finding 3: a manifest that declares orchestrator,
    evaluator, and participant_runtime must infer the
    ``FULL_REMOTE_CONTROL_PLANE`` profile so the default
    ``run_target_conformance`` path validates the participant-episode
    contract family without requiring callers to override the profile.
    """

    target = create_stub_target()

    assert profile_for_manifest(target.manifest) == BackendCapabilityProfile.FULL_REMOTE_CONTROL_PLANE


def test_profile_falls_back_to_orchestration_evaluation_without_participant_runtime():
    """A manifest without participant_runtime continues to infer
    ``ORCHESTRATION_EVALUATION`` so existing two-tier backends remain
    compatible.
    """
    from aces_backend_stubs.stubs import create_stub_manifest

    manifest = create_stub_manifest(with_participant_runtime=False)
    assert profile_for_manifest(manifest) == BackendCapabilityProfile.ORCHESTRATION_EVALUATION


def test_live_probe_catches_participant_runtime_that_does_not_populate_snapshot():
    """RUN-311 finding 4: a backend that exposes the participant runtime
    surface but never publishes state/history through the snapshot must
    fail conformance, not silently certify clean.
    """
    from aces_backend_stubs.stubs import (
        StubEvaluator,
        StubOrchestrator,
        StubProvisioner,
        create_stub_manifest,
    )
    from aces_processor.models import ApplyResult

    class _SilentParticipantRuntime:
        """Accepts every action without mutating the snapshot."""

        def initialize(self, request, snapshot):
            return ApplyResult(success=True, snapshot=snapshot)

        def reset(self, request, snapshot):
            return ApplyResult(success=True, snapshot=snapshot)

        def restart(self, request, snapshot):
            return ApplyResult(success=True, snapshot=snapshot)

        def terminate(self, request, snapshot):
            return ApplyResult(success=True, snapshot=snapshot)

        def status(self):
            return {}

        def results(self):
            return {}

        def history(self):
            return {}

    manifest = create_stub_manifest()
    target = RuntimeTarget(
        name="silent-participant",
        manifest=manifest,
        provisioner=StubProvisioner(),
        orchestrator=StubOrchestrator(),
        evaluator=StubEvaluator(),
        participant_runtime=_SilentParticipantRuntime(),
    )

    report = run_target_conformance(target)

    assert report.profile == BackendCapabilityProfile.FULL_REMOTE_CONTROL_PLANE
    assert report.passed is False
    snapshot_case = next(case for case in report.cases if case.name == "participant-snapshot-consistent")
    assert snapshot_case.passed is False
    messages = [diag.message for diag in snapshot_case.diagnostics]
    assert any("exposes no participant_episode_results" in msg for msg in messages)
    assert any("exposes no participant_episode_history" in msg for msg in messages)


def test_fixture_suite_passes_for_full_remote_control_plane_profile():
    """RUN-311 — the FULL_REMOTE_CONTROL_PLANE profile now requires the
    participant episode envelope + history event stream fixtures, so running
    the fixture suite at that profile must succeed cleanly and must touch
    every newly-registered contract.
    """

    report = run_fixture_suite(profile=BackendCapabilityProfile.FULL_REMOTE_CONTROL_PLANE)

    assert report.passed is True
    assert not report.diagnostics
    contract_names = {case.contract_name for case in report.cases}
    assert "participant-episode-state-envelope-v1" in contract_names
    assert "participant-episode-history-event-stream-v1" in contract_names
    assert "participant-behavior-history-event-stream-v1" in contract_names


def test_runtime_snapshot_semantic_diagnostics_reject_invalid_participant_episode_state():
    """RUN-311 — a ``/snapshot`` payload that embeds participant episode state
    that violates the state-machine invariants (e.g. ``status=running`` with a
    terminal reason) must raise a ``conformance.semantic-invalid`` diagnostic.
    Without this guard, invalid RUN-311 data could pass both schema validation
    and conformance.
    """

    snapshot_payload = {
        "schema_version": "runtime-snapshot/v1",
        "entries": {},
        "orchestration_results": {},
        "orchestration_history": {},
        "evaluation_results": {},
        "evaluation_history": {},
        "participant_episode_results": {
            "participant.alice": {
                "state_schema_version": "participant-episode-state/v1",
                "participant_address": "participant.alice",
                "episode_id": "ep-0001",
                "sequence_number": 0,
                "status": "running",
                "terminal_reason": "completed",
                "initialized_at": "2026-04-12T10:00:00Z",
                "updated_at": "2026-04-12T10:00:05Z",
                "terminated_at": None,
                "last_control_action": "initialize",
                "previous_episode_id": None,
            }
        },
        "participant_episode_history": {},
        "metadata": {},
    }

    diagnostics = _semantic_diagnostics("runtime-snapshot-v1", snapshot_payload)

    codes = {diag.code for diag in diagnostics}
    assert "conformance.semantic-invalid" in codes
    assert any("participant episode result is invalid" in diag.message for diag in diagnostics)


def test_runtime_snapshot_semantic_diagnostics_reject_invalid_participant_episode_history():
    """RUN-311 — a history stream emitting ``episode_reset`` at
    ``sequence_number=0`` cannot correspond to any valid episode chain.
    Conformance must reject it with a semantic diagnostic.
    """

    snapshot_payload = {
        "schema_version": "runtime-snapshot/v1",
        "entries": {},
        "orchestration_results": {},
        "orchestration_history": {},
        "evaluation_results": {},
        "evaluation_history": {},
        "participant_episode_results": {},
        "participant_episode_history": {
            "participant.alice": [
                {
                    "event_type": "episode_reset",
                    "timestamp": "2026-04-12T10:00:00Z",
                    "participant_address": "participant.alice",
                    "episode_id": "ep-0001",
                    "sequence_number": 0,
                    "terminal_reason": None,
                    "control_action": "reset",
                    "details": {},
                }
            ]
        },
        "metadata": {},
    }

    diagnostics = _semantic_diagnostics("runtime-snapshot-v1", snapshot_payload)

    codes = {diag.code for diag in diagnostics}
    assert "conformance.semantic-invalid" in codes
    assert any("must report sequence_number>0" in diag.message for diag in diagnostics)


def test_runtime_snapshot_behavior_history_refs_must_match_snapshot_entries():
    action_address = "participant.action-contract.scan"
    missing_boundary_address = "participant.observation-boundary.missing"
    snapshot_payload = {
        "schema_version": "runtime-snapshot/v1",
        "entries": {
            action_address: {
                "address": action_address,
                "domain": "participant",
                "resource_type": "participant-action-contract",
                "payload": {},
                "ordering_dependencies": [],
                "refresh_dependencies": [],
                "status": "ready",
            }
        },
        "orchestration_results": {},
        "orchestration_history": {},
        "evaluation_results": {},
        "evaluation_history": {},
        "participant_episode_results": {},
        "participant_episode_history": {},
        "participant_behavior_history": {
            "participant.red": [
                {
                    "event_type": "action_attempted",
                    "timestamp": "2026-05-18T18:30:00Z",
                    "participant_address": "participant.red",
                    "episode_id": "episode-1",
                    "action_instance_id": "scan-1",
                    "action_contract_address": action_address,
                    "actor_provenance": "participant:red",
                    "details": {},
                },
                {
                    "event_type": "state_transition_recorded",
                    "timestamp": "2026-05-18T18:30:01Z",
                    "participant_address": "participant.red",
                    "episode_id": "episode-1",
                    "action_instance_id": "scan-1",
                    "action_contract_address": action_address,
                    "state_transition_kind": "knowledge-expanded",
                    "post_state_digest": "sha256:known",
                    "details": {},
                },
                {
                    "event_type": "observation_emitted",
                    "timestamp": "2026-05-18T18:30:02Z",
                    "participant_address": "participant.red",
                    "episode_id": "episode-1",
                    "action_instance_id": "scan-1",
                    "action_contract_address": action_address,
                    "observation_boundary_address": missing_boundary_address,
                    "observation_status": "terminal",
                    "post_state_digest": "sha256:known",
                    "details": {},
                },
            ]
        },
        "metadata": {},
    }

    diagnostics = _semantic_diagnostics("runtime-snapshot-v1", snapshot_payload)

    messages = [diagnostic.message for diagnostic in diagnostics]
    assert any("unknown observation_boundary_address" in message for message in messages)
    assert not any("unknown action_contract_address" in message for message in messages)


def test_target_conformance_fails_when_declared_contracts_do_not_cover_profile_requirements():
    reference_manifest = create_stub_manifest()
    manifest = BackendManifest(
        identity=reference_manifest.identity,
        supported_contract_versions=frozenset({"backend-manifest-v2"}),
        compatibility=reference_manifest.compatibility,
        realization_support=reference_manifest.realization_support,
        concept_bindings=reference_manifest.concept_bindings,
        constraints=reference_manifest.constraints,
        capabilities=reference_manifest.capabilities,
    )
    components = create_stub_components(manifest=manifest)
    target = RuntimeTarget(
        name=manifest.name,
        manifest=manifest,
        provisioner=components.provisioner,
        orchestrator=components.orchestrator,
        evaluator=components.evaluator,
        participant_runtime=components.participant_runtime,
    )

    report = run_target_conformance(target)

    # The reference stub manifest now declares participant_runtime, so
    # profile_for_manifest infers the FULL_REMOTE_CONTROL_PLANE profile
    # (RUN-311 finding 3). The contract gap set therefore also covers
    # the participant-episode contracts and the plan contracts that
    # the FULL profile requires.
    assert report.profile == BackendCapabilityProfile.FULL_REMOTE_CONTROL_PLANE
    assert report.passed is False
    assert set(report.unsupported_contract_gaps) == {
        "evaluation-history-event-stream-v1",
        "evaluation-plan-v1",
        "evaluation-result-envelope-v1",
        "operation-receipt-v1",
        "operation-status-v1",
        "orchestration-plan-v1",
        "participant-behavior-history-event-stream-v1",
        "participant-episode-history-event-stream-v1",
        "participant-episode-state-envelope-v1",
        "provisioning-plan-v1",
        "runtime-snapshot-v1",
        "workflow-history-event-stream-v1",
        "workflow-result-envelope-v1",
    }
    assert any(diagnostic.code == "conformance.unsupported-contract-declaration" for diagnostic in report.diagnostics)


def test_required_contracts_authority_is_the_published_backend_profile(tmp_path: Path):
    """ASR-502: the runner reads ``required_contracts(...)`` from the
    published ``contracts/profiles/backend/<profile>.json`` artifact, not
    from a code-side table. Pointing a temporary ``profiles_root`` at a
    synthetic profile must change the result the runner sees — proving
    the published JSON is the single source of truth."""

    synthetic = {
        "profile": "provisioning-only",
        "required_contracts": ["backend-manifest-v2"],
    }
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "provisioning-only.json").write_text(json.dumps(synthetic) + "\n", encoding="utf-8")

    contracts = required_contracts(
        BackendCapabilityProfile.PROVISIONING_ONLY,
        profiles_root=backend_dir,
    )

    assert contracts == frozenset({"backend-manifest-v2"})


def test_run_fixture_suite_uses_profiles_root_override(tmp_path: Path):
    """The fixture suite must accept a ``profiles_root`` override so the
    JSON authority is visible end-to-end, not just at ``required_contracts``."""

    synthetic = {
        "profile": "provisioning-only",
        "required_contracts": ["backend-manifest-v2"],
    }
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "provisioning-only.json").write_text(json.dumps(synthetic) + "\n", encoding="utf-8")

    report = run_fixture_suite(
        profile=BackendCapabilityProfile.PROVISIONING_ONLY,
        profiles_root=backend_dir,
    )

    contract_names = {case.contract_name for case in report.cases}
    assert contract_names == {"backend-manifest-v2"}
    assert report.passed is True


def test_in_code_profile_requirements_table_is_removed():
    """ASR-502 demands a single authority for backend profile contract sets.
    The pre-refactor ``_PROFILE_REQUIREMENTS`` dict was that authority; once
    the runner loads from ``contracts/profiles/backend/*.json`` the dict must
    be gone. This is a structural gate: if a future change re-introduces the
    in-code table, this test fails and the drift is caught before merge."""

    from aces_conformance import conformance as conformance_module

    assert not hasattr(conformance_module, "_PROFILE_REQUIREMENTS")


def test_required_contracts_rejects_unknown_profile_id(tmp_path: Path):
    """A profile id that has no published JSON should produce a clear error,
    not a silent empty contract set.

    ``required_contracts`` is the raising surface; the runner wraps it in
    :func:`_resolve_required_contracts` so the conformance report can stay
    structured. See ``test_run_fixture_suite_reports_profile_load_failure_*``.
    """

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()

    with pytest.raises(FileNotFoundError):
        required_contracts(
            BackendCapabilityProfile.PROVISIONING_ONLY,
            profiles_root=backend_dir,
        )


def test_run_fixture_suite_reports_profile_load_failure_as_diagnostic(tmp_path: Path):
    """ASR-502 + codex review (issue #66, finding 1): if the published
    profile cannot be loaded, the runner must still emit a structured
    :class:`BackendConformanceReport` with a ``conformance.profile-load-failed``
    diagnostic and ``passed=False``, not raise out of the conformance boundary.
    """

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()

    report = run_fixture_suite(
        profile=BackendCapabilityProfile.PROVISIONING_ONLY,
        profiles_root=backend_dir,
    )

    assert report.passed is False
    assert report.cases == ()
    codes = {diag.code for diag in report.diagnostics}
    assert "conformance.profile-load-failed" in codes


def test_run_fixture_suite_reports_malformed_profile_json_as_diagnostic(tmp_path: Path):
    """Malformed profile JSON must surface as a structured diagnostic, not a
    raw JSONDecodeError escape."""

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "provisioning-only.json").write_text("{not valid json", encoding="utf-8")

    report = run_fixture_suite(
        profile=BackendCapabilityProfile.PROVISIONING_ONLY,
        profiles_root=backend_dir,
    )

    assert report.passed is False
    codes = {diag.code for diag in report.diagnostics}
    assert "conformance.profile-load-failed" in codes


def test_run_fixture_suite_reports_schema_invalid_profile_as_diagnostic(tmp_path: Path):
    """A profile whose payload fails closed-world Pydantic validation must
    surface as a structured diagnostic, not a raw ValidationError escape."""

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "provisioning-only.json").write_text(
        json.dumps(
            {"profile": "provisioning-only", "required_contracts": ["definitely-not-a-published-contract-v999"]}
        ),
        encoding="utf-8",
    )

    report = run_fixture_suite(
        profile=BackendCapabilityProfile.PROVISIONING_ONLY,
        profiles_root=backend_dir,
    )

    assert report.passed is False
    codes = {diag.code for diag in report.diagnostics}
    assert "conformance.profile-load-failed" in codes


def test_run_fixture_suite_rejects_swapped_profile_identity(tmp_path: Path):
    """ASR-502 + codex review (issue #66, finding 2): a profile artifact
    whose ``profile`` field does not match the requested profile id must
    fail the load, not silently drive the wrong contract set."""

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "provisioning-only.json").write_text(
        json.dumps(
            {
                "profile": "full-remote-control-plane",
                "required_contracts": ["backend-manifest-v2"],
            }
        ),
        encoding="utf-8",
    )

    report = run_fixture_suite(
        profile=BackendCapabilityProfile.PROVISIONING_ONLY,
        profiles_root=backend_dir,
    )

    assert report.passed is False
    codes = {diag.code for diag in report.diagnostics}
    assert "conformance.profile-load-failed" in codes
    assert any("full-remote-control-plane" in diag.message for diag in report.diagnostics)


def test_run_target_conformance_surfaces_profile_load_failure(tmp_path: Path):
    """The target-conformance entry point must also convert profile-load
    failures into structured diagnostics rather than raise — the boundary
    applies to every public conformance surface.

    Codex review (issue #66, finding 1 of cycle 2): a failed profile load is
    a hard prerequisite, so the runner must NOT proceed to ``_live_target_cases``
    (which would submit provisioning/orchestration/evaluation actions against
    the target). The report must therefore contain no live probe cases.
    """

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()

    report = run_target_conformance(create_stub_target(), profiles_root=backend_dir)

    assert report.passed is False
    codes = {diag.code for diag in report.diagnostics}
    assert "conformance.profile-load-failed" in codes
    case_names = {case.name for case in report.cases}
    assert "live-manifest" not in case_names
    assert "live-snapshot" not in case_names
    assert "participant-initialize" not in case_names


def test_run_target_conformance_refuses_unknown_profile_id(tmp_path: Path):
    """ASR-502 + codex review (issue #66, finding 2 of cycle 4): target
    conformance enforces runtime-surface gates (orchestrator/evaluator/
    participant_runtime). Those gates depend on knowing the profile's
    runtime-surface contract; an unknown profile id has no such authority.
    The runner must refuse with a structured
    ``conformance.profile-runtime-surface-unknown`` diagnostic instead of
    silently certifying a target that's missing every required role."""

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "future-control-plane.json").write_text(
        json.dumps(
            {
                "schema_version": "backend-profile/v1",
                "profile": "future-control-plane",
                "required_contracts": ["backend-manifest-v2"],
            }
        ),
        encoding="utf-8",
    )

    report = run_target_conformance(
        create_stub_target(),
        profile="future-control-plane",
        profiles_root=backend_dir,
    )

    assert report.passed is False
    codes = {diag.code for diag in report.diagnostics}
    assert "conformance.profile-runtime-surface-unknown" in codes
    case_names = {case.name for case in report.cases}
    assert "live-manifest" not in case_names
    assert "live-snapshot" not in case_names


def test_run_fixture_suite_path_traversal_id_surfaces_as_load_diagnostic(tmp_path: Path):
    """ASR-502 + codex review (issue #66, cycle 4 security finding): a profile
    id that contains path separators must be rejected at the loader and
    surface as a structured ``conformance.profile-load-failed`` diagnostic,
    not escape the profile root."""

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()

    report = run_fixture_suite(profile="../etc/passwd", profiles_root=backend_dir)

    assert report.passed is False
    codes = {diag.code for diag in report.diagnostics}
    assert "conformance.profile-load-failed" in codes


def test_run_fixture_suite_load_failure_diagnostic_does_not_echo_input(tmp_path: Path):
    """Codex review (issue #66, cycle 4 security finding, sanitization arm):
    the profile-load diagnostic must not echo the rejected JSON payload
    verbatim. A Pydantic ``ValidationError`` carries the rejected input;
    rendering it through ``str(exc)`` would turn a malformed-profile failure
    into a file-content disclosure when the loader is wrapped behind a
    less-trusted boundary."""

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    sentinel = "PRIVATE-DATA-SENTINEL-9D8A"
    (backend_dir / "provisioning-only.json").write_text(
        json.dumps(
            {
                "schema_version": "backend-profile/v1",
                "profile": "provisioning-only",
                "required_contracts": [sentinel],
            }
        ),
        encoding="utf-8",
    )

    report = run_fixture_suite(
        profile=BackendCapabilityProfile.PROVISIONING_ONLY,
        profiles_root=backend_dir,
    )

    assert report.passed is False
    for diag in report.diagnostics:
        assert sentinel not in diag.message, "profile-load diagnostic must not echo the rejected input value verbatim"
