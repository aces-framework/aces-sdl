"""Stub runtime backends for compiler/planner testing."""

from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version

from aces_backend_protocols.capabilities import (
    BackendCapabilitySet,
    BackendManifest,
    EvaluatorCapabilities,
    OrchestratorCapabilities,
    ParticipantRuntimeCapabilities,
    ProvisionerCapabilities,
    WorkflowFeature,
    WorkflowStatePredicateFeature,
)
from aces_contracts.apparatus import ConceptBinding, RealizationSupportDeclaration
from aces_contracts.manifest_authority import BACKEND_SUPPORTED_CONTRACT_IDS
from aces_contracts.vocabulary import RealizationSupportMode
from aces_processor.models import (
    EVALUATION_STATE_SCHEMA_VERSION,
    ApplyResult,
    ChangeAction,
    Diagnostic,
    EvaluationPlan,
    OrchestrationPlan,
    ParticipantEpisodeControlAction,
    ParticipantEpisodeExecutionState,
    ParticipantEpisodeHistoryEvent,
    ParticipantEpisodeHistoryEventType,
    ParticipantEpisodeInitializeRequest,
    ParticipantEpisodeResetRequest,
    ParticipantEpisodeRestartRequest,
    ParticipantEpisodeStatus,
    ParticipantEpisodeTerminalReason,
    ParticipantEpisodeTerminateRequest,
    ProvisioningPlan,
    RuntimeDomain,
    RuntimeSnapshot,
    SnapshotEntry,
)
from aces_processor.registry import RuntimeTarget, RuntimeTargetComponents

REFERENCE_BACKEND_SUPPORTED_CONTRACT_VERSIONS = BACKEND_SUPPORTED_CONTRACT_IDS


def _current_backend_version() -> str:
    try:
        return distribution_version("aces-sdl")
    except PackageNotFoundError:
        return "0.0.0+unknown"


def create_stub_manifest(
    *,
    with_participant_runtime: bool = True,
    **config,
) -> BackendManifest:
    """Return the fully capable stub manifest.

    ``with_participant_runtime=False`` omits the participant runtime
    capability block so legacy tests that construct targets with only
    provisioner/orchestrator/evaluator components still satisfy
    ``registry.target-shape-mismatch`` validation. Production callers
    should leave this at its default.
    """

    del config
    supported_contract_versions = set(REFERENCE_BACKEND_SUPPORTED_CONTRACT_VERSIONS)
    if not with_participant_runtime:
        supported_contract_versions.discard("participant-episode-state-envelope-v1")
        supported_contract_versions.discard("participant-episode-history-event-stream-v1")
    return BackendManifest(
        name="stub",
        version=_current_backend_version(),
        supported_contract_versions=frozenset(supported_contract_versions),
        compatible_processors=frozenset({"aces-reference-processor"}),
        concept_bindings=(
            ConceptBinding(scope="capabilities.provisioner.supported_node_types", family="assets"),
            ConceptBinding(scope="capabilities.provisioner.supported_os_families", family="assets"),
            ConceptBinding(scope="capabilities.provisioner.supported_content_types", family="tools-and-artifacts"),
            ConceptBinding(scope="capabilities.provisioner.supported_account_features", family="identities"),
            ConceptBinding(scope="capabilities.orchestrator.supported_sections", family="actions-and-events"),
            ConceptBinding(scope="capabilities.evaluator.supported_sections", family="observables"),
        ),
        realization_support=(
            RealizationSupportDeclaration(
                domain="runtime-realization",
                support_mode=RealizationSupportMode.CONSTRAINED,
                supported_constraint_kinds=frozenset(
                    {
                        "node-type",
                        "os-family",
                        "content-type",
                        "account-feature",
                        "workflow-feature",
                        "workflow-state-predicate",
                    }
                ),
                supported_exact_requirement_kinds=frozenset({"declared-capability-match"}),
                disclosure_kinds=frozenset(
                    {
                        "backend-manifest-v2",
                        "runtime-snapshot-v1",
                        "operation-status-v1",
                    }
                ),
            ),
        ),
        capabilities=BackendCapabilitySet(
            provisioner=ProvisionerCapabilities(
                name="stub-provisioner",
                supported_node_types=frozenset({"vm", "switch"}),
                supported_os_families=frozenset({"linux", "windows", "macos", "freebsd", "other"}),
                supported_content_types=frozenset({"file", "dataset", "directory"}),
                supported_account_features=frozenset(
                    {"groups", "mail", "spn", "shell", "home", "disabled", "auth_method"}
                ),
                max_total_nodes=None,
                supports_acls=True,
                supports_accounts=True,
            ),
            orchestrator=OrchestratorCapabilities(
                name="stub-orchestrator",
                supported_sections=frozenset({"injects", "events", "scripts", "stories", "workflows"}),
                supports_workflows=True,
                supports_condition_refs=True,
                supports_inject_bindings=True,
                supported_workflow_features=frozenset(
                    {
                        WorkflowFeature.DECISION,
                        WorkflowFeature.SWITCH,
                        WorkflowFeature.CALL,
                        WorkflowFeature.PARALLEL_BARRIER,
                        WorkflowFeature.RETRY,
                        WorkflowFeature.FAILURE_TRANSITIONS,
                        WorkflowFeature.CANCELLATION,
                        WorkflowFeature.TIMEOUTS,
                        WorkflowFeature.COMPENSATION,
                    }
                ),
                supported_workflow_state_predicates=frozenset(
                    {
                        WorkflowStatePredicateFeature.OUTCOME_MATCHING,
                        WorkflowStatePredicateFeature.ATTEMPT_COUNTS,
                    }
                ),
            ),
            evaluator=EvaluatorCapabilities(
                name="stub-evaluator",
                supported_sections=frozenset({"conditions", "metrics", "evaluations", "tlos", "goals", "objectives"}),
                supports_scoring=True,
                supports_objectives=True,
            ),
            participant_runtime=(
                ParticipantRuntimeCapabilities(name="stub-participant-runtime") if with_participant_runtime else None
            ),
        ),
    )


