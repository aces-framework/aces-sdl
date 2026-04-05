"""Schema-first external contract models for ACES artifact boundaries."""

from __future__ import annotations

from typing import Any, Literal

from aces_sdl.scenario import InstantiatedScenario, Scenario
from pydantic import BaseModel, ConfigDict, Field, GetJsonSchemaHandler, model_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from .versions import (
    BACKEND_MANIFEST_SCHEMA_VERSION,
    CONCEPT_FAMILIES_SCHEMA_VERSION,
    EVALUATION_STATE_SCHEMA_VERSION,
    OPERATION_SCHEMA_VERSION,
    PROCESSOR_MANIFEST_SCHEMA_VERSION,
    RUNTIME_SNAPSHOT_SCHEMA_VERSION,
    SCENARIO_INSTANTIATION_REQUEST_SCHEMA_VERSION,
    WORKFLOW_CANCELLATION_REQUEST_SCHEMA_VERSION,
    WORKFLOW_STATE_SCHEMA_VERSION,
)
from .vocabulary import ConceptProvenanceCategory, ProcessorFeature


class ContractModel(BaseModel):
    """Base model for closed-world external contracts."""

    model_config = ConfigDict(extra="forbid")


class InstantiationRequestModel(ContractModel):
    schema_version: Literal[SCENARIO_INSTANTIATION_REQUEST_SCHEMA_VERSION] = (
        SCENARIO_INSTANTIATION_REQUEST_SCHEMA_VERSION
    )
    profile: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class WorkflowStepStateModel(ContractModel):
    lifecycle: str
    outcome: str | None = None
    attempts: int


class WorkflowExecutionStateModel(ContractModel):
    state_schema_version: Literal[WORKFLOW_STATE_SCHEMA_VERSION] = WORKFLOW_STATE_SCHEMA_VERSION
    workflow_status: str
    run_id: str
    started_at: str
    updated_at: str
    terminal_reason: str | None = None
    compensation_status: str
    compensation_started_at: str | None = None
    compensation_updated_at: str | None = None
    compensation_failures: list[dict[str, Any]] = Field(default_factory=list)
    steps: dict[str, WorkflowStepStateModel] = Field(default_factory=dict)


class WorkflowHistoryEventModel(ContractModel):
    event_type: str
    timestamp: str
    step_name: str | None = None
    branch_name: str | None = None
    join_step: str | None = None
    outcome: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class WorkflowCancellationRequestModel(ContractModel):
    schema_version: Literal[WORKFLOW_CANCELLATION_REQUEST_SCHEMA_VERSION] = WORKFLOW_CANCELLATION_REQUEST_SCHEMA_VERSION
    run_id: str | None = None
    reason: str = "cancelled by operator"


class EvaluationResultStateModel(ContractModel):
    state_schema_version: Literal[EVALUATION_STATE_SCHEMA_VERSION] = EVALUATION_STATE_SCHEMA_VERSION
    resource_type: str
    run_id: str
    status: str
    observed_at: str
    updated_at: str
    passed: bool | None = None
    score: float | int | None = None
    max_score: int | None = None
    detail: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class EvaluationHistoryEventModel(ContractModel):
    event_type: str
    timestamp: str
    status: str
    passed: bool | None = None
    score: float | int | None = None
    max_score: int | None = None
    detail: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class PlanOperationModel(ContractModel):
    action: str
    address: str
    resource_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    ordering_dependencies: list[str] = Field(default_factory=list)
    refresh_dependencies: list[str] = Field(default_factory=list)


class ProvisioningPlanModel(ContractModel):
    operations: list[PlanOperationModel] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class OrchestrationPlanModel(ContractModel):
    operations: list[PlanOperationModel] = Field(default_factory=list)
    startup_order: list[str] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class EvaluationPlanModel(ContractModel):
    operations: list[PlanOperationModel] = Field(default_factory=list)
    startup_order: list[str] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class SnapshotEntryModel(ContractModel):
    address: str
    domain: str
    resource_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    ordering_dependencies: list[str] = Field(default_factory=list)
    refresh_dependencies: list[str] = Field(default_factory=list)
    status: str = "ready"


