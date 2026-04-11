"""Processor manifest declaration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aces_cli.main import app
from aces_contracts.apparatus import ConceptBinding
from aces_contracts.contracts import ProcessorManifestV2Model
from aces_contracts.manifest_authority import (
    PROCESSOR_SUPPORTED_CONTRACT_IDS,
    PROCESSOR_SUPPORTED_SDL_VERSION_IDS,
)
from aces_contracts.vocabulary import ProcessorFeature
from aces_processor.capabilities import ProcessorManifest
from aces_processor.manifest import (
    create_reference_processor_manifest,
    reference_processor_manifest_payload,
)
from pydantic import ValidationError
from typer.testing import CliRunner

FIXTURES_ROOT = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"
V2_VALID_DIR = FIXTURES_ROOT / "processor-manifest" / "processor-manifest-v2" / "valid"
V2_INVALID_DIR = FIXTURES_ROOT / "processor-manifest" / "processor-manifest-v2" / "invalid"
EXPECTED_SUPPORTED_CONTRACT_VERSIONS_V2 = [
    "processor-manifest-v2",
    "provisioning-plan-v1",
    "orchestration-plan-v1",
    "evaluation-plan-v1",
    "workflow-cancellation-request-v1",
    "operation-receipt-v1",
    "operation-status-v1",
    "runtime-snapshot-v1",
]


def _processor_concept_bindings() -> tuple[ConceptBinding, ...]:
    return (
        ConceptBinding(scope="capabilities.supported_sdl_versions", family="scenarios"),
        ConceptBinding(scope="capabilities.supported_features", family="apparatus-declarations"),
    )


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
    assert {feature.value for feature in ProcessorFeature} == expected


def test_processor_manifest_construction():
    manifest = ProcessorManifest(
        name="test",
        version="1.0.0",
        supported_contract_versions=frozenset({"processor-manifest-v2"}),
        supported_sdl_versions=frozenset({"sdl-authoring-input-v1"}),
        supported_features=frozenset({ProcessorFeature.COMPILATION}),
        compatible_backends=frozenset({"stub"}),
        concept_bindings=_processor_concept_bindings(),
    )
    assert manifest.name == "test"
    assert manifest.version == "1.0.0"
    assert manifest.supported_sdl_versions == frozenset({"sdl-authoring-input-v1"})
    assert manifest.supported_contract_versions == frozenset({"processor-manifest-v2"})
    assert manifest.supported_features == frozenset({ProcessorFeature.COMPILATION})
    assert manifest.compatible_backends == frozenset({"stub"})
    assert manifest.constraints == {}
    assert manifest.concept_bindings == _processor_concept_bindings()


def test_processor_manifest_frozen():
    manifest = ProcessorManifest(
        name="test",
        version="1.0.0",
        supported_contract_versions=frozenset({"processor-manifest-v2"}),
        supported_sdl_versions=frozenset({"sdl-authoring-input-v1"}),
        supported_features=frozenset({ProcessorFeature.COMPILATION}),
        compatible_backends=frozenset({"stub"}),
        concept_bindings=_processor_concept_bindings(),
    )
    with pytest.raises(AttributeError):
        manifest.name = "changed"


def test_processor_manifest_rejects_hollow_defaults():
    with pytest.raises(ValueError):
        ProcessorManifest(name="test", version="1.0.0")


def test_processor_manifest_with_features():
    manifest = ProcessorManifest(
        name="aces-reference",
        version="0.1.0",
        supported_contract_versions=frozenset({"processor-manifest-v2"}),
        supported_sdl_versions=frozenset({"sdl-authoring-input-v1"}),
        supported_features=frozenset({ProcessorFeature.COMPILATION, ProcessorFeature.PLANNING}),
        compatible_backends=frozenset({"stub"}),
        concept_bindings=_processor_concept_bindings(),
    )
    assert ProcessorFeature.COMPILATION in manifest.supported_features
    assert ProcessorFeature.PLANNING in manifest.supported_features
    assert manifest.compatible_backends == frozenset({"stub"})
    assert len(manifest.supported_features) == 2


def test_processor_manifest_v2_model_roundtrip():
    payload = {
        "schema_version": "processor-manifest/v2",
        "identity": {
            "name": "test-processor",
            "version": "0.1.0",
        },
        "supported_contract_versions": ["processor-manifest-v2"],
        "compatibility": {
            "backends": ["stub"],
        },
        "concept_bindings": [
            {"scope": "capabilities.supported_sdl_versions", "family": "scenarios"},
            {"scope": "capabilities.supported_features", "family": "apparatus-declarations"},
        ],
        "constraints": {"max_nodes": "64"},
        "capabilities": {
            "supported_sdl_versions": ["sdl-authoring-input-v1"],
            "supported_features": ["compilation", "planning"],
        },
    }
    model = ProcessorManifestV2Model.model_validate(payload)
    assert model.identity.name == "test-processor"
    assert model.identity.version == "0.1.0"
    assert model.capabilities.supported_features == [
        ProcessorFeature.COMPILATION,
        ProcessorFeature.PLANNING,
    ]
    assert model.concept_bindings[0].scope == "capabilities.supported_sdl_versions"
    assert model.concept_bindings[0].family == "scenarios"
    assert model.model_dump(mode="json") == payload


def test_processor_manifest_v2_model_requires_manifest_sections():
    with pytest.raises(ValidationError):
        ProcessorManifestV2Model(
            identity={"name": "minimal", "version": "0.0.1"},
            capabilities={},
        )


def test_processor_manifest_v2_model_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ProcessorManifestV2Model(
            identity={"name": "bad", "version": "0.0.1"},
            capabilities={},
            unknown_extra_field=True,
        )


def test_processor_manifest_models_reject_unknown_feature():
    with pytest.raises(ValidationError):
        ProcessorManifestV2Model(
            identity={"name": "bad", "version": "0.0.1"},
            capabilities={"supported_features": ["definitely-not-a-real-feature"]},
        )


def test_processor_manifest_runtime_rejects_unknown_supported_contract_versions():
    with pytest.raises(ValueError, match="supported_contract_versions"):
        ProcessorManifest(
            name="bad",
            version="0.0.1",
            supported_contract_versions=frozenset({"semantic-profile-v1"}),
            supported_sdl_versions=frozenset({"sdl-authoring-input-v1"}),
            supported_features=frozenset({ProcessorFeature.COMPILATION}),
            compatible_backends=frozenset({"stub"}),
            concept_bindings=_processor_concept_bindings(),
        )


def test_processor_manifest_runtime_rejects_unknown_supported_sdl_versions():
    with pytest.raises(ValueError, match="supported_sdl_versions"):
        ProcessorManifest(
            name="bad",
            version="0.0.1",
            supported_contract_versions=frozenset({"processor-manifest-v2"}),
            supported_sdl_versions=frozenset({"sdl-authoring-input-v9"}),
            supported_features=frozenset({ProcessorFeature.COMPILATION}),
            compatible_backends=frozenset({"stub"}),
            concept_bindings=_processor_concept_bindings(),
        )


def test_processor_manifest_v2_rejects_empty_compatibility():
    with pytest.raises(ValidationError):
        ProcessorManifestV2Model.model_validate(
            {
                "schema_version": "processor-manifest/v2",
                "identity": {"name": "bad", "version": "0.0.1"},
                "supported_contract_versions": ["processor-manifest-v2"],
                "compatibility": {},
                "capabilities": {
                    "supported_sdl_versions": ["sdl-authoring-input-v1"],
                    "supported_features": ["compilation"],
                },
            }
        )


def test_processor_manifest_v2_rejects_non_backend_compatibility_surfaces():
    with pytest.raises(ValidationError):
        ProcessorManifestV2Model.model_validate(
            {
                "schema_version": "processor-manifest/v2",
                "identity": {"name": "bad", "version": "0.0.1"},
                "supported_contract_versions": ["processor-manifest-v2"],
                "compatibility": {"processors": ["other-processor"], "backends": ["stub"]},
                "capabilities": {
                    "supported_sdl_versions": ["sdl-authoring-input-v1"],
                    "supported_features": ["compilation"],
                },
            }
        )
    with pytest.raises(ValidationError):
        ProcessorManifestV2Model.model_validate(
            {
                "schema_version": "processor-manifest/v2",
                "identity": {"name": "bad", "version": "0.0.1"},
                "supported_contract_versions": ["processor-manifest-v2"],
                "compatibility": {
                    "backends": ["stub"],
                    "participant_implementations": ["participant-impl"],
                },
                "capabilities": {
                    "supported_sdl_versions": ["sdl-authoring-input-v1"],
                    "supported_features": ["compilation"],
                },
            }
        )


def test_processor_manifest_v2_rejects_realization_support_section():
    with pytest.raises(ValidationError):
        ProcessorManifestV2Model.model_validate(
            {
                "schema_version": "processor-manifest/v2",
                "identity": {"name": "bad", "version": "0.0.1"},
                "supported_contract_versions": ["processor-manifest-v2"],
                "compatibility": {"backends": ["stub"]},
                "realization_support": [
                    {
                        "domain": "instantiation",
                        "support_mode": "constrained",
                        "supported_constraint_kinds": ["parameter-values"],
                        "disclosure_kinds": ["parameter-instantiation"],
                    }
                ],
                "capabilities": {
                    "supported_sdl_versions": ["sdl-authoring-input-v1"],
                    "supported_features": ["compilation"],
                },
            }
        )


def test_processor_manifest_v2_rejects_empty_capability_lists():
    with pytest.raises(ValidationError):
        ProcessorManifestV2Model.model_validate(
            {
                "schema_version": "processor-manifest/v2",
                "identity": {"name": "bad", "version": "0.0.1"},
                "supported_contract_versions": ["processor-manifest-v2"],
                "compatibility": {"backends": ["stub"]},
                "capabilities": {},
            }
        )


def test_reference_processor_manifest_v2_matches_contract_payload():
    manifest = create_reference_processor_manifest(version="0.2.0")
    payload = reference_processor_manifest_payload(version="0.2.0")

    assert payload["schema_version"] == "processor-manifest/v2"
    assert manifest.name == payload["identity"]["name"]
    assert manifest.version == payload["identity"]["version"]
    assert set(manifest.supported_contract_versions) == set(EXPECTED_SUPPORTED_CONTRACT_VERSIONS_V2)
    assert payload["capabilities"]["supported_sdl_versions"] == ["sdl-authoring-input-v1"]
    assert payload["supported_contract_versions"] == EXPECTED_SUPPORTED_CONTRACT_VERSIONS_V2
    assert payload["compatibility"] == {"backends": ["stub"]}
    assert payload["capabilities"]["supported_features"] == [feature.value for feature in ProcessorFeature]
    assert payload["capabilities"]["supported_sdl_versions"] == list(PROCESSOR_SUPPORTED_SDL_VERSION_IDS)
    assert set(payload["supported_contract_versions"]) <= set(PROCESSOR_SUPPORTED_CONTRACT_IDS)
    assert "backend-manifest-v1" not in payload["supported_contract_versions"]
    assert "concept-families-v1" not in payload["supported_contract_versions"]
    assert "instantiated-scenario-v1" not in payload["supported_contract_versions"]
    assert "scenario-instantiation-request-v1" not in payload["supported_contract_versions"]


def test_reference_processor_v2_fixture_matches_reference_manifest():
    payload = json.loads((V2_VALID_DIR / "reference.json").read_text(encoding="utf-8"))
    assert payload == reference_processor_manifest_payload(version=payload["identity"]["version"])


def test_processor_manifest_valid_fixtures_pass_validation():
    for path in sorted(V2_VALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        model = ProcessorManifestV2Model.model_validate(payload)
        assert model.identity.name, f"Valid v2 fixture {path.name} should have a name"


def test_processor_manifest_invalid_fixtures_fail_validation():
    for path in sorted(V2_INVALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(ValidationError):
            ProcessorManifestV2Model.model_validate(payload)


def test_processor_manifest_cli_emits_reference_v2_manifest():
    runner = CliRunner()
    result = runner.invoke(app, ["processor", "manifest"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == reference_processor_manifest_payload(version=payload["identity"]["version"])
