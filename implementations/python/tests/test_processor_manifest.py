"""Processor manifest declaration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aces_cli.main import app
from aces_contracts.contracts import ProcessorManifestModel
from aces_contracts.vocabulary import ProcessorFeature
from aces_processor.capabilities import ProcessorManifest
from aces_processor.manifest import (
    create_reference_processor_manifest,
    reference_processor_manifest_payload,
)
from pydantic import ValidationError
from typer.testing import CliRunner

FIXTURES_ROOT = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"
VALID_DIR = FIXTURES_ROOT / "processor-manifest" / "processor-manifest-v1" / "valid"
INVALID_DIR = FIXTURES_ROOT / "processor-manifest" / "processor-manifest-v1" / "invalid"
EXPECTED_SUPPORTED_CONTRACT_VERSIONS = [
    "processor-manifest-v1",
    "provisioning-plan-v1",
    "orchestration-plan-v1",
    "evaluation-plan-v1",
    "workflow-cancellation-request-v1",
    "operation-receipt-v1",
    "operation-status-v1",
    "runtime-snapshot-v1",
]


def test_processor_feature_enum_values():
    expected = {
        "compilation",
        "planning",
        "orchestration-coordination",
        "evaluation-coordination",
        "workflow-semantics",
        "objective-window-consistency",
        "dependency-ordering",
        "runtime-control-plane",
    }
    assert {f.value for f in ProcessorFeature} == expected


def test_processor_manifest_construction():
    manifest = ProcessorManifest(name="test", version="1.0.0")
    assert manifest.name == "test"
    assert manifest.version == "1.0.0"
    assert manifest.supported_sdl_versions == frozenset()
    assert manifest.supported_contract_versions == frozenset()
    assert manifest.supported_features == frozenset()
    assert manifest.compatible_backends == frozenset()
    assert manifest.constraints == {}


def test_processor_manifest_frozen():
    manifest = ProcessorManifest(name="test", version="1.0.0")
    with pytest.raises(AttributeError):
        manifest.name = "changed"


def test_processor_manifest_with_features():
    manifest = ProcessorManifest(
        name="aces-reference",
        version="0.1.0",
        supported_sdl_versions=frozenset({"sdl-authoring-input-v1"}),
        supported_features=frozenset({ProcessorFeature.COMPILATION, ProcessorFeature.PLANNING}),
    )
    assert ProcessorFeature.COMPILATION in manifest.supported_features
    assert ProcessorFeature.PLANNING in manifest.supported_features
    assert len(manifest.supported_features) == 2


def test_processor_manifest_model_roundtrip():
    payload = {
        "schema_version": "processor-manifest/v1",
        "name": "test-processor",
        "version": "0.1.0",
        "supported_sdl_versions": ["sdl-authoring-input-v1"],
        "supported_contract_versions": ["backend-manifest-v1"],
        "supported_features": ["compilation", "planning"],
        "compatible_backends": ["stub"],
        "constraints": {"max_nodes": "64"},
    }
    model = ProcessorManifestModel.model_validate(payload)
    assert model.name == "test-processor"
    assert model.version == "0.1.0"
    assert model.supported_features == [
        ProcessorFeature.COMPILATION,
        ProcessorFeature.PLANNING,
    ]
    dumped = model.model_dump(mode="json")
    assert dumped == payload


def test_processor_manifest_model_defaults():
    model = ProcessorManifestModel(name="minimal", version="0.0.1")
    assert model.schema_version == "processor-manifest/v1"
    assert model.supported_sdl_versions == []
    assert model.supported_contract_versions == []
    assert model.supported_features == []
    assert model.compatible_backends == []
    assert model.constraints == {}


def test_processor_manifest_model_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ProcessorManifestModel(
            name="bad",
            version="0.0.1",
            unknown_extra_field=True,
        )


def test_processor_manifest_model_rejects_unknown_feature():
    with pytest.raises(ValidationError):
        ProcessorManifestModel(
            name="bad",
            version="0.0.1",
            supported_features=["definitely-not-a-real-feature"],
        )


def test_reference_processor_manifest_matches_contract_payload():
    manifest = create_reference_processor_manifest(version="0.2.0")
    payload = reference_processor_manifest_payload(version="0.2.0")

    assert manifest.name == payload["name"]
    assert manifest.version == payload["version"]
    assert set(manifest.supported_contract_versions) == set(EXPECTED_SUPPORTED_CONTRACT_VERSIONS)
    assert payload["supported_sdl_versions"] == ["sdl-authoring-input-v1"]
    assert payload["supported_contract_versions"] == EXPECTED_SUPPORTED_CONTRACT_VERSIONS
    assert payload["compatible_backends"] == ["stub"]
    assert payload["supported_features"] == [feature.value for feature in ProcessorFeature]
    assert "backend-manifest-v1" not in payload["supported_contract_versions"]
    assert "concept-families-v1" not in payload["supported_contract_versions"]
    assert "instantiated-scenario-v1" not in payload["supported_contract_versions"]
    assert "scenario-instantiation-request-v1" not in payload["supported_contract_versions"]


def test_reference_processor_fixture_matches_reference_manifest():
    payload = json.loads((VALID_DIR / "reference.json").read_text(encoding="utf-8"))
    assert payload == reference_processor_manifest_payload(version=payload["version"])


def test_valid_fixture_passes_validation():
    for path in sorted(VALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        model = ProcessorManifestModel.model_validate(payload)
        assert model.name, f"Valid fixture {path.name} should have a name"


def test_invalid_fixture_fails_validation():
    for path in sorted(INVALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(ValidationError):
            ProcessorManifestModel.model_validate(payload)


def test_processor_manifest_cli_emits_reference_manifest():
    runner = CliRunner()
    result = runner.invoke(app, ["processor", "manifest"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == reference_processor_manifest_payload(version=payload["version"])
