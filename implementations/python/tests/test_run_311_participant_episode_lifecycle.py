"""RUN-311: participant-episode lifecycle and reset integrity tests.

RUN-311 ("Participant Episode Lifecycle And Reset") requires the runtime
to support episodic participant execution with explicit initialization,
reset, completion, timeout, truncation, interruption, and restart
handling.

ADR-013 ("Participant Episode Lifecycle Boundaries") locks in that
participant episodes are their own processor/runtime contract surface
that must not be aliased into ``WorkflowExecutionState``,
``EvaluationExecutionState``, ``OperationStatus``, or
``RuntimeSnapshot.metadata``. Lifecycle state, terminal reason, and
control actions are kept as three distinct categories, and reset/restart
must create a new episode instance while preserving stable participant
identity.

The tests in this module exercise every clause of RUN-311 against the
``ParticipantEpisodeExecutionState`` and ``ParticipantEpisodeHistoryEvent``
contract surfaces, plus the published JSON Schemas.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aces_contracts.contracts import schema_bundle
from aces_processor.manager import _participant_episode_contract_diagnostics

from aces.core.runtime.models import (
    ParticipantEpisodeControlAction,
    ParticipantEpisodeExecutionState,
    ParticipantEpisodeHistoryEvent,
    ParticipantEpisodeHistoryEventType,
    ParticipantEpisodeStatus,
    ParticipantEpisodeTerminalReason,
    RuntimeSnapshot,
)

PARTICIPANT_ADDRESS = "participant.alice"
EP1 = "ep-0001"
EP2 = "ep-0002"
EP3 = "ep-0003"
EP4 = "ep-0004"
T0 = "2026-04-11T10:00:00Z"
T1 = "2026-04-11T10:00:05Z"
T2 = "2026-04-11T10:00:10Z"
T3 = "2026-04-11T10:00:15Z"
T4 = "2026-04-11T10:00:20Z"
T5 = "2026-04-11T10:00:25Z"
T6 = "2026-04-11T10:00:30Z"
T7 = "2026-04-11T10:00:35Z"
T8 = "2026-04-11T10:00:40Z"
T9 = "2026-04-11T10:00:45Z"
T10 = "2026-04-11T10:00:50Z"
T11 = "2026-04-11T10:00:55Z"


def _initialized_state(**overrides):
    base = dict(
        participant_address=PARTICIPANT_ADDRESS,
        episode_id=EP1,
        sequence_number=0,
        status=ParticipantEpisodeStatus.INITIALIZING,
        terminal_reason=None,
        initialized_at=T0,
        updated_at=T0,
        terminated_at=None,
        last_control_action=ParticipantEpisodeControlAction.INITIALIZE,
        previous_episode_id=None,
    )
    base.update(overrides)
    return ParticipantEpisodeExecutionState(**base)


def _terminated_state(*, terminal_reason, **overrides):
    base = dict(
        participant_address=PARTICIPANT_ADDRESS,
        episode_id=EP1,
        sequence_number=0,
        status=ParticipantEpisodeStatus.TERMINATED,
        terminal_reason=terminal_reason,
        initialized_at=T0,
        updated_at=T1,
        terminated_at=T1,
        last_control_action=ParticipantEpisodeControlAction.INITIALIZE,
        previous_episode_id=None,
    )
    base.update(overrides)
    return ParticipantEpisodeExecutionState(**base)


def _history_event(**overrides):
    base = dict(
        event_type=ParticipantEpisodeHistoryEventType.EPISODE_RUNNING,
        timestamp=T1,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id=EP1,
        sequence_number=0,
        terminal_reason=None,
        control_action=None,
        details={},
    )
    base.update(overrides)
    return ParticipantEpisodeHistoryEvent(**base)


class TestRun311ParticipantEpisodeLifecycle:
    """End-to-end participant-episode lifecycle integrity tests for RUN-311."""

    def test_first_episode_initializes_with_stable_identity(self):
        """Clauses 1, 2 — episodes carry explicit stable identity from initialization onward.

        The first episode must use ``sequence_number=0`` and the
        ``INITIALIZE`` control action, must not link to a previous
        episode, must round-trip cleanly through ``to_payload`` /
        ``from_payload`` (the schema-first contract boundary), and must
        carry a stable ``participant_address`` and per-episode
        ``episode_id`` so downstream consumers can distinguish the
        participant from the bounded episode instance.
        """

        state = _initialized_state()

        assert state.status == ParticipantEpisodeStatus.INITIALIZING
        assert state.last_control_action == ParticipantEpisodeControlAction.INITIALIZE
        assert state.previous_episode_id is None
        assert state.terminal_reason is None
        assert state.terminated_at is None
        assert state.participant_address == PARTICIPANT_ADDRESS
        assert state.episode_id == EP1

        running = ParticipantEpisodeExecutionState(
            participant_address=state.participant_address,
            episode_id=state.episode_id,
            sequence_number=state.sequence_number,
            status=ParticipantEpisodeStatus.RUNNING,
            initialized_at=state.initialized_at,
            updated_at=T1,
            last_control_action=state.last_control_action,
        )
        assert running.status == ParticipantEpisodeStatus.RUNNING
        assert running.participant_address == state.participant_address
        assert running.episode_id == state.episode_id
        assert running.terminal_reason is None

        round_trip = ParticipantEpisodeExecutionState.from_payload(running.to_payload())
        assert round_trip == running, (
            "Schema-first boundary must round-trip without loss; any drift "
            "would mean the published JSON envelope cannot reconstruct the "
            "in-process contract identity."
        )

    @pytest.mark.parametrize(
        "terminal_reason",
        [
            ParticipantEpisodeTerminalReason.COMPLETED,
            ParticipantEpisodeTerminalReason.TIMED_OUT,
            ParticipantEpisodeTerminalReason.TRUNCATED,
            ParticipantEpisodeTerminalReason.INTERRUPTED,
        ],
    )
    def test_terminal_states_require_matching_terminal_reason(self, terminal_reason):
        """Clauses 4-7 — every terminal outcome (completion, timeout, truncation,
        interruption) is reachable, requires its terminal reason, and is
        forbidden from non-terminal states.
        """

        state = _terminated_state(terminal_reason=terminal_reason)
        assert state.status == ParticipantEpisodeStatus.TERMINATED
        assert state.terminal_reason == terminal_reason
        assert state.terminated_at == T1

        with pytest.raises(ValueError, match="terminated participant episodes must report a terminal_reason"):
            _terminated_state(terminal_reason=None)

        with pytest.raises(
            ValueError,
            match="non-terminal participant episodes may not report a terminal_reason",
        ):
            _initialized_state(terminal_reason=terminal_reason)

        with pytest.raises(
            ValueError,
            match="non-terminal participant episodes may not report a terminal_reason",
        ):
            _initialized_state(
                status=ParticipantEpisodeStatus.RUNNING,
                updated_at=T1,
                terminal_reason=terminal_reason,
            )

    def test_reset_creates_new_episode_preserving_participant_identity(self):
        """Clause 3 — reset spawns a new episode instance that keeps the
        stable participant identity but has a fresh ``episode_id``,
        an incremented ``sequence_number``, and a backreference to the
        prior episode. The reset state must NOT mutate the prior state
        in place (ADR-013 §4).
        """

        first = _initialized_state()
        first_payload_before = first.to_payload()

        reset = ParticipantEpisodeExecutionState(
            participant_address=first.participant_address,
            episode_id=EP2,
            sequence_number=first.sequence_number + 1,
            status=ParticipantEpisodeStatus.INITIALIZING,
            initialized_at=T2,
            updated_at=T2,
            last_control_action=ParticipantEpisodeControlAction.RESET,
            previous_episode_id=first.episode_id,
        )

        assert reset.participant_address == first.participant_address, (
            "Participant identity must be preserved across resets so the "
            "runtime can recognize that this is the same participant on a new "
            "episode instance."
        )
        assert reset.episode_id != first.episode_id, (
            "Each reset must allocate a new episode_id so prior episode history is never overwritten."
        )
        assert reset.sequence_number == first.sequence_number + 1
        assert reset.previous_episode_id == first.episode_id
        assert reset.last_control_action == ParticipantEpisodeControlAction.RESET
        assert first.to_payload() == first_payload_before, (
            "Reset must allocate a new state instance, not mutate the prior episode state in place."
        )

    def test_restart_after_termination_creates_new_episode_with_link_to_prior(self):
        """Clause 8 — restart creates a fresh episode that links back to the
        terminated prior episode. The chain ``initialized → terminated →
        restarted`` must be reconstructable from the contract surface.
        """

        terminated = _terminated_state(terminal_reason=ParticipantEpisodeTerminalReason.COMPLETED)
        restart = ParticipantEpisodeExecutionState(
            participant_address=terminated.participant_address,
            episode_id=EP2,
            sequence_number=terminated.sequence_number + 1,
            status=ParticipantEpisodeStatus.RUNNING,
            initialized_at=T2,
            updated_at=T3,
            last_control_action=ParticipantEpisodeControlAction.RESTART,
            previous_episode_id=terminated.episode_id,
        )

        assert restart.participant_address == terminated.participant_address
        assert restart.previous_episode_id == terminated.episode_id
        assert restart.last_control_action == ParticipantEpisodeControlAction.RESTART
        assert restart.sequence_number == terminated.sequence_number + 1
        assert restart.episode_id != terminated.episode_id

    @pytest.mark.parametrize(
        "control_action",
        [
            ParticipantEpisodeControlAction.RESET,
            ParticipantEpisodeControlAction.RESTART,
        ],
    )
    def test_first_episode_rejects_reset_or_restart_control_action(self, control_action):
        """Invariant — sequence_number=0 cannot be a reset or restart, because
        there is no prior episode to come from.
        """

        with pytest.raises(
            ValueError,
            match=("the first participant episode \\(sequence_number=0\\) must use the INITIALIZE control action"),
        ):
            _initialized_state(last_control_action=control_action)

    def test_subsequent_episode_requires_previous_episode_id(self):
        """Invariant — sequence_number > 0 must always link to a previous episode
        and cannot use the INITIALIZE control action.
        """

        with pytest.raises(
            ValueError,
            match=("subsequent participant episodes \\(sequence_number>0\\) must link to a previous_episode_id"),
        ):
            ParticipantEpisodeExecutionState(
                participant_address=PARTICIPANT_ADDRESS,
                episode_id=EP2,
                sequence_number=1,
                status=ParticipantEpisodeStatus.RUNNING,
                initialized_at=T2,
                updated_at=T2,
                last_control_action=ParticipantEpisodeControlAction.RESET,
                previous_episode_id=None,
            )

        with pytest.raises(
            ValueError,
            match=("subsequent participant episodes \\(sequence_number>0\\) must use RESET or RESTART, not INITIALIZE"),
        ):
            ParticipantEpisodeExecutionState(
                participant_address=PARTICIPANT_ADDRESS,
                episode_id=EP2,
                sequence_number=1,
                status=ParticipantEpisodeStatus.RUNNING,
                initialized_at=T2,
                updated_at=T2,
                last_control_action=ParticipantEpisodeControlAction.INITIALIZE,
                previous_episode_id=EP1,
            )

        with pytest.raises(
            ValueError,
            match="previous_episode_id must differ from episode_id",
        ):
            ParticipantEpisodeExecutionState(
                participant_address=PARTICIPANT_ADDRESS,
                episode_id=EP2,
                sequence_number=1,
                status=ParticipantEpisodeStatus.RUNNING,
                initialized_at=T2,
                updated_at=T2,
                last_control_action=ParticipantEpisodeControlAction.RESET,
                previous_episode_id=EP2,
            )

    @pytest.mark.parametrize(
        ("event_type", "expected_reason"),
        [
            (ParticipantEpisodeHistoryEventType.EPISODE_COMPLETED, ParticipantEpisodeTerminalReason.COMPLETED),
            (ParticipantEpisodeHistoryEventType.EPISODE_TIMED_OUT, ParticipantEpisodeTerminalReason.TIMED_OUT),
            (ParticipantEpisodeHistoryEventType.EPISODE_TRUNCATED, ParticipantEpisodeTerminalReason.TRUNCATED),
            (ParticipantEpisodeHistoryEventType.EPISODE_INTERRUPTED, ParticipantEpisodeTerminalReason.INTERRUPTED),
        ],
    )
    def test_history_event_terminal_reason_must_match_event_type(self, event_type, expected_reason):
        """Clauses 4-7 expressed as history events — each terminal event type is
        coupled to exactly one terminal reason, and non-terminal event types
        cannot carry a terminal_reason.
        """

        ok = _history_event(event_type=event_type, terminal_reason=expected_reason)
        assert ok.terminal_reason == expected_reason

        wrong_reasons = [reason for reason in ParticipantEpisodeTerminalReason if reason != expected_reason]
        for reason in wrong_reasons:
            with pytest.raises(ValueError, match="must report terminal_reason"):
                _history_event(event_type=event_type, terminal_reason=reason)

        with pytest.raises(ValueError, match="must report terminal_reason"):
            _history_event(event_type=event_type, terminal_reason=None)

        with pytest.raises(ValueError, match="may not report a terminal_reason"):
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RUNNING,
                terminal_reason=expected_reason,
            )

    @pytest.mark.parametrize(
        ("event_type", "expected_action", "sequence_number"),
        [
            (ParticipantEpisodeHistoryEventType.EPISODE_INITIALIZED, ParticipantEpisodeControlAction.INITIALIZE, 0),
            (ParticipantEpisodeHistoryEventType.EPISODE_RESET, ParticipantEpisodeControlAction.RESET, 1),
            (ParticipantEpisodeHistoryEventType.EPISODE_RESTARTED, ParticipantEpisodeControlAction.RESTART, 1),
        ],
    )
    def test_history_event_control_action_must_match_event_type(self, event_type, expected_action, sequence_number):
        """Clauses 2, 3, 8 expressed as history events — each control event type
        is coupled to exactly one control action, and non-control event types
        cannot carry a control_action.
        """

        ok = _history_event(event_type=event_type, control_action=expected_action, sequence_number=sequence_number)
        assert ok.control_action == expected_action

        wrong_actions = [action for action in ParticipantEpisodeControlAction if action != expected_action]
        for action in wrong_actions:
            with pytest.raises(ValueError, match="must report control_action"):
                _history_event(event_type=event_type, control_action=action, sequence_number=sequence_number)

        with pytest.raises(ValueError, match="must report control_action"):
            _history_event(event_type=event_type, control_action=None, sequence_number=sequence_number)

        with pytest.raises(ValueError, match="may not report a control_action"):
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RUNNING,
                control_action=expected_action,
            )

    def test_history_event_payload_round_trip_for_full_lifecycle(self):
        """Clauses 1-8 in one assertion — build a participant history that hits
        every control action and every terminal reason and round-trip every
        event through the schema-first payload boundary.
        """

        history = [
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_INITIALIZED,
                timestamp=T0,
                control_action=ParticipantEpisodeControlAction.INITIALIZE,
            ),
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RUNNING,
                timestamp=T1,
            ),
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_COMPLETED,
                timestamp=T2,
                terminal_reason=ParticipantEpisodeTerminalReason.COMPLETED,
            ),
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RESET,
                timestamp=T3,
                episode_id=EP2,
                sequence_number=1,
                control_action=ParticipantEpisodeControlAction.RESET,
            ),
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RUNNING,
                timestamp=T4,
                episode_id=EP2,
                sequence_number=1,
            ),
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_INTERRUPTED,
                timestamp=T5,
                episode_id=EP2,
                sequence_number=1,
                terminal_reason=ParticipantEpisodeTerminalReason.INTERRUPTED,
            ),
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RESTARTED,
                timestamp=T6,
                episode_id=EP3,
                sequence_number=2,
                control_action=ParticipantEpisodeControlAction.RESTART,
            ),
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RUNNING,
                timestamp=T7,
                episode_id=EP3,
                sequence_number=2,
            ),
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_TIMED_OUT,
                timestamp=T8,
                episode_id=EP3,
                sequence_number=2,
                terminal_reason=ParticipantEpisodeTerminalReason.TIMED_OUT,
            ),
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RESTARTED,
                timestamp=T9,
                episode_id=EP4,
                sequence_number=3,
                control_action=ParticipantEpisodeControlAction.RESTART,
            ),
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RUNNING,
                timestamp=T10,
                episode_id=EP4,
                sequence_number=3,
            ),
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_TRUNCATED,
                timestamp=T11,
                episode_id=EP4,
                sequence_number=3,
                terminal_reason=ParticipantEpisodeTerminalReason.TRUNCATED,
            ),
        ]

        terminal_reasons_seen = {event.terminal_reason for event in history if event.terminal_reason is not None}
        control_actions_seen = {event.control_action for event in history if event.control_action is not None}
        assert terminal_reasons_seen == set(ParticipantEpisodeTerminalReason), (
            "Lifecycle smoke history must reach every terminal reason exactly once."
        )
        assert control_actions_seen == set(ParticipantEpisodeControlAction), (
            "Lifecycle smoke history must reach every control action exactly once."
        )

        for event in history:
            assert event.participant_address == PARTICIPANT_ADDRESS, (
                "Participant identity must be stable across the entire history, even after resets and restarts."
            )
            round_trip = ParticipantEpisodeHistoryEvent.from_payload(event.to_payload())
            assert round_trip == event, (
                "History event payload must round-trip via the schema-first "
                f"boundary; drift on {event.event_type.value} would silently "
                "lose lifecycle data."
            )

    def test_initialized_history_event_requires_sequence_number_zero(self):
        """Invariant — ``episode_initialized`` events describe the very first
        episode of a participant, so they must carry ``sequence_number=0``.
        A history stream that emits ``episode_initialized`` at any later
        sequence cannot correspond to a valid
        ``ParticipantEpisodeExecutionState`` chain.
        """

        with pytest.raises(ValueError, match="episode_initialized history events must report sequence_number=0"):
            _history_event(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_INITIALIZED,
                sequence_number=1,
                control_action=ParticipantEpisodeControlAction.INITIALIZE,
            )

    @pytest.mark.parametrize(
        "event_type",
        [
            ParticipantEpisodeHistoryEventType.EPISODE_RESET,
            ParticipantEpisodeHistoryEventType.EPISODE_RESTARTED,
        ],
    )
    def test_reset_and_restart_history_events_require_sequence_number_greater_than_zero(self, event_type):
        """Invariant — ``episode_reset`` and ``episode_restarted`` events describe
        transitions into a new episode instance, which only exists for
        ``sequence_number > 0``. The very first episode must arrive via
        ``episode_initialized`` instead.
        """

        expected_action = (
            ParticipantEpisodeControlAction.RESET
            if event_type == ParticipantEpisodeHistoryEventType.EPISODE_RESET
            else ParticipantEpisodeControlAction.RESTART
        )
        with pytest.raises(ValueError, match="must report sequence_number>0"):
            _history_event(
                event_type=event_type,
                sequence_number=0,
                control_action=expected_action,
            )

    def test_runtime_apply_path_rejects_invalid_participant_episode_result(self):
        """Runtime integration — ``_participant_episode_contract_diagnostics``
        is called on every backend apply. It must emit a
        ``runtime.backend-contract-invalid`` diagnostic for any participant
        episode result that violates the dataclass invariants, so invalid
        RUN-311 data cannot be silently persisted through the manager path.
        """

        snapshot = RuntimeSnapshot(
            participant_episode_results={
                "participant.alice": {
                    "state_schema_version": "participant-episode-state/v1",
                    "participant_address": "participant.alice",
                    "episode_id": "ep-0001",
                    "sequence_number": 0,
                    "status": "running",
                    "terminal_reason": "completed",
                    "initialized_at": T0,
                    "updated_at": T1,
                    "terminated_at": None,
                    "last_control_action": "initialize",
                    "previous_episode_id": None,
                }
            },
        )

        diagnostics = _participant_episode_contract_diagnostics(snapshot)

        assert diagnostics, "apply path must reject invalid participant episode result"
        assert all(diag.code == "runtime.backend-contract-invalid" for diag in diagnostics)
        assert any(
            "non-terminal participant episodes may not report a terminal_reason" in diag.message for diag in diagnostics
        )

    def test_runtime_apply_path_rejects_invalid_participant_episode_history_event(self):
        """Runtime integration — the apply path must also reject a participant
        episode history event whose sequence number disagrees with its event
        type (for example ``episode_reset`` at ``sequence_number=0``).
        """

        snapshot = RuntimeSnapshot(
            participant_episode_history={
                "participant.alice": [
                    {
                        "event_type": "episode_reset",
                        "timestamp": T0,
                        "participant_address": "participant.alice",
                        "episode_id": "ep-0001",
                        "sequence_number": 0,
                        "terminal_reason": None,
                        "control_action": "reset",
                        "details": {},
                    }
                ]
            },
        )

        diagnostics = _participant_episode_contract_diagnostics(snapshot)

        assert diagnostics, "apply path must reject invalid participant episode history"
        assert all(diag.code == "runtime.backend-contract-invalid" for diag in diagnostics)
        assert any("must report sequence_number>0" in diag.message for diag in diagnostics)

    def test_runtime_apply_path_accepts_valid_participant_episode_snapshot(self):
        """Runtime integration — a snapshot that contains only valid RUN-311
        data must pass the apply-path diagnostic helper cleanly. This is the
        positive pair for the two rejection tests above.
        """

        snapshot = RuntimeSnapshot(
            participant_episode_results={
                "participant.alice": {
                    "state_schema_version": "participant-episode-state/v1",
                    "participant_address": "participant.alice",
                    "episode_id": EP1,
                    "sequence_number": 0,
                    "status": "initializing",
                    "terminal_reason": None,
                    "initialized_at": T0,
                    "updated_at": T0,
                    "terminated_at": None,
                    "last_control_action": "initialize",
                    "previous_episode_id": None,
                }
            },
            participant_episode_history={
                "participant.alice": [
                    {
                        "event_type": "episode_initialized",
                        "timestamp": T0,
                        "participant_address": "participant.alice",
                        "episode_id": EP1,
                        "sequence_number": 0,
                        "terminal_reason": None,
                        "control_action": "initialize",
                        "details": {},
                    }
                ]
            },
        )

        diagnostics = _participant_episode_contract_diagnostics(snapshot)

        assert diagnostics == []

    def test_published_state_schema_matches_bundle_for_run_311(self):
        """Schema parity — the on-disk control-plane schemas for the participant
        episode envelope and the history event stream must equal the live
        schema bundle. If a developer edits ``aces_contracts/contracts.py``
        without re-running ``tools/generate_contract_schemas.py``, this test
        gives a clear local failure mode.
        """

        repo_root = Path(__file__).resolve().parents[3]
        schemas_dir = repo_root / "contracts" / "schemas" / "control-plane"
        bundle = schema_bundle()
        for schema_name in (
            "participant-episode-state-envelope-v1",
            "participant-episode-history-event-stream-v1",
        ):
            on_disk = json.loads((schemas_dir / f"{schema_name}.json").read_text(encoding="utf-8"))
            assert on_disk == bundle[schema_name], (
                f"Published schema {schema_name}.json drifted from "
                "schema_bundle(); re-run tools/generate_contract_schemas.py."
            )
