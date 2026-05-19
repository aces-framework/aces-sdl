"""SEM-208/209/210 participant behavior, interaction, and visibility tests."""

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
from aces_sdl._errors import SDLParseError, SDLValidationError
from aces_sdl.parser import parse_sdl
from aces_sdl.participant_behavior import ParticipantInteractionClass

T0 = "2026-05-18T18:30:00Z"
T1 = "2026-05-18T18:30:05Z"
T2 = "2026-05-18T18:30:10Z"
PARTICIPANT_ADDRESS = "participant.behavior.red-agent"
ACTION_ADDRESS = "participant.action-contract.scan"
OBSERVATION_ADDRESS = "participant.observation-boundary.red-view"
ACTION_INSTANCE = "scan-0001"
POST_STATE_DIGEST = "sha256:fb2f5a36c0d7d2a0"


def _complete_behavior_history_payloads(
    action_instance_id: str,
    *,
    realized_order: int | None = None,
    participant_address: str = PARTICIPANT_ADDRESS,
) -> list[dict[str, object]]:
    action_kwargs = {}
    if realized_order is not None:
        action_kwargs = {
            "joint_action_set_id": "joint-0001",
            "realized_order": realized_order,
            "interaction_class": ParticipantInteractionClass.SHARED_STATE_CHANGE,
            "shared_state_refs": ("nodes.web.services.http",),
        }
    action = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED,
        timestamp=T0,
        participant_address=participant_address,
        episode_id="episode-1",
        action_instance_id=action_instance_id,
        action_contract_address=ACTION_ADDRESS,
        actor_provenance=f"participant:{participant_address.rsplit('.', 1)[-1]}",
        **action_kwargs,
    )
    transition = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.STATE_TRANSITION_RECORDED,
        timestamp=T1,
        participant_address=participant_address,
        episode_id="episode-1",
        action_instance_id=action_instance_id,
        action_contract_address=ACTION_ADDRESS,
        state_transition_kind="participant_knowledge_expanded",
        post_state_digest=POST_STATE_DIGEST,
    )
    observation = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED,
        timestamp=T2,
        participant_address=participant_address,
        episode_id="episode-1",
        action_instance_id=action_instance_id,
        action_contract_address=ACTION_ADDRESS,
        observation_boundary_address=OBSERVATION_ADDRESS,
        observation_status=ParticipantObservationStatus.TERMINAL,
        post_state_digest=POST_STATE_DIGEST,
    )
    return [action.to_payload(), transition.to_payload(), observation.to_payload()]


def _scenario_yaml(*, actions: str = "[scan]", boundaries: str = "[red-view]") -> str:
    return textwrap.dedent(
        f"""
        name: sem-208
        nodes:
          web:
            type: VM
            resources: {{ram: 1 GiB, cpu: 1}}
            services: [{{port: 80, name: http}}]
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
            interactions:
              - interaction-class: shared_state_change
                target: nodes.web.services.http
                rationale: scan reads and updates participant-visible service knowledge
                shared-state-refs: [nodes.web.services.http]
            external-mappings:
              - system: attack
                identifier: T1046
                loss-label: technique-to-contract
                rationale: ATT&CK does not encode ACES observation or state-transition semantics
        observation-boundaries:
          red-view:
            projection-basis: participant-local projection over observed services
            observable-refs: []
            hidden-refs: [nodes.web, content.private-answer-key]
            evidence-refs: [evidence.scan-output]
            redaction-policy: hidden refs never project without explicit disclosure
            latency-profile: terminal observation emitted after state transition commit
            observer-effects: [tool execution may affect telemetry]
            realized-view-disclosure: backend reports terminal scan output only
            view-rules:
              - information-ref: nodes.web
                boundary-class: observable_resource
                disposition: hidden
                visibility-basis: service is not known before terminal scan output
                latency-profile: terminal observation latency
              - information-ref: content.private-answer-key
                boundary-class: private_answer_key
                disposition: hidden
                visibility-basis: adjudication-only hidden truth
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
            actions: {actions}
            observation-boundaries: {boundaries}
        """
    )


def test_participant_behavior_contracts_parse_and_validate():
    scenario = parse_sdl(_scenario_yaml())

    assert scenario.action_contracts["scan"].semantic_version == "1.0.0"
    assert scenario.action_contracts["scan"].lifecycle_state.value == "active"
    assert scenario.action_contracts["scan"].interactions[0].interaction_class.value == "shared_state_change"
    assert scenario.observation_boundaries["red-view"].projection_basis.startswith("participant-local")
    assert scenario.observation_boundaries["red-view"].view_rules[1].disposition.value == "hidden"
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