class StubProvisioner:
    """In-memory provisioner."""

    def validate(self, plan: ProvisioningPlan) -> list[Diagnostic]:
        return []

    def apply(
        self,
        plan: ProvisioningPlan,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        entries = dict(snapshot.entries)
        changed_addresses: list[str] = []
        for op in plan.operations:
            if op.action == ChangeAction.DELETE:
                entries.pop(op.address, None)
                changed_addresses.append(op.address)
                continue
            status = "unchanged" if op.action == ChangeAction.UNCHANGED else "applied"
            entries[op.address] = SnapshotEntry(
                address=op.address,
                domain=RuntimeDomain.PROVISIONING,
                resource_type=op.resource_type,
                payload=op.payload,
                ordering_dependencies=op.ordering_dependencies,
                refresh_dependencies=op.refresh_dependencies,
                status=status,
            )
            if op.action != ChangeAction.UNCHANGED:
                changed_addresses.append(op.address)

        return ApplyResult(
            success=True,
            snapshot=snapshot.with_entries(entries),
            changed_addresses=changed_addresses,
        )


class StubOrchestrator:
    """In-memory orchestrator."""

    def __init__(self) -> None:
        self._running = False
        self._startup_order: list[str] = []
        self._results: dict[str, dict[str, object]] = {}
        self._history: dict[str, list[dict[str, object]]] = {}

    def start(
        self,
        plan: OrchestrationPlan,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        entries = dict(snapshot.entries)
        results = dict(snapshot.orchestration_results)
        history = {
            workflow_address: list(events) for workflow_address, events in snapshot.orchestration_history.items()
        }
        changed_addresses: list[str] = []
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        for op in plan.operations:
            if op.action == ChangeAction.DELETE:
                entries.pop(op.address, None)
                results.pop(op.address, None)
                history.pop(op.address, None)
                changed_addresses.append(op.address)
                continue
            status = "queued" if op.resource_type in {"event", "script", "story", "workflow"} else "bound"
            entries[op.address] = SnapshotEntry(
                address=op.address,
                domain=RuntimeDomain.ORCHESTRATION,
                resource_type=op.resource_type,
                payload=op.payload,
                ordering_dependencies=op.ordering_dependencies,
                refresh_dependencies=op.refresh_dependencies,
                status=status,
            )
            if op.resource_type == "workflow":
                result_contract = op.payload.get("result_contract", {})
                observable_steps = result_contract.get("observable_steps", {})
                observable_steps = {
                    step_name: {
                        "lifecycle": "pending",
                        "outcome": None,
                        "attempts": 0,
                    }
                    for step_name, step_payload in observable_steps.items()
                    if isinstance(step_payload, dict)
                }
                results[op.address] = {
                    "state_schema_version": result_contract.get(
                        "state_schema_version",
                        op.payload.get("state_schema_version", "workflow-step-state/v1"),
                    ),
                    "workflow_status": "running",
                    "run_id": f"{op.address}-run",
                    "started_at": now,
                    "updated_at": now,
                    "terminal_reason": None,
                    "compensation_status": "not_required",
                    "compensation_started_at": None,
                    "compensation_updated_at": None,
                    "compensation_failures": [],
                    "steps": observable_steps,
                }
                history[op.address] = [
                    {
                        "event_type": "workflow_started",
                        "timestamp": now,
                        "step_name": op.payload.get("execution_contract", {}).get("start_step"),
                        "branch_name": None,
                        "join_step": None,
                        "outcome": None,
                        "details": {},
                    }
                ]
            if op.action != ChangeAction.UNCHANGED:
                changed_addresses.append(op.address)
        self._running = bool(plan.resources)
        self._startup_order = list(plan.startup_order)
        self._results = results
        self._history = history
        return ApplyResult(
            success=True,
            snapshot=snapshot.with_entries(
                entries,
                orchestration_results=results,
                orchestration_history=history,
            ),
            changed_addresses=changed_addresses,
        )

    def status(self) -> dict[str, object]:
        return {
            "running": self._running,
            "startup_order": list(self._startup_order),
            "results": len(self._results),
        }

    def results(self) -> dict[str, dict[str, object]]:
        return dict(self._results)

    def history(self) -> dict[str, list[dict[str, object]]]:
        return {workflow_address: list(events) for workflow_address, events in self._history.items()}

    def stop(self, snapshot: RuntimeSnapshot) -> ApplyResult:
        entries = {
            address: entry for address, entry in snapshot.entries.items() if entry.domain != RuntimeDomain.ORCHESTRATION
        }
        removed = [
            address for address, entry in snapshot.entries.items() if entry.domain == RuntimeDomain.ORCHESTRATION
        ]
        self._running = False
        self._startup_order = []
        self._results = {}
        self._history = {}
        return ApplyResult(
            success=True,
            snapshot=snapshot.with_entries(
                entries,
                orchestration_results={},
                orchestration_history={},
            ),
            changed_addresses=removed,
        )


class StubEvaluator:
    """In-memory evaluator."""

    def __init__(self) -> None:
        self._running = False
        self._startup_order: list[str] = []
        self._results: dict[str, dict[str, object]] = {}
        self._history: dict[str, list[dict[str, object]]] = {}

    def start(
        self,
        plan: EvaluationPlan,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        entries = dict(snapshot.entries)
        changed_addresses: list[str] = []
        results = dict(snapshot.evaluation_results)
        history = {address: list(events) for address, events in snapshot.evaluation_history.items()}
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        for op in plan.operations:
            if op.action == ChangeAction.DELETE:
                entries.pop(op.address, None)
                results.pop(op.address, None)
                history.pop(op.address, None)
                changed_addresses.append(op.address)
                continue
            entries[op.address] = SnapshotEntry(
                address=op.address,
                domain=RuntimeDomain.EVALUATION,
                resource_type=op.resource_type,
                payload=op.payload,
                ordering_dependencies=op.ordering_dependencies,
                refresh_dependencies=op.refresh_dependencies,
                status="evaluating",
            )
            result_contract = op.payload.get("result_contract", {})
            resource_type = str(result_contract.get("resource_type", op.resource_type))
            result_payload: dict[str, object] = {
                "state_schema_version": result_contract.get(
                    "state_schema_version",
                    EVALUATION_STATE_SCHEMA_VERSION,
                ),
                "resource_type": resource_type,
                "run_id": "evaluation-run",
                "status": "ready",
                "observed_at": now,
                "updated_at": now,
                "detail": f"stub result for {op.address}",
                "evidence_refs": [],
            }
            if result_contract.get("supports_score"):
                fixed_max_score = result_contract.get("fixed_max_score")
                result_payload["score"] = fixed_max_score if fixed_max_score is not None else 100
                result_payload["max_score"] = fixed_max_score if fixed_max_score is not None else 100
            if result_contract.get("supports_passed"):
                result_payload["passed"] = True
            results[op.address] = result_payload
            history[op.address] = [
                {
                    "event_type": "evaluation_started",
                    "timestamp": now,
                    "status": "running",
                    "passed": None,
                    "score": None,
                    "max_score": None,
                    "detail": None,
                    "evidence_refs": [],
                    "details": {},
                },
                {
                    "event_type": "evaluation_ready",
                    "timestamp": now,
                    "status": "ready",
                    "passed": result_payload.get("passed"),
                    "score": result_payload.get("score"),
                    "max_score": result_payload.get("max_score"),
                    "detail": result_payload.get("detail"),
                    "evidence_refs": list(result_payload.get("evidence_refs", [])),
                    "details": {},
                },
            ]
            if op.action != ChangeAction.UNCHANGED:
                changed_addresses.append(op.address)
        self._running = bool(plan.resources)
        self._startup_order = list(plan.startup_order)
        self._results = results
        self._history = history
        return ApplyResult(
            success=True,
            snapshot=snapshot.with_entries(
                entries,
                evaluation_results=results,
                evaluation_history=history,
            ),
            changed_addresses=changed_addresses,
        )

    def status(self) -> dict[str, object]:
        return {
            "running": self._running,
            "startup_order": list(self._startup_order),
            "results": len(self._results),
        }

    def results(self) -> dict[str, dict[str, object]]:
        return dict(self._results)

    def history(self) -> dict[str, list[dict[str, object]]]:
        return {address: list(events) for address, events in self._history.items()}

    def stop(self, snapshot: RuntimeSnapshot) -> ApplyResult:
        entries = {
            address: entry for address, entry in snapshot.entries.items() if entry.domain != RuntimeDomain.EVALUATION
        }
        removed = [address for address, entry in snapshot.entries.items() if entry.domain == RuntimeDomain.EVALUATION]
        self._running = False
        self._startup_order = []
        self._results = {}
        self._history = {}
        return ApplyResult(
            success=True,
            snapshot=snapshot.with_entries(
                entries,
                evaluation_results={},
                evaluation_history={},
            ),
            changed_addresses=removed,
        )


class StubParticipantRuntime:
    """In-memory participant runtime that drives RUN-311 transitions.

    Each control method allocates new history events and advances the
    current ``participant_episode_results`` entry in lockstep so the
    resulting snapshot always satisfies
    ``iter_participant_episode_snapshot_violations`` — identity is
    stable across resets/restarts, history is append-only, and the
    current result is the head of the history chain.
    """

    def __init__(self) -> None:
        self._results: dict[str, dict[str, object]] = {}
        self._history: dict[str, list[dict[str, object]]] = {}
        self._episode_counter: dict[str, int] = {}

    def initialize(
        self,
        request: ParticipantEpisodeInitializeRequest,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        address = request.participant_address
        if not address:
            return self._reject(snapshot, "participant_address must be non-empty", address)
        if address in snapshot.participant_episode_results:
            return self._reject(
                snapshot,
                f"participant {address!r} already has a live episode; use reset or restart",
                address,
            )
        now = _now_iso()
        episode_id = request.episode_id or self._allocate_episode_id(address)
        state = ParticipantEpisodeExecutionState(
            participant_address=address,
            episode_id=episode_id,
            sequence_number=0,
            status=ParticipantEpisodeStatus.RUNNING,
            initialized_at=now,
            updated_at=now,
            last_control_action=ParticipantEpisodeControlAction.INITIALIZE,
        )
        events = [
            ParticipantEpisodeHistoryEvent(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_INITIALIZED,
                timestamp=now,
                participant_address=address,
                episode_id=episode_id,
                sequence_number=0,
                control_action=ParticipantEpisodeControlAction.INITIALIZE,
            ),
            ParticipantEpisodeHistoryEvent(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RUNNING,
                timestamp=now,
                participant_address=address,
                episode_id=episode_id,
                sequence_number=0,
            ),
        ]
        return self._apply(snapshot, address, state, events, replace_history=True)

    def reset(
        self,
        request: ParticipantEpisodeResetRequest,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        address = request.participant_address
        if not address:
            return self._reject(snapshot, "participant_address must be non-empty", address)
        current = snapshot.participant_episode_results.get(address)
        if current is None:
            return self._reject(
                snapshot,
                f"cannot reset participant {address!r}: no live episode",
                address,
            )
        try:
            current_state = ParticipantEpisodeExecutionState.from_payload(current)
        except (TypeError, ValueError) as exc:
            return self._reject(snapshot, f"current state is invalid: {exc}", address)
        if current_state.status == ParticipantEpisodeStatus.TERMINATED:
            return self._reject(
                snapshot,
                f"cannot reset terminated participant {address!r}; use restart",
                address,
            )
        now = _now_iso()
        new_episode_id = request.episode_id or self._allocate_episode_id(address)
        new_sequence = current_state.sequence_number + 1
        new_state = ParticipantEpisodeExecutionState(
            participant_address=address,
            episode_id=new_episode_id,
            sequence_number=new_sequence,
            status=ParticipantEpisodeStatus.RUNNING,
            initialized_at=now,
            updated_at=now,
            last_control_action=ParticipantEpisodeControlAction.RESET,
            previous_episode_id=current_state.episode_id,
        )
        events = [
            ParticipantEpisodeHistoryEvent(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RESET,
                timestamp=now,
                participant_address=address,
                episode_id=new_episode_id,
                sequence_number=new_sequence,
                control_action=ParticipantEpisodeControlAction.RESET,
                details={
                    "previous_episode_id": current_state.episode_id,
                    "reason": request.reason,
                },
            ),
            ParticipantEpisodeHistoryEvent(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RUNNING,
                timestamp=now,
                participant_address=address,
                episode_id=new_episode_id,
                sequence_number=new_sequence,
            ),
        ]
        return self._apply(snapshot, address, new_state, events, replace_history=False)

    def restart(
        self,
        request: ParticipantEpisodeRestartRequest,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        address = request.participant_address
        if not address:
            return self._reject(snapshot, "participant_address must be non-empty", address)
        current = snapshot.participant_episode_results.get(address)
        if current is None:
            return self._reject(
                snapshot,
                f"cannot restart participant {address!r}: no live episode",
                address,
            )
        try:
            current_state = ParticipantEpisodeExecutionState.from_payload(current)
        except (TypeError, ValueError) as exc:
            return self._reject(snapshot, f"current state is invalid: {exc}", address)
        if current_state.status != ParticipantEpisodeStatus.TERMINATED:
            return self._reject(
                snapshot,
                f"cannot restart non-terminated participant {address!r}; use reset",
                address,
            )
        now = _now_iso()
        new_episode_id = request.episode_id or self._allocate_episode_id(address)
        new_sequence = current_state.sequence_number + 1
        new_state = ParticipantEpisodeExecutionState(
            participant_address=address,
            episode_id=new_episode_id,
            sequence_number=new_sequence,
            status=ParticipantEpisodeStatus.RUNNING,
            initialized_at=now,
            updated_at=now,
            last_control_action=ParticipantEpisodeControlAction.RESTART,
            previous_episode_id=current_state.episode_id,
        )
        events = [
            ParticipantEpisodeHistoryEvent(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RESTARTED,
                timestamp=now,
                participant_address=address,
                episode_id=new_episode_id,
                sequence_number=new_sequence,
                control_action=ParticipantEpisodeControlAction.RESTART,
                details={
                    "previous_episode_id": current_state.episode_id,
                    "reason": request.reason,
                },
            ),
            ParticipantEpisodeHistoryEvent(
                event_type=ParticipantEpisodeHistoryEventType.EPISODE_RUNNING,
                timestamp=now,
                participant_address=address,
                episode_id=new_episode_id,
                sequence_number=new_sequence,
            ),
        ]
        return self._apply(snapshot, address, new_state, events, replace_history=False)

    def terminate(
        self,
        request: ParticipantEpisodeTerminateRequest,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        address = request.participant_address
        if not address:
            return self._reject(snapshot, "participant_address must be non-empty", address)
        current = snapshot.participant_episode_results.get(address)
        if current is None:
            return self._reject(
                snapshot,
                f"cannot terminate participant {address!r}: no live episode",
                address,
            )
        try:
            current_state = ParticipantEpisodeExecutionState.from_payload(current)
        except (TypeError, ValueError) as exc:
            return self._reject(snapshot, f"current state is invalid: {exc}", address)
        if current_state.status == ParticipantEpisodeStatus.TERMINATED:
            return self._reject(
                snapshot,
                f"participant {address!r} is already terminated",
                address,
            )
        now = _now_iso()
        terminal_reason = request.terminal_reason
        terminal_event_type = _PARTICIPANT_TERMINAL_EVENT_FOR_REASON[terminal_reason]
        new_state = ParticipantEpisodeExecutionState(
            participant_address=address,
            episode_id=current_state.episode_id,
            sequence_number=current_state.sequence_number,
            status=ParticipantEpisodeStatus.TERMINATED,
            terminal_reason=terminal_reason,
            initialized_at=current_state.initialized_at,
            updated_at=now,
            terminated_at=now,
            last_control_action=current_state.last_control_action,
            previous_episode_id=current_state.previous_episode_id,
        )
        events = [
            ParticipantEpisodeHistoryEvent(
                event_type=terminal_event_type,
                timestamp=now,
                participant_address=address,
                episode_id=current_state.episode_id,
                sequence_number=current_state.sequence_number,
                terminal_reason=terminal_reason,
                details={"detail": request.detail},
            ),
        ]
        return self._apply(snapshot, address, new_state, events, replace_history=False)

    def status(self) -> dict[str, object]:
        return {
            "participants": len(self._results),
            "running": sum(1 for result in self._results.values() if result.get("status") == "running"),
        }

    def results(self) -> dict[str, dict[str, object]]:
        return {address: dict(result) for address, result in self._results.items()}

    def history(self) -> dict[str, list[dict[str, object]]]:
        return {address: list(events) for address, events in self._history.items()}

    def _apply(
        self,
        snapshot: RuntimeSnapshot,
        address: str,
        state: ParticipantEpisodeExecutionState,
        new_events: list[ParticipantEpisodeHistoryEvent],
        *,
        replace_history: bool,
    ) -> ApplyResult:
        results = {addr: dict(result) for addr, result in snapshot.participant_episode_results.items()}
        history = {addr: list(events) for addr, events in snapshot.participant_episode_history.items()}
        results[address] = state.to_payload()
        if replace_history:
            history[address] = [event.to_payload() for event in new_events]
        else:
            history.setdefault(address, [])
            history[address].extend(event.to_payload() for event in new_events)
        self._results = results
        self._history = history
        return ApplyResult(
            success=True,
            snapshot=snapshot.with_entries(
                dict(snapshot.entries),
                participant_episode_results=results,
                participant_episode_history=history,
            ),
            changed_addresses=[address],
        )

    def _reject(self, snapshot: RuntimeSnapshot, message: str, address: str) -> ApplyResult:
        diagnostic = Diagnostic(
            code="runtime.participant-runtime.rejected",
            domain="runtime",
            address=address or "runtime.participant-runtime",
            message=message,
        )
        return ApplyResult(success=False, snapshot=snapshot, diagnostics=[diagnostic])

    def _allocate_episode_id(self, address: str) -> str:
        next_index = self._episode_counter.get(address, 0) + 1
        self._episode_counter[address] = next_index
        return f"{address}-episode-{next_index}"


_PARTICIPANT_TERMINAL_EVENT_FOR_REASON: dict[
    ParticipantEpisodeTerminalReason,
    ParticipantEpisodeHistoryEventType,
] = {
    ParticipantEpisodeTerminalReason.COMPLETED: ParticipantEpisodeHistoryEventType.EPISODE_COMPLETED,
    ParticipantEpisodeTerminalReason.TIMED_OUT: ParticipantEpisodeHistoryEventType.EPISODE_TIMED_OUT,
    ParticipantEpisodeTerminalReason.TRUNCATED: ParticipantEpisodeHistoryEventType.EPISODE_TRUNCATED,
    ParticipantEpisodeTerminalReason.INTERRUPTED: ParticipantEpisodeHistoryEventType.EPISODE_INTERRUPTED,
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def create_stub_components(
    *,
    manifest: BackendManifest,
    **config,
) -> RuntimeTargetComponents:
    """Factory for stub runtime components."""

    del config
    return RuntimeTargetComponents(
        provisioner=StubProvisioner(),
        orchestrator=StubOrchestrator(),
        evaluator=StubEvaluator(),
        participant_runtime=StubParticipantRuntime() if manifest.has_participant_runtime else None,
    )


def create_stub_target(**config) -> RuntimeTarget:
    """Convenience helper returning the fully configured stub target."""

    manifest = create_stub_manifest(**config)
    components = create_stub_components(manifest=manifest, **config)
    return RuntimeTarget(
        name="stub",
        manifest=manifest,
        provisioner=components.provisioner,
        orchestrator=components.orchestrator,
        evaluator=components.evaluator,
        participant_runtime=components.participant_runtime,
    )
