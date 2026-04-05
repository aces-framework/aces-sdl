"""Schema-first runtime contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import aces_processor.contracts as processor_contracts
from aces_contracts.contracts import (
    BackendManifestV2Model,
    ProcessorManifestModel,
    ProcessorManifestV2Model,
    schema_bundle,
)

from aces.core.runtime import contracts as compat_runtime_contracts


def test_published_contract_schemas_exist_and_match_bundle():
    repo_root = Path(__file__).resolve().parents[3]
    schemas_dir = repo_root / "contracts" / "schemas"
    published = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in schemas_dir.rglob("*.json")}

    generated = schema_bundle()

    assert set(generated) <= set(published)
    for name, schema in generated.items():
        assert published[name] == schema


def test_compat_contract_imports_reexport_neutral_contracts():
    assert processor_contracts.ProcessorManifestModel is ProcessorManifestModel
    assert processor_contracts.ProcessorManifestV2Model is ProcessorManifestV2Model
    assert processor_contracts.BackendManifestV2Model is BackendManifestV2Model
    assert compat_runtime_contracts.ProcessorManifestModel is ProcessorManifestModel
    assert compat_runtime_contracts.ProcessorManifestV2Model is ProcessorManifestV2Model
    assert compat_runtime_contracts.BackendManifestV2Model is BackendManifestV2Model
    assert processor_contracts.schema_bundle() == schema_bundle()
    assert compat_runtime_contracts.schema_bundle() == schema_bundle()


def test_closed_world_contract_models_for_runtime_envelopes():
    generated = schema_bundle()

    assert generated["workflow-result-envelope-v1"]["additionalProperties"] is False
    assert generated["evaluation-result-envelope-v1"]["additionalProperties"] is False
    assert generated["operation-receipt-v1"]["additionalProperties"] is False
    assert generated["operation-status-v1"]["additionalProperties"] is False
    assert generated["runtime-snapshot-v1"]["additionalProperties"] is False
    assert generated["backend-manifest-v1"]["additionalProperties"] is False
    assert generated["backend-manifest-v2"]["additionalProperties"] is False
    assert generated["processor-manifest-v1"]["additionalProperties"] is False
    assert generated["processor-manifest-v2"]["additionalProperties"] is False
    assert generated["concept-families-v1"]["additionalProperties"] is False


def test_manifest_schemas_publish_v1_and_v2_with_shared_and_enum_constrained_shapes():
    generated = schema_bundle()
    backend_v1_orchestrator = generated["backend-manifest-v1"]["$defs"]["OrchestratorCapabilitiesModel"]

    assert backend_v1_orchestrator["properties"]["supported_workflow_features"]["items"]["$ref"] == (
        "#/$defs/WorkflowFeature"
    )
    assert generated["backend-manifest-v1"]["$defs"]["WorkflowFeature"]["enum"] == [
        feature.value for feature in processor_contracts.WorkflowFeature
    ]
    assert backend_v1_orchestrator["properties"]["supported_workflow_state_predicates"]["items"]["$ref"] == (
        "#/$defs/WorkflowStatePredicateFeature"
    )
    assert generated["backend-manifest-v1"]["$defs"]["WorkflowStatePredicateFeature"]["enum"] == [
        feature.value for feature in processor_contracts.WorkflowStatePredicateFeature
    ]
    assert generated["backend-manifest-v2"]["properties"]["identity"]["$ref"] == "#/$defs/ApparatusIdentityModel"
    assert generated["backend-manifest-v2"]["properties"]["compatibility"]["$ref"] == (
        "#/$defs/ApparatusCompatibilityModel"
    )
    assert generated["backend-manifest-v2"]["properties"]["realization_support"]["items"]["$ref"] == (
        "#/$defs/RealizationSupportDeclarationModel"
    )
    assert generated["processor-manifest-v2"]["properties"]["identity"]["$ref"] == "#/$defs/ApparatusIdentityModel"
    assert generated["processor-manifest-v2"]["properties"]["compatibility"]["$ref"] == (
        "#/$defs/ApparatusCompatibilityModel"
    )
    assert generated["processor-manifest-v2"]["properties"]["realization_support"]["items"]["$ref"] == (
        "#/$defs/RealizationSupportDeclarationModel"
    )


def test_concept_authority_schema_enforces_keyed_catalog_and_provenance_rules():
    generated = schema_bundle()
    concept_catalog = generated["concept-families-v1"]
    family_definition = concept_catalog["$defs"]["ConceptFamilyDefinitionModel"]
    provenance_rules = {
        rule["if"]["properties"]["provenance"]["const"]: rule["then"] for rule in family_definition["allOf"]
    }

    assert concept_catalog["properties"]["families"]["type"] == "object"
    assert concept_catalog["properties"]["families"]["propertyNames"] == {"minLength": 1}
    assert (
        concept_catalog["properties"]["families"]["additionalProperties"]["$ref"]
        == "#/$defs/ConceptFamilyDefinitionModel"
    )
    assert provenance_rules["adopted"]["required"] == ["authority", "authority_reference"]
    assert provenance_rules["adapted"]["required"] == ["authority", "authority_reference"]
    assert provenance_rules["native"]["not"]["anyOf"] == [
        {"required": ["authority"]},
        {"required": ["authority_reference"]},
    ]
