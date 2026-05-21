"""SDL-to-runtime compiler."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from aces_backend_protocols.capabilities import (
    WorkflowFeature,
    WorkflowStatePredicateFeature,
)
from aces_contracts.versions import WORKFLOW_STATE_SCHEMA_VERSION
from aces_sdl.entities import flatten_entities
from aces_sdl.instantiate import instantiate_scenario
from aces_sdl.nodes import NodeType
from aces_sdl.orchestration import WorkflowStepType
from aces_sdl.participant_outcome_semantics import (
    OutcomeInterpretationSourceLayer,
    OutcomeInterpretationTargetLayer,
)
from aces_sdl.scenario import InstantiatedScenario, Scenario
from aces_sdl.semantics.assessment import partition_assessment_dependencies
from aces_sdl.semantics.objective_semantics import (
    OBJECTIVE_WINDOW_DEPENDENCY_ROLES,
    partition_objective_dependencies,
)
from aces_sdl.semantics.objectives import analyze_objective_window
from aces_sdl.semantics.workflow import (
    workflow_step_semantic_contract,
)

from .models import (
    AccountPlacement,
    ConditionBinding,
    ContentPlacement,
    Diagnostic,
    EvaluationExecutionContract,
    EvaluationResultContract,
    EvaluationRuntime,
    EventRuntime,
    FeatureBinding,
    GoalRuntime,
    InjectBinding,
    InjectRuntime,
    MetricRuntime,
    NetworkRuntime,
    NodeRuntime,
    ObjectiveRuntime,
    ObjectiveWindowReferenceRuntime,
    ParticipantActionContractRuntime,
    ParticipantBehaviorRuntime,
    ParticipantObservationBoundaryRuntime,
    ParticipantOutcomeInterpretationRuleRuntime,
    RuntimeModel,
    RuntimeTemplate,
    ScriptRuntime,
    StoryRuntime,
    TLORuntime,
    WorkflowExecutionContract,
    WorkflowPredicateRuntime,
    WorkflowResultContract,
    WorkflowRuntime,
    WorkflowStepOutcome,
    WorkflowStepRuntime,
    WorkflowStepStatePredicateRuntime,
    WorkflowSwitchCaseRuntime,
)


def _dump(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", by_alias=True)
    if isinstance(model, dict):
        return dict(model)
    return {}


def _address(*parts: str) -> str:
    return ".".join(part for part in parts if part)


def _dedupe(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def _dedupe_by_value(items: list[Any]) -> tuple[Any, ...]:
    ordered: dict[str, Any] = {}
    for item in items:
        key = getattr(item, "value", repr(item))
        ordered.setdefault(key, item)
    return tuple(item for _, item in sorted(ordered.items()))


_VISIBLE_VIEW_DISPOSITIONS = frozenset({"observable", "discovered", "inferred", "disclosed", "deceptive"})


def _initial_view_relation(*, view_rules: list[Any]) -> dict[str, str]:
    view_relation: dict[str, str] = {}
    for rule in view_rules:
        if not isinstance(rule, dict):
            continue
        information_ref = rule.get("information_ref")
        disposition = rule.get("disposition")
        if not information_ref or not disposition:
            continue
        ref = str(information_ref)
        view_relation[ref] = str(disposition)
    return view_relation


def _view_relation_refs(view_relation: dict[str, str], dispositions: set[str] | frozenset[str]) -> tuple[str, ...]:
    return tuple(ref for ref, disposition in sorted(view_relation.items()) if disposition in dispositions)


def _view_relation_snapshot(
    *,
    transition_id: str,
    effective_from: str,
    effective_order: int,
    view_relation: dict[str, str],
    transition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = {
        "transition_id": transition_id,
        "effective_from": effective_from,
        "effective_order": effective_order,
        "view_relation": dict(sorted(view_relation.items())),
        "visible_refs": _view_relation_refs(view_relation, _VISIBLE_VIEW_DISPOSITIONS),
        "hidden_refs": _view_relation_refs(view_relation, {"hidden"}),
        "evidence_only_refs": _view_relation_refs(view_relation, {"evidence_only"}),
        "disclosed_refs": _view_relation_refs(view_relation, {"disclosed"}),
        "discovered_refs": _view_relation_refs(view_relation, {"discovered"}),
        "inferred_refs": _view_relation_refs(view_relation, {"inferred"}),
        "concealed_refs": _view_relation_refs(view_relation, {"concealed"}),
        "deceptive_refs": _view_relation_refs(view_relation, {"deceptive"}),
    }
    if transition is not None:
        snapshot.update(
            {
                "transition_kind": str(transition.get("transition_kind") or ""),
                "information_ref": str(transition.get("information_ref") or ""),
                "history_event_type": str(transition.get("history_event_type") or ""),
                "action_instance_id": (
                    str(transition.get("action_instance_id"))
                    if transition.get("action_instance_id") is not None
                    else ""
                ),
            }
        )
    return snapshot


def _ordered_view_transitions(view_transitions: list[Any]) -> tuple[dict[str, Any], ...]:
    return tuple(
        sorted(
            (dict(transition) for transition in view_transitions if isinstance(transition, dict)),
            key=lambda transition: int(transition.get("effective_order", 0)),
        )
    )


def _compile_view_relation_timeline(
    *,
    view_rules: list[Any],
    view_transitions: list[Any],
) -> tuple[dict[str, Any], ...]:
    view_relation = _initial_view_relation(view_rules=view_rules)
    timeline: list[dict[str, Any]] = [
        _view_relation_snapshot(
            transition_id="initial",
            effective_from="initial",
            effective_order=-1,
            view_relation=view_relation,
        )
    ]
    for transition in _ordered_view_transitions(view_transitions):
        information_ref = transition.get("information_ref")
        to_disposition = transition.get("to_disposition")
        if not information_ref or not to_disposition:
            continue
        view_relation[str(information_ref)] = str(to_disposition)
        timeline.append(
            _view_relation_snapshot(
                transition_id=str(transition.get("transition_id") or ""),
                effective_from=str(transition.get("effective_from") or ""),
                effective_order=int(transition.get("effective_order", 0)),
                view_relation=view_relation,
                transition=transition,
            )
        )
    return tuple(timeline)


def _template_address(kind: str, name: str) -> str:
    return _address("template", kind, name)


def _network_address(name: str) -> str:
    return _address("provision", "network", name)


def _node_address(name: str) -> str:
    return _address("provision", "node", name)


def _feature_binding_address(node_name: str, feature_name: str) -> str:
    return _address("provision", "feature", node_name, feature_name)


def _content_address(name: str) -> str:
    return _address("provision", "content", name)


def _account_address(name: str) -> str:
    return _address("provision", "account", name)


def _action_contract_address(name: str) -> str:
    return _address("participant", "action-contract", name)


def _observation_boundary_address(name: str) -> str:
    return _address("participant", "observation-boundary", name)


def _outcome_interpretation_rule_address(name: str) -> str:
    return _address("participant", "outcome-interpretation-rule", name)


def _participant_behavior_address(name: str) -> str:
    return _address("participant", "behavior", name)


def _condition_binding_address(node_name: str, condition_name: str) -> str:
    return _address("evaluation", "condition", node_name, condition_name)


def _inject_address(name: str) -> str:
    return _address("orchestration", "inject", name)


def _inject_binding_address(node_name: str, inject_name: str) -> str:
    return _address("orchestration", "inject-binding", node_name, inject_name)


def _event_address(name: str) -> str:
    return _address("orchestration", "event", name)


def _script_address(name: str) -> str:
    return _address("orchestration", "script", name)


def _story_address(name: str) -> str:
    return _address("orchestration", "story", name)


def _workflow_address(name: str) -> str:
    return _address("orchestration", "workflow", name)


def _metric_address(name: str) -> str:
    return _address("evaluation", "metric", name)


def _evaluation_address(name: str) -> str:
    return _address("evaluation", "evaluation", name)


def _tlo_address(name: str) -> str:
    return _address("evaluation", "tlo", name)


def _goal_address(name: str) -> str:
    return _address("evaluation", "goal", name)


def _objective_address(name: str) -> str:
    return _address("evaluation", "objective", name)


def _resource_address_for_node(scenario: Scenario, node_name: str) -> str:
    node = scenario.nodes.get(node_name)
    if node is not None and node.type == NodeType.SWITCH:
        return _network_address(node_name)
    return _node_address(node_name)


def _evaluation_contracts(
    resource_type: str,
    spec: dict[str, Any] | None = None,
) -> tuple[EvaluationResultContract, EvaluationExecutionContract]:
    payload = spec or {}
    if resource_type == "metric":
        max_score_raw = payload.get("max-score", payload.get("max_score"))
        fixed_max_score = (
            max_score_raw if isinstance(max_score_raw, int) and not isinstance(max_score_raw, bool) else None
        )
        return (
            EvaluationResultContract(
                resource_type=resource_type,
                supports_score=True,
                fixed_max_score=fixed_max_score,
            ),
            EvaluationExecutionContract(resource_type=resource_type),
        )
    if resource_type in {
        "condition-binding",
        "evaluation",
        "tlo",
        "goal",
        "objective",
    }:
        return (
            EvaluationResultContract(
                resource_type=resource_type,
                supports_passed=True,
            ),
            EvaluationExecutionContract(resource_type=resource_type),
        )
    return (
        EvaluationResultContract(resource_type=resource_type),
        EvaluationExecutionContract(resource_type=resource_type),
    )


def _resolve_binding_ref(
    bindings: dict[str, Any],
    *,
    ref_name: str,
    owner_address: str,
    domain: str,
    code_prefix: str,
    binding_attr: str,
    binding_label: str,
) -> tuple[tuple[str, ...], list[Diagnostic]]:
    matches = tuple(
        sorted(address for address, binding in bindings.items() if getattr(binding, binding_attr) == ref_name)
    )
    if len(matches) == 1:
        return matches, []

    if not matches:
        return (), [
            Diagnostic(
                code=f"{code_prefix}-unbound",
                domain=domain,
                address=owner_address,
                message=(f"Reference '{ref_name}' does not resolve to a bound {binding_label}."),
            )
        ]

    joined = ", ".join(matches)
    return (), [
        Diagnostic(
            code=f"{code_prefix}-ambiguous",
            domain=domain,
            address=owner_address,
            message=(f"Reference '{ref_name}' resolves to multiple bound {binding_label}s: {joined}."),
        )
    ]


def _resolve_binding_refs(
    bindings: dict[str, Any],
    *,
    ref_names: list[str],
    owner_address: str,
    domain: str,
    code_prefix: str,
    binding_attr: str,
    binding_label: str,
) -> tuple[tuple[str, ...], list[Diagnostic]]:
    resolved: list[str] = []
    diagnostics: list[Diagnostic] = []
    for ref_name in dict.fromkeys(ref_names):
        addresses, ref_diagnostics = _resolve_binding_ref(
            bindings,
            ref_name=ref_name,
            owner_address=owner_address,
            domain=domain,
            code_prefix=code_prefix,
            binding_attr=binding_attr,
            binding_label=binding_label,
        )
        resolved.extend(addresses)
        diagnostics.extend(ref_diagnostics)
    return _dedupe(resolved), diagnostics


def _resolve_resource_refs(
    resources: dict[str, Any],
    *,
    ref_names: list[str],
    owner_address: str,
    domain: str,
    code_prefix: str,
    resource_label: str,
) -> tuple[tuple[str, ...], list[Diagnostic]]:
    resolved: list[str] = []
    diagnostics: list[Diagnostic] = []
    for ref_name in dict.fromkeys(ref_names):
        matched_address = next(
            (address for address, resource in resources.items() if resource.name == ref_name),
            None,
        )
        if matched_address is None:
            diagnostics.append(
                Diagnostic(
                    code=f"{code_prefix}-unbound",
                    domain=domain,
                    address=owner_address,
                    message=(f"Reference '{ref_name}' does not resolve to a defined {resource_label}."),
                )
            )
            continue
        resolved.append(matched_address)
    return _dedupe(resolved), diagnostics


def _resolve_named_refs(
    *,
    ref_names: list[str],
    available_names: set[str],
    address_builder: Callable[[str], str],
    owner_address: str,
    domain: str,
    code_prefix: str,
    resource_label: str,
) -> tuple[tuple[str, ...], list[Diagnostic]]:
    resolved: list[str] = []
    diagnostics: list[Diagnostic] = []
    for ref_name in dict.fromkeys(ref_names):
        if ref_name not in available_names:
            diagnostics.append(
                Diagnostic(
                    code=f"{code_prefix}-unbound",
                    domain=domain,
                    address=owner_address,
                    message=(f"Reference '{ref_name}' does not resolve to a defined {resource_label}."),
                )
            )
            continue
        resolved.append(address_builder(ref_name))
    return _dedupe(resolved), diagnostics


def _resolve_node_ref(
    scenario: Scenario,
    *,
    ref_name: str,
    owner_address: str,
    domain: str,
    code_prefix: str,
    node_label: str,
    require_vm: bool = False,
    require_switch: bool = False,
) -> tuple[str | None, list[Diagnostic]]:
    node = scenario.nodes.get(ref_name)
    if node is None:
        return None, [
            Diagnostic(
                code=f"{code_prefix}-unbound",
                domain=domain,
                address=owner_address,
                message=(f"Reference '{ref_name}' does not resolve to a defined {node_label}."),
            )
        ]

    if require_vm and node.type != NodeType.VM:
        return None, [
            Diagnostic(
                code=f"{code_prefix}-invalid-type",
                domain=domain,
                address=owner_address,
                message=(f"Reference '{ref_name}' must resolve to a VM node for {node_label}."),
            )
        ]

    if require_switch and node.type != NodeType.SWITCH:
        return None, [
            Diagnostic(
                code=f"{code_prefix}-invalid-type",
                domain=domain,
                address=owner_address,
                message=(f"Reference '{ref_name}' must resolve to a switch/network node for {node_label}."),
            )
        ]

    return _resource_address_for_node(scenario, ref_name), []


@dataclass(frozen=True)
class _ObjectiveWindowCompilation:
    story_addresses: tuple[str, ...] = ()
    script_addresses: tuple[str, ...] = ()
    event_addresses: tuple[str, ...] = ()
    workflow_addresses: tuple[str, ...] = ()
    step_refs: tuple[str, ...] = ()
    step_workflow_addresses: tuple[str, ...] = ()
    references: tuple[ObjectiveWindowReferenceRuntime, ...] = ()


@dataclass(frozen=True)
class _WorkflowPredicateCompilation:
    predicate: WorkflowPredicateRuntime
    condition_addresses: tuple[str, ...]
    predicate_addresses: tuple[str, ...]
    objective_addresses: tuple[str, ...]
    step_state_predicates: tuple[WorkflowStepStatePredicateRuntime, ...]


@dataclass
class _WorkflowCompilationState:
    join_owners: dict[str, str]
    control_steps: dict[str, WorkflowStepRuntime] = field(default_factory=dict)
    control_edges: dict[str, tuple[str, ...]] = field(default_factory=dict)
    referenced_objectives: list[str] = field(default_factory=list)
    step_condition_addresses: dict[str, tuple[str, ...]] = field(default_factory=dict)
    step_predicate_addresses: dict[str, tuple[str, ...]] = field(default_factory=dict)
    required_features: list[WorkflowFeature] = field(default_factory=list)
    required_state_predicate_features: list[WorkflowStatePredicateFeature] = field(default_factory=list)
    compensation_targets: dict[str, str] = field(default_factory=dict)


_OBJECTIVE_WINDOW_ISSUE_DIAGNOSTICS = {
    "story-unbound": ("evaluation.story-ref-unbound", "Reference '{ref}' does not resolve to a defined story."),
    "script-unbound": ("evaluation.script-ref-unbound", "Reference '{ref}' does not resolve to a defined script."),
    "script-outside-window-stories": (
        "evaluation.script-ref-outside-window-stories",
        "Reference '{ref}' is not included by the objective window's referenced stories.",
    ),
    "event-unbound": ("evaluation.event-ref-unbound", "Reference '{ref}' does not resolve to a defined event."),
    "event-outside-window-scripts": (
        "evaluation.event-ref-outside-window-scripts",
        "Reference '{ref}' is not included by the objective window's referenced scripts.",
    ),
    "workflow-unbound": (
        "evaluation.workflow-ref-unbound",
        "Reference '{ref}' does not resolve to a defined workflow.",
    ),
    "step-requires-workflow-window": (
        "evaluation.workflow-step-ref-window-missing-workflow",
        "Workflow step references require at least one referenced workflow.",
    ),
    "step-invalid-format": (
        "evaluation.workflow-step-ref-invalid-format",
        "Reference '{ref}' must use '<workflow>.<step>' syntax.",
    ),
    "step-workflow-unbound": (
        "evaluation.workflow-step-ref-workflow-unbound",
        "Reference '{ref}' does not resolve to a defined workflow.",
    ),
    "step-workflow-outside-window": (
        "evaluation.workflow-step-ref-workflow-outside-window",
        "Reference '{ref}' is not part of the objective window's referenced workflows.",
    ),
    "step-unbound": (
        "evaluation.workflow-step-ref-step-unbound",
        "Reference '{ref}' does not resolve to a defined workflow step.",
    ),
}

_WORKFLOW_STEP_TYPE_FEATURES = {
    WorkflowStepType.DECISION: WorkflowFeature.DECISION,
    WorkflowStepType.SWITCH: WorkflowFeature.SWITCH,
    WorkflowStepType.PARALLEL: WorkflowFeature.PARALLEL_BARRIER,
    WorkflowStepType.RETRY: WorkflowFeature.RETRY,
    WorkflowStepType.CALL: WorkflowFeature.CALL,
}


def _compile_templates(
    scenario: InstantiatedScenario,
) -> tuple[
    dict[str, RuntimeTemplate],
    dict[str, RuntimeTemplate],
    dict[str, RuntimeTemplate],
    dict[str, RuntimeTemplate],
]:
    feature_templates = {
        name: RuntimeTemplate(address=_template_address("feature", name), name=name, spec=_dump(template))
        for name, template in scenario.features.items()
    }
    condition_templates = {
        name: RuntimeTemplate(address=_template_address("condition", name), name=name, spec=_dump(template))
        for name, template in scenario.conditions.items()
    }
    inject_templates = {
        name: RuntimeTemplate(address=_template_address("inject", name), name=name, spec=_dump(template))
        for name, template in scenario.injects.items()
    }
    vulnerability_templates = {
        name: RuntimeTemplate(address=_template_address("vulnerability", name), name=name, spec=_dump(template))
        for name, template in scenario.vulnerabilities.items()
    }
    return feature_templates, condition_templates, inject_templates, vulnerability_templates


def _metadata_specs(
    scenario: InstantiatedScenario,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    entity_specs = {name: _dump(entity) for name, entity in flatten_entities(scenario.entities).items()}
    agent_specs = {name: _dump(agent) for name, agent in scenario.agents.items()}
    relationship_specs = {name: _dump(relationship) for name, relationship in scenario.relationships.items()}
    variable_specs = {name: _dump(variable) for name, variable in scenario.variables.items()}
    for prefixed_name, spec in scenario.module_variable_specs.items():
        if prefixed_name in variable_specs:
            raise ValueError(
                "Outer scenario variable "
                f"{prefixed_name!r} collides with a module-import "
                "provenance entry generated under the reserved private "
                "namespace; rename the outer variable so it does not "
                "shadow the imported domain."
            )
        variable_specs[prefixed_name] = spec
    return entity_specs, agent_specs, relationship_specs, variable_specs


def _node_dependency_addresses(
    scenario: InstantiatedScenario,
    *,
    node_name: str,
    ref_names: list[str],
    code_prefix: str,
    node_label: str,
    diagnostics: list[Diagnostic],
    require_switch: bool = False,
) -> list[str]:
    addresses: list[str] = []
    for ref_name in ref_names:
        dep_address, dep_diagnostics = _resolve_node_ref(
            scenario,
            ref_name=ref_name,
            owner_address=_resource_address_for_node(scenario, node_name),
            domain="provisioning",
            code_prefix=code_prefix,
            node_label=node_label,
            require_switch=require_switch,
        )
        diagnostics.extend(dep_diagnostics)
        if dep_address is not None:
            addresses.append(dep_address)
    return addresses


def _compile_node_runtimes(
    scenario: InstantiatedScenario,
    diagnostics: list[Diagnostic],
) -> tuple[dict[str, NetworkRuntime], dict[str, NodeRuntime]]:
    networks: dict[str, NetworkRuntime] = {}
    node_deployments: dict[str, NodeRuntime] = {}
    for node_name, node in scenario.nodes.items():
        node_spec = _dump(node)
        infra = scenario.infrastructure.get(node_name)
        infra_spec = _dump(infra) if infra is not None else {}
        dependency_addresses: list[str] = []
        if infra is not None:
            dependency_addresses.extend(
                _node_dependency_addresses(
                    scenario,
                    node_name=node_name,
                    ref_names=list(infra.dependencies),
                    code_prefix="provisioning.infrastructure-dependency-ref",
                    node_label="infrastructure dependency",
                    diagnostics=diagnostics,
                )
            )
            dependency_addresses.extend(
                _node_dependency_addresses(
                    scenario,
                    node_name=node_name,
                    ref_names=list(infra.links),
                    code_prefix="provisioning.infrastructure-link-ref",
                    node_label="infrastructure link",
                    diagnostics=diagnostics,
                    require_switch=True,
                )
            )
        _record_node_runtime(
            node_name=node_name,
            node_type=node.type,
            node_spec=node_spec,
            infra_spec=infra_spec,
            dependency_addresses=dependency_addresses,
            networks=networks,
            node_deployments=node_deployments,
        )
    return networks, node_deployments


def _record_node_runtime(
    *,
    node_name: str,
    node_type: NodeType,
    node_spec: dict[str, Any],
    infra_spec: dict[str, Any],
    dependency_addresses: list[str],
    networks: dict[str, NetworkRuntime],
    node_deployments: dict[str, NodeRuntime],
) -> None:
    spec = {"node": node_spec, "infrastructure": infra_spec}
    if node_type == NodeType.SWITCH:
        networks[_network_address(node_name)] = NetworkRuntime(
            address=_network_address(node_name),
            name=node_name,
            node_name=node_name,
            spec=spec,
            ordering_dependencies=_dedupe(dependency_addresses),
            refresh_dependencies=_dedupe(dependency_addresses),
        )
        return
    node_deployments[_node_address(node_name)] = NodeRuntime(
        address=_node_address(node_name),
        name=node_name,
        node_name=node_name,
        node_type=node_spec.get("type", ""),
        os_family=node_spec.get("os", "") or "",
        count=infra_spec.get("count"),
        spec=spec,
        ordering_dependencies=_dedupe(dependency_addresses),
        refresh_dependencies=_dedupe(dependency_addresses),
    )


def _feature_dependency_addresses(
    node: Any,
    feature: Any,
    *,
    feature_name: str,
    node_name: str,
    address: str,
    diagnostics: list[Diagnostic],
) -> list[str]:
    dep_addresses = [_node_address(node_name)]
    for dep_name in feature.dependencies:
        if dep_name in node.features:
            dep_addresses.append(_feature_binding_address(node_name, dep_name))
            continue
        diagnostics.append(
            Diagnostic(
                code="provisioning.feature-dependency-binding-missing",
                domain="provisioning",
                address=address,
                message=(
                    f"Feature binding '{feature_name}' on node '{node_name}' "
                    f"requires feature dependency '{dep_name}' to also be bound on the same node."
                ),
            )
        )
    return dep_addresses


def _compile_feature_bindings(
    scenario: InstantiatedScenario,
    feature_templates: dict[str, RuntimeTemplate],
    diagnostics: list[Diagnostic],
) -> dict[str, FeatureBinding]:
    feature_bindings: dict[str, FeatureBinding] = {}
    for node_name, node in scenario.nodes.items():
        if node.type != NodeType.VM:
            continue
        node_addr = _node_address(node_name)
        for feature_name, role_name in node.features.items():
            template = feature_templates.get(feature_name)
            feature = scenario.features.get(feature_name)
            if template is None or feature is None:
                diagnostics.append(
                    Diagnostic(
                        code="provisioning.feature-template-ref-unbound",
                        domain="provisioning",
                        address=node_addr,
                        message=(
                            f"Feature binding '{feature_name}' on node '{node_name}' "
                            "does not resolve to a declared feature template."
                        ),
                    )
                )
                continue
            address = _feature_binding_address(node_name, feature_name)
            dep_addresses = _feature_dependency_addresses(
                node,
                feature,
                feature_name=feature_name,
                node_name=node_name,
                address=address,
                diagnostics=diagnostics,
            )
            feature_bindings[address] = FeatureBinding(
                address=address,
                name=feature_name,
                node_name=node_name,
                node_address=node_addr,
                feature_name=feature_name,
                template_address=template.address,
                role_name=role_name,
                ordering_dependencies=_dedupe(dep_addresses),
                refresh_dependencies=_dedupe(dep_addresses),
                spec={"binding": {"node": node_name, "role": role_name}, "template": template.spec},
            )
    return feature_bindings


def _compile_condition_bindings(
    scenario: InstantiatedScenario,
    condition_templates: dict[str, RuntimeTemplate],
    diagnostics: list[Diagnostic],
) -> dict[str, ConditionBinding]:
    condition_bindings: dict[str, ConditionBinding] = {}
    for node_name, node in scenario.nodes.items():
        if node.type != NodeType.VM:
            continue
        node_addr = _node_address(node_name)
        for condition_name, role_name in node.conditions.items():
            template = condition_templates.get(condition_name)
            if template is None:
                diagnostics.append(
                    Diagnostic(
                        code="evaluation.condition-template-ref-unbound",
                        domain="evaluation",
                        address=node_addr,
                        message=(
                            f"Condition binding '{condition_name}' on node '{node_name}' "
                            "does not resolve to a declared condition template."
                        ),
                    )
                )
                continue
            address = _condition_binding_address(node_name, condition_name)
            result_contract, execution_contract = _evaluation_contracts("condition-binding")
            condition_bindings[address] = ConditionBinding(
                address=address,
                name=condition_name,
                node_name=node_name,
                node_address=node_addr,
                condition_name=condition_name,
                template_address=template.address,
                role_name=role_name,
                refresh_dependencies=(node_addr,),
                spec={"binding": {"node": node_name, "role": role_name}, "template": template.spec},
                result_contract=result_contract,
                execution_contract=execution_contract,
            )
    return condition_bindings


def _compile_inject_runtimes(inject_templates: dict[str, RuntimeTemplate]) -> dict[str, InjectRuntime]:
    return {
        _inject_address(name): InjectRuntime(address=_inject_address(name), name=name, spec=template.spec)
        for name, template in inject_templates.items()
    }


def _compile_inject_bindings(
    scenario: InstantiatedScenario,
    inject_templates: dict[str, RuntimeTemplate],
    diagnostics: list[Diagnostic],
) -> dict[str, InjectBinding]:
    inject_bindings: dict[str, InjectBinding] = {}
    for node_name, node in scenario.nodes.items():
        if node.type != NodeType.VM:
            continue
        node_addr = _node_address(node_name)
        for inject_name, role_name in node.injects.items():
            template = inject_templates.get(inject_name)
            if template is None:
                diagnostics.append(
                    Diagnostic(
                        code="orchestration.inject-template-ref-unbound",
                        domain="orchestration",
                        address=node_addr,
                        message=(
                            f"Inject binding '{inject_name}' on node '{node_name}' "
                            "does not resolve to a declared inject template."
                        ),
                    )
                )
                continue
            inject_address = _inject_address(inject_name)
            address = _inject_binding_address(node_name, inject_name)
            inject_bindings[address] = InjectBinding(
                address=address,
                name=inject_name,
                node_name=node_name,
                node_address=node_addr,
                inject_name=inject_name,
                template_address=template.address,
                role_name=role_name,
                ordering_dependencies=(inject_address,),
                refresh_dependencies=(node_addr, inject_address),
                spec={"binding": {"node": node_name, "role": role_name}, "inject_address": inject_address},
            )
    return inject_bindings


def _compile_content_placements(
    scenario: InstantiatedScenario,
    diagnostics: list[Diagnostic],
) -> dict[str, ContentPlacement]:
    content_placements: dict[str, ContentPlacement] = {}
    for name, content in scenario.content.items():
        address = _content_address(name)
        target_address, target_diagnostics = _resolve_node_ref(
            scenario,
            ref_name=content.target,
            owner_address=address,
            domain="provisioning",
            code_prefix="provisioning.content-target-ref",
            node_label="content target",
            require_vm=True,
        )
        diagnostics.extend(target_diagnostics)
        if target_address is None:
            continue
        content_placements[address] = ContentPlacement(
            address=address,
            name=name,
            content_name=name,
            target_node=content.target,
            target_address=target_address,
            ordering_dependencies=(target_address,),
            refresh_dependencies=(target_address,),
            spec=_dump(content),
        )
    return content_placements


def _compile_account_placements(
    scenario: InstantiatedScenario,
    diagnostics: list[Diagnostic],
) -> dict[str, AccountPlacement]:
    account_placements: dict[str, AccountPlacement] = {}
    for name, account in scenario.accounts.items():
        address = _account_address(name)
        target_address, target_diagnostics = _resolve_node_ref(
            scenario,
            ref_name=account.node,
            owner_address=address,
            domain="provisioning",
            code_prefix="provisioning.account-node-ref",
            node_label="account node",
            require_vm=True,
        )
        diagnostics.extend(target_diagnostics)
        if target_address is None:
            continue
        account_placements[address] = AccountPlacement(
            address=address,
            name=name,
            account_name=name,
            node_name=account.node,
            target_address=target_address,
            ordering_dependencies=(target_address,),
            refresh_dependencies=(target_address,),
            spec=_dump(account),
        )
    return account_placements


def _compile_action_contracts(scenario: InstantiatedScenario) -> dict[str, ParticipantActionContractRuntime]:
    action_contracts: dict[str, ParticipantActionContractRuntime] = {}
    for name, contract in scenario.action_contracts.items():
        contract_spec = _dump(contract)
        interactions = contract_spec.get("interactions", [])
        temporal_contracts = contract_spec.get("temporal_contracts", [])
        interaction_classes = _dedupe(
            [
                str(interaction.get("interaction_class", ""))
                for interaction in interactions
                if isinstance(interaction, dict) and interaction.get("interaction_class")
            ]
        )
        shared_state_refs = _dedupe(
            [
                str(ref)
                for interaction in interactions
                if isinstance(interaction, dict)
                for ref in interaction.get("shared_state_refs", [])
            ]
        )
        precondition_classes = _dedupe(
            [
                str(precondition.get("precondition_class", ""))
                for precondition in contract_spec.get("preconditions", [])
                if isinstance(precondition, dict) and precondition.get("precondition_class")
            ]
        )
        effect_classes = _dedupe(
            [
                str(effect.get("effect_class", ""))
                for effect in contract_spec.get("effects", [])
                if isinstance(effect, dict) and effect.get("effect_class")
            ]
        )
        failure_classes = _dedupe(str(failure_class) for failure_class in contract_spec.get("failure_classes", []))
        backend_failure_mappings = tuple(
            {
                "backend_error_code": str(mapping.get("backend_error_code", "")),
                "failure_class": str(mapping.get("failure_class", "")),
                "diagnostic": str(mapping.get("diagnostic", "")),
            }
            for mapping in contract_spec.get("backend_failure_mappings", [])
            if isinstance(mapping, dict)
        )
        temporal_contract_ids = _dedupe(
            [
                str(temporal_contract.get("temporal_id", ""))
                for temporal_contract in temporal_contracts
                if isinstance(temporal_contract, dict) and temporal_contract.get("temporal_id")
            ]
        )
        temporal_kinds = _dedupe(
            [
                str(temporal_contract.get("temporal_kind", ""))
                for temporal_contract in temporal_contracts
                if isinstance(temporal_contract, dict) and temporal_contract.get("temporal_kind")
            ]
        )
        time_domains = _dedupe(
            [
                str(temporal_contract.get("time_domain", ""))
                for temporal_contract in temporal_contracts
                if isinstance(temporal_contract, dict) and temporal_contract.get("time_domain")
            ]
        )
        clock_authorities = _dedupe(
            [
                str(temporal_contract.get("clock_authority", ""))
                for temporal_contract in temporal_contracts
                if isinstance(temporal_contract, dict) and temporal_contract.get("clock_authority")
            ]
        )
        backend_timing_disclosures = tuple(
            {
                "disclosure_id": str(disclosure.get("disclosure_id", "")),
                "disclosure_kind": str(disclosure.get("disclosure_kind", "")),
                "support_mode": str(disclosure.get("support_mode", "")),
                "description": str(disclosure.get("description", "")),
                "affected_temporal_ids": [
                    str(temporal_id) for temporal_id in disclosure.get("affected_temporal_ids", [])
                ],
                "limitations": [str(limitation) for limitation in disclosure.get("limitations", [])],
            }
            for disclosure in contract_spec.get("backend_timing_disclosures", [])
            if isinstance(disclosure, dict)
        )
        action_contracts[_action_contract_address(name)] = ParticipantActionContractRuntime(
            address=_action_contract_address(name),
            name=name,
            action_name=name,
            semantic_version=str(contract_spec.get("semantic_version", "")),
            lifecycle_state=str(contract_spec.get("lifecycle_state", "")),
            behavioral_granularity=str(contract_spec.get("behavioral_granularity", "")),
            precondition_classes=precondition_classes,
            effect_classes=effect_classes,
            failure_classes=failure_classes,
            backend_failure_mappings=backend_failure_mappings,
            interaction_classes=interaction_classes,
            shared_state_refs=shared_state_refs,
            temporal_contract_ids=temporal_contract_ids,
            temporal_kinds=temporal_kinds,
            time_domains=time_domains,
            clock_authorities=clock_authorities,
            backend_timing_disclosures=backend_timing_disclosures,
            spec=contract_spec,
        )
    return action_contracts


def _compile_observation_boundaries(scenario: InstantiatedScenario) -> dict[str, ParticipantObservationBoundaryRuntime]:
    observation_boundaries: dict[str, ParticipantObservationBoundaryRuntime] = {}
    for name, boundary in scenario.observation_boundaries.items():
        boundary_spec = _dump(boundary)
        view_rules = boundary_spec.get("view_rules", [])
        view_transitions = boundary_spec.get("view_transitions", [])
        initial_view_relation = _initial_view_relation(view_rules=view_rules)
        disclosed_refs = _view_relation_refs(initial_view_relation, {"disclosed"})
        evidence_only_refs = _view_relation_refs(initial_view_relation, {"evidence_only"})
        discovered_refs = _view_relation_refs(initial_view_relation, {"discovered"})
        inferred_refs = _view_relation_refs(initial_view_relation, {"inferred"})
        concealed_refs = _view_relation_refs(initial_view_relation, {"concealed"})
        deceptive_refs = _view_relation_refs(initial_view_relation, {"deceptive"})
        view_relation_timeline = _compile_view_relation_timeline(
            view_rules=view_rules,
            view_transitions=view_transitions,
        )
        ordered_view_transitions = _ordered_view_transitions(view_transitions)
        observation_boundaries[_observation_boundary_address(name)] = ParticipantObservationBoundaryRuntime(
            address=_observation_boundary_address(name),
            name=name,
            boundary_name=name,
            projection_basis=str(boundary_spec.get("projection_basis", "")),
            hidden_refs=tuple(str(ref) for ref in boundary_spec.get("hidden_refs", [])),
            observable_refs=tuple(str(ref) for ref in boundary_spec.get("observable_refs", [])),
            evidence_refs=tuple(str(ref) for ref in boundary_spec.get("evidence_refs", [])),
            disclosed_refs=disclosed_refs,
            evidence_only_refs=evidence_only_refs,
            discovered_refs=discovered_refs,
            inferred_refs=inferred_refs,
            concealed_refs=concealed_refs,
            deceptive_refs=deceptive_refs,
            view_transitions=ordered_view_transitions,
            view_relation_timeline=view_relation_timeline,
            realized_view_disclosure=str(boundary_spec.get("realized_view_disclosure") or ""),
            spec=boundary_spec,
        )
    return observation_boundaries


def _outcome_source_ref_address(source_layer: str, ref: str) -> str:
    if source_layer == OutcomeInterpretationSourceLayer.PARTICIPANT_ACTION_OUTCOME.value:
        return _action_contract_address(ref)
    if source_layer == OutcomeInterpretationSourceLayer.OBJECTIVE_RESULT.value:
        return _objective_address(ref)
    if source_layer == OutcomeInterpretationSourceLayer.WORKFLOW_RESULT.value:
        return _workflow_address(ref)
    if source_layer == OutcomeInterpretationSourceLayer.EVALUATION_RESULT.value:
        return _evaluation_address(ref)
    return ref


def _outcome_target_ref_address(target_layer: str, ref: str) -> str:
    if target_layer == OutcomeInterpretationTargetLayer.OBJECTIVE_RESULT.value:
        return _objective_address(ref)
    if target_layer == OutcomeInterpretationTargetLayer.WORKFLOW_RESULT.value:
        return _workflow_address(ref)
    if target_layer == OutcomeInterpretationTargetLayer.EVALUATION_RESULT.value:
        return _evaluation_address(ref)
    return ref


def _compile_outcome_interpretation_rules(
    scenario: InstantiatedScenario,
) -> dict[str, ParticipantOutcomeInterpretationRuleRuntime]:
    rules: dict[str, ParticipantOutcomeInterpretationRuleRuntime] = {}
    for name, rule in scenario.outcome_interpretation_rules.items():
        rule_spec = _dump(rule)
        sources = tuple(source for source in rule_spec.get("source_bindings", ()) if isinstance(source, dict))
        targets = tuple(target for target in rule_spec.get("target_bindings", ()) if isinstance(target, dict))
        source_layers = tuple(str(source.get("source_layer", "")) for source in sources)
        target_layers = tuple(str(target.get("target_layer", "")) for target in targets)
        source_refs = tuple(
            _outcome_source_ref_address(str(source.get("source_layer", "")), str(source.get("ref", "")))
            for source in sources
        )
        target_refs = tuple(
            _outcome_target_ref_address(str(target.get("target_layer", "")), str(target.get("ref", "")))
            for target in targets
        )
        address = _outcome_interpretation_rule_address(name)
        rules[address] = ParticipantOutcomeInterpretationRuleRuntime(
            address=address,
            name=name,
            rule_name=name,
            semantic_version=str(rule_spec.get("semantic_version", "")),
            participant_scope=str(rule_spec.get("participant_scope", "")),
            observation_point_basis=str(rule_spec.get("observation_point_basis", "")),
            interpretation_basis=str(rule_spec.get("interpretation_basis", "")),
            source_layers=source_layers,
            source_refs=source_refs,
            target_layers=target_layers,
            target_refs=target_refs,
            evidence_refs=tuple(str(ref) for ref in rule_spec.get("evidence_refs", ())),
            limitations=tuple(str(item) for item in rule_spec.get("limitations", ())),
            spec=rule_spec,
        )
    return rules


def _participant_action_addresses(
    scenario: InstantiatedScenario,
    *,
    participant_name: str,
    action_names: list[str],
    diagnostics: list[Diagnostic],
) -> list[str]:
    action_addresses: list[str] = []
    if not scenario.action_contracts:
        return action_addresses
    for action_name in dict.fromkeys(action_names):
        if action_name in scenario.action_contracts:
            action_addresses.append(_action_contract_address(action_name))
            continue
        if action_name:
            diagnostics.append(
                Diagnostic(
                    code="participant.action-contract-ref-unbound",
                    domain="participant",
                    address=_participant_behavior_address(participant_name),
                    message=f"Reference '{action_name}' does not resolve to a declared participant action contract.",
                )
            )
    return action_addresses


def _participant_observation_addresses(
    scenario: InstantiatedScenario,
    *,
    participant_name: str,
    boundary_names: list[str],
    diagnostics: list[Diagnostic],
) -> list[str]:
    observation_addresses: list[str] = []
    for boundary_name in dict.fromkeys(boundary_names):
        if boundary_name in scenario.observation_boundaries:
            observation_addresses.append(_observation_boundary_address(boundary_name))
            continue
        if boundary_name:
            diagnostics.append(
                Diagnostic(
                    code="participant.observation-boundary-ref-unbound",
                    domain="participant",
                    address=_participant_behavior_address(participant_name),
                    message=(
                        f"Reference '{boundary_name}' does not resolve to a declared participant observation boundary."
                    ),
                )
            )
    return observation_addresses


def _compile_participant_behaviors(
    scenario: InstantiatedScenario,
    diagnostics: list[Diagnostic],
) -> dict[str, ParticipantBehaviorRuntime]:
    participant_behaviors: dict[str, ParticipantBehaviorRuntime] = {}
    for name, agent in scenario.agents.items():
        action_addresses = _participant_action_addresses(
            scenario,
            participant_name=name,
            action_names=list(agent.actions),
            diagnostics=diagnostics,
        )
        observation_addresses = _participant_observation_addresses(
            scenario,
            participant_name=name,
            boundary_names=list(agent.observation_boundaries),
            diagnostics=diagnostics,
        )
        dependency_addresses = _dedupe([*action_addresses, *observation_addresses])
        participant_behaviors[_participant_behavior_address(name)] = ParticipantBehaviorRuntime(
            address=_participant_behavior_address(name),
            name=name,
            participant_name=name,
            entity_name=agent.entity,
            action_contract_addresses=tuple(action_addresses),
            observation_boundary_addresses=tuple(observation_addresses),
            refresh_dependencies=dependency_addresses,
            spec={"agent": _dump(agent), "interpretation_mode": "role-neutral-projection"},
        )
    return participant_behaviors


def _compile_events(
    scenario: InstantiatedScenario,
    condition_bindings: dict[str, ConditionBinding],
    injects: dict[str, InjectRuntime],
    inject_bindings: dict[str, InjectBinding],
    diagnostics: list[Diagnostic],
) -> dict[str, EventRuntime]:
    events: dict[str, EventRuntime] = {}
    for name, event in scenario.events.items():
        event_address = _event_address(name)
        condition_names = list(event.conditions)
        inject_names = list(event.injects)
        condition_addresses, condition_diagnostics = _resolve_binding_refs(
            condition_bindings,
            ref_names=condition_names,
            owner_address=event_address,
            domain="orchestration",
            code_prefix="orchestration.condition-ref",
            binding_attr="condition_name",
            binding_label="condition",
        )
        inject_addresses, inject_diagnostics = _resolve_resource_refs(
            injects,
            ref_names=inject_names,
            owner_address=event_address,
            domain="orchestration",
            code_prefix="orchestration.inject-ref",
            resource_label="inject",
        )
        diagnostics.extend(condition_diagnostics)
        diagnostics.extend(inject_diagnostics)
        inject_binding_ordering_dependencies = [
            address for address, binding in inject_bindings.items() if binding.inject_name in inject_names
        ]
        events[event_address] = EventRuntime(
            address=event_address,
            name=name,
            condition_names=tuple(condition_names),
            condition_addresses=condition_addresses,
            inject_names=tuple(inject_names),
            inject_addresses=inject_addresses,
            ordering_dependencies=_dedupe([*inject_addresses, *inject_binding_ordering_dependencies]),
            refresh_dependencies=_dedupe(
                [*condition_addresses, *inject_addresses, *inject_binding_ordering_dependencies]
            ),
            spec=_dump(event),
        )
    return events


def _compile_scripts(
    scenario: InstantiatedScenario,
    diagnostics: list[Diagnostic],
) -> dict[str, ScriptRuntime]:
    scripts: dict[str, ScriptRuntime] = {}
    for name, script in scenario.scripts.items():
        script_address = _script_address(name)
        event_addresses, script_diagnostics = _resolve_named_refs(
            ref_names=list(script.events),
            available_names=set(scenario.events),
            address_builder=_event_address,
            owner_address=script_address,
            domain="orchestration",
            code_prefix="orchestration.event-ref",
            resource_label="event",
        )
        diagnostics.extend(script_diagnostics)
        scripts[script_address] = ScriptRuntime(
            address=script_address,
            name=name,
            event_addresses=event_addresses,
            ordering_dependencies=event_addresses,
            refresh_dependencies=event_addresses,
            spec=_dump(script),
        )
    return scripts


def _compile_stories(
    scenario: InstantiatedScenario,
    diagnostics: list[Diagnostic],
) -> dict[str, StoryRuntime]:
    stories: dict[str, StoryRuntime] = {}
    for name, story in scenario.stories.items():
        story_address = _story_address(name)
        script_addresses, story_diagnostics = _resolve_named_refs(
            ref_names=list(story.scripts),
            available_names=set(scenario.scripts),
            address_builder=_script_address,
            owner_address=story_address,
            domain="orchestration",
            code_prefix="orchestration.script-ref",
            resource_label="script",
        )
        diagnostics.extend(story_diagnostics)
        stories[story_address] = StoryRuntime(
            address=story_address,
            name=name,
            script_addresses=script_addresses,
            ordering_dependencies=script_addresses,
            refresh_dependencies=script_addresses,
            spec=_dump(story),
        )
    return stories


def _compile_metrics(
    scenario: InstantiatedScenario,
    condition_bindings: dict[str, ConditionBinding],
    diagnostics: list[Diagnostic],
) -> dict[str, MetricRuntime]:
    metrics: dict[str, MetricRuntime] = {}
    for name, metric in scenario.metrics.items():
        metric_spec = _dump(metric)
        metric_address = _metric_address(name)
        condition_addresses = _metric_condition_addresses(metric_spec, metric_address, condition_bindings, diagnostics)
        result_contract, execution_contract = _evaluation_contracts("metric", metric_spec)
        ordering_dependencies, refresh_dependencies = partition_assessment_dependencies(condition_addresses)
        metrics[metric_address] = MetricRuntime(
            address=metric_address,
            name=name,
            condition_name=metric_spec.get("condition") or "",
            condition_addresses=condition_addresses,
            ordering_dependencies=ordering_dependencies,
            refresh_dependencies=refresh_dependencies,
            spec=metric_spec,
            result_contract=result_contract,
            execution_contract=execution_contract,
        )
    return metrics


def _metric_condition_addresses(
    metric_spec: dict[str, Any],
    metric_address: str,
    condition_bindings: dict[str, ConditionBinding],
    diagnostics: list[Diagnostic],
) -> tuple[str, ...]:
    condition_name = metric_spec.get("condition") or ""
    if not condition_name:
        return ()
    condition_addresses, metric_diagnostics = _resolve_binding_ref(
        condition_bindings,
        ref_name=condition_name,
        owner_address=metric_address,
        domain="evaluation",
        code_prefix="evaluation.condition-ref",
        binding_attr="condition_name",
        binding_label="condition",
    )
    diagnostics.extend(metric_diagnostics)
    return condition_addresses


def _compile_evaluations(
    scenario: InstantiatedScenario,
    diagnostics: list[Diagnostic],
) -> dict[str, EvaluationRuntime]:
    evaluations: dict[str, EvaluationRuntime] = {}
    for name, evaluation in scenario.evaluations.items():
        evaluation_address = _evaluation_address(name)
        metric_addresses, evaluation_diagnostics = _resolve_named_refs(
            ref_names=list(evaluation.metrics),
            available_names=set(scenario.metrics),
            address_builder=_metric_address,
            owner_address=evaluation_address,
            domain="evaluation",
            code_prefix="evaluation.metric-ref",
            resource_label="metric",
        )
        diagnostics.extend(evaluation_diagnostics)
        result_contract, execution_contract = _evaluation_contracts("evaluation")
        ordering_dependencies, refresh_dependencies = partition_assessment_dependencies(metric_addresses)
        evaluations[evaluation_address] = EvaluationRuntime(
            address=evaluation_address,
            name=name,
            metric_addresses=metric_addresses,
            ordering_dependencies=ordering_dependencies,
            refresh_dependencies=refresh_dependencies,
            spec=_dump(evaluation),
            result_contract=result_contract,
            execution_contract=execution_contract,
        )
    return evaluations


def _compile_tlos(
    scenario: InstantiatedScenario,
    diagnostics: list[Diagnostic],
) -> dict[str, TLORuntime]:
    tlos: dict[str, TLORuntime] = {}
    for name, tlo in scenario.tlos.items():
        tlo_address = _tlo_address(name)
        evaluation_addresses, tlo_diagnostics = _resolve_named_refs(
            ref_names=[tlo.evaluation],
            available_names=set(scenario.evaluations),
            address_builder=_evaluation_address,
            owner_address=tlo_address,
            domain="evaluation",
            code_prefix="evaluation.evaluation-ref",
            resource_label="evaluation",
        )
        diagnostics.extend(tlo_diagnostics)
        result_contract, execution_contract = _evaluation_contracts("tlo")
        ordering_dependencies, refresh_dependencies = partition_assessment_dependencies(evaluation_addresses)
        tlos[tlo_address] = TLORuntime(
            address=tlo_address,
            name=name,
            evaluation_address=evaluation_addresses[0] if evaluation_addresses else "",
            ordering_dependencies=ordering_dependencies,
            refresh_dependencies=refresh_dependencies,
            spec=_dump(tlo),
            result_contract=result_contract,
            execution_contract=execution_contract,
        )
    return tlos


def _compile_goals(
    scenario: InstantiatedScenario,
    diagnostics: list[Diagnostic],
) -> dict[str, GoalRuntime]:
    goals: dict[str, GoalRuntime] = {}
    for name, goal in scenario.goals.items():
        goal_address = _goal_address(name)
        tlo_addresses, goal_diagnostics = _resolve_named_refs(
            ref_names=list(goal.tlos),
            available_names=set(scenario.tlos),
            address_builder=_tlo_address,
            owner_address=goal_address,
            domain="evaluation",
            code_prefix="evaluation.tlo-ref",
            resource_label="TLO",
        )
        diagnostics.extend(goal_diagnostics)
        result_contract, execution_contract = _evaluation_contracts("goal")
        ordering_dependencies, refresh_dependencies = partition_assessment_dependencies(tlo_addresses)
        goals[goal_address] = GoalRuntime(
            address=goal_address,
            name=name,
            tlo_addresses=tlo_addresses,
            ordering_dependencies=ordering_dependencies,
            refresh_dependencies=refresh_dependencies,
            spec=_dump(goal),
            result_contract=result_contract,
            execution_contract=execution_contract,
        )
    return goals


def _objective_success_addresses(
    scenario: InstantiatedScenario,
    condition_bindings: dict[str, ConditionBinding],
    objective: Any,
    objective_address: str,
    diagnostics: list[Diagnostic],
) -> list[str]:
    condition_addresses, condition_diagnostics = _resolve_binding_refs(
        condition_bindings,
        ref_names=list(objective.success.conditions),
        owner_address=objective_address,
        domain="evaluation",
        code_prefix="evaluation.condition-ref",
        binding_attr="condition_name",
        binding_label="condition",
    )
    metric_addresses, metric_diagnostics = _resolve_named_refs(
        ref_names=list(objective.success.metrics),
        available_names=set(scenario.metrics),
        address_builder=_metric_address,
        owner_address=objective_address,
        domain="evaluation",
        code_prefix="evaluation.metric-ref",
        resource_label="metric",
    )
    evaluation_addresses, evaluation_diagnostics = _resolve_named_refs(
        ref_names=list(objective.success.evaluations),
        available_names=set(scenario.evaluations),
        address_builder=_evaluation_address,
        owner_address=objective_address,
        domain="evaluation",
        code_prefix="evaluation.evaluation-ref",
        resource_label="evaluation",
    )
    tlo_addresses, tlo_diagnostics = _resolve_named_refs(
        ref_names=list(objective.success.tlos),
        available_names=set(scenario.tlos),
        address_builder=_tlo_address,
        owner_address=objective_address,
        domain="evaluation",
        code_prefix="evaluation.tlo-ref",
        resource_label="TLO",
    )
    goal_addresses, goal_diagnostics = _resolve_named_refs(
        ref_names=list(objective.success.goals),
        available_names=set(scenario.goals),
        address_builder=_goal_address,
        owner_address=objective_address,
        domain="evaluation",
        code_prefix="evaluation.goal-ref",
        resource_label="goal",
    )
    diagnostics.extend(
        [
            *condition_diagnostics,
            *metric_diagnostics,
            *evaluation_diagnostics,
            *tlo_diagnostics,
            *goal_diagnostics,
        ]
    )
    return [*condition_addresses, *metric_addresses, *evaluation_addresses, *tlo_addresses, *goal_addresses]


def _objective_dependency_addresses(
    scenario: InstantiatedScenario,
    objective: Any,
    objective_address: str,
    diagnostics: list[Diagnostic],
) -> tuple[str, ...]:
    objective_dependencies, objective_dependency_diagnostics = _resolve_named_refs(
        ref_names=list(objective.depends_on),
        available_names=set(scenario.objectives),
        address_builder=_objective_address,
        owner_address=objective_address,
        domain="evaluation",
        code_prefix="evaluation.objective-ref",
        resource_label="objective",
    )
    diagnostics.extend(objective_dependency_diagnostics)
    return objective_dependencies


def _objective_window_issue_diagnostic(issue: Any, objective_address: str) -> Diagnostic | None:
    spec = _OBJECTIVE_WINDOW_ISSUE_DIAGNOSTICS.get(issue.code)
    if spec is None:
        return None
    code, message_template = spec
    return Diagnostic(
        code=code,
        domain="evaluation",
        address=objective_address,
        message=message_template.format(ref=issue.ref),
    )


def _compile_objective_window(
    scenario: InstantiatedScenario,
    objective: Any,
    objective_address: str,
    diagnostics: list[Diagnostic],
) -> _ObjectiveWindowCompilation:
    if objective.window is None:
        return _ObjectiveWindowCompilation()
    window_analysis = analyze_objective_window(
        story_refs=list(objective.window.stories),
        script_refs=list(objective.window.scripts),
        event_refs=list(objective.window.events),
        workflow_refs=list(objective.window.workflows),
        step_refs=list(objective.window.steps),
        stories_by_name=scenario.stories,
        scripts_by_name=scenario.scripts,
        events_by_name=scenario.events,
        workflows_by_name=scenario.workflows,
    )
    for issue in window_analysis.issues:
        diagnostic = _objective_window_issue_diagnostic(issue, objective_address)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
    window_role_values = tuple(role.value for role in OBJECTIVE_WINDOW_DEPENDENCY_ROLES)
    return _ObjectiveWindowCompilation(
        story_addresses=_dedupe([_story_address(name) for name in window_analysis.story_names]),
        script_addresses=_dedupe([_script_address(name) for name in window_analysis.script_names]),
        event_addresses=_dedupe([_event_address(name) for name in window_analysis.event_names]),
        workflow_addresses=_dedupe([_workflow_address(name) for name in window_analysis.workflow_names]),
        step_refs=window_analysis.workflow_step_refs,
        step_workflow_addresses=_dedupe(
            [_workflow_address(workflow_name) for workflow_name in window_analysis.refresh_workflow_names]
        ),
        references=tuple(
            ObjectiveWindowReferenceRuntime(
                raw=ref.raw,
                canonical_name=ref.canonical_name,
                reference_kind=ref.reference_kind.value,
                dependency_roles=window_role_values,
                workflow_name=ref.workflow_name or "",
                step_name=ref.step_name or "",
                namespace_path=ref.namespace_path,
            )
            for ref in window_analysis.references
        ),
    )


def _compile_objectives(
    scenario: InstantiatedScenario,
    condition_bindings: dict[str, ConditionBinding],
    diagnostics: list[Diagnostic],
) -> dict[str, ObjectiveRuntime]:
    objectives: dict[str, ObjectiveRuntime] = {}
    for name, objective in scenario.objectives.items():
        objective_address = _objective_address(name)
        success_addresses = _objective_success_addresses(
            scenario,
            condition_bindings,
            objective,
            objective_address,
            diagnostics,
        )
        objective_dependencies = _objective_dependency_addresses(scenario, objective, objective_address, diagnostics)
        window = _compile_objective_window(scenario, objective, objective_address, diagnostics)
        ordering_dependencies, refresh_dependencies = partition_objective_dependencies(
            success_refs=success_addresses,
            dependency_refs=objective_dependencies,
            window_refresh_refs=[
                *window.story_addresses,
                *window.script_addresses,
                *window.event_addresses,
                *window.workflow_addresses,
                *window.step_workflow_addresses,
            ],
        )
        result_contract, execution_contract = _evaluation_contracts("objective")
        objectives[objective_address] = ObjectiveRuntime(
            address=objective_address,
            name=name,
            actor_type="agent" if objective.agent else "entity",
            actor_name=objective.agent or objective.entity,
            success_addresses=tuple(success_addresses),
            objective_dependencies=objective_dependencies,
            window_story_addresses=window.story_addresses,
            window_script_addresses=window.script_addresses,
            window_event_addresses=window.event_addresses,
            window_workflow_addresses=window.workflow_addresses,
            window_step_refs=window.step_refs,
            window_step_workflow_addresses=window.step_workflow_addresses,
            window_references=window.references,
            ordering_dependencies=ordering_dependencies,
            refresh_dependencies=refresh_dependencies,
            spec=_dump(objective),
            result_contract=result_contract,
            execution_contract=execution_contract,
        )
    return objectives


def _compile_workflow_predicate(
    predicate_source: Any,
    *,
    scenario: InstantiatedScenario,
    condition_bindings: dict[str, ConditionBinding],
    predicate_address: str,
    diagnostics: list[Diagnostic],
) -> _WorkflowPredicateCompilation:
    condition_addresses, workflow_diagnostics = _resolve_binding_refs(
        condition_bindings,
        ref_names=list(predicate_source.conditions),
        owner_address=predicate_address,
        domain="orchestration",
        code_prefix="orchestration.condition-ref",
        binding_attr="condition_name",
        binding_label="condition",
    )
    metric_addresses, metric_diagnostics = _resolve_named_refs(
        ref_names=list(predicate_source.metrics),
        available_names=set(scenario.metrics),
        address_builder=_metric_address,
        owner_address=predicate_address,
        domain="orchestration",
        code_prefix="orchestration.metric-ref",
        resource_label="metric",
    )
    evaluation_addresses, evaluation_diagnostics = _resolve_named_refs(
        ref_names=list(predicate_source.evaluations),
        available_names=set(scenario.evaluations),
        address_builder=_evaluation_address,
        owner_address=predicate_address,
        domain="orchestration",
        code_prefix="orchestration.evaluation-ref",
        resource_label="evaluation",
    )
    tlo_addresses, tlo_diagnostics = _resolve_named_refs(
        ref_names=list(predicate_source.tlos),
        available_names=set(scenario.tlos),
        address_builder=_tlo_address,
        owner_address=predicate_address,
        domain="orchestration",
        code_prefix="orchestration.tlo-ref",
        resource_label="TLO",
    )
    goal_addresses, goal_diagnostics = _resolve_named_refs(
        ref_names=list(predicate_source.goals),
        available_names=set(scenario.goals),
        address_builder=_goal_address,
        owner_address=predicate_address,
        domain="orchestration",
        code_prefix="orchestration.goal-ref",
        resource_label="goal",
    )
    objective_addresses, objective_diagnostics = _resolve_named_refs(
        ref_names=list(predicate_source.objectives),
        available_names=set(scenario.objectives),
        address_builder=_objective_address,
        owner_address=predicate_address,
        domain="orchestration",
        code_prefix="orchestration.objective-ref",
        resource_label="objective",
    )
    diagnostics.extend(
        [
            *workflow_diagnostics,
            *metric_diagnostics,
            *evaluation_diagnostics,
            *tlo_diagnostics,
            *goal_diagnostics,
            *objective_diagnostics,
        ]
    )
    step_state_predicates = tuple(
        WorkflowStepStatePredicateRuntime(
            step_name=ref.step,
            outcomes=tuple(WorkflowStepOutcome(outcome.value) for outcome in ref.outcomes),
            min_attempts=ref.min_attempts,
        )
        for ref in predicate_source.steps
        if isinstance(ref.step, str) and ref.step
    )
    predicate_addresses = _dedupe(
        [
            *condition_addresses,
            *metric_addresses,
            *evaluation_addresses,
            *tlo_addresses,
            *goal_addresses,
            *objective_addresses,
        ]
    )
    return _WorkflowPredicateCompilation(
        predicate=WorkflowPredicateRuntime(
            condition_addresses=condition_addresses,
            metric_addresses=tuple(metric_addresses),
            evaluation_addresses=tuple(evaluation_addresses),
            tlo_addresses=tuple(tlo_addresses),
            goal_addresses=tuple(goal_addresses),
            objective_addresses=tuple(objective_addresses),
            step_state_predicates=step_state_predicates,
        ),
        condition_addresses=condition_addresses,
        predicate_addresses=predicate_addresses,
        objective_addresses=tuple(objective_addresses),
        step_state_predicates=step_state_predicates,
    )


def _workflow_step_edges_and_features(step: Any) -> tuple[tuple[str, ...], tuple[WorkflowFeature, ...]]:
    edge_values = {
        WorkflowStepType.OBJECTIVE: (step.on_success, step.on_failure),
        WorkflowStepType.DECISION: (step.then_step, step.else_step),
        WorkflowStepType.SWITCH: (*[case.next_step for case in step.cases], step.default_step),
        WorkflowStepType.PARALLEL: (*step.branches, step.on_failure),
        WorkflowStepType.JOIN: (step.next,),
        WorkflowStepType.RETRY: (step.on_success, step.on_exhausted),
        WorkflowStepType.CALL: (step.on_success, step.on_failure),
    }.get(step.type, ())
    feature = _WORKFLOW_STEP_TYPE_FEATURES.get(step.type)
    return _dedupe([edge for edge in edge_values if edge]), (() if feature is None else (feature,))


def _workflow_cross_cutting_features(step: Any, workflow: Any) -> tuple[WorkflowFeature, ...]:
    features: list[WorkflowFeature] = []
    if step.on_failure or step.on_exhausted:
        features.append(WorkflowFeature.FAILURE_TRANSITIONS)
    if workflow.timeout is not None:
        features.append(WorkflowFeature.TIMEOUTS)
    if workflow.compensation is not None and workflow.compensation.mode.value != "disabled":
        features.append(WorkflowFeature.COMPENSATION)
    return tuple(features)


def _workflow_step_primary_addresses(
    scenario: InstantiatedScenario,
    *,
    workflow_address: str,
    step: Any,
    state: _WorkflowCompilationState,
    diagnostics: list[Diagnostic],
) -> tuple[str, str]:
    objective_address = ""
    called_workflow_address = ""
    if step.objective:
        objective_addresses, objective_diagnostics = _resolve_named_refs(
            ref_names=[step.objective],
            available_names=set(scenario.objectives),
            address_builder=_objective_address,
            owner_address=workflow_address,
            domain="orchestration",
            code_prefix="orchestration.objective-ref",
            resource_label="objective",
        )
        diagnostics.extend(objective_diagnostics)
        state.referenced_objectives.extend(objective_addresses)
        objective_address = objective_addresses[0] if objective_addresses else ""
    elif step.workflow:
        workflow_addresses, workflow_diagnostics = _resolve_named_refs(
            ref_names=[step.workflow],
            available_names=set(scenario.workflows),
            address_builder=_workflow_address,
            owner_address=workflow_address,
            domain="orchestration",
            code_prefix="orchestration.workflow-ref",
            resource_label="workflow",
        )
        diagnostics.extend(workflow_diagnostics)
        called_workflow_address = workflow_addresses[0] if workflow_addresses else ""
    return objective_address, called_workflow_address


def _workflow_step_compensation_address(
    scenario: InstantiatedScenario,
    *,
    workflow_address: str,
    step_name: str,
    step: Any,
    state: _WorkflowCompilationState,
    diagnostics: list[Diagnostic],
) -> str:
    if not step.compensate_with:
        return ""
    workflow_addresses, workflow_diagnostics = _resolve_named_refs(
        ref_names=[step.compensate_with],
        available_names=set(scenario.workflows),
        address_builder=_workflow_address,
        owner_address=workflow_address,
        domain="orchestration",
        code_prefix="orchestration.workflow-ref",
        resource_label="workflow",
    )
    diagnostics.extend(workflow_diagnostics)
    compensation_workflow_address = workflow_addresses[0] if workflow_addresses else ""
    if compensation_workflow_address:
        state.compensation_targets[step_name] = compensation_workflow_address
        state.required_features.append(WorkflowFeature.COMPENSATION)
    return compensation_workflow_address


def _apply_workflow_predicate_compilation(
    state: _WorkflowCompilationState,
    step_name: str,
    compilation: _WorkflowPredicateCompilation,
) -> None:
    state.referenced_objectives.extend(compilation.objective_addresses)
    state.step_condition_addresses[step_name] = compilation.condition_addresses
    state.step_predicate_addresses[step_name] = compilation.predicate_addresses
    _apply_step_state_predicate_features(state, compilation.step_state_predicates)


def _apply_step_state_predicate_features(
    state: _WorkflowCompilationState,
    step_state_predicates: tuple[WorkflowStepStatePredicateRuntime, ...],
) -> None:
    if step_state_predicates:
        state.required_state_predicate_features.append(WorkflowStatePredicateFeature.OUTCOME_MATCHING)
    if any(state_predicate.min_attempts is not None for state_predicate in step_state_predicates):
        state.required_state_predicate_features.append(WorkflowStatePredicateFeature.ATTEMPT_COUNTS)


def _compile_switch_cases(
    scenario: InstantiatedScenario,
    *,
    workflow_address: str,
    step_name: str,
    step: Any,
    state: _WorkflowCompilationState,
    condition_bindings: dict[str, ConditionBinding],
    diagnostics: list[Diagnostic],
) -> tuple[WorkflowSwitchCaseRuntime, ...]:
    compiled_cases: list[WorkflowSwitchCaseRuntime] = []
    switch_condition_addresses: list[str] = []
    switch_predicate_addresses: list[str] = []
    for case_index, case in enumerate(step.cases):
        compilation = _compile_workflow_predicate(
            case.when,
            scenario=scenario,
            condition_bindings=condition_bindings,
            predicate_address=_address(workflow_address, "step", step_name, "case", str(case_index)),
            diagnostics=diagnostics,
        )
        state.referenced_objectives.extend(compilation.objective_addresses)
        switch_condition_addresses.extend(compilation.condition_addresses)
        switch_predicate_addresses.extend(compilation.predicate_addresses)
        _apply_step_state_predicate_features(state, compilation.step_state_predicates)
        compiled_cases.append(
            WorkflowSwitchCaseRuntime(case_index=case_index, predicate=compilation.predicate, next_step=case.next_step)
        )
    if switch_condition_addresses:
        state.step_condition_addresses[step_name] = _dedupe(switch_condition_addresses)
    if switch_predicate_addresses:
        state.step_predicate_addresses[step_name] = _dedupe(switch_predicate_addresses)
    return tuple(compiled_cases)


def _compile_workflow_step_predicates(
    scenario: InstantiatedScenario,
    *,
    workflow_address: str,
    step_name: str,
    step: Any,
    state: _WorkflowCompilationState,
    condition_bindings: dict[str, ConditionBinding],
    diagnostics: list[Diagnostic],
) -> tuple[WorkflowPredicateRuntime | None, tuple[WorkflowSwitchCaseRuntime, ...]]:
    if step.when is not None:
        compilation = _compile_workflow_predicate(
            step.when,
            scenario=scenario,
            condition_bindings=condition_bindings,
            predicate_address=_address(workflow_address, "step", step_name),
            diagnostics=diagnostics,
        )
        _apply_workflow_predicate_compilation(state, step_name, compilation)
        return compilation.predicate, ()
    if step.type != WorkflowStepType.SWITCH:
        return None, ()
    return None, _compile_switch_cases(
        scenario,
        workflow_address=workflow_address,
        step_name=step_name,
        step=step,
        state=state,
        condition_bindings=condition_bindings,
        diagnostics=diagnostics,
    )


def _compile_workflow_step(
    scenario: InstantiatedScenario,
    *,
    workflow: Any,
    workflow_address: str,
    step_name: str,
    step: Any,
    state: _WorkflowCompilationState,
    condition_bindings: dict[str, ConditionBinding],
    diagnostics: list[Diagnostic],
) -> None:
    edges, type_features = _workflow_step_edges_and_features(step)
    state.control_edges[step_name] = edges
    state.required_features.extend(type_features)
    objective_address, called_workflow_address = _workflow_step_primary_addresses(
        scenario,
        workflow_address=workflow_address,
        step=step,
        state=state,
        diagnostics=diagnostics,
    )
    compensation_workflow_address = _workflow_step_compensation_address(
        scenario,
        workflow_address=workflow_address,
        step_name=step_name,
        step=step,
        state=state,
        diagnostics=diagnostics,
    )
    predicate, switch_cases = _compile_workflow_step_predicates(
        scenario,
        workflow_address=workflow_address,
        step_name=step_name,
        step=step,
        state=state,
        condition_bindings=condition_bindings,
        diagnostics=diagnostics,
    )
    state.required_features.extend(_workflow_cross_cutting_features(step, workflow))
    state.control_steps[step_name] = WorkflowStepRuntime(
        name=step_name,
        step_type=step.type.value,
        objective_address=objective_address,
        predicate=predicate,
        next_step=step.next,
        on_success=step.on_success,
        on_failure=step.on_failure,
        on_exhausted=step.on_exhausted,
        then_step=step.then_step,
        else_step=step.else_step,
        switch_cases=switch_cases,
        default_step=step.default_step,
        branches=tuple(step.branches),
        join_step=step.join,
        owning_parallel_step=state.join_owners.get(step_name, ""),
        called_workflow_address=called_workflow_address,
        compensation_workflow_address=compensation_workflow_address,
        max_attempts=step.max_attempts,
        state_contract=workflow_step_semantic_contract(step.type.value),
    )


def _workflow_timeout_seconds(workflow: Any) -> int | None:
    if workflow.timeout is None or not isinstance(workflow.timeout.seconds, int):
        return None
    return workflow.timeout.seconds


def _workflow_join_owners(workflow: Any) -> dict[str, str]:
    return {
        step.join: step_name
        for step_name, step in workflow.steps.items()
        if step.type == WorkflowStepType.PARALLEL and step.join
    }


def _workflow_result_contract_steps(
    control_steps: dict[str, WorkflowStepRuntime],
) -> dict[str, Any]:
    return {
        step_name: step_runtime.state_contract
        for step_name, step_runtime in control_steps.items()
        if step_runtime.state_contract.state_observable
    }


def _workflow_predicate_dependency_addresses(state: _WorkflowCompilationState) -> tuple[str, ...]:
    return _dedupe([address for addresses in state.step_predicate_addresses.values() for address in addresses])


def _workflow_compensation_mode(workflow: Any) -> str:
    return workflow.compensation.mode.value if workflow.compensation is not None else "disabled"


def _workflow_compensation_triggers(workflow: Any) -> tuple[str, ...]:
    return tuple(trigger.value for trigger in (workflow.compensation.on if workflow.compensation is not None else []))


def _workflow_compensation_ordering(workflow: Any) -> str:
    return workflow.compensation.order if workflow.compensation is not None else "reverse_completion"


def _workflow_compensation_failure_policy(workflow: Any) -> str:
    if workflow.compensation is None:
        return "fail_workflow"
    return workflow.compensation.failure_policy.value


def _workflow_execution_contract(
    workflow: Any,
    state: _WorkflowCompilationState,
    result_contract_steps: dict[str, Any],
) -> WorkflowExecutionContract:
    return WorkflowExecutionContract(
        state_schema_version=WORKFLOW_STATE_SCHEMA_VERSION,
        start_step=workflow.start,
        timeout_seconds=_workflow_timeout_seconds(workflow),
        steps={step_name: step_runtime.state_contract for step_name, step_runtime in state.control_steps.items()},
        step_types={step_name: step_runtime.step_type for step_name, step_runtime in state.control_steps.items()},
        control_edges=state.control_edges,
        join_owners=state.join_owners,
        call_steps={
            step_name: step_runtime.called_workflow_address
            for step_name, step_runtime in state.control_steps.items()
            if step_runtime.called_workflow_address
        },
        compensation_mode=_workflow_compensation_mode(workflow),
        compensation_triggers=_workflow_compensation_triggers(workflow),
        compensation_targets=state.compensation_targets,
        compensation_ordering=_workflow_compensation_ordering(workflow),
        compensation_failure_policy=_workflow_compensation_failure_policy(workflow),
        observable_steps=tuple(sorted(result_contract_steps)),
    )


def _compile_workflow_runtime(
    scenario: InstantiatedScenario,
    *,
    name: str,
    workflow: Any,
    condition_bindings: dict[str, ConditionBinding],
    diagnostics: list[Diagnostic],
) -> WorkflowRuntime:
    workflow_address = _workflow_address(name)
    state = _WorkflowCompilationState(join_owners=_workflow_join_owners(workflow))
    for step_name, step in workflow.steps.items():
        _compile_workflow_step(
            scenario,
            workflow=workflow,
            workflow_address=workflow_address,
            step_name=step_name,
            step=step,
            state=state,
            condition_bindings=condition_bindings,
            diagnostics=diagnostics,
        )
    objective_addresses = _dedupe(state.referenced_objectives)
    result_contract_steps = _workflow_result_contract_steps(state.control_steps)
    predicate_dependency_addresses = _workflow_predicate_dependency_addresses(state)
    return WorkflowRuntime(
        address=workflow_address,
        name=name,
        start_step=workflow.start,
        referenced_objective_addresses=objective_addresses,
        control_steps=state.control_steps,
        control_edges=state.control_edges,
        join_owners=state.join_owners,
        step_condition_addresses=state.step_condition_addresses,
        step_predicate_addresses=state.step_predicate_addresses,
        required_features=_dedupe_by_value(state.required_features),
        required_state_predicate_features=_dedupe_by_value(state.required_state_predicate_features),
        result_contract=WorkflowResultContract(
            state_schema_version=WORKFLOW_STATE_SCHEMA_VERSION,
            observable_steps=result_contract_steps,
        ),
        execution_contract=_workflow_execution_contract(workflow, state, result_contract_steps),
        refresh_dependencies=_dedupe([*objective_addresses, *predicate_dependency_addresses]),
        spec=_dump(workflow),
    )


def _compile_workflows(
    scenario: InstantiatedScenario,
    condition_bindings: dict[str, ConditionBinding],
    diagnostics: list[Diagnostic],
) -> dict[str, WorkflowRuntime]:
    return {
        _workflow_address(name): _compile_workflow_runtime(
            scenario,
            name=name,
            workflow=workflow,
            condition_bindings=condition_bindings,
            diagnostics=diagnostics,
        )
        for name, workflow in scenario.workflows.items()
    }


def _node_variable_refs_by_address(
    scenario: InstantiatedScenario,
    node_variable_refs: dict[str, dict[str, str | None]],
) -> dict[str, dict[str, str | None]]:
    refs_by_address: dict[str, dict[str, str | None]] = {}
    for node_name, refs in node_variable_refs.items():
        if not refs.get("os") and not refs.get("count"):
            continue
        scenario_node = scenario.nodes.get(node_name)
        if scenario_node is None:
            continue
        address = _network_address(node_name) if scenario_node.type == NodeType.SWITCH else _node_address(node_name)
        refs_by_address[address] = refs
    return refs_by_address


def compile_runtime_model(scenario: Scenario | InstantiatedScenario) -> RuntimeModel:
    """Compile an SDL scenario into bound runtime objects."""

    if not isinstance(scenario, InstantiatedScenario):
        scenario = instantiate_scenario(scenario, validate_semantics=False)
    node_variable_refs = dict(scenario.node_variable_refs)
    diagnostics: list[Diagnostic] = []

    (
        feature_templates,
        condition_templates,
        inject_templates,
        vulnerability_templates,
    ) = _compile_templates(scenario)
    entity_specs, agent_specs, relationship_specs, variable_specs = _metadata_specs(scenario)

    networks, node_deployments = _compile_node_runtimes(scenario, diagnostics)
    feature_bindings = _compile_feature_bindings(scenario, feature_templates, diagnostics)
    condition_bindings = _compile_condition_bindings(scenario, condition_templates, diagnostics)
    injects = _compile_inject_runtimes(inject_templates)
    inject_bindings = _compile_inject_bindings(scenario, inject_templates, diagnostics)
    content_placements = _compile_content_placements(scenario, diagnostics)
    account_placements = _compile_account_placements(scenario, diagnostics)
    action_contracts = _compile_action_contracts(scenario)
    observation_boundaries = _compile_observation_boundaries(scenario)
    outcome_interpretation_rules = _compile_outcome_interpretation_rules(scenario)
    participant_behaviors = _compile_participant_behaviors(scenario, diagnostics)
    events = _compile_events(scenario, condition_bindings, injects, inject_bindings, diagnostics)
    scripts = _compile_scripts(scenario, diagnostics)
    stories = _compile_stories(scenario, diagnostics)
    metrics = _compile_metrics(scenario, condition_bindings, diagnostics)
    evaluations = _compile_evaluations(scenario, diagnostics)
    tlos = _compile_tlos(scenario, diagnostics)
    goals = _compile_goals(scenario, diagnostics)
    objectives = _compile_objectives(scenario, condition_bindings, diagnostics)
    workflows = _compile_workflows(scenario, condition_bindings, diagnostics)

    return RuntimeModel(
        scenario_name=scenario.name,
        feature_templates=feature_templates,
        condition_templates=condition_templates,
        inject_templates=inject_templates,
        vulnerability_templates=vulnerability_templates,
        entity_specs=entity_specs,
        agent_specs=agent_specs,
        relationship_specs=relationship_specs,
        variable_specs=variable_specs,
        node_variable_refs=_node_variable_refs_by_address(scenario, node_variable_refs),
        networks=networks,
        node_deployments=node_deployments,
        feature_bindings=feature_bindings,
        condition_bindings=condition_bindings,
        injects=injects,
        inject_bindings=inject_bindings,
        content_placements=content_placements,
        account_placements=account_placements,
        action_contracts=action_contracts,
        observation_boundaries=observation_boundaries,
        outcome_interpretation_rules=outcome_interpretation_rules,
        participant_behaviors=participant_behaviors,
        events=events,
        scripts=scripts,
        stories=stories,
        workflows=workflows,
        metrics=metrics,
        evaluations=evaluations,
        tlos=tlos,
        goals=goals,
        objectives=objectives,
        diagnostics=diagnostics,
    )
