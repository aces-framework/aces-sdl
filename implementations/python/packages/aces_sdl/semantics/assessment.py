"""Pure assessment-pipeline semantic helpers (SEM-206).

The *assessment pipeline* is the SDL scoring chain::

    condition bindings -> metrics -> evaluations -> TLOs -> goals

This module is the single name-level source of truth for that chain: which
cross-resource references are well-formed, how evaluation scores aggregate from
their metrics, and which dependency roles each pipeline edge carries.
``aces_sdl.validator`` enforces these rules on authored SDL (mapping the
machine-readable issues here back onto its authoring-error strings);
``aces_processor.compiler`` reuses the dependency-role decision when it maps the
chain onto canonical ``evaluation.*`` runtime addresses, and the planner then
walks those edges generically (ordering for execution order, refresh for change
propagation). Per ADR-015 this helper lives with the SDL package and has no
processor-runtime dependencies; per ADR-016 it is part of the realized artifact
set for SEM-206.

Whether a declared condition is actually *bound* to a node — i.e. *realized* —
is a compilation-phase concern (the compiler emits ``evaluation.condition-ref``
diagnostics for unbound/ambiguous bindings); this module deals only with the
name-level reference graph that is meaningful before binding resolution.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum


class AssessmentResourceKind(str, Enum):
    """Kinds of resource that participate in the assessment pipeline."""

    CONDITION = "condition"
    METRIC = "metric"
    EVALUATION = "evaluation"
    TLO = "tlo"
    GOAL = "goal"


class AssessmentDependencyRole(str, Enum):
    """Semantic roles an assessment-pipeline edge can carry."""

    ORDERING = "ordering"
    REFRESH = "refresh"


#: Every edge in the assessment pipeline is both an ordering edge (the
#: downstream resource is computed after its inputs) and a refresh edge (the
#: downstream resource must recompute when any input changes). Keeping this in
#: one place lets the compiler derive ``ordering_dependencies`` /
#: ``refresh_dependencies`` from a single semantic fact instead of restating it
#: at every resource site.
ASSESSMENT_DEPENDENCY_ROLES: tuple[AssessmentDependencyRole, ...] = (
    AssessmentDependencyRole.ORDERING,
    AssessmentDependencyRole.REFRESH,
)


def partition_assessment_dependencies(
    upstream: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split an upstream-dependency list into (ordering, refresh) tuples.

    Both roles cover the whole upstream set today; callers should still route
    through here so a future refresh-only (or ordering-only) edge changes one
    place rather than every compiled-resource construction.
    """

    ordering = tuple(upstream) if AssessmentDependencyRole.ORDERING in ASSESSMENT_DEPENDENCY_ROLES else ()
    refresh = tuple(upstream) if AssessmentDependencyRole.REFRESH in ASSESSMENT_DEPENDENCY_ROLES else ()
    return ordering, refresh


@dataclass(frozen=True)
class AssessmentReference:
    """A normalized assessment-pipeline edge from one resource to an upstream one."""

    raw: str
    source_kind: AssessmentResourceKind
    source_name: str
    target_kind: AssessmentResourceKind
    target_name: str
    dependency_roles: tuple[AssessmentDependencyRole, ...] = ASSESSMENT_DEPENDENCY_ROLES
    #: Reserved for later module/import expansion; the analysis is run on
    #: already-composed scenarios, so it is empty today.
    namespace_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssessmentIssue:
    """A machine-readable assessment-pipeline consistency problem.

    ``ref`` names the offending reference target (an undeclared condition /
    metric / evaluation / TLO). ``observed`` / ``limit`` carry the numbers for
    aggregation issues (e.g. an absolute min-score and the metric-max-score
    total it exceeds).
    """

    code: str
    resource_kind: AssessmentResourceKind
    resource_name: str
    ref: str | None = None
    observed: int | None = None
    limit: int | None = None


