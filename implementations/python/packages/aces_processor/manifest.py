"""Reference processor manifest declarations."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from typing import Any, Literal

from aces_contracts.apparatus import RealizationSupportDeclaration
from aces_contracts.contracts import (
    ApparatusCompatibilityModel,
    ApparatusIdentityModel,
    ProcessorCapabilitiesV2Model,
    ProcessorManifestModel,
    ProcessorManifestV2Model,
    RealizationSupportDeclarationModel,
)
from aces_contracts.vocabulary import ProcessorFeature, RealizationSupportMode

from aces_processor.capabilities import ProcessorCapabilitySet, ProcessorManifest

REFERENCE_PROCESSOR_NAME = "aces-reference-processor"
REFERENCE_SUPPORTED_CONTRACT_VERSIONS_V1 = (
    "processor-manifest-v1",
    "provisioning-plan-v1",
    "orchestration-plan-v1",
    "evaluation-plan-v1",
    "workflow-cancellation-request-v1",
    "operation-receipt-v1",
    "operation-status-v1",
    "runtime-snapshot-v1",
)
REFERENCE_SUPPORTED_CONTRACT_VERSIONS_V2 = (
    "processor-manifest-v2",
    "provisioning-plan-v1",
    "orchestration-plan-v1",
    "evaluation-plan-v1",
    "workflow-cancellation-request-v1",
    "operation-receipt-v1",
    "operation-status-v1",
    "runtime-snapshot-v1",
)
REFERENCE_REALIZATION_SUPPORT = (
    RealizationSupportDeclaration(
        domain="instantiation",
        support_mode=RealizationSupportMode.CONSTRAINED,
        supported_constraint_kinds=frozenset({"parameter-values", "module-selection"}),
        supported_exact_requirement_kinds=frozenset({"declared-parameter-values"}),
        disclosure_kinds=frozenset({"parameter-instantiation", "module-composition"}),
    ),
)


def _current_processor_version() -> str:
    try:
        return distribution_version("aces-sdl")
    except PackageNotFoundError:
        return "0.0.0+unknown"


def create_reference_processor_manifest(
    *,
    version: str | None = None,
) -> ProcessorManifest:
    """Return the current repo-owned reference processor manifest."""

    return ProcessorManifest(
        name=REFERENCE_PROCESSOR_NAME,
        version=version or _current_processor_version(),
        supported_contract_versions=frozenset(REFERENCE_SUPPORTED_CONTRACT_VERSIONS_V2),
        capabilities=ProcessorCapabilitySet(
            supported_sdl_versions=frozenset({"sdl-authoring-input-v1"}),
            supported_features=frozenset(ProcessorFeature),
        ),
        compatible_backends=frozenset({"stub"}),
        realization_support=REFERENCE_REALIZATION_SUPPORT,
        constraints={},
    )


def reference_processor_manifest_v1_model(
    *,
    version: str | None = None,
) -> ProcessorManifestModel:
    """Return the reference processor manifest as the legacy v1 contract model."""

    manifest = create_reference_processor_manifest(version=version)
    return ProcessorManifestModel(
        name=manifest.name,
        version=manifest.version,
        supported_sdl_versions=["sdl-authoring-input-v1"],
        supported_contract_versions=list(REFERENCE_SUPPORTED_CONTRACT_VERSIONS_V1),
        supported_features=[feature for feature in ProcessorFeature if feature in manifest.supported_features],
        compatible_backends=sorted(manifest.compatible_backends),
        constraints=dict(manifest.constraints),
    )


def reference_processor_manifest_v2_model(
    *,
    version: str | None = None,
) -> ProcessorManifestV2Model:
    """Return the reference processor manifest as the shared v2 apparatus model."""

    manifest = create_reference_processor_manifest(version=version)
    return ProcessorManifestV2Model(
        identity=ApparatusIdentityModel(name=manifest.identity.name, version=manifest.identity.version),
        supported_contract_versions=list(REFERENCE_SUPPORTED_CONTRACT_VERSIONS_V2),
        compatibility=ApparatusCompatibilityModel(
            backends=sorted(manifest.compatible_backends),
        ),
        realization_support=[
            RealizationSupportDeclarationModel(
                domain=declaration.domain,
                support_mode=declaration.support_mode,
                supported_constraint_kinds=sorted(declaration.supported_constraint_kinds),
                supported_exact_requirement_kinds=sorted(declaration.supported_exact_requirement_kinds),
                disclosure_kinds=sorted(declaration.disclosure_kinds),
                constraints=dict(declaration.constraints),
            )
            for declaration in manifest.realization_support
        ],
        constraints=dict(manifest.constraints),
        capabilities=ProcessorCapabilitiesV2Model(
            supported_sdl_versions=sorted(manifest.supported_sdl_versions),
            supported_features=[feature for feature in ProcessorFeature if feature in manifest.supported_features],
        ),
    )


def reference_processor_manifest_model(
    *,
    version: str | None = None,
) -> ProcessorManifestV2Model:
    """Return the reference processor manifest as the authoritative v2 contract model."""

    return reference_processor_manifest_v2_model(version=version)


def reference_processor_manifest_payload(
    *,
    version: str | None = None,
    schema_version: Literal["v1", "v2"] = "v2",
) -> dict[str, Any]:
    """Return the reference processor manifest as JSON-ready data."""

    if schema_version == "v1":
        return reference_processor_manifest_v1_model(version=version).model_dump(mode="json")
    return reference_processor_manifest_v2_model(version=version).model_dump(mode="json")
