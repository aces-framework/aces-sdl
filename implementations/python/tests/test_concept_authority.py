"""Concept authority catalog and cross-artifact binding tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aces_contracts.contracts import (
    BackendManifestV2Model,
    ConceptBindingEntryModel,
    ConceptFamilyCatalogModel,
    ConceptFamilyDefinitionModel,
    ProcessorManifestV2Model,
)
from aces_contracts.vocabulary import (
    ConceptProvenanceCategory,
)
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = REPO_ROOT / "contracts" / "concept-authority" / "concept-families-v1.json"
FIXTURES_ROOT = REPO_ROOT / "contracts" / "fixtures"
VALID_DIR = FIXTURES_ROOT / "concept-authority" / "concept-families-v1" / "valid"
INVALID_DIR = FIXTURES_ROOT / "concept-authority" / "concept-families-v1" / "invalid"


def _native_family_payload() -> dict[str, object]:
    return {
        "title": "Scenarios",
        "description": "SDL scenarios.",
        "provenance": "native",
        "extension_scope": "SDL-native scenario authoring constructs.",
        "relation_rules": ["Must remain the scenario authoring layer."],
        "non_ambiguity_constraints": ["Must not redefine adopted cyber-domain families."],
    }


def test_provenance_category_values():
    assert {c.value for c in ConceptProvenanceCategory} == {"adopted", "adapted", "native"}


def test_concept_family_definition_construction():
    family = ConceptFamilyDefinitionModel(
        title="Assets",
        description="Nodes and infrastructure.",
        provenance=ConceptProvenanceCategory.ADOPTED,
        authority="UCO",
        authority_reference="https://github.com/ucoProject/UCO",
    )
    assert family.provenance == ConceptProvenanceCategory.ADOPTED
    assert family.authority == "UCO"


def test_concept_family_definition_defaults():
    family = ConceptFamilyDefinitionModel(
        title="Scenarios",
        description="SDL scenarios.",
        provenance=ConceptProvenanceCategory.NATIVE,
        extension_scope="SDL-native scenario authoring constructs.",
        relation_rules=["Must remain the scenario authoring layer."],
        non_ambiguity_constraints=["Must not redefine adopted cyber-domain families."],
    )
    assert family.authority is None
    assert family.authority_reference is None
    assert family.extension_scope == "SDL-native scenario authoring constructs."
    assert family.relation_rules == ["Must remain the scenario authoring layer."]
    assert family.non_ambiguity_constraints == ["Must not redefine adopted cyber-domain families."]


def test_concept_family_definition_rejects_extra_fields():
    payload = _native_family_payload()
    payload["unknown_field"] = True
    with pytest.raises(ValidationError):
        ConceptFamilyDefinitionModel.model_validate(payload)


def test_adopted_family_requires_authority():
    with pytest.raises(ValidationError):
        ConceptFamilyDefinitionModel(
            title="Assets",
            description="Nodes.",
            provenance=ConceptProvenanceCategory.ADOPTED,
            authority_reference="https://github.com/ucoProject/UCO",
        )


def test_adopted_family_requires_authority_reference():
    with pytest.raises(ValidationError):
        ConceptFamilyDefinitionModel(
            title="Assets",
            description="Nodes.",
            provenance=ConceptProvenanceCategory.ADOPTED,
            authority="UCO",
        )


def test_adapted_family_requires_authority_metadata():
    with pytest.raises(ValidationError):
        ConceptFamilyDefinitionModel(
            title="Relationships",
            description="Typed associations.",
            provenance=ConceptProvenanceCategory.ADAPTED,
            authority="UCO",
        )


def test_native_family_rejects_authority_metadata():
    with pytest.raises(ValidationError):
        ConceptFamilyDefinitionModel(
            title="Scenarios",
            description="SDL scenarios.",
            provenance=ConceptProvenanceCategory.NATIVE,
            authority="ACES",
            authority_reference="https://aces-framework.org/concepts",
            extension_scope="SDL-native scenario authoring constructs.",
            relation_rules=["Must remain the scenario authoring layer."],
            non_ambiguity_constraints=["Must not redefine adopted cyber-domain families."],
        )


@pytest.mark.parametrize(
    ("missing_field", "expected_message"),
    [
        ("extension_scope", "extension_scope"),
        ("relation_rules", "relation_rules"),
        ("non_ambiguity_constraints", "non_ambiguity_constraints"),
    ],
)
def test_native_family_requires_extension_discipline_fields(missing_field: str, expected_message: str):
    payload = _native_family_payload()
    payload.pop(missing_field)
    with pytest.raises(ValidationError, match=expected_message):
        ConceptFamilyDefinitionModel.model_validate(payload)


@pytest.mark.parametrize(
    "invalid_update",
    [
        {"extension_scope": None},
        {"extension_scope": ""},
        {"relation_rules": None},
        {"relation_rules": []},
        {"relation_rules": [""]},
        {"non_ambiguity_constraints": None},
        {"non_ambiguity_constraints": []},
        {"non_ambiguity_constraints": [""]},
    ],
)
def test_native_family_rejects_empty_extension_discipline_fields(invalid_update: dict[str, object]):
    payload = _native_family_payload()
    payload.update(invalid_update)
    with pytest.raises(ValidationError):
        ConceptFamilyDefinitionModel.model_validate(payload)


def test_catalog_model_roundtrip():
    payload = {
        "schema_version": "concept-families/v1",
        "families": {
            "assets": {
                "title": "Assets",
                "description": "Nodes.",
                "provenance": "adopted",
                "authority": "UCO",
                "authority_reference": "https://github.com/ucoProject/UCO",
            },
            "scenarios": _native_family_payload(),
        },
    }
    model = ConceptFamilyCatalogModel.model_validate(payload)
    assert len(model.families) == 2
    assert model.families["assets"].provenance == ConceptProvenanceCategory.ADOPTED
    assert model.families["scenarios"].provenance == ConceptProvenanceCategory.NATIVE


def test_concept_family_definition_rejects_empty_title():
    payload = _native_family_payload()
    payload["title"] = ""
    with pytest.raises(ValidationError):
        ConceptFamilyDefinitionModel.model_validate(payload)


def test_catalog_model_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ConceptFamilyCatalogModel(
            schema_version="concept-families/v1",
            families=[],
            unknown_extra=True,
        )


def test_catalog_rejects_invalid_provenance():
    with pytest.raises(ValidationError):
        ConceptFamilyCatalogModel.model_validate(
            {
                "schema_version": "concept-families/v1",
                "families": {
                    "bad": {
                        "title": "Bad",
                        "description": "Bad provenance.",
                        "provenance": "invented",
                    }
                },
            }
        )


def test_catalog_rejects_empty_family_identifier():
    with pytest.raises(ValidationError):
        ConceptFamilyCatalogModel.model_validate(
            {
                "schema_version": "concept-families/v1",
                "families": {
                    "": _native_family_payload(),
                },
            }
        )


def test_catalog_rejects_empty_family_map():
    with pytest.raises(ValidationError):
        ConceptFamilyCatalogModel.model_validate(
            {
                "schema_version": "concept-families/v1",
                "families": {},
            }
        )


def test_authoritative_catalog_validates():
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    model = ConceptFamilyCatalogModel.model_validate(payload)
    assert len(model.families) >= 12


def test_authoritative_catalog_uses_keyed_family_map():
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    model = ConceptFamilyCatalogModel.model_validate(payload)
    assert set(payload["families"]) == set(model.families)
    assert "assets" in model.families


def test_authoritative_catalog_cyber_families_have_authority_metadata():
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    model = ConceptFamilyCatalogModel.model_validate(payload)
    for family_id, family in model.families.items():
        if family.provenance in {ConceptProvenanceCategory.ADOPTED, ConceptProvenanceCategory.ADAPTED}:
            assert family.authority is not None, f"Family '{family_id}' is {family.provenance} but has no authority"
            assert family.authority_reference is not None, (
                f"Family '{family_id}' is {family.provenance} but has no authority reference"
            )


def test_authoritative_catalog_native_families_have_no_authority_metadata():
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    model = ConceptFamilyCatalogModel.model_validate(payload)
    for family_id, family in model.families.items():
        if family.provenance == ConceptProvenanceCategory.NATIVE:
            assert family.authority is None, f"Native family '{family_id}' should not have an authority"
            assert family.authority_reference is None, f"Native family '{family_id}' should not have an authority ref"
            assert family.extension_scope is not None, f"Native family '{family_id}' should declare extension scope"
            assert family.relation_rules, f"Native family '{family_id}' should declare relation rules"
            assert family.non_ambiguity_constraints, (
                f"Native family '{family_id}' should declare non-ambiguity constraints"
            )


def test_valid_fixture_passes_validation():
    for path in sorted(VALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        model = ConceptFamilyCatalogModel.model_validate(payload)
        assert model.families, f"Valid fixture {path.name} should have families"


def test_invalid_fixture_fails_validation():
    for path in sorted(INVALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(ValidationError):
            ConceptFamilyCatalogModel.model_validate(payload)


# --- Cross-artifact concept binding tests ---

BACKEND_V2_VALID_DIR = FIXTURES_ROOT / "backend-manifest" / "backend-manifest-v2" / "valid"
PROCESSOR_V2_VALID_DIR = FIXTURES_ROOT / "processor-manifest" / "processor-manifest-v2" / "valid"


def test_concept_binding_entry_construction():
    entry = ConceptBindingEntryModel(scope="capabilities.provisioner.supported_node_types", family="assets")
    assert entry.scope == "capabilities.provisioner.supported_node_types"
    assert entry.family == "assets"


def test_concept_binding_entry_roundtrip():
    payload = {"scope": "capabilities.supported_features", "family": "apparatus-declarations"}
    entry = ConceptBindingEntryModel.model_validate(payload)
    assert entry.model_dump(mode="json") == payload


def test_concept_binding_entry_rejects_empty_scope():
    with pytest.raises(ValidationError):
        ConceptBindingEntryModel(scope="", family="assets")


def test_concept_binding_entry_rejects_invalid_family_pattern():
    with pytest.raises(ValidationError):
        ConceptBindingEntryModel(scope="capabilities.provisioner.supported_node_types", family="NOT VALID")


def test_concept_binding_entry_rejects_uppercase_family():
    with pytest.raises(ValidationError):
        ConceptBindingEntryModel(scope="capabilities.provisioner.supported_node_types", family="Assets")


def test_concept_binding_entry_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ConceptBindingEntryModel(
            scope="capabilities.provisioner.supported_node_types",
            family="assets",
            unknown_field=True,
        )


@pytest.mark.parametrize(
    ("fixture_path", "model_cls"),
    [
        (BACKEND_V2_VALID_DIR / "stub.json", BackendManifestV2Model),
        (PROCESSOR_V2_VALID_DIR / "reference.json", ProcessorManifestV2Model),
    ],
)
def test_manifest_bindings_reject_unknown_catalog_families(fixture_path: Path, model_cls: type) -> None:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["concept_bindings"][0]["family"] = "made-up-family"
    with pytest.raises(ValidationError, match="concept-families-v1"):
        model_cls.model_validate(payload)


@pytest.mark.parametrize(
    ("fixture_path", "model_cls", "invalid_scope"),
    [
        (
            BACKEND_V2_VALID_DIR / "stub.json",
            BackendManifestV2Model,
            "capabilities.provisioner.not_a_real_field",
        ),
        (
            PROCESSOR_V2_VALID_DIR / "reference.json",
            ProcessorManifestV2Model,
            "capabilities.not_a_real_field",
        ),
    ],
)
def test_manifest_bindings_reject_unknown_scopes(
    fixture_path: Path,
    model_cls: type,
    invalid_scope: str,
) -> None:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["concept_bindings"][0]["scope"] = invalid_scope
    with pytest.raises(ValidationError, match="governed manifest vocabulary surface"):
        model_cls.model_validate(payload)


def test_backend_manifest_bindings_reject_omitted_optional_surface() -> None:
    payload = json.loads((BACKEND_V2_VALID_DIR / "stub.json").read_text(encoding="utf-8"))
    payload["capabilities"]["evaluator"] = None
    with pytest.raises(ValidationError, match="does not resolve to a declared field"):
        BackendManifestV2Model.model_validate(payload)


def test_reference_fixture_bindings_resolve_to_authoritative_catalog():
    """Verify that all concept family IDs used in reference fixtures exist in the catalog."""
    catalog_payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog = ConceptFamilyCatalogModel.model_validate(catalog_payload)
    catalog_family_ids = set(catalog.families)

    for fixture_dir, model_cls in [
        (BACKEND_V2_VALID_DIR, BackendManifestV2Model),
        (PROCESSOR_V2_VALID_DIR, ProcessorManifestV2Model),
    ]:
        for path in sorted(fixture_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            model = model_cls.model_validate(payload)
            for binding in model.concept_bindings:
                assert binding.family in catalog_family_ids, (
                    f"Fixture {path.name} binds to unknown concept family '{binding.family}'"
                )
