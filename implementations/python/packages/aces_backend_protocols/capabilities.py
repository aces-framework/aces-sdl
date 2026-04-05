"""Domain-specific runtime capability declarations."""

from __future__ import annotations

from dataclasses import dataclass, field

from aces_contracts.apparatus import (
    ApparatusCompatibility,
    ApparatusIdentity,
    RealizationSupportDeclaration,
)
from aces_contracts.vocabulary import WorkflowFeature, WorkflowStatePredicateFeature


@dataclass(frozen=True)
class ProvisionerCapabilities:
    """Provisioning support declaration."""

    name: str
    supported_node_types: frozenset[str] = frozenset()
    supported_os_families: frozenset[str] = frozenset()
    supported_content_types: frozenset[str] = frozenset()
    supported_account_features: frozenset[str] = frozenset()
    max_total_nodes: int | None = None
    supports_acls: bool = False
    supports_accounts: bool = False
    constraints: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class OrchestratorCapabilities:
    """Orchestration support declaration."""

    name: str
    supported_sections: frozenset[str] = frozenset()
    supports_workflows: bool = False
    supports_condition_refs: bool = True
    supports_inject_bindings: bool = True
    supported_workflow_features: frozenset[WorkflowFeature] = frozenset()
    supported_workflow_state_predicates: frozenset[WorkflowStatePredicateFeature] = frozenset()
    constraints: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluatorCapabilities:
    """Evaluation support declaration."""

    name: str
    supported_sections: frozenset[str] = frozenset()
    supports_scoring: bool = True
    supports_objectives: bool = True
    constraints: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BackendCapabilitySet:
    """Backend-specific nested capability blocks."""

    provisioner: ProvisionerCapabilities
    orchestrator: OrchestratorCapabilities | None = None
    evaluator: EvaluatorCapabilities | None = None


@dataclass(frozen=True, init=False)
class BackendManifest:
    """Complete runtime target capability declaration."""

    identity: ApparatusIdentity
    supported_contract_versions: frozenset[str]
    compatibility: ApparatusCompatibility
    realization_support: tuple[RealizationSupportDeclaration, ...]
    constraints: dict[str, str]
    capabilities: BackendCapabilitySet

    def __init__(
        self,
        *,
        identity: ApparatusIdentity | None = None,
        supported_contract_versions: frozenset[str] = frozenset(),
        compatibility: ApparatusCompatibility | None = None,
        realization_support: tuple[RealizationSupportDeclaration, ...] = (),
        constraints: dict[str, str] | None = None,
        capabilities: BackendCapabilitySet | None = None,
        name: str | None = None,
        version: str = "0.0.0+unknown",
        compatible_processors: frozenset[str] = frozenset(),
        compatible_backends: frozenset[str] = frozenset(),
        compatible_participant_implementations: frozenset[str] = frozenset(),
        provisioner: ProvisionerCapabilities | None = None,
        orchestrator: OrchestratorCapabilities | None = None,
        evaluator: EvaluatorCapabilities | None = None,
    ) -> None:
        if identity is None:
            if name is None:
                raise ValueError("BackendManifest requires either identity or name.")
            identity = ApparatusIdentity(name=name, version=version)
        if compatibility is None:
            compatibility = ApparatusCompatibility(
                processors=frozenset(compatible_processors),
                backends=frozenset(compatible_backends),
                participant_implementations=frozenset(compatible_participant_implementations),
            )
        if capabilities is None:
            if provisioner is None:
                raise ValueError("BackendManifest requires either capabilities or provisioner.")
            capabilities = BackendCapabilitySet(
                provisioner=provisioner,
                orchestrator=orchestrator,
                evaluator=evaluator,
            )
        object.__setattr__(self, "identity", identity)
        object.__setattr__(self, "supported_contract_versions", frozenset(supported_contract_versions))
        object.__setattr__(self, "compatibility", compatibility)
        object.__setattr__(self, "realization_support", tuple(realization_support))
        object.__setattr__(self, "constraints", {} if constraints is None else dict(constraints))
        object.__setattr__(self, "capabilities", capabilities)

    @property
    def name(self) -> str:
        return self.identity.name

    @property
    def version(self) -> str:
        return self.identity.version

    @property
    def compatible_processors(self) -> frozenset[str]:
        return self.compatibility.processors

    @property
    def compatible_backends(self) -> frozenset[str]:
        return self.compatibility.backends

    @property
    def compatible_participant_implementations(self) -> frozenset[str]:
        return self.compatibility.participant_implementations

    @property
    def provisioner(self) -> ProvisionerCapabilities:
        return self.capabilities.provisioner

    @property
    def orchestrator(self) -> OrchestratorCapabilities | None:
        return self.capabilities.orchestrator

    @property
    def evaluator(self) -> EvaluatorCapabilities | None:
        return self.capabilities.evaluator

    @property
    def has_orchestrator(self) -> bool:
        return self.orchestrator is not None

    @property
    def has_evaluator(self) -> bool:
        return self.evaluator is not None

    @property
    def evaluator_supported_sections(self) -> frozenset[str]:
        if self.evaluator is None:
            return frozenset()
        return self.evaluator.supported_sections

    @property
    def supports_scoring(self) -> bool:
        return self.evaluator.supports_scoring if self.evaluator is not None else False

    @property
    def supports_objectives(self) -> bool:
        return self.evaluator.supports_objectives if self.evaluator is not None else False
