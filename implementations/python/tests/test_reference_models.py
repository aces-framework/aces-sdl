"""Shared reference model catalog tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aces_contracts.contracts import ReferenceModelCatalogModel
from aces_contracts.reference_models import load_reference_model_catalog, reference_model_catalog_path
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = REPO_ROOT / "contracts" / "concept-authority" / "reference-models-v1.json"
FIXTURES_ROOT = REPO_ROOT / "contracts" / "fixtures" / "concept-authority" / "reference-models-v1"
VALID_DIR = FIXTURES_ROOT / "valid"
INVALID_DIR = FIXTURES_ROOT / "invalid"


def test_load_reference_model_catalog():
    catalog = load_reference_model_catalog()

    assert catalog.schema_version == "reference-models/v1"
    assert set(catalog.models) >= {
        "scenario-node",
        "scenario-account",
        "scenario-relationship",
        "scenario-condition",
        "scenario-event",
        "scenario-content",
    }


def test_reference_model_catalog_path_resolves():
    assert reference_model_catalog_path() == CATALOG_PATH


def test_reference_model_catalog_matches_valid_fixture():
    payload = json.loads((VALID_DIR / "reference.json").read_text(encoding="utf-8"))
    authoritative = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    assert payload == authoritative
    assert ReferenceModelCatalogModel.model_validate(payload).models["scenario-node"].concept_family == "assets"


def test_reference_model_valid_fixtures_pass_validation():
    for path in sorted(VALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        model = ReferenceModelCatalogModel.model_validate(payload)
        assert model.models, f"Valid reference model fixture {path.name} should declare models"


def test_reference_model_invalid_fixtures_fail_validation():
    for path in sorted(INVALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(ValidationError):
            ReferenceModelCatalogModel.model_validate(payload)


def test_reference_model_rejects_unknown_contract_ids():
    payload = json.loads((INVALID_DIR / "unknown-contract-id.json").read_text(encoding="utf-8"))

    with pytest.raises(ValidationError, match="unknown contract ids"):
        ReferenceModelCatalogModel.model_validate(payload)


def test_reference_model_rejects_schema_pointer_mismatches():
    payload = json.loads((INVALID_DIR / "schema-pointer-not-found.json").read_text(encoding="utf-8"))

    with pytest.raises(ValidationError, match="schema_pointer"):
        ReferenceModelCatalogModel.model_validate(payload)


def test_reference_model_rejects_instance_path_mismatches():
    payload = json.loads((INVALID_DIR / "instance-path-mismatch.json").read_text(encoding="utf-8"))

    with pytest.raises(ValidationError, match="instance_path"):
        ReferenceModelCatalogModel.model_validate(payload)


def test_reference_model_rejects_missing_key_fields():
    payload = json.loads((INVALID_DIR / "missing-key-field.json").read_text(encoding="utf-8"))

    with pytest.raises(ValidationError, match="key_fields"):
        ReferenceModelCatalogModel.model_validate(payload)
