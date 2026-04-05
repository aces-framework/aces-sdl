"""Concept authority catalog tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aces_processor.contracts import (
    ConceptFamilyCatalogModel,
    ConceptFamilyModel,
    ConceptProvenanceCategory,
)
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = REPO_ROOT / "contracts" / "concept-authority" / "concept-families-v1.json"
FIXTURES_ROOT = REPO_ROOT / "contracts" / "fixtures"
VALID_DIR = FIXTURES_ROOT / "concept-authority" / "concept-families-v1" / "valid"
INVALID_DIR = FIXTURES_ROOT / "concept-authority" / "concept-families-v1" / "invalid"


def test_provenance_category_values():
    assert {c.value for c in ConceptProvenanceCategory} == {"adopted", "adapted", "native"}


def test_concept_family_model_construction():
    family = ConceptFamilyModel(
        id="assets",
        title="Assets",
        description="Nodes and infrastructure.",
        provenance=ConceptProvenanceCategory.ADOPTED,
        authority="UCO",
        authority_reference="https://github.com/ucoProject/UCO",
    )
    assert family.id == "assets"
    assert family.provenance == ConceptProvenanceCategory.ADOPTED
    assert family.authority == "UCO"


def test_concept_family_model_defaults():
    family = ConceptFamilyModel(
        id="scenarios",
        title="Scenarios",
        description="SDL scenarios.",
        provenance=ConceptProvenanceCategory.NATIVE,
    )
    assert family.authority is None
    assert family.authority_reference is None


def test_concept_family_model_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ConceptFamilyModel(
            id="bad",
            title="Bad",
            description="Bad.",
            provenance="native",
            unknown_field=True,
        )


def test_catalog_model_roundtrip():
    payload = {
        "schema_version": "concept-families/v1",
        "families": [
            {
                "id": "assets",
                "title": "Assets",
                "description": "Nodes.",
                "provenance": "adopted",
                "authority": "UCO",
                "authority_reference": "https://github.com/ucoProject/UCO",
            },
            {
                "id": "scenarios",
                "title": "Scenarios",
                "description": "SDL scenarios.",
                "provenance": "native",
            },
        ],
    }
    model = ConceptFamilyCatalogModel.model_validate(payload)
    assert len(model.families) == 2
    assert model.families[0].provenance == ConceptProvenanceCategory.ADOPTED
    assert model.families[1].provenance == ConceptProvenanceCategory.NATIVE


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
                "families": [
                    {
                        "id": "bad",
                        "title": "Bad",
                        "description": "Bad provenance.",
                        "provenance": "invented",
                    }
                ],
            }
        )


def test_authoritative_catalog_validates():
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    model = ConceptFamilyCatalogModel.model_validate(payload)
    assert len(model.families) >= 12


def test_authoritative_catalog_families_have_unique_ids():
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    model = ConceptFamilyCatalogModel.model_validate(payload)
    ids = [f.id for f in model.families]
    assert len(ids) == len(set(ids)), f"Duplicate family IDs: {ids}"


def test_authoritative_catalog_cyber_families_have_authority():
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    model = ConceptFamilyCatalogModel.model_validate(payload)
    for family in model.families:
        if family.provenance in {ConceptProvenanceCategory.ADOPTED, ConceptProvenanceCategory.ADAPTED}:
            assert family.authority is not None, f"Family '{family.id}' is {family.provenance} but has no authority"


def test_authoritative_catalog_native_families_have_no_authority():
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    model = ConceptFamilyCatalogModel.model_validate(payload)
    for family in model.families:
        if family.provenance == ConceptProvenanceCategory.NATIVE:
            assert family.authority is None, f"Native family '{family.id}' should not have an authority"


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
