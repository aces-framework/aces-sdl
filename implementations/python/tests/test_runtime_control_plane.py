"""Reference runtime control-plane tests."""

from __future__ import annotations

import textwrap

from aces_backend_stubs.stubs import create_stub_components, create_stub_manifest
from aces_processor.models import iter_participant_episode_snapshot_violations

from aces.backends.stubs import create_stub_target
from aces.core.runtime.compiler import compile_runtime_model
from aces.core.runtime.control_plane import RuntimeControlPlane
from aces.core.runtime.models import (
    OperationState,
    ParticipantEpisodeTerminalReason,
    RuntimeDomain,
)
from aces.core.runtime.planner import plan
from aces.core.runtime.registry import RuntimeTarget
from aces.core.sdl import parse_sdl


def _scenario(yaml_str: str):
    return parse_sdl(textwrap.dedent(yaml_str))


def test_control_plane_submits_provisioning_and_updates_snapshot():
    scenario = _scenario("""
name: provision
nodes:
  vm:
    type: vm
    os: linux
    resources: {ram: 1 gib, cpu: 1}
""")
    execution_plan = plan(compile_runtime_model(scenario), create_stub_target().manifest)
    control_plane = RuntimeControlPlane(create_stub_target())

    receipt = control_plane.submit_provisioning(execution_plan.provisioning)
    status = control_plane.get_operation(receipt.operation_id)
    snapshot = control_plane.get_snapshot()

    assert receipt.accepted is True
    assert receipt.domain == RuntimeDomain.PROVISIONING
    assert status is not None
    assert status.state == OperationState.SUCCEEDED
    assert snapshot.snapshot.entries


def test_control_plane_submits_orchestration_with_portable_workflow_state():
    scenario = _scenario("""
name: workflow
nodes:
  vm:
    type: vm
    os: linux
    resources: {ram: 1 gib, cpu: 1}
    conditions: {health: ops}
    roles: {ops: operator}
conditions:
  health: {command: /bin/true, interval: 15}
entities:
  blue: {role: blue}
objectives:
  validate:
    entity: blue
    success: {conditions: [health]}
workflows:
  response:
    start: run
    steps:
      run:
        type: objective
        objective: validate
        on-success: finish
      finish: {type: end}
""")
    target = create_stub_target()
    execution_plan = plan(compile_runtime_model(scenario), target.manifest)
    control_plane = RuntimeControlPlane(target)

    receipt = control_plane.submit_orchestration(execution_plan.orchestration)
    status = control_plane.get_operation(receipt.operation_id)
    snapshot = control_plane.get_snapshot()

    assert receipt.accepted is True
    assert status is not None
    assert status.state == OperationState.SUCCEEDED
    workflow_result = next(iter(snapshot.snapshot.orchestration_results.values()))
    assert workflow_result["workflow_status"] == "running"
    assert "run_id" in workflow_result
    assert snapshot.snapshot.orchestration_history


