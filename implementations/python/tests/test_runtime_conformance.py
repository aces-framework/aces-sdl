"""Backend conformance tests."""

from __future__ import annotations

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

    assert report.profile == BackendCapabilityProfile.ORCHESTRATION_EVALUATION
    assert report.passed is True
    assert not report.unsupported_contract_gaps
    assert not report.unsupported_capability_gaps


def test_profile_is_inferred_from_manifest_shape():
    target = create_stub_target()

    assert profile_for_manifest(target.manifest) == BackendCapabilityProfile.ORCHESTRATION_EVALUATION


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

    assert report.profile == BackendCapabilityProfile.ORCHESTRATION_EVALUATION
    assert report.passed is False
    assert set(report.unsupported_contract_gaps) == {
        "evaluation-history-event-stream-v1",
        "evaluation-result-envelope-v1",
        "operation-receipt-v1",
        "operation-status-v1",
        "runtime-snapshot-v1",
        "workflow-history-event-stream-v1",
        "workflow-result-envelope-v1",
    }
    assert any(diagnostic.code == "conformance.unsupported-contract-declaration" for diagnostic in report.diagnostics)
