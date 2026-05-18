"""Participant behavior contract models (SEM-208).

The legacy ``agents.*.actions`` list remains the authoring reference list.
These models provide the governed source of truth those names resolve to when
an SDL document declares explicit participant behavior semantics.
"""

from enum import Enum

from pydantic import Field, field_validator, model_validator

from ._base import SDLModel


class ParticipantActionLifecycle(str, Enum):
    """Governance lifecycle for participant action contracts."""

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class ParticipantActionGranularity(str, Enum):
    """Behavioral granularity of a participant action contract."""

    ATOMIC = "atomic"
    PROCEDURE = "procedure"
    AGGREGATE = "aggregate"


class ExternalMappingLoss(SDLModel):
    """Loss-labeled mapping from an external vocabulary to ACES semantics."""

    system: str
    identifier: str
    loss_label: str
    rationale: str

    @field_validator("system", "identifier", "loss_label", "rationale")
    @classmethod
    def _require_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("external mapping fields must be non-empty")
        return value


class ParticipantActionContract(SDLModel):
    """Governed semantic contract for one participant action name."""

    semantic_version: str
    lifecycle_state: ParticipantActionLifecycle = ParticipantActionLifecycle.ACTIVE
    behavioral_granularity: ParticipantActionGranularity
    procedure_basis: str
    realization_profile: str
    fidelity_claim: str
    preconditions: list[str] = Field(default_factory=list)
    intended_effects: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    state_transition_effects: list[str] = Field(default_factory=list)
    observation_expectations: list[str] = Field(default_factory=list)
    evidence_expectations: list[str] = Field(default_factory=list)
    failure_classes: list[str] = Field(default_factory=list)
    external_mappings: list[ExternalMappingLoss] = Field(default_factory=list)

    @field_validator(
        "semantic_version",
        "procedure_basis",
        "realization_profile",
        "fidelity_claim",
    )
    @classmethod
    def _require_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("participant action contract fields must be non-empty")
        return value


class ParticipantObservationBoundary(SDLModel):
    """Participant-specific observation projection boundary."""

    projection_basis: str
    observable_refs: list[str] = Field(default_factory=list)
    hidden_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    redaction_policy: str
    latency_profile: str
    observer_effects: list[str] = Field(default_factory=list)

    @field_validator("projection_basis", "redaction_policy", "latency_profile")
    @classmethod
    def _require_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("participant observation boundary fields must be non-empty")
        return value

    @model_validator(mode="after")
    def _validate_projection(self) -> "ParticipantObservationBoundary":
        if not self.observable_refs and not self.evidence_refs:
            raise ValueError("participant observation boundary requires observable_refs or evidence_refs")
        exposed = set(self.observable_refs) | set(self.evidence_refs)
        leaked = sorted(exposed & set(self.hidden_refs))
        if leaked:
            joined = ", ".join(leaked)
            raise ValueError(f"hidden_refs must not also be observable or evidence refs: {joined}")
        return self
