"""Runtime data models for the SDL-native execution layer.

The runtime is split into three domains:

- provisioning: desired deployed state
- orchestration: resolved exercise control graph
- evaluation: resolved monitoring/scoring graph

The compiler produces a ``RuntimeModel`` with reusable templates separated
from bound runtime instances. The planner reconciles those instances against
the current ``RuntimeSnapshot`` and emits a composite ``ExecutionPlan``.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from aces_backend_protocols.capabilities import (
    BackendManifest,
    WorkflowFeature,
    WorkflowStatePredicateFeature,
)
from aces_contracts.versions import (
    EVALUATION_STATE_SCHEMA_VERSION,
    OPERATION_SCHEMA_VERSION,
    PARTICIPANT_EPISODE_STATE_SCHEMA_VERSION,
    RUNTIME_SNAPSHOT_SCHEMA_VERSION,
    WORKFLOW_STATE_SCHEMA_VERSION,
)
from aces_sdl.participant_attribution_semantics import (
    OUTCOME_ATTRIBUTION_CANDIDATE_KINDS,
    STRONG_ATTRIBUTION_SUPPORT_CLASSES,
    ParticipantAttributionCandidateKind,
    ParticipantAttributionOrderingBasisKind,
    ParticipantAttributionSupportClass,
)
from aces_sdl.participant_behavior import (
    ParticipantEffectClass,
    ParticipantFailureClass,
    ParticipantInteractionClass,
    ParticipantPreconditionClass,
)
from aces_sdl.participant_temporal_semantics import (
    ParticipantTemporalEventPoint,
    ParticipantTemporalState,
    ParticipantTimeDomain,
)
from aces_sdl.semantics.workflow import WorkflowStepSemanticContract

_PARTICIPANT_ACTION_CONTRACT_PREFIX = "participant.action-contract."
_PARTICIPANT_OBSERVATION_BOUNDARY_PREFIX = "participant.observation-boundary."
_PARTICIPANT_BEHAVIOR_HISTORY_KEY = "runtime.snapshot.participant-behavior-history"


class RuntimeDomain(str, Enum):
    """Top-level runtime concern."""

    PROVISIONING = "provisioning"
    ORCHESTRATION = "orchestration"
    EVALUATION = "evaluation"
    PARTICIPANT = "participant"


class ChangeAction(str, Enum):
    """Planner reconciliation result for a resource."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    UNCHANGED = "unchanged"


class Severity(str, Enum):
    """Diagnostic severity level."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class OperationState(str, Enum):
    """Lifecycle for async control-plane operations."""

    ACCEPTED = "accepted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStepLifecycle(str, Enum):
    """Portable execution lifecycle for workflow-visible step state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"


class WorkflowStepOutcome(str, Enum):
    """Portable execution outcomes for workflow-visible step state."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXHAUSTED = "exhausted"


class WorkflowStatus(str, Enum):
    """Portable workflow-level execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class WorkflowCompensationStatus(str, Enum):
    """Portable workflow compensation status."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class WorkflowHistoryEventType(str, Enum):
    """Portable workflow history event kinds."""

    WORKFLOW_STARTED = "workflow_started"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    SWITCH_CASE_SELECTED = "switch_case_selected"
    CALL_STARTED = "call_started"
    CALL_COMPLETED = "call_completed"
    BRANCH_ENTERED = "branch_entered"
    BRANCH_CONVERGED = "branch_converged"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    WORKFLOW_TIMED_OUT = "workflow_timed_out"
    COMPENSATION_REGISTERED = "compensation_registered"
    COMPENSATION_STARTED = "compensation_started"
    COMPENSATION_WORKFLOW_STARTED = "compensation_workflow_started"
    COMPENSATION_WORKFLOW_COMPLETED = "compensation_workflow_completed"
    COMPENSATION_WORKFLOW_FAILED = "compensation_workflow_failed"
    COMPENSATION_COMPLETED = "compensation_completed"
    COMPENSATION_FAILED = "compensation_failed"


class EvaluationResultStatus(str, Enum):
    """Portable lifecycle for evaluator-observable results."""

    PENDING = "pending"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


class EvaluationHistoryEventType(str, Enum):
    """Portable evaluator history event kinds."""

    EVALUATION_STARTED = "evaluation_started"
    EVALUATION_UPDATED = "evaluation_updated"
    EVALUATION_READY = "evaluation_ready"
    EVALUATION_FAILED = "evaluation_failed"


class ParticipantEpisodeStatus(str, Enum):
    """Portable lifecycle position for one participant episode instance."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    TERMINATED = "terminated"


class ParticipantEpisodeTerminalReason(str, Enum):
    """Portable terminal-reason classifier for participant episodes."""

    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    TRUNCATED = "truncated"
    INTERRUPTED = "interrupted"


class ParticipantEpisodeControlAction(str, Enum):
    """Portable control actions that drive participant-episode transitions."""

    INITIALIZE = "initialize"
    RESET = "reset"
    RESTART = "restart"


class ParticipantEpisodeHistoryEventType(str, Enum):
    """Portable history event kinds for participant episodes."""

    EPISODE_INITIALIZED = "episode_initialized"
    EPISODE_RUNNING = "episode_running"
    EPISODE_COMPLETED = "episode_completed"
    EPISODE_TIMED_OUT = "episode_timed_out"
    EPISODE_TRUNCATED = "episode_truncated"
    EPISODE_INTERRUPTED = "episode_interrupted"
    EPISODE_RESET = "episode_reset"
    EPISODE_RESTARTED = "episode_restarted"


class ParticipantBehaviorHistoryEventType(str, Enum):
    """Portable history event kinds for participant behavior semantics."""

    ACTION_ATTEMPTED = "action_attempted"
    STATE_TRANSITION_RECORDED = "state_transition_recorded"
    OBSERVATION_EMITTED = "observation_emitted"


class ParticipantObservationStatus(str, Enum):
    """Terminal interpretation of a participant observation event."""

    TERMINAL = "terminal"
    ORPHANED_ACTION = "orphaned_action"


class ParticipantActionPreconditionStatus(str, Enum):
    """Runtime resolution state for one SEM-211 action precondition."""

    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    UNRESOLVED = "unresolved"


