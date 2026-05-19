"""Name-level participant behavior semantics (SEM-208)."""

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

    return ParticipantBehaviorAnalysis(references=tuple(references), issues=tuple(issues))
