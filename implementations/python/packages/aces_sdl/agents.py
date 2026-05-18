"""Agent models — autonomous participants in the scenario.

Adapted from CybORG's Agents section. An agent has a role (from
entities), available actions, initial authenticated access (via
accounts), initial knowledge of the environment, and network
scope constraints.

The SDL specifies *what's available* to each agent, not *how*
the agent executes. Framework bindings (Gymnasium, PettingZoo)
are a deployment-layer concern.

The ``Agent`` model is the SDL-authoring surface for declarative
participant framing (ACT-601, ADR-020). Identity binds to a declared
``entities`` entry, role reuses ``entities.role``, starting conditions
combine ``starting_accounts``/``initial_knowledge``/``starting_conditions``,
authority anchors point at declared SDL elements, and operating scope
combines ``allowed_subnets`` with the broader ``operating_scope`` list.
"""

from pydantic import Field, model_validator

from ._base import SDLModel


class InitialKnowledge(SDLModel):
    """What an agent knows about the scenario at start time.

    Adapted from CybORG's INT (Initial Network Topology).
    Specifies which hosts, subnets, services, and accounts
    the agent has knowledge of before the scenario begins.
    """

    hosts: list[str] = Field(default_factory=list)
    subnets: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    accounts: list[str] = Field(default_factory=list)


class Agent(SDLModel):
    """An autonomous participant in the scenario.

    Agents reference existing scenario elements:
    - ``entity`` links to the entities section (team/role) and supplies
      identity and role per ADR-020
    - ``starting_accounts`` links to the accounts section
    - ``allowed_subnets`` links to infrastructure entries
    - ``initial_knowledge`` references nodes and infrastructure
    - ``starting_conditions`` links to the conditions section, giving the
      authoring surface a declarative hook for participant-relevant
      precondition checks (ACT-601)
    - ``authority_anchors`` links to declared SDL elements (entities,
      relationships, content, etc.) that anchor what the participant is
      allowed or expected to do in scenario meaning (ACT-601, ADR-020)
    - ``operating_scope`` links to targetable named scenario elements
      (subnets, hosts, services, content) defining where the participant
      may act or observe (ACT-601, ADR-020)
    """

    entity: str = ""
    description: str = ""
    actions: list[str] = Field(default_factory=list)
    starting_accounts: list[str] = Field(default_factory=list)
    initial_knowledge: InitialKnowledge | None = None
    allowed_subnets: list[str] = Field(default_factory=list)
    reward_calculator: str = ""
    starting_conditions: list[str] = Field(default_factory=list)
    authority_anchors: list[str] = Field(default_factory=list)
    operating_scope: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_required_entity(self) -> "Agent":
        if not self.entity:
            raise ValueError("Agent requires 'entity'")
        return self
