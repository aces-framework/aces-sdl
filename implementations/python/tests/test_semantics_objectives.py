"""Shared objective/window semantic tests."""

from __future__ import annotations

from types import SimpleNamespace

from hypothesis import given
from hypothesis import strategies as st

from aces.core.semantics.assessment import AssessmentResourceKind
from aces.core.semantics.objective_semantics import (
    OBJECTIVE_ACTOR_DEPENDENCY_ROLES,
    OBJECTIVE_DEPENDENCY_DEPENDENCY_ROLES,
    OBJECTIVE_SUCCESS_DEPENDENCY_ROLES,
    OBJECTIVE_TARGET_DEPENDENCY_ROLES,
    OBJECTIVE_WINDOW_DEPENDENCY_ROLES,
    AssessmentResourceCatalog,
    ObjectiveReferenceKind,
    WindowResourceCatalog,
    analyze_objective_semantics,
    partition_objective_dependencies,
)
from aces.core.semantics.objectives import (
    ObjectiveDependencyRole,
    ObjectiveWindowReferenceKind,
    analyze_objective_window,
)


def _workflow(*step_names: str) -> SimpleNamespace:
    return SimpleNamespace(steps={name: object() for name in step_names})


class TestObjectiveWindowSemantics:
    def test_window_analysis_normalizes_references_and_reachability(self):
        analysis = analyze_objective_window(
            story_refs=["exercise"],
            script_refs=["timeline"],
            event_refs=["kickoff"],
            workflow_refs=["flow"],
            step_refs=["flow.branch"],
            stories_by_name={
                "exercise": SimpleNamespace(scripts=["timeline"]),
            },
            scripts_by_name={
                "timeline": SimpleNamespace(events={"kickoff": 10}),
            },
            events_by_name={"kickoff": SimpleNamespace()},
            workflows_by_name={"flow": _workflow("start", "branch", "end")},
        )

        assert not analysis.issues
        assert analysis.story_names == ("exercise",)
        assert analysis.script_names == ("timeline",)
        assert analysis.event_names == ("kickoff",)
        assert analysis.workflow_names == ("flow",)
        assert analysis.workflow_step_refs == ("flow.branch",)
        assert analysis.reachable_script_names == ("timeline",)
        assert analysis.reachable_event_names == ("kickoff",)
        assert analysis.refresh_workflow_names == ("flow",)
        assert [ref.reference_kind for ref in analysis.references] == [
            ObjectiveWindowReferenceKind.STORY,
            ObjectiveWindowReferenceKind.SCRIPT,
            ObjectiveWindowReferenceKind.EVENT,
            ObjectiveWindowReferenceKind.WORKFLOW,
            ObjectiveWindowReferenceKind.WORKFLOW_STEP,
        ]

    def test_window_analysis_reports_fail_closed_issues(self):
        analysis = analyze_objective_window(
            story_refs=["missing-story"],
            script_refs=["side"],
            event_refs=["cleanup"],
            workflow_refs=["flow"],
            step_refs=["bad", "other.done", "flow.missing"],
            stories_by_name={},
            scripts_by_name={
                "side": SimpleNamespace(events={"kickoff": 10}),
            },
            events_by_name={"cleanup": SimpleNamespace()},
            workflows_by_name={
                "flow": _workflow("start"),
                "other": _workflow("done"),
            },
        )

        assert {issue.code for issue in analysis.issues} == {
            "story-unbound",
            "event-outside-window-scripts",
            "step-invalid-format",
            "step-workflow-outside-window",
            "step-unbound",
        }

    @given(st.lists(st.sampled_from(["flow.start", "flow.branch"]), max_size=12))
    def test_workflow_step_normalization_is_stable(self, step_refs: list[str]):
        analysis = analyze_objective_window(
            story_refs=[],
            script_refs=[],
            event_refs=[],
            workflow_refs=["flow"],
            step_refs=step_refs,
            stories_by_name={},
            scripts_by_name={},
            events_by_name={},
            workflows_by_name={"flow": _workflow("start", "branch")},
        )

        assert analysis.workflow_step_refs == tuple(dict.fromkeys(step_refs))


def _success(*, conditions=None, metrics=None, evaluations=None, tlos=None, goals=None, mode="all_of"):
    return SimpleNamespace(
        conditions=list(conditions or []),
        metrics=list(metrics or []),
        evaluations=list(evaluations or []),
        tlos=list(tlos or []),
        goals=list(goals or []),
        mode=mode,
    )


def _window(*, stories=None, scripts=None, events=None, workflows=None, steps=None):
    return SimpleNamespace(
        stories=list(stories or []),
        scripts=list(scripts or []),
        events=list(events or []),
        workflows=list(workflows or []),
        steps=list(steps or []),
    )


