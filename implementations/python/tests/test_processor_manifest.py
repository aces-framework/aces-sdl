"""Processor manifest declaration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aces_processor.capabilities import ProcessorFeature, ProcessorManifest
from aces_processor.contracts import ProcessorManifestModel


FIXTURES_ROOT = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"
VALID_DIR = FIXTURES_ROOT / "processor-manifest" / "processor-manifest-v1" / "valid"
INVALID_DIR = FIXTURES_ROOT / "processor-manifest" / "processor-manifest-v1" / "invalid"


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
        supported_sdl_versions=frozenset({"sdl-authoring-input/v1"}),
        supported_features=frozenset(
            {ProcessorFeature.COMPILATION, ProcessorFeature.PLANNING}
        ),
    )
    assert ProcessorFeature.COMPILATION in manifest.supported_features
    assert ProcessorFeature.PLANNING in manifest.supported_features
    assert len(manifest.supported_features) == 2


def test_processor_manifest_model_roundtrip():
    payload = {
        "schema_version": "processor-manifest/v1",
        "name": "test-processor",
        "version": "0.1.0",
        "supported_sdl_versions": ["sdl-authoring-input/v1"],
        "supported_contract_versions": ["backend-manifest/v1"],
        "supported_features": ["compilation", "planning"],
        "compatible_backends": ["stub"],
        "constraints": {"max_nodes": "64"},
    }
    model = ProcessorManifestModel.model_validate(payload)
    assert model.name == "test-processor"
    assert model.version == "0.1.0"
    assert model.supported_features == ["compilation", "planning"]
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


def test_valid_fixture_passes_validation():
    for path in sorted(VALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        model = ProcessorManifestModel.model_validate(payload)
        assert model.name, f"Valid fixture {path.name} should have a name"


def test_invalid_fixture_fails_validation():
    for path in sorted(INVALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ProcessorManifestModel.model_validate(payload)