class TestParticipantEpisodeControlPlane:
    """RUN-311 — runtime-level participant episode control methods.

    These exercise the full ``initialize → reset → terminate → restart``
    lifecycle through the control plane, asserting that each backend
    ``ApplyResult`` is persisted into the snapshot, each operation gets
    a succeeded ``OperationStatus``, and the resulting
    ``participant_episode_results`` / ``participant_episode_history``
    satisfy the RUN-311 invariants.
    """

    def test_initialize_creates_first_episode_with_running_state(self):
        control_plane = RuntimeControlPlane(create_stub_target())

        receipt = control_plane.initialize_participant_episode("participant.alice")
        status = control_plane.get_operation(receipt.operation_id)
        snapshot = control_plane.get_snapshot()

        assert receipt.accepted is True
        assert receipt.domain == RuntimeDomain.PARTICIPANT
        assert status is not None
        assert status.state == OperationState.SUCCEEDED
        state = snapshot.snapshot.participant_episode_results["participant.alice"]
        assert state["status"] == "running"
        assert state["sequence_number"] == 0
        assert state["previous_episode_id"] is None
        assert state["last_control_action"] == "initialize"
        history = snapshot.snapshot.participant_episode_history["participant.alice"]
        assert [event["event_type"] for event in history] == [
            "episode_initialized",
            "episode_running",
        ]

    def test_initialize_twice_rejects_duplicate(self):
        control_plane = RuntimeControlPlane(create_stub_target())
        control_plane.initialize_participant_episode("participant.alice")

        receipt = control_plane.initialize_participant_episode("participant.alice")
        status = control_plane.get_operation(receipt.operation_id)

        assert status is not None
        assert status.state == OperationState.FAILED
        assert any("already has a live episode" in diag.message for diag in status.diagnostics)

    def test_reset_allocates_new_episode_preserving_identity(self):
        control_plane = RuntimeControlPlane(create_stub_target())
        control_plane.initialize_participant_episode("participant.alice")

        receipt = control_plane.reset_participant_episode("participant.alice", reason="operator reset")
        status = control_plane.get_operation(receipt.operation_id)
        snapshot = control_plane.get_snapshot()

        assert status is not None
        assert status.state == OperationState.SUCCEEDED
        state = snapshot.snapshot.participant_episode_results["participant.alice"]
        assert state["sequence_number"] == 1
        assert state["last_control_action"] == "reset"
        assert state["previous_episode_id"] == "participant.alice-episode-1"
        assert state["episode_id"] == "participant.alice-episode-2"
        assert state["status"] == "running"

    def test_reset_rejects_terminated_participant(self):
        control_plane = RuntimeControlPlane(create_stub_target())
        control_plane.initialize_participant_episode("participant.alice")
        control_plane.terminate_participant_episode(
            "participant.alice",
            terminal_reason=ParticipantEpisodeTerminalReason.COMPLETED,
        )

        receipt = control_plane.reset_participant_episode("participant.alice")
        status = control_plane.get_operation(receipt.operation_id)

        assert status is not None
        assert status.state == OperationState.FAILED
        assert any("use restart" in diag.message for diag in status.diagnostics)

    def test_terminate_drives_state_to_terminated_with_reason(self):
        control_plane = RuntimeControlPlane(create_stub_target())
        control_plane.initialize_participant_episode("participant.alice")

        receipt = control_plane.terminate_participant_episode(
            "participant.alice",
            terminal_reason=ParticipantEpisodeTerminalReason.TIMED_OUT,
        )
        status = control_plane.get_operation(receipt.operation_id)
        snapshot = control_plane.get_snapshot()

        assert status is not None
        assert status.state == OperationState.SUCCEEDED
        state = snapshot.snapshot.participant_episode_results["participant.alice"]
        assert state["status"] == "terminated"
        assert state["terminal_reason"] == "timed_out"
        assert state["terminated_at"] is not None
        history = snapshot.snapshot.participant_episode_history["participant.alice"]
        assert history[-1]["event_type"] == "episode_timed_out"
        assert history[-1]["terminal_reason"] == "timed_out"

    def test_terminate_rejects_already_terminated(self):
        control_plane = RuntimeControlPlane(create_stub_target())
        control_plane.initialize_participant_episode("participant.alice")
        control_plane.terminate_participant_episode("participant.alice")

        receipt = control_plane.terminate_participant_episode("participant.alice")
        status = control_plane.get_operation(receipt.operation_id)

        assert status is not None
        assert status.state == OperationState.FAILED
        assert any("already terminated" in diag.message for diag in status.diagnostics)

    def test_restart_resumes_from_terminated_predecessor(self):
        control_plane = RuntimeControlPlane(create_stub_target())
        control_plane.initialize_participant_episode("participant.alice")
        control_plane.terminate_participant_episode(
            "participant.alice",
            terminal_reason=ParticipantEpisodeTerminalReason.COMPLETED,
        )

        receipt = control_plane.restart_participant_episode("participant.alice")
        status = control_plane.get_operation(receipt.operation_id)
        snapshot = control_plane.get_snapshot()

        assert status is not None
        assert status.state == OperationState.SUCCEEDED
        state = snapshot.snapshot.participant_episode_results["participant.alice"]
        assert state["sequence_number"] == 1
        assert state["last_control_action"] == "restart"
        assert state["previous_episode_id"] == "participant.alice-episode-1"
        assert state["status"] == "running"

    def test_restart_rejects_non_terminated_participant(self):
        control_plane = RuntimeControlPlane(create_stub_target())
        control_plane.initialize_participant_episode("participant.alice")

        receipt = control_plane.restart_participant_episode("participant.alice")
        status = control_plane.get_operation(receipt.operation_id)

        assert status is not None
        assert status.state == OperationState.FAILED
        assert any("non-terminated" in diag.message for diag in status.diagnostics)

    def test_initialize_rejects_target_without_participant_runtime(self):
        manifest = create_stub_manifest(with_participant_runtime=False)
        components = create_stub_components(manifest=manifest)
        target = RuntimeTarget(
            name="no-participant",
            manifest=manifest,
            provisioner=components.provisioner,
            orchestrator=components.orchestrator,
            evaluator=components.evaluator,
        )
        control_plane = RuntimeControlPlane(target)

        receipt = control_plane.initialize_participant_episode("participant.alice")
        status = control_plane.get_operation(receipt.operation_id)

        assert receipt.accepted is False
        assert status is not None
        assert status.state == OperationState.FAILED
        assert any("does not provide a participant runtime" in diag.message for diag in receipt.diagnostics)

    def test_full_lifecycle_snapshot_chain_is_consistent(self):
        """End-to-end: initialize → reset → terminate → restart and verify
        history chain matches the final result (RUN-311 cross-check invariant).
        """
        control_plane = RuntimeControlPlane(create_stub_target())

        control_plane.initialize_participant_episode("participant.alice")
        control_plane.reset_participant_episode("participant.alice")
        control_plane.terminate_participant_episode(
            "participant.alice",
            terminal_reason=ParticipantEpisodeTerminalReason.COMPLETED,
        )
        control_plane.restart_participant_episode("participant.alice")

        snapshot = control_plane.get_snapshot().snapshot
        violations = list(
            iter_participant_episode_snapshot_violations(
                snapshot.participant_episode_results,
                snapshot.participant_episode_history,
            )
        )
        assert violations == [], (
            f"Full participant lifecycle must satisfy every RUN-311 snapshot invariant; got violations: {violations}"
        )

    def test_initialize_is_idempotent_via_idempotency_key(self):
        """Idempotency — a second submission with the same idempotency key
        must return the original receipt without running the backend twice.
        """
        control_plane = RuntimeControlPlane(create_stub_target())

        first = control_plane.initialize_participant_episode(
            "participant.alice",
            idempotency_key="init-alice-1",
        )
        second = control_plane.initialize_participant_episode(
            "participant.alice",
            idempotency_key="init-alice-1",
        )

        assert first.operation_id == second.operation_id
        snapshot = control_plane.get_snapshot().snapshot
        history = snapshot.participant_episode_history["participant.alice"]
        assert [event["event_type"] for event in history] == [
            "episode_initialized",
            "episode_running",
        ]
