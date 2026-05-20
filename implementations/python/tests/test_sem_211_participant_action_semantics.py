"""SEM-211 participant action precondition/effect/failure semantics."""

from __future__ import annotations

import textwrap

import pytest
from aces_processor.compiler import compile_runtime_model
from aces_processor.models import (
    Diagnostic,
    ParticipantActionEffectResult,
    ParticipantActionPreconditionResult,
    ParticipantActionPreconditionStatus,
    ParticipantActionResult,
    ParticipantActionResultStatus,
    ParticipantBehaviorHistoryEvent,
    ParticipantBehaviorHistoryEventType,
    ParticipantObservationStatus,
    iter_participant_behavior_history_violations,
    map_backend_diagnostic_to_participant_failure,
)
from aces_sdl._errors import SDLParseError
from aces_sdl.parser import parse_sdl
from aces_sdl.participant_behavior import (
    ParticipantEffectClass,
    ParticipantFailureClass,
    ParticipantPreconditionClass,
)

T0 = "2026-05-19T20:00:00Z"
PARTICIPANT_ADDRESS = "participant.behavior.red-agent"
ACTION_ADDRESS = "participant.action-contract.scan"
OBSERVATION_ADDRESS = "participant.observation-boundary.red-view"
ACTION_INSTANCE = "scan-0001"


def _scenario_yaml() -> str:
    return textwrap.dedent(
        """
        name: sem-211
        nodes:
          web:
            type: VM
            resources: {ram: 1 GiB, cpu: 1}
            services: [{port: 80, name: http}]
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
            preconditions:
              - precondition-id: authority-in-scope
                precondition-class: authority
                description: red participant is authorized to scan the web service
                support-refs: [agents.red-agent, nodes.web.services.http]
              - precondition-id: target-service-present
                precondition-class: target
                description: target service exists in the participant action scope
                support-refs: [nodes.web.services.http]
              - precondition-id: backend-can-realize-scan
                precondition-class: realization
                description: backend can realize the scan action contract
                support-refs: [backend.participant-runtime]
            effects:
              - effect-id: discover-http-service
                effect-class: intended_effect
                description: participant may discover the web HTTP service
                target-refs: [nodes.web.services.http]
              - effect-id: scan-shared-knowledge-update
                effect-class: side_effect
                description: participant-local service knowledge is updated
                target-refs: [nodes.web.services.http]
              - effect-id: terminal-scan-observation
                effect-class: observation_effect
                description: terminal scan observation is emitted for the participant
                evidence-refs: [evidence.scan-output]
              - effect-id: participant-view-discovers-service
                effect-class: visibility_effect
                description: participant view marks the web node discovered
                target-refs: [nodes.web]
              - effect-id: scan-evidence
                effect-class: evidence_effect
                description: scan tool output is retained as run evidence
                evidence-refs: [evidence.scan-output]
              - effect-id: no-hidden-truth-change
                effect-class: no_effect
                description: scan does not expose hidden adjudication material
            state-transition-effects: [participant knowledge expands]
            failure-classes:
              - precondition_unsatisfied
              - unsupported_action
              - target_unavailable
              - timeout
              - backend_error
              - unknown
            backend-failure-mappings:
              - backend-error-code: backend.timeout
                failure-class: timeout
                diagnostic: backend reported action timeout
              - backend-error-code: backend.not-supported
                failure-class: unsupported_action
                diagnostic: backend lacks the scan action implementation
            interactions:
              - interaction-class: shared_state_change
                target: nodes.web.services.http
                rationale: scan reads and updates participant-visible service knowledge
                shared-state-refs: [nodes.web.services.http]
        observation-boundaries:
          red-view:
            projection-basis: participant-local projection over observed services
            observable-refs: []
            hidden-refs: [nodes.web]
            evidence-refs: [evidence.scan-output]
            redaction-policy: hidden refs never project without explicit disclosure
            latency-profile: terminal observation emitted after state transition commit
            view-rules:
              - information-ref: nodes.web
                boundary-class: observable_resource
                disposition: hidden
                visibility-basis: service is not known before terminal scan output
              - information-ref: evidence.scan-output
                boundary-class: archival_evidence
                disposition: evidence_only
                visibility-basis: archival run evidence reference
                evidence-refs: [evidence.scan-output]
            view-transitions:
              - transition-id: discover-web-service
                transition-kind: discovery
                information-ref: nodes.web
                trigger: scan terminal observation
                effective-from: episode-step:scan-0001:terminal-observation
                effective-order: 30
                history-event-type: observation_emitted
                action-instance-id: scan-0001
                from-disposition: hidden
                to-disposition: discovered
                evidence-refs: [evidence.scan-output]
                certainty: high
                latency-profile: terminal observation latency
        agents:
          red-agent:
            entity: red-team
            actions: [scan]
            observation-boundaries: [red-view]
        """
    )