def _objective(*, agent="", entity="", actions=None, targets=None, success=None, window=None, depends_on=None):
    return SimpleNamespace(
        agent=agent,
        entity=entity,
        actions=list(actions or []),
        targets=list(targets or []),
        success=success if success is not None else _success(conditions=["health"]),
        window=window,
        depends_on=list(depends_on or []),
    )


def _agent(*actions: str) -> SimpleNamespace:
    return SimpleNamespace(actions=list(actions))


def _is_var(value: object) -> bool:
    return isinstance(value, str) and value.startswith("${") and value.endswith("}")


def _analyze(objectives, **overrides):
    """Drive the analyzer with empty defaults; per-test overrides drop in.

    Resource maps are bundled into ``AssessmentResourceCatalog`` /
    ``WindowResourceCatalog`` for the analyzer; tests still pass the per-section
    overrides (``conditions_by_name``, ``stories_by_name``, …) for readability.
    """

    section_defaults = {
        "conditions_by_name": {},
        "metrics_by_name": {},
        "evaluations_by_name": {},
        "tlos_by_name": {},
        "goals_by_name": {},
        "stories_by_name": {},
        "scripts_by_name": {},
        "events_by_name": {},
        "workflows_by_name": {},
    }
    sections = {key: overrides.pop(key, default) for key, default in section_defaults.items()}
    kwargs: dict = {
        "objectives_by_name": objectives,
        "agents_by_name": {},
        "entity_names": set(),
        "assessment_resources": AssessmentResourceCatalog(
            conditions=sections["conditions_by_name"],
            metrics=sections["metrics_by_name"],
            evaluations=sections["evaluations_by_name"],
            tlos=sections["tlos_by_name"],
            goals=sections["goals_by_name"],
        ),
        "window_resources": WindowResourceCatalog(
            stories=sections["stories_by_name"],
            scripts=sections["scripts_by_name"],
            events=sections["events_by_name"],
            workflows=sections["workflows_by_name"],
        ),
        "targetable_name_index": {},
    }
    kwargs.update(overrides)
    return analyze_objective_semantics(**kwargs)


