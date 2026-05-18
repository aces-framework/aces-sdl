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


@dataclass(frozen=True)
class ParticipantBehaviorAnalysis:
    """Result of analyzing participant behavior references."""

    references: tuple[ParticipantBehaviorReference, ...] = ()
    issues: tuple[ParticipantBehaviorIssue, ...] = ()

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


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
        for action_name in getattr(agent, "actions", []) or []:
            if is_unresolved(action_name):
                continue
            if action_contracts and action_name not in action_contracts:
                issues.append(
                    ParticipantBehaviorIssue(
                        code="participant.action-contract-unbound",
                        participant_name=participant_name,
                        ref=action_name,
                    )
                )
                continue
            if action_name in action_contracts:
                references.append(
                    ParticipantBehaviorReference(
                        participant_name=participant_name,
                        reference_kind="action_contract",
                        raw=action_name,
                        canonical_name=action_name,
                    )
                )

        for boundary_name in getattr(agent, "observation_boundaries", []) or []:
            if is_unresolved(boundary_name):
                continue
            if boundary_name not in observation_boundaries:
                issues.append(
                    ParticipantBehaviorIssue(
                        code="participant.observation-boundary-unbound",
                        participant_name=participant_name,
                        ref=boundary_name,
                    )
                )
                continue
            references.append(
                ParticipantBehaviorReference(
                    participant_name=participant_name,
                    reference_kind="observation_boundary",
                    raw=boundary_name,
                    canonical_name=boundary_name,
                )
            )

    return ParticipantBehaviorAnalysis(references=tuple(references), issues=tuple(issues))