def _satisfied_preconditions(
    *,
    participant_address: str = PARTICIPANT_ADDRESS,
) -> tuple[ParticipantActionPreconditionResult, ...]:
    return (
        ParticipantActionPreconditionResult(
            precondition_id="authority-in-scope",
            precondition_class=ParticipantPreconditionClass.AUTHORITY,
            status=ParticipantActionPreconditionStatus.SATISFIED,
            participant_address=participant_address,
            episode_id="episode-1",
            action_contract_address=ACTION_ADDRESS,
            observation_point="episode-step:scan-0001:attempt",
            support_refs=("agents.red-agent",),
        ),
        ParticipantActionPreconditionResult(
            precondition_id="target-service-present",
            precondition_class=ParticipantPreconditionClass.TARGET,
            status=ParticipantActionPreconditionStatus.SATISFIED,
            participant_address=participant_address,
            episode_id="episode-1",
            action_contract_address=ACTION_ADDRESS,
            observation_point="episode-step:scan-0001:attempt",
            support_refs=("nodes.web.services.http",),
        ),
    )


def _declared_effects() -> tuple[ParticipantActionEffectResult, ...]:
    return (
        ParticipantActionEffectResult(
            effect_id="discover-http-service",
            effect_class=ParticipantEffectClass.INTENDED_EFFECT,
            description="participant discovered the web HTTP service",
            target_refs=("nodes.web.services.http",),
        ),
        ParticipantActionEffectResult(
            effect_id="terminal-scan-observation",
            effect_class=ParticipantEffectClass.OBSERVATION_EFFECT,
            description="terminal scan observation emitted",
            evidence_refs=("evidence.scan-output",),
        ),
    )


def test_action_contract_declares_sem_211_classes_and_compiles_them():
    scenario = parse_sdl(_scenario_yaml())

    contract = scenario.action_contracts["scan"]
    assert [item.precondition_class.value for item in contract.preconditions] == [
        "authority",
        "target",
        "realization",
    ]
    assert [item.effect_class.value for item in contract.effects] == [
        "intended_effect",
        "side_effect",
        "observation_effect",
        "visibility_effect",
        "evidence_effect",
        "no_effect",
    ]
    assert [item.value for item in contract.failure_classes] == [
        "precondition_unsatisfied",
        "unsupported_action",
        "target_unavailable",
        "timeout",
        "backend_error",
        "unknown",
    ]

    model = compile_runtime_model(scenario)
    compiled = model.action_contracts[ACTION_ADDRESS]
    assert compiled.precondition_classes == ("authority", "target", "realization")
    assert compiled.effect_classes == (
        "intended_effect",
        "side_effect",
        "observation_effect",
        "visibility_effect",
        "evidence_effect",
        "no_effect",
    )
    assert compiled.failure_classes == (
        "precondition_unsatisfied",
        "unsupported_action",
        "target_unavailable",
        "timeout",
        "backend_error",
        "unknown",
    )
    assert compiled.backend_failure_mappings == (
        {
            "backend_error_code": "backend.timeout",
            "failure_class": "timeout",
            "diagnostic": "backend reported action timeout",
        },
        {
            "backend_error_code": "backend.not-supported",
            "failure_class": "unsupported_action",
            "diagnostic": "backend lacks the scan action implementation",
        },
    )


def test_legacy_string_preconditions_are_not_sem_211_contracts():
    scenario = _scenario_yaml().replace("precondition-class: authority", "precondition-class: legacy_string")

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "preconditions" in str(excinfo.value)


def test_action_result_rejects_success_when_preconditions_are_unresolved():
    unresolved = ParticipantActionPreconditionResult(
        precondition_id="backend-can-realize-scan",
        precondition_class=ParticipantPreconditionClass.REALIZATION,
        status=ParticipantActionPreconditionStatus.UNRESOLVED,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_contract_address=ACTION_ADDRESS,
        observation_point="episode-step:scan-0001:attempt",
        diagnostics=("backend runtime did not declare realization support",),
    )

    with pytest.raises(ValueError, match="unsatisfied or unresolved preconditions fail closed"):
        ParticipantActionResult(
            status=ParticipantActionResultStatus.SUCCEEDED,
            participant_address=PARTICIPANT_ADDRESS,
            episode_id="episode-1",
            action_instance_id=ACTION_INSTANCE,
            action_contract_address=ACTION_ADDRESS,
            observation_point="episode-step:scan-0001:terminal-observation",
            preconditions=(unresolved,),
            effects=_declared_effects(),
        )


def test_successful_action_result_requires_declared_effects():
    with pytest.raises(ValueError, match="succeeded action results require declared effects"):
        ParticipantActionResult(
            status=ParticipantActionResultStatus.SUCCEEDED,
            participant_address=PARTICIPANT_ADDRESS,
            episode_id="episode-1",
            action_instance_id=ACTION_INSTANCE,
            action_contract_address=ACTION_ADDRESS,
            observation_point="episode-step:scan-0001:terminal-observation",
            preconditions=_satisfied_preconditions(),
            effects=(),
        )