class ParticipantActionResultStatus(str, Enum):
    """Portable local status for a SEM-211 participant action attempt."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHHELD = "withheld"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"
    UNKNOWN = "unknown"


_PARTICIPANT_EPISODE_TERMINAL_EVENTS: dict[
    ParticipantEpisodeHistoryEventType,
    ParticipantEpisodeTerminalReason,
] = {
    ParticipantEpisodeHistoryEventType.EPISODE_COMPLETED: ParticipantEpisodeTerminalReason.COMPLETED,
    ParticipantEpisodeHistoryEventType.EPISODE_TIMED_OUT: ParticipantEpisodeTerminalReason.TIMED_OUT,
    ParticipantEpisodeHistoryEventType.EPISODE_TRUNCATED: ParticipantEpisodeTerminalReason.TRUNCATED,
    ParticipantEpisodeHistoryEventType.EPISODE_INTERRUPTED: ParticipantEpisodeTerminalReason.INTERRUPTED,
}


_PARTICIPANT_EPISODE_CONTROL_EVENTS: dict[
    ParticipantEpisodeHistoryEventType,
    ParticipantEpisodeControlAction,
] = {
    ParticipantEpisodeHistoryEventType.EPISODE_INITIALIZED: ParticipantEpisodeControlAction.INITIALIZE,
    ParticipantEpisodeHistoryEventType.EPISODE_RESET: ParticipantEpisodeControlAction.RESET,
    ParticipantEpisodeHistoryEventType.EPISODE_RESTARTED: ParticipantEpisodeControlAction.RESTART,
}


@dataclass(frozen=True)
class Diagnostic:
    """Structured planner/runtime message."""

    code: str
    domain: str
    address: str
    message: str
    severity: Severity = Severity.ERROR

    @property
    def is_error(self) -> bool:
        return self.severity == Severity.ERROR


@dataclass(frozen=True)
class RuntimeTemplate:
    """Reusable SDL definition preserved in compiled form."""

    address: str
    name: str
    spec: dict[str, Any]


@dataclass(frozen=True)
class ResolvedResource:
    """Base class for bound runtime resources."""

    address: str
    name: str
    spec: dict[str, Any]
    ordering_dependencies: tuple[str, ...] = ()
    refresh_dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class NetworkRuntime(ResolvedResource):
    """Compiled switch/network deployment."""

    node_name: str = ""


@dataclass(frozen=True)
class NodeRuntime(ResolvedResource):
    """Compiled VM deployment."""

    node_name: str = ""
    node_type: str = ""
    os_family: str = ""
    count: int | str | None = None


@dataclass(frozen=True)
class FeatureBinding(ResolvedResource):
    """Feature template bound to a specific node role."""

    node_name: str = ""
    node_address: str = ""
    feature_name: str = ""
    template_address: str = ""
    role_name: str = ""


@dataclass(frozen=True)
class ConditionBinding(ResolvedResource):
    """Condition template bound to a specific node role."""

    node_name: str = ""
    node_address: str = ""
    condition_name: str = ""
    template_address: str = ""
    role_name: str = ""
    result_contract: "EvaluationResultContract" = field(
        default_factory=lambda: EvaluationResultContract(resource_type="condition-binding")
    )
    execution_contract: "EvaluationExecutionContract" = field(
        default_factory=lambda: EvaluationExecutionContract(resource_type="condition-binding")
    )


@dataclass(frozen=True)
class InjectBinding(ResolvedResource):
    """Inject template bound to a specific node role."""

    node_name: str = ""
    node_address: str = ""
    inject_name: str = ""
    template_address: str = ""
    role_name: str = ""


@dataclass(frozen=True)
class InjectRuntime(ResolvedResource):
    """Resolved top-level inject resource."""


@dataclass(frozen=True)
class ContentPlacement(ResolvedResource):
    """Content entry resolved to a concrete target node."""

    content_name: str = ""
    target_node: str = ""
    target_address: str = ""


@dataclass(frozen=True)
class AccountPlacement(ResolvedResource):
    """Account entry resolved to a concrete target node."""

    account_name: str = ""
    node_name: str = ""
    target_address: str = ""


@dataclass(frozen=True)
class ParticipantActionContractRuntime(ResolvedResource):
    """Compiled participant action contract."""

    action_name: str = ""
    semantic_version: str = ""
    lifecycle_state: str = ""
    behavioral_granularity: str = ""
    precondition_classes: tuple[str, ...] = ()
    effect_classes: tuple[str, ...] = ()
    failure_classes: tuple[str, ...] = ()
    backend_failure_mappings: tuple[dict[str, str], ...] = ()
    interaction_classes: tuple[str, ...] = ()
    shared_state_refs: tuple[str, ...] = ()
    temporal_contract_ids: tuple[str, ...] = ()
    temporal_kinds: tuple[str, ...] = ()
    time_domains: tuple[str, ...] = ()
    clock_authorities: tuple[str, ...] = ()
    backend_timing_disclosures: tuple[dict[str, Any], ...] = ()


def map_backend_diagnostic_to_participant_failure(
    diagnostic: Diagnostic | Mapping[str, Any] | str,
    contract: ParticipantActionContractRuntime,
) -> ParticipantFailureClass:
    """Map a backend diagnostic to a portable SEM-211 failure class."""

    if isinstance(diagnostic, Diagnostic):
        code = diagnostic.code
    elif isinstance(diagnostic, Mapping):
        code = str(diagnostic.get("code", ""))
    else:
        code = str(diagnostic)

    for mapping in contract.backend_failure_mappings:
        if mapping.get("backend_error_code") == code:
            return ParticipantFailureClass(str(mapping.get("failure_class", ParticipantFailureClass.UNKNOWN.value)))
    return ParticipantFailureClass.BACKEND_ERROR if code else ParticipantFailureClass.UNKNOWN


def _as_string_set(value: Any) -> set[str]:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
        return set()
    return {str(item) for item in value if isinstance(item, str) and item}


def _contract_sem211_precondition_refs(
    contract: ParticipantActionContractRuntime,
) -> dict[tuple[str, str], dict[str, set[str]]]:
    preconditions = contract.spec.get("preconditions", ())
    if isinstance(preconditions, (str, bytes, Mapping)) or not isinstance(preconditions, Iterable):
        return {}
    refs: dict[tuple[str, str], dict[str, set[str]]] = {}
    for item in preconditions:
        if not isinstance(item, Mapping) or not item.get("precondition_id") or not item.get("precondition_class"):
            continue
        key = (str(item.get("precondition_id", "")), str(item.get("precondition_class", "")))
        refs[key] = {
            "support_refs": _as_string_set(item.get("support_refs", ())),
            "evidence_refs": _as_string_set(item.get("evidence_refs", ())),
        }
    return refs


def _contract_sem211_effect_refs(
    contract: ParticipantActionContractRuntime,
) -> dict[tuple[str, str], dict[str, set[str]]]:
    effects = contract.spec.get("effects", ())
    if isinstance(effects, (str, bytes, Mapping)) or not isinstance(effects, Iterable):
        return {}
    refs: dict[tuple[str, str], dict[str, set[str]]] = {}
    for item in effects:
        if not isinstance(item, Mapping) or not item.get("effect_id") or not item.get("effect_class"):
            continue
        key = (str(item.get("effect_id", "")), str(item.get("effect_class", "")))
        refs[key] = {
            "target_refs": _as_string_set(item.get("target_refs", ())),
            "evidence_refs": _as_string_set(item.get("evidence_refs", ())),
        }
    return refs


def _contract_uses_sem211_action_results(contract: ParticipantActionContractRuntime) -> bool:
    return bool(contract.precondition_classes or contract.effect_classes or contract.failure_classes)


def validate_participant_action_result_contract(
    result: "ParticipantActionResult",
    contract: ParticipantActionContractRuntime,
) -> list[str]:
    """Return SEM-211 contract violations for one typed action result."""

    violations: list[str] = []
    if result.action_contract_address != contract.address:
        violations.append(
            "action_result action_contract_address "
            f"{result.action_contract_address!r} does not match compiled action contract {contract.address!r}"
        )
        return violations

    declared_precondition_classes = set(contract.precondition_classes)
    declared_effect_classes = set(contract.effect_classes)
    declared_failure_classes = set(contract.failure_classes)
    declared_precondition_refs = _contract_sem211_precondition_refs(contract)
    declared_effect_refs = _contract_sem211_effect_refs(contract)
    declared_preconditions = set(declared_precondition_refs)
    declared_effects = set(declared_effect_refs)
    reported_preconditions: set[tuple[str, str]] = set()

    for precondition in result.preconditions:
        precondition_key = (precondition.precondition_id, precondition.precondition_class.value)
        reported_preconditions.add(precondition_key)
        if precondition.precondition_class.value not in declared_precondition_classes:
            violations.append(
                f"action_result precondition {precondition.precondition_id!r} uses undeclared "
                f"precondition_class {precondition.precondition_class.value!r}"
            )
        if declared_preconditions and precondition_key not in declared_preconditions:
            violations.append(
                f"action_result precondition {precondition.precondition_id!r}/"
                f"{precondition.precondition_class.value!r} is not declared by {contract.address}"
            )
        declared_refs = declared_precondition_refs.get(precondition_key)
        if declared_refs is not None:
            undeclared_support_refs = set(precondition.support_refs) - declared_refs["support_refs"]
            undeclared_evidence_refs = set(precondition.evidence_refs) - declared_refs["evidence_refs"]
            for ref in sorted(undeclared_support_refs):
                violations.append(
                    f"action_result precondition {precondition.precondition_id!r} reports undeclared "
                    f"support_ref {ref!r}"
                )
            for ref in sorted(undeclared_evidence_refs):
                violations.append(
                    f"action_result precondition {precondition.precondition_id!r} reports undeclared "
                    f"evidence_ref {ref!r}"
                )
    for precondition_id, precondition_class in sorted(declared_preconditions - reported_preconditions):
        violations.append(
            f"action_result is missing declared precondition {precondition_id!r}/"
            f"{precondition_class!r} for {contract.address}"
        )

    for effect in result.effects:
        effect_key = (effect.effect_id, effect.effect_class.value)
        if effect.effect_class.value not in declared_effect_classes:
            violations.append(
                f"action_result effect {effect.effect_id!r} uses undeclared effect_class {effect.effect_class.value!r}"
            )
        if declared_effects and effect_key not in declared_effects:
            violations.append(
                f"action_result effect {effect.effect_id!r}/"
                f"{effect.effect_class.value!r} is not declared by {contract.address}"
            )
        declared_refs = declared_effect_refs.get(effect_key)
        if declared_refs is not None:
            undeclared_target_refs = set(effect.target_refs) - declared_refs["target_refs"]
            undeclared_evidence_refs = set(effect.evidence_refs) - declared_refs["evidence_refs"]
            for ref in sorted(undeclared_target_refs):
                violations.append(f"action_result effect {effect.effect_id!r} reports undeclared target_ref {ref!r}")
            for ref in sorted(undeclared_evidence_refs):
                violations.append(f"action_result effect {effect.effect_id!r} reports undeclared evidence_ref {ref!r}")

    declared_result_evidence_refs = {
        ref for declared_refs in declared_precondition_refs.values() for ref in declared_refs["evidence_refs"]
    } | {ref for declared_refs in declared_effect_refs.values() for ref in declared_refs["evidence_refs"]}
    reported_result_evidence_refs = {
        ref for precondition in result.preconditions for ref in precondition.evidence_refs
    } | {ref for effect in result.effects for ref in effect.evidence_refs}
    if declared_precondition_refs or declared_effect_refs:
        for ref in sorted(set(result.evidence_refs) - declared_result_evidence_refs):
            violations.append(f"action_result reports undeclared evidence_ref {ref!r}")
        for ref in sorted(set(result.evidence_refs) & declared_result_evidence_refs - reported_result_evidence_refs):
            violations.append(
                f"action_result evidence_ref {ref!r} is not grounded in reported precondition or effect evidence_refs"
            )

    if result.failure_class is not None and result.failure_class.value not in declared_failure_classes:
        violations.append(
            f"action_result failure_class {result.failure_class.value!r} is not declared by {contract.address}"
        )
    return violations


@dataclass(frozen=True)
class ParticipantObservationBoundaryRuntime(ResolvedResource):
    """Compiled participant observation projection boundary."""

    boundary_name: str = ""
    projection_basis: str = ""
    hidden_refs: tuple[str, ...] = ()
    observable_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    disclosed_refs: tuple[str, ...] = ()
    evidence_only_refs: tuple[str, ...] = ()
    discovered_refs: tuple[str, ...] = ()
    inferred_refs: tuple[str, ...] = ()
    concealed_refs: tuple[str, ...] = ()
    deceptive_refs: tuple[str, ...] = ()
    view_transitions: tuple[dict[str, Any], ...] = ()
    view_relation_timeline: tuple[dict[str, Any], ...] = ()
    realized_view_disclosure: str = ""


@dataclass(frozen=True)
class ParticipantBehaviorRuntime(ResolvedResource):
    """Compiled role-neutral participant behavior binding."""

    participant_name: str = ""
    entity_name: str = ""
    action_contract_addresses: tuple[str, ...] = ()
    observation_boundary_addresses: tuple[str, ...] = ()
    interpretation_mode: str = "role-neutral-projection"


@dataclass(frozen=True)
class EventRuntime(ResolvedResource):
    """Resolved orchestration event."""

    condition_names: tuple[str, ...] = ()
    condition_addresses: tuple[str, ...] = ()
    inject_names: tuple[str, ...] = ()
    inject_addresses: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScriptRuntime(ResolvedResource):
    """Resolved script with event dependencies."""

    event_addresses: tuple[str, ...] = ()


@dataclass(frozen=True)
class StoryRuntime(ResolvedResource):
    """Resolved story with script dependencies."""

    script_addresses: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObjectiveWindowReferenceRuntime:
    """Normalized resolved objective/window reference."""

    raw: str
    canonical_name: str
    reference_kind: str
    dependency_roles: tuple[str, ...] = ()
    workflow_name: str = ""
    step_name: str = ""
    namespace_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowStepStatePredicateRuntime:
    """Resolved predicate clause over prior workflow step state."""

    step_name: str
    outcomes: tuple[WorkflowStepOutcome, ...] = ()
    min_attempts: int | str | None = None


@dataclass(frozen=True)
class WorkflowPredicateRuntime:
    """Resolved workflow predicate semantics."""

    condition_addresses: tuple[str, ...] = ()
    metric_addresses: tuple[str, ...] = ()
    evaluation_addresses: tuple[str, ...] = ()
    tlo_addresses: tuple[str, ...] = ()
    goal_addresses: tuple[str, ...] = ()
    objective_addresses: tuple[str, ...] = ()
    step_state_predicates: tuple[WorkflowStepStatePredicateRuntime, ...] = ()

    @property
    def external_addresses(self) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for address in (
            *self.condition_addresses,
            *self.metric_addresses,
            *self.evaluation_addresses,
            *self.tlo_addresses,
            *self.goal_addresses,
            *self.objective_addresses,
        ):
            if address in seen:
                continue
            seen.add(address)
            ordered.append(address)
        return tuple(ordered)


@dataclass(frozen=True)
class WorkflowSwitchCaseRuntime:
    """Resolved ordered switch-case branch semantics."""

    case_index: int
    predicate: WorkflowPredicateRuntime
    next_step: str


@dataclass(frozen=True)
class WorkflowStepRuntime:
    """Resolved workflow step semantics."""

    name: str
    step_type: str
    objective_address: str = ""
    predicate: WorkflowPredicateRuntime | None = None
    next_step: str = ""
    on_success: str = ""
    on_failure: str = ""
    on_exhausted: str = ""
    then_step: str = ""
    else_step: str = ""
    switch_cases: tuple[WorkflowSwitchCaseRuntime, ...] = ()
    default_step: str = ""
    branches: tuple[str, ...] = ()
    join_step: str = ""
    owning_parallel_step: str = ""
    called_workflow_address: str = ""
    compensation_workflow_address: str = ""
    max_attempts: int | str | None = None
    state_contract: WorkflowStepSemanticContract = field(
        default_factory=lambda: WorkflowStepSemanticContract(step_type="")
    )


@dataclass(frozen=True)
class WorkflowRuntime(ResolvedResource):
    """Resolved workflow control program."""

    start_step: str = ""
    referenced_objective_addresses: tuple[str, ...] = ()
    control_steps: dict[str, WorkflowStepRuntime] = field(default_factory=dict)
    control_edges: dict[str, tuple[str, ...]] = field(default_factory=dict)
    join_owners: dict[str, str] = field(default_factory=dict)
    step_condition_addresses: dict[str, tuple[str, ...]] = field(default_factory=dict)
    step_predicate_addresses: dict[str, tuple[str, ...]] = field(default_factory=dict)
    required_features: tuple[WorkflowFeature, ...] = ()
    required_state_predicate_features: tuple[WorkflowStatePredicateFeature, ...] = ()
    result_contract: "WorkflowResultContract" = field(default_factory=lambda: WorkflowResultContract())
    execution_contract: "WorkflowExecutionContract" = field(default_factory=lambda: WorkflowExecutionContract())
    state_schema_version: str = WORKFLOW_STATE_SCHEMA_VERSION


@dataclass(frozen=True)
class WorkflowResultContract:
    """Compiled contract for validating portable workflow result envelopes."""

    state_schema_version: str = WORKFLOW_STATE_SCHEMA_VERSION
    observable_steps: dict[str, WorkflowStepSemanticContract] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.state_schema_version, str) or not self.state_schema_version:
            raise TypeError("workflow result contract state_schema_version must be a non-empty string")
        if not isinstance(self.observable_steps, dict):
            raise TypeError("workflow result contract observable_steps must be a dict")
        if any(not isinstance(step_name, str) for step_name in self.observable_steps):
            raise TypeError("workflow result contract step names must be strings")
        if any(not isinstance(contract, WorkflowStepSemanticContract) for contract in self.observable_steps.values()):
            raise TypeError("workflow result contract step contracts must be WorkflowStepSemanticContract values")

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
    ) -> "WorkflowResultContract":
        if not isinstance(payload, Mapping):
            raise TypeError("workflow result contract must be a mapping")
        observable_steps_payload = payload.get("observable_steps", {})
        if not isinstance(observable_steps_payload, Mapping):
            raise TypeError("workflow result contract observable_steps must be a mapping")
        observable_steps: dict[str, WorkflowStepSemanticContract] = {}
        for step_name, step_payload in observable_steps_payload.items():
            if not isinstance(step_name, str):
                raise TypeError("workflow result contract step names must be strings")
            if not isinstance(step_payload, Mapping):
                raise TypeError("workflow result contract step payloads must be mappings")
            observable_steps[step_name] = WorkflowStepSemanticContract.from_mapping(step_payload)
            if not observable_steps[step_name].state_observable:
                raise ValueError("workflow result contract may only include observable steps")
        return cls(
            state_schema_version=str(payload.get("state_schema_version", WORKFLOW_STATE_SCHEMA_VERSION)),
            observable_steps=observable_steps,
        )


@dataclass(frozen=True)
class WorkflowExecutionContract:
    """Compiled contract for validating workflow-level execution state/history."""

    state_schema_version: str = WORKFLOW_STATE_SCHEMA_VERSION
    start_step: str = ""
    timeout_seconds: int | None = None
    steps: dict[str, WorkflowStepSemanticContract] = field(default_factory=dict)
    step_types: dict[str, str] = field(default_factory=dict)
    control_edges: dict[str, tuple[str, ...]] = field(default_factory=dict)
    join_owners: dict[str, str] = field(default_factory=dict)
    call_steps: dict[str, str] = field(default_factory=dict)
    compensation_mode: str = "disabled"
    compensation_triggers: tuple[str, ...] = ()
    compensation_targets: dict[str, str] = field(default_factory=dict)
    compensation_ordering: str = "reverse_completion"
    compensation_failure_policy: str = "fail_workflow"
    observable_steps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.state_schema_version, str) or not self.state_schema_version:
            raise TypeError("workflow execution contract state_schema_version must be a non-empty string")
        if not isinstance(self.start_step, str):
            raise TypeError("workflow execution contract start_step must be a string")
        if self.timeout_seconds is not None:
            if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, int):
                raise TypeError("workflow execution contract timeout_seconds must be an int or None")
            if self.timeout_seconds <= 0:
                raise ValueError("workflow execution contract timeout_seconds must be > 0")
        if not isinstance(self.steps, dict):
            raise TypeError("workflow execution contract steps must be a dict")
        if any(not isinstance(name, str) for name in self.steps):
            raise TypeError("workflow execution contract step names must be strings")
        if any(not isinstance(contract, WorkflowStepSemanticContract) for contract in self.steps.values()):
            raise TypeError("workflow execution contract step contracts must be WorkflowStepSemanticContract values")
        if not isinstance(self.step_types, dict):
            raise TypeError("workflow execution contract step_types must be a dict")
        if any(
            not isinstance(name, str) or not isinstance(step_type, str) for name, step_type in self.step_types.items()
        ):
            raise TypeError("workflow execution contract step_types must map strings to strings")
        if not isinstance(self.control_edges, dict):
            raise TypeError("workflow execution contract control_edges must be a dict")
        if not isinstance(self.join_owners, dict):
            raise TypeError("workflow execution contract join_owners must be a dict")
        if not isinstance(self.call_steps, dict):
            raise TypeError("workflow execution contract call_steps must be a dict")
        if any(
            not isinstance(step_name, str) or not isinstance(workflow_address, str)
            for step_name, workflow_address in self.call_steps.items()
        ):
            raise TypeError("workflow execution contract call_steps must map strings to strings")
        if not isinstance(self.compensation_mode, str):
            raise TypeError("workflow execution contract compensation_mode must be a string")
        if any(not isinstance(trigger, str) for trigger in self.compensation_triggers):
            raise TypeError("workflow execution contract compensation_triggers must be strings")
        if not isinstance(self.compensation_targets, dict):
            raise TypeError("workflow execution contract compensation_targets must be a dict")
        if any(
            not isinstance(step_name, str) or not isinstance(workflow_address, str)
            for step_name, workflow_address in self.compensation_targets.items()
        ):
            raise TypeError("workflow execution contract compensation_targets must map strings to strings")
        if not isinstance(self.compensation_ordering, str):
            raise TypeError("workflow execution contract compensation_ordering must be a string")
        if not isinstance(self.compensation_failure_policy, str):
            raise TypeError("workflow execution contract compensation_failure_policy must be a string")
        if any(not isinstance(step_name, str) for step_name in self.observable_steps):
            raise TypeError("workflow execution contract observable_steps must be strings")

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
    ) -> "WorkflowExecutionContract":
        if not isinstance(payload, Mapping):
            raise TypeError("workflow execution contract must be a mapping")
        steps_payload = payload.get("steps", {})
        if not isinstance(steps_payload, Mapping):
            raise TypeError("workflow execution contract steps must be a mapping")
        steps: dict[str, WorkflowStepSemanticContract] = {}
        for step_name, step_payload in steps_payload.items():
            if not isinstance(step_name, str):
                raise TypeError("workflow execution contract step names must be strings")
            if not isinstance(step_payload, Mapping):
                raise TypeError("workflow execution contract step payloads must be mappings")
            steps[step_name] = WorkflowStepSemanticContract.from_mapping(step_payload)
        control_edges_payload = payload.get("control_edges", {})
        if not isinstance(control_edges_payload, Mapping):
            raise TypeError("workflow execution contract control_edges must be a mapping")
        control_edges = {
            str(step_name): tuple(str(successor) for successor in successors)
            for step_name, successors in control_edges_payload.items()
            if isinstance(successors, Iterable)
        }
        join_owners_payload = payload.get("join_owners", {})
        if not isinstance(join_owners_payload, Mapping):
            raise TypeError("workflow execution contract join_owners must be a mapping")
        return cls(
            state_schema_version=str(payload.get("state_schema_version", WORKFLOW_STATE_SCHEMA_VERSION)),
            start_step=str(payload.get("start_step", "")),
            timeout_seconds=(int(payload["timeout_seconds"]) if payload.get("timeout_seconds") is not None else None),
            steps=steps,
            step_types={
                str(step_name): str(step_type) for step_name, step_type in payload.get("step_types", {}).items()
            },
            control_edges=control_edges,
            join_owners={str(join): str(owner) for join, owner in join_owners_payload.items()},
            call_steps={
                str(step_name): str(workflow_address)
                for step_name, workflow_address in payload.get("call_steps", {}).items()
            },
            compensation_mode=str(payload.get("compensation_mode", "disabled")),
            compensation_triggers=tuple(str(trigger) for trigger in payload.get("compensation_triggers", ())),
            compensation_targets={
                str(step_name): str(workflow_address)
                for step_name, workflow_address in payload.get("compensation_targets", {}).items()
            },
            compensation_ordering=str(payload.get("compensation_ordering", "reverse_completion")),
            compensation_failure_policy=str(payload.get("compensation_failure_policy", "fail_workflow")),
            observable_steps=tuple(str(step_name) for step_name in payload.get("observable_steps", ())),
        )


@dataclass(frozen=True)
class WorkflowHistoryEvent:
    """Internal normalized workflow history event."""

    event_type: WorkflowHistoryEventType
    timestamp: str
    step_name: str | None = None
    branch_name: str | None = None
    join_step: str | None = None
    outcome: WorkflowStepOutcome | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "WorkflowHistoryEvent":
        if not isinstance(payload, Mapping):
            raise TypeError("workflow history event must be a mapping")
        event_type_raw = payload.get("event_type")
        timestamp_raw = payload.get("timestamp")
        if event_type_raw is None or timestamp_raw is None:
            raise ValueError("workflow history event is missing required fields: event_type, timestamp")
        outcome_raw = payload.get("outcome")
        return cls(
            event_type=(
                event_type_raw
                if isinstance(event_type_raw, WorkflowHistoryEventType)
                else WorkflowHistoryEventType(str(event_type_raw))
            ),
            timestamp=str(timestamp_raw),
            step_name=(str(payload["step_name"]) if payload.get("step_name") is not None else None),
            branch_name=(str(payload["branch_name"]) if payload.get("branch_name") is not None else None),
            join_step=(str(payload["join_step"]) if payload.get("join_step") is not None else None),
            outcome=(
                outcome_raw
                if isinstance(outcome_raw, WorkflowStepOutcome)
                else (WorkflowStepOutcome(str(outcome_raw)) if outcome_raw is not None else None)
            ),
            details=dict(payload.get("details", {})) if isinstance(payload.get("details", {}), Mapping) else {},
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "step_name": self.step_name,
            "branch_name": self.branch_name,
            "join_step": self.join_step,
            "outcome": self.outcome.value if self.outcome is not None else None,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class WorkflowStepExecutionState:
    """Internal normalized execution state for one workflow-visible step."""

    lifecycle: WorkflowStepLifecycle = WorkflowStepLifecycle.PENDING
    outcome: WorkflowStepOutcome | None = None
    attempts: int = 0

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "WorkflowStepExecutionState":
        if not isinstance(payload, Mapping):
            raise TypeError("workflow step result must be a mapping")
        missing_keys = [key for key in ("lifecycle", "outcome", "attempts") if key not in payload]
        if missing_keys:
            raise ValueError("workflow step result is missing required fields: " + ", ".join(missing_keys))
        lifecycle_raw = payload.get("lifecycle")
        outcome_raw = payload.get("outcome")
        attempts_raw = payload.get("attempts")
        lifecycle = (
            lifecycle_raw
            if isinstance(lifecycle_raw, WorkflowStepLifecycle)
            else WorkflowStepLifecycle(str(lifecycle_raw))
        )
        outcome = None
        if outcome_raw is not None:
            outcome = (
                outcome_raw if isinstance(outcome_raw, WorkflowStepOutcome) else WorkflowStepOutcome(str(outcome_raw))
            )
        if isinstance(attempts_raw, bool) or not isinstance(attempts_raw, int):
            raise TypeError("workflow step attempts must be an int")
        return cls(
            lifecycle=lifecycle,
            outcome=outcome,
            attempts=attempts_raw,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "lifecycle": self.lifecycle.value,
            "outcome": self.outcome.value if self.outcome is not None else None,
            "attempts": self.attempts,
        }

    def __post_init__(self) -> None:
        if not isinstance(self.lifecycle, WorkflowStepLifecycle):
            raise TypeError("lifecycle must be a WorkflowStepLifecycle")
        if self.outcome is not None and not isinstance(self.outcome, WorkflowStepOutcome):
            raise TypeError("outcome must be a WorkflowStepOutcome or None")
        if isinstance(self.attempts, bool) or not isinstance(self.attempts, int):
            raise TypeError("attempts must be an int")
        if self.attempts < 0:
            raise ValueError("attempts must be >= 0")
        if self.lifecycle != WorkflowStepLifecycle.COMPLETED and self.outcome is not None:
            raise ValueError("non-completed workflow steps may not report an outcome")
        if self.lifecycle == WorkflowStepLifecycle.PENDING and self.attempts != 0:
            raise ValueError("pending workflow steps must report 0 attempts")


@dataclass(frozen=True)
class WorkflowExecutionState:
    """Internal normalized workflow result envelope."""

    state_schema_version: str = WORKFLOW_STATE_SCHEMA_VERSION
    workflow_status: WorkflowStatus = WorkflowStatus.PENDING
    run_id: str = ""
    started_at: str = ""
    updated_at: str = ""
    terminal_reason: str | None = None
    compensation_status: WorkflowCompensationStatus = WorkflowCompensationStatus.NOT_REQUIRED
    compensation_started_at: str | None = None
    compensation_updated_at: str | None = None
    compensation_failures: list[dict[str, Any]] = field(default_factory=list)
    steps: dict[str, WorkflowStepExecutionState] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "WorkflowExecutionState":
        if not isinstance(payload, Mapping):
            raise TypeError("workflow result payload must be a mapping")
        missing_keys = [
            key
            for key in (
                "state_schema_version",
                "workflow_status",
                "run_id",
                "started_at",
                "updated_at",
                "compensation_status",
                "compensation_failures",
                "steps",
            )
            if key not in payload
        ]
        if missing_keys:
            raise ValueError("workflow result payload is missing required fields: " + ", ".join(missing_keys))
        state_schema_version = str(payload.get("state_schema_version"))
        workflow_status_raw = payload.get("workflow_status")
        steps_payload = payload.get("steps")
        if not isinstance(steps_payload, Mapping):
            raise TypeError("workflow result steps must be a mapping")
        steps: dict[str, WorkflowStepExecutionState] = {}
        for step_name, step_payload in steps_payload.items():
            if not isinstance(step_name, str):
                raise TypeError("workflow result step names must be strings")
            if not isinstance(step_payload, Mapping):
                raise TypeError("workflow result step payloads must be mappings")
            steps[step_name] = WorkflowStepExecutionState.from_payload(step_payload)
        return cls(
            state_schema_version=state_schema_version,
            workflow_status=(
                workflow_status_raw
                if isinstance(workflow_status_raw, WorkflowStatus)
                else WorkflowStatus(str(workflow_status_raw))
            ),
            run_id=str(payload.get("run_id")),
            started_at=str(payload.get("started_at")),
            updated_at=str(payload.get("updated_at")),
            terminal_reason=(str(payload["terminal_reason"]) if payload.get("terminal_reason") is not None else None),
            compensation_status=(
                payload.get("compensation_status")
                if isinstance(payload.get("compensation_status"), WorkflowCompensationStatus)
                else WorkflowCompensationStatus(str(payload.get("compensation_status")))
            ),
            compensation_started_at=(
                str(payload["compensation_started_at"]) if payload.get("compensation_started_at") is not None else None
            ),
            compensation_updated_at=(
                str(payload["compensation_updated_at"]) if payload.get("compensation_updated_at") is not None else None
            ),
            compensation_failures=[
                dict(item) for item in payload.get("compensation_failures", []) if isinstance(item, Mapping)
            ],
            steps=steps,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "state_schema_version": self.state_schema_version,
            "workflow_status": self.workflow_status.value,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "terminal_reason": self.terminal_reason,
            "compensation_status": self.compensation_status.value,
            "compensation_started_at": self.compensation_started_at,
            "compensation_updated_at": self.compensation_updated_at,
            "compensation_failures": [dict(item) for item in self.compensation_failures],
            "steps": {step_name: step_state.to_payload() for step_name, step_state in self.steps.items()},
        }

    def __post_init__(self) -> None:
        if not isinstance(self.state_schema_version, str) or not self.state_schema_version:
            raise TypeError("workflow result state_schema_version must be a non-empty string")
        if not isinstance(self.workflow_status, WorkflowStatus):
            raise TypeError("workflow_status must be a WorkflowStatus")
        if not isinstance(self.run_id, str) or not self.run_id:
            raise TypeError("run_id must be a non-empty string")
        if not isinstance(self.started_at, str) or not self.started_at:
            raise TypeError("started_at must be a non-empty string")
        if not isinstance(self.updated_at, str) or not self.updated_at:
            raise TypeError("updated_at must be a non-empty string")
        if self.terminal_reason is not None and not isinstance(self.terminal_reason, str):
            raise TypeError("terminal_reason must be a string or None")
        if not isinstance(self.compensation_status, WorkflowCompensationStatus):
            raise TypeError("compensation_status must be a WorkflowCompensationStatus")
        if self.compensation_started_at is not None and not isinstance(self.compensation_started_at, str):
            raise TypeError("compensation_started_at must be a string or None")
        if self.compensation_updated_at is not None and not isinstance(self.compensation_updated_at, str):
            raise TypeError("compensation_updated_at must be a string or None")
        if not isinstance(self.compensation_failures, list):
            raise TypeError("compensation_failures must be a list")
        if any(not isinstance(item, dict) for item in self.compensation_failures):
            raise TypeError("compensation_failures entries must be dicts")
        if not isinstance(self.steps, dict):
            raise TypeError("workflow step results must be stored in a dict")
        if any(not isinstance(step_name, str) for step_name in self.steps):
            raise TypeError("workflow step result keys must be strings")
        if any(not isinstance(step_state, WorkflowStepExecutionState) for step_state in self.steps.values()):
            raise TypeError("workflow step results must be WorkflowStepExecutionState values")
        if (
            self.workflow_status
            in {
                WorkflowStatus.SUCCEEDED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
                WorkflowStatus.TIMED_OUT,
            }
            and self.terminal_reason is None
        ):
            raise ValueError("terminal workflow statuses must include terminal_reason")
        if (
            self.workflow_status in {WorkflowStatus.PENDING, WorkflowStatus.RUNNING}
            and self.terminal_reason is not None
        ):
            raise ValueError("non-terminal workflow statuses may not include terminal_reason")
        if self.workflow_status in {WorkflowStatus.PENDING, WorkflowStatus.RUNNING}:
            if self.compensation_status != WorkflowCompensationStatus.NOT_REQUIRED:
                raise ValueError("non-terminal workflow statuses may not report compensation activity")
            if self.compensation_started_at is not None or self.compensation_updated_at is not None:
                raise ValueError("non-terminal workflow statuses may not report compensation timestamps")
        if self.compensation_status == WorkflowCompensationStatus.NOT_REQUIRED:
            if self.compensation_started_at is not None or self.compensation_updated_at is not None:
                raise ValueError("compensation_status=not_required may not report compensation timestamps")
            if self.compensation_failures:
                raise ValueError("compensation_status=not_required may not report compensation failures")
        if self.compensation_status == WorkflowCompensationStatus.RUNNING:
            if self.compensation_started_at is None:
                raise ValueError("compensation_status=running requires compensation_started_at")


@dataclass(frozen=True)
class EvaluationResultContract:
    """Compiled contract for validating evaluator result envelopes."""

    state_schema_version: str = EVALUATION_STATE_SCHEMA_VERSION
    resource_type: str = ""
    supports_passed: bool = False
    supports_score: bool = False
    fixed_max_score: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state_schema_version, str) or not self.state_schema_version:
            raise TypeError("evaluation result contract state_schema_version must be a non-empty string")
        if not isinstance(self.resource_type, str) or not self.resource_type:
            raise TypeError("evaluation result contract resource_type must be a non-empty string")
        if not isinstance(self.supports_passed, bool):
            raise TypeError("evaluation result contract supports_passed must be a bool")
        if not isinstance(self.supports_score, bool):
            raise TypeError("evaluation result contract supports_score must be a bool")
        if self.fixed_max_score is not None:
            if isinstance(self.fixed_max_score, bool) or not isinstance(self.fixed_max_score, int):
                raise TypeError("evaluation result contract fixed_max_score must be an int or None")
            if self.fixed_max_score < 0:
                raise ValueError("evaluation result contract fixed_max_score must be >= 0")
            if not self.supports_score:
                raise ValueError("evaluation result contract fixed_max_score requires supports_score")

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
    ) -> "EvaluationResultContract":
        if not isinstance(payload, Mapping):
            raise TypeError("evaluation result contract must be a mapping")
        fixed_max_score_raw = payload.get("fixed_max_score")
        fixed_max_score: int | None
        if fixed_max_score_raw is None:
            fixed_max_score = None
        elif isinstance(fixed_max_score_raw, bool) or not isinstance(fixed_max_score_raw, int):
            raise TypeError("evaluation result contract fixed_max_score must be an int or None")
        else:
            fixed_max_score = fixed_max_score_raw
        return cls(
            state_schema_version=str(payload.get("state_schema_version", EVALUATION_STATE_SCHEMA_VERSION)),
            resource_type=str(payload.get("resource_type", "")),
            supports_passed=bool(payload.get("supports_passed", False)),
            supports_score=bool(payload.get("supports_score", False)),
            fixed_max_score=fixed_max_score,
        )


@dataclass(frozen=True)
class EvaluationExecutionContract:
    """Compiled contract for validating evaluator history/state transitions."""

    state_schema_version: str = EVALUATION_STATE_SCHEMA_VERSION
    resource_type: str = ""
    allowed_statuses: tuple[str, ...] = (
        EvaluationResultStatus.PENDING.value,
        EvaluationResultStatus.RUNNING.value,
        EvaluationResultStatus.READY.value,
        EvaluationResultStatus.FAILED.value,
    )
    history_event_types: tuple[str, ...] = (
        EvaluationHistoryEventType.EVALUATION_STARTED.value,
        EvaluationHistoryEventType.EVALUATION_UPDATED.value,
        EvaluationHistoryEventType.EVALUATION_READY.value,
        EvaluationHistoryEventType.EVALUATION_FAILED.value,
    )
    requires_start_event: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.state_schema_version, str) or not self.state_schema_version:
            raise TypeError("evaluation execution contract state_schema_version must be a non-empty string")
        if not isinstance(self.resource_type, str) or not self.resource_type:
            raise TypeError("evaluation execution contract resource_type must be a non-empty string")
        if any(not isinstance(status, str) for status in self.allowed_statuses):
            raise TypeError("evaluation execution contract allowed_statuses must be strings")
        if any(not isinstance(event_type, str) for event_type in self.history_event_types):
            raise TypeError("evaluation execution contract history_event_types must be strings")
        if not isinstance(self.requires_start_event, bool):
            raise TypeError("evaluation execution contract requires_start_event must be a bool")

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
    ) -> "EvaluationExecutionContract":
        if not isinstance(payload, Mapping):
            raise TypeError("evaluation execution contract must be a mapping")
        return cls(
            state_schema_version=str(payload.get("state_schema_version", EVALUATION_STATE_SCHEMA_VERSION)),
            resource_type=str(payload.get("resource_type", "")),
            allowed_statuses=tuple(
                str(status)
                for status in payload.get(
                    "allowed_statuses",
                    (
                        EvaluationResultStatus.PENDING.value,
                        EvaluationResultStatus.RUNNING.value,
                        EvaluationResultStatus.READY.value,
                        EvaluationResultStatus.FAILED.value,
                    ),
                )
            ),
            history_event_types=tuple(
                str(event_type)
                for event_type in payload.get(
                    "history_event_types",
                    (
                        EvaluationHistoryEventType.EVALUATION_STARTED.value,
                        EvaluationHistoryEventType.EVALUATION_UPDATED.value,
                        EvaluationHistoryEventType.EVALUATION_READY.value,
                        EvaluationHistoryEventType.EVALUATION_FAILED.value,
                    ),
                )
            ),
            requires_start_event=bool(payload.get("requires_start_event", True)),
        )


@dataclass(frozen=True)
class EvaluationHistoryEvent:
    """Internal normalized evaluator history event."""

    event_type: EvaluationHistoryEventType
    timestamp: str
    status: EvaluationResultStatus
    passed: bool | None = None
    score: float | int | None = None
    max_score: int | None = None
    detail: str | None = None
    evidence_refs: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "EvaluationHistoryEvent":
        if not isinstance(payload, Mapping):
            raise TypeError("evaluation history event must be a mapping")
        missing_keys = [key for key in ("event_type", "timestamp", "status") if key not in payload]
        if missing_keys:
            raise ValueError("evaluation history event is missing required fields: " + ", ".join(missing_keys))
        score_raw = payload.get("score")
        max_score_raw = payload.get("max_score")
        evidence_refs_raw = payload.get("evidence_refs", ())
        if isinstance(evidence_refs_raw, (str, bytes)) or not isinstance(evidence_refs_raw, Iterable):
            raise TypeError("evaluation history event evidence_refs must be an iterable of strings")
        evidence_ref_items = list(evidence_refs_raw)
        evidence_refs = tuple(str(ref) for ref in evidence_ref_items if isinstance(ref, str))
        if len(evidence_refs) != len(evidence_ref_items):
            raise TypeError("evaluation history event evidence_refs must contain only strings")
        return cls(
            event_type=(
                payload["event_type"]
                if isinstance(payload["event_type"], EvaluationHistoryEventType)
                else EvaluationHistoryEventType(str(payload["event_type"]))
            ),
            timestamp=str(payload["timestamp"]),
            status=(
                payload["status"]
                if isinstance(payload["status"], EvaluationResultStatus)
                else EvaluationResultStatus(str(payload["status"]))
            ),
            passed=(payload.get("passed") if isinstance(payload.get("passed"), bool) else None),
            score=(score_raw if isinstance(score_raw, (int, float)) and not isinstance(score_raw, bool) else None),
            max_score=(
                max_score_raw if isinstance(max_score_raw, int) and not isinstance(max_score_raw, bool) else None
            ),
            detail=(str(payload["detail"]) if payload.get("detail") is not None else None),
            evidence_refs=evidence_refs,
            details=dict(payload.get("details", {})) if isinstance(payload.get("details", {}), Mapping) else {},
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "passed": self.passed,
            "score": self.score,
            "max_score": self.max_score,
            "detail": self.detail,
            "evidence_refs": list(self.evidence_refs),
            "details": dict(self.details),
        }

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, EvaluationHistoryEventType):
            raise TypeError("event_type must be an EvaluationHistoryEventType")
        if not isinstance(self.timestamp, str) or not self.timestamp:
            raise TypeError("timestamp must be a non-empty string")
        if not isinstance(self.status, EvaluationResultStatus):
            raise TypeError("status must be an EvaluationResultStatus")
        if self.passed is not None and not isinstance(self.passed, bool):
            raise TypeError("passed must be a bool or None")
        if self.score is not None and (isinstance(self.score, bool) or not isinstance(self.score, (int, float))):
            raise TypeError("score must be numeric or None")
        if self.max_score is not None and (isinstance(self.max_score, bool) or not isinstance(self.max_score, int)):
            raise TypeError("max_score must be an int or None")
        if self.detail is not None and not isinstance(self.detail, str):
            raise TypeError("detail must be a string or None")
        if any(not isinstance(ref, str) for ref in self.evidence_refs):
            raise TypeError("evidence_refs must contain only strings")
        if not isinstance(self.details, dict):
            raise TypeError("details must be a dict")
        if self.status in {
            EvaluationResultStatus.PENDING,
            EvaluationResultStatus.RUNNING,
            EvaluationResultStatus.FAILED,
        }:
            if self.passed is not None or self.score is not None or self.max_score is not None:
                raise ValueError("pending/running/failed evaluation history events may not report result values")
        if self.status == EvaluationResultStatus.READY:
            if self.passed is None and self.score is None:
                raise ValueError("ready evaluation history events must report passed or score")
        if self.max_score is not None and self.score is None:
            raise ValueError("evaluation history events may not report max_score without score")


@dataclass(frozen=True)
class EvaluationExecutionState:
    """Internal normalized execution state for one evaluator-observable resource."""

    state_schema_version: str = EVALUATION_STATE_SCHEMA_VERSION
    resource_type: str = ""
    run_id: str = ""
    status: EvaluationResultStatus = EvaluationResultStatus.PENDING
    observed_at: str = ""
    updated_at: str = ""
    passed: bool | None = None
    score: float | int | None = None
    max_score: int | None = None
    detail: str | None = None
    evidence_refs: tuple[str, ...] = ()

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "EvaluationExecutionState":
        if not isinstance(payload, Mapping):
            raise TypeError("evaluation result payload must be a mapping")
        missing_keys = [
            key
            for key in (
                "state_schema_version",
                "resource_type",
                "run_id",
                "status",
                "observed_at",
                "updated_at",
            )
            if key not in payload
        ]
        if missing_keys:
            raise ValueError("evaluation result payload is missing required fields: " + ", ".join(missing_keys))
        score_raw = payload.get("score")
        max_score_raw = payload.get("max_score")
        evidence_refs_raw = payload.get("evidence_refs", ())
        if isinstance(evidence_refs_raw, (str, bytes)) or not isinstance(evidence_refs_raw, Iterable):
            raise TypeError("evaluation result evidence_refs must be an iterable of strings")
        evidence_ref_items = list(evidence_refs_raw)
        evidence_refs = tuple(str(ref) for ref in evidence_ref_items if isinstance(ref, str))
        if len(evidence_refs) != len(evidence_ref_items):
            raise TypeError("evaluation result evidence_refs must contain only strings")
        return cls(
            state_schema_version=str(payload["state_schema_version"]),
            resource_type=str(payload["resource_type"]),
            run_id=str(payload["run_id"]),
            status=(
                payload["status"]
                if isinstance(payload["status"], EvaluationResultStatus)
                else EvaluationResultStatus(str(payload["status"]))
            ),
            observed_at=str(payload["observed_at"]),
            updated_at=str(payload["updated_at"]),
            passed=(payload.get("passed") if isinstance(payload.get("passed"), bool) else None),
            score=(score_raw if isinstance(score_raw, (int, float)) and not isinstance(score_raw, bool) else None),
            max_score=(
                max_score_raw if isinstance(max_score_raw, int) and not isinstance(max_score_raw, bool) else None
            ),
            detail=(str(payload["detail"]) if payload.get("detail") is not None else None),
            evidence_refs=evidence_refs,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "state_schema_version": self.state_schema_version,
            "resource_type": self.resource_type,
            "run_id": self.run_id,
            "status": self.status.value,
            "observed_at": self.observed_at,
            "updated_at": self.updated_at,
            "passed": self.passed,
            "score": self.score,
            "max_score": self.max_score,
            "detail": self.detail,
            "evidence_refs": list(self.evidence_refs),
        }

    def __post_init__(self) -> None:
        if not isinstance(self.state_schema_version, str) or not self.state_schema_version:
            raise TypeError("evaluation result state_schema_version must be a non-empty string")
        if not isinstance(self.resource_type, str) or not self.resource_type:
            raise TypeError("evaluation result resource_type must be a non-empty string")
        if not isinstance(self.run_id, str) or not self.run_id:
            raise TypeError("evaluation result run_id must be a non-empty string")
        if not isinstance(self.status, EvaluationResultStatus):
            raise TypeError("status must be an EvaluationResultStatus")
        if not isinstance(self.observed_at, str) or not self.observed_at:
            raise TypeError("observed_at must be a non-empty string")
        if not isinstance(self.updated_at, str) or not self.updated_at:
            raise TypeError("updated_at must be a non-empty string")
        if self.passed is not None and not isinstance(self.passed, bool):
            raise TypeError("passed must be a bool or None")
        if self.score is not None and (isinstance(self.score, bool) or not isinstance(self.score, (int, float))):
            raise TypeError("score must be numeric or None")
        if self.max_score is not None and (isinstance(self.max_score, bool) or not isinstance(self.max_score, int)):
            raise TypeError("max_score must be an int or None")
        if self.detail is not None and not isinstance(self.detail, str):
            raise TypeError("detail must be a string or None")
        if any(not isinstance(ref, str) for ref in self.evidence_refs):
            raise TypeError("evidence_refs must contain only strings")
        if self.status in {
            EvaluationResultStatus.PENDING,
            EvaluationResultStatus.RUNNING,
            EvaluationResultStatus.FAILED,
        }:
            if self.passed is not None or self.score is not None or self.max_score is not None:
                raise ValueError("pending/running/failed evaluation results may not report result values")
        if self.status == EvaluationResultStatus.READY:
            if self.passed is None and self.score is None:
                raise ValueError("ready evaluation results must report passed or score")
        if self.max_score is not None and self.score is None:
            raise ValueError("evaluation results may not report max_score without score")
        if self.score is not None and self.max_score is not None and float(self.score) > float(self.max_score):
            raise ValueError("evaluation result score may not exceed max_score")


@dataclass(frozen=True)
class ParticipantEpisodeExecutionState:
    """Internal normalized participant-episode execution state envelope.

    Models one bounded participant-execution episode with explicit identity.
    Stable participant identity (``participant_address``) is preserved across
    resets and restarts; each episode instance gets a fresh ``episode_id`` and
    an incremented ``sequence_number``, and links back to the prior episode
    via ``previous_episode_id`` so reset/restart history is never rewritten in
    place.
    """

    state_schema_version: str = PARTICIPANT_EPISODE_STATE_SCHEMA_VERSION
    participant_address: str = ""
    episode_id: str = ""
    sequence_number: int = 0
    status: ParticipantEpisodeStatus = ParticipantEpisodeStatus.INITIALIZING
    terminal_reason: ParticipantEpisodeTerminalReason | None = None
    initialized_at: str = ""
    updated_at: str = ""
    terminated_at: str | None = None
    last_control_action: ParticipantEpisodeControlAction = ParticipantEpisodeControlAction.INITIALIZE
    previous_episode_id: str | None = None

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "ParticipantEpisodeExecutionState":
        if not isinstance(payload, Mapping):
            raise TypeError("participant episode payload must be a mapping")
        missing_keys = [
            key
            for key in (
                "state_schema_version",
                "participant_address",
                "episode_id",
                "sequence_number",
                "status",
                "initialized_at",
                "updated_at",
                "last_control_action",
            )
            if key not in payload
        ]
        if missing_keys:
            raise ValueError("participant episode payload is missing required fields: " + ", ".join(missing_keys))
        sequence_number_raw = payload.get("sequence_number")
        if isinstance(sequence_number_raw, bool) or not isinstance(sequence_number_raw, int):
            raise TypeError("participant episode sequence_number must be an int")
        status_raw = payload.get("status")
        terminal_reason_raw = payload.get("terminal_reason")
        last_control_action_raw = payload.get("last_control_action")
        return cls(
            state_schema_version=str(payload.get("state_schema_version")),
            participant_address=str(payload.get("participant_address")),
            episode_id=str(payload.get("episode_id")),
            sequence_number=sequence_number_raw,
            status=(
                status_raw
                if isinstance(status_raw, ParticipantEpisodeStatus)
                else ParticipantEpisodeStatus(str(status_raw))
            ),
            terminal_reason=(
                terminal_reason_raw
                if isinstance(terminal_reason_raw, ParticipantEpisodeTerminalReason)
                else (
                    ParticipantEpisodeTerminalReason(str(terminal_reason_raw))
                    if terminal_reason_raw is not None
                    else None
                )
            ),
            initialized_at=str(payload.get("initialized_at")),
            updated_at=str(payload.get("updated_at")),
            terminated_at=(str(payload["terminated_at"]) if payload.get("terminated_at") is not None else None),
            last_control_action=(
                last_control_action_raw
                if isinstance(last_control_action_raw, ParticipantEpisodeControlAction)
                else ParticipantEpisodeControlAction(str(last_control_action_raw))
            ),
            previous_episode_id=(
                str(payload["previous_episode_id"]) if payload.get("previous_episode_id") is not None else None
            ),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "state_schema_version": self.state_schema_version,
            "participant_address": self.participant_address,
            "episode_id": self.episode_id,
            "sequence_number": self.sequence_number,
            "status": self.status.value,
            "terminal_reason": self.terminal_reason.value if self.terminal_reason is not None else None,
            "initialized_at": self.initialized_at,
            "updated_at": self.updated_at,
            "terminated_at": self.terminated_at,
            "last_control_action": self.last_control_action.value,
            "previous_episode_id": self.previous_episode_id,
        }

    def __post_init__(self) -> None:
        if not isinstance(self.state_schema_version, str) or not self.state_schema_version:
            raise TypeError("participant episode state_schema_version must be a non-empty string")
        if not isinstance(self.participant_address, str) or not self.participant_address:
            raise TypeError("participant_address must be a non-empty string")
        if not isinstance(self.episode_id, str) or not self.episode_id:
            raise TypeError("episode_id must be a non-empty string")
        if isinstance(self.sequence_number, bool) or not isinstance(self.sequence_number, int):
            raise TypeError("sequence_number must be an int")
        if self.sequence_number < 0:
            raise ValueError("sequence_number must be >= 0")
        if not isinstance(self.status, ParticipantEpisodeStatus):
            raise TypeError("status must be a ParticipantEpisodeStatus")
        if self.terminal_reason is not None and not isinstance(self.terminal_reason, ParticipantEpisodeTerminalReason):
            raise TypeError("terminal_reason must be a ParticipantEpisodeTerminalReason or None")
        if not isinstance(self.initialized_at, str) or not self.initialized_at:
            raise TypeError("initialized_at must be a non-empty string")
        if not isinstance(self.updated_at, str) or not self.updated_at:
            raise TypeError("updated_at must be a non-empty string")
        if self.terminated_at is not None and (not isinstance(self.terminated_at, str) or not self.terminated_at):
            raise TypeError("terminated_at must be a non-empty string or None")
        if not isinstance(self.last_control_action, ParticipantEpisodeControlAction):
            raise TypeError("last_control_action must be a ParticipantEpisodeControlAction")
        if self.previous_episode_id is not None and (
            not isinstance(self.previous_episode_id, str) or not self.previous_episode_id
        ):
            raise TypeError("previous_episode_id must be a non-empty string or None")
        if self.status in {ParticipantEpisodeStatus.INITIALIZING, ParticipantEpisodeStatus.RUNNING}:
            if self.terminal_reason is not None:
                raise ValueError("non-terminal participant episodes may not report a terminal_reason")
            if self.terminated_at is not None:
                raise ValueError("non-terminal participant episodes may not report a terminated_at timestamp")
        if self.status == ParticipantEpisodeStatus.TERMINATED:
            if self.terminal_reason is None:
                raise ValueError("terminated participant episodes must report a terminal_reason")
            if self.terminated_at is None:
                raise ValueError("terminated participant episodes must report a terminated_at timestamp")
        if self.sequence_number == 0:
            if self.last_control_action != ParticipantEpisodeControlAction.INITIALIZE:
                raise ValueError(
                    "the first participant episode (sequence_number=0) must use the INITIALIZE control action"
                )
            if self.previous_episode_id is not None:
                raise ValueError(
                    "the first participant episode (sequence_number=0) must not link to a previous episode"
                )
        else:
            if self.last_control_action == ParticipantEpisodeControlAction.INITIALIZE:
                raise ValueError(
                    "subsequent participant episodes (sequence_number>0) must use RESET or RESTART, not INITIALIZE"
                )
            if self.previous_episode_id is None:
                raise ValueError(
                    "subsequent participant episodes (sequence_number>0) must link to a previous_episode_id"
                )
            if self.previous_episode_id == self.episode_id:
                raise ValueError("previous_episode_id must differ from episode_id; reset/restart create a new instance")


@dataclass(frozen=True)
class ParticipantEpisodeHistoryEvent:
    """Internal normalized participant-episode history event.

    History is append-only and per-episode-instance. Each event carries the
    participant identity, the owning episode identity, and (when applicable)
    the terminal reason or control action that the event records. The event
    type, terminal reason, and control action are kept distinct categories so
    history records cannot conflate "what happened" with "why it stopped" or
    "what action drove the transition".
    """

    event_type: ParticipantEpisodeHistoryEventType
    timestamp: str
    participant_address: str
    episode_id: str
    sequence_number: int
    terminal_reason: ParticipantEpisodeTerminalReason | None = None
    control_action: ParticipantEpisodeControlAction | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "ParticipantEpisodeHistoryEvent":
        if not isinstance(payload, Mapping):
            raise TypeError("participant episode history event must be a mapping")
        missing_keys = [
            key
            for key in (
                "event_type",
                "timestamp",
                "participant_address",
                "episode_id",
                "sequence_number",
            )
            if key not in payload
        ]
        if missing_keys:
            raise ValueError("participant episode history event is missing required fields: " + ", ".join(missing_keys))
        sequence_number_raw = payload.get("sequence_number")
        if isinstance(sequence_number_raw, bool) or not isinstance(sequence_number_raw, int):
            raise TypeError("participant episode history sequence_number must be an int")
        terminal_reason_raw = payload.get("terminal_reason")
        control_action_raw = payload.get("control_action")
        return cls(
            event_type=(
                payload["event_type"]
                if isinstance(payload["event_type"], ParticipantEpisodeHistoryEventType)
                else ParticipantEpisodeHistoryEventType(str(payload["event_type"]))
            ),
            timestamp=str(payload["timestamp"]),
            participant_address=str(payload["participant_address"]),
            episode_id=str(payload["episode_id"]),
            sequence_number=sequence_number_raw,
            terminal_reason=(
                terminal_reason_raw
                if isinstance(terminal_reason_raw, ParticipantEpisodeTerminalReason)
                else (
                    ParticipantEpisodeTerminalReason(str(terminal_reason_raw))
                    if terminal_reason_raw is not None
                    else None
                )
            ),
            control_action=(
                control_action_raw
                if isinstance(control_action_raw, ParticipantEpisodeControlAction)
                else (
                    ParticipantEpisodeControlAction(str(control_action_raw)) if control_action_raw is not None else None
                )
            ),
            details=dict(payload.get("details", {})) if isinstance(payload.get("details", {}), Mapping) else {},
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "participant_address": self.participant_address,
            "episode_id": self.episode_id,
            "sequence_number": self.sequence_number,
            "terminal_reason": self.terminal_reason.value if self.terminal_reason is not None else None,
            "control_action": self.control_action.value if self.control_action is not None else None,
            "details": dict(self.details),
        }

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, ParticipantEpisodeHistoryEventType):
            raise TypeError("event_type must be a ParticipantEpisodeHistoryEventType")
        if not isinstance(self.timestamp, str) or not self.timestamp:
            raise TypeError("timestamp must be a non-empty string")
        if not isinstance(self.participant_address, str) or not self.participant_address:
            raise TypeError("participant_address must be a non-empty string")
        if not isinstance(self.episode_id, str) or not self.episode_id:
            raise TypeError("episode_id must be a non-empty string")
        if isinstance(self.sequence_number, bool) or not isinstance(self.sequence_number, int):
            raise TypeError("sequence_number must be an int")
        if self.sequence_number < 0:
            raise ValueError("sequence_number must be >= 0")
        if self.terminal_reason is not None and not isinstance(self.terminal_reason, ParticipantEpisodeTerminalReason):
            raise TypeError("terminal_reason must be a ParticipantEpisodeTerminalReason or None")
        if self.control_action is not None and not isinstance(self.control_action, ParticipantEpisodeControlAction):
            raise TypeError("control_action must be a ParticipantEpisodeControlAction or None")
        if not isinstance(self.details, dict):
            raise TypeError("details must be a dict")
        expected_terminal_reason = _PARTICIPANT_EPISODE_TERMINAL_EVENTS.get(self.event_type)
        if expected_terminal_reason is not None:
            if self.terminal_reason != expected_terminal_reason:
                raise ValueError(
                    f"{self.event_type.value} history events must report terminal_reason "
                    f"{expected_terminal_reason.value}"
                )
        elif self.terminal_reason is not None:
            raise ValueError(f"{self.event_type.value} history events may not report a terminal_reason")
        expected_control_action = _PARTICIPANT_EPISODE_CONTROL_EVENTS.get(self.event_type)
        if expected_control_action is not None:
            if self.control_action != expected_control_action:
                raise ValueError(
                    f"{self.event_type.value} history events must report control_action {expected_control_action.value}"
                )
        elif self.control_action is not None:
            raise ValueError(f"{self.event_type.value} history events may not report a control_action")
        if self.event_type == ParticipantEpisodeHistoryEventType.EPISODE_INITIALIZED and self.sequence_number != 0:
            raise ValueError(
                "episode_initialized history events must report sequence_number=0; "
                "later episodes arrive via episode_reset or episode_restarted"
            )
        if (
            self.event_type
            in {
                ParticipantEpisodeHistoryEventType.EPISODE_RESET,
                ParticipantEpisodeHistoryEventType.EPISODE_RESTARTED,
            }
            and self.sequence_number == 0
        ):
            raise ValueError(
                f"{self.event_type.value} history events must report sequence_number>0; "
                "the first episode uses episode_initialized"
            )


def _participant_observation_status_from_payload(value: Any) -> ParticipantObservationStatus | None:
    if isinstance(value, ParticipantObservationStatus):
        return value
    if value is None:
        return None
    return ParticipantObservationStatus(str(value))


def _validate_required_string(value: Any, message: str) -> None:
    if not isinstance(value, str) or not value:
        raise TypeError(message)


def _validate_optional_string(value: Any, message: str) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise TypeError(message)


def _validate_optional_address(value: str | None, *, prefix: str, message: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.startswith(prefix)):
        raise ValueError(message)


def _validate_required_address(value: str, *, prefix: str, message: str) -> None:
    if not isinstance(value, str) or not value.startswith(prefix):
        raise ValueError(message)


def _tuple_of_non_empty_strings(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
        raise TypeError(f"{field_name} must be a list of strings")
    values = tuple(value)
    refs = tuple(str(item) for item in values if isinstance(item, str) and item)
    if len(refs) != len(values):
        raise TypeError(f"{field_name} entries must be non-empty strings")
    if len(set(refs)) != len(refs):
        raise ValueError(f"{field_name} entries must be unique")
    return refs


def _observation_point_matches_action_instance(observation_point: str, action_instance_id: str) -> bool:
    return action_instance_id in observation_point.split(":")


@dataclass(frozen=True)
class ParticipantActionPreconditionResult:
    """Resolved applicability state for one typed SEM-211 precondition."""

    precondition_id: str
    precondition_class: ParticipantPreconditionClass
    status: ParticipantActionPreconditionStatus
    participant_address: str
    episode_id: str
    action_contract_address: str
    observation_point: str
    support_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ParticipantActionPreconditionResult":
        if not isinstance(payload, Mapping):
            raise TypeError("participant action precondition result must be a mapping")
        missing = [
            key
            for key in (
                "precondition_id",
                "precondition_class",
                "status",
                "participant_address",
                "episode_id",
                "action_contract_address",
                "observation_point",
            )
            if key not in payload
        ]
        if missing:
            raise ValueError("participant action precondition result is missing required fields: " + ", ".join(missing))
        precondition_class_raw = payload.get("precondition_class")
        status_raw = payload.get("status")
        return cls(
            precondition_id=str(payload.get("precondition_id")),
            precondition_class=(
                precondition_class_raw
                if isinstance(precondition_class_raw, ParticipantPreconditionClass)
                else ParticipantPreconditionClass(str(precondition_class_raw))
            ),
            status=(
                status_raw
                if isinstance(status_raw, ParticipantActionPreconditionStatus)
                else ParticipantActionPreconditionStatus(str(status_raw))
            ),
            participant_address=str(payload.get("participant_address")),
            episode_id=str(payload.get("episode_id")),
            action_contract_address=str(payload.get("action_contract_address")),
            observation_point=str(payload.get("observation_point")),
            support_refs=_tuple_of_non_empty_strings(payload.get("support_refs", ()), field_name="support_refs"),
            evidence_refs=_tuple_of_non_empty_strings(payload.get("evidence_refs", ()), field_name="evidence_refs"),
            diagnostics=_tuple_of_non_empty_strings(payload.get("diagnostics", ()), field_name="diagnostics"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "precondition_id": self.precondition_id,
            "precondition_class": self.precondition_class.value,
            "status": self.status.value,
            "participant_address": self.participant_address,
            "episode_id": self.episode_id,
            "action_contract_address": self.action_contract_address,
            "observation_point": self.observation_point,
            "support_refs": list(self.support_refs),
            "evidence_refs": list(self.evidence_refs),
            "diagnostics": list(self.diagnostics),
        }

    def __post_init__(self) -> None:
        _validate_required_string(
            self.precondition_id,
            "precondition_id must be a non-empty string",
        )
        if not isinstance(self.precondition_class, ParticipantPreconditionClass):
            raise TypeError("precondition_class must be a ParticipantPreconditionClass")
        if not isinstance(self.status, ParticipantActionPreconditionStatus):
            raise TypeError("status must be a ParticipantActionPreconditionStatus")
        _validate_required_string(
            self.participant_address,
            "participant action precondition participant_address must be a non-empty string",
        )
        _validate_required_string(
            self.episode_id,
            "participant action precondition episode_id must be a non-empty string",
        )
        _validate_required_address(
            self.action_contract_address,
            prefix=_PARTICIPANT_ACTION_CONTRACT_PREFIX,
            message="action_contract_address must be a compiled participant action contract address",
        )
        _validate_required_string(
            self.observation_point,
            "observation_point must be a non-empty string",
        )
        _tuple_of_non_empty_strings(self.support_refs, field_name="support_refs")
        _tuple_of_non_empty_strings(self.evidence_refs, field_name="evidence_refs")
        _tuple_of_non_empty_strings(self.diagnostics, field_name="diagnostics")


@dataclass(frozen=True)
class ParticipantActionEffectResult:
    """Realized effect entry for a SEM-211 participant action result."""

    effect_id: str
    effect_class: ParticipantEffectClass
    description: str
    target_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ParticipantActionEffectResult":
        if not isinstance(payload, Mapping):
            raise TypeError("participant action effect result must be a mapping")
        missing = [key for key in ("effect_id", "effect_class", "description") if key not in payload]
        if missing:
            raise ValueError("participant action effect result is missing required fields: " + ", ".join(missing))
        effect_class_raw = payload.get("effect_class")
        return cls(
            effect_id=str(payload.get("effect_id")),
            effect_class=(
                effect_class_raw
                if isinstance(effect_class_raw, ParticipantEffectClass)
                else ParticipantEffectClass(str(effect_class_raw))
            ),
            description=str(payload.get("description")),
            target_refs=_tuple_of_non_empty_strings(payload.get("target_refs", ()), field_name="target_refs"),
            evidence_refs=_tuple_of_non_empty_strings(payload.get("evidence_refs", ()), field_name="evidence_refs"),
            diagnostics=_tuple_of_non_empty_strings(payload.get("diagnostics", ()), field_name="diagnostics"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "effect_id": self.effect_id,
            "effect_class": self.effect_class.value,
            "description": self.description,
            "target_refs": list(self.target_refs),
            "evidence_refs": list(self.evidence_refs),
            "diagnostics": list(self.diagnostics),
        }

    def __post_init__(self) -> None:
        _validate_required_string(self.effect_id, "effect_id must be a non-empty string")
        if not isinstance(self.effect_class, ParticipantEffectClass):
            raise TypeError("effect_class must be a ParticipantEffectClass")
        _validate_required_string(
            self.description,
            "participant action effect description must be a non-empty string",
        )
        _tuple_of_non_empty_strings(self.target_refs, field_name="target_refs")
        _tuple_of_non_empty_strings(self.evidence_refs, field_name="evidence_refs")
        _tuple_of_non_empty_strings(self.diagnostics, field_name="diagnostics")
        if self.effect_class not in {ParticipantEffectClass.NO_EFFECT, ParticipantEffectClass.UNKNOWN_EFFECT}:
            if not self.target_refs and not self.evidence_refs:
                raise ValueError(f"{self.effect_class.value} effects require target_refs or evidence_refs")


_PARTICIPANT_ACTION_FAILURE_STATUSES = frozenset(
    {
        ParticipantActionResultStatus.REJECTED,
        ParticipantActionResultStatus.WITHHELD,
        ParticipantActionResultStatus.FAILED,
        ParticipantActionResultStatus.PARTIAL_SUCCESS,
        ParticipantActionResultStatus.UNKNOWN,
    }
)
_PARTICIPANT_ACTION_SUCCESS_STATUSES = frozenset(
    {
        ParticipantActionResultStatus.ACCEPTED,
        ParticipantActionResultStatus.SUCCEEDED,
        ParticipantActionResultStatus.PARTIAL_SUCCESS,
    }
)
_PARTICIPANT_ACTION_TERMINAL_EFFECT_STATUSES = frozenset(
    {
        ParticipantActionResultStatus.SUCCEEDED,
        ParticipantActionResultStatus.PARTIAL_SUCCESS,
    }
)


@dataclass(frozen=True)
class ParticipantActionResult:
    """Typed SEM-211 local result for a participant action attempt."""

    status: ParticipantActionResultStatus
    participant_address: str
    episode_id: str
    action_instance_id: str
    action_contract_address: str
    observation_point: str
    preconditions: tuple[ParticipantActionPreconditionResult, ...] = ()
    effects: tuple[ParticipantActionEffectResult, ...] = ()
    failure_class: ParticipantFailureClass | None = None
    observations: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ParticipantActionResult":
        if not isinstance(payload, Mapping):
            raise TypeError("participant action result must be a mapping")
        missing = [
            key
            for key in (
                "status",
                "participant_address",
                "episode_id",
                "action_instance_id",
                "action_contract_address",
                "observation_point",
            )
            if key not in payload
        ]
        if missing:
            raise ValueError("participant action result is missing required fields: " + ", ".join(missing))
        status_raw = payload.get("status")
        failure_raw = payload.get("failure_class")
        preconditions_raw = payload.get("preconditions", ())
        effects_raw = payload.get("effects", ())
        if isinstance(preconditions_raw, (str, bytes, Mapping)) or not isinstance(preconditions_raw, Iterable):
            raise TypeError("preconditions must be a list of participant action precondition results")
        if isinstance(effects_raw, (str, bytes, Mapping)) or not isinstance(effects_raw, Iterable):
            raise TypeError("effects must be a list of participant action effect results")
        return cls(
            status=(
                status_raw
                if isinstance(status_raw, ParticipantActionResultStatus)
                else ParticipantActionResultStatus(str(status_raw))
            ),
            participant_address=str(payload.get("participant_address")),
            episode_id=str(payload.get("episode_id")),
            action_instance_id=str(payload.get("action_instance_id")),
            action_contract_address=str(payload.get("action_contract_address")),
            observation_point=str(payload.get("observation_point")),
            preconditions=tuple(ParticipantActionPreconditionResult.from_payload(item) for item in preconditions_raw),
            effects=tuple(ParticipantActionEffectResult.from_payload(item) for item in effects_raw),
            failure_class=(
                None
                if failure_raw is None
                else (
                    failure_raw
                    if isinstance(failure_raw, ParticipantFailureClass)
                    else ParticipantFailureClass(str(failure_raw))
                )
            ),
            observations=_tuple_of_non_empty_strings(payload.get("observations", ()), field_name="observations"),
            evidence_refs=_tuple_of_non_empty_strings(payload.get("evidence_refs", ()), field_name="evidence_refs"),
            diagnostics=_tuple_of_non_empty_strings(payload.get("diagnostics", ()), field_name="diagnostics"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "participant_address": self.participant_address,
            "episode_id": self.episode_id,
            "action_instance_id": self.action_instance_id,
            "action_contract_address": self.action_contract_address,
            "observation_point": self.observation_point,
            "preconditions": [item.to_payload() for item in self.preconditions],
            "effects": [item.to_payload() for item in self.effects],
            "failure_class": self.failure_class.value if self.failure_class is not None else None,
            "observations": list(self.observations),
            "evidence_refs": list(self.evidence_refs),
            "diagnostics": list(self.diagnostics),
        }

    def __post_init__(self) -> None:
        if not isinstance(self.status, ParticipantActionResultStatus):
            raise TypeError("status must be a ParticipantActionResultStatus")
        _validate_required_string(
            self.participant_address,
            "participant action result participant_address must be a non-empty string",
        )
        _validate_required_string(
            self.episode_id,
            "participant action result episode_id must be a non-empty string",
        )
        _validate_required_string(
            self.action_instance_id,
            "participant action result action_instance_id must be a non-empty string",
        )
        _validate_required_address(
            self.action_contract_address,
            prefix=_PARTICIPANT_ACTION_CONTRACT_PREFIX,
            message="action_contract_address must be a compiled participant action contract address",
        )
        _validate_required_string(
            self.observation_point,
            "observation_point must be a non-empty string",
        )
        if not _observation_point_matches_action_instance(self.observation_point, self.action_instance_id):
            raise ValueError("action result observation_point must be anchored to action_instance_id")
        if not isinstance(self.preconditions, tuple):
            raise TypeError("preconditions must be a tuple")
        if not self.preconditions:
            raise ValueError("participant action results require precondition results")
        if any(not isinstance(item, ParticipantActionPreconditionResult) for item in self.preconditions):
            raise TypeError("preconditions must contain ParticipantActionPreconditionResult values")
        if len({item.precondition_id for item in self.preconditions}) != len(self.preconditions):
            raise ValueError("precondition result ids must be unique")
        if not isinstance(self.effects, tuple):
            raise TypeError("effects must be a tuple")
        if any(not isinstance(item, ParticipantActionEffectResult) for item in self.effects):
            raise TypeError("effects must contain ParticipantActionEffectResult values")
        if len({item.effect_id for item in self.effects}) != len(self.effects):
            raise ValueError("effect result ids must be unique")
        if self.failure_class is not None and not isinstance(self.failure_class, ParticipantFailureClass):
            raise TypeError("failure_class must be a ParticipantFailureClass or None")
        _tuple_of_non_empty_strings(self.observations, field_name="observations")
        _tuple_of_non_empty_strings(self.evidence_refs, field_name="evidence_refs")
        _tuple_of_non_empty_strings(self.diagnostics, field_name="diagnostics")
        self._validate_scope()
        self._validate_fail_closed()

    def _validate_scope(self) -> None:
        for precondition in self.preconditions:
            if precondition.participant_address != self.participant_address:
                raise ValueError("precondition participant_address must match action result participant_address")
            if precondition.episode_id != self.episode_id:
                raise ValueError("precondition episode_id must match action result episode_id")
            if precondition.action_contract_address != self.action_contract_address:
                raise ValueError(
                    "precondition action_contract_address must match action result action_contract_address"
                )
            if not _observation_point_matches_action_instance(precondition.observation_point, self.action_instance_id):
                raise ValueError("precondition observation_point must be anchored to action result action_instance_id")

    def _validate_fail_closed(self) -> None:
        blocked = [
            item
            for item in self.preconditions
            if item.status
            in {
                ParticipantActionPreconditionStatus.UNSATISFIED,
                ParticipantActionPreconditionStatus.UNRESOLVED,
            }
        ]
        if blocked and self.status in _PARTICIPANT_ACTION_SUCCESS_STATUSES:
            raise ValueError("unsatisfied or unresolved preconditions fail closed")
        if blocked and self.failure_class is None:
            raise ValueError("unsatisfied or unresolved preconditions require a portable failure_class")
        if self.status == ParticipantActionResultStatus.SUCCEEDED:
            if self.failure_class is not None:
                raise ValueError("succeeded action results may not report failure_class")
        if self.status == ParticipantActionResultStatus.ACCEPTED and self.failure_class is not None:
            raise ValueError("accepted action results may not report failure_class")
        if self.status in _PARTICIPANT_ACTION_TERMINAL_EFFECT_STATUSES:
            if not self.effects:
                raise ValueError(f"{self.status.value} action results require declared effects")
        if self.status in _PARTICIPANT_ACTION_FAILURE_STATUSES and self.failure_class is None:
            raise ValueError(f"{self.status.value} action results require a portable failure_class")


@dataclass(frozen=True)
class ParticipantAttributionCandidate:
    """Candidate endpoint for a SEM-212 attribution edge."""

    candidate_kind: ParticipantAttributionCandidateKind
    ref: str
    description: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ParticipantAttributionCandidate":
        if not isinstance(payload, Mapping):
            raise TypeError("participant attribution candidate must be a mapping")
        missing = [key for key in ("candidate_kind", "ref", "description") if key not in payload]
        if missing:
            raise ValueError("participant attribution candidate is missing required fields: " + ", ".join(missing))
        candidate_kind_raw = payload.get("candidate_kind")
        return cls(
            candidate_kind=(
                candidate_kind_raw
                if isinstance(candidate_kind_raw, ParticipantAttributionCandidateKind)
                else ParticipantAttributionCandidateKind(str(candidate_kind_raw))
            ),
            ref=str(payload.get("ref")),
            description=str(payload.get("description")),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "candidate_kind": self.candidate_kind.value,
            "ref": self.ref,
            "description": self.description,
        }

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_kind, ParticipantAttributionCandidateKind):
            raise TypeError("candidate_kind must be a ParticipantAttributionCandidateKind")
        _validate_required_string(self.ref, "participant attribution candidate ref must be a non-empty string")
        _validate_required_string(
            self.description,
            "participant attribution candidate description must be a non-empty string",
        )


@dataclass(frozen=True)
class ParticipantAttributionOrderingBasis:
    """Explicit ordering basis for a SEM-212 attribution edge."""

    basis_kind: ParticipantAttributionOrderingBasisKind
    relation_ref: str
    description: str
    ordered_event_refs: tuple[str, ...] = ()

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ParticipantAttributionOrderingBasis":
        if not isinstance(payload, Mapping):
            raise TypeError("participant attribution ordering_basis must be a mapping")
        missing = [key for key in ("basis_kind", "relation_ref", "description") if key not in payload]
        if missing:
            raise ValueError("participant attribution ordering_basis is missing required fields: " + ", ".join(missing))
        basis_kind_raw = payload.get("basis_kind")
        return cls(
            basis_kind=(
                basis_kind_raw
                if isinstance(basis_kind_raw, ParticipantAttributionOrderingBasisKind)
                else ParticipantAttributionOrderingBasisKind(str(basis_kind_raw))
            ),
            relation_ref=str(payload.get("relation_ref")),
            description=str(payload.get("description")),
            ordered_event_refs=_tuple_of_non_empty_strings(
                payload.get("ordered_event_refs", ()),
                field_name="ordered_event_refs",
            ),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "basis_kind": self.basis_kind.value,
            "relation_ref": self.relation_ref,
            "description": self.description,
            "ordered_event_refs": list(self.ordered_event_refs),
        }

    def __post_init__(self) -> None:
        if not isinstance(self.basis_kind, ParticipantAttributionOrderingBasisKind):
            raise TypeError("basis_kind must be a ParticipantAttributionOrderingBasisKind")
        _validate_required_string(self.relation_ref, "ordering_basis relation_ref must be a non-empty string")
        _validate_required_string(self.description, "ordering_basis description must be a non-empty string")
        _tuple_of_non_empty_strings(self.ordered_event_refs, field_name="ordered_event_refs")


@dataclass(frozen=True)
class ParticipantAttributionEvidenceBasis:
    """Evidence-disclosure basis for a SEM-212 attribution edge."""

    capture_apparatus: str
    granularity: str
    loss_model: str
    redaction_policy: str
    observer_effects: tuple[str, ...]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ParticipantAttributionEvidenceBasis":
        if not isinstance(payload, Mapping):
            raise TypeError("participant attribution evidence_basis must be a mapping")
        missing = [
            key
            for key in (
                "capture_apparatus",
                "granularity",
                "loss_model",
                "redaction_policy",
                "observer_effects",
            )
            if key not in payload
        ]
        if missing:
            raise ValueError("participant attribution evidence_basis is missing required fields: " + ", ".join(missing))
        return cls(
            capture_apparatus=str(payload.get("capture_apparatus")),
            granularity=str(payload.get("granularity")),
            loss_model=str(payload.get("loss_model")),
            redaction_policy=str(payload.get("redaction_policy")),
            observer_effects=_tuple_of_non_empty_strings(
                payload.get("observer_effects", ()),
                field_name="observer_effects",
            ),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "capture_apparatus": self.capture_apparatus,
            "granularity": self.granularity,
            "loss_model": self.loss_model,
            "redaction_policy": self.redaction_policy,
            "observer_effects": list(self.observer_effects),
        }

    def __post_init__(self) -> None:
        _validate_required_string(
            self.capture_apparatus,
            "evidence_basis capture_apparatus must be a non-empty string",
        )
        _validate_required_string(self.granularity, "evidence_basis granularity must be a non-empty string")
        _validate_required_string(self.loss_model, "evidence_basis loss_model must be a non-empty string")
        _validate_required_string(self.redaction_policy, "evidence_basis redaction_policy must be a non-empty string")
        observer_effects = _tuple_of_non_empty_strings(self.observer_effects, field_name="observer_effects")
        if not observer_effects:
            raise ValueError("evidence_basis observer_effects must disclose at least one observer effect")


@dataclass(frozen=True)
class ParticipantAttributionEdge:
    """Evidence-labeled SEM-212 attribution edge."""

    edge_id: str
    participant_address: str
    episode_id: str
    observation_point: str
    cause_candidate: ParticipantAttributionCandidate
    effect_candidate: ParticipantAttributionCandidate
    ordering_basis: ParticipantAttributionOrderingBasis
    evidence_basis: ParticipantAttributionEvidenceBasis
    support_class: ParticipantAttributionSupportClass
    confidence: str
    strength: str
    limitations: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    interpretation_rule_ref: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ParticipantAttributionEdge":
        if not isinstance(payload, Mapping):
            raise TypeError("participant attribution edge must be a mapping")
        missing = [
            key
            for key in (
                "edge_id",
                "participant_address",
                "episode_id",
                "observation_point",
                "cause_candidate",
                "effect_candidate",
                "ordering_basis",
                "evidence_basis",
                "support_class",
                "confidence",
                "strength",
                "limitations",
                "evidence_refs",
            )
            if key not in payload
        ]
        if missing:
            raise ValueError("participant attribution edge is missing required fields: " + ", ".join(missing))
        support_class_raw = payload.get("support_class")
        return cls(
            edge_id=str(payload.get("edge_id")),
            participant_address=str(payload.get("participant_address")),
            episode_id=str(payload.get("episode_id")),
            observation_point=str(payload.get("observation_point")),
            cause_candidate=ParticipantAttributionCandidate.from_payload(payload.get("cause_candidate")),
            effect_candidate=ParticipantAttributionCandidate.from_payload(payload.get("effect_candidate")),
            ordering_basis=ParticipantAttributionOrderingBasis.from_payload(payload.get("ordering_basis")),
            evidence_basis=ParticipantAttributionEvidenceBasis.from_payload(payload.get("evidence_basis")),
            support_class=(
                support_class_raw
                if isinstance(support_class_raw, ParticipantAttributionSupportClass)
                else ParticipantAttributionSupportClass(str(support_class_raw))
            ),
            confidence=str(payload.get("confidence")),
            strength=str(payload.get("strength")),
            limitations=_tuple_of_non_empty_strings(payload.get("limitations"), field_name="limitations"),
            evidence_refs=_tuple_of_non_empty_strings(payload.get("evidence_refs"), field_name="evidence_refs"),
            interpretation_rule_ref=(
                str(payload["interpretation_rule_ref"]) if payload.get("interpretation_rule_ref") is not None else None
            ),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "participant_address": self.participant_address,
            "episode_id": self.episode_id,
            "observation_point": self.observation_point,
            "cause_candidate": self.cause_candidate.to_payload(),
            "effect_candidate": self.effect_candidate.to_payload(),
            "ordering_basis": self.ordering_basis.to_payload(),
            "evidence_basis": self.evidence_basis.to_payload(),
            "support_class": self.support_class.value,
            "confidence": self.confidence,
            "strength": self.strength,
            "limitations": list(self.limitations),
            "evidence_refs": list(self.evidence_refs),
            "interpretation_rule_ref": self.interpretation_rule_ref,
        }

    def __post_init__(self) -> None:
        _validate_required_string(self.edge_id, "participant attribution edge_id must be a non-empty string")
        _validate_required_string(
            self.participant_address,
            "participant attribution participant_address must be a non-empty string",
        )
        _validate_required_string(self.episode_id, "participant attribution episode_id must be a non-empty string")
        _validate_required_string(
            self.observation_point,
            "participant attribution observation_point must be a non-empty string",
        )
        if not isinstance(self.cause_candidate, ParticipantAttributionCandidate):
            raise TypeError("cause_candidate must be a ParticipantAttributionCandidate")
        if not isinstance(self.effect_candidate, ParticipantAttributionCandidate):
            raise TypeError("effect_candidate must be a ParticipantAttributionCandidate")
        if not isinstance(self.ordering_basis, ParticipantAttributionOrderingBasis):
            raise TypeError("ordering_basis must be a ParticipantAttributionOrderingBasis")
        if not isinstance(self.evidence_basis, ParticipantAttributionEvidenceBasis):
            raise TypeError("evidence_basis must be a ParticipantAttributionEvidenceBasis")
        if not isinstance(self.support_class, ParticipantAttributionSupportClass):
            raise TypeError("support_class must be a ParticipantAttributionSupportClass")
        _validate_required_string(self.confidence, "participant attribution confidence must be a non-empty string")
        _validate_required_string(self.strength, "participant attribution strength must be a non-empty string")
        limitations = _tuple_of_non_empty_strings(self.limitations, field_name="limitations")
        evidence_refs = _tuple_of_non_empty_strings(self.evidence_refs, field_name="evidence_refs")
        if not limitations:
            raise ValueError("participant attribution edges require limitations")
        if not evidence_refs:
            raise ValueError("participant attribution edges require evidence_refs")
        _validate_optional_string(
            self.interpretation_rule_ref,
            "interpretation_rule_ref must be a non-empty string or None",
        )
        if (
            self.support_class in STRONG_ATTRIBUTION_SUPPORT_CLASSES
            and self.ordering_basis.basis_kind == ParticipantAttributionOrderingBasisKind.TIMESTAMP_ADJACENCY
        ):
            raise ValueError("timestamp_adjacency ordering_basis cannot support strong causal attribution claims")
        if (
            self.effect_candidate.candidate_kind in OUTCOME_ATTRIBUTION_CANDIDATE_KINDS
            and self.interpretation_rule_ref is None
        ):
            raise ValueError("downstream outcome attribution requires interpretation_rule_ref")


def _participant_time_domain_from_payload(value: Any) -> ParticipantTimeDomain:
    if isinstance(value, ParticipantTimeDomain):
        return value
    return ParticipantTimeDomain(str(value))


def _participant_temporal_event_point_from_payload(value: Any) -> ParticipantTemporalEventPoint:
    if isinstance(value, ParticipantTemporalEventPoint):
        return value
    return ParticipantTemporalEventPoint(str(value))


def _participant_temporal_state_from_payload(value: Any) -> ParticipantTemporalState:
    if isinstance(value, ParticipantTemporalState):
        return value
    return ParticipantTemporalState(str(value))


def _participant_temporal_event_points_from_payload(value: Any) -> tuple[ParticipantTemporalEventPoint, ...]:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
        raise TypeError("temporal event_points must be a list of event-point strings")
    points = tuple(_participant_temporal_event_point_from_payload(item) for item in value)
    if not points:
        raise ValueError("temporal event_points must be non-empty")
    if len(set(points)) != len(points):
        raise ValueError("temporal event_points must be unique")
    return points


@dataclass(frozen=True)
class ParticipantTemporalRuntimeContext:
    """Realized SEM-213 temporal context on a participant behavior event."""

    temporal_contract_id: str
    time_domain: ParticipantTimeDomain
    clock_authority: str
    event_points: tuple[ParticipantTemporalEventPoint, ...]
    observation_point: str
    backend_disclosure_refs: tuple[str, ...] = ()
    reset_boundary: str | None = None
    replay_boundary: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ParticipantTemporalRuntimeContext":
        if not isinstance(payload, Mapping):
            raise TypeError("participant temporal runtime context must be a mapping")
        missing = [
            key
            for key in (
                "temporal_contract_id",
                "time_domain",
                "clock_authority",
                "event_points",
                "observation_point",
            )
            if key not in payload
        ]
        if missing:
            raise ValueError("participant temporal runtime context is missing required fields: " + ", ".join(missing))
        return cls(
            temporal_contract_id=str(payload.get("temporal_contract_id")),
            time_domain=_participant_time_domain_from_payload(payload.get("time_domain")),
            clock_authority=str(payload.get("clock_authority")),
            event_points=_participant_temporal_event_points_from_payload(payload.get("event_points")),
            observation_point=str(payload.get("observation_point")),
            backend_disclosure_refs=_tuple_of_non_empty_strings(
                payload.get("backend_disclosure_refs", ()),
                field_name="backend_disclosure_refs",
            ),
            reset_boundary=_optional_payload_string(payload, "reset_boundary"),
            replay_boundary=_optional_payload_string(payload, "replay_boundary"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "temporal_contract_id": self.temporal_contract_id,
            "time_domain": self.time_domain.value,
            "clock_authority": self.clock_authority,
            "event_points": [point.value for point in self.event_points],
            "observation_point": self.observation_point,
            "backend_disclosure_refs": list(self.backend_disclosure_refs),
            "reset_boundary": self.reset_boundary,
            "replay_boundary": self.replay_boundary,
        }

    def __post_init__(self) -> None:
        _validate_required_string(
            self.temporal_contract_id,
            "participant temporal temporal_contract_id must be a non-empty string",
        )
        if not isinstance(self.time_domain, ParticipantTimeDomain):
            raise TypeError("time_domain must be a ParticipantTimeDomain")
        _validate_required_string(self.clock_authority, "participant temporal clock_authority must be non-empty")
        if not isinstance(self.event_points, tuple):
            raise TypeError("event_points must be a tuple")
        if not self.event_points:
            raise ValueError("participant temporal event_points must be non-empty")
        if any(not isinstance(point, ParticipantTemporalEventPoint) for point in self.event_points):
            raise TypeError("event_points must contain ParticipantTemporalEventPoint values")
        if len(set(self.event_points)) != len(self.event_points):
            raise ValueError("participant temporal event_points must be unique")
        _validate_required_string(self.observation_point, "participant temporal observation_point must be non-empty")
        _tuple_of_non_empty_strings(self.backend_disclosure_refs, field_name="backend_disclosure_refs")
        _validate_optional_string(self.reset_boundary, "reset_boundary must be a non-empty string or None")
        _validate_optional_string(self.replay_boundary, "replay_boundary must be a non-empty string or None")


@dataclass(frozen=True)
class ParticipantTemporalStateTransition:
    """Abstract SEM-213 deadline / dwell / timeout state transition."""

    temporal_contract_id: str
    from_state: ParticipantTemporalState
    to_state: ParticipantTemporalState
    event_point: ParticipantTemporalEventPoint
    time_domain: ParticipantTimeDomain
    clock_authority: str
    boundary_ref: str
    evidence_refs: tuple[str, ...]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ParticipantTemporalStateTransition":
        if not isinstance(payload, Mapping):
            raise TypeError("participant temporal state transition must be a mapping")
        missing = [
            key
            for key in (
                "temporal_contract_id",
                "from_state",
                "to_state",
                "event_point",
                "time_domain",
                "clock_authority",
                "boundary_ref",
                "evidence_refs",
            )
            if key not in payload
        ]
        if missing:
            raise ValueError("participant temporal state transition is missing required fields: " + ", ".join(missing))
        return cls(
            temporal_contract_id=str(payload.get("temporal_contract_id")),
            from_state=_participant_temporal_state_from_payload(payload.get("from_state")),
            to_state=_participant_temporal_state_from_payload(payload.get("to_state")),
            event_point=_participant_temporal_event_point_from_payload(payload.get("event_point")),
            time_domain=_participant_time_domain_from_payload(payload.get("time_domain")),
            clock_authority=str(payload.get("clock_authority")),
            boundary_ref=str(payload.get("boundary_ref")),
            evidence_refs=_tuple_of_non_empty_strings(payload.get("evidence_refs"), field_name="evidence_refs"),
        )

    def __post_init__(self) -> None:
        _validate_required_string(
            self.temporal_contract_id,
            "participant temporal temporal_contract_id must be a non-empty string",
        )
        if not isinstance(self.from_state, ParticipantTemporalState):
            raise TypeError("from_state must be a ParticipantTemporalState")
        if not isinstance(self.to_state, ParticipantTemporalState):
            raise TypeError("to_state must be a ParticipantTemporalState")
        if not isinstance(self.event_point, ParticipantTemporalEventPoint):
            raise TypeError("event_point must be a ParticipantTemporalEventPoint")
        if not isinstance(self.time_domain, ParticipantTimeDomain):
            raise TypeError("time_domain must be a ParticipantTimeDomain")
        _validate_required_string(self.clock_authority, "participant temporal clock_authority must be non-empty")
        _validate_required_string(self.boundary_ref, "participant temporal boundary_ref must be non-empty")
        evidence_refs = _tuple_of_non_empty_strings(self.evidence_refs, field_name="evidence_refs")
        if not evidence_refs:
            raise ValueError("participant temporal state transitions require evidence_refs")


def _participant_temporal_state_transition_from_payload(
    value: ParticipantTemporalStateTransition | Mapping[str, Any],
) -> ParticipantTemporalStateTransition:
    if isinstance(value, ParticipantTemporalStateTransition):
        return value
    return ParticipantTemporalStateTransition.from_payload(value)


def iter_participant_temporal_state_machine_violations(
    transitions: Iterable[ParticipantTemporalStateTransition | Mapping[str, Any]],
) -> Iterator[tuple[str, str]]:
    """Yield SEM-213 abstract state-machine violations."""

    prior_state: dict[str, ParticipantTemporalState] = {}
    domain_authority: dict[str, tuple[ParticipantTimeDomain, str]] = {}
    terminal_states = {ParticipantTemporalState.DEADLINE_MISSED, ParticipantTemporalState.TIMEOUT}
    boundary_events = {ParticipantTemporalEventPoint.RESET, ParticipantTemporalEventPoint.REPLAY}
    boundary_states = {ParticipantTemporalState.RESET, ParticipantTemporalState.REPLAY_BOUNDARY}

    for index, raw_transition in enumerate(transitions):
        locator = f"participant temporal state transition[{index}]"
        try:
            transition = _participant_temporal_state_transition_from_payload(raw_transition)
        except (TypeError, ValueError) as exc:
            yield (locator, f"participant temporal state transition is invalid: {exc}")
            continue

        key = transition.temporal_contract_id
        observed_domain_authority = (transition.time_domain, transition.clock_authority)
        if key in domain_authority and domain_authority[key] != observed_domain_authority:
            expected_domain, expected_authority = domain_authority[key]
            yield (
                locator,
                f"temporal contract {key!r} changed time domain or clock authority from "
                f"{expected_domain.value}/{expected_authority!r} to "
                f"{transition.time_domain.value}/{transition.clock_authority!r}",
            )
        else:
            domain_authority[key] = observed_domain_authority

        if (
            transition.to_state == ParticipantTemporalState.DWELL_SATISFIED
            and transition.from_state != ParticipantTemporalState.DWELL_ACTIVE
            and prior_state.get(key) != ParticipantTemporalState.DWELL_ACTIVE
        ):
            yield (locator, "dwell_satisfied requires prior dwell_active state in the same temporal segment")

        if (
            transition.from_state in terminal_states
            and transition.event_point not in boundary_events
            and transition.to_state not in boundary_states
        ):
            yield (locator, "terminal temporal state requires reset or replay boundary before reuse")

        prior_state[key] = transition.to_state


def _optional_payload_string(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return str(value) if value is not None else None


def _participant_behavior_event_type_from_payload(value: Any) -> ParticipantBehaviorHistoryEventType:
    if isinstance(value, ParticipantBehaviorHistoryEventType):
        return value
    return ParticipantBehaviorHistoryEventType(str(value))


def _participant_interaction_class_from_payload(value: Any) -> ParticipantInteractionClass | None:
    if value is None:
        return None
    if isinstance(value, ParticipantInteractionClass):
        return value
    return ParticipantInteractionClass(str(value))


def _participant_behavior_shared_state_refs_from_payload(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise TypeError("shared_state_refs must be a list of strings")
    return tuple(str(ref) for ref in value)


def _participant_action_result_from_payload(value: Any) -> ParticipantActionResult | None:
    if value is None:
        return None
    if isinstance(value, ParticipantActionResult):
        return value
    return ParticipantActionResult.from_payload(value)


def _participant_attribution_edges_from_payload(value: Any) -> tuple[ParticipantAttributionEdge, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
        raise TypeError("attribution_edges must be a list of participant attribution edges")
    return tuple(
        edge if isinstance(edge, ParticipantAttributionEdge) else ParticipantAttributionEdge.from_payload(edge)
        for edge in value
    )


def _participant_temporal_contexts_from_payload(value: Any) -> tuple[ParticipantTemporalRuntimeContext, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
        raise TypeError("temporal_contexts must be a list of participant temporal runtime contexts")
    return tuple(
        context
        if isinstance(context, ParticipantTemporalRuntimeContext)
        else ParticipantTemporalRuntimeContext.from_payload(context)
        for context in value
    )


def _participant_behavior_details_from_payload(value: Any) -> dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise TypeError("participant behavior details must be a mapping")
    details = dict(value)
    for empty_ref_key in ("visible_refs", "disclosed_refs", "evidence_refs"):
        refs = details.get(empty_ref_key)
        if isinstance(refs, (list, tuple)) and not refs:
            details.pop(empty_ref_key)
    return details


@dataclass(frozen=True)
class ParticipantBehaviorHistoryEvent:
    """Internal normalized participant behavior history event.

    The canonical record keeps actor provenance and compiled behavior-contract
    addresses. Role-neutral interpretation is a projection over those records,
    not a reason to treat raw action names or backend-native logs as behavior
    semantics.
    """

    event_type: ParticipantBehaviorHistoryEventType
    timestamp: str
    participant_address: str
    episode_id: str
    action_instance_id: str
    action_contract_address: str | None = None
    observation_boundary_address: str | None = None
    observation_status: ParticipantObservationStatus | None = None
    actor_provenance: str | None = None
    state_transition_kind: str | None = None
    post_state_digest: str | None = None
    joint_action_set_id: str | None = None
    realized_order: int | None = None
    interaction_class: ParticipantInteractionClass | None = None
    interaction_ref: str | None = None
    shared_state_refs: tuple[str, ...] = ()
    action_result: ParticipantActionResult | None = None
    attribution_edges: tuple[ParticipantAttributionEdge, ...] = ()
    temporal_contexts: tuple[ParticipantTemporalRuntimeContext, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "ParticipantBehaviorHistoryEvent":
        if not isinstance(payload, Mapping):
            raise TypeError("participant behavior history event must be a mapping")
        missing_keys = [
            key
            for key in (
                "event_type",
                "timestamp",
                "participant_address",
                "episode_id",
                "action_instance_id",
            )
            if key not in payload
        ]
        if missing_keys:
            raise ValueError(
                "participant behavior history event is missing required fields: " + ", ".join(missing_keys)
            )
        return cls(
            event_type=_participant_behavior_event_type_from_payload(payload.get("event_type")),
            timestamp=str(payload.get("timestamp")),
            participant_address=str(payload.get("participant_address")),
            episode_id=str(payload.get("episode_id")),
            action_instance_id=str(payload.get("action_instance_id")),
            action_contract_address=_optional_payload_string(payload, "action_contract_address"),
            observation_boundary_address=_optional_payload_string(payload, "observation_boundary_address"),
            observation_status=_participant_observation_status_from_payload(payload.get("observation_status")),
            actor_provenance=_optional_payload_string(payload, "actor_provenance"),
            state_transition_kind=_optional_payload_string(payload, "state_transition_kind"),
            post_state_digest=_optional_payload_string(payload, "post_state_digest"),
            joint_action_set_id=_optional_payload_string(payload, "joint_action_set_id"),
            realized_order=payload.get("realized_order"),
            interaction_class=_participant_interaction_class_from_payload(payload.get("interaction_class")),
            interaction_ref=_optional_payload_string(payload, "interaction_ref"),
            shared_state_refs=_participant_behavior_shared_state_refs_from_payload(
                payload.get("shared_state_refs", ())
            ),
            action_result=_participant_action_result_from_payload(payload.get("action_result")),
            attribution_edges=_participant_attribution_edges_from_payload(payload.get("attribution_edges", ())),
            temporal_contexts=_participant_temporal_contexts_from_payload(payload.get("temporal_contexts", ())),
            details=_participant_behavior_details_from_payload(payload.get("details", {})),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "participant_address": self.participant_address,
            "episode_id": self.episode_id,
            "action_instance_id": self.action_instance_id,
            "action_contract_address": self.action_contract_address,
            "observation_boundary_address": self.observation_boundary_address,
            "observation_status": self.observation_status.value if self.observation_status is not None else None,
            "actor_provenance": self.actor_provenance,
            "state_transition_kind": self.state_transition_kind,
            "post_state_digest": self.post_state_digest,
            "joint_action_set_id": self.joint_action_set_id,
            "realized_order": self.realized_order,
            "interaction_class": self.interaction_class.value if self.interaction_class is not None else None,
            "interaction_ref": self.interaction_ref,
            "shared_state_refs": list(self.shared_state_refs),
            "action_result": self.action_result.to_payload() if self.action_result is not None else None,
            "attribution_edges": [edge.to_payload() for edge in self.attribution_edges],
            "temporal_contexts": [context.to_payload() for context in self.temporal_contexts],
            "details": dict(self.details),
        }

    def __post_init__(self) -> None:
        self._validate_common_fields()
        self._validate_event_type_fields()

    def _validate_common_fields(self) -> None:
        if not isinstance(self.event_type, ParticipantBehaviorHistoryEventType):
            raise TypeError("event_type must be a ParticipantBehaviorHistoryEventType")
        self._validate_required_string(self.timestamp, "participant behavior timestamp must be a non-empty string")
        self._validate_required_string(
            self.participant_address,
            "participant behavior participant_address must be a non-empty string",
        )
        self._validate_required_string(self.episode_id, "participant behavior episode_id must be a non-empty string")
        self._validate_required_string(self.action_instance_id, "action_instance_id must be a non-empty string")
        self._validate_optional_address(
            self.action_contract_address,
            prefix=_PARTICIPANT_ACTION_CONTRACT_PREFIX,
            message="action_contract_address must be a compiled participant action contract address",
        )
        self._validate_optional_address(
            self.observation_boundary_address,
            prefix=_PARTICIPANT_OBSERVATION_BOUNDARY_PREFIX,
            message="observation_boundary_address must be a compiled participant observation boundary address",
        )
        if self.observation_status is not None and not isinstance(
            self.observation_status,
            ParticipantObservationStatus,
        ):
            raise TypeError("observation_status must be a ParticipantObservationStatus or None")
        self._validate_optional_string(self.actor_provenance, "actor_provenance must be a non-empty string or None")
        self._validate_optional_state_fields()
        self._validate_realized_order()
        self._validate_interaction_type()
        if not isinstance(self.shared_state_refs, tuple):
            raise TypeError("shared_state_refs must be a tuple")
        for ref in self.shared_state_refs:
            self._validate_required_string(ref, "shared_state_refs entries must be non-empty strings")
        if len(set(self.shared_state_refs)) != len(self.shared_state_refs):
            raise ValueError("shared_state_refs entries must be unique")
        self._validate_interaction_fields()
        self._validate_action_result_type()
        self._validate_attribution_edge_types()
        self._validate_temporal_context_types()
        if not isinstance(self.details, dict):
            raise TypeError("participant behavior details must be a dict")

    def _validate_optional_state_fields(self) -> None:
        self._validate_optional_string(
            self.state_transition_kind,
            "state_transition_kind must be a non-empty string or None",
        )
        self._validate_optional_string(self.post_state_digest, "post_state_digest must be a non-empty string or None")
        self._validate_optional_string(
            self.joint_action_set_id,
            "joint_action_set_id must be a non-empty string or None",
        )

    def _validate_realized_order(self) -> None:
        if self.realized_order is not None and (
            not isinstance(self.realized_order, int) or isinstance(self.realized_order, bool) or self.realized_order < 0
        ):
            raise TypeError("realized_order must be a non-negative integer or None")

    def _validate_interaction_type(self) -> None:
        if self.interaction_class is not None and not isinstance(self.interaction_class, ParticipantInteractionClass):
            raise TypeError("interaction_class must be a ParticipantInteractionClass or None")
        self._validate_optional_string(self.interaction_ref, "interaction_ref must be a non-empty string or None")

    def _validate_action_result_type(self) -> None:
        if self.action_result is not None and not isinstance(self.action_result, ParticipantActionResult):
            raise TypeError("action_result must be a ParticipantActionResult or None")

    def _validate_attribution_edge_types(self) -> None:
        if not isinstance(self.attribution_edges, tuple):
            raise TypeError("attribution_edges must be a tuple")
        if any(not isinstance(edge, ParticipantAttributionEdge) for edge in self.attribution_edges):
            raise TypeError("attribution_edges must contain ParticipantAttributionEdge values")
        if len({edge.edge_id for edge in self.attribution_edges}) != len(self.attribution_edges):
            raise ValueError("participant attribution edge_id values must be unique per event")
        if self.attribution_edges and self.event_type != ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED:
            raise ValueError("participant attribution edges are only allowed on observation_emitted events")

    def _validate_temporal_context_types(self) -> None:
        if not isinstance(self.temporal_contexts, tuple):
            raise TypeError("temporal_contexts must be a tuple")
        if any(not isinstance(context, ParticipantTemporalRuntimeContext) for context in self.temporal_contexts):
            raise TypeError("temporal_contexts must contain ParticipantTemporalRuntimeContext values")
        if len({context.temporal_contract_id for context in self.temporal_contexts}) != len(self.temporal_contexts):
            raise ValueError("participant temporal_contract_id values must be unique per event")

    @staticmethod
    def _validate_required_string(value: Any, message: str) -> None:
        if not isinstance(value, str) or not value:
            raise TypeError(message)

    @staticmethod
    def _validate_optional_string(value: Any, message: str) -> None:
        if value is not None and (not isinstance(value, str) or not value):
            raise TypeError(message)

    @staticmethod
    def _validate_optional_address(value: str | None, *, prefix: str, message: str) -> None:
        if value is not None and (not isinstance(value, str) or not value.startswith(prefix)):
            raise ValueError(message)

    def _validate_event_type_fields(self) -> None:
        validators = {
            ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED: self._validate_action_attempted_fields,
            ParticipantBehaviorHistoryEventType.STATE_TRANSITION_RECORDED: self._validate_state_transition_fields,
            ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED: self._validate_observation_emitted_fields,
        }
        validators[self.event_type]()

    def _validate_interaction_fields(self) -> None:
        if self.joint_action_set_id is None and self.realized_order is not None:
            raise ValueError("realized_order requires joint_action_set_id")
        if self.joint_action_set_id is not None and self.realized_order is None:
            raise ValueError("joint_action_set_id requires realized_order")
        if self.interaction_class is None:
            if self.interaction_ref is not None:
                raise ValueError("interaction_ref requires interaction_class")
            return
        if self.joint_action_set_id is None:
            raise ValueError("interaction_class requires joint_action_set_id and realized_order")
        if (
            self.interaction_class
            in {
                ParticipantInteractionClass.COORDINATION,
                ParticipantInteractionClass.INTERFERENCE,
            }
            and self.interaction_ref is None
        ):
            raise ValueError(f"{self.interaction_class.value} events require interaction_ref")
        if (
            self.interaction_class
            in {
                ParticipantInteractionClass.CONTENTION,
                ParticipantInteractionClass.SHARED_STATE_CHANGE,
            }
            and not self.shared_state_refs
        ):
            raise ValueError(f"{self.interaction_class.value} events require shared_state_refs")

    def _validate_action_attempted_fields(self) -> None:
        if self.action_contract_address is None:
            raise ValueError("action_attempted events require action_contract_address")
        if self.actor_provenance is None:
            raise ValueError("action_attempted events require actor_provenance")
        if self.observation_boundary_address is not None or self.observation_status is not None:
            raise ValueError("action_attempted events may not report observation fields")
        if self.state_transition_kind is not None or self.post_state_digest is not None:
            raise ValueError("action_attempted events may not report state-transition fields")
        if self.action_result is not None:
            raise ValueError("action_attempted events may not report action_result")

    def _validate_state_transition_fields(self) -> None:
        if self.action_contract_address is None:
            raise ValueError("state_transition_recorded events require action_contract_address")
        if self.state_transition_kind is None:
            raise ValueError("state_transition_recorded events require state_transition_kind")
        if self.post_state_digest is None:
            raise ValueError("state_transition_recorded events require post_state_digest")
        if self.observation_boundary_address is not None or self.observation_status is not None:
            raise ValueError("state_transition_recorded events may not report observation fields")
        if self.action_result is not None:
            raise ValueError("state_transition_recorded events may not report action_result")

    def _validate_observation_emitted_fields(self) -> None:
        if self.action_contract_address is None:
            raise ValueError("observation_emitted events require action_contract_address")
        if self.observation_boundary_address is None:
            raise ValueError("observation_emitted events require observation_boundary_address")
        if self.observation_status is None:
            raise ValueError("observation_emitted events require observation_status")
        if self.observation_status == ParticipantObservationStatus.TERMINAL and self.post_state_digest is None:
            raise ValueError("terminal observation_emitted events require post_state_digest")
        if self.state_transition_kind is not None:
            raise ValueError("observation_emitted events may not report state_transition_kind")
        if self.action_result is not None:
            self._validate_action_result_scope()
        self._validate_attribution_edges()

    def _validate_action_result_scope(self) -> None:
        if self.action_result is None:
            return
        if self.action_result.participant_address != self.participant_address:
            raise ValueError("action_result participant_address must match event participant_address")
        if self.action_result.episode_id != self.episode_id:
            raise ValueError("action_result episode_id must match event episode_id")
        if self.action_result.action_instance_id != self.action_instance_id:
            raise ValueError("action_result action_instance_id must match event action_instance_id")
        if self.action_result.action_contract_address != self.action_contract_address:
            raise ValueError("action_result action_contract_address must match event action_contract_address")
        if (
            self.observation_status in _PARTICIPANT_TERMINAL_OBSERVATION_STATUSES
            and self.action_result.status == ParticipantActionResultStatus.ACCEPTED
        ):
            raise ValueError("terminal observation action_result must report a terminal status")

    def _validate_attribution_edges(self) -> None:
        for edge in self.attribution_edges:
            if edge.participant_address != self.participant_address:
                raise ValueError("attribution edge participant_address must match event participant_address")
            if edge.episode_id != self.episode_id:
                raise ValueError("attribution edge episode_id must match event episode_id")
            if self.action_result is not None:
                if edge.observation_point != self.action_result.observation_point:
                    raise ValueError("attribution edge observation_point must match action_result observation_point")
            elif not _observation_point_matches_action_instance(edge.observation_point, self.action_instance_id):
                raise ValueError("attribution edge observation_point must be anchored to action_instance_id")
            self._validate_attribution_candidate_grounding(edge)

    def _validate_attribution_candidate_grounding(self, edge: ParticipantAttributionEdge) -> None:
        allowed_action_refs = {self.action_instance_id}
        if self.action_contract_address is not None:
            allowed_action_refs.add(self.action_contract_address)
        if edge.cause_candidate.candidate_kind == ParticipantAttributionCandidateKind.ACTION:
            if edge.cause_candidate.ref not in allowed_action_refs:
                raise ValueError("attribution edge action cause_candidate must match the event action")
        elif edge.cause_candidate.ref not in self._attribution_grounded_refs():
            raise ValueError(f"attribution edge cause_candidate {edge.cause_candidate.ref!r} is not grounded")

        if edge.effect_candidate.candidate_kind in OUTCOME_ATTRIBUTION_CANDIDATE_KINDS:
            return
        if edge.effect_candidate.ref not in self._attribution_grounded_refs():
            raise ValueError(f"attribution edge effect_candidate {edge.effect_candidate.ref!r} is not grounded")

    def _attribution_grounded_refs(self) -> set[str]:
        refs: set[str] = {self.action_instance_id}
        if self.action_contract_address is not None:
            refs.add(self.action_contract_address)
        if self.observation_boundary_address is not None:
            refs.add(self.observation_boundary_address)
        if self.post_state_digest is not None:
            refs.add(self.post_state_digest)
        for key in _PARTICIPANT_OBSERVATION_DETAIL_REF_KEYS:
            value = self.details.get(key)
            if isinstance(value, (list, tuple)):
                refs.update(str(item) for item in value if isinstance(item, str) and item)
        if self.action_result is None:
            return refs
        refs.update(self.action_result.observations)
        refs.update(self.action_result.evidence_refs)
        for precondition in self.action_result.preconditions:
            refs.update(precondition.support_refs)
            refs.update(precondition.evidence_refs)
        for effect in self.action_result.effects:
            refs.update(effect.target_refs)
            refs.update(effect.evidence_refs)
        return refs


_PARTICIPANT_TERMINAL_OBSERVATION_STATUSES = frozenset(
    {
        ParticipantObservationStatus.TERMINAL,
        ParticipantObservationStatus.ORPHANED_ACTION,
    }
)
_PARTICIPANT_VISIBLE_VIEW_DISPOSITIONS = frozenset({"observable", "discovered", "inferred", "disclosed", "deceptive"})
_PARTICIPANT_OBSERVATION_DETAIL_REF_KEYS = ("visible_refs", "disclosed_refs", "evidence_refs")
_PARTICIPANT_OBSERVATION_DETAIL_KEYS = frozenset(_PARTICIPANT_OBSERVATION_DETAIL_REF_KEYS)


def _participant_behavior_detail_refs(
    event: ParticipantBehaviorHistoryEvent,
    *,
    key: str,
    locator: str,
) -> tuple[tuple[str, ...], list[tuple[str, str]]]:
    if key not in event.details:
        return (), []
    value = event.details[key]
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
        return (), [(locator, f"observation details field {key!r} must be a list of strings")]
    items = tuple(value)
    refs = tuple(str(ref) for ref in items if isinstance(ref, str) and ref)
    if len(refs) != len(items):
        return (), [(locator, f"observation details field {key!r} must contain only non-empty strings")]
    if len(set(refs)) != len(refs):
        return (), [(locator, f"observation details field {key!r} must not contain duplicate refs")]
    return refs, []


def _participant_behavior_detail_shape_violations(
    event: ParticipantBehaviorHistoryEvent,
    *,
    locator: str,
) -> list[tuple[str, str]]:
    if not event.details:
        return []
    violations: list[tuple[str, str]] = []
    if event.event_type != ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED:
        violations.append((locator, "participant behavior details are only allowed on observation_emitted events"))
    unsupported_keys = sorted(str(key) for key in event.details if key not in _PARTICIPANT_OBSERVATION_DETAIL_KEYS)
    if unsupported_keys:
        allowed = ", ".join(_PARTICIPANT_OBSERVATION_DETAIL_REF_KEYS)
        unsupported = ", ".join(unsupported_keys)
        violations.append(
            (
                locator,
                f"observation details may only contain {allowed}; unsupported fields: {unsupported}",
            )
        )
    return violations


def _participant_behavior_timeline_relations(
    boundary: ParticipantObservationBoundaryRuntime,
) -> tuple[tuple[int, dict[str, str]], ...]:
    relations: list[tuple[int, dict[str, str]]] = []
    for snapshot in boundary.view_relation_timeline:
        order = snapshot.get("effective_order")
        raw_relation = snapshot.get("view_relation", {})
        if not isinstance(order, int) or isinstance(order, bool) or not isinstance(raw_relation, Mapping):
            continue
        relations.append((order, {str(ref): str(disposition) for ref, disposition in raw_relation.items()}))
    return tuple(sorted(relations, key=lambda item: item[0]))


def _participant_behavior_initial_view_relation(
    boundary: ParticipantObservationBoundaryRuntime,
) -> dict[str, str]:
    initial_relation: dict[str, str] = {}
    for order, relation in _participant_behavior_timeline_relations(boundary):
        if order > -1:
            break
        initial_relation = dict(relation)
    return initial_relation


def _participant_behavior_view_relation_deltas_by_order(
    boundary: ParticipantObservationBoundaryRuntime,
) -> dict[int, dict[str, str]]:
    deltas: dict[int, dict[str, str]] = {}
    previous_relation: dict[str, str] | None = None
    for order, relation in _participant_behavior_timeline_relations(boundary):
        if previous_relation is None:
            previous_relation = relation
            continue
        deltas[order] = {
            ref: disposition for ref, disposition in relation.items() if previous_relation.get(ref) != disposition
        }
        previous_relation = relation
    return deltas


def _participant_behavior_transition_effective_order(transition: Mapping[str, Any]) -> int | None:
    order = transition.get("effective_order")
    if not isinstance(order, int) or isinstance(order, bool):
        return None
    return order


def _participant_behavior_transition_delta(
    transition: Mapping[str, Any],
    *,
    deltas_by_order: Mapping[int, Mapping[str, str]],
) -> dict[str, str]:
    information_ref = transition.get("information_ref")
    to_disposition = transition.get("to_disposition")
    if isinstance(information_ref, str) and information_ref and isinstance(to_disposition, str) and to_disposition:
        return {information_ref: to_disposition}
    order = _participant_behavior_transition_effective_order(transition)
    if order is None:
        return {}
    return dict(deltas_by_order.get(order, {}))


def _participant_behavior_transition_matches_relation(
    transition: Mapping[str, Any],
    *,
    relation: Mapping[str, str],
) -> bool:
    information_ref = transition.get("information_ref")
    from_disposition = transition.get("from_disposition")
    if not isinstance(information_ref, str) or not information_ref:
        return True
    if not isinstance(from_disposition, str) or not from_disposition:
        return True
    return relation.get(information_ref) == from_disposition


def _participant_behavior_observation_detail_refs(
    event: ParticipantBehaviorHistoryEvent,
    *,
    locator: str,
) -> tuple[dict[str, tuple[str, ...]], list[tuple[str, str]]]:
    detail_refs: dict[str, tuple[str, ...]] = {}
    violations: list[tuple[str, str]] = []
    for key in _PARTICIPANT_OBSERVATION_DETAIL_REF_KEYS:
        refs, ref_violations = _participant_behavior_detail_refs(event, key=key, locator=locator)
        detail_refs[key] = refs
        violations.extend(ref_violations)
    return detail_refs, violations


def _participant_behavior_disposition_ref_violations(
    *,
    locator: str,
    refs: tuple[str, ...],
    relation: Mapping[str, str],
    allowed_dispositions: frozenset[str],
    effective_order: int,
    detail_key: str,
    allowed_label: str,
) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for ref in refs:
        disposition = relation.get(ref)
        if disposition in allowed_dispositions:
            continue
        violations.append(
            (
                locator,
                (
                    f"observation {detail_key} may only contain {allowed_label} refs at "
                    f"effective_order {effective_order}: "
                    f"{ref!r} has disposition {disposition!r}"
                ),
            )
        )
    return violations


def _participant_behavior_evidence_ref_violations(
    *,
    locator: str,
    refs: tuple[str, ...],
    boundary: ParticipantObservationBoundaryRuntime,
    relation: Mapping[str, str],
    effective_order: int,
) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for ref in refs:
        if ref in boundary.evidence_refs or relation.get(ref) == "evidence_only":
            continue
        violations.append(
            (
                locator,
                (
                    "observation evidence_refs may only contain boundary evidence refs at "
                    f"effective_order {effective_order}: {ref!r}"
                ),
            )
        )
    return violations


def _participant_behavior_visibility_detail_violations(
    *,
    locator: str,
    detail_refs: Mapping[str, tuple[str, ...]],
    boundary: ParticipantObservationBoundaryRuntime,
    relation: Mapping[str, str],
    effective_order: int,
) -> list[tuple[str, str]]:
    return [
        *_participant_behavior_disposition_ref_violations(
            locator=locator,
            refs=detail_refs["visible_refs"],
            relation=relation,
            allowed_dispositions=_PARTICIPANT_VISIBLE_VIEW_DISPOSITIONS,
            effective_order=effective_order,
            detail_key="visible_refs",
            allowed_label="participant-visible",
        ),
        *_participant_behavior_disposition_ref_violations(
            locator=locator,
            refs=detail_refs["disclosed_refs"],
            relation=relation,
            allowed_dispositions=frozenset({"disclosed"}),
            effective_order=effective_order,
            detail_key="disclosed_refs",
            allowed_label="disclosed",
        ),
        *_participant_behavior_evidence_ref_violations(
            locator=locator,
            refs=detail_refs["evidence_refs"],
            boundary=boundary,
            relation=relation,
            effective_order=effective_order,
        ),
    ]


def _participant_behavior_action_result_visible_ref_violations(
    *,
    locator: str,
    owner_label: str,
    field_name: str,
    refs: tuple[str, ...],
    boundary: ParticipantObservationBoundaryRuntime,
    relation: Mapping[str, str],
    effective_order: int,
) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    owner_prefix = f" {owner_label}" if owner_label else ""
    for ref in refs:
        disposition = relation.get(ref)
        if disposition is None and ref in boundary.hidden_refs:
            disposition = "hidden"
        if disposition is None:
            continue
        if disposition in _PARTICIPANT_VISIBLE_VIEW_DISPOSITIONS:
            continue
        violations.append(
            (
                locator,
                (
                    f"action_result{owner_prefix} {field_name} {ref!r} is not participant-visible "
                    f"at effective_order {effective_order}: disposition {disposition!r}"
                ),
            )
        )
    return violations


def _participant_behavior_action_result_evidence_ref_violations(
    *,
    locator: str,
    owner_label: str,
    field_name: str,
    refs: tuple[str, ...],
    boundary: ParticipantObservationBoundaryRuntime,
    relation: Mapping[str, str],
    effective_order: int,
) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    owner_prefix = f" {owner_label}" if owner_label else ""
    for ref in refs:
        disposition = relation.get(ref)
        if disposition is None and ref in boundary.hidden_refs:
            disposition = "hidden"
        if ref in boundary.evidence_refs or disposition == "evidence_only":
            continue
        suffix = f": disposition {disposition!r}" if disposition is not None else ""
        violations.append(
            (
                locator,
                (
                    f"action_result{owner_prefix} {field_name} {ref!r} is not authorized evidence "
                    f"at effective_order {effective_order}{suffix}"
                ),
            )
        )
    return violations


def _participant_behavior_action_result_ref_authorization_violations(
    *,
    event: ParticipantBehaviorHistoryEvent,
    locator: str,
    boundary: ParticipantObservationBoundaryRuntime,
    relation: Mapping[str, str],
    effective_order: int,
) -> list[tuple[str, str]]:
    if event.action_result is None:
        return []
    violations: list[tuple[str, str]] = []
    for precondition in event.action_result.preconditions:
        owner_label = f"precondition {precondition.precondition_id!r}"
        violations.extend(
            _participant_behavior_action_result_visible_ref_violations(
                locator=locator,
                owner_label=owner_label,
                field_name="support_ref",
                refs=precondition.support_refs,
                boundary=boundary,
                relation=relation,
                effective_order=effective_order,
            )
        )
        violations.extend(
            _participant_behavior_action_result_evidence_ref_violations(
                locator=locator,
                owner_label=owner_label,
                field_name="evidence_ref",
                refs=precondition.evidence_refs,
                boundary=boundary,
                relation=relation,
                effective_order=effective_order,
            )
        )
    for effect in event.action_result.effects:
        owner_label = f"effect {effect.effect_id!r}"
        violations.extend(
            _participant_behavior_action_result_visible_ref_violations(
                locator=locator,
                owner_label=owner_label,
                field_name="target_ref",
                refs=effect.target_refs,
                boundary=boundary,
                relation=relation,
                effective_order=effective_order,
            )
        )
        violations.extend(
            _participant_behavior_action_result_evidence_ref_violations(
                locator=locator,
                owner_label=owner_label,
                field_name="evidence_ref",
                refs=effect.evidence_refs,
                boundary=boundary,
                relation=relation,
                effective_order=effective_order,
            )
        )
    violations.extend(
        _participant_behavior_action_result_evidence_ref_violations(
            locator=locator,
            owner_label="",
            field_name="evidence_ref",
            refs=event.action_result.evidence_refs,
            boundary=boundary,
            relation=relation,
            effective_order=effective_order,
        )
    )
    return violations


def _participant_behavior_attribution_evidence_ref_violations(
    *,
    locator: str,
    edge: ParticipantAttributionEdge,
    refs: tuple[str, ...],
    boundary: ParticipantObservationBoundaryRuntime,
    relation: Mapping[str, str],
    effective_order: int,
) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for ref in refs:
        disposition = relation.get(ref)
        if disposition is None and ref in boundary.hidden_refs:
            disposition = "hidden"
        if ref in boundary.evidence_refs or disposition == "evidence_only":
            continue
        suffix = f": disposition {disposition!r}" if disposition is not None else ""
        violations.append(
            (
                locator,
                (
                    f"attribution edge {edge.edge_id!r} evidence_ref {ref!r} is not authorized evidence "
                    f"at effective_order {effective_order}{suffix}"
                ),
            )
        )
    return violations


def _participant_behavior_attribution_candidate_ref_violations(
    *,
    locator: str,
    edge: ParticipantAttributionEdge,
    candidate: ParticipantAttributionCandidate,
    boundary: ParticipantObservationBoundaryRuntime,
    relation: Mapping[str, str],
    effective_order: int,
) -> list[tuple[str, str]]:
    if candidate.candidate_kind == ParticipantAttributionCandidateKind.ACTION:
        return []
    if candidate.candidate_kind == ParticipantAttributionCandidateKind.EVIDENCE:
        return _participant_behavior_attribution_evidence_ref_violations(
            locator=locator,
            edge=edge,
            refs=(candidate.ref,),
            boundary=boundary,
            relation=relation,
            effective_order=effective_order,
        )
    disposition = relation.get(candidate.ref)
    if disposition is None and candidate.ref in boundary.hidden_refs:
        disposition = "hidden"
    if disposition is None or disposition in _PARTICIPANT_VISIBLE_VIEW_DISPOSITIONS:
        return []
    return [
        (
            locator,
            (
                f"attribution edge {edge.edge_id!r} {candidate.candidate_kind.value} candidate "
                f"{candidate.ref!r} is not participant-visible at effective_order {effective_order}: "
                f"disposition {disposition!r}"
            ),
        )
    ]


def _participant_behavior_attribution_ref_authorization_violations(
    *,
    event: ParticipantBehaviorHistoryEvent,
    locator: str,
    boundary: ParticipantObservationBoundaryRuntime,
    relation: Mapping[str, str],
    effective_order: int,
) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for edge in event.attribution_edges:
        violations.extend(
            _participant_behavior_attribution_evidence_ref_violations(
                locator=locator,
                edge=edge,
                refs=edge.evidence_refs,
                boundary=boundary,
                relation=relation,
                effective_order=effective_order,
            )
        )
        violations.extend(
            _participant_behavior_attribution_candidate_ref_violations(
                locator=locator,
                edge=edge,
                candidate=edge.cause_candidate,
                boundary=boundary,
                relation=relation,
                effective_order=effective_order,
            )
        )
        violations.extend(
            _participant_behavior_attribution_candidate_ref_violations(
                locator=locator,
                edge=edge,
                candidate=edge.effect_candidate,
                boundary=boundary,
                relation=relation,
                effective_order=effective_order,
            )
        )
    return violations


def _participant_behavior_history_anchor_indexes(
    events: Iterable[ParticipantBehaviorHistoryEvent],
) -> tuple[dict[str, int], dict[str, int], dict[tuple[str, str | None], int]]:
    action_attempts: dict[str, int] = {}
    state_transitions: dict[str, int] = {}
    observations: dict[tuple[str, str | None], int] = {}
    for index, event in enumerate(events):
        if event.event_type == ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED:
            action_attempts.setdefault(event.action_instance_id, index)
        elif event.event_type == ParticipantBehaviorHistoryEventType.STATE_TRANSITION_RECORDED:
            state_transitions.setdefault(event.action_instance_id, index)
        elif event.event_type == ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED:
            observations.setdefault((event.action_instance_id, event.observation_boundary_address), index)
    return action_attempts, state_transitions, observations


def _participant_behavior_transition_anchor_index(
    *,
    transition: Mapping[str, Any],
    boundary_address: str,
    action_attempts: Mapping[str, int],
    state_transitions: Mapping[str, int],
    observations: Mapping[tuple[str, str | None], int],
) -> int | None:
    event_type = str(transition.get("history_event_type", ""))
    if event_type == "episode_close":
        return None
    action_instance_id = transition.get("action_instance_id")
    if not isinstance(action_instance_id, str) or not action_instance_id:
        return None
    if event_type == "action_attempted":
        return action_attempts.get(action_instance_id)
    if event_type == "state_transition_recorded":
        return state_transitions.get(action_instance_id)
    if event_type == "observation_emitted":
        return observations.get((action_instance_id, boundary_address))
    return None


def _participant_behavior_transition_anchor_violation(
    *,
    transition: Mapping[str, Any],
    boundary_address: str,
    action_attempts: Mapping[str, int],
    state_transitions: Mapping[str, int],
    observations: Mapping[tuple[str, str | None], int],
    episode_close_resolved: bool,
) -> tuple[str, str] | None:
    event_type = str(transition.get("history_event_type", ""))
    action_instance_id = transition.get("action_instance_id")
    transition_id = str(transition.get("transition_id", ""))
    locator = f"{boundary_address}.view_transitions.{transition_id}"
    if event_type == "episode_close":
        if episode_close_resolved:
            return None
        return (
            locator,
            "visibility transition anchor does not resolve to a terminal participant episode history event",
        )
    if not isinstance(action_instance_id, str) or not action_instance_id:
        return (locator, "visibility transition anchors require action_instance_id")
    event_indexes = {
        "action_attempted": action_instance_id in action_attempts,
        "state_transition_recorded": action_instance_id in state_transitions,
        "observation_emitted": (action_instance_id, boundary_address) in observations,
    }
    if event_type not in event_indexes:
        return (locator, f"visibility transition anchor has unknown history_event_type {event_type!r}")
    if event_indexes[event_type]:
        return None
    article = "an" if event_type == "observation_emitted" else "a"
    return (locator, f"visibility transition anchor does not resolve to {article} {event_type} event")


def _participant_behavior_transition_anchor_violations(
    events: list[ParticipantBehaviorHistoryEvent],
    *,
    observation_boundaries: Mapping[str, ParticipantObservationBoundaryRuntime],
    participant_episode_history: Any = None,
) -> Iterator[tuple[str, str]]:
    action_attempts, state_transitions, observations = _participant_behavior_history_anchor_indexes(events)
    episode_close_resolved = _participant_behavior_episode_close_resolved(
        events,
        participant_episode_history=participant_episode_history,
    )
    for boundary_address, boundary in observation_boundaries.items():
        for transition in boundary.view_transitions:
            violation = _participant_behavior_transition_anchor_violation(
                transition=transition,
                boundary_address=boundary_address,
                action_attempts=action_attempts,
                state_transitions=state_transitions,
                observations=observations,
                episode_close_resolved=episode_close_resolved,
            )
            if violation is not None:
                yield violation


def _participant_behavior_episode_close_resolved(
    events: list[ParticipantBehaviorHistoryEvent],
    *,
    participant_episode_history: Any,
) -> bool:
    if not isinstance(participant_episode_history, list):
        return False
    participant_addresses = {event.participant_address for event in events}
    episode_ids = {event.episode_id for event in events}
    if not participant_addresses or not episode_ids:
        return False
    closed_episode_ids: set[str] = set()
    for event in participant_episode_history:
        if not isinstance(event, Mapping):
            continue
        try:
            normalized = ParticipantEpisodeHistoryEvent.from_payload(event)
        except (TypeError, ValueError):
            continue
        if normalized.participant_address not in participant_addresses:
            continue
        if normalized.episode_id not in episode_ids:
            continue
        if normalized.event_type in _PARTICIPANT_EPISODE_TERMINAL_EVENTS:
            closed_episode_ids.add(normalized.episode_id)
    return episode_ids <= closed_episode_ids


def _participant_behavior_observation_effective_relation(
    *,
    observation_index: int,
    boundary_address: str,
    boundary: ParticipantObservationBoundaryRuntime,
    action_attempts: Mapping[str, int],
    state_transitions: Mapping[str, int],
    observations: Mapping[tuple[str, str | None], int],
) -> tuple[dict[str, str], int]:
    relation = _participant_behavior_initial_view_relation(boundary)
    deltas_by_order = _participant_behavior_view_relation_deltas_by_order(boundary)
    effective_order = -1
    for transition in sorted(
        boundary.view_transitions,
        key=lambda item: (
            _participant_behavior_transition_effective_order(item)
            if _participant_behavior_transition_effective_order(item) is not None
            else -1
        ),
    ):
        order = _participant_behavior_transition_effective_order(transition)
        if order is None:
            continue
        anchor_index = _participant_behavior_transition_anchor_index(
            transition=transition,
            boundary_address=boundary_address,
            action_attempts=action_attempts,
            state_transitions=state_transitions,
            observations=observations,
        )
        if anchor_index is None or anchor_index > observation_index:
            continue
        if not _participant_behavior_transition_matches_relation(transition, relation=relation):
            continue
        relation.update(_participant_behavior_transition_delta(transition, deltas_by_order=deltas_by_order))
        effective_order = max(effective_order, order)
    return relation, effective_order


def _participant_behavior_detail_shape_violations_for_events(
    events: list[ParticipantBehaviorHistoryEvent],
) -> Iterator[tuple[str, str]]:
    for index, event in enumerate(events):
        locator = f"{_PARTICIPANT_BEHAVIOR_HISTORY_KEY}[{index}]"
        yield from _participant_behavior_detail_shape_violations(event, locator=locator)


def _participant_behavior_observation_visibility_violations(
    events: list[ParticipantBehaviorHistoryEvent],
    *,
    observation_boundaries: Mapping[str, ParticipantObservationBoundaryRuntime],
) -> Iterator[tuple[str, str]]:
    action_attempts, state_transitions, observations = _participant_behavior_history_anchor_indexes(events)
    for index, event in enumerate(events):
        if event.event_type != ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED:
            continue
        boundary_address = event.observation_boundary_address or ""
        boundary = observation_boundaries.get(boundary_address)
        if boundary is None:
            continue
        locator = f"{_PARTICIPANT_BEHAVIOR_HISTORY_KEY}[{index}]"
        detail_refs, violations = _participant_behavior_observation_detail_refs(event, locator=locator)
        if violations:
            yield from violations
            continue
        if not any(detail_refs.values()):
            continue
        relation, effective_order = _participant_behavior_observation_effective_relation(
            observation_index=index,
            boundary_address=boundary_address,
            boundary=boundary,
            action_attempts=action_attempts,
            state_transitions=state_transitions,
            observations=observations,
        )
        yield from _participant_behavior_visibility_detail_violations(
            locator=locator,
            detail_refs=detail_refs,
            boundary=boundary,
            relation=relation,
            effective_order=effective_order,
        )


def _participant_behavior_action_result_ref_authorization_violations_for_events(
    events: list[ParticipantBehaviorHistoryEvent],
    *,
    observation_boundaries: Mapping[str, ParticipantObservationBoundaryRuntime],
) -> Iterator[tuple[str, str]]:
    action_attempts, state_transitions, observations = _participant_behavior_history_anchor_indexes(events)
    for index, event in enumerate(events):
        if event.event_type != ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED:
            continue
        if event.action_result is None and not event.attribution_edges:
            continue
        boundary_address = event.observation_boundary_address or ""
        boundary = observation_boundaries.get(boundary_address)
        if boundary is None:
            continue
        locator = f"{_PARTICIPANT_BEHAVIOR_HISTORY_KEY}[{index}]"
        relation, effective_order = _participant_behavior_observation_effective_relation(
            observation_index=index,
            boundary_address=boundary_address,
            boundary=boundary,
            action_attempts=action_attempts,
            state_transitions=state_transitions,
            observations=observations,
        )
        if event.action_result is not None:
            yield from _participant_behavior_action_result_ref_authorization_violations(
                event=event,
                locator=locator,
                boundary=boundary,
                relation=relation,
                effective_order=effective_order,
            )
        yield from _participant_behavior_attribution_ref_authorization_violations(
            event=event,
            locator=locator,
            boundary=boundary,
            relation=relation,
            effective_order=effective_order,
        )


def _participant_behavior_address_violations(
    event: ParticipantBehaviorHistoryEvent,
    *,
    locator: str,
    action_contract_addresses: set[str] | frozenset[str] | None,
    observation_boundary_addresses: set[str] | frozenset[str] | None,
) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    if action_contract_addresses is not None and event.action_contract_address not in action_contract_addresses:
        violations.append(
            (
                locator,
                (
                    "participant behavior event references unknown action_contract_address "
                    f"{event.action_contract_address!r}"
                ),
            )
        )
    if (
        observation_boundary_addresses is not None
        and event.observation_boundary_address is not None
        and event.observation_boundary_address not in observation_boundary_addresses
    ):
        violations.append(
            (
                locator,
                (
                    "participant behavior event references unknown observation_boundary_address "
                    f"{event.observation_boundary_address!r}"
                ),
            )
        )
    return violations


def _contract_sem213_temporal_contracts(
    contract: ParticipantActionContractRuntime,
) -> dict[str, Mapping[str, Any]]:
    temporal_contracts = contract.spec.get("temporal_contracts", ())
    if isinstance(temporal_contracts, (str, bytes, Mapping)) or not isinstance(temporal_contracts, Iterable):
        return {}
    return {
        str(temporal_contract.get("temporal_id")): temporal_contract
        for temporal_contract in temporal_contracts
        if isinstance(temporal_contract, Mapping) and temporal_contract.get("temporal_id")
    }


def _contract_sem213_backend_disclosure_ids(contract: ParticipantActionContractRuntime) -> set[str]:
    disclosures = contract.spec.get("backend_timing_disclosures", ())
    if isinstance(disclosures, (str, bytes, Mapping)) or not isinstance(disclosures, Iterable):
        return set()
    return {
        str(disclosure.get("disclosure_id"))
        for disclosure in disclosures
        if isinstance(disclosure, Mapping) and disclosure.get("disclosure_id")
    }


def _participant_temporal_context_contract_violations(
    context: ParticipantTemporalRuntimeContext,
    *,
    contract: ParticipantActionContractRuntime,
) -> list[str]:
    violations: list[str] = []
    temporal_contracts = _contract_sem213_temporal_contracts(contract)
    temporal_contract = temporal_contracts.get(context.temporal_contract_id)
    if temporal_contract is None:
        return [f"temporal context references undeclared temporal_contract_id {context.temporal_contract_id!r}"]

    declared_time_domain = str(temporal_contract.get("time_domain", ""))
    if context.time_domain.value != declared_time_domain:
        violations.append(
            f"temporal context {context.temporal_contract_id!r} time_domain {context.time_domain.value!r} "
            f"does not match compiled contract {declared_time_domain!r}"
        )

    declared_clock_authority = str(temporal_contract.get("clock_authority", ""))
    if context.clock_authority != declared_clock_authority:
        violations.append(
            f"temporal context {context.temporal_contract_id!r} clock_authority {context.clock_authority!r} "
            f"does not match compiled contract {declared_clock_authority!r}"
        )

    declared_event_points = tuple(str(point) for point in temporal_contract.get("event_points", ()))
    observed_event_points = tuple(point.value for point in context.event_points)
    if observed_event_points != declared_event_points:
        violations.append(
            f"temporal context {context.temporal_contract_id!r} event_points {observed_event_points!r} "
            f"do not match compiled contract {declared_event_points!r}"
        )

    declared_contract_disclosures = set(str(ref) for ref in temporal_contract.get("backend_disclosure_refs", ()))
    declared_disclosures = _contract_sem213_backend_disclosure_ids(contract)
    for ref in sorted(set(context.backend_disclosure_refs) - declared_contract_disclosures):
        violations.append(
            f"temporal context {context.temporal_contract_id!r} reports backend_disclosure_ref {ref!r} "
            "not declared by the temporal contract"
        )
    for ref in sorted(set(context.backend_disclosure_refs) - declared_disclosures):
        violations.append(
            f"temporal context {context.temporal_contract_id!r} reports unknown backend_disclosure_ref {ref!r}"
        )

    declared_reset_boundary = temporal_contract.get("reset_boundary")
    if declared_reset_boundary is not None and context.reset_boundary != str(declared_reset_boundary):
        violations.append(
            f"temporal context {context.temporal_contract_id!r} reset_boundary {context.reset_boundary!r} "
            f"does not match compiled contract {str(declared_reset_boundary)!r}"
        )
    declared_replay_boundary = temporal_contract.get("replay_boundary")
    if declared_replay_boundary is not None and context.replay_boundary != str(declared_replay_boundary):
        violations.append(
            f"temporal context {context.temporal_contract_id!r} replay_boundary {context.replay_boundary!r} "
            f"does not match compiled contract {str(declared_replay_boundary)!r}"
        )

    return violations


def _participant_behavior_temporal_contract_violations(
    events: Iterable[ParticipantBehaviorHistoryEvent],
    *,
    action_contracts: Mapping[str, ParticipantActionContractRuntime],
) -> Iterator[tuple[str, str]]:
    for index, event in enumerate(events):
        if not event.temporal_contexts:
            continue
        action_contract_address = event.action_contract_address or ""
        contract = action_contracts.get(action_contract_address)
        locator = f"{_PARTICIPANT_BEHAVIOR_HISTORY_KEY}[{index}]"
        if contract is None:
            yield (locator, f"temporal context cannot resolve action contract {action_contract_address!r}")
            continue
        for context in event.temporal_contexts:
            for violation in _participant_temporal_context_contract_violations(context, contract=contract):
                yield (locator, violation)


def _participant_behavior_action_result_contract_violations(
    events: Iterable[ParticipantBehaviorHistoryEvent],
    *,
    action_contracts: Mapping[str, ParticipantActionContractRuntime],
) -> Iterator[tuple[str, str]]:
    for index, event in enumerate(events):
        if event.event_type != ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED:
            continue
        if event.observation_status not in _PARTICIPANT_TERMINAL_OBSERVATION_STATUSES:
            continue
        action_contract_address = event.action_contract_address or ""
        contract = action_contracts.get(action_contract_address)
        if contract is None or not _contract_uses_sem211_action_results(contract):
            continue
        locator = f"{_PARTICIPANT_BEHAVIOR_HISTORY_KEY}[{index}]"
        if event.action_result is None:
            yield (
                locator,
                f"terminal observation must carry SEM-211 action_result for {action_contract_address}",
            )
            continue
        for violation in validate_participant_action_result_contract(event.action_result, contract):
            yield (locator, violation)


def _normalize_participant_behavior_events(
    participant_behavior_history: list[Any],
    *,
    action_contract_addresses: set[str] | frozenset[str] | None,
    observation_boundary_addresses: set[str] | frozenset[str] | None,
    expected_participant_address: str | None = None,
) -> tuple[list[ParticipantBehaviorHistoryEvent], list[tuple[str, str]]]:
    normalized_events: list[ParticipantBehaviorHistoryEvent] = []
    violations: list[tuple[str, str]] = []
    for index, event in enumerate(participant_behavior_history):
        locator = f"{_PARTICIPANT_BEHAVIOR_HISTORY_KEY}[{index}]"
        if not isinstance(event, Mapping):
            violations.append((locator, "participant behavior history event must be a mapping"))
            continue
        try:
            normalized = ParticipantBehaviorHistoryEvent.from_payload(event)
        except (TypeError, ValueError) as exc:
            violations.append((locator, f"participant behavior history event is invalid: {exc}"))
            continue
        if expected_participant_address is not None and normalized.participant_address != expected_participant_address:
            violations.append(
                (
                    locator,
                    (
                        f"participant behavior history event outer key {expected_participant_address!r} "
                        f"does not match inner participant_address {normalized.participant_address!r}"
                    ),
                )
            )
            continue
        violations.extend(
            _participant_behavior_address_violations(
                normalized,
                locator=locator,
                action_contract_addresses=action_contract_addresses,
                observation_boundary_addresses=observation_boundary_addresses,
            )
        )
        normalized_events.append(normalized)
    return normalized_events, violations


def _participant_behavior_events_by_action_instance(
    events: list[ParticipantBehaviorHistoryEvent],
) -> dict[str, list[ParticipantBehaviorHistoryEvent]]:
    events_by_action_instance: dict[str, list[ParticipantBehaviorHistoryEvent]] = {}
    for event in events:
        events_by_action_instance.setdefault(event.action_instance_id, []).append(event)
    return events_by_action_instance


def _participant_behavior_action_instance_violation(
    action_instance_id: str,
    events: list[ParticipantBehaviorHistoryEvent],
) -> tuple[str, str] | None:
    attempts = [event for event in events if event.event_type == ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED]
    observations = [
        event
        for event in events
        if event.event_type == ParticipantBehaviorHistoryEventType.OBSERVATION_EMITTED
        and event.observation_status in _PARTICIPANT_TERMINAL_OBSERVATION_STATUSES
    ]
    transitions = [
        event for event in events if event.event_type == ParticipantBehaviorHistoryEventType.STATE_TRANSITION_RECORDED
    ]

    if len(attempts) > 1:
        return (action_instance_id, "participant action instance may only have one action_attempted event")
    if len(attempts) == 0:
        return (action_instance_id, "participant behavior events require a matching action_attempted event")
    if len(observations) != 1:
        return (
            action_instance_id,
            "participant action instance requires exactly one terminal observation or orphaned-action observation",
        )
    observation = observations[0]
    if observation.observation_status == ParticipantObservationStatus.ORPHANED_ACTION:
        return None
    if len(transitions) != 1:
        return (action_instance_id, "participant action instance requires exactly one state transition")
    if observation.post_state_digest != transitions[0].post_state_digest:
        return (
            action_instance_id,
            "terminal observation post_state_digest must match the state transition post_state_digest",
        )
    return None


def _participant_behavior_action_instance_violations(
    events: list[ParticipantBehaviorHistoryEvent],
) -> Iterator[tuple[str, str]]:
    for action_instance_id, grouped_events in _participant_behavior_events_by_action_instance(events).items():
        violation = _participant_behavior_action_instance_violation(action_instance_id, grouped_events)
        if violation is not None:
            yield violation


def _participant_behavior_joint_action_order_violations(
    events: Iterable[ParticipantBehaviorHistoryEvent],
) -> Iterator[tuple[str, str]]:
    attempts_by_joint_set: dict[str, list[ParticipantBehaviorHistoryEvent]] = {}
    for event in events:
        if (
            event.event_type == ParticipantBehaviorHistoryEventType.ACTION_ATTEMPTED
            and event.joint_action_set_id is not None
        ):
            attempts_by_joint_set.setdefault(event.joint_action_set_id, []).append(event)

    for joint_action_set_id, attempts in sorted(attempts_by_joint_set.items()):
        attempts_by_order: dict[int, list[ParticipantBehaviorHistoryEvent]] = {}
        for event in attempts:
            if event.realized_order is None:
                continue
            attempts_by_order.setdefault(event.realized_order, []).append(event)
        for realized_order, duplicate_attempts in sorted(attempts_by_order.items()):
            if len(duplicate_attempts) <= 1:
                continue
            instances = ", ".join(
                sorted(f"{event.participant_address}/{event.action_instance_id}" for event in duplicate_attempts)
            )
            yield (
                f"joint-action-set.{joint_action_set_id}",
                (
                    f"joint action set realized_order {realized_order} is assigned to "
                    f"multiple action_attempted events: {instances}"
                ),
            )


def iter_participant_behavior_history_violations(
    participant_behavior_history: Any,
    *,
    action_contract_addresses: set[str] | frozenset[str] | None = None,
    action_contracts: Mapping[str, ParticipantActionContractRuntime] | None = None,
    observation_boundary_addresses: set[str] | frozenset[str] | None = None,
    observation_boundaries: Mapping[str, ParticipantObservationBoundaryRuntime] | None = None,
    participant_episode_history: Any = None,
    expected_participant_address: str | None = None,
) -> Iterator[tuple[str, str]]:
    """Yield every SEM-208 behavior-history invariant violation.

    The helper checks that each action instance has one terminal observation
    paired with the state transition digest it reports. When compiled address
    sets are provided, it also rejects references outside those sets. When
    compiled observation boundaries are provided, SEM-210 observation details
    and SEM-211 action-result references are checked against the time-indexed
    participant view relation.
    """

    if not isinstance(participant_behavior_history, list):
        yield (_PARTICIPANT_BEHAVIOR_HISTORY_KEY, "participant behavior history must be a list of events")
        return
    if action_contracts is not None and action_contract_addresses is None:
        action_contract_addresses = frozenset(action_contracts.keys())
    if observation_boundaries is not None and observation_boundary_addresses is None:
        observation_boundary_addresses = frozenset(observation_boundaries.keys())

    normalized_events, entry_violations = _normalize_participant_behavior_events(
        participant_behavior_history,
        action_contract_addresses=action_contract_addresses,
        observation_boundary_addresses=observation_boundary_addresses,
        expected_participant_address=expected_participant_address,
    )
    if entry_violations:
        yield from entry_violations
        return

    yield from _participant_behavior_detail_shape_violations_for_events(normalized_events)
    yield from _participant_behavior_action_instance_violations(normalized_events)
    yield from _participant_behavior_joint_action_order_violations(normalized_events)
    if action_contracts is not None:
        yield from _participant_behavior_action_result_contract_violations(
            normalized_events,
            action_contracts=action_contracts,
        )
        yield from _participant_behavior_temporal_contract_violations(
            normalized_events,
            action_contracts=action_contracts,
        )
    if observation_boundaries is not None:
        yield from _participant_behavior_transition_anchor_violations(
            normalized_events,
            observation_boundaries=observation_boundaries,
            participant_episode_history=participant_episode_history,
        )
        yield from _participant_behavior_observation_visibility_violations(
            normalized_events,
            observation_boundaries=observation_boundaries,
        )
        yield from _participant_behavior_action_result_ref_authorization_violations_for_events(
            normalized_events,
            observation_boundaries=observation_boundaries,
        )


def iter_participant_behavior_joint_action_violations(
    participant_behavior_history_by_participant: Any,
) -> Iterator[tuple[str, str]]:
    """Yield SEM-209 joint-action ordering violations across participant histories."""

    if not isinstance(participant_behavior_history_by_participant, Mapping):
        yield (_PARTICIPANT_BEHAVIOR_HISTORY_KEY, "participant behavior histories must be a mapping")
        return

    normalized_events: list[ParticipantBehaviorHistoryEvent] = []
    for history in participant_behavior_history_by_participant.values():
        if not isinstance(history, list):
            continue
        participant_events, entry_violations = _normalize_participant_behavior_events(
            history,
            action_contract_addresses=None,
            observation_boundary_addresses=None,
        )
        if entry_violations:
            continue
        normalized_events.extend(participant_events)

    yield from _participant_behavior_joint_action_order_violations(normalized_events)


def iter_participant_episode_snapshot_violations(
    participant_episode_results: Any,
    participant_episode_history: Any,
) -> Iterator[tuple[str, str]]:
    """Yield every participant-episode invariant violation in a snapshot.

    Both arguments are the raw ``RuntimeSnapshot.participant_episode_results``
    and ``RuntimeSnapshot.participant_episode_history`` maps keyed by the
    stable ``participant_address``. The helper exists so that the runtime
    manager apply path and the conformance semantic-check path share one
    source of truth for RUN-311 invariants; each caller wraps the yielded
    ``(address, message)`` tuples in its own diagnostic type.

    The following invariants are checked:

    - ``participant_episode_results`` / ``_history`` are mappings.
    - Each outer key is a non-empty string.
    - Each result value is a mapping and reconstructs through
      ``ParticipantEpisodeExecutionState.from_payload`` (i.e. respects the
      state-machine invariants enforced in ``__post_init__``).
    - Each result's inner ``participant_address`` matches the outer key.
    - Each history value is a list of mappings and every event reconstructs
      through ``ParticipantEpisodeHistoryEvent.from_payload``.
    - Each history event's inner ``participant_address`` matches the outer
      key.
    - Within one participant's history, ``sequence_number`` is monotonic
      non-decreasing.
    - Within one sequence number, ``episode_id`` is stable.
    - Cross-sequence transitions are gated by an ``EPISODE_RESET`` or
      ``EPISODE_RESTARTED`` event (the first sequence number observed in
      a history stream is exempt because history may be truncated).
    - When both a ``participant_episode_results`` entry and a non-empty
      ``participant_episode_history`` entry exist for the same
      participant, the current result must match the head of the history
      chain: same ``episode_id``, same ``sequence_number``, and a status
      that is consistent with the head event type and terminal reason.
      A stale result that points at an earlier episode than the history
      shows is a semantic inconsistency that breaks replay and operator
      reasoning.
    """

    results_key = "runtime.snapshot.participant-episode-results"
    history_key = "runtime.snapshot.participant-episode-history"

    if not isinstance(participant_episode_results, Mapping):
        yield (results_key, "participant_episode_results must be a mapping")
    else:
        for outer_key, result in participant_episode_results.items():
            if not isinstance(outer_key, str) or not outer_key:
                yield (results_key, "participant episode result keys must be non-empty strings")
                continue
            if not isinstance(result, Mapping):
                yield (outer_key, "participant episode result must be a mapping")
                continue
            try:
                normalized_result = ParticipantEpisodeExecutionState.from_payload(result)
            except (TypeError, ValueError) as exc:
                yield (outer_key, f"participant episode result is invalid: {exc}")
                continue
            if normalized_result.participant_address != outer_key:
                yield (
                    outer_key,
                    (
                        f"participant episode result outer key {outer_key!r} does not match "
                        f"inner participant_address {normalized_result.participant_address!r}"
                    ),
                )

    if not isinstance(participant_episode_history, Mapping):
        yield (history_key, "participant_episode_history must be a mapping")
        return

    for outer_key, history in participant_episode_history.items():
        if not isinstance(outer_key, str) or not outer_key:
            yield (history_key, "participant episode history keys must be non-empty strings")
            continue
        if not isinstance(history, list):
            yield (outer_key, "participant episode history must be a list of events")
            continue
        normalized_events: list[ParticipantEpisodeHistoryEvent] = []
        per_entry_violations = False
        for index, event in enumerate(history):
            locator = f"{outer_key}[{index}]"
            if not isinstance(event, Mapping):
                yield (locator, "participant episode history event must be a mapping")
                per_entry_violations = True
                continue
            try:
                normalized_event = ParticipantEpisodeHistoryEvent.from_payload(event)
            except (TypeError, ValueError) as exc:
                yield (locator, f"participant episode history event is invalid: {exc}")
                per_entry_violations = True
                continue
            if normalized_event.participant_address != outer_key:
                yield (
                    locator,
                    (
                        f"participant episode history event outer key {outer_key!r} does not match "
                        f"inner participant_address {normalized_event.participant_address!r}"
                    ),
                )
                per_entry_violations = True
                continue
            normalized_events.append(normalized_event)

        if per_entry_violations:
            continue

        last_sequence = -1
        sequence_to_episode: dict[int, str] = {}
        for index, event in enumerate(normalized_events):
            locator = f"{outer_key}[{index}]"
            # A strict backward movement cannot be reconciled into the same
            # stream, so the event is dropped and stream state is not
            # advanced for it. Every other violation path still advances
            # stream state so that downstream events are not re-checked
            # against stale ``last_sequence`` / ``sequence_to_episode``
            # values.
            if event.sequence_number < last_sequence:
                yield (
                    locator,
                    (
                        f"participant episode history sequence_number went backward "
                        f"({last_sequence} -> {event.sequence_number})"
                    ),
                )
                continue
            if (
                event.sequence_number > last_sequence
                and last_sequence != -1
                and event.event_type
                not in {
                    ParticipantEpisodeHistoryEventType.EPISODE_RESET,
                    ParticipantEpisodeHistoryEventType.EPISODE_RESTARTED,
                }
            ):
                yield (
                    locator,
                    (
                        f"participant episode transition to sequence_number "
                        f"{event.sequence_number} must arrive via episode_reset or "
                        f"episode_restarted; saw {event.event_type.value}"
                    ),
                )
            expected_episode_id = sequence_to_episode.get(event.sequence_number)
            if expected_episode_id is not None and expected_episode_id != event.episode_id:
                yield (
                    locator,
                    (
                        f"participant episode history episode_id changed within "
                        f"sequence_number {event.sequence_number}: "
                        f"{expected_episode_id!r} -> {event.episode_id!r}"
                    ),
                )
            sequence_to_episode[event.sequence_number] = event.episode_id
            last_sequence = event.sequence_number

    # Cross-check: when both a result and a non-empty history exist for the
    # same participant, the result must match the head of the history chain.
    # An absent history is allowed (truncated observation); a present history
    # whose last event describes a different episode than the current result
    # is a stale result that breaks replay and operator reasoning.
    if isinstance(participant_episode_results, Mapping) and isinstance(participant_episode_history, Mapping):
        for outer_key, result in participant_episode_results.items():
            if not isinstance(outer_key, str) or not outer_key:
                continue
            if not isinstance(result, Mapping):
                continue
            history = participant_episode_history.get(outer_key)
            if not isinstance(history, list) or not history:
                continue
            try:
                normalized_result = ParticipantEpisodeExecutionState.from_payload(result)
            except (TypeError, ValueError):
                continue
            last_event: ParticipantEpisodeHistoryEvent | None = None
            for event in history:
                if not isinstance(event, Mapping):
                    continue
                try:
                    candidate = ParticipantEpisodeHistoryEvent.from_payload(event)
                except (TypeError, ValueError):
                    continue
                if candidate.participant_address != outer_key:
                    continue
                last_event = candidate
            if last_event is None:
                continue
            if (
                last_event.episode_id != normalized_result.episode_id
                or last_event.sequence_number != normalized_result.sequence_number
            ):
                yield (
                    outer_key,
                    (
                        f"participant episode result (episode_id="
                        f"{normalized_result.episode_id!r}, sequence_number="
                        f"{normalized_result.sequence_number}) does not match head of "
                        f"history chain (episode_id={last_event.episode_id!r}, "
                        f"sequence_number={last_event.sequence_number})"
                    ),
                )
                continue
            if normalized_result.status == ParticipantEpisodeStatus.TERMINATED:
                if last_event.event_type not in _PARTICIPANT_EPISODE_TERMINAL_EVENTS:
                    yield (
                        outer_key,
                        (
                            f"participant episode result status is 'terminated' but head "
                            f"history event is {last_event.event_type.value!r}, not a "
                            f"terminal event"
                        ),
                    )
                elif normalized_result.terminal_reason != last_event.terminal_reason:
                    expected = (
                        normalized_result.terminal_reason.value
                        if normalized_result.terminal_reason is not None
                        else None
                    )
                    got = last_event.terminal_reason.value if last_event.terminal_reason is not None else None
                    yield (
                        outer_key,
                        (
                            f"participant episode result terminal_reason {expected!r} does "
                            f"not match head history terminal_reason {got!r}"
                        ),
                    )
            elif normalized_result.status in (
                ParticipantEpisodeStatus.INITIALIZING,
                ParticipantEpisodeStatus.RUNNING,
            ):
                if last_event.event_type in _PARTICIPANT_EPISODE_TERMINAL_EVENTS:
                    yield (
                        outer_key,
                        (
                            f"participant episode result status is "
                            f"{normalized_result.status.value!r} but head history event is "
                            f"terminal ({last_event.event_type.value!r})"
                        ),
                    )


def validate_evaluation_result(
    contract: EvaluationResultContract,
    state: EvaluationExecutionState,
) -> list[str]:
    """Return contract violations for one evaluator result envelope."""

    violations: list[str] = []
    if state.resource_type != contract.resource_type:
        violations.append(
            f"Result resource_type {state.resource_type!r} does not match compiled contract {contract.resource_type!r}."
        )
    if state.state_schema_version != contract.state_schema_version:
        violations.append(
            "Result state_schema_version "
            f"{state.state_schema_version!r} does not match compiled contract "
            f"{contract.state_schema_version!r}."
        )
    if not contract.supports_passed and state.passed is not None:
        violations.append("Result may not report 'passed' for this resource type.")
    if contract.supports_passed and state.status == EvaluationResultStatus.READY and state.passed is None:
        violations.append("Ready result must report 'passed' for this resource type.")
    if not contract.supports_score and (state.score is not None or state.max_score is not None):
        violations.append("Result may not report score fields for this resource type.")
    if contract.supports_score and state.status == EvaluationResultStatus.READY and state.score is None:
        violations.append("Ready result must report 'score' for this resource type.")
    if contract.fixed_max_score is not None:
        if state.status == EvaluationResultStatus.READY and state.max_score != contract.fixed_max_score:
            violations.append(f"Ready result must report max_score {contract.fixed_max_score} for this resource type.")
    return violations


@dataclass(frozen=True)
class MetricRuntime(ResolvedResource):
    """Resolved metric node."""

    condition_name: str = ""
    condition_addresses: tuple[str, ...] = ()
    result_contract: "EvaluationResultContract" = field(
        default_factory=lambda: EvaluationResultContract(resource_type="metric")
    )
    execution_contract: "EvaluationExecutionContract" = field(
        default_factory=lambda: EvaluationExecutionContract(resource_type="metric")
    )


@dataclass(frozen=True)
class EvaluationRuntime(ResolvedResource):
    """Resolved evaluation node."""

    metric_addresses: tuple[str, ...] = ()
    result_contract: "EvaluationResultContract" = field(
        default_factory=lambda: EvaluationResultContract(resource_type="evaluation")
    )
    execution_contract: "EvaluationExecutionContract" = field(
        default_factory=lambda: EvaluationExecutionContract(resource_type="evaluation")
    )


@dataclass(frozen=True)
class TLORuntime(ResolvedResource):
    """Resolved TLO node."""

    evaluation_address: str = ""
    result_contract: "EvaluationResultContract" = field(
        default_factory=lambda: EvaluationResultContract(resource_type="tlo")
    )
    execution_contract: "EvaluationExecutionContract" = field(
        default_factory=lambda: EvaluationExecutionContract(resource_type="tlo")
    )


@dataclass(frozen=True)
class GoalRuntime(ResolvedResource):
    """Resolved goal node."""

    tlo_addresses: tuple[str, ...] = ()
    result_contract: "EvaluationResultContract" = field(
        default_factory=lambda: EvaluationResultContract(resource_type="goal")
    )
    execution_contract: "EvaluationExecutionContract" = field(
        default_factory=lambda: EvaluationExecutionContract(resource_type="goal")
    )


@dataclass(frozen=True)
class ObjectiveRuntime(ResolvedResource):
    """Resolved objective node."""

    actor_type: str = ""
    actor_name: str = ""
    success_addresses: tuple[str, ...] = ()
    objective_dependencies: tuple[str, ...] = ()
    window_story_addresses: tuple[str, ...] = ()
    window_script_addresses: tuple[str, ...] = ()
    window_event_addresses: tuple[str, ...] = ()
    window_workflow_addresses: tuple[str, ...] = ()
    window_step_refs: tuple[str, ...] = ()
    window_step_workflow_addresses: tuple[str, ...] = ()
    window_references: tuple[ObjectiveWindowReferenceRuntime, ...] = ()
    result_contract: "EvaluationResultContract" = field(
        default_factory=lambda: EvaluationResultContract(resource_type="objective")
    )
    execution_contract: "EvaluationExecutionContract" = field(
        default_factory=lambda: EvaluationExecutionContract(resource_type="objective")
    )


@dataclass(frozen=True)
class RuntimeModel:
    """Compiled SDL runtime model.

    Reusable definitions stay as templates or metadata. Only bound runtime
    instances become planned resources.
    """

    scenario_name: str
    feature_templates: dict[str, RuntimeTemplate] = field(default_factory=dict)
    condition_templates: dict[str, RuntimeTemplate] = field(default_factory=dict)
    inject_templates: dict[str, RuntimeTemplate] = field(default_factory=dict)
    vulnerability_templates: dict[str, RuntimeTemplate] = field(default_factory=dict)
    entity_specs: dict[str, dict[str, Any]] = field(default_factory=dict)
    agent_specs: dict[str, dict[str, Any]] = field(default_factory=dict)
    relationship_specs: dict[str, dict[str, Any]] = field(default_factory=dict)
    variable_specs: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Pre-instantiation `${name}` refs on `nodes.os` and `infrastructure.count`,
    # keyed by the network/node resource address. Lets the planner reach a
    # variable's `allowed_values` even after `compile_runtime_model` substitutes
    # the resolved values onto the corresponding runtime resources. Kept on the
    # model rather than on the resources themselves so the provenance does not
    # leak into the backend-facing `resource_payload()` envelope. Inner dict
    # carries `"os"` and `"count"` keys; missing or `None` values mean the
    # field was authored as a concrete literal rather than a variable ref.
    node_variable_refs: dict[str, dict[str, str | None]] = field(default_factory=dict)
    networks: dict[str, NetworkRuntime] = field(default_factory=dict)
    node_deployments: dict[str, NodeRuntime] = field(default_factory=dict)
    feature_bindings: dict[str, FeatureBinding] = field(default_factory=dict)
    condition_bindings: dict[str, ConditionBinding] = field(default_factory=dict)
    injects: dict[str, InjectRuntime] = field(default_factory=dict)
    inject_bindings: dict[str, InjectBinding] = field(default_factory=dict)
    content_placements: dict[str, ContentPlacement] = field(default_factory=dict)
    account_placements: dict[str, AccountPlacement] = field(default_factory=dict)
    action_contracts: dict[str, ParticipantActionContractRuntime] = field(default_factory=dict)
    observation_boundaries: dict[str, ParticipantObservationBoundaryRuntime] = field(default_factory=dict)
    participant_behaviors: dict[str, ParticipantBehaviorRuntime] = field(default_factory=dict)
    events: dict[str, EventRuntime] = field(default_factory=dict)
    scripts: dict[str, ScriptRuntime] = field(default_factory=dict)
    stories: dict[str, StoryRuntime] = field(default_factory=dict)
    workflows: dict[str, WorkflowRuntime] = field(default_factory=dict)
    metrics: dict[str, MetricRuntime] = field(default_factory=dict)
    evaluations: dict[str, EvaluationRuntime] = field(default_factory=dict)
    tlos: dict[str, TLORuntime] = field(default_factory=dict)
    goals: dict[str, GoalRuntime] = field(default_factory=dict)
    objectives: dict[str, ObjectiveRuntime] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass(frozen=True)
class PlannedResource:
    """Normalized resource used by the planner and snapshot."""

    address: str
    domain: RuntimeDomain
    resource_type: str
    payload: dict[str, Any]
    ordering_dependencies: tuple[str, ...] = ()
    refresh_dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanOperation:
    """A reconciliation operation for a planned resource."""

    action: ChangeAction
    address: str
    resource_type: str
    payload: dict[str, Any]
    ordering_dependencies: tuple[str, ...] = ()
    refresh_dependencies: tuple[str, ...] = ()


class ProvisionOp(PlanOperation):
    """Provisioning reconciliation operation."""


class OrchestrationOp(PlanOperation):
    """Orchestration reconciliation operation."""


class EvaluationOp(PlanOperation):
    """Evaluation reconciliation operation."""


@dataclass(frozen=True)
class ProvisioningPlan:
    """Provisioning plan over canonical deployment resources."""

    resources: dict[str, PlannedResource] = field(default_factory=dict)
    operations: list[ProvisionOp] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def actionable_operations(self) -> list[ProvisionOp]:
        return [op for op in self.operations if op.action != ChangeAction.UNCHANGED]


@dataclass(frozen=True)
class OrchestrationPlan:
    """Resolved orchestration graph and reconciliation actions."""

    resources: dict[str, PlannedResource] = field(default_factory=dict)
    operations: list[OrchestrationOp] = field(default_factory=list)
    startup_order: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def actionable_operations(self) -> list[OrchestrationOp]:
        return [op for op in self.operations if op.action != ChangeAction.UNCHANGED]


@dataclass(frozen=True)
class EvaluationPlan:
    """Resolved evaluation graph and reconciliation actions."""

    resources: dict[str, PlannedResource] = field(default_factory=dict)
    operations: list[EvaluationOp] = field(default_factory=list)
    startup_order: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def actionable_operations(self) -> list[EvaluationOp]:
        return [op for op in self.operations if op.action != ChangeAction.UNCHANGED]


@dataclass(frozen=True)
class ExecutionPlan:
    """Composite runtime execution plan."""

    target_name: str | None
    manifest: BackendManifest
    base_snapshot: "RuntimeSnapshot"
    scenario_name: str
    model: RuntimeModel
    provisioning: ProvisioningPlan
    orchestration: OrchestrationPlan
    evaluation: EvaluationPlan
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(diag.is_error for diag in self.diagnostics)


@dataclass(frozen=True)
class SnapshotEntry:
    """Recorded runtime state for a single canonical resource."""

    address: str
    domain: RuntimeDomain
    resource_type: str
    payload: dict[str, Any]
    ordering_dependencies: tuple[str, ...] = ()
    refresh_dependencies: tuple[str, ...] = ()
    status: str = "ready"


@dataclass
class RuntimeSnapshot:
    """Current runtime snapshot.

    Participant episode surfaces (``participant_episode_results`` and
    ``participant_episode_history``) are both keyed by the stable
    ``participant_address``. Participant behavior history is also keyed by
    that stable address and records SEM-208 action/observation/state
    transition events using compiled behavior-contract addresses. The episode
    results map holds the *current* live episode state for each participant;
    prior episode instances are preserved only through append-only history
    streams and the ``previous_episode_id`` chain on each state.
    """

    entries: dict[str, SnapshotEntry] = field(default_factory=dict)
    orchestration_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    orchestration_history: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    evaluation_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    evaluation_history: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    participant_episode_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    participant_episode_history: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    participant_behavior_history: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get(self, address: str) -> SnapshotEntry | None:
        return self.entries.get(address)

    def for_domain(self, domain: RuntimeDomain) -> dict[str, SnapshotEntry]:
        return {address: entry for address, entry in self.entries.items() if entry.domain == domain}

    def with_entries(
        self,
        entries: dict[str, SnapshotEntry],
        *,
        orchestration_results: dict[str, dict[str, Any]] | None = None,
        orchestration_history: dict[str, list[dict[str, Any]]] | None = None,
        evaluation_results: dict[str, dict[str, Any]] | None = None,
        evaluation_history: dict[str, list[dict[str, Any]]] | None = None,
        participant_episode_results: dict[str, dict[str, Any]] | None = None,
        participant_episode_history: dict[str, list[dict[str, Any]]] | None = None,
        participant_behavior_history: dict[str, list[dict[str, Any]]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "RuntimeSnapshot":
        return RuntimeSnapshot(
            entries=entries,
            orchestration_results=(
                dict(self.orchestration_results) if orchestration_results is None else dict(orchestration_results)
            ),
            orchestration_history=(
                {workflow_address: list(events) for workflow_address, events in self.orchestration_history.items()}
                if orchestration_history is None
                else {workflow_address: list(events) for workflow_address, events in orchestration_history.items()}
            ),
            evaluation_results=(
                dict(self.evaluation_results) if evaluation_results is None else dict(evaluation_results)
            ),
            evaluation_history=(
                {address: list(events) for address, events in self.evaluation_history.items()}
                if evaluation_history is None
                else {address: list(events) for address, events in evaluation_history.items()}
            ),
            participant_episode_results=(
                dict(self.participant_episode_results)
                if participant_episode_results is None
                else dict(participant_episode_results)
            ),
            participant_episode_history=(
                {
                    participant_address: list(events)
                    for participant_address, events in self.participant_episode_history.items()
                }
                if participant_episode_history is None
                else {
                    participant_address: list(events)
                    for participant_address, events in participant_episode_history.items()
                }
            ),
            participant_behavior_history=(
                {
                    participant_address: list(events)
                    for participant_address, events in self.participant_behavior_history.items()
                }
                if participant_behavior_history is None
                else {
                    participant_address: list(events)
                    for participant_address, events in participant_behavior_history.items()
                }
            ),
            metadata=dict(self.metadata) if metadata is None else dict(metadata),
        )


@dataclass
class ApplyResult:
    """Result of applying or starting a runtime plan."""

    success: bool
    snapshot: RuntimeSnapshot
    diagnostics: list[Diagnostic] = field(default_factory=list)
    changed_addresses: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowCancellationRequest:
    """Portable request for cancelling one workflow run."""

    workflow_address: str
    run_id: str | None = None
    reason: str = "cancelled by operator"


@dataclass(frozen=True)
class ParticipantEpisodeInitializeRequest:
    """Portable request for initializing the first episode of a participant.

    Carries the stable ``participant_address`` plus an optional
    caller-provided ``episode_id`` hint (the backend allocates one if the
    caller does not supply one). See RUN-311.
    """

    participant_address: str
    episode_id: str | None = None


@dataclass(frozen=True)
class ParticipantEpisodeResetRequest:
    """Portable request for resetting a non-terminal participant episode.

    The backend must allocate a new ``episode_id``, increment
    ``sequence_number``, preserve the stable participant identity, and
    link to the prior episode via ``previous_episode_id``.
    """

    participant_address: str
    episode_id: str | None = None
    reason: str = "reset by operator"


@dataclass(frozen=True)
class ParticipantEpisodeRestartRequest:
    """Portable request for restarting a terminated participant episode.

    The backend must allocate a new ``episode_id``, increment
    ``sequence_number``, preserve the stable participant identity, and
    link to the prior episode via ``previous_episode_id``.
    """

    participant_address: str
    episode_id: str | None = None
    reason: str = "restarted by operator"


@dataclass(frozen=True)
class ParticipantEpisodeTerminateRequest:
    """Portable request for driving the current episode to ``TERMINATED``.

    The ``terminal_reason`` must be one of the published
    ``ParticipantEpisodeTerminalReason`` values; the control plane
    defaults to ``INTERRUPTED`` for operator-driven termination but
    backends may also call this method with a terminal reason reflecting
    an internally-detected ``COMPLETED``, ``TIMED_OUT``, or ``TRUNCATED``
    condition.
    """

    participant_address: str
    terminal_reason: ParticipantEpisodeTerminalReason = ParticipantEpisodeTerminalReason.INTERRUPTED
    detail: str = "terminated by operator"


@dataclass(frozen=True)
class OperationReceipt:
    """Portable acknowledgment for an accepted control-plane operation."""

    schema_version: str = OPERATION_SCHEMA_VERSION
    operation_id: str = ""
    domain: RuntimeDomain = RuntimeDomain.PROVISIONING
    submitted_at: str = ""
    accepted: bool = True
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass(frozen=True)
class OperationStatus:
    """Portable status for a submitted control-plane operation."""

    schema_version: str = OPERATION_SCHEMA_VERSION
    operation_id: str = ""
    domain: RuntimeDomain = RuntimeDomain.PROVISIONING
    state: OperationState = OperationState.ACCEPTED
    submitted_at: str = ""
    updated_at: str = ""
    diagnostics: list[Diagnostic] = field(default_factory=list)
    changed_addresses: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RuntimeSnapshotEnvelope:
    """Portable envelope around the current runtime snapshot."""

    schema_version: str = RUNTIME_SNAPSHOT_SCHEMA_VERSION
    snapshot: RuntimeSnapshot = field(default_factory=RuntimeSnapshot)


def resource_payload(resource: ResolvedResource) -> dict[str, Any]:
    """Convert a compiled resource to a stable planner payload."""

    payload = asdict(resource)
    payload.pop("address", None)
    payload.pop("ordering_dependencies", None)
    payload.pop("refresh_dependencies", None)
    return payload