class RuntimeSnapshotEnvelopeModel(ContractModel):
    schema_version: Literal[RUNTIME_SNAPSHOT_SCHEMA_VERSION] = RUNTIME_SNAPSHOT_SCHEMA_VERSION
    entries: dict[str, SnapshotEntryModel] = Field(default_factory=dict)
    orchestration_results: dict[str, WorkflowExecutionStateModel] = Field(default_factory=dict)
    orchestration_history: dict[str, list[WorkflowHistoryEventModel]] = Field(default_factory=dict)
    evaluation_results: dict[str, EvaluationResultStateModel] = Field(default_factory=dict)
    evaluation_history: dict[str, list[EvaluationHistoryEventModel]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OperationReceiptModel(ContractModel):
    schema_version: Literal[OPERATION_SCHEMA_VERSION] = OPERATION_SCHEMA_VERSION
    operation_id: str
    domain: str
    submitted_at: str
    accepted: bool
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class OperationStatusModel(ContractModel):
    schema_version: Literal[OPERATION_SCHEMA_VERSION] = OPERATION_SCHEMA_VERSION
    operation_id: str
    domain: str
    state: str
    submitted_at: str
    updated_at: str
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    changed_addresses: list[str] = Field(default_factory=list)


class ProvisionerCapabilitiesModel(ContractModel):
    name: str
    supported_node_types: list[str] = Field(default_factory=list)
    supported_os_families: list[str] = Field(default_factory=list)
    supported_content_types: list[str] = Field(default_factory=list)
    supported_account_features: list[str] = Field(default_factory=list)
    max_total_nodes: int | None = None
    supports_acls: bool = False
    supports_accounts: bool = False
    constraints: dict[str, str] = Field(default_factory=dict)


class OrchestratorCapabilitiesModel(ContractModel):
    name: str
    supported_sections: list[str] = Field(default_factory=list)
    supports_workflows: bool = False
    supports_condition_refs: bool = True
    supports_inject_bindings: bool = True
    supported_workflow_features: list[str] = Field(default_factory=list)
    supported_workflow_state_predicates: list[str] = Field(default_factory=list)
    constraints: dict[str, str] = Field(default_factory=dict)


class EvaluatorCapabilitiesModel(ContractModel):
    name: str
    supported_sections: list[str] = Field(default_factory=list)
    supports_scoring: bool = True
    supports_objectives: bool = True
    constraints: dict[str, str] = Field(default_factory=dict)


class BackendManifestModel(ContractModel):
    schema_version: Literal[BACKEND_MANIFEST_SCHEMA_VERSION] = BACKEND_MANIFEST_SCHEMA_VERSION
    name: str
    provisioner: ProvisionerCapabilitiesModel
    orchestrator: OrchestratorCapabilitiesModel | None = None
    evaluator: EvaluatorCapabilitiesModel | None = None


class ProcessorManifestModel(ContractModel):
    schema_version: Literal[PROCESSOR_MANIFEST_SCHEMA_VERSION] = PROCESSOR_MANIFEST_SCHEMA_VERSION
    name: str
    version: str
    supported_sdl_versions: list[str] = Field(default_factory=list)
    supported_contract_versions: list[str] = Field(default_factory=list)
    supported_features: list[ProcessorFeature] = Field(default_factory=list)
    compatible_backends: list[str] = Field(default_factory=list)
    constraints: dict[str, str] = Field(default_factory=dict)


class ConceptFamilyDefinitionModel(ContractModel):
    title: str
    description: str
    provenance: ConceptProvenanceCategory
    authority: str | None = Field(default=None, min_length=1)
    authority_reference: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_provenance_rules(self) -> ConceptFamilyDefinitionModel:
        if self.provenance in {ConceptProvenanceCategory.ADOPTED, ConceptProvenanceCategory.ADAPTED}:
            if self.authority is None or self.authority_reference is None:
                raise ValueError("adopted and adapted concept families require both authority and authority_reference")
        if self.provenance == ConceptProvenanceCategory.NATIVE and (
            self.authority is not None or self.authority_reference is not None
        ):
            raise ValueError("native concept families must not declare authority metadata")
        return self

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        json_schema.setdefault("allOf", []).extend(
            [
                {
                    "if": {
                        "properties": {"provenance": {"const": ConceptProvenanceCategory.ADOPTED.value}},
                        "required": ["provenance"],
                    },
                    "then": {"required": ["authority", "authority_reference"]},
                },
                {
                    "if": {
                        "properties": {"provenance": {"const": ConceptProvenanceCategory.ADAPTED.value}},
                        "required": ["provenance"],
                    },
                    "then": {"required": ["authority", "authority_reference"]},
                },
                {
                    "if": {
                        "properties": {"provenance": {"const": ConceptProvenanceCategory.NATIVE.value}},
                        "required": ["provenance"],
                    },
                    "then": {
                        "not": {
                            "anyOf": [
                                {"required": ["authority"]},
                                {"required": ["authority_reference"]},
                            ]
                        }
                    },
                },
            ]
        )
        return json_schema


class ConceptFamilyCatalogModel(ContractModel):
    schema_version: Literal[CONCEPT_FAMILIES_SCHEMA_VERSION] = CONCEPT_FAMILIES_SCHEMA_VERSION
    families: dict[str, ConceptFamilyDefinitionModel] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_family_keys(self) -> ConceptFamilyCatalogModel:
        if any(not family_id.strip() for family_id in self.families):
            raise ValueError("concept family identifiers must be non-empty")
        return self

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        families_schema = json_schema.get("properties", {}).get("families")
        if isinstance(families_schema, dict):
            families_schema.setdefault("propertyNames", {"minLength": 1})
        return json_schema


def schema_bundle() -> dict[str, dict[str, Any]]:
    """Return the repo-published JSON Schemas for external contracts."""

    return {
        "sdl-authoring-input-v1": Scenario.model_json_schema(),
        "instantiated-scenario-v1": InstantiatedScenario.model_json_schema(),
        "scenario-instantiation-request-v1": InstantiationRequestModel.model_json_schema(),
        "backend-manifest-v1": BackendManifestModel.model_json_schema(),
        "processor-manifest-v1": ProcessorManifestModel.model_json_schema(),
        "concept-families-v1": ConceptFamilyCatalogModel.model_json_schema(),
        "provisioning-plan-v1": ProvisioningPlanModel.model_json_schema(),
        "orchestration-plan-v1": OrchestrationPlanModel.model_json_schema(),
        "evaluation-plan-v1": EvaluationPlanModel.model_json_schema(),
        "runtime-snapshot-v1": RuntimeSnapshotEnvelopeModel.model_json_schema(),
        "workflow-result-envelope-v1": WorkflowExecutionStateModel.model_json_schema(),
        "workflow-history-event-stream-v1": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "WorkflowHistoryEventStream",
            "type": "array",
            "items": WorkflowHistoryEventModel.model_json_schema(),
        },
        "workflow-cancellation-request-v1": WorkflowCancellationRequestModel.model_json_schema(),
        "evaluation-result-envelope-v1": EvaluationResultStateModel.model_json_schema(),
        "evaluation-history-event-stream-v1": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "EvaluationHistoryEventStream",
            "type": "array",
            "items": EvaluationHistoryEventModel.model_json_schema(),
        },
        "operation-receipt-v1": OperationReceiptModel.model_json_schema(),
        "operation-status-v1": OperationStatusModel.model_json_schema(),
    }


