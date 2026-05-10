"""Pure declarative-objective semantic helpers (SEM-207).

A declarative *objective* is the SDL construct that binds, in one place:

* an **actor** — exactly one of an authored ``agent`` or an authored
  ``entity`` — that owns the objective;
* zero or more **targets**, normalized through the targetable named-reference
  index (bare or section-qualified);
* a **success** interpretation — ``mode`` (``all_of`` / ``any_of``) over
  referenced conditions, metrics, evaluations, TLOs, and goals;
* an optional **window** that constrains when the objective matters (the
  story/script/event/workflow/workflow-step semantics live in
  :func:`aces_sdl.semantics.objectives.analyze_objective_window`);
* a ``depends_on`` **ordering** relation onto other objectives, which must be
  acyclic.

:func:`analyze_objective_semantics` is the single name-level source of truth
for that construct: which cross-resource references are well-formed, which
dependency roles each carries (success and ``depends_on`` edges order *and*
refresh; window edges only refresh; actor and target references are normalized
for fail-closed validation but the compiler does not propagate refresh through
them today, so they carry an empty role tuple), and which fail-closed issues an
authored objective has. ``aces_sdl.validator`` renders the machine-readable
issues here as authoring errors; ``aces_processor.compiler`` reuses the
ordering/refresh role decision (:func:`partition_objective_dependencies`) when
it maps a compiled ``evaluation.objective.*`` resource onto its dependency
tuples, and the planner then walks those edges generically. Per ADR-015 this
helper lives with the SDL package and has no processor-runtime dependencies;
per ADR-016 it is part of the realized artifact set for SEM-207.

Whether a declared success ``condition`` is actually *bound* to a node is a
compilation-phase concern (the compiler emits ``evaluation.condition-ref``
diagnostics against the resolved addresses); this module deals only with the
name-level reference graph that is meaningful before binding resolution.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from enum import Enum

from .assessment import AssessmentResourceKind
from .objectives import (
    ObjectiveDependencyRole,
    ObjectiveWindowAnalysis,
    ObjectiveWindowReferenceKind,
    analyze_objective_window,
)


class ObjectiveReferenceKind(str, Enum):
    """Kinds of cross-resource reference an objective carries."""

    ACTOR = "actor"
    TARGET = "target"
    SUCCESS = "success"
    WINDOW = "window"
    DEPENDENCY = "dependency"


#: Success references (``success.{conditions,metrics,evaluations,tlos,goals}``)
#: and ``depends_on`` edges are both ordering edges (the objective is evaluated
#: after its inputs) and refresh edges (re-evaluated when an input changes).
#: Window references only refresh the objective. Actor and target references
#: are normalized for fail-closed validation but carry no runtime dependency
#: role today: the compiler does not propagate ordering or refresh through
#: actor or target identity, and advertising a role here would let
#: ``analyze_objective_semantics`` claim a propagation that never reaches the
#: planner. A future change that compiles actor/target into runtime addresses
#: lifts ``REFRESH`` (or ``ORDERING``) here in lockstep.
OBJECTIVE_SUCCESS_DEPENDENCY_ROLES: tuple[ObjectiveDependencyRole, ...] = (
    ObjectiveDependencyRole.ORDERING,
    ObjectiveDependencyRole.REFRESH,
)
OBJECTIVE_DEPENDENCY_DEPENDENCY_ROLES: tuple[ObjectiveDependencyRole, ...] = (
    ObjectiveDependencyRole.ORDERING,
    ObjectiveDependencyRole.REFRESH,
)
OBJECTIVE_ACTOR_DEPENDENCY_ROLES: tuple[ObjectiveDependencyRole, ...] = ()
OBJECTIVE_TARGET_DEPENDENCY_ROLES: tuple[ObjectiveDependencyRole, ...] = ()
OBJECTIVE_WINDOW_DEPENDENCY_ROLES: tuple[ObjectiveDependencyRole, ...] = (ObjectiveDependencyRole.REFRESH,)


@dataclass(frozen=True)
class ObjectiveReference:
    """A normalized reference from one objective to an upstream resource."""

    raw: str
    canonical_name: str
    reference_kind: ObjectiveReferenceKind
    source_name: str
    dependency_roles: tuple[ObjectiveDependencyRole, ...] = ()
    #: Set on ``SUCCESS`` references to disambiguate the assessment-pipeline
    #: namespace (a condition and a metric may legally share an SDL name).
    success_resource_kind: AssessmentResourceKind | None = None
    window_reference_kind: ObjectiveWindowReferenceKind | None = None
    workflow_name: str | None = None
    step_name: str | None = None
    #: Reserved for later module/import expansion; the analysis runs on
    #: already-composed scenarios, so it is empty today.
    namespace_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObjectiveIssue:
    """A machine-readable objective-semantics consistency problem.

    ``ref`` names the offending reference target. ``actor_name`` carries the
    declaring agent for ``action-not-declared``. ``candidates`` carries the
    sorted alternatives for an ambiguous target. ``workflow_name`` / ``step_name``
    carry the parsed parts of a window step ref. ``objective_name`` is empty for
    the global ``objective.dependency-cycle`` issue.
    """

    code: str
    objective_name: str
    ref: str | None = None
    actor_name: str | None = None
    candidates: tuple[str, ...] = ()
    workflow_name: str | None = None
    step_name: str | None = None


@dataclass(frozen=True)
class ObjectiveResourceDependencies:
    """Derived upstream dependencies for one objective."""

    name: str
    ordering_names: tuple[str, ...] = ()
    refresh_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObjectiveSemanticAnalysis:
    """Result of analyzing the declarative objectives of a scenario."""

    references: tuple[ObjectiveReference, ...] = ()
    issues: tuple[ObjectiveIssue, ...] = ()
    dependencies: tuple[ObjectiveResourceDependencies, ...] = ()
    window_analyses: Mapping[str, ObjectiveWindowAnalysis] = field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)

    def issues_of_code(self, code: str) -> tuple[ObjectiveIssue, ...]:
        return tuple(issue for issue in self.issues if issue.code == code)

    def references_of_kind(self, kind: ObjectiveReferenceKind) -> tuple[ObjectiveReference, ...]:
        return tuple(ref for ref in self.references if ref.reference_kind == kind)

    def dependencies_for(self, name: str) -> ObjectiveResourceDependencies:
        for dependency in self.dependencies:
            if dependency.name == name:
                return dependency
        raise KeyError(name)


def _ordered_unique(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def _never_unresolved(_value: object) -> bool:
    return False


def partition_objective_dependencies(
    *,
    success_refs: Collection[str],
    dependency_refs: Collection[str],
    window_refresh_refs: Collection[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split an objective's upstream references into (ordering, refresh) tuples.

    Each category is gated by its own ``OBJECTIVE_*_DEPENDENCY_ROLES`` constant
    so a future role change to one category (say, ``depends_on`` becoming
    refresh-only) lands in exactly one place. Works on names (validator side)
    or compiled addresses (compiler side); the result is order-preserving and
    de-duplicated within each role.
    """

    success = list(success_refs)
    deps = list(dependency_refs)
    window = list(window_refresh_refs)
    ordering: list[str] = []
    refresh: list[str] = []
    for category, roles in (
        (success, OBJECTIVE_SUCCESS_DEPENDENCY_ROLES),
        (deps, OBJECTIVE_DEPENDENCY_DEPENDENCY_ROLES),
        (window, OBJECTIVE_WINDOW_DEPENDENCY_ROLES),
    ):
        if ObjectiveDependencyRole.ORDERING in roles:
            ordering.extend(category)
        if ObjectiveDependencyRole.REFRESH in roles:
            refresh.extend(category)
    return _ordered_unique(ordering), _ordered_unique(refresh)