@dataclass(frozen=True)
class AssessmentResourceDependencies:
    """Derived upstream dependencies for one assessment-pipeline resource."""

    kind: AssessmentResourceKind
    name: str
    ordering_names: tuple[str, ...] = ()
    refresh_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssessmentPipelineAnalysis:
    """Result of analyzing the assessment pipeline of a scenario."""

    references: tuple[AssessmentReference, ...] = ()
    issues: tuple[AssessmentIssue, ...] = ()
    dependencies: tuple[AssessmentResourceDependencies, ...] = ()
    evaluation_metric_totals: Mapping[str, int | None] = field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)

    def issues_of_code(self, code: str) -> tuple[AssessmentIssue, ...]:
        return tuple(issue for issue in self.issues if issue.code == code)

    def dependencies_for(self, kind: AssessmentResourceKind, name: str) -> AssessmentResourceDependencies:
        for dependency in self.dependencies:
            if dependency.kind == kind and dependency.name == name:
                return dependency
        raise KeyError((kind, name))


def _ordered_unique(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def _never_unresolved(_value: object) -> bool:
    return False


def analyze_assessment_pipeline(
    *,
    conditions_by_name: Mapping[str, object],
    metrics_by_name: Mapping[str, object],
    evaluations_by_name: Mapping[str, object],
    tlos_by_name: Mapping[str, object],
    goals_by_name: Mapping[str, object],
    is_unresolved: Callable[[object], bool] | None = None,
) -> AssessmentPipelineAnalysis:
    """Resolve the assessment-pipeline reference graph and derive its semantics.

    Inputs are name-keyed mappings of the SDL constructs (accessed structurally
    via ``getattr``); ``is_unresolved`` (default: never) lets a caller skip
    references that are still ``${var}`` placeholders. Returns the normalized
    reference edges, the per-resource ordering/refresh dependency names, the
    per-evaluation metric-max-score totals (``None`` when any contributing
    max-score is unknown), and any consistency issues — in pipeline order:
    metrics, then evaluations, then TLOs, then goals.
    """

    unresolved = is_unresolved or _never_unresolved
    references: list[AssessmentReference] = []
    issues: list[AssessmentIssue] = []
    dependencies: list[AssessmentResourceDependencies] = []
    evaluation_metric_totals: dict[str, int | None] = {}

    # --- metrics -> conditions ------------------------------------------------
    scored_conditions: set[str] = set()
    for metric_name, metric in metrics_by_name.items():
        condition_name = getattr(metric, "condition", None)
        ordering: tuple[str, ...] = ()
        if condition_name and not unresolved(condition_name):
            if condition_name not in conditions_by_name:
                issues.append(
                    AssessmentIssue(
                        code="metric.condition-undeclared",
                        resource_kind=AssessmentResourceKind.METRIC,
                        resource_name=metric_name,
                        ref=condition_name,
                    )
                )
            else:
                references.append(
                    AssessmentReference(
                        raw=condition_name,
                        source_kind=AssessmentResourceKind.METRIC,
                        source_name=metric_name,
                        target_kind=AssessmentResourceKind.CONDITION,
                        target_name=condition_name,
                    )
                )
                ordering = (condition_name,)
            if condition_name in scored_conditions:
                issues.append(
                    AssessmentIssue(
                        code="metric.condition-multiply-scored",
                        resource_kind=AssessmentResourceKind.CONDITION,
                        resource_name=condition_name,
                        ref=metric_name,
                    )
                )
            scored_conditions.add(condition_name)
        dependencies.append(
            AssessmentResourceDependencies(
                kind=AssessmentResourceKind.METRIC,
                name=metric_name,
                ordering_names=ordering,
                refresh_names=ordering,
            )
        )

    # --- evaluations -> metrics ----------------------------------------------
    for evaluation_name, evaluation in evaluations_by_name.items():
        resolved_metric_names: list[str] = []
        total = 0
        total_known = True
        for ref_name in getattr(evaluation, "metrics", []) or []:
            if unresolved(ref_name):
                total_known = False
                continue
            if ref_name not in metrics_by_name:
                issues.append(
                    AssessmentIssue(
                        code="evaluation.metric-undeclared",
                        resource_kind=AssessmentResourceKind.EVALUATION,
                        resource_name=evaluation_name,
                        ref=ref_name,
                    )
                )
                continue
            references.append(
                AssessmentReference(
                    raw=ref_name,
                    source_kind=AssessmentResourceKind.EVALUATION,
                    source_name=evaluation_name,
                    target_kind=AssessmentResourceKind.METRIC,
                    target_name=ref_name,
                )
            )
            resolved_metric_names.append(ref_name)
            metric_max_score = getattr(metrics_by_name[ref_name], "max_score", None)
            if isinstance(metric_max_score, int) and not isinstance(metric_max_score, bool):
                total += metric_max_score
            else:
                total_known = False
        evaluation_metric_totals[evaluation_name] = total if total_known else None
        upstream = _ordered_unique(resolved_metric_names)
        dependencies.append(
            AssessmentResourceDependencies(
                kind=AssessmentResourceKind.EVALUATION,
                name=evaluation_name,
                ordering_names=upstream,
                refresh_names=upstream,
            )
        )
        min_score = getattr(evaluation, "min_score", None)
        absolute = getattr(min_score, "absolute", None) if min_score is not None else None
        if isinstance(absolute, int) and not isinstance(absolute, bool) and total_known and absolute > total:
            issues.append(
                AssessmentIssue(
                    code="evaluation.min-score-exceeds-metric-total",
                    resource_kind=AssessmentResourceKind.EVALUATION,
                    resource_name=evaluation_name,
                    observed=absolute,
                    limit=total,
                )
            )

    # --- TLOs -> evaluations --------------------------------------------------
    for tlo_name, tlo in tlos_by_name.items():
        evaluation_name = getattr(tlo, "evaluation", None)
        ordering = ()
        if evaluation_name is not None and not unresolved(evaluation_name):
            if evaluation_name not in evaluations_by_name:
                issues.append(
                    AssessmentIssue(
                        code="tlo.evaluation-undeclared",
                        resource_kind=AssessmentResourceKind.TLO,
                        resource_name=tlo_name,
                        ref=evaluation_name,
                    )
                )
            else:
                references.append(
                    AssessmentReference(
                        raw=evaluation_name,
                        source_kind=AssessmentResourceKind.TLO,
                        source_name=tlo_name,
                        target_kind=AssessmentResourceKind.EVALUATION,
                        target_name=evaluation_name,
                    )
                )
                ordering = (evaluation_name,)
        dependencies.append(
            AssessmentResourceDependencies(
                kind=AssessmentResourceKind.TLO,
                name=tlo_name,
                ordering_names=ordering,
                refresh_names=ordering,
            )
        )

    # --- goals -> TLOs --------------------------------------------------------
    for goal_name, goal in goals_by_name.items():
        resolved_tlo_names: list[str] = []
        for ref_name in getattr(goal, "tlos", []) or []:
            if unresolved(ref_name):
                continue
            if ref_name not in tlos_by_name:
                issues.append(
                    AssessmentIssue(
                        code="goal.tlo-undeclared",
                        resource_kind=AssessmentResourceKind.GOAL,
                        resource_name=goal_name,
                        ref=ref_name,
                    )
                )
                continue
            references.append(
                AssessmentReference(
                    raw=ref_name,
                    source_kind=AssessmentResourceKind.GOAL,
                    source_name=goal_name,
                    target_kind=AssessmentResourceKind.TLO,
                    target_name=ref_name,
                )
            )
            resolved_tlo_names.append(ref_name)
        upstream = _ordered_unique(resolved_tlo_names)
        dependencies.append(
            AssessmentResourceDependencies(
                kind=AssessmentResourceKind.GOAL,
                name=goal_name,
                ordering_names=upstream,
                refresh_names=upstream,
            )
        )

    return AssessmentPipelineAnalysis(
        references=tuple(references),
        issues=tuple(issues),
        dependencies=tuple(dependencies),
        evaluation_metric_totals=dict(evaluation_metric_totals),
    )
