"""Name-level participant behavior semantics (SEM-208/209/210)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ParticipantBehaviorReference:
    """Normalized reference from an agent to a behavior contract artifact."""

    participant_name: str
    reference_kind: str
    raw: str
    canonical_name: str


@dataclass(frozen=True)
class ParticipantBehaviorIssue:
    """Machine-readable participant behavior consistency issue."""

    code: str
    participant_name: str
    ref: str
    action_name: str = ""
    boundary_name: str = ""
    transition_id: str = ""


@dataclass(frozen=True)
class ParticipantBehaviorAnalysis:
    """Result of analyzing participant behavior references."""

    references: tuple[ParticipantBehaviorReference, ...] = ()
    issues: tuple[ParticipantBehaviorIssue, ...] = ()

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


def _action_references_for_agent(
    *,
    participant_name: str,
    action_names: list[object],
    action_contracts: Mapping[str, object],
    is_unresolved: Callable[[object], bool],
) -> tuple[list[ParticipantBehaviorReference], list[ParticipantBehaviorIssue]]:
    references: list[ParticipantBehaviorReference] = []
    issues: list[ParticipantBehaviorIssue] = []
    for action_name in action_names:
        if is_unresolved(action_name):
            continue
        if action_contracts and action_name not in action_contracts:
            issues.append(
                ParticipantBehaviorIssue(
                    code="participant.action-contract-unbound",
                    participant_name=participant_name,
                    ref=str(action_name),
                )
            )
            continue
        if action_name in action_contracts:
            references.append(
                ParticipantBehaviorReference(
                    participant_name=participant_name,
                    reference_kind="action_contract",
                    raw=str(action_name),
                    canonical_name=str(action_name),
                )
            )
    return references, issues


def _observation_boundary_references_for_agent(
    *,
    participant_name: str,
    boundary_names: list[object],
    observation_boundaries: Mapping[str, object],
    is_unresolved: Callable[[object], bool],
) -> tuple[list[ParticipantBehaviorReference], list[ParticipantBehaviorIssue]]:
    references: list[ParticipantBehaviorReference] = []
    issues: list[ParticipantBehaviorIssue] = []
    for boundary_name in boundary_names:
        if is_unresolved(boundary_name):
            continue
        if boundary_name not in observation_boundaries:
            issues.append(
                ParticipantBehaviorIssue(
                    code="participant.observation-boundary-unbound",
                    participant_name=participant_name,
                    ref=str(boundary_name),
                )
            )
            continue
        references.append(
            ParticipantBehaviorReference(
                participant_name=participant_name,
                reference_kind="observation_boundary",
                raw=str(boundary_name),
                canonical_name=str(boundary_name),
            )
        )
    return references, issues


def _interaction_references_for_action_contracts(
    *,
    action_contracts: Mapping[str, object],
    is_unresolved: Callable[[object], bool],
) -> list[ParticipantBehaviorIssue]:
    issues: list[ParticipantBehaviorIssue] = []
    for action_name, action_contract in action_contracts.items():
        for interaction in getattr(action_contract, "interactions", []) or []:
            for related_action in getattr(interaction, "related_actions", []) or []:
                if is_unresolved(related_action):
                    continue
                if related_action not in action_contracts:
                    issues.append(
                        ParticipantBehaviorIssue(
                            code="participant.interaction-action-unbound",
                            participant_name="",
                            action_name=str(action_name),
                            ref=str(related_action),
                        )
                    )
    return issues


def _observation_boundary_declared_refs(observation_boundary: object) -> set[str]:
    refs: set[str] = set()
    refs.update(str(ref) for ref in getattr(observation_boundary, "observable_refs", []) or [])
    refs.update(str(ref) for ref in getattr(observation_boundary, "hidden_refs", []) or [])
    refs.update(str(ref) for ref in getattr(observation_boundary, "evidence_refs", []) or [])
    return refs


def _observation_boundary_evidence_refs(observation_boundary: object) -> set[str]:
    return {str(ref) for ref in getattr(observation_boundary, "evidence_refs", []) or []}


def _is_bound_reference(
    ref: object,
    *,
    declared_refs: set[str],
    is_unresolved: Callable[[object], bool],
) -> bool:
    return is_unresolved(ref) or str(ref) in declared_refs


def _view_rule_visibility_issues(
    *,
    boundary_name: str,
    boundary: object,
    declared_refs: set[str],
    evidence_refs: set[str],
    is_unresolved: Callable[[object], bool],
) -> list[ParticipantBehaviorIssue]:
    issues: list[ParticipantBehaviorIssue] = []
    for rule in getattr(boundary, "view_rules", []) or []:
        information_ref = getattr(rule, "information_ref", "")
        if not _is_bound_reference(information_ref, declared_refs=declared_refs, is_unresolved=is_unresolved):
            issues.append(
                ParticipantBehaviorIssue(
                    code="participant.view-rule-ref-unbound",
                    participant_name="",
                    boundary_name=boundary_name,
                    ref=str(information_ref),
                )
            )
        for evidence_ref in getattr(rule, "evidence_refs", []) or []:
            if not _is_bound_reference(evidence_ref, declared_refs=evidence_refs, is_unresolved=is_unresolved):
                issues.append(
                    ParticipantBehaviorIssue(
                        code="participant.view-rule-evidence-unbound",
                        participant_name="",
                        boundary_name=boundary_name,
                        ref=str(evidence_ref),
                    )
                )
    return issues


def _view_transition_visibility_issues(
    *,
    boundary_name: str,
    boundary: object,
    declared_refs: set[str],
    evidence_refs: set[str],
    is_unresolved: Callable[[object], bool],
) -> list[ParticipantBehaviorIssue]:
    issues: list[ParticipantBehaviorIssue] = []
    for transition in getattr(boundary, "view_transitions", []) or []:
        information_ref = getattr(transition, "information_ref", "")
        transition_id = str(getattr(transition, "transition_id", ""))
        if not _is_bound_reference(information_ref, declared_refs=declared_refs, is_unresolved=is_unresolved):
            issues.append(
                ParticipantBehaviorIssue(
                    code="participant.view-transition-ref-unbound",
                    participant_name="",
                    boundary_name=boundary_name,
                    transition_id=transition_id,
                    ref=str(information_ref),
                )
            )
        for evidence_ref in getattr(transition, "evidence_refs", []) or []:
            if not _is_bound_reference(evidence_ref, declared_refs=evidence_refs, is_unresolved=is_unresolved):
                issues.append(
                    ParticipantBehaviorIssue(
                        code="participant.view-transition-evidence-unbound",
                        participant_name="",
                        boundary_name=boundary_name,
                        transition_id=transition_id,
                        ref=str(evidence_ref),
                    )
                )
    return issues


def _visibility_issues_for_observation_boundaries(
    *,
    observation_boundaries: Mapping[str, object],
    is_unresolved: Callable[[object], bool],
) -> list[ParticipantBehaviorIssue]:
    issues: list[ParticipantBehaviorIssue] = []
    for boundary_name, boundary in observation_boundaries.items():
        declared_refs = _observation_boundary_declared_refs(boundary)
        evidence_refs = _observation_boundary_evidence_refs(boundary)
        issues.extend(
            _view_rule_visibility_issues(
                boundary_name=str(boundary_name),
                boundary=boundary,
                declared_refs=declared_refs,
                evidence_refs=evidence_refs,
                is_unresolved=is_unresolved,
            )
        )
        issues.extend(
            _view_transition_visibility_issues(
                boundary_name=str(boundary_name),
                boundary=boundary,
                declared_refs=declared_refs,
                evidence_refs=evidence_refs,
                is_unresolved=is_unresolved,
            )
        )

    return issues


def analyze_participant_behavior(
    *,
    agents_by_name: Mapping[str, object],
    action_contracts: Mapping[str, object],
    observation_boundaries: Mapping[str, object],
    is_unresolved: Callable[[object], bool],
) -> ParticipantBehaviorAnalysis:
    """Validate and normalize participant action/observation references.

    ``agents.*.actions`` can stay as a legacy authoring affordance when no
    action-contract registry exists. Once a scenario declares
    ``action_contracts``, every authored action name must resolve to that
    governed registry so the compiler never treats raw names as behavior
    semantics.
    """

    references: list[ParticipantBehaviorReference] = []
    issues: list[ParticipantBehaviorIssue] = []

    for participant_name, agent in agents_by_name.items():
        action_references, action_issues = _action_references_for_agent(
            participant_name=participant_name,
            action_names=list(getattr(agent, "actions", []) or []),
            action_contracts=action_contracts,
            is_unresolved=is_unresolved,
        )
        boundary_references, boundary_issues = _observation_boundary_references_for_agent(
            participant_name=participant_name,
            boundary_names=list(getattr(agent, "observation_boundaries", []) or []),
            observation_boundaries=observation_boundaries,
            is_unresolved=is_unresolved,
        )
        references.extend(action_references)
        references.extend(boundary_references)
        issues.extend(action_issues)
        issues.extend(boundary_issues)

    issues.extend(
        _interaction_references_for_action_contracts(
            action_contracts=action_contracts,
            is_unresolved=is_unresolved,
        )
    )
    issues.extend(
        _visibility_issues_for_observation_boundaries(
            observation_boundaries=observation_boundaries,
            is_unresolved=is_unresolved,
        )
    )

    return ParticipantBehaviorAnalysis(references=tuple(references), issues=tuple(issues))
