"""Top-level Scenario model — the root of the SDL.

The Scenario combines 21 specification sections covering
who (entities, accounts, agents), what (nodes, features,
vulnerabilities, content), when (scripts, stories, events),
and declarative experiment semantics (objectives, scoring
pipeline, conditions, relationships, workflows, variables).

Delivery-level concerns (Docker, Terraform, cloud APIs) are
outside the SDL.
"""

from pydantic import Field, PrivateAttr, model_validator

from ._base import SDLModel
from .accounts import Account
from .agents import Agent
from .conditions import Condition
from .content import Content
from .entities import Entity
from .features import Feature
from .infrastructure import InfraNode
from .nodes import Node
from .objectives import Objective
from .orchestration import Event, Inject, Script, Story, Workflow
from .participant_behavior import ParticipantActionContract, ParticipantObservationBoundary
from .participant_outcome_semantics import OutcomeInterpretationRule
from .relationships import Relationship
from .scoring import TLO, Evaluation, Goal, Metric
from .variables import Variable
from .vulnerabilities import Vulnerability


class ModuleDescriptor(SDLModel):
    """Published module metadata for SDL composition."""

    id: str
    version: str
    parameters: list[str] = Field(default_factory=list)
    exports: dict[str, list[str]] = Field(default_factory=dict)
    description: str = ""

    @model_validator(mode="after")
    def validate_descriptor(self) -> "ModuleDescriptor":
        if "/" not in self.id or self.id.startswith("/") or self.id.endswith("/"):
            raise ValueError("module.id must use canonical 'publisher/name' format")
        if len(self.parameters) != len(set(self.parameters)):
            raise ValueError("module.parameters must be unique")
        for section, names in self.exports.items():
            if len(names) != len(set(names)):
                raise ValueError(f"module.exports.{section} entries must be unique")
        return self


class ImportDecl(SDLModel):
    """A module import expanded before full semantic validation."""

    source: str = ""
    path: str = ""
    namespace: str = ""
    version: str = "*"
    parameters: dict[str, object] = Field(default_factory=dict)
    digest: str = ""

    @model_validator(mode="after")
    def validate_source_fields(self) -> "ImportDecl":
        if not self.source and not self.path:
            raise ValueError("Import requires either 'source' or deprecated 'path'")
        if self.source and self.path:
            raise ValueError("Import may specify only one of 'source' or 'path'")
        if self.path and not self.namespace:
            # Local path imports remain backward compatible and may derive namespace.
            return self
        if self.source.startswith("oci:") and not self.namespace:
            raise ValueError("OCI imports require an explicit namespace")
        return self

    @property
    def normalized_source(self) -> str:
        if self.source:
            return self.source
        return f"local:{self.path}"