def test_participant_interactions_must_resolve_related_action_contracts():
    scenario = _scenario_yaml().replace(
        "        shared-state-refs: [nodes.web.services.http]",
        ("        related-actions: [coordinate]\n        shared-state-refs: [nodes.web.services.http]"),
    )

    with pytest.raises(SDLValidationError) as excinfo:
        parse_sdl(scenario)

    assert (
        "Action contract 'scan' interaction related_action 'coordinate' does not reference a declared action_contract"
    ) in str(excinfo.value)


def test_participant_interactions_must_resolve_targets():
    scenario = _scenario_yaml().replace(
        "target: nodes.web.services.http",
        "target: nodes.missing.services.http",
    )

    with pytest.raises(SDLValidationError) as excinfo:
        parse_sdl(scenario)

    assert (
        "Action contract 'scan' interaction[0] target 'nodes.missing.services.http' "
        "does not reference any defined targetable element"
    ) in str(excinfo.value)


def test_participant_interactions_must_resolve_shared_state_refs():
    scenario = _scenario_yaml().replace(
        "shared-state-refs: [nodes.web.services.http]",
        "shared-state-refs: [nodes.missing.services.http]",
    )

    with pytest.raises(SDLValidationError) as excinfo:
        parse_sdl(scenario)

    assert (
        "Action contract 'scan' interaction[0] shared_state_ref 'nodes.missing.services.http' "
        "does not reference any defined targetable element"
    ) in str(excinfo.value)


def test_compiler_maps_participant_behavior_to_runtime_addresses():
    model = compile_runtime_model(parse_sdl(_scenario_yaml()))

    assert set(model.action_contracts) == {ACTION_ADDRESS}
    assert set(model.observation_boundaries) == {OBSERVATION_ADDRESS}
    contract = model.action_contracts[ACTION_ADDRESS]
    assert contract.interaction_classes == ("shared_state_change",)
    assert contract.shared_state_refs == ("nodes.web.services.http",)
    boundary = model.observation_boundaries[OBSERVATION_ADDRESS]
    assert boundary.hidden_refs == ("nodes.web", "content.private-answer-key")
    assert boundary.observable_refs == ()
    assert boundary.evidence_only_refs == ("evidence.scan-output",)
    assert boundary.discovered_refs == ()
    assert boundary.view_transitions[0]["transition_id"] == "discover-web-service"
    assert boundary.view_transitions[0]["effective_from"] == "episode-step:scan-0001:terminal-observation"
    assert boundary.view_transitions[0]["effective_order"] == 30
    assert boundary.view_transitions[0]["history_event_type"] == "observation_emitted"
    assert boundary.view_relation_timeline[0]["view_relation"]["nodes.web"] == "hidden"
    assert "nodes.web" not in boundary.view_relation_timeline[0]["visible_refs"]
    assert boundary.view_relation_timeline[1]["view_relation"]["nodes.web"] == "discovered"
    assert "nodes.web" in boundary.view_relation_timeline[1]["visible_refs"]
    assert boundary.realized_view_disclosure == "backend reports terminal scan output only"

    binding = model.participant_behaviors[PARTICIPANT_ADDRESS]
    assert binding.participant_name == "red-agent"
    assert binding.entity_name == "red-team"
    assert binding.action_contract_addresses == (ACTION_ADDRESS,)
    assert binding.observation_boundary_addresses == (OBSERVATION_ADDRESS,)
    assert binding.interpretation_mode == "role-neutral-projection"
    assert binding.spec["interpretation_mode"] == "role-neutral-projection"


