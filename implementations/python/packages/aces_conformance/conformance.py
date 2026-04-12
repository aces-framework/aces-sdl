"""Backend conformance runner for schema-first runtime contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from textwrap import dedent
from typing import Any

from aces_backend_protocols.capabilities import BackendManifest
from aces_backend_protocols.manifest import backend_manifest_payload
from aces_contracts.contracts import (
    BackendManifestV2Model,
    EvaluationHistoryEventModel,
    EvaluationPlanModel,
    EvaluationResultStateModel,
    OperationReceiptModel,
    OperationStatusModel,
    OrchestrationPlanModel,
    ParticipantEpisodeHistoryEventModel,
    ParticipantEpisodeStateModel,
    ProvisioningPlanModel,
    RuntimeSnapshotEnvelopeModel,
    WorkflowExecutionStateModel,
    WorkflowHistoryEventModel,
    schema_bundle,
)
from aces_processor.compiler import compile_runtime_model
from aces_processor.control_plane import RuntimeControlPlane
from aces_processor.manager import (
    _evaluation_result_contract_diagnostics,
    _workflow_result_contract_diagnostics,
)
from aces_processor.models import (
    Diagnostic,
    EvaluationExecutionState,
    ParticipantEpisodeExecutionState,
    ParticipantEpisodeHistoryEvent,
    ParticipantEpisodeTerminalReason,
    RuntimeDomain,
    RuntimeSnapshot,
    RuntimeSnapshotEnvelope,
    Severity,
    SnapshotEntry,
    WorkflowExecutionState,
    iter_participant_episode_snapshot_violations,
)
from aces_processor.planner import plan
from aces_processor.registry import RuntimeTarget
from aces_sdl.parser import parse_sdl


class BackendCapabilityProfile(str, Enum):
    """Declared runtime surface level for backend conformance."""

    PROVISIONING_ONLY = "provisioning-only"
    ORCHESTRATION_CAPABLE = "orchestration-capable"
    ORCHESTRATION_EVALUATION = "orchestration-evaluation"
    FULL_REMOTE_CONTROL_PLANE = "full-remote-control-plane"


@dataclass(frozen=True)
class ConformanceCaseResult:
    """Result for one fixture or probe case."""

    name: str
    contract_name: str
    valid: bool
    passed: bool
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True)
class BackendConformanceReport:
    """Machine-friendly conformance result."""

    profile: BackendCapabilityProfile
    passed: bool
    cases: tuple[ConformanceCaseResult, ...] = ()
    contract_versions: dict[str, str] = field(default_factory=dict)
    unsupported_contract_gaps: tuple[str, ...] = ()
    unsupported_capability_gaps: tuple[str, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()


_PROFILE_REQUIREMENTS: dict[BackendCapabilityProfile, frozenset[str]] = {
    BackendCapabilityProfile.PROVISIONING_ONLY: frozenset(
        {
            "backend-manifest-v2",
            "operation-receipt-v1",
            "operation-status-v1",
            "runtime-snapshot-v1",
        }
    ),
    BackendCapabilityProfile.ORCHESTRATION_CAPABLE: frozenset(
        {
            "backend-manifest-v2",
            "operation-receipt-v1",
            "operation-status-v1",
            "runtime-snapshot-v1",
            "workflow-result-envelope-v1",
            "workflow-history-event-stream-v1",
        }
    ),
    BackendCapabilityProfile.ORCHESTRATION_EVALUATION: frozenset(
        {
            "backend-manifest-v2",
            "operation-receipt-v1",
            "operation-status-v1",
            "runtime-snapshot-v1",
            "workflow-result-envelope-v1",
            "workflow-history-event-stream-v1",
            "evaluation-result-envelope-v1",
            "evaluation-history-event-stream-v1",
        }
    ),
    BackendCapabilityProfile.FULL_REMOTE_CONTROL_PLANE: frozenset(
        {
            "backend-manifest-v2",
            "provisioning-plan-v1",
            "orchestration-plan-v1",
            "evaluation-plan-v1",
            "operation-receipt-v1",
            "operation-status-v1",
            "runtime-snapshot-v1",
            "workflow-result-envelope-v1",
            "workflow-history-event-stream-v1",
            "evaluation-result-envelope-v1",
            "evaluation-history-event-stream-v1",
            "participant-episode-state-envelope-v1",
            "participant-episode-history-event-stream-v1",
        }
    ),
}


_MODEL_VALIDATORS = {
    "backend-manifest-v2": BackendManifestV2Model.model_validate,
    "provisioning-plan-v1": ProvisioningPlanModel.model_validate,
    "orchestration-plan-v1": OrchestrationPlanModel.model_validate,
    "evaluation-plan-v1": EvaluationPlanModel.model_validate,
    "operation-receipt-v1": OperationReceiptModel.model_validate,
    "operation-status-v1": OperationStatusModel.model_validate,
    "runtime-snapshot-v1": RuntimeSnapshotEnvelopeModel.model_validate,
    "workflow-result-envelope-v1": WorkflowExecutionStateModel.model_validate,
    "evaluation-result-envelope-v1": EvaluationResultStateModel.model_validate,
    "participant-episode-state-envelope-v1": ParticipantEpisodeStateModel.model_validate,
}


_EVENT_STREAM_VALIDATORS: dict[str, tuple[type, str]] = {
    "workflow-history-event-stream-v1": (WorkflowHistoryEventModel, "workflow"),
    "evaluation-history-event-stream-v1": (EvaluationHistoryEventModel, "evaluation"),
    "participant-episode-history-event-stream-v1": (
        ParticipantEpisodeHistoryEventModel,
        "participant episode",
    ),
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def fixtures_root() -> Path:
    return _repo_root() / "contracts" / "fixtures"


def profiles_root() -> Path:
    return _repo_root() / "contracts" / "profiles"


def _fixture_contract_root(root: Path, contract_name: str) -> Path:
    matches = sorted(path for path in root.glob(f"**/{contract_name}") if path.is_dir())
    if matches:
        return matches[0]
    return root / contract_name


def required_contracts(
    profile: BackendCapabilityProfile,
) -> frozenset[str]:
    return _PROFILE_REQUIREMENTS[profile]


def _diagnostic(code: str, address: str, message: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        domain="conformance",
        address=address,
        message=message,
        severity=Severity.ERROR,
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_event_stream(
    *,
    contract_name: str,
    payload: Any,
    model_cls: type,
    event_label: str,
) -> list[Diagnostic]:
    """Validate a published history event stream against one Pydantic model.

    Shared by the workflow, evaluation, and participant-episode history
    event streams so adding a new stream type only requires extending
    ``_EVENT_STREAM_VALIDATORS``.
    """

    if not isinstance(payload, list):
        return [
            _diagnostic(
                "conformance.schema-invalid",
                contract_name,
                f"{event_label} history payload must be a list",
            )
        ]
    diagnostics: list[Diagnostic] = []
    for index, event in enumerate(payload):
        try:
            model_cls.model_validate(event)
        except Exception as exc:
            diagnostics.append(
                _diagnostic(
                    "conformance.schema-invalid",
                    f"{contract_name}[{index}]",
                    f"{event_label} history event is invalid: {exc}",
                )
            )
    return diagnostics


def _validate_payload(contract_name: str, payload: Any) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    validator = _MODEL_VALIDATORS.get(contract_name)
    if validator is not None:
        try:
            validator(payload)
        except Exception as exc:
            diagnostics.append(
                _diagnostic(
                    "conformance.schema-invalid",
                    contract_name,
                    f"{contract_name} failed contract validation: {exc}",
                )
            )
            return diagnostics
    elif contract_name in _EVENT_STREAM_VALIDATORS:
        diagnostics.extend(
            _validate_event_stream(
                contract_name=contract_name,
                payload=payload,
                model_cls=_EVENT_STREAM_VALIDATORS[contract_name][0],
                event_label=_EVENT_STREAM_VALIDATORS[contract_name][1],
            )
        )
    else:
        diagnostics.append(
            _diagnostic(
                "conformance.contract-unknown",
                contract_name,
                f"No conformance validator is registered for {contract_name}.",
            )
        )
    return diagnostics


def _snapshot_from_envelope(payload: dict[str, Any]) -> RuntimeSnapshot:
    validated = RuntimeSnapshotEnvelopeModel.model_validate(payload)
    entries = {
        address: SnapshotEntry(
            address=entry.address,
            domain=RuntimeDomain(entry.domain),
            resource_type=entry.resource_type,
            payload=dict(entry.payload),
            ordering_dependencies=tuple(entry.ordering_dependencies),
            refresh_dependencies=tuple(entry.refresh_dependencies),
            status=entry.status,
        )
        for address, entry in validated.entries.items()
    }
    return RuntimeSnapshot(
        entries=entries,
        orchestration_results={
            address: result.model_dump(mode="json") for address, result in validated.orchestration_results.items()
        },
        orchestration_history={
            address: [event.model_dump(mode="json") for event in history]
            for address, history in validated.orchestration_history.items()
        },
        evaluation_results={
            address: result.model_dump(mode="json") for address, result in validated.evaluation_results.items()
        },
        evaluation_history={
            address: [event.model_dump(mode="json") for event in history]
            for address, history in validated.evaluation_history.items()
        },
        participant_episode_results={
            participant_address: result.model_dump(mode="json")
            for participant_address, result in validated.participant_episode_results.items()
        },
        participant_episode_history={
            participant_address: [event.model_dump(mode="json") for event in history]
            for participant_address, history in validated.participant_episode_history.items()
        },
        metadata=dict(validated.metadata),
    )


def _participant_episode_snapshot_diagnostics(
    snapshot: RuntimeSnapshot,
) -> list[Diagnostic]:
    """Surface participant-episode snapshot invariants as conformance diagnostics.

    Delegates to ``iter_participant_episode_snapshot_violations`` so the
    conformance path and the manager apply path share one source of truth
    for every RUN-311 invariant, and wraps each violation in a
    ``conformance.semantic-invalid`` diagnostic.
    """

    return [
        _diagnostic("conformance.semantic-invalid", address, message)
        for address, message in iter_participant_episode_snapshot_violations(
            snapshot.participant_episode_results,
            snapshot.participant_episode_history,
        )
    ]


def _semantic_diagnostics(contract_name: str, payload: Any) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if contract_name == "workflow-result-envelope-v1":
        try:
            WorkflowExecutionState.from_payload(payload)
        except (TypeError, ValueError) as exc:
            diagnostics.append(
                _diagnostic(
                    "conformance.semantic-invalid",
                    contract_name,
                    f"workflow result semantics are invalid: {exc}",
                )
            )
        return diagnostics
    if contract_name == "evaluation-result-envelope-v1":
        try:
            EvaluationExecutionState.from_payload(payload)
        except (TypeError, ValueError) as exc:
            diagnostics.append(
                _diagnostic(
                    "conformance.semantic-invalid",
                    contract_name,
                    f"evaluation result semantics are invalid: {exc}",
                )
            )
        return diagnostics
    if contract_name == "participant-episode-state-envelope-v1":
        try:
            ParticipantEpisodeExecutionState.from_payload(payload)
        except (TypeError, ValueError) as exc:
            diagnostics.append(
                _diagnostic(
                    "conformance.semantic-invalid",
                    contract_name,
                    f"participant episode state semantics are invalid: {exc}",
                )
            )
        return diagnostics
    if contract_name == "participant-episode-history-event-stream-v1":
        if not isinstance(payload, list):
            return [
                _diagnostic(
                    "conformance.semantic-invalid",
                    contract_name,
                    "participant episode history payload must be a list",
                )
            ]
        for index, event in enumerate(payload):
            try:
                ParticipantEpisodeHistoryEvent.from_payload(event)
            except (TypeError, ValueError) as exc:
                diagnostics.append(
                    _diagnostic(
                        "conformance.semantic-invalid",
                        f"{contract_name}[{index}]",
                        f"participant episode history event semantics are invalid: {exc}",
                    )
                )
        return diagnostics
    if contract_name != "runtime-snapshot-v1":
        return []
    snapshot = _snapshot_from_envelope(payload)
    return [
        *_workflow_result_contract_diagnostics(snapshot),
        *_evaluation_result_contract_diagnostics(snapshot),
        *_participant_episode_snapshot_diagnostics(snapshot),
    ]


def run_fixture_suite(
    *,
    profile: BackendCapabilityProfile,
    root: Path | None = None,
) -> BackendConformanceReport:
    """Run the checked-in fixture corpus for a backend profile."""

    root = fixtures_root() if root is None else root
    bundle = schema_bundle()
    required = required_contracts(profile)
    cases: list[ConformanceCaseResult] = []
    diagnostics: list[Diagnostic] = []

    for contract_name in sorted(required):
        contract_root = _fixture_contract_root(root, contract_name)
        valid_dir = contract_root / "valid"
        invalid_dir = contract_root / "invalid"
        if not valid_dir.exists():
            diagnostics.append(
                _diagnostic(
                    "conformance.fixture-missing",
                    contract_name,
                    f"Missing valid fixture directory for {contract_name}.",
                )
            )
            continue

        for path in sorted(valid_dir.glob("*.json")):
            payload = _load_json(path)
            case_diagnostics = [
                *_validate_payload(contract_name, payload),
                *_semantic_diagnostics(contract_name, payload),
            ]
            cases.append(
                ConformanceCaseResult(
                    name=path.stem,
                    contract_name=contract_name,
                    valid=True,
                    passed=not case_diagnostics,
                    diagnostics=tuple(case_diagnostics),
                )
            )

        if invalid_dir.exists():
            for path in sorted(invalid_dir.glob("*.json")):
                payload = _load_json(path)
                case_diagnostics = [
                    *_validate_payload(contract_name, payload),
                    *_semantic_diagnostics(contract_name, payload),
                ]
                cases.append(
                    ConformanceCaseResult(
                        name=path.stem,
                        contract_name=contract_name,
                        valid=False,
                        passed=bool(case_diagnostics),
                        diagnostics=tuple(case_diagnostics),
                    )
                )

    return BackendConformanceReport(
        profile=profile,
        passed=not diagnostics and all(case.passed for case in cases),
        cases=tuple(cases),
        contract_versions={name: str(schema.get("title", name)) for name, schema in bundle.items() if name in required},
        diagnostics=tuple(diagnostics),
    )


def profile_for_manifest(manifest: BackendManifest) -> BackendCapabilityProfile:
    """Infer the nearest conformance profile for a backend manifest.

    A backend that declares orchestrator, evaluator, AND participant
    runtime capabilities is treated as ``FULL_REMOTE_CONTROL_PLANE``,
    so the default ``run_target_conformance`` path automatically
    validates the live target against the participant-episode contract
    family (RUN-311). Backends that only declare orchestrator/evaluator
    fall back to ``ORCHESTRATION_EVALUATION``; orchestrator-only
    declarations fall back to ``ORCHESTRATION_CAPABLE``; provisioner-only
    backends remain at ``PROVISIONING_ONLY``.
    """

    if manifest.has_orchestrator and manifest.has_evaluator and manifest.has_participant_runtime:
        return BackendCapabilityProfile.FULL_REMOTE_CONTROL_PLANE
    if manifest.has_orchestrator and manifest.has_evaluator:
        return BackendCapabilityProfile.ORCHESTRATION_EVALUATION
    if manifest.has_orchestrator:
        return BackendCapabilityProfile.ORCHESTRATION_CAPABLE
    return BackendCapabilityProfile.PROVISIONING_ONLY


def _capability_gaps(
    profile: BackendCapabilityProfile,
    target: RuntimeTarget,
) -> tuple[str, ...]:
    gaps: list[str] = []
    if (
        profile
        in {
            BackendCapabilityProfile.ORCHESTRATION_CAPABLE,
            BackendCapabilityProfile.ORCHESTRATION_EVALUATION,
            BackendCapabilityProfile.FULL_REMOTE_CONTROL_PLANE,
        }
        and target.orchestrator is None
    ):
        gaps.append("orchestrator")
    if (
        profile
        in {
            BackendCapabilityProfile.ORCHESTRATION_EVALUATION,
            BackendCapabilityProfile.FULL_REMOTE_CONTROL_PLANE,
        }
        and target.evaluator is None
    ):
        gaps.append("evaluator")
    if profile == BackendCapabilityProfile.FULL_REMOTE_CONTROL_PLANE and target.participant_runtime is None:
        gaps.append("participant_runtime")
    return tuple(gaps)


def _declared_contract_gaps(
    profile: BackendCapabilityProfile,
    manifest: BackendManifest,
) -> tuple[str, ...]:
    required = required_contracts(profile)
    return tuple(sorted(required - manifest.supported_contract_versions))


def run_target_conformance(
    target: RuntimeTarget,
    *,
    profile: BackendCapabilityProfile | None = None,
    root: Path | None = None,
) -> BackendConformanceReport:
    """Run fixture conformance for a target's declared runtime surface."""

    effective_profile = profile or profile_for_manifest(target.manifest)
    fixture_report = run_fixture_suite(profile=effective_profile, root=root)
    contract_gaps = _declared_contract_gaps(effective_profile, target.manifest)
    gaps = _capability_gaps(effective_profile, target)
    passed = fixture_report.passed and not contract_gaps and not gaps
    diagnostics = list(fixture_report.diagnostics)
    if contract_gaps:
        diagnostics.append(
            _diagnostic(
                "conformance.unsupported-contract-declaration",
                target.name,
                f"Target does not declare required contracts for {effective_profile.value}: {', '.join(contract_gaps)}",
            )
        )
    if gaps:
        diagnostics.append(
            _diagnostic(
                "conformance.unsupported-surface",
                target.name,
                "Target is missing required runtime surfaces: " + ", ".join(gaps),
            )
        )
    live_cases = _live_target_cases(target, effective_profile)
    cases = tuple((*fixture_report.cases, *live_cases))
    passed = passed and all(case.passed for case in live_cases)
    return BackendConformanceReport(
        profile=effective_profile,
        passed=passed,
        cases=cases,
        contract_versions=dict(fixture_report.contract_versions),
        unsupported_contract_gaps=contract_gaps,
        unsupported_capability_gaps=gaps,
        diagnostics=tuple(diagnostics),
    )