def test_side_effect_results_require_target_or_evidence_refs():
    with pytest.raises(ValueError, match="side_effect effects require target_refs or evidence_refs"):
        ParticipantActionEffectResult(
            effect_id="scan-shared-knowledge-update",
            effect_class=ParticipantEffectClass.SIDE_EFFECT,
            description="participant-local service knowledge is updated",
        )


def test_rejected_action_result_round_trips_with_portable_failure_class():
    unresolved = ParticipantActionPreconditionResult(
        precondition_id="backend-can-realize-scan",
        precondition_class=ParticipantPreconditionClass.REALIZATION,
        status=ParticipantActionPreconditionStatus.UNRESOLVED,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_contract_address=ACTION_ADDRESS,
        observation_point="episode-step:scan-0001:attempt",
        diagnostics=("backend runtime did not declare realization support",),
    )
    result = ParticipantActionResult(
        status=ParticipantActionResultStatus.REJECTED,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        observation_point="episode-step:scan-0001:attempt",
        preconditions=(unresolved,),
        effects=(),
        failure_class=ParticipantFailureClass.PRECONDITION_UNSATISFIED,
        diagnostics=("action withheld because realization support is unresolved",),
    )

    assert ParticipantActionResult.from_payload(result.to_payload()) == result


def test_terminal_observation_action_result_must_match_behavior_event_scope():
    result = ParticipantActionResult(
        status=ParticipantActionResultStatus.SUCCEEDED,
        participant_address="participant.behavior.blue-agent",
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        observation_point="episode-step:scan-0001:terminal-observation",
        preconditions=_satisfied_preconditions(participant_address="participant.behavior.blue-agent"),
        effects=_declared_effects(),
        evidence_refs=("evidence.scan-output",),
    )

    with pytest.raises(ValueError, match="action_result participant_address must match event participant_address"):
        ParticipantBehaviorHistoryEvent(
            event_type=ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED,
            timestamp=T0,
            participant_address=PARTICIPANT_ADDRESS,
            episode_id="episode-1",
            action_instance_id=ACTION_INSTANCE,
            action_contract_address=ACTION_ADDRESS,
            observation_boundary_address=OBSERVATION_ADDRESS,
            observation_status=ParticipantObservationStatus.TERMINAL,
            post_state_digest="sha256:scan",
            action_result=result,
        )


def test_terminal_observation_requires_sem_211_action_result_when_contract_available():
    model = compile_runtime_model(parse_sdl(_scenario_yaml()))
    events = [
        {
            "event_type": "action_attempted",
            "timestamp": T0,
            "participant_address": PARTICIPANT_ADDRESS,
            "episode_id": "episode-1",
            "action_instance_id": ACTION_INSTANCE,
            "action_contract_address": ACTION_ADDRESS,
            "actor_provenance": "participant:red-agent",
            "details": {},
        },
        {
            "event_type": "state_transition_recorded",
            "timestamp": T0,
            "participant_address": PARTICIPANT_ADDRESS,
            "episode_id": "episode-1",
            "action_instance_id": ACTION_INSTANCE,
            "action_contract_address": ACTION_ADDRESS,
            "state_transition_kind": "participant_knowledge_expanded",
            "post_state_digest": "sha256:scan",
            "details": {},
        },
        {
            "event_type": "observation_emitted",
            "timestamp": T0,
            "participant_address": PARTICIPANT_ADDRESS,
            "episode_id": "episode-1",
            "action_instance_id": ACTION_INSTANCE,
            "action_contract_address": ACTION_ADDRESS,
            "observation_boundary_address": OBSERVATION_ADDRESS,
            "observation_status": "terminal",
            "post_state_digest": "sha256:scan",
            "details": {},
        },
    ]

    violations = list(
        iter_participant_behavior_history_violations(
            events,
            action_contract_addresses=set(model.action_contracts),
            action_contracts=model.action_contracts,
            observation_boundary_addresses={OBSERVATION_ADDRESS},
        )
    )

    assert violations == [
        (
            "runtime.snapshot.participant-behavior-history[2]",
            f"terminal observation must carry SEM-211 action_result for {ACTION_ADDRESS}",
        )
    ]