def test_view_relation_timeline_tracks_inference_and_concealment_transitions():
    scenario = (
        _scenario_yaml()
        .replace(
            "hidden-refs: [nodes.web, content.private-answer-key]",
            "hidden-refs: [nodes.web, content.private-answer-key, nodes.web.services.http]",
        )
        .replace(
            "      - information-ref: evidence.scan-output\n"
            "        boundary-class: archival_evidence\n"
            "        disposition: evidence_only\n"
            "        visibility-basis: archival run evidence reference\n"
            "        evidence-refs: [evidence.scan-output]",
            "      - information-ref: nodes.web.services.http\n"
            "        boundary-class: observable_resource\n"
            "        disposition: hidden\n"
            "        visibility-basis: service is not known before scan output inference\n"
            "      - information-ref: evidence.scan-output\n"
            "        boundary-class: archival_evidence\n"
            "        disposition: evidence_only\n"
            "        visibility-basis: archival run evidence reference\n"
            "        evidence-refs: [evidence.scan-output]",
        )
        .replace(
            "        evidence-refs: [evidence.scan-output]\n"
            "        certainty: high\n"
            "        latency-profile: terminal observation latency",
            "        evidence-refs: [evidence.scan-output]\n"
            "        certainty: high\n"
            "        latency-profile: terminal observation latency\n"
            "      - transition-id: infer-http-service\n"
            "        transition-kind: inference\n"
            "        information-ref: nodes.web.services.http\n"
            "        trigger: interpret scan output\n"
            "        effective-from: episode-step:scan-0001:analysis\n"
            "        effective-order: 40\n"
            "        history-event-type: observation_emitted\n"
            "        action-instance-id: scan-0001\n"
            "        from-disposition: hidden\n"
            "        to-disposition: inferred\n"
            "        evidence-refs: [evidence.scan-output]\n"
            "        certainty: medium\n"
            "        latency-profile: participant analysis latency\n"
            "      - transition-id: conceal-http-service\n"
            "        transition-kind: concealment\n"
            "        information-ref: nodes.web.services.http\n"
            "        trigger: redacted follow-up observation\n"
            "        effective-from: episode-step:scan-0001:redacted-observation\n"
            "        effective-order: 50\n"
            "        history-event-type: observation_emitted\n"
            "        action-instance-id: scan-0001\n"
            "        from-disposition: inferred\n"
            "        to-disposition: concealed\n"
            "        evidence-refs: [evidence.scan-output]\n"
            "        certainty: medium\n"
            "        latency-profile: redaction latency",
        )
    )

    model = compile_runtime_model(parse_sdl(scenario))

    boundary = model.observation_boundaries[OBSERVATION_ADDRESS]
    assert boundary.inferred_refs == ()
    assert boundary.concealed_refs == ()
    assert boundary.view_relation_timeline[2]["transition_id"] == "infer-http-service"
    assert boundary.view_relation_timeline[2]["view_relation"]["nodes.web.services.http"] == "inferred"
    assert boundary.view_relation_timeline[3]["transition_id"] == "conceal-http-service"
    assert boundary.view_relation_timeline[3]["view_relation"]["nodes.web.services.http"] == "concealed"