def _has_cycle(graph: Mapping[str, list[str]]) -> bool:
    """Return True if the directed ``graph`` (node -> deps) contains a cycle."""

    in_degree: dict[str, int] = defaultdict(int)
    for node in graph:
        in_degree.setdefault(node, 0)
    for deps in graph.values():
        for dep in deps:
            in_degree[dep] += 1
    queue = deque(node for node, degree in in_degree.items() if degree == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for dep in graph.get(node, []):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)
    return visited != len(in_degree)


_SUCCESS_REFERENCE_SECTIONS: tuple[tuple[str, AssessmentResourceKind, str], ...] = (
    ("conditions", AssessmentResourceKind.CONDITION, "objective.success-condition-undeclared"),
    ("metrics", AssessmentResourceKind.METRIC, "objective.success-metric-undeclared"),
    ("evaluations", AssessmentResourceKind.EVALUATION, "objective.success-evaluation-undeclared"),
    ("tlos", AssessmentResourceKind.TLO, "objective.success-tlo-undeclared"),
    ("goals", AssessmentResourceKind.GOAL, "objective.success-goal-undeclared"),
)


def analyze_objective_semantics(
    *,
    objectives_by_name: Mapping[str, object],
    agents_by_name: Mapping[str, object],
    entity_names: Collection[str],
    conditions_by_name: Mapping[str, object],
    metrics_by_name: Mapping[str, object],
    evaluations_by_name: Mapping[str, object],
    tlos_by_name: Mapping[str, object],
    goals_by_name: Mapping[str, object],
    stories_by_name: Mapping[str, object],
    scripts_by_name: Mapping[str, object],
    events_by_name: Mapping[str, object],
    workflows_by_name: Mapping[str, object],
    targetable_name_index: Mapping[str, Collection[str]],
    is_unresolved: Callable[[object], bool] | None = None,
) -> ObjectiveSemanticAnalysis:
    """Resolve the objective reference graph and derive its shared semantics.

    Inputs are name-keyed mappings of the SDL constructs (accessed structurally
    via ``getattr``) plus the targetable named-reference index;
    ``is_unresolved`` (default: never) lets a caller skip references that are
    still ``${var}`` placeholders. Returns the normalized references, the
    per-objective ordering/refresh dependency names, the per-objective window
    analyses, and any consistency issues — per objective in the order actor,
    action, target, success, window, dependency, then a single global
    ``objective.dependency-cycle`` issue when the ``depends_on`` graph cycles.
    """

    unresolved = is_unresolved or _never_unresolved
    entity_name_set = set(entity_names)
    success_sections = (
        (conditions_by_name, _SUCCESS_REFERENCE_SECTIONS[0]),
        (metrics_by_name, _SUCCESS_REFERENCE_SECTIONS[1]),
        (evaluations_by_name, _SUCCESS_REFERENCE_SECTIONS[2]),
        (tlos_by_name, _SUCCESS_REFERENCE_SECTIONS[3]),
        (goals_by_name, _SUCCESS_REFERENCE_SECTIONS[4]),
    )

    references: list[ObjectiveReference] = []
    issues: list[ObjectiveIssue] = []
    dependencies: list[ObjectiveResourceDependencies] = []
    window_analyses: dict[str, ObjectiveWindowAnalysis] = {}

    for objective_name, objective in objectives_by_name.items():
        # --- actor binding (agent xor entity) -------------------------------
        agent_name = getattr(objective, "agent", "") or ""
        entity_ref = getattr(objective, "entity", "") or ""
        if agent_name and not unresolved(agent_name):
            if agent_name not in agents_by_name:
                issues.append(
                    ObjectiveIssue(
                        code="objective.actor-agent-undeclared",
                        objective_name=objective_name,
                        ref=agent_name,
                    )
                )
            else:
                references.append(
                    ObjectiveReference(
                        raw=agent_name,
                        canonical_name=agent_name,
                        reference_kind=ObjectiveReferenceKind.ACTOR,
                        source_name=objective_name,
                        dependency_roles=OBJECTIVE_ACTOR_DEPENDENCY_ROLES,
                    )
                )
                allowed_actions = set(getattr(agents_by_name[agent_name], "actions", []) or [])
                for action in getattr(objective, "actions", []) or []:
                    if unresolved(action):
                        continue
                    if action not in allowed_actions:
                        issues.append(
                            ObjectiveIssue(
                                code="objective.action-not-declared",
                                objective_name=objective_name,
                                ref=action,
                                actor_name=agent_name,
                            )
                        )
        if entity_ref and not unresolved(entity_ref):
            if entity_ref not in entity_name_set:
                issues.append(
                    ObjectiveIssue(
                        code="objective.actor-entity-undeclared",
                        objective_name=objective_name,
                        ref=entity_ref,
                    )
                )
            else:
                references.append(
                    ObjectiveReference(
                        raw=entity_ref,
                        canonical_name=f"entities.{entity_ref}",
                        reference_kind=ObjectiveReferenceKind.ACTOR,
                        source_name=objective_name,
                        dependency_roles=OBJECTIVE_ACTOR_DEPENDENCY_ROLES,
                    )
                )

        # --- targets --------------------------------------------------------
        for target in getattr(objective, "targets", []) or []:
            if unresolved(target):
                continue
            candidates = targetable_name_index.get(target)
            if not candidates:
                issues.append(
                    ObjectiveIssue(
                        code="objective.target-unresolvable",
                        objective_name=objective_name,
                        ref=target,
                    )
                )
                continue
            if len(candidates) > 1:
                issues.append(
                    ObjectiveIssue(
                        code="objective.target-ambiguous",
                        objective_name=objective_name,
                        ref=target,
                        candidates=tuple(sorted(candidates)),
                    )
                )
                continue
            (canonical_target,) = tuple(candidates)
            references.append(
                ObjectiveReference(
                    raw=target,
                    canonical_name=canonical_target,
                    reference_kind=ObjectiveReferenceKind.TARGET,
                    source_name=objective_name,
                    dependency_roles=OBJECTIVE_TARGET_DEPENDENCY_ROLES,
                )
            )

        # --- success interpretation ----------------------------------------
        # Each success namespace (condition / metric / evaluation / TLO / goal)
        # contributes its own keyspace; success names are kind-qualified before
        # they enter the derived ordering/refresh tuples so that a metric and a
        # condition with the same SDL name remain distinguishable to callers.
        success = getattr(objective, "success", None)
        resolved_success: list[str] = []
        for section, (attr, kind, code) in success_sections:
            for ref_name in getattr(success, attr, []) or []:
                if unresolved(ref_name):
                    continue
                if ref_name not in section:
                    issues.append(ObjectiveIssue(code=code, objective_name=objective_name, ref=ref_name))
                    continue
                qualified_name = f"{kind.value}.{ref_name}"
                references.append(
                    ObjectiveReference(
                        raw=ref_name,
                        canonical_name=qualified_name,
                        reference_kind=ObjectiveReferenceKind.SUCCESS,
                        source_name=objective_name,
                        dependency_roles=OBJECTIVE_SUCCESS_DEPENDENCY_ROLES,
                        success_resource_kind=kind,
                    )
                )
                resolved_success.append(qualified_name)

        # --- window --------------------------------------------------------
        window = getattr(objective, "window", None)
        window_refresh: list[str] = []
        if window is not None:
            window_analysis = analyze_objective_window(
                story_refs=[ref for ref in getattr(window, "stories", []) or [] if not unresolved(ref)],
                script_refs=[ref for ref in getattr(window, "scripts", []) or [] if not unresolved(ref)],
                event_refs=[ref for ref in getattr(window, "events", []) or [] if not unresolved(ref)],
                workflow_refs=[ref for ref in getattr(window, "workflows", []) or [] if not unresolved(ref)],
                step_refs=[ref for ref in getattr(window, "steps", []) or [] if not unresolved(ref)],
                stories_by_name=stories_by_name,
                scripts_by_name=scripts_by_name,
                events_by_name=events_by_name,
                workflows_by_name=workflows_by_name,
            )
            window_analyses[objective_name] = window_analysis
            for window_ref in window_analysis.references:
                references.append(
                    ObjectiveReference(
                        raw=window_ref.raw,
                        canonical_name=window_ref.canonical_name,
                        reference_kind=ObjectiveReferenceKind.WINDOW,
                        source_name=objective_name,
                        # The SEM-207 role constant is the single authority for
                        # objective-side window roles; the lower-level
                        # ``ObjectiveWindowReference.dependency_roles`` is the
                        # SEM-202 helper's own metadata and must not double as
                        # the planner-facing role decision.
                        dependency_roles=OBJECTIVE_WINDOW_DEPENDENCY_ROLES,
                        window_reference_kind=window_ref.reference_kind,
                        workflow_name=window_ref.workflow_name,
                        step_name=window_ref.step_name,
                        namespace_path=window_ref.namespace_path,
                    )
                )
            for window_issue in window_analysis.issues:
                issues.append(
                    ObjectiveIssue(
                        code=f"objective.window.{window_issue.code}",
                        objective_name=objective_name,
                        ref=window_issue.ref,
                        workflow_name=window_issue.workflow_name,
                        step_name=window_issue.step_name,
                    )
                )
            # Each window keyspace gets its kind prefix so it cannot collide
            # with success-side or depends_on-side names in ``refresh_names``.
            window_refresh = [
                *(f"story.{name}" for name in window_analysis.story_names),
                *(f"script.{name}" for name in window_analysis.script_names),
                *(f"event.{name}" for name in window_analysis.event_names),
                *(f"workflow.{name}" for name in window_analysis.workflow_names),
                *(f"workflow.{name}" for name in window_analysis.refresh_workflow_names),
            ]

        # --- dependency ordering -------------------------------------------
        resolved_dependencies: list[str] = []
        for dep_name in getattr(objective, "depends_on", []) or []:
            if unresolved(dep_name):
                continue
            if dep_name not in objectives_by_name:
                issues.append(
                    ObjectiveIssue(
                        code="objective.dependency-undeclared",
                        objective_name=objective_name,
                        ref=dep_name,
                    )
                )
                continue
            qualified_dep = f"objective.{dep_name}"
            references.append(
                ObjectiveReference(
                    raw=dep_name,
                    canonical_name=qualified_dep,
                    reference_kind=ObjectiveReferenceKind.DEPENDENCY,
                    source_name=objective_name,
                    dependency_roles=OBJECTIVE_DEPENDENCY_DEPENDENCY_ROLES,
                )
            )
            resolved_dependencies.append(qualified_dep)

        ordering_names, refresh_names = partition_objective_dependencies(
            success_refs=_ordered_unique(resolved_success),
            dependency_refs=_ordered_unique(resolved_dependencies),
            window_refresh_refs=window_refresh,
        )
        dependencies.append(
            ObjectiveResourceDependencies(
                name=objective_name,
                ordering_names=ordering_names,
                refresh_names=refresh_names,
            )
        )

    dependency_graph: dict[str, list[str]] = {
        name: [
            dep
            for dep in getattr(objective, "depends_on", []) or []
            if not unresolved(dep) and dep in objectives_by_name
        ]
        for name, objective in objectives_by_name.items()
    }
    if dependency_graph and _has_cycle(dependency_graph):
        issues.append(ObjectiveIssue(code="objective.dependency-cycle", objective_name=""))

    return ObjectiveSemanticAnalysis(
        references=tuple(references),
        issues=tuple(issues),
        dependencies=tuple(dependencies),
        window_analyses=dict(window_analyses),
    )
