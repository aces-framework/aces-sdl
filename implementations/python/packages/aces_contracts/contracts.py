"""Schema-first external contract models for ACES artifact boundaries."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from aces_sdl.scenario import InstantiatedScenario, Scenario
from pydantic import BaseModel, ConfigDict, Field, GetJsonSchemaHandler, model_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from .versions import (
    BACKEND_MANIFEST_SCHEMA_VERSION,
    BACKEND_MANIFEST_V2_SCHEMA_VERSION,
    CONCEPT_FAMILIES_SCHEMA_VERSION,
    EVALUATION_STATE_SCHEMA_VERSION,
    OPERATION_SCHEMA_VERSION,
    PROCESSOR_MANIFEST_SCHEMA_VERSION,
    PROCESSOR_MANIFEST_V2_SCHEMA_VERSION,
    RUNTIME_SNAPSHOT_SCHEMA_VERSION,
    SCENARIO_INSTANTIATION_REQUEST_SCHEMA_VERSION,
    SEMANTIC_PROFILE_SCHEMA_VERSION,
    WORKFLOW_CANCELLATION_REQUEST_SCHEMA_VERSION,
    WORKFLOW_STATE_SCHEMA_VERSION,
)
from .vocabulary import (
    ConceptFamilyId,
    ConceptProvenanceCategory,
    ProcessorFeature,
    RealizationSupportMode,
    WorkflowFeature,
    WorkflowStatePredicateFeature,
)


class ContractModel(BaseModel):
    """Base model for closed-world external contracts."""

    model_config = ConfigDict(extra="forbid")


NonEmptyString = Annotated[str, Field(min_length=1)]
SemanticProfileId = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*-v[0-9]+$")]
SemanticAssumptionId = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]

_BACKEND_CONCEPT_BINDING_SCOPES = frozenset(
    {
        "capabilities.provisioner.supported_node_types",
        "capabilities.provisioner.supported_os_families",
        "capabilities.provisioner.supported_content_types",
        "capabilities.provisioner.supported_account_features",
        "capabilities.orchestrator.supported_sections",
        "capabilities.evaluator.supported_sections",
    }
)

_PROCESSOR_CONCEPT_BINDING_SCOPES = frozenset(
    {
        "capabilities.supported_sdl_versions",
        "capabilities.supported_features",
    }
)

_SEMANTIC_PROFILE_PHASE_ALLOWED_BINDING_SCOPES = {
    "authoring": frozenset(),
    "exchange": frozenset(),
    "processing": _PROCESSOR_CONCEPT_BINDING_SCOPES,
    "execution": _BACKEND_CONCEPT_BINDING_SCOPES,
}


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
    name: NonEmptyString
    supported_node_types: list[NonEmptyString] = Field(min_length=1)
    supported_os_families: list[NonEmptyString] = Field(min_length=1)
    supported_content_types: list[NonEmptyString] = Field(default_factory=list)
    supported_account_features: list[NonEmptyString] = Field(default_factory=list)
    max_total_nodes: int | None = Field(default=None, gt=0)
    supports_acls: bool = False
    supports_accounts: bool = False
    constraints: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_account_support(self) -> ProvisionerCapabilitiesModel:
        if self.supports_accounts and not self.supported_account_features:
            raise ValueError("provisioners that support accounts must declare supported_account_features")
        if not self.supports_accounts and self.supported_account_features:
            raise ValueError("supported_account_features require supports_accounts=true")
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
                        "properties": {"supports_accounts": {"const": True}},
                        "required": ["supports_accounts"],
                    },
                    "then": {
                        "required": ["supported_account_features"],
                        "properties": {"supported_account_features": {"minItems": 1}},
                    },
                },
                {
                    "if": {
                        "properties": {"supports_accounts": {"const": False}},
                        "required": ["supports_accounts"],
                    },
                    "then": {
                        "properties": {"supported_account_features": {"maxItems": 0}},
                    },
                },
            ]
        )
        return json_schema


class OrchestratorCapabilitiesModel(ContractModel):
    name: NonEmptyString
    supported_sections: list[NonEmptyString] = Field(min_length=1)
    supports_workflows: bool = False
    supports_condition_refs: bool = True
    supports_inject_bindings: bool = True
    supported_workflow_features: list[WorkflowFeature] = Field(default_factory=list)
    supported_workflow_state_predicates: list[WorkflowStatePredicateFeature] = Field(default_factory=list)
    constraints: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_workflow_support(self) -> OrchestratorCapabilitiesModel:
        if self.supports_workflows:
            if "workflows" not in self.supported_sections:
                raise ValueError("orchestrators that support workflows must include 'workflows' in supported_sections")
            if not self.supported_workflow_features:
                raise ValueError("orchestrators that support workflows must declare supported_workflow_features")
        else:
            if "workflows" in self.supported_sections:
                raise ValueError("'workflows' in supported_sections requires supports_workflows=true")
            if self.supported_workflow_features:
                raise ValueError("supported_workflow_features require supports_workflows=true")
            if self.supported_workflow_state_predicates:
                raise ValueError("supported_workflow_state_predicates require supports_workflows=true")
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
                        "properties": {"supports_workflows": {"const": True}},
                        "required": ["supports_workflows"],
                    },
                    "then": {
                        "required": ["supported_workflow_features", "supported_sections"],
                        "properties": {
                            "supported_workflow_features": {"minItems": 1},
                            "supported_sections": {"contains": {"const": "workflows"}},
                        },
                    },
                },
                {
                    "if": {
                        "properties": {"supports_workflows": {"const": False}},
                        "required": ["supports_workflows"],
                    },
                    "then": {
                        "properties": {
                            "supported_workflow_features": {"maxItems": 0},
                            "supported_workflow_state_predicates": {"maxItems": 0},
                            "supported_sections": {"not": {"contains": {"const": "workflows"}}},
                        },
                    },
                },
            ]
        )
        return json_schema


class EvaluatorCapabilitiesModel(ContractModel):
    name: NonEmptyString
    supported_sections: list[NonEmptyString] = Field(min_length=1)
    supports_scoring: bool = True
    supports_objectives: bool = True
    constraints: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_evaluator_support(self) -> EvaluatorCapabilitiesModel:
        if not self.supports_scoring and not self.supports_objectives:
            raise ValueError("evaluators must support scoring, objectives, or both")
        return self

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        json_schema.setdefault("allOf", []).append(
            {
                "not": {
                    "allOf": [
                        {
                            "properties": {"supports_scoring": {"const": False}},
                            "required": ["supports_scoring"],
                        },
                        {
                            "properties": {"supports_objectives": {"const": False}},
                            "required": ["supports_objectives"],
                        },
                    ]
                }
            }
        )
        return json_schema


class BackendManifestModel(ContractModel):
    schema_version: Literal[BACKEND_MANIFEST_SCHEMA_VERSION] = BACKEND_MANIFEST_SCHEMA_VERSION
    name: NonEmptyString
    provisioner: ProvisionerCapabilitiesModel
    orchestrator: OrchestratorCapabilitiesModel | None = None
    evaluator: EvaluatorCapabilitiesModel | None = None


class ProcessorManifestModel(ContractModel):
    schema_version: Literal[PROCESSOR_MANIFEST_SCHEMA_VERSION] = PROCESSOR_MANIFEST_SCHEMA_VERSION
    name: NonEmptyString
    version: NonEmptyString
    supported_sdl_versions: list[NonEmptyString] = Field(min_length=1)
    supported_contract_versions: list[NonEmptyString] = Field(min_length=1)
    supported_features: list[ProcessorFeature] = Field(min_length=1)
    compatible_backends: list[NonEmptyString] = Field(min_length=1)
    constraints: dict[str, str] = Field(default_factory=dict)


class ApparatusIdentityModel(ContractModel):
    name: NonEmptyString
    version: NonEmptyString


class ApparatusCompatibilityModel(ContractModel):
    processors: list[NonEmptyString] = Field(default_factory=list)
    backends: list[NonEmptyString] = Field(default_factory=list)
    participant_implementations: list[NonEmptyString] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_non_hollow_compatibility(self) -> ApparatusCompatibilityModel:
        if not (self.processors or self.backends or self.participant_implementations):
            raise ValueError(
                "compatibility must declare at least one processor, backend, or participant implementation"
            )
        return self

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        json_schema.setdefault("allOf", []).append(
            {
                "anyOf": [
                    {"required": ["processors"], "properties": {"processors": {"minItems": 1}}},
                    {"required": ["backends"], "properties": {"backends": {"minItems": 1}}},
                    {
                        "required": ["participant_implementations"],
                        "properties": {"participant_implementations": {"minItems": 1}},
                    },
                ]
            }
        )
        return json_schema


class RealizationSupportDeclarationModel(ContractModel):
    domain: NonEmptyString
    support_mode: RealizationSupportMode
    supported_constraint_kinds: list[NonEmptyString] = Field(default_factory=list)
    supported_exact_requirement_kinds: list[NonEmptyString] = Field(default_factory=list)
    disclosure_kinds: list[NonEmptyString] = Field(min_length=1)
    constraints: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_realization_support(self) -> RealizationSupportDeclarationModel:
        if not self.supported_constraint_kinds and not self.supported_exact_requirement_kinds:
            raise ValueError(
                "realization_support declarations must declare supported_constraint_kinds "
                "or supported_exact_requirement_kinds"
            )
        if self.support_mode == RealizationSupportMode.EXACT_ONLY and self.supported_constraint_kinds:
            raise ValueError("exact-only realization support must not declare supported_constraint_kinds")
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
                    "anyOf": [
                        {
                            "required": ["supported_constraint_kinds"],
                            "properties": {"supported_constraint_kinds": {"minItems": 1}},
                        },
                        {
                            "required": ["supported_exact_requirement_kinds"],
                            "properties": {"supported_exact_requirement_kinds": {"minItems": 1}},
                        },
                    ]
                },
                {
                    "if": {
                        "properties": {"support_mode": {"const": RealizationSupportMode.EXACT_ONLY.value}},
                        "required": ["support_mode"],
                    },
                    "then": {
                        "required": ["supported_exact_requirement_kinds"],
                        "properties": {
                            "supported_exact_requirement_kinds": {"minItems": 1},
                            "supported_constraint_kinds": {"maxItems": 0},
                        },
                    },
                },
            ]
        )
        return json_schema


class ConceptBindingEntryModel(ContractModel):
    """Binds a vocabulary surface in an artifact to a canonical concept family."""

    scope: NonEmptyString = Field(
        ...,
        pattern=r"^[a-z_][a-z0-9_.]*[a-z0-9_]$",
    )
    family: ConceptFamilyId


class ProcessorCapabilitiesV2Model(ContractModel):
    supported_sdl_versions: list[NonEmptyString] = Field(min_length=1)
    supported_features: list[ProcessorFeature] = Field(min_length=1)


class BackendCapabilitiesV2Model(ContractModel):
    provisioner: ProvisionerCapabilitiesModel
    orchestrator: OrchestratorCapabilitiesModel | None = None
    evaluator: EvaluatorCapabilitiesModel | None = None


class ProcessorManifestV2Model(ContractModel):
    schema_version: Literal[PROCESSOR_MANIFEST_V2_SCHEMA_VERSION] = PROCESSOR_MANIFEST_V2_SCHEMA_VERSION
    identity: ApparatusIdentityModel
    supported_contract_versions: list[NonEmptyString] = Field(min_length=1)
    compatibility: ApparatusCompatibilityModel
    realization_support: list[RealizationSupportDeclarationModel] = Field(min_length=1)
    concept_bindings: list[ConceptBindingEntryModel] = Field(min_length=1)
    constraints: dict[str, str] = Field(default_factory=dict)
    capabilities: ProcessorCapabilitiesV2Model

    @model_validator(mode="after")
    def _validate_unique_binding_scopes(self) -> ProcessorManifestV2Model:
        scopes = [binding.scope for binding in self.concept_bindings]
        if len(scopes) != len(set(scopes)):
            raise ValueError("concept_bindings must not contain duplicate scopes")
        _validate_canonical_concept_bindings(self, allowed_scopes=_PROCESSOR_CONCEPT_BINDING_SCOPES)
        return self


class BackendManifestV2Model(ContractModel):
    schema_version: Literal[BACKEND_MANIFEST_V2_SCHEMA_VERSION] = BACKEND_MANIFEST_V2_SCHEMA_VERSION
    identity: ApparatusIdentityModel
    supported_contract_versions: list[NonEmptyString] = Field(min_length=1)
    compatibility: ApparatusCompatibilityModel
    realization_support: list[RealizationSupportDeclarationModel] = Field(min_length=1)
    concept_bindings: list[ConceptBindingEntryModel] = Field(min_length=1)
    constraints: dict[str, str] = Field(default_factory=dict)
    capabilities: BackendCapabilitiesV2Model

    @model_validator(mode="after")
    def _validate_unique_binding_scopes(self) -> BackendManifestV2Model:
        scopes = [binding.scope for binding in self.concept_bindings]
        if len(scopes) != len(set(scopes)):
            raise ValueError("concept_bindings must not contain duplicate scopes")
        _validate_canonical_concept_bindings(self, allowed_scopes=_BACKEND_CONCEPT_BINDING_SCOPES)
        return self


class ConceptFamilyDefinitionModel(ContractModel):
    title: NonEmptyString
    description: NonEmptyString
    provenance: ConceptProvenanceCategory
    authority: str | None = Field(default=None, min_length=1)
    authority_reference: str | None = Field(default=None, min_length=1)
    extension_scope: str | None = Field(default=None, min_length=1)
    relation_rules: list[NonEmptyString] = Field(default_factory=list, min_length=1)
    non_ambiguity_constraints: list[NonEmptyString] = Field(default_factory=list, min_length=1)

    @model_validator(mode="after")
    def _validate_provenance_rules(self) -> ConceptFamilyDefinitionModel:
        if self.provenance in {ConceptProvenanceCategory.ADOPTED, ConceptProvenanceCategory.ADAPTED}:
            if self.authority is None or self.authority_reference is None:
                raise ValueError("adopted and adapted concept families require both authority and authority_reference")
        if self.provenance == ConceptProvenanceCategory.NATIVE and (
            self.authority is not None or self.authority_reference is not None
        ):
            raise ValueError("native concept families must not declare authority metadata")
        if self.provenance == ConceptProvenanceCategory.NATIVE:
            if self.extension_scope is None:
                raise ValueError("native concept families require extension_scope")
            if not self.relation_rules:
                raise ValueError("native concept families require relation_rules")
            if not self.non_ambiguity_constraints:
                raise ValueError("native concept families require non_ambiguity_constraints")
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
                    "then": {
                        "required": ["authority", "authority_reference"],
                        "properties": {
                            "authority": {"type": "string", "minLength": 1},
                            "authority_reference": {"type": "string", "minLength": 1},
                        },
                    },
                },
                {
                    "if": {
                        "properties": {"provenance": {"const": ConceptProvenanceCategory.ADAPTED.value}},
                        "required": ["provenance"],
                    },
                    "then": {
                        "required": ["authority", "authority_reference"],
                        "properties": {
                            "authority": {"type": "string", "minLength": 1},
                            "authority_reference": {"type": "string", "minLength": 1},
                        },
                    },
                },
                {
                    "if": {
                        "properties": {"provenance": {"const": ConceptProvenanceCategory.NATIVE.value}},
                        "required": ["provenance"],
                    },
                    "then": {
                        "required": ["extension_scope", "relation_rules", "non_ambiguity_constraints"],
                        "properties": {
                            "extension_scope": {"type": "string", "minLength": 1},
                            "relation_rules": {"type": "array", "minItems": 1},
                            "non_ambiguity_constraints": {"type": "array", "minItems": 1},
                        },
                        "not": {
                            "anyOf": [
                                {"required": ["authority"]},
                                {"required": ["authority_reference"]},
                            ]
                        },
                    },
                },
            ]
        )
        return json_schema


class ConceptFamilyCatalogModel(ContractModel):
    schema_version: Literal[CONCEPT_FAMILIES_SCHEMA_VERSION] = CONCEPT_FAMILIES_SCHEMA_VERSION
    families: dict[NonEmptyString, ConceptFamilyDefinitionModel] = Field(min_length=1)

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


class SemanticBehaviorAssumptionModel(ContractModel):
    id: SemanticAssumptionId
    statement: NonEmptyString


class SemanticProfilePhaseModel(ContractModel):
    required_contracts: list[NonEmptyString] = Field(min_length=1)
    required_concept_families: list[ConceptFamilyId] = Field(min_length=1)
    required_bindings: list[ConceptBindingEntryModel] = Field(default_factory=list)
    behavior_assumptions: list[SemanticBehaviorAssumptionModel] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_phase_assumptions(self) -> SemanticProfilePhaseModel:
        if len(self.required_contracts) != len(set(self.required_contracts)):
            raise ValueError("semantic profile required_contracts must not contain duplicates")
        if len(self.required_concept_families) != len(set(self.required_concept_families)):
            raise ValueError("semantic profile required_concept_families must not contain duplicates")

        known_contracts = _known_contract_ids()
        unknown_contracts = set(self.required_contracts) - known_contracts
        if unknown_contracts:
            unknown = ", ".join(sorted(unknown_contracts))
            raise ValueError(f"semantic profile required_contracts include unknown contract ids: {unknown}")

        known_families = _authoritative_concept_family_ids()
        unknown_families = set(self.required_concept_families) - known_families
        if unknown_families:
            unknown = ", ".join(sorted(unknown_families))
            raise ValueError(f"semantic profile required_concept_families include unknown families: {unknown}")

        binding_scopes = [binding.scope for binding in self.required_bindings]
        if len(binding_scopes) != len(set(binding_scopes)):
            raise ValueError("semantic profile required_bindings must not contain duplicate scopes")

        undeclared_binding_families = {
            binding.family for binding in self.required_bindings if binding.family not in self.required_concept_families
        }
        if undeclared_binding_families:
            missing = ", ".join(sorted(undeclared_binding_families))
            raise ValueError(
                f"semantic profile required_bindings must use families declared in required_concept_families: {missing}"
            )

        assumption_ids = [assumption.id for assumption in self.behavior_assumptions]
        if len(assumption_ids) != len(set(assumption_ids)):
            raise ValueError("semantic profile behavior_assumptions must not contain duplicate ids")
        return self


class SemanticProfileModel(ContractModel):
    schema_version: Literal[SEMANTIC_PROFILE_SCHEMA_VERSION] = SEMANTIC_PROFILE_SCHEMA_VERSION
    profile_id: SemanticProfileId
    title: NonEmptyString
    description: NonEmptyString
    concept_catalog_version: Literal[CONCEPT_FAMILIES_SCHEMA_VERSION]
    authoring: SemanticProfilePhaseModel
    exchange: SemanticProfilePhaseModel
    processing: SemanticProfilePhaseModel
    execution: SemanticProfilePhaseModel

    @model_validator(mode="after")
    def _validate_phase_binding_scopes(self) -> SemanticProfileModel:
        for phase_name, allowed_scopes in _SEMANTIC_PROFILE_PHASE_ALLOWED_BINDING_SCOPES.items():
            phase = getattr(self, phase_name)
            declared_scopes = {binding.scope for binding in phase.required_bindings}
            invalid_scopes = declared_scopes - allowed_scopes
            if invalid_scopes:
                invalid = ", ".join(sorted(invalid_scopes))
                if allowed_scopes:
                    allowed = ", ".join(sorted(allowed_scopes))
                    raise ValueError(
                        f"semantic profile {phase_name} required_bindings include scopes outside the governed "
                        f"{phase_name} surfaces: {invalid}; allowed scopes: {allowed}"
                    )
                raise ValueError(
                    f"semantic profile {phase_name} does not define governed required_bindings surfaces: {invalid}"
                )
        return self


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@lru_cache(maxsize=1)
def _authoritative_concept_family_ids() -> frozenset[str]:
    catalog_path = _repo_root() / "contracts" / "concept-authority" / "concept-families-v1.json"
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog = ConceptFamilyCatalogModel.model_validate(payload)
    return frozenset(catalog.families)


@lru_cache(maxsize=1)
def _known_contract_ids() -> frozenset[str]:
    return frozenset(schema_bundle())


def _scope_is_present(model: ContractModel, scope: str) -> bool:
    current: Any = model
    for segment in scope.split("."):
        if not isinstance(current, BaseModel):
            return False
        if segment not in type(current).model_fields:
            return False
        current = getattr(current, segment)
        if current is None:
            return False
    return True


def _validate_canonical_concept_bindings(model: ContractModel, *, allowed_scopes: frozenset[str]) -> None:
    family_ids = _authoritative_concept_family_ids()
    for binding in getattr(model, "concept_bindings", ()):
        if binding.family not in family_ids:
            raise ValueError(f"concept_bindings family '{binding.family}' is not defined in concept-families-v1")
        if binding.scope not in allowed_scopes:
            allowed = ", ".join(sorted(allowed_scopes))
            raise ValueError(
                f"concept_bindings scope '{binding.scope}' is not a governed manifest vocabulary surface; "
                f"allowed scopes: {allowed}"
            )
        if not _scope_is_present(model, binding.scope):
            raise ValueError(
                f"concept_bindings scope '{binding.scope}' does not resolve to a declared field in this manifest"
            )


def schema_bundle() -> dict[str, dict[str, Any]]:
    """Return the repo-published JSON Schemas for external contracts."""

    return {
        "sdl-authoring-input-v1": Scenario.model_json_schema(),
        "instantiated-scenario-v1": InstantiatedScenario.model_json_schema(),
        "scenario-instantiation-request-v1": InstantiationRequestModel.model_json_schema(),
        "backend-manifest-v1": BackendManifestModel.model_json_schema(),
        "backend-manifest-v2": BackendManifestV2Model.model_json_schema(),
        "processor-manifest-v1": ProcessorManifestModel.model_json_schema(),
        "processor-manifest-v2": ProcessorManifestV2Model.model_json_schema(),
        "concept-families-v1": ConceptFamilyCatalogModel.model_json_schema(),
        "semantic-profile-v1": SemanticProfileModel.model_json_schema(),
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
    "BACKEND_MANIFEST_V2_SCHEMA_VERSION",
    "ApparatusCompatibilityModel",
    "ApparatusIdentityModel",
    "BackendManifestModel",
    "BackendManifestV2Model",
    "BackendCapabilitiesV2Model",
    "CONCEPT_FAMILIES_SCHEMA_VERSION",
    "ConceptBindingEntryModel",
    "ConceptFamilyCatalogModel",
    "ConceptFamilyDefinitionModel",
    "ConceptFamilyId",
    "ConceptProvenanceCategory",
    "ContractModel",
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
    "PROCESSOR_MANIFEST_V2_SCHEMA_VERSION",
    "ProcessorManifestModel",
    "ProcessorManifestV2Model",
    "ProcessorCapabilitiesV2Model",
    "ProvisionerCapabilitiesModel",
    "ProvisioningPlanModel",
    "RealizationSupportDeclarationModel",
    "RealizationSupportMode",
    "RUNTIME_SNAPSHOT_SCHEMA_VERSION",
    "RuntimeSnapshotEnvelopeModel",
    "SCENARIO_INSTANTIATION_REQUEST_SCHEMA_VERSION",
    "SEMANTIC_PROFILE_SCHEMA_VERSION",
    "schema_bundle",
    "SemanticBehaviorAssumptionModel",
    "SemanticProfileModel",
    "SemanticProfilePhaseModel",
    "SnapshotEntryModel",
    "WorkflowCancellationRequestModel",
    "WORKFLOW_CANCELLATION_REQUEST_SCHEMA_VERSION",
    "WorkflowExecutionStateModel",
    "WorkflowFeature",
    "WorkflowHistoryEventModel",
    "WorkflowStatePredicateFeature",
    "WorkflowStepStateModel",
    "WORKFLOW_STATE_SCHEMA_VERSION",
]
