"""Name-level participant outcome interpretation semantics (SEM-215)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from aces_sdl.participant_outcome_semantics import (
    OutcomeInterpretationSourceLayer,
    OutcomeInterpretationTargetLayer,
)


@dataclass(frozen=True)
class ParticipantOutcomeIssue:
    """Machine-readable participant outcome interpretation consistency issue."""

    code: str
    rule_name: str
    binding_id: str
    ref: str
    layer: str


@dataclass(frozen=True)
class ParticipantOutcomeAnalysis:
    """Result of analyzing outcome interpretation rule references."""

    issues: tuple[ParticipantOutcomeIssue, ...] = ()

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


def _source_ref_issue(
    *,
    rule_name: str,
    binding: object,
    action_contracts: Mapping[str, object],
    objectives: Mapping[str, object],
    workflows: Mapping[str, object],
    evaluations: Mapping[str, object],
    is_unresolved: Callable[[object], bool],
) -> ParticipantOutcomeIssue | None:
    layer = getattr(binding, "source_layer", None)
    ref = getattr(binding, "ref", "")
    binding_id = str(getattr(binding, "source_id", ""))
    if is_unresolved(ref):
        return None
    if layer == OutcomeInterpretationSourceLayer.PARTICIPANT_ACTION_OUTCOME and ref not in action_contracts:
        return ParticipantOutcomeIssue(
            code="participant.outcome.source-action-unbound",
            rule_name=rule_name,
            binding_id=binding_id,
            ref=str(ref),
            layer=layer.value,
        )
    if layer == OutcomeInterpretationSourceLayer.OBJECTIVE_RESULT and ref not in objectives:
        return ParticipantOutcomeIssue(
            code="participant.outcome.source-objective-unbound",
            rule_name=rule_name,
            binding_id=binding_id,
            ref=str(ref),
            layer=layer.value,
        )
    if layer == OutcomeInterpretationSourceLayer.WORKFLOW_RESULT and ref not in workflows:
        return ParticipantOutcomeIssue(
            code="participant.outcome.source-workflow-unbound",
            rule_name=rule_name,
            binding_id=binding_id,
            ref=str(ref),
            layer=layer.value,
        )
    if layer == OutcomeInterpretationSourceLayer.EVALUATION_RESULT and ref not in evaluations:
        return ParticipantOutcomeIssue(
            code="participant.outcome.source-evaluation-unbound",
            rule_name=rule_name,
            binding_id=binding_id,
            ref=str(ref),
            layer=layer.value,
        )
    return None


def _target_ref_issue(
    *,
    rule_name: str,
    binding: object,
    objectives: Mapping[str, object],
    workflows: Mapping[str, object],
    evaluations: Mapping[str, object],
    is_unresolved: Callable[[object], bool],
) -> ParticipantOutcomeIssue | None:
    layer = getattr(binding, "target_layer", None)
    ref = getattr(binding, "ref", "")
    binding_id = str(getattr(binding, "target_id", ""))
    if is_unresolved(ref):
        return None
    if layer == OutcomeInterpretationTargetLayer.OBJECTIVE_RESULT and ref not in objectives:
        return ParticipantOutcomeIssue(
            code="participant.outcome.target-objective-unbound",
            rule_name=rule_name,
            binding_id=binding_id,
            ref=str(ref),
            layer=layer.value,
        )
    if layer == OutcomeInterpretationTargetLayer.WORKFLOW_RESULT and ref not in workflows:
        return ParticipantOutcomeIssue(
            code="participant.outcome.target-workflow-unbound",
            rule_name=rule_name,
            binding_id=binding_id,
            ref=str(ref),
            layer=layer.value,
        )
    if layer == OutcomeInterpretationTargetLayer.EVALUATION_RESULT and ref not in evaluations:
        return ParticipantOutcomeIssue(
            code="participant.outcome.target-evaluation-unbound",
            rule_name=rule_name,
            binding_id=binding_id,
            ref=str(ref),
            layer=layer.value,
        )
    return None


def analyze_participant_outcome_interpretations(
    *,
    outcome_interpretation_rules: Mapping[str, object],
    action_contracts: Mapping[str, object],
    objectives: Mapping[str, object],
    workflows: Mapping[str, object],
    evaluations: Mapping[str, object],
    is_unresolved: Callable[[object], bool],
) -> ParticipantOutcomeAnalysis:
    """Validate source/target refs declared by SEM-215 interpretation rules."""

    issues: list[ParticipantOutcomeIssue] = []
    for rule_name, rule in outcome_interpretation_rules.items():
        for binding in getattr(rule, "source_bindings", ()) or ():
            issue = _source_ref_issue(
                rule_name=str(rule_name),
                binding=binding,
                action_contracts=action_contracts,
                objectives=objectives,
                workflows=workflows,
                evaluations=evaluations,
                is_unresolved=is_unresolved,
            )
            if issue is not None:
                issues.append(issue)
        for binding in getattr(rule, "target_bindings", ()) or ():
            issue = _target_ref_issue(
                rule_name=str(rule_name),
                binding=binding,
                objectives=objectives,
                workflows=workflows,
                evaluations=evaluations,
                is_unresolved=is_unresolved,
            )
            if issue is not None:
                issues.append(issue)
    return ParticipantOutcomeAnalysis(issues=tuple(issues))


__all__ = [
    "ParticipantOutcomeAnalysis",
    "ParticipantOutcomeIssue",
    "analyze_participant_outcome_interpretations",
]