class TestObjectiveSemantics:
    def test_well_formed_objectives_normalize_references_and_dependencies(self) -> None:
        analysis = _analyze(
            {
                "base": _objective(entity="blue", success=_success(metrics=["m1"])),
                "follow": _objective(
                    agent="red",
                    actions=["Scan"],
                    targets=["nodes.web"],
                    success=_success(goals=["g1"]),
                    window=_window(workflows=["flow"], steps=["flow.branch"]),
                    depends_on=["base"],
                ),
            },
            agents_by_name={"red": _agent("Scan", "Exploit")},
            entity_names={"blue"},
            metrics_by_name={"m1": object()},
            goals_by_name={"g1": object()},
            workflows_by_name={"flow": _workflow("start", "branch")},
            targetable_name_index={"nodes.web": {"nodes.web"}},
        )

        assert not analysis.has_issues

        actor_names = {ref.canonical_name for ref in analysis.references_of_kind(ObjectiveReferenceKind.ACTOR)}
        assert actor_names == {"entities.blue", "red"}
        assert {ref.canonical_name for ref in analysis.references_of_kind(ObjectiveReferenceKind.TARGET)} == {
            "nodes.web"
        }
        assert {ref.canonical_name for ref in analysis.references_of_kind(ObjectiveReferenceKind.SUCCESS)} == {
            "metric.m1",
            "goal.g1",
        }
        success_kinds = {
            ref.canonical_name: ref.success_resource_kind
            for ref in analysis.references_of_kind(ObjectiveReferenceKind.SUCCESS)
        }
        assert success_kinds["metric.m1"] == AssessmentResourceKind.METRIC
        assert success_kinds["goal.g1"] == AssessmentResourceKind.GOAL
        assert {ref.canonical_name for ref in analysis.references_of_kind(ObjectiveReferenceKind.WINDOW)} == {
            "flow",
            "flow.branch",
        }
        assert {ref.canonical_name for ref in analysis.references_of_kind(ObjectiveReferenceKind.DEPENDENCY)} == {
            "objective.base"
        }

        for ref in analysis.references_of_kind(ObjectiveReferenceKind.SUCCESS):
            assert ref.dependency_roles == OBJECTIVE_SUCCESS_DEPENDENCY_ROLES
        for ref in analysis.references_of_kind(ObjectiveReferenceKind.DEPENDENCY):
            assert ref.dependency_roles == OBJECTIVE_DEPENDENCY_DEPENDENCY_ROLES
        for ref in analysis.references_of_kind(ObjectiveReferenceKind.WINDOW):
            assert ObjectiveDependencyRole.REFRESH in ref.dependency_roles
            assert ObjectiveDependencyRole.ORDERING not in ref.dependency_roles
        for kind in (ObjectiveReferenceKind.ACTOR, ObjectiveReferenceKind.TARGET):
            for ref in analysis.references_of_kind(kind):
                assert ref.dependency_roles == ()

        assert analysis.dependencies_for("base").ordering_names == ("metric.m1",)
        assert analysis.dependencies_for("base").refresh_names == ("metric.m1",)
        assert analysis.dependencies_for("follow").ordering_names == ("goal.g1", "objective.base")
        assert analysis.dependencies_for("follow").refresh_names == ("goal.g1", "objective.base", "workflow.flow")
        assert "follow" in analysis.window_analyses

    def test_undeclared_actor_references_are_reported(self) -> None:
        analysis = _analyze(
            {
                "a": _objective(agent="ghost"),
                "b": _objective(entity="ghost-team"),
            },
            agents_by_name={"red": _agent()},
            entity_names={"blue"},
            conditions_by_name={"health": object()},
        )
        codes = {issue.code for issue in analysis.issues}
        assert "objective.actor-agent-undeclared" in codes
        assert "objective.actor-entity-undeclared" in codes

    def test_agent_action_must_be_declared(self) -> None:
        analysis = _analyze(
            {"a": _objective(agent="red", actions=["Persist"])},
            agents_by_name={"red": _agent("Scan")},
            conditions_by_name={"health": object()},
        )
        issue = analysis.issues_of_code("objective.action-not-declared")[0]
        assert issue.ref == "Persist"
        assert issue.actor_name == "red"

    def test_unresolvable_target_is_reported(self) -> None:
        analysis = _analyze(
            {"a": _objective(entity="blue", targets=["ghost"])},
            entity_names={"blue"},
            conditions_by_name={"health": object()},
        )
        assert analysis.issues_of_code("objective.target-unresolvable")[0].ref == "ghost"

    def test_ambiguous_target_is_reported_with_sorted_candidates(self) -> None:
        analysis = _analyze(
            {"a": _objective(entity="blue", targets=["web"])},
            entity_names={"blue"},
            conditions_by_name={"health": object()},
            targetable_name_index={"web": {"nodes.web", "features.web"}},
        )
        issue = analysis.issues_of_code("objective.target-ambiguous")[0]
        assert issue.ref == "web"
        assert issue.candidates == ("features.web", "nodes.web")

    def test_undeclared_success_references_are_reported_per_kind(self) -> None:
        analysis = _analyze(
            {
                "a": _objective(
                    entity="blue",
                    success=_success(
                        conditions=["c?"],
                        metrics=["m?"],
                        evaluations=["e?"],
                        tlos=["t?"],
                        goals=["g?"],
                    ),
                )
            },
            entity_names={"blue"},
        )
        codes = {issue.code for issue in analysis.issues}
        assert {
            "objective.success-condition-undeclared",
            "objective.success-metric-undeclared",
            "objective.success-evaluation-undeclared",
            "objective.success-tlo-undeclared",
            "objective.success-goal-undeclared",
        } <= codes

    def test_window_issues_are_resurfaced_under_objective_codes(self) -> None:
        analysis = _analyze(
            {
                "a": _objective(
                    entity="blue",
                    success=_success(conditions=["health"]),
                    window=_window(scripts=["s1"], events=["evt"]),
                )
            },
            entity_names={"blue"},
            conditions_by_name={"health": object()},
            scripts_by_name={"s1": SimpleNamespace(events={"kickoff": 1})},
            events_by_name={"evt": SimpleNamespace()},
        )
        assert analysis.issues_of_code("objective.window.event-outside-window-scripts")

    def test_undeclared_dependency_is_reported(self) -> None:
        analysis = _analyze(
            {"a": _objective(entity="blue", depends_on=["ghost"])},
            entity_names={"blue"},
            conditions_by_name={"health": object()},
        )
        assert analysis.issues_of_code("objective.dependency-undeclared")[0].ref == "ghost"

    def test_dependency_cycle_is_reported_once_globally(self) -> None:
        analysis = _analyze(
            {
                "a": _objective(entity="blue", depends_on=["b"]),
                "b": _objective(entity="blue", depends_on=["a"]),
            },
            entity_names={"blue"},
            conditions_by_name={"health": object()},
        )
        cycle_issues = analysis.issues_of_code("objective.dependency-cycle")
        assert len(cycle_issues) == 1
        assert cycle_issues[0].objective_name == ""

    def test_unresolved_variable_references_are_skipped(self) -> None:
        analysis = _analyze(
            {
                "a": _objective(
                    agent="${actor}",
                    actions=["${act}"],
                    targets=["${tgt}"],
                    success=_success(metrics=["${m}"]),
                    window=_window(stories=["${story}"]),
                    depends_on=["${dep}"],
                )
            },
            is_unresolved=_is_var,
        )
        assert not analysis.has_issues
        assert analysis.references == ()

    def test_no_objectives_is_empty_analysis(self) -> None:
        analysis = _analyze({})
        assert analysis.references == ()
        assert analysis.issues == ()
        assert analysis.dependencies == ()


