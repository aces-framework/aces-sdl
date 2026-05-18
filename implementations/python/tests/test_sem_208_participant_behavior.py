"""SEM-208: participant behavior action/observation semantics tests."""

from __future__ import annotations

import textwrap

import pytest
from aces_contracts.contracts import schema_bundle
from aces_processor.compiler import compile_runtime_model
from aces_processor.models import (
    ParticipantBehaviorHistoryEvent,
    ParticipantBehaviorHistoryEventType,
    ParticipantObservationStatus,
    iter_participant_behavior_history_violations,
)
from aces_sdl._errors import SDLValidationError
from aces_sdl.parser import parse_sdl

T0 = "2026-05-18T18:30:00Z"
T1 = "2026-05-18T18:30:05Z"
T2 = "2026-05-18T18:30:10Z"
PARTICIPANT_ADDRESS = "participant.behavior.red-agent"
ACTION_ADDRESS = "participant.action-contract.scan"
OBSERVATION_ADDRESS = "participant.observation-boundary.red-view"
ACTION_INSTANCE = "scan-0001"
POST_STATE_DIGEST = "sha256:fb2f5a36c0d7d2a0"


def _scenario_yaml(*, actions: str = "[scan]", boundaries: str = "[red-view]") -> str:
    return textwrap.dedent(
        f"""
        name: sem-208
        entities:
          red-team:
            role: red
        action-contracts:
          scan:
            semantic-version: 1.0.0
            lifecycle-state: active
            behavioral-granularity: atomic
            procedure-basis: nmap service discovery
            realization-profile: backend-declared
            fidelity-claim: records participant discovery intent and terminal observation
            preconditions: [authority-in-scope]
            intended-effects: [discover network services]
            state-transition-effects: [participant knowledge expands]
            observation-expectations: [terminal scan result]
            evidence-expectations: [tool output]
            failure-classes: [target_unreachable]
            external-mappings:
              - system: attack
                identifier: T1046
                loss-label: technique-to-contract
                rationale: ATT&CK does not encode ACES observation or state-transition semantics
        observation-boundaries:
          red-view:
            projection-basis: participant-local projection over observed services
            observable-refs: [nodes.web, evidence.scan-output]
            hidden-refs: [content.private-answer-key]
            evidence-refs: [evidence.scan-output]
            redaction-policy: hidden refs never project without explicit disclosure
            latency-profile: terminal observation emitted after state transition commit
            observer-effects: [tool execution may affect telemetry]
        agents:
          red-agent:
            entity: red-team
            actions: {actions}
            observation-boundaries: {boundaries}
        """
    )


def test_participant_behavior_contracts_parse_and_validate():
    scenario = parse_sdl(_scenario_yaml())

    assert scenario.action_contracts["scan"].semantic_version == "1.0.0"
    assert scenario.action_contracts["scan"].lifecycle_state.value == "active"
    assert scenario.observation_boundaries["red-view"].projection_basis.startswith("participant-local")
    assert scenario.agents["red-agent"].observation_boundaries == ["red-view"]


def test_agent_actions_must_resolve_to_governed_action_contracts():
    with pytest.raises(SDLValidationError) as excinfo:
        parse_sdl(_scenario_yaml(actions="[scan, exploit]"))

    assert "Agent 'red-agent' action 'exploit' does not reference a declared action_contract" in str(excinfo.value)


def test_agent_observation_boundaries_must_resolve_to_declared_boundaries():
    with pytest.raises(SDLValidationError) as excinfo:
        parse_sdl(_scenario_yaml(boundaries="[red-view, leaked-view]"))

    assert (
        "Agent 'red-agent' observation_boundary 'leaked-view' does not reference a declared observation_boundary"
        in str(excinfo.value)
    )


def test_compiler_maps_participant_behavior_to_runtime_addresses():
    model = compile_runtime_model(parse_sdl(_scenario_yaml()))

    assert set(model.action_contracts) == {ACTION_ADDRESS}
    assert set(model.observation_boundaries) == {OBSERVATION_ADDRESS}

    binding = model.participant_behaviors[PARTICIPANT_ADDRESS]
    assert binding.participant_name == "red-agent"
    assert binding.entity_name == "red-team"
    assert binding.action_contract_addresses == (ACTION_ADDRESS,)
    assert binding.observation_boundary_addresses == (OBSERVATION_ADDRESS,)
    assert binding.interpretation_mode == "role-neutral-projection"
    assert binding.spec["interpretation_mode"] == "role-neutral-projection"