class Scenario(SDLModel):
    """Top-level scenario specification.

    A YAML document with up to 21 named sections. Only ``name``
    is required. All sections are optional dicts keyed by
    user-defined identifiers.
    """

    # --- Identity ---
    name: str
    version: str = "*"
    description: str = ""
    module: ModuleDescriptor | None = None
    imports: list[ImportDecl] = Field(default_factory=list)

    # --- OCR SDL: 14 sections ---
    nodes: dict[str, Node] = Field(default_factory=dict)
    infrastructure: dict[str, InfraNode] = Field(default_factory=dict)
    features: dict[str, Feature] = Field(default_factory=dict)
    conditions: dict[str, Condition] = Field(default_factory=dict)
    vulnerabilities: dict[str, Vulnerability] = Field(default_factory=dict)
    metrics: dict[str, Metric] = Field(default_factory=dict)
    evaluations: dict[str, Evaluation] = Field(default_factory=dict)
    tlos: dict[str, TLO] = Field(default_factory=dict)
    goals: dict[str, Goal] = Field(default_factory=dict)
    entities: dict[str, Entity] = Field(default_factory=dict)
    injects: dict[str, Inject] = Field(default_factory=dict)
    events: dict[str, Event] = Field(default_factory=dict)
    scripts: dict[str, Script] = Field(default_factory=dict)
    stories: dict[str, Story] = Field(default_factory=dict)

    # --- Extended sections ---
    content: dict[str, Content] = Field(default_factory=dict)
    accounts: dict[str, Account] = Field(default_factory=dict)
    relationships: dict[str, Relationship] = Field(default_factory=dict)
    agents: dict[str, Agent] = Field(default_factory=dict)
    action_contracts: dict[str, ParticipantActionContract] = Field(default_factory=dict)
    observation_boundaries: dict[str, ParticipantObservationBoundary] = Field(default_factory=dict)
    outcome_interpretation_rules: dict[str, OutcomeInterpretationRule] = Field(default_factory=dict)
    objectives: dict[str, Objective] = Field(default_factory=dict)
    workflows: dict[str, Workflow] = Field(default_factory=dict)
    variables: dict[str, Variable] = Field(default_factory=dict)

    _advisories: list[str] = PrivateAttr(default_factory=list)
    _semantic_validated: bool = PrivateAttr(default=False)
    # Capability-variable provenance carried across the SDL module-import
    # composition boundary. The composition pass strips imported variables
    # from the merged payload by design, so this side-channel preserves the
    # imported variable specs (namespace-prefixed) and the imported nodes'
    # `${name}` refs onto the outer scenario. The instantiation and runtime-
    # compile paths read these to enforce backend `allowed_values` against
    # imported modules even though their variables don't survive the merge.
    # Inner mapping shape mirrors `InstantiatedScenario._node_variable_refs`.
    _module_variable_specs: dict[str, dict[str, object]] = PrivateAttr(default_factory=dict)
    _module_node_variable_refs: dict[str, dict[str, str | None]] = PrivateAttr(default_factory=dict)

    @property
    def advisories(self) -> list[str]:
        """Non-fatal SDL advisories gathered during semantic validation."""
        return list(self._advisories)

    def _set_advisories(self, advisories: list[str]) -> None:
        self._advisories = list(advisories)

    @property
    def semantic_validated(self) -> bool:
        """Whether full semantic validation has already run on this scenario."""
        return self._semantic_validated

    def _set_semantic_validated(self, validated: bool) -> None:
        self._semantic_validated = bool(validated)

    @property
    def module_variable_specs(self) -> dict[str, dict[str, object]]:
        """Namespace-prefixed variable specs preserved across module imports."""
        return {name: dict(spec) for name, spec in self._module_variable_specs.items()}

    @property
    def module_node_variable_refs(self) -> dict[str, dict[str, str | None]]:
        """Refs on imported-module nodes that survived the composition merge."""
        return {name: dict(refs) for name, refs in self._module_node_variable_refs.items()}

    def _set_module_variable_specs(self, specs: dict[str, dict[str, object]]) -> None:
        self._module_variable_specs = {name: dict(spec) for name, spec in specs.items()}

    def _set_module_node_variable_refs(self, refs: dict[str, dict[str, str | None]]) -> None:
        self._module_node_variable_refs = {name: dict(entry) for name, entry in refs.items()}


class InstantiatedScenario(Scenario):
    """Scenario with all `${var}` references resolved to concrete values."""

    _instantiation_parameters: dict[str, object] = PrivateAttr(default_factory=dict)
    _instantiation_profile: str | None = PrivateAttr(default=None)
    # Snapshot of pre-instantiation `${name}` refs on `nodes.os` and
    # `infrastructure.count`, captured by `instantiate_scenario` before
    # substitution. Carries downstream so the runtime processor / planner
    # can reach each variable's `allowed_values` after the resolved values
    # have been written onto the concrete scenario.
    _node_variable_refs: dict[str, dict[str, str | None]] = PrivateAttr(default_factory=dict)

    @property
    def instantiation_parameters(self) -> dict[str, object]:
        """Concrete parameter values used during instantiation."""
        return dict(self._instantiation_parameters)

    @property
    def instantiation_profile(self) -> str | None:
        """Optional instantiation profile name."""
        return self._instantiation_profile

    @property
    def node_variable_refs(self) -> dict[str, dict[str, str | None]]:
        """Pre-instantiation `${var}` refs on `nodes.os` / `infrastructure.count`."""
        return {name: dict(refs) for name, refs in self._node_variable_refs.items()}

    def _set_instantiation_context(
        self,
        *,
        parameters: dict[str, object],
        profile: str | None,
    ) -> None:
        self._instantiation_parameters = dict(parameters)
        self._instantiation_profile = profile

    def _set_node_variable_refs(self, refs: dict[str, dict[str, str | None]]) -> None:
        self._node_variable_refs = {name: dict(entry) for name, entry in refs.items()}


class ExpandedScenario(Scenario):
    """Scenario produced by module/import expansion."""

    _module_namespaces: dict[str, str] = PrivateAttr(default_factory=dict)

    @property
    def module_namespaces(self) -> dict[str, str]:
        return dict(self._module_namespaces)

    def _set_module_namespaces(self, namespaces: dict[str, str]) -> None:
        self._module_namespaces = dict(namespaces)
