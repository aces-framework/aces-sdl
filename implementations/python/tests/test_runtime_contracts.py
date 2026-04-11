"""Schema-first runtime contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from aces_contracts.contracts import (
    BackendManifestV2Model,
    ProcessorManifestModel,
    ProcessorManifestV2Model,
    schema_bundle,
)
from aces_contracts.manifest_authority import (
    PROCESSOR_SUPPORTED_CONTRACT_IDS,
    PROCESSOR_SUPPORTED_SDL_VERSION_IDS,
)
from aces_contracts.vocabulary import WorkflowFeature, WorkflowStatePredicateFeature

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
    assert compat_runtime_contracts.ProcessorManifestModel is ProcessorManifestModel
    assert compat_runtime_contracts.ProcessorManifestV2Model is ProcessorManifestV2Model
    assert compat_runtime_contracts.BackendManifestV2Model is BackendManifestV2Model
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
    assert generated["reference-models-v1"]["additionalProperties"] is False
    assert generated["controlled-vocabularies-v1"]["additionalProperties"] is False
    assert generated["semantic-profile-v1"]["additionalProperties"] is False


def test_manifest_schemas_publish_v1_and_v2_with_shared_and_enum_constrained_shapes():
    generated = schema_bundle()
    backend_v1_orchestrator = generated["backend-manifest-v1"]["$defs"]["OrchestratorCapabilitiesModel"]
    backend_v1_provisioner = generated["backend-manifest-v1"]["$defs"]["ProvisionerCapabilitiesModel"]
    backend_v2_compatibility = generated["backend-manifest-v2"]["$defs"]["ApparatusCompatibilityModel"]
    backend_v2_realization = generated["backend-manifest-v2"]["$defs"]["RealizationSupportDeclarationModel"]
    processor_v1 = generated["processor-manifest-v1"]
    processor_v2_compatibility = generated["processor-manifest-v2"]["$defs"]["ProcessorCompatibilityModel"]
    processor_v2_caps = generated["processor-manifest-v2"]["$defs"]["ProcessorCapabilitiesV2Model"]

    assert backend_v1_orchestrator["properties"]["supported_workflow_features"]["items"]["$ref"] == (
        "#/$defs/WorkflowFeature"
    )
    assert generated["backend-manifest-v1"]["$defs"]["WorkflowFeature"]["enum"] == [
        feature.value for feature in WorkflowFeature
    ]
    assert backend_v1_orchestrator["properties"]["supported_workflow_state_predicates"]["items"]["$ref"] == (
        "#/$defs/WorkflowStatePredicateFeature"
    )
    assert generated["backend-manifest-v1"]["$defs"]["WorkflowStatePredicateFeature"]["enum"] == [
        feature.value for feature in WorkflowStatePredicateFeature
    ]
    assert generated["backend-manifest-v2"]["properties"]["identity"]["$ref"] == "#/$defs/ApparatusIdentityModel"
    assert generated["backend-manifest-v2"]["properties"]["compatibility"]["$ref"] == (
        "#/$defs/ApparatusCompatibilityModel"
    )
    assert generated["backend-manifest-v2"]["properties"]["realization_support"]["items"]["$ref"] == (
        "#/$defs/RealizationSupportDeclarationModel"
    )
    assert generated["backend-manifest-v2"]["properties"]["supported_contract_versions"]["minItems"] == 1
    assert generated["backend-manifest-v2"]["properties"]["realization_support"]["minItems"] == 1
    assert backend_v2_compatibility["allOf"] == [
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
    ]
    assert backend_v2_realization["properties"]["disclosure_kinds"]["minItems"] == 1
    assert backend_v2_realization["allOf"] == [
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
                "properties": {"support_mode": {"const": "exact-only"}},
                "required": ["support_mode"],
            },
            "then": {
                "required": ["supported_exact_requirement_kinds"],
                "properties": {
                    "supported_constraint_kinds": {"maxItems": 0},
                    "supported_exact_requirement_kinds": {"minItems": 1},
                },
            },
        },
    ]
    assert backend_v1_provisioner["properties"]["supported_node_types"]["minItems"] == 1
    assert backend_v1_provisioner["properties"]["supported_os_families"]["minItems"] == 1
    assert generated["backend-manifest-v2"]["required"] == [
        "identity",
        "supported_contract_versions",
        "compatibility",
        "realization_support",
        "concept_bindings",
        "capabilities",
    ]
    assert generated["processor-manifest-v2"]["properties"]["identity"]["$ref"] == "#/$defs/ApparatusIdentityModel"
    assert (
        generated["processor-manifest-v2"]["properties"]["compatibility"]["$ref"]
        == "#/$defs/ProcessorCompatibilityModel"
    )
    assert generated["processor-manifest-v2"]["properties"]["supported_contract_versions"]["minItems"] == 1
    assert generated["processor-manifest-v2"]["properties"]["supported_contract_versions"]["items"]["enum"] == list(
        PROCESSOR_SUPPORTED_CONTRACT_IDS
    )
    assert "realization_support" not in generated["processor-manifest-v2"]["properties"]
    assert processor_v2_compatibility["properties"]["backends"]["minItems"] == 1
    assert processor_v2_compatibility["required"] == ["backends"]
    assert "processors" not in processor_v2_compatibility["properties"]
    assert "participant_implementations" not in processor_v2_compatibility["properties"]
    assert processor_v2_caps["properties"]["supported_sdl_versions"]["minItems"] == 1
    assert processor_v2_caps["properties"]["supported_sdl_versions"]["items"]["enum"] == list(
        PROCESSOR_SUPPORTED_SDL_VERSION_IDS
    )
    assert processor_v2_caps["properties"]["supported_features"]["minItems"] == 1
    assert processor_v2_caps["required"] == ["supported_sdl_versions", "supported_features"]
    assert generated["processor-manifest-v2"]["required"] == [
        "identity",
        "supported_contract_versions",
        "compatibility",
        "concept_bindings",
        "capabilities",
    ]
    assert processor_v1["properties"]["supported_sdl_versions"]["minItems"] == 1
    assert processor_v1["properties"]["supported_sdl_versions"]["items"]["enum"] == list(
        PROCESSOR_SUPPORTED_SDL_VERSION_IDS
    )
    assert processor_v1["properties"]["supported_contract_versions"]["minItems"] == 1
    assert processor_v1["properties"]["supported_contract_versions"]["items"]["enum"] == list(
        PROCESSOR_SUPPORTED_CONTRACT_IDS
    )
    assert processor_v1["properties"]["supported_features"]["minItems"] == 1
    assert processor_v1["properties"]["compatible_backends"]["minItems"] == 1


def test_concept_binding_schema_in_v2_manifests():
    generated = schema_bundle()

    for schema_name in ("backend-manifest-v2", "processor-manifest-v2"):
        schema = generated[schema_name]
        assert "concept_bindings" in schema["properties"], f"{schema_name} should have concept_bindings"
        assert "concept_bindings" in schema["required"], f"{schema_name} should require concept_bindings"
        bindings_prop = schema["properties"]["concept_bindings"]
        assert bindings_prop["type"] == "array"
        assert bindings_prop["minItems"] == 1
        assert "$ref" in bindings_prop["items"]
        assert "ConceptBindingEntryModel" in bindings_prop["items"]["$ref"]

    binding_def = generated["backend-manifest-v2"]["$defs"]["ConceptBindingEntryModel"]
    assert binding_def["additionalProperties"] is False
    assert "scope" in binding_def["properties"]
    assert "family" in binding_def["properties"]
    assert binding_def["properties"]["scope"]["pattern"]
    assert binding_def["properties"]["family"]["pattern"]


def test_concept_authority_schema_enforces_keyed_catalog_and_provenance_rules():
    generated = schema_bundle()
    concept_catalog = generated["concept-families-v1"]
    family_definition = concept_catalog["$defs"]["ConceptFamilyDefinitionModel"]
    provenance_rules = {
        rule["if"]["properties"]["provenance"]["const"]: rule["then"] for rule in family_definition["allOf"]
    }

    assert concept_catalog["properties"]["families"]["type"] == "object"
    assert concept_catalog["properties"]["families"]["minProperties"] == 1
    assert concept_catalog["properties"]["families"]["propertyNames"] == {"minLength": 1}
    assert (
        concept_catalog["properties"]["families"]["additionalProperties"]["$ref"]
        == "#/$defs/ConceptFamilyDefinitionModel"
    )
    assert family_definition["properties"]["title"]["minLength"] == 1
    assert family_definition["properties"]["description"]["minLength"] == 1
    assert provenance_rules["adopted"]["required"] == ["authority", "authority_reference"]
    assert provenance_rules["adopted"]["properties"]["authority"] == {"type": "string", "minLength": 1}
    assert provenance_rules["adopted"]["properties"]["authority_reference"] == {"type": "string", "minLength": 1}
    assert provenance_rules["adapted"]["required"] == ["authority", "authority_reference"]
    assert provenance_rules["adapted"]["properties"]["authority"] == {"type": "string", "minLength": 1}
    assert provenance_rules["adapted"]["properties"]["authority_reference"] == {"type": "string", "minLength": 1}
    assert provenance_rules["native"]["required"] == [
        "extension_scope",
        "relation_rules",
        "non_ambiguity_constraints",
    ]
    assert provenance_rules["native"]["properties"]["extension_scope"] == {"type": "string", "minLength": 1}
    assert provenance_rules["native"]["properties"]["relation_rules"] == {"type": "array", "minItems": 1}
    assert provenance_rules["native"]["properties"]["non_ambiguity_constraints"] == {
        "type": "array",
        "minItems": 1,
    }
    assert provenance_rules["native"]["not"]["anyOf"] == [
        {"required": ["authority"]},
        {"required": ["authority_reference"]},
    ]


def test_semantic_profile_schema_publishes_phase_assumptions():
    generated = schema_bundle()
    semantic_profile = generated["semantic-profile-v1"]
    phase_definition = semantic_profile["$defs"]["SemanticProfilePhaseModel"]
    assumption_definition = semantic_profile["$defs"]["SemanticBehaviorAssumptionModel"]

    assert semantic_profile["properties"]["profile_id"]["pattern"]
    assert semantic_profile["properties"]["concept_catalog_version"]["const"] == "concept-families/v1"
    assert semantic_profile["required"] == [
        "profile_id",
        "title",
        "description",
        "concept_catalog_version",
        "authoring",
        "exchange",
        "processing",
        "execution",
    ]
    assert phase_definition["properties"]["required_contracts"]["minItems"] == 1
    assert phase_definition["properties"]["required_concept_families"]["minItems"] == 1
    assert phase_definition["properties"]["required_bindings"]["type"] == "array"
    assert phase_definition["properties"]["behavior_assumptions"]["minItems"] == 1
    assert assumption_definition["properties"]["id"]["pattern"]
    assert assumption_definition["properties"]["statement"]["minLength"] == 1


def test_reference_model_schema_publishes_catalog():
    generated = schema_bundle()
    reference_models = generated["reference-models-v1"]
    model_definition = reference_models["$defs"]["ReferenceModelDefinitionModel"]
    schema_binding_definition = reference_models["$defs"]["ReferenceModelSchemaBindingModel"]

    assert reference_models["properties"]["models"]["type"] == "object"
    assert reference_models["properties"]["models"]["minProperties"] == 1
    assert reference_models["properties"]["models"]["propertyNames"] == {"minLength": 1}
    assert reference_models["properties"]["models"]["additionalProperties"]["$ref"] == (
        "#/$defs/ReferenceModelDefinitionModel"
    )
    assert reference_models["required"] == ["models"]
    assert model_definition["required"] == [
        "title",
        "description",
        "concept_family",
        "authoritative_schema",
        "key_fields",
    ]
    assert model_definition["properties"]["key_fields"]["minItems"] == 1
    assert schema_binding_definition["required"] == ["contract_id", "schema_pointer", "instance_path"]
    assert schema_binding_definition["properties"]["schema_pointer"]["pattern"]
    assert schema_binding_definition["properties"]["instance_path"]["pattern"]


def test_controlled_vocabulary_schema_publishes_catalog():
    generated = schema_bundle()
    controlled_vocabularies = generated["controlled-vocabularies-v1"]
    vocabulary_definition = controlled_vocabularies["$defs"]["ControlledVocabularyDefinitionModel"]
    term_definition = controlled_vocabularies["$defs"]["ControlledVocabularyTermModel"]

    assert controlled_vocabularies["properties"]["vocabularies"]["type"] == "object"
    assert controlled_vocabularies["properties"]["vocabularies"]["minProperties"] == 1
    assert controlled_vocabularies["properties"]["vocabularies"]["propertyNames"] == {"minLength": 1}
    assert controlled_vocabularies["properties"]["vocabularies"]["additionalProperties"]["$ref"] == (
        "#/$defs/ControlledVocabularyDefinitionModel"
    )
    assert controlled_vocabularies["required"] == ["vocabularies"]
    assert vocabulary_definition["required"] == [
        "title",
        "description",
        "kind",
        "extension_policy",
        "terms",
    ]
    assert vocabulary_definition["properties"]["governed_scopes"]["type"] == "array"
    assert vocabulary_definition["properties"]["terms"]["minProperties"] == 1
    assert term_definition["required"] == ["title", "description"]
