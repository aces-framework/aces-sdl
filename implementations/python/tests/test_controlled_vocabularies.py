"""Controlled vocabulary catalog tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aces_contracts.contracts import ControlledVocabularyCatalogModel
from aces_contracts.controlled_vocabularies import (
    controlled_vocabulary_catalog_path,
    load_controlled_vocabulary_catalog,
    validate_controlled_vocabulary_value,
)
from aces_contracts.vocabulary import (
    ConceptProvenanceCategory,
    ProcessorFeature,
    RealizationSupportMode,
    WorkflowFeature,
    WorkflowStatePredicateFeature,
)
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = REPO_ROOT / "contracts" / "concept-authority" / "controlled-vocabularies-v1.json"
FIXTURES_ROOT = REPO_ROOT / "contracts" / "fixtures" / "concept-authority" / "controlled-vocabularies-v1"
VALID_DIR = FIXTURES_ROOT / "valid"
INVALID_DIR = FIXTURES_ROOT / "invalid"


def test_load_controlled_vocabulary_catalog():
    catalog = load_controlled_vocabulary_catalog()

    assert catalog.schema_version == "controlled-vocabularies/v1"
    assert set(catalog.vocabularies) >= {
        "processor-features",
        "workflow-features",
        "workflow-state-predicate-features",
        "provisioner-node-types",
        "provisioner-os-families",
        "provisioner-content-types",
        "provisioner-account-features",
        "orchestrator-supported-sections",
        "evaluator-supported-sections",
        "realization-support-modes",
        "concept-provenance-categories",
    }


def test_controlled_vocabulary_catalog_path_resolves():
    assert controlled_vocabulary_catalog_path() == CATALOG_PATH


def test_controlled_vocabulary_catalog_matches_valid_fixture():
    payload = json.loads((VALID_DIR / "reference.json").read_text(encoding="utf-8"))
    authoritative = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    assert payload == authoritative
    assert ControlledVocabularyCatalogModel.model_validate(payload).vocabularies["processor-features"].terms


def test_controlled_vocabulary_valid_fixtures_pass_validation():
    for path in sorted(VALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        model = ControlledVocabularyCatalogModel.model_validate(payload)
        assert model.vocabularies, f"Valid vocabulary fixture {path.name} should declare vocabularies"


def test_controlled_vocabulary_invalid_fixtures_fail_validation():
    for path in sorted(INVALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(ValidationError):
            ControlledVocabularyCatalogModel.model_validate(payload)


def test_closed_enum_vocabularies_match_python_enums():
    catalog = load_controlled_vocabulary_catalog()

    assert set(catalog.vocabularies["processor-features"].terms) == {feature.value for feature in ProcessorFeature}
    assert set(catalog.vocabularies["workflow-features"].terms) == {feature.value for feature in WorkflowFeature}
    assert set(catalog.vocabularies["workflow-state-predicate-features"].terms) == {
        feature.value for feature in WorkflowStatePredicateFeature
    }
    assert set(catalog.vocabularies["realization-support-modes"].terms) == {
        mode.value for mode in RealizationSupportMode
    }
    assert set(catalog.vocabularies["concept-provenance-categories"].terms) == {
        category.value for category in ConceptProvenanceCategory
    }


def test_governed_extension_values_are_allowed_for_extensible_vocabularies():
    validate_controlled_vocabulary_value("provisioner-node-types", "x-acme:bare-metal")
    validate_controlled_vocabulary_value("orchestrator-supported-sections", "x-acme:custom-stage")


def test_unguarded_extension_values_are_rejected():
    with pytest.raises(ValueError, match="not a permitted term"):
        validate_controlled_vocabulary_value("provisioner-node-types", "bare-metal")


def test_extensions_are_rejected_for_closed_vocabularies():
    with pytest.raises(ValueError, match="does not allow extensions"):
        validate_controlled_vocabulary_value("realization-support-modes", "x-acme:custom-mode")
