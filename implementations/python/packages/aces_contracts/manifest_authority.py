"""Authority sets for processor and backend manifest declarations."""

from __future__ import annotations

from collections.abc import Iterable

PROCESSOR_SUPPORTED_SDL_VERSION_IDS = ("sdl-authoring-input-v1",)

# These are the published processor-facing and live-control-plane contracts a
# processor may honestly claim to support. Concept-authority catalogs, semantic
# profiles, backend manifests, and authoring-side request artifacts are
# separate authority surfaces and do not belong in this declaration field.
PROCESSOR_SUPPORTED_CONTRACT_IDS = (
    "processor-manifest-v2",
    "provisioning-plan-v1",
    "orchestration-plan-v1",
    "evaluation-plan-v1",
    "workflow-cancellation-request-v1",
    "operation-receipt-v1",
    "operation-status-v1",
    "runtime-snapshot-v1",
    "workflow-result-envelope-v1",
    "workflow-history-event-stream-v1",
    "evaluation-result-envelope-v1",
    "evaluation-history-event-stream-v1",
    "participant-episode-state-envelope-v1",
    "participant-episode-history-event-stream-v1",
)

# These are the published backend-facing and live-control-plane contracts a
# backend may honestly claim to support. Concept-authority catalogs, semantic
# profiles, processor manifests, and authoring-side request artifacts are
# separate authority surfaces and do not belong in this declaration field.
BACKEND_SUPPORTED_CONTRACT_IDS = (
    "backend-manifest-v2",
    "provisioning-plan-v1",
    "orchestration-plan-v1",
    "evaluation-plan-v1",
    "operation-receipt-v1",
    "operation-status-v1",
    "runtime-snapshot-v1",
    "workflow-result-envelope-v1",
    "workflow-history-event-stream-v1",
    "evaluation-result-envelope-v1",
    "evaluation-history-event-stream-v1",
    "participant-episode-state-envelope-v1",
    "participant-episode-history-event-stream-v1",
)


def validate_processor_supported_sdl_versions(values: Iterable[str]) -> None:
    _validate_allowed_values(
        "supported_sdl_versions",
        values,
        PROCESSOR_SUPPORTED_SDL_VERSION_IDS,
        "published SDL authoring contract ids",
    )


def validate_processor_supported_contract_versions(values: Iterable[str]) -> None:
    _validate_allowed_values(
        "supported_contract_versions",
        values,
        PROCESSOR_SUPPORTED_CONTRACT_IDS,
        "published processor/runtime contract ids",
    )


def validate_backend_supported_contract_versions(values: Iterable[str]) -> None:
    _validate_allowed_values(
        "supported_contract_versions",
        values,
        BACKEND_SUPPORTED_CONTRACT_IDS,
        "published backend/runtime contract ids",
    )


def _validate_allowed_values(
    field_name: str,
    values: Iterable[str],
    allowed_values: tuple[str, ...],
    allowed_label: str,
) -> None:
    materialized = list(values)
    if len(materialized) != len(set(materialized)):
        raise ValueError(f"{field_name} must not contain duplicates")

    allowed = frozenset(allowed_values)
    unknown = sorted(set(materialized) - allowed)
    if unknown:
        declared = ", ".join(unknown)
        raise ValueError(f"{field_name} include values outside the {allowed_label}: {declared}")