class TestObjectiveDependencyPartition:
    def test_partition_orders_primary_then_refreshes_window(self) -> None:
        ordering, refresh = partition_objective_dependencies(
            success_refs=["a", "b"],
            dependency_refs=["c"],
            window_refresh_refs=["w1", "w2"],
        )
        assert ordering == ("a", "b", "c")
        assert refresh == ("a", "b", "c", "w1", "w2")

    def test_partition_dedupes_across_categories(self) -> None:
        ordering, refresh = partition_objective_dependencies(
            success_refs=["a", "a"],
            dependency_refs=["a", "b"],
            window_refresh_refs=["b", "w"],
        )
        assert ordering == ("a", "b")
        assert refresh == ("a", "b", "w")

    def test_partition_handles_empty_inputs(self) -> None:
        assert partition_objective_dependencies(success_refs=[], dependency_refs=[], window_refresh_refs=[]) == ((), ())

    def test_role_constants_are_sane(self) -> None:
        assert ObjectiveDependencyRole.ORDERING in OBJECTIVE_SUCCESS_DEPENDENCY_ROLES
        assert ObjectiveDependencyRole.REFRESH in OBJECTIVE_SUCCESS_DEPENDENCY_ROLES
        assert ObjectiveDependencyRole.ORDERING in OBJECTIVE_DEPENDENCY_DEPENDENCY_ROLES
        assert ObjectiveDependencyRole.REFRESH in OBJECTIVE_DEPENDENCY_DEPENDENCY_ROLES
        assert OBJECTIVE_WINDOW_DEPENDENCY_ROLES == (ObjectiveDependencyRole.REFRESH,)
        # Actor and target references are normalized for fail-closed validation
        # but the compiler does not propagate ordering or refresh through them.
        assert OBJECTIVE_ACTOR_DEPENDENCY_ROLES == ()
        assert OBJECTIVE_TARGET_DEPENDENCY_ROLES == ()

    def test_partition_emits_each_category_under_default_roles(self) -> None:
        # Default roles (success and depends_on both ORDERING+REFRESH; window
        # REFRESH only) place the success and dependency entries in both tuples
        # and the window entry in refresh only.
        ordering, refresh = partition_objective_dependencies(
            success_refs=["s"],
            dependency_refs=["d"],
            window_refresh_refs=["w"],
        )
        assert ordering == ("s", "d")
        assert refresh == ("s", "d", "w")

    def test_partition_reads_each_categorys_own_role_constant(self, monkeypatch) -> None:
        # The cycle-1 bug merged success+depends_on into one list and gated
        # both through OBJECTIVE_SUCCESS_DEPENDENCY_ROLES, so a hypothetical
        # change to the dependency-role constant alone never reached the
        # runtime tuples. Toggle just OBJECTIVE_DEPENDENCY_DEPENDENCY_ROLES to
        # refresh-only and assert the partition output reflects exactly that
        # difference — proving each category is keyed independently.
        import aces_sdl.semantics.objective_semantics as os_module

        monkeypatch.setattr(
            os_module,
            "OBJECTIVE_DEPENDENCY_DEPENDENCY_ROLES",
            (ObjectiveDependencyRole.REFRESH,),
        )
        ordering, refresh = partition_objective_dependencies(
            success_refs=["s"],
            dependency_refs=["d"],
            window_refresh_refs=["w"],
        )
        # success kept ORDERING; deps lost it; window unchanged.
        assert ordering == ("s",)
        assert refresh == ("s", "d", "w")

    @given(st.lists(st.sampled_from(["a", "b", "c", "d"]), max_size=16))
    def test_partition_ordering_is_dedup_stable(self, refs: list[str]) -> None:
        ordering, _refresh = partition_objective_dependencies(
            success_refs=refs,
            dependency_refs=[],
            window_refresh_refs=[],
        )
        assert ordering == tuple(dict.fromkeys(refs))
