"""Reference processor manifest declarations."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from typing import Any

from aces_contracts.contracts import ProcessorManifestModel
from aces_contracts.vocabulary import ProcessorFeature

from aces_processor.capabilities import ProcessorManifest

REFERENCE_PROCESSOR_NAME = "aces-reference-processor"
REFERENCE_SUPPORTED_CONTRACT_VERSIONS = (
    "processor-manifest-v1",
    "provisioning-plan-v1",
    "orchestration-plan-v1",
    "evaluation-plan-v1",
    "workflow-cancellation-request-v1",
    "operation-receipt-v1",
    "operation-status-v1",
    "runtime-snapshot-v1",
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
        supported_sdl_versions=frozenset({"sdl-authoring-input-v1"}),
        supported_contract_versions=frozenset(REFERENCE_SUPPORTED_CONTRACT_VERSIONS),
        supported_features=frozenset(ProcessorFeature),
        compatible_backends=frozenset({"stub"}),
        constraints={},
    )


def reference_processor_manifest_model(
    *,
    version: str | None = None,
) -> ProcessorManifestModel:
    """Return the reference processor manifest as a closed-world contract model."""

    manifest = create_reference_processor_manifest(version=version)
    return ProcessorManifestModel(
        name=manifest.name,
        version=manifest.version,
        supported_sdl_versions=["sdl-authoring-input-v1"],
        supported_contract_versions=list(REFERENCE_SUPPORTED_CONTRACT_VERSIONS),
        supported_features=[feature for feature in ProcessorFeature if feature in manifest.supported_features],
        compatible_backends=sorted(manifest.compatible_backends),
        constraints=dict(manifest.constraints),
    )


def reference_processor_manifest_payload(
    *,
    version: str | None = None,
) -> dict[str, Any]:
    """Return the reference processor manifest as JSON-ready data."""

    return reference_processor_manifest_model(version=version).model_dump(mode="json")