def test_behavior_history_events_round_trip_with_compiled_addresses():
    event = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED,
        timestamp=T0,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        actor_provenance="participant:red-agent",
    )

    assert ParticipantBehaviorHistoryEvent.from_payload(event.to_payload()) == event

    with pytest.raises(ValueError, match="compiled participant action contract address"):
        ParticipantBehaviorHistoryEvent(
            event_type=ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED,
            timestamp=T0,
            participant_address=PARTICIPANT_ADDRESS,
            episode_id="episode-1",
            action_instance_id=ACTION_INSTANCE,
            action_contract_address="scan",
            actor_provenance="participant:red-agent",
        )


def test_behavior_history_requires_terminal_observation_for_action_instance():
    action = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED,
        timestamp=T0,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        actor_provenance="participant:red-agent",
    )

    violations = list(
        iter_participant_behavior_history_violations(
            [action.to_payload()],
            action_contract_addresses={ACTION_ADDRESS},
            observation_boundary_addresses={OBSERVATION_ADDRESS},
        )
    )

    assert violations == [
        (
            ACTION_INSTANCE,
            "participant action instance requires exactly one terminal observation or orphaned-action observation",
        )
    ]


def test_behavior_history_pairs_state_transition_and_terminal_observation():
    action = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED,
        timestamp=T0,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        actor_provenance="participant:red-agent",
    )
    transition = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.STATE_TRANSITION_RECORDED,
        timestamp=T1,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        state_transition_kind="participant_knowledge_expanded",
        post_state_digest=POST_STATE_DIGEST,
    )
    observation = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED,
        timestamp=T2,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        observation_boundary_address=OBSERVATION_ADDRESS,
        observation_status=ParticipantObservationStatus.TERMINAL,
        post_state_digest=POST_STATE_DIGEST,
    )

    assert (
        list(
            iter_participant_behavior_history_violations(
                [action.to_payload(), transition.to_payload(), observation.to_payload()],
                action_contract_addresses={ACTION_ADDRESS},
                observation_boundary_addresses={OBSERVATION_ADDRESS},
            )
        )
        == []
    )


def test_behavior_history_rejects_state_transition_observation_digest_mismatch():
    action = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED,
        timestamp=T0,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        actor_provenance="participant:red-agent",
    )
    transition = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.STATE_TRANSITION_RECORDED,
        timestamp=T1,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        state_transition_kind="participant_knowledge_expanded",
        post_state_digest=POST_STATE_DIGEST,
    )
    observation = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED,
        timestamp=T2,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        observation_boundary_address=OBSERVATION_ADDRESS,
        observation_status=ParticipantObservationStatus.TERMINAL,
        post_state_digest="sha256:different",
    )

    violations = list(
        iter_participant_behavior_history_violations(
            [action.to_payload(), transition.to_payload(), observation.to_payload()],
            action_contract_addresses={ACTION_ADDRESS},
            observation_boundary_addresses={OBSERVATION_ADDRESS},
        )
    )

    assert violations == [
        (
            ACTION_INSTANCE,
            "terminal observation post_state_digest must match the state transition post_state_digest",
        )
    ]


def test_behavior_history_allows_orphaned_action_observation_without_state_digest():
    action = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED,
        timestamp=T0,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        actor_provenance="participant:red-agent",
    )
    observation = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED,
        timestamp=T2,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        observation_boundary_address=OBSERVATION_ADDRESS,
        observation_status=ParticipantObservationStatus.ORPHANED_ACTION,
    )

    assert (
        list(
            iter_participant_behavior_history_violations(
                [action.to_payload(), observation.to_payload()],
                action_contract_addresses={ACTION_ADDRESS},
                observation_boundary_addresses={OBSERVATION_ADDRESS},
            )
        )
        == []
    )


def test_behavior_history_schema_is_published_as_closed_world_contract():
    generated = schema_bundle()

    schema = generated["participant-behavior-history-event-stream-v1"]
    event_schema = schema["items"]

    assert event_schema["additionalProperties"] is False
    assert "ParticipantBehaviorHistoryEventModel" in event_schema["title"]
