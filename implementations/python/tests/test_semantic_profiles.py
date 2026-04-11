"""Shared semantic profile contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aces_backend_stubs.stubs import create_stub_manifest
from aces_contracts.contracts import SemanticProfileModel
from aces_contracts.semantic_profiles import load_semantic_profile, semantic_profile_path
from aces_processor.manifest import create_reference_processor_manifest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = REPO_ROOT / "contracts" / "profiles" / "semantic" / "reference-stack-v1.json"
FIXTURES_ROOT = REPO_ROOT / "contracts" / "fixtures" / "semantic-profile" / "semantic-profile-v1"
VALID_DIR = FIXTURES_ROOT / "valid"
INVALID_DIR = FIXTURES_ROOT / "invalid"


def _binding_set(bindings: object) -> set[tuple[str, str]]:
    return {(binding.scope, binding.family) for binding in bindings}


def test_load_reference_semantic_profile():
    profile = load_semantic_profile("reference-stack-v1")

    assert profile.profile_id == "reference-stack-v1"
    assert profile.concept_catalog_version == "concept-families/v1"
    assert profile.processing.required_bindings
    assert profile.execution.required_bindings


def test_reference_profile_path_resolves():
    assert semantic_profile_path("reference-stack-v1") == PROFILE_PATH


def test_reference_profile_matches_valid_fixture():
    payload = json.loads((VALID_DIR / "reference-stack-v1.json").read_text(encoding="utf-8"))
    authoritative = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))

    assert payload == authoritative
    assert SemanticProfileModel.model_validate(payload).profile_id == "reference-stack-v1"


def test_semantic_profile_valid_fixtures_pass_validation():
    for path in sorted(VALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        model = SemanticProfileModel.model_validate(payload)
        assert model.profile_id, f"Valid semantic profile fixture {path.name} should have a profile id"


def test_semantic_profile_invalid_fixtures_fail_validation():
    for path in sorted(INVALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(ValidationError):
            SemanticProfileModel.model_validate(payload)


def test_semantic_profile_rejects_bindings_outside_phase_surfaces():
    payload = json.loads((INVALID_DIR / "processing-binding-scope-not-governed.json").read_text(encoding="utf-8"))

    with pytest.raises(ValidationError, match="governed processing surfaces"):
        SemanticProfileModel.model_validate(payload)


def test_semantic_profile_rejects_bindings_for_authoring_phase():
    payload = json.loads((INVALID_DIR / "authoring-binding-scope-not-governed.json").read_text(encoding="utf-8"))

    with pytest.raises(ValidationError, match="authoring does not define governed required_bindings surfaces"):
        SemanticProfileModel.model_validate(payload)


def test_reference_processor_satisfies_processing_profile():
    profile = load_semantic_profile("reference-stack-v1")
    manifest = create_reference_processor_manifest()

    required_contracts = set(profile.processing.required_contracts)
    required_bindings = _binding_set(profile.processing.required_bindings)

    assert required_contracts <= manifest.supported_contract_versions
    assert required_bindings <= _binding_set(manifest.concept_bindings)


def test_stub_backend_satisfies_execution_profile():
    profile = load_semantic_profile("reference-stack-v1")
    manifest = create_stub_manifest()

    required_contracts = set(profile.execution.required_contracts)
    required_bindings = _binding_set(profile.execution.required_bindings)

    assert required_contracts <= manifest.supported_contract_versions
    assert required_bindings <= _binding_set(manifest.concept_bindings)