def _drive_participant_episode_probe(
    control_plane: RuntimeControlPlane,
    *,
    participant_address: str,
) -> list[ConformanceCaseResult]:
    """Drive a full RUN-311 participant lifecycle via the control plane.

    Each control action becomes one ``ConformanceCaseResult`` so that
    ``run_target_conformance`` reports a separate failure for any step
    the backend rejects, and a final case validates the resulting
    ``participant_episode_results`` / ``participant_episode_history``
    against the shared snapshot invariants.

    A target that registers a participant runtime but never populates
    the snapshot fields fails the snapshot-state-not-empty check, so
    the live conformance probe cannot certify a backend whose runtime
    accepts every action but produces no observable state.
    """

    cases: list[ConformanceCaseResult] = []
    actions = (
        ("participant-initialize", lambda: control_plane.initialize_participant_episode(participant_address)),
        ("participant-reset", lambda: control_plane.reset_participant_episode(participant_address)),
        (
            "participant-terminate",
            lambda: control_plane.terminate_participant_episode(
                participant_address,
                terminal_reason=ParticipantEpisodeTerminalReason.COMPLETED,
            ),
        ),
        ("participant-restart", lambda: control_plane.restart_participant_episode(participant_address)),
    )
    contract_name = "participant-episode-state-envelope-v1"
    for case_name, invoke in actions:
        try:
            receipt = invoke()
        except Exception as exc:  # pragma: no cover - defensive only
            cases.append(
                ConformanceCaseResult(
                    name=case_name,
                    contract_name=contract_name,
                    valid=True,
                    passed=False,
                    diagnostics=(
                        _diagnostic(
                            "conformance.participant-runtime-failed",
                            f"runtime.control-plane.participant.{participant_address}",
                            f"{case_name} raised {type(exc).__name__}: {exc}",
                        ),
                    ),
                )
            )
            continue
        status = control_plane.get_operation(receipt.operation_id)
        diagnostics: list[Diagnostic] = []
        if status is None:
            diagnostics.append(
                _diagnostic(
                    "conformance.participant-runtime-missing-status",
                    f"runtime.control-plane.participant.{participant_address}",
                    f"{case_name} did not produce an OperationStatus record",
                )
            )
        elif status.state.value not in {"succeeded"}:
            diagnostics.append(
                _diagnostic(
                    "conformance.participant-runtime-failed",
                    f"runtime.control-plane.participant.{participant_address}",
                    (
                        f"{case_name} returned state {status.state.value!r} with diagnostics: "
                        + "; ".join(diag.message for diag in status.diagnostics)
                    ),
                )
            )
        cases.append(
            ConformanceCaseResult(
                name=case_name,
                contract_name=contract_name,
                valid=True,
                passed=not diagnostics,
                diagnostics=tuple(diagnostics),
            )
        )

    snapshot = control_plane.snapshot
    final_diagnostics: list[Diagnostic] = []
    if not snapshot.participant_episode_results:
        final_diagnostics.append(
            _diagnostic(
                "conformance.participant-runtime-empty",
                f"runtime.snapshot.participant-episode-results.{participant_address}",
                (
                    "Participant runtime accepted every control action but the snapshot "
                    "exposes no participant_episode_results. RUN-311 backends must publish "
                    "live episode state through the snapshot."
                ),
            )
        )
    if not snapshot.participant_episode_history:
        final_diagnostics.append(
            _diagnostic(
                "conformance.participant-runtime-empty",
                f"runtime.snapshot.participant-episode-history.{participant_address}",
                (
                    "Participant runtime accepted every control action but the snapshot "
                    "exposes no participant_episode_history. RUN-311 backends must publish "
                    "live episode history events through the snapshot."
                ),
            )
        )
    for address, message in iter_participant_episode_snapshot_violations(
        snapshot.participant_episode_results,
        snapshot.participant_episode_history,
    ):
        final_diagnostics.append(_diagnostic("conformance.semantic-invalid", address, message))
    cases.append(
        ConformanceCaseResult(
            name="participant-snapshot-consistent",
            contract_name=contract_name,
            valid=True,
            passed=not final_diagnostics,
            diagnostics=tuple(final_diagnostics),
        )
    )
    return cases