__all__ = [
    "BACKEND_MANIFEST_SCHEMA_VERSION",
    "BackendManifestModel",
    "CONCEPT_FAMILIES_SCHEMA_VERSION",
    "ContractModel",
    "ConceptFamilyCatalogModel",
    "ConceptFamilyDefinitionModel",
    "ConceptProvenanceCategory",
    "EvaluationHistoryEventModel",
    "EvaluationPlanModel",
    "EvaluationResultStateModel",
    "EVALUATION_STATE_SCHEMA_VERSION",
    "EvaluatorCapabilitiesModel",
    "InstantiationRequestModel",
    "OPERATION_SCHEMA_VERSION",
    "OperationReceiptModel",
    "OperationStatusModel",
    "OrchestrationPlanModel",
    "OrchestratorCapabilitiesModel",
    "PlanOperationModel",
    "ProcessorFeature",
    "PROCESSOR_MANIFEST_SCHEMA_VERSION",
    "ProcessorManifestModel",
    "ProvisionerCapabilitiesModel",
    "ProvisioningPlanModel",
    "RUNTIME_SNAPSHOT_SCHEMA_VERSION",
    "RuntimeSnapshotEnvelopeModel",
    "SCENARIO_INSTANTIATION_REQUEST_SCHEMA_VERSION",
    "schema_bundle",
    "SnapshotEntryModel",
    "WorkflowCancellationRequestModel",
    "WORKFLOW_CANCELLATION_REQUEST_SCHEMA_VERSION",
    "WorkflowExecutionStateModel",
    "WorkflowHistoryEventModel",
    "WorkflowStepStateModel",
    "WORKFLOW_STATE_SCHEMA_VERSION",
]
