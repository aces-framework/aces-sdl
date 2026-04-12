"""Backend conformance tests."""

from __future__ import annotations

from aces_backend_protocols.capabilities import BackendManifest

from aces.backends.stubs import create_stub_components, create_stub_manifest, create_stub_target
from aces.core.runtime.conformance import (
    BackendCapabilityProfile,
    profile_for_manifest,
    required_contracts,
    run_fixture_suite,
    run_target_conformance,
)
from aces.core.runtime.registry import RuntimeTarget


def test_fixture_suite_passes_for_orchestration_evaluation_profile():
    report = run_fixture_suite(profile=BackendCapabilityProfile.ORCHESTRATION_EVALUATION)

    assert report.passed is True
    assert report.cases
    assert not report.diagnostics
    assert required_contracts(report.profile)


def test_target_conformance_passes_for_stub_target():
    report = run_target_conformance(create_stub_target())

    assert report.profile == BackendCapabilityProfile.ORCHESTRATION_EVALUATION
    assert report.passed is True
    assert not report.unsupported_contract_gaps
    assert not report.unsupported_capability_gaps


def test_profile_is_inferred_from_manifest_shape():
    target = create_stub_target()

    assert profile_for_manifest(target.manifest) == BackendCapabilityProfile.ORCHESTRATION_EVALUATION


def test_target_conformance_fails_when_declared_contracts_do_not_cover_profile_requirements():
    reference_manifest = create_stub_manifest()
    manifest = BackendManifest(
        identity=reference_manifest.identity,
        supported_contract_versions=frozenset({"backend-manifest-v2"}),
        compatibility=reference_manifest.compatibility,
        realization_support=reference_manifest.realization_support,
        concept_bindings=reference_manifest.concept_bindings,
        constraints=reference_manifest.constraints,
        capabilities=reference_manifest.capabilities,
    )
    components = create_stub_components(manifest=manifest)
    target = RuntimeTarget(
        name=manifest.name,
        manifest=manifest,
        provisioner=components.provisioner,
        orchestrator=components.orchestrator,
        evaluator=components.evaluator,
    )

    report = run_target_conformance(target)

    assert report.profile == BackendCapabilityProfile.ORCHESTRATION_EVALUATION
    assert report.passed is False
    assert set(report.unsupported_contract_gaps) == {
        "evaluation-history-event-stream-v1",
        "evaluation-result-envelope-v1",
        "operation-receipt-v1",
        "operation-status-v1",
        "runtime-snapshot-v1",
        "workflow-history-event-stream-v1",
        "workflow-result-envelope-v1",
    }
    assert any(diagnostic.code == "conformance.unsupported-contract-declaration" for diagnostic in report.diagnostics)