def test_action_result_effects_must_be_declared_by_compiled_contract():
    model = compile_runtime_model(parse_sdl(_scenario_yaml()))
    result = ParticipantActionResult(
        status=ParticipantActionResultStatus.SUCCEEDED,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        observation_point="episode-step:scan-0001:terminal-observation",
        preconditions=_satisfied_preconditions(),
        effects=(
            *_declared_effects(),
            ParticipantActionEffectResult(
                effect_id="undeclared-detection-change",
                effect_class=ParticipantEffectClass.DETECTION_EFFECT,
                description="scan changed the backend detection surface",
                target_refs=("telemetry.ids-alerts",),
            ),
        ),
    )
    observation = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED,
        timestamp=T0,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        observation_boundary_address=OBSERVATION_ADDRESS,
        observation_status=ParticipantObservationStatus.TERMINAL,
        post_state_digest="sha256:scan",
        action_result=result,
    )

    violations = list(
        iter_participant_behavior_history_violations(
            [
                {
                    "event_type": "action_attempted",
                    "timestamp": T0,
                    "participant_address": PARTICIPANT_ADDRESS,
                    "episode_id": "episode-1",
                    "action_instance_id": ACTION_INSTANCE,
                    "action_contract_address": ACTION_ADDRESS,
                    "actor_provenance": "participant:red-agent",
                    "details": {},
                },
                {
                    "event_type": "state_transition_recorded",
                    "timestamp": T0,
                    "participant_address": PARTICIPANT_ADDRESS,
                    "episode_id": "episode-1",
                    "action_instance_id": ACTION_INSTANCE,
                    "action_contract_address": ACTION_ADDRESS,
                    "state_transition_kind": "participant_knowledge_expanded",
                    "post_state_digest": "sha256:scan",
                    "details": {},
                },
                observation.to_payload(),
            ],
            action_contract_addresses=set(model.action_contracts),
            action_contracts=model.action_contracts,
            observation_boundary_addresses={OBSERVATION_ADDRESS},
        )
    )

    assert violations == [
        (
            "runtime.snapshot.participant-behavior-history[2]",
            "action_result effect 'undeclared-detection-change' uses undeclared effect_class 'detection_effect'",
        ),
        (
            "runtime.snapshot.participant-behavior-history[2]",
            f"action_result effect 'undeclared-detection-change'/'detection_effect' is not declared by {ACTION_ADDRESS}",
        ),
    ]


def test_action_result_failure_class_must_be_declared_by_compiled_contract():
    model = compile_runtime_model(parse_sdl(_scenario_yaml()))
    unresolved = ParticipantActionPreconditionResult(
        precondition_id="backend-can-realize-scan",
        precondition_class=ParticipantPreconditionClass.REALIZATION,
        status=ParticipantActionPreconditionStatus.UNRESOLVED,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_contract_address=ACTION_ADDRESS,
        observation_point="episode-step:scan-0001:attempt",
        diagnostics=("backend runtime did not declare realization support",),
    )
    result = ParticipantActionResult(
        status=ParticipantActionResultStatus.REJECTED,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        observation_point="episode-step:scan-0001:attempt",
        preconditions=(unresolved,),
        effects=(),
        failure_class=ParticipantFailureClass.AUTHORITY_DENIED,
        diagnostics=("backend rejected action outside portable contract",),
    )
    observation = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED,
        timestamp=T0,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        observation_boundary_address=OBSERVATION_ADDRESS,
        observation_status=ParticipantObservationStatus.ORPHANED_ACTION,
        action_result=result,
    )

    violations = list(
        iter_participant_behavior_history_violations(
            [
                {
                    "event_type": "action_attempted",
                    "timestamp": T0,
                    "participant_address": PARTICIPANT_ADDRESS,
                    "episode_id": "episode-1",
                    "action_instance_id": ACTION_INSTANCE,
                    "action_contract_address": ACTION_ADDRESS,
                    "actor_provenance": "participant:red-agent",
                    "details": {},
                },
                observation.to_payload(),
            ],
            action_contract_addresses=set(model.action_contracts),
            action_contracts=model.action_contracts,
            observation_boundary_addresses={OBSERVATION_ADDRESS},
        )
    )

    assert violations == [
        (
            "runtime.snapshot.participant-behavior-history[1]",
            f"action_result failure_class 'authority_denied' is not declared by {ACTION_ADDRESS}",
        )
    ]


def test_backend_diagnostic_mapping_returns_portable_failure_class():
    model = compile_runtime_model(parse_sdl(_scenario_yaml()))
    contract = model.action_contracts[ACTION_ADDRESS]

    assert (
        map_backend_diagnostic_to_participant_failure(
            Diagnostic(
                code="backend.timeout",
                domain="participant",
                address=ACTION_ADDRESS,
                message="operation timed out",
            ),
            contract,
        )
        == ParticipantFailureClass.TIMEOUT
    )
    assert (
        map_backend_diagnostic_to_participant_failure(
            Diagnostic(
                code="backend.unmapped",
                domain="participant",
                address=ACTION_ADDRESS,
                message="backend reported an unmapped failure",
            ),
            contract,
        )
        == ParticipantFailureClass.BACKEND_ERROR
    )
