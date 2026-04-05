"""Backend manifest declaration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aces_backend_protocols.manifest import backend_manifest_payload
from aces_backend_stubs.stubs import create_stub_manifest
from aces_contracts.contracts import BackendManifestModel, BackendManifestV2Model
from aces_contracts.vocabulary import WorkflowFeature, WorkflowStatePredicateFeature
from pydantic import ValidationError

FIXTURES_ROOT = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"
V1_VALID_DIR = FIXTURES_ROOT / "backend-manifest" / "backend-manifest-v1" / "valid"
V1_INVALID_DIR = FIXTURES_ROOT / "backend-manifest" / "backend-manifest-v1" / "invalid"
V2_VALID_DIR = FIXTURES_ROOT / "backend-manifest" / "backend-manifest-v2" / "valid"
V2_INVALID_DIR = FIXTURES_ROOT / "backend-manifest" / "backend-manifest-v2" / "invalid"
EXPECTED_SUPPORTED_CONTRACT_VERSIONS_V2 = [
    "backend-manifest-v2",
    "evaluation-history-event-stream-v1",
    "evaluation-plan-v1",
    "evaluation-result-envelope-v1",
    "operation-receipt-v1",
    "operation-status-v1",
    "orchestration-plan-v1",
    "provisioning-plan-v1",
    "runtime-snapshot-v1",
    "workflow-history-event-stream-v1",
    "workflow-result-envelope-v1",
]


def test_backend_workflow_vocab_enum_values():
    assert {feature.value for feature in WorkflowFeature} == {
        "decision",
        "switch",
        "retry",
        "call",
        "parallel-barrier",
        "failure-transitions",
        "cancellation",
        "timeouts",
        "compensation",
    }
    assert {feature.value for feature in WorkflowStatePredicateFeature} == {
        "outcome-matching",
        "attempt-counts",
    }


def test_backend_manifest_v1_roundtrip_from_stub_manifest():
    payload = backend_manifest_payload(create_stub_manifest(), version="v1")
    model = BackendManifestModel.model_validate(payload)

    assert model.schema_version == "backend-manifest/v1"
    assert model.name == "stub"
    assert model.orchestrator is not None
    assert model.orchestrator.supported_workflow_features == [
        WorkflowFeature.CALL,
        WorkflowFeature.CANCELLATION,
        WorkflowFeature.COMPENSATION,
        WorkflowFeature.DECISION,
        WorkflowFeature.FAILURE_TRANSITIONS,
        WorkflowFeature.PARALLEL_BARRIER,
        WorkflowFeature.RETRY,
        WorkflowFeature.SWITCH,
        WorkflowFeature.TIMEOUTS,
    ]
    assert model.orchestrator.supported_workflow_state_predicates == [
        WorkflowStatePredicateFeature.ATTEMPT_COUNTS,
        WorkflowStatePredicateFeature.OUTCOME_MATCHING,
    ]
    assert model.model_dump(mode="json") == payload


def test_backend_manifest_v2_roundtrip_from_stub_manifest():
    payload = backend_manifest_payload(create_stub_manifest(), version="v2")
    model = BackendManifestV2Model.model_validate(payload)

    assert model.schema_version == "backend-manifest/v2"
    assert model.identity.name == "stub"
    assert model.identity.version
    assert model.compatibility.processors == ["aces-reference-processor"]
    assert model.supported_contract_versions == EXPECTED_SUPPORTED_CONTRACT_VERSIONS_V2
    assert model.capabilities.orchestrator is not None
    assert model.capabilities.orchestrator.supported_workflow_features == [
        WorkflowFeature.CALL,
        WorkflowFeature.CANCELLATION,
        WorkflowFeature.COMPENSATION,
        WorkflowFeature.DECISION,
        WorkflowFeature.FAILURE_TRANSITIONS,
        WorkflowFeature.PARALLEL_BARRIER,
        WorkflowFeature.RETRY,
        WorkflowFeature.SWITCH,
        WorkflowFeature.TIMEOUTS,
    ]
    assert model.realization_support[0].support_mode.value == "constrained"
    assert model.model_dump(mode="json") == payload


def test_reference_backend_v1_fixture_matches_emitted_manifest():
    payload = json.loads((V1_VALID_DIR / "stub.json").read_text(encoding="utf-8"))
    assert payload == backend_manifest_payload(create_stub_manifest(), version="v1")


def test_reference_backend_v2_fixture_matches_emitted_manifest():
    payload = json.loads((V2_VALID_DIR / "stub.json").read_text(encoding="utf-8"))
    assert payload == backend_manifest_payload(create_stub_manifest(), version="v2")


def test_backend_manifest_valid_fixtures_pass_validation():
    for path in sorted(V1_VALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        model = BackendManifestModel.model_validate(payload)
        assert model.name, f"Valid v1 fixture {path.name} should have a name"

    for path in sorted(V2_VALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        model = BackendManifestV2Model.model_validate(payload)
        assert model.identity.name, f"Valid v2 fixture {path.name} should have a name"


def test_backend_manifest_invalid_fixtures_fail_validation():
    for path in sorted(V1_INVALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(ValidationError):
            BackendManifestModel.model_validate(payload)

    for path in sorted(V2_INVALID_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(ValidationError):
            BackendManifestV2Model.model_validate(payload)