def _live_target_cases(
    target: RuntimeTarget,
    profile: BackendCapabilityProfile,
) -> tuple[ConformanceCaseResult, ...]:
    cases: list[ConformanceCaseResult] = []
    manifest_payload = backend_manifest_payload(target.manifest)
    manifest_diags = _validate_payload("backend-manifest-v2", manifest_payload)
    cases.append(
        ConformanceCaseResult(
            name="live-manifest",
            contract_name="backend-manifest-v2",
            valid=True,
            passed=not manifest_diags,
            diagnostics=tuple(manifest_diags),
        )
    )

    if profile == BackendCapabilityProfile.PROVISIONING_ONLY:
        return tuple(cases)

    scenario = parse_sdl(
        dedent(
            """
            name: conformance
            nodes:
              vm:
                type: vm
                os: linux
                resources: {ram: 1 gib, cpu: 1}
                conditions: {health: ops}
                roles: {ops: operator}
            conditions:
              health: {command: /bin/true, interval: 15}
            entities:
              blue: {role: blue}
            objectives:
              validate:
                entity: blue
                success: {conditions: [health]}
            workflows:
              response:
                start: run
                steps:
                  run:
                    type: objective
                    objective: validate
                    on-success: finish
                  finish: {type: end}
            """
        )
    )
    execution_plan = plan(compile_runtime_model(scenario), target.manifest)
    control_plane = RuntimeControlPlane(target)
    control_plane.submit_provisioning(execution_plan.provisioning)
    if target.orchestrator is not None:
        control_plane.submit_orchestration(execution_plan.orchestration)
    if target.evaluator is not None:
        control_plane.submit_evaluation(execution_plan.evaluation)
    if target.participant_runtime is not None:
        cases.extend(
            _drive_participant_episode_probe(
                control_plane,
                participant_address="participant.conformance",
            )
        )
    snapshot_payload = {
        "schema_version": RuntimeSnapshotEnvelope().schema_version,
        "entries": {
            address: {
                "address": entry.address,
                "domain": entry.domain.value,
                "resource_type": entry.resource_type,
                "payload": dict(entry.payload),
                "ordering_dependencies": list(entry.ordering_dependencies),
                "refresh_dependencies": list(entry.refresh_dependencies),
                "status": entry.status,
            }
            for address, entry in control_plane.snapshot.entries.items()
        },
        "orchestration_results": dict(control_plane.snapshot.orchestration_results),
        "orchestration_history": dict(control_plane.snapshot.orchestration_history),
        "evaluation_results": dict(control_plane.snapshot.evaluation_results),
        "evaluation_history": dict(control_plane.snapshot.evaluation_history),
        "participant_episode_results": dict(control_plane.snapshot.participant_episode_results),
        "participant_episode_history": {
            participant_address: list(events)
            for participant_address, events in control_plane.snapshot.participant_episode_history.items()
        },
        "metadata": dict(control_plane.snapshot.metadata),
    }
    snapshot_diags = [
        *_validate_payload("runtime-snapshot-v1", snapshot_payload),
        *_semantic_diagnostics("runtime-snapshot-v1", snapshot_payload),
    ]
    cases.append(
        ConformanceCaseResult(
            name="live-snapshot",
            contract_name="runtime-snapshot-v1",
            valid=True,
            passed=not snapshot_diags,
            diagnostics=tuple(snapshot_diags),
        )
    )
    return tuple(cases)