def test_hidden_truth_cannot_be_observed_without_explicit_disclosure_rule():
    scenario = _scenario_yaml().replace(
        "observable-refs: []",
        "observable-refs: [content.private-answer-key]",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert (
        "hidden_refs must not also be observable_refs; use a disclosed view_rule instead: content.private-answer-key"
    ) in str(excinfo.value)


def test_evidence_only_refs_cannot_be_boundary_observable_refs():
    scenario = _scenario_yaml().replace(
        "observable-refs: []",
        "observable-refs: [evidence.scan-output]",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert (
        "evidence_only refs must not also be observable_refs; use evidence_refs instead: evidence.scan-output"
        in str(excinfo.value)
    )


def test_hidden_truth_disclosure_is_separate_from_observable_projection():
    scenario = _scenario_yaml().replace(
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency",
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency\n"
        "      - transition-id: disclose-answer-key\n"
        "        transition-kind: disclosure\n"
        "        information-ref: content.private-answer-key\n"
        "        trigger: episode close adjudication\n"
        "        effective-from: episode-close\n"
        "        effective-order: 100\n"
        "        history-event-type: episode_close\n"
        "        from-disposition: hidden\n"
        "        to-disposition: disclosed\n"
        "        disclosure-rule: reveal answer key after episode close\n"
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: post-run adjudication latency\n"
        "        realized-backend-disclosure: emitted only in post-run adjudication view",
    )

    model = compile_runtime_model(parse_sdl(scenario))

    boundary = model.observation_boundaries[OBSERVATION_ADDRESS]
    assert "content.private-answer-key" not in boundary.observable_refs
    assert boundary.disclosed_refs == ()
    assert boundary.view_transitions[1]["transition_kind"] == "disclosure"
    assert boundary.view_relation_timeline[2]["view_relation"]["content.private-answer-key"] == "disclosed"
    assert "content.private-answer-key" in boundary.view_relation_timeline[2]["disclosed_refs"]


def test_hidden_truth_disclosure_does_not_make_observable_refs_safe():
    scenario = _scenario_yaml()
    scenario = scenario.replace(
        "observable-refs: []",
        "observable-refs: [content.private-answer-key]",
    ).replace(
        "      - information-ref: content.private-answer-key\n"
        "        boundary-class: private_answer_key\n"
        "        disposition: hidden\n"
        "        visibility-basis: adjudication-only hidden truth",
        "      - information-ref: content.private-answer-key\n"
        "        boundary-class: private_answer_key\n"
        "        disposition: disclosed\n"
        "        visibility-basis: explicit evaluator disclosure\n"
        "        disclosure-rule: reveal answer key after episode close",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "hidden_refs must not also be observable_refs" in str(excinfo.value)


def test_private_answer_key_view_rule_requires_disclosure_rule_when_exposed():
    scenario = _scenario_yaml().replace(
        "      - information-ref: content.private-answer-key\n"
        "        boundary-class: private_answer_key\n"
        "        disposition: hidden\n"
        "        visibility-basis: adjudication-only hidden truth",
        "      - information-ref: content.private-answer-key\n"
        "        boundary-class: private_answer_key\n"
        "        disposition: disclosed\n"
        "        visibility-basis: explicit evaluator disclosure",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "disclosed view rules require an explicit disclosure_rule" in str(excinfo.value)


def test_disclosure_transition_requires_disclosure_rule():
    scenario = _scenario_yaml().replace(
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency",
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency\n"
        "      - transition-id: disclose-answer-key\n"
        "        transition-kind: disclosure\n"
        "        information-ref: content.private-answer-key\n"
        "        trigger: episode close adjudication\n"
        "        effective-from: episode-close\n"
        "        effective-order: 100\n"
        "        history-event-type: episode_close\n"
        "        from-disposition: hidden\n"
        "        to-disposition: disclosed\n"
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: post-run adjudication latency",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "disclosure transitions require disclosure_rule" in str(excinfo.value)


def test_transition_from_disposition_must_match_initial_view_rule():
    scenario = _scenario_yaml().replace(
        "      - information-ref: nodes.web\n"
        "        boundary-class: observable_resource\n"
        "        disposition: hidden\n"
        "        visibility-basis: service is not known before terminal scan output",
        "      - information-ref: nodes.web\n"
        "        boundary-class: observable_resource\n"
        "        disposition: observable\n"
        "        visibility-basis: incorrectly declared initially visible",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert (
        "view_transition 'discover-web-service' from_disposition does not match current disposition for nodes.web"
        in str(excinfo.value)
    )


def test_sensitive_view_rule_cannot_be_directly_observable():
    scenario = _scenario_yaml().replace(
        "      - information-ref: content.private-answer-key\n"
        "        boundary-class: private_answer_key\n"
        "        disposition: hidden\n"
        "        visibility-basis: adjudication-only hidden truth",
        "      - information-ref: content.private-answer-key\n"
        "        boundary-class: private_answer_key\n"
        "        disposition: observable\n"
        "        visibility-basis: adjudication-only hidden truth",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "private_answer_key must use disposition disclosed, not observable" in str(excinfo.value)


def test_hidden_truth_view_rule_cannot_be_directly_observable():
    scenario = (
        _scenario_yaml()
        .replace(
            "        boundary-class: private_answer_key",
            "        boundary-class: hidden_truth",
        )
        .replace(
            "        disposition: hidden",
            "        disposition: observable",
        )
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "hidden_truth must use disposition disclosed, not observable" in str(excinfo.value)


def test_sensitive_inference_transition_requires_disclosure_rule():
    scenario = _scenario_yaml().replace(
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency",
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency\n"
        "      - transition-id: infer-answer-key\n"
        "        transition-kind: inference\n"
        "        information-ref: content.private-answer-key\n"
        "        trigger: leaked benchmark clue\n"
        "        effective-from: episode-step:scan-0001:leak\n"
        "        effective-order: 40\n"
        "        history-event-type: observation_emitted\n"
        "        action-instance-id: scan-0001\n"
        "        from-disposition: hidden\n"
        "        to-disposition: inferred\n"
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: low\n"
        "        latency-profile: terminal observation latency",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "inference transitions exposing private_answer_key require disclosure_rule" in str(excinfo.value)


def test_hidden_truth_evidence_reference_requires_evidence_only_rule():
    scenario = _scenario_yaml().replace(
        "evidence-refs: [evidence.scan-output]",
        "evidence-refs: [evidence.scan-output, content.private-answer-key]",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert (
        "hidden_refs may only appear in evidence_refs through evidence_only view_rules: content.private-answer-key"
    ) in str(excinfo.value)


def test_view_rule_information_ref_must_be_declared_by_boundary_refs():
    scenario = _scenario_yaml().replace(
        "information-ref: nodes.web",
        "information-ref: nodes.db",
    )

    with pytest.raises(SDLValidationError) as excinfo:
        parse_sdl(scenario)

    assert (
        "Observation boundary 'red-view' view_rule information_ref 'nodes.db' "
        "is not declared by observable_refs, hidden_refs, or evidence_refs"
    ) in str(excinfo.value)
    assert (
        "Observation boundary 'red-view' view_transition 'discover-web-service' "
        "information_ref 'nodes.db' is not declared by observable_refs, hidden_refs, or evidence_refs"
    ) in str(excinfo.value)


def test_view_rule_evidence_ref_must_be_declared_by_boundary_evidence_refs():
    scenario = _scenario_yaml().replace(
        "      - information-ref: evidence.scan-output\n"
        "        boundary-class: archival_evidence\n"
        "        disposition: evidence_only\n"
        "        visibility-basis: archival run evidence reference\n"
        "        evidence-refs: [evidence.scan-output]",
        "      - information-ref: evidence.scan-output\n"
        "        boundary-class: archival_evidence\n"
        "        disposition: evidence_only\n"
        "        visibility-basis: archival run evidence reference\n"
        "        evidence-refs: [evidence.missing]",
    )

    with pytest.raises(SDLValidationError) as excinfo:
        parse_sdl(scenario)

    assert (
        "Observation boundary 'red-view' view_rule evidence_ref 'evidence.missing' is not declared by evidence_refs"
    ) in str(excinfo.value)


def test_view_transition_evidence_ref_must_be_declared_by_boundary_evidence_refs():
    scenario = _scenario_yaml().replace(
        "        evidence-refs: [evidence.scan-output]\n        certainty: high",
        "        evidence-refs: [evidence.missing]\n        certainty: high",
    )

    with pytest.raises(SDLValidationError) as excinfo:
        parse_sdl(scenario)

    assert (
        "Observation boundary 'red-view' view_transition 'discover-web-service' "
        "evidence_ref 'evidence.missing' is not declared by evidence_refs"
    ) in str(excinfo.value)


def test_view_transition_to_disposition_must_match_transition_kind():
    scenario = _scenario_yaml().replace(
        "        to-disposition: discovered",
        "        to-disposition: inferred",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "discovery transitions require to_disposition in: discovered" in str(excinfo.value)


def test_view_transition_requires_matching_view_rule():
    scenario = (
        _scenario_yaml()
        .replace(
            "hidden-refs: [nodes.web, content.private-answer-key]",
            "hidden-refs: [nodes.web, content.private-answer-key, nodes.web.services.http]",
        )
        .replace(
            "        evidence-refs: [evidence.scan-output]\n"
            "        certainty: high\n"
            "        latency-profile: terminal observation latency",
            "        evidence-refs: [evidence.scan-output]\n"
            "        certainty: high\n"
            "        latency-profile: terminal observation latency\n"
            "      - transition-id: infer-http-service\n"
            "        transition-kind: inference\n"
            "        information-ref: nodes.web.services.http\n"
            "        trigger: interpret scan output\n"
            "        effective-from: episode-step:scan-0001:analysis\n"
            "        effective-order: 40\n"
            "        history-event-type: observation_emitted\n"
            "        action-instance-id: scan-0001\n"
            "        from-disposition: hidden\n"
            "        to-disposition: inferred\n"
            "        evidence-refs: [evidence.scan-output]\n"
            "        certainty: medium\n"
            "        latency-profile: participant analysis latency",
        )
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "view_transitions require matching view_rules: infer-http-service" in str(excinfo.value)


def test_view_rules_require_unique_information_refs():
    scenario = _scenario_yaml().replace(
        "      - information-ref: evidence.scan-output\n"
        "        boundary-class: archival_evidence\n"
        "        disposition: evidence_only\n"
        "        visibility-basis: archival run evidence reference\n"
        "        evidence-refs: [evidence.scan-output]",
        "      - information-ref: nodes.web\n"
        "        boundary-class: archival_evidence\n"
        "        disposition: evidence_only\n"
        "        visibility-basis: archival run evidence reference\n"
        "        evidence-refs: [evidence.scan-output]",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "view_rules require unique information_ref values: nodes.web" in str(excinfo.value)


def test_view_transitions_require_unique_transition_ids():
    scenario = _scenario_yaml().replace(
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency",
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency\n"
        "      - transition-id: discover-web-service\n"
        "        transition-kind: discovery\n"
        "        information-ref: nodes.web\n"
        "        trigger: duplicate scan terminal observation\n"
        "        effective-from: episode-step:scan-0001:duplicate-terminal-observation\n"
        "        effective-order: 31\n"
        "        history-event-type: observation_emitted\n"
        "        action-instance-id: scan-0001\n"
        "        from-disposition: hidden\n"
        "        to-disposition: discovered\n"
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "view_transitions require unique transition_id values: discover-web-service" in str(excinfo.value)


def test_view_transition_from_and_to_dispositions_must_differ():
    scenario = _scenario_yaml().replace(
        "        from-disposition: hidden\n        to-disposition: discovered",
        "        from-disposition: discovered\n        to-disposition: discovered",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "participant view transitions must alter disposition" in str(excinfo.value)


def test_view_transition_from_disposition_must_match_current_relation():
    scenario = _scenario_yaml().replace(
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency",
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency\n"
        "      - transition-id: conceal-web-service\n"
        "        transition-kind: concealment\n"
        "        information-ref: nodes.web\n"
        "        trigger: redacted scan follow-up\n"
        "        effective-from: episode-step:scan-0001:redacted-observation\n"
        "        effective-order: 40\n"
        "        history-event-type: observation_emitted\n"
        "        action-instance-id: scan-0001\n"
        "        from-disposition: hidden\n"
        "        to-disposition: concealed\n"
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: medium\n"
        "        latency-profile: redaction latency",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert (
        "view_transition 'conceal-web-service' from_disposition does not match current disposition for nodes.web"
        in str(excinfo.value)
    )


def test_view_transition_effective_order_drives_timeline_not_declaration_order():
    scenario = _scenario_yaml().replace(
        "      - transition-id: discover-web-service\n",
        "      - transition-id: infer-web-service\n"
        "        transition-kind: inference\n"
        "        information-ref: nodes.web\n"
        "        trigger: participant interprets terminal scan observation\n"
        "        effective-from: episode-step:scan-0001:analysis\n"
        "        effective-order: 40\n"
        "        history-event-type: observation_emitted\n"
        "        action-instance-id: scan-0001\n"
        "        from-disposition: discovered\n"
        "        to-disposition: inferred\n"
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: medium\n"
        "        latency-profile: participant analysis latency\n"
        "      - transition-id: discover-web-service\n",
    )

    model = compile_runtime_model(parse_sdl(scenario))

    boundary = model.observation_boundaries[OBSERVATION_ADDRESS]
    assert [transition["transition_id"] for transition in boundary.view_transitions] == [
        "discover-web-service",
        "infer-web-service",
    ]
    assert [snapshot["transition_id"] for snapshot in boundary.view_relation_timeline] == [
        "initial",
        "discover-web-service",
        "infer-web-service",
    ]


def test_view_transitions_require_unique_effective_order_values():
    scenario = _scenario_yaml().replace(
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency",
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency\n"
        "      - transition-id: duplicate-effective-order\n"
        "        transition-kind: discovery\n"
        "        information-ref: nodes.web\n"
        "        trigger: duplicate scan terminal observation\n"
        "        effective-from: episode-step:scan-0001:duplicate-terminal-observation\n"
        "        effective-order: 30\n"
        "        history-event-type: observation_emitted\n"
        "        action-instance-id: scan-0001\n"
        "        from-disposition: hidden\n"
        "        to-disposition: discovered\n"
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "view_transitions require unique effective_order values: 30" in str(excinfo.value)


def test_view_transitions_require_evidence_certainty_and_latency():
    scenario = _scenario_yaml().replace(
        "        to-disposition: discovered\n"
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency",
        "        to-disposition: discovered\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency",
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "participant view transitions require evidence_refs" in str(excinfo.value)


def test_coordination_interactions_require_related_actions():
    scenario = (
        _scenario_yaml()
        .replace(
            "interaction-class: shared_state_change",
            "interaction-class: coordination",
        )
        .replace(
            "        shared-state-refs: [nodes.web.services.http]\n",
            "",
        )
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "coordination interactions require related_actions" in str(excinfo.value)


def test_contention_interactions_require_shared_state_refs():
    scenario = (
        _scenario_yaml()
        .replace(
            "interaction-class: shared_state_change",
            "interaction-class: contention",
        )
        .replace(
            "        shared-state-refs: [nodes.web.services.http]\n",
            "",
        )
    )

    with pytest.raises(SDLParseError) as excinfo:
        parse_sdl(scenario)

    assert "contention interactions require shared_state_refs" in str(excinfo.value)


def test_behavior_history_events_round_trip_with_compiled_addresses():
    event = ParticipantBehaviorHistoryEvent(
        event_type=ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED,
        timestamp=T0,
        participant_address=PARTICIPANT_ADDRESS,
        episode_id="episode-1",
        action_instance_id=ACTION_INSTANCE,
        action_contract_address=ACTION_ADDRESS,
        actor_provenance="participant:red-agent",
        joint_action_set_id="joint-0001",
        realized_order=0,
        interaction_class=ParticipantInteractionClass.SHARED_STATE_CHANGE,
        shared_state_refs=("nodes.web.services.http",),
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


def test_behavior_history_requires_realized_order_for_joint_action_sets():
    with pytest.raises(ValueError, match="joint_action_set_id requires realized_order"):
        ParticipantBehaviorHistoryEvent(
            event_type=ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED,
            timestamp=T0,
            participant_address=PARTICIPANT_ADDRESS,
            episode_id="episode-1",
            action_instance_id=ACTION_INSTANCE,
            action_contract_address=ACTION_ADDRESS,
            actor_provenance="participant:red-agent",
            joint_action_set_id="joint-0001",
        )


def test_behavior_history_requires_shared_state_refs_for_shared_state_interactions():
    with pytest.raises(ValueError, match="shared_state_change events require shared_state_refs"):
        ParticipantBehaviorHistoryEvent(
            event_type=ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED,
            timestamp=T0,
            participant_address=PARTICIPANT_ADDRESS,
            episode_id="episode-1",
            action_instance_id=ACTION_INSTANCE,
            action_contract_address=ACTION_ADDRESS,
            actor_provenance="participant:red-agent",
            joint_action_set_id="joint-0001",
            realized_order=0,
            interaction_class=ParticipantInteractionClass.SHARED_STATE_CHANGE,
        )


def test_behavior_history_payload_rejects_string_shared_state_refs():
    payload = {
        "event_type": "action_attempted",
        "timestamp": T0,
        "participant_address": PARTICIPANT_ADDRESS,
        "episode_id": "episode-1",
        "action_instance_id": ACTION_INSTANCE,
        "action_contract_address": ACTION_ADDRESS,
        "actor_provenance": "participant:red-agent",
        "joint_action_set_id": "joint-0001",
        "realized_order": 0,
        "interaction_class": "shared_state_change",
        "shared_state_refs": "nodes.web.services.http",
    }

    with pytest.raises(TypeError, match="shared_state_refs must be a list of strings"):
        ParticipantBehaviorHistoryEvent.from_payload(payload)


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


def test_behavior_history_rejects_observation_details_that_expose_hidden_truth():
    model = compile_runtime_model(parse_sdl(_scenario_yaml()))
    events = _complete_behavior_history_payloads(ACTION_INSTANCE)
    events[2]["details"] = {
        "visible_refs": ["nodes.web", "content.private-answer-key"],
        "evidence_refs": ["evidence.scan-output"],
    }

    violations = list(
        iter_participant_behavior_history_violations(
            events,
            action_contract_addresses={ACTION_ADDRESS},
            observation_boundary_addresses={OBSERVATION_ADDRESS},
            observation_boundaries=model.observation_boundaries,
        )
    )

    assert violations == [
        (
            "runtime.snapshot.participant-behavior-history[2]",
            (
                "observation visible_refs may only contain participant-visible refs at effective_order 30: "
                "'content.private-answer-key' has disposition 'hidden'"
            ),
        )
    ]


def test_behavior_history_rejects_future_episode_close_disclosure_in_observation_details():
    scenario = _scenario_yaml().replace(
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency",
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: terminal observation latency\n"
        "      - transition-id: disclose-answer-key\n"
        "        transition-kind: disclosure\n"
        "        information-ref: content.private-answer-key\n"
        "        trigger: episode close adjudication\n"
        "        effective-from: episode-close\n"
        "        effective-order: 100\n"
        "        history-event-type: episode_close\n"
        "        from-disposition: hidden\n"
        "        to-disposition: disclosed\n"
        "        disclosure-rule: reveal answer key after episode close\n"
        "        evidence-refs: [evidence.scan-output]\n"
        "        certainty: high\n"
        "        latency-profile: post-run adjudication latency",
    )
    model = compile_runtime_model(parse_sdl(scenario))
    events = _complete_behavior_history_payloads(ACTION_INSTANCE)
    events[2]["details"] = {"visible_refs": ["content.private-answer-key"]}

    violations = list(
        iter_participant_behavior_history_violations(
            events,
            action_contract_addresses={ACTION_ADDRESS},
            observation_boundary_addresses={OBSERVATION_ADDRESS},
            observation_boundaries=model.observation_boundaries,
        )
    )

    assert violations == [
        (
            "runtime.snapshot.participant-behavior-history[2]",
            (
                "observation visible_refs may only contain participant-visible refs at effective_order 30: "
                "'content.private-answer-key' has disposition 'hidden'"
            ),
        )
    ]


def test_behavior_history_rejects_nested_observation_details_payload_side_channel():
    model = compile_runtime_model(parse_sdl(_scenario_yaml()))
    events = _complete_behavior_history_payloads(ACTION_INSTANCE)
    events[2]["details"] = {"payload": {"visible_refs": ["content.private-answer-key"]}}

    violations = list(
        iter_participant_behavior_history_violations(
            events,
            action_contract_addresses={ACTION_ADDRESS},
            observation_boundary_addresses={OBSERVATION_ADDRESS},
            observation_boundaries=model.observation_boundaries,
        )
    )

    assert violations == [
        (
            "runtime.snapshot.participant-behavior-history[2]",
            "observation details may only contain visible_refs, disclosed_refs, evidence_refs; unsupported fields: payload",
        )
    ]


def test_behavior_history_rejects_caller_supplied_observation_effective_order():
    model = compile_runtime_model(parse_sdl(_scenario_yaml()))
    events = _complete_behavior_history_payloads(ACTION_INSTANCE)
    events[2]["details"] = {
        "effective_order": 100,
        "visible_refs": ["nodes.web"],
    }

    violations = list(
        iter_participant_behavior_history_violations(
            events,
            action_contract_addresses={ACTION_ADDRESS},
            observation_boundary_addresses={OBSERVATION_ADDRESS},
            observation_boundaries=model.observation_boundaries,
        )
    )

    assert violations == [
        (
            "runtime.snapshot.participant-behavior-history[2]",
            (
                "observation details may only contain visible_refs, disclosed_refs, evidence_refs; "
                "unsupported fields: effective_order"
            ),
        )
    ]


def test_behavior_history_rejects_details_on_non_observation_events():
    events = _complete_behavior_history_payloads(ACTION_INSTANCE)
    events[0]["details"] = {"visible_refs": ["nodes.web"]}

    violations = list(
        iter_participant_behavior_history_violations(
            events,
            action_contract_addresses={ACTION_ADDRESS},
            observation_boundary_addresses={OBSERVATION_ADDRESS},
        )
    )

    assert violations == [
        (
            "runtime.snapshot.participant-behavior-history[0]",
            "participant behavior details are only allowed on observation_emitted events",
        )
    ]


def test_behavior_history_rejects_unresolved_visibility_transition_anchor():
    scenario = _scenario_yaml().replace("action-instance-id: scan-0001", "action-instance-id: scan-9999")
    model = compile_runtime_model(parse_sdl(scenario))

    violations = list(
        iter_participant_behavior_history_violations(
            _complete_behavior_history_payloads(ACTION_INSTANCE),
            action_contract_addresses={ACTION_ADDRESS},
            observation_boundary_addresses={OBSERVATION_ADDRESS},
            observation_boundaries=model.observation_boundaries,
        )
    )

    assert violations == [
        (
            "participant.observation-boundary.red-view.view_transitions.discover-web-service",
            "visibility transition anchor does not resolve to an observation_emitted event",
        )
    ]


def test_behavior_history_rejects_duplicate_realized_order_in_joint_action_set():
    events = [
        *_complete_behavior_history_payloads("scan-0001", realized_order=0),
        *_complete_behavior_history_payloads("scan-0002", realized_order=0),
    ]

    violations = list(
        iter_participant_behavior_history_violations(
            events,
            action_contract_addresses={ACTION_ADDRESS},
            observation_boundary_addresses={OBSERVATION_ADDRESS},
        )
    )

    assert violations == [
        (
            "joint-action-set.joint-0001",
            (
                "joint action set realized_order 0 is assigned to multiple action_attempted events: "
                f"{PARTICIPANT_ADDRESS}/scan-0001, {PARTICIPANT_ADDRESS}/scan-0002"
            ),
        )
    ]


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
    details_schema = event_schema["properties"]["details"]
    if "$ref" in details_schema:
        schema_defs = event_schema.get("$defs", schema.get("$defs", {}))
        details_schema = schema_defs[details_schema["$ref"].rsplit("/", 1)[-1]]

    assert event_schema["additionalProperties"] is False
    assert "ParticipantBehaviorHistoryEventModel" in event_schema["title"]
    assert details_schema["additionalProperties"] is False
    assert set(details_schema["properties"]) == {"visible_refs", "disclosed_refs", "evidence_refs"}
