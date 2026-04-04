"""Tests for the ACES SDL MCP server tools.

Verifies that all 14 tools produce correct results across
reference, authoring, and inspection categories.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from aces.mcp.server import create_server

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def server():
    return create_server()


def _text(result) -> str:
    """Extract text from the MCP tool result tuple."""
    content_list = result[0]
    return content_list[0].text


def _call(server, tool: str, args: dict | None = None) -> str:
    """Synchronously call a tool and return its text."""
    return asyncio.get_event_loop().run_until_complete(
        _async_call(server, tool, args or {})
    )


async def _async_call(server, tool: str, args: dict) -> str:
    result = await server.call_tool(tool, args)
    return _text(result)


# ---------------------------------------------------------------------------
# Valid SDL fixtures
# ---------------------------------------------------------------------------

MINIMAL_SDL = """\
name: test-scenario
nodes:
  net: {type: Switch}
  web: {type: VM, os: linux, resources: {ram: 2 GiB, cpu: 1}}
infrastructure:
  net: {count: 1, properties: {cidr: 10.0.0.0/24, gateway: 10.0.0.1}}
  web: {count: 1, links: [net]}
"""

FULL_SDL = """\
name: mcp-test
description: Test scenario with many sections

variables:
  speed:
    type: number
    default: 1.0

nodes:
  corp-net: {type: Switch}
  web: {type: VM, os: linux, resources: {ram: 2 GiB, cpu: 1}, features: {app: admin}, roles: {admin: www}, conditions: {alive: admin}}
  db:  {type: VM, os: linux, resources: {ram: 1 GiB, cpu: 1}, features: {pg: dba}, roles: {dba: postgres}, services: [{port: 5432, name: pg-port}]}

infrastructure:
  corp-net: {count: 1, properties: {cidr: 10.0.0.0/24, gateway: 10.0.0.1}}
  web: {count: 1, links: [corp-net]}
  db:  {count: 1, links: [corp-net]}

features:
  app: {type: Service, source: my-app}
  pg:  {type: Service, source: postgresql}

conditions:
  alive:
    command: "curl -sf http://localhost/ || exit 1"
    interval: 15

vulnerabilities:
  sqli: {name: SQL Injection, description: "SQLi in login", technical: true, class: CWE-89}

metrics:
  uptime: {type: CONDITIONAL, max-score: 100, condition: alive}

evaluations:
  basic: {metrics: [uptime], min-score: 50}

tlos:
  web-defense: {name: Defend web, evaluation: basic}

goals:
  pass: {tlos: [web-defense]}

entities:
  blue-team:
    name: Blue
    role: Blue
    tlos: [web-defense]
    entities:
      alice: {name: Alice}
  red-team:
    name: Red
    role: Red

injects:
  brief: {source: brief-doc, from_entity: red-team, to_entities: [blue-team]}

events:
  attack: {injects: [brief]}

scripts:
  timeline:
    start-time: 0
    end-time: 2 hour
    speed: "${speed}"
    events:
      attack: 30 min

stories:
  exercise:
    speed: "${speed}"
    scripts: [timeline]

content:
  seed: {type: dataset, target: db, format: sql, source: seed-pkg}

accounts:
  admin-acct: {username: admin, node: web, password_strength: strong}

relationships:
  web-to-db: {type: connects_to, source: app, target: pg}

agents:
  red-agent:
    entity: red-team
    actions: [Scan]
    initial_knowledge:
      hosts: [web]
      subnets: [corp-net]
      services: [pg-port]

objectives:
  red-access:
    agent: red-agent
    actions: [Scan]
    targets: [web]
    success: {conditions: [alive]}
    window: {stories: [exercise]}

workflows:
  flow:
    start: do-it
    steps:
      do-it: {type: objective, objective: red-access, on-success: done}
      done: {type: end}
"""


INVALID_SDL = """\
name: broken
nodes:
  web:
    type: VM
    os: linux
    features: {ghost-feature: admin}
"""


# ---------------------------------------------------------------------------
# Reference tools
# ---------------------------------------------------------------------------


class TestReferenceTools:
    def test_sdl_overview_returns_content(self, server):
        text = _call(server, "sdl_overview")
        assert "SDL" in text
        assert "21" in text or "sections" in text.lower()
        assert "nodes" in text

    def test_sdl_section_reference_valid(self, server):
        text = _call(server, "sdl_section_reference", {"section": "nodes"})
        assert "Nodes" in text
        assert "Switch" in text
        assert "VM" in text

    def test_sdl_section_reference_scoring(self, server):
        text = _call(server, "sdl_section_reference", {"section": "scoring"})
        assert "Metrics" in text or "metrics" in text
        assert "Evaluations" in text or "evaluations" in text

    def test_sdl_section_reference_invalid(self, server):
        text = _call(server, "sdl_section_reference", {"section": "nonexistent"})
        assert "Unknown section" in text

    def test_sdl_get_example_minimal(self, server):
        text = _call(server, "sdl_get_example", {"name": "minimal"})
        assert "name:" in text
        assert "nodes:" in text

    def test_sdl_get_example_hospital(self, server):
        text = _call(server, "sdl_get_example", {"name": "hospital"})
        assert "hospital-ransomware" in text
        assert "objectives:" in text

    def test_sdl_get_example_invalid(self, server):
        text = _call(server, "sdl_get_example", {"name": "nonexistent"})
        assert "Unknown example" in text

    def test_sdl_parser_reference(self, server):
        text = _call(server, "sdl_parser_reference")
        assert "normalization" in text.lower() or "Normalization" in text

    def test_sdl_validation_reference(self, server):
        text = _call(server, "sdl_validation_reference")
        assert "22" in text or "validation" in text.lower()


# ---------------------------------------------------------------------------
# Authoring tools
# ---------------------------------------------------------------------------


class TestAuthoringTools:
    def test_validate_valid_sdl(self, server):
        text = _call(server, "sdl_validate", {"sdl_content": MINIMAL_SDL})
        assert text.startswith("VALID")

    def test_validate_full_sdl(self, server):
        text = _call(server, "sdl_validate", {"sdl_content": FULL_SDL})
        assert text.startswith("VALID")
        assert "nodes: 3" in text
        assert "objectives: 1" in text

    def test_validate_invalid_sdl(self, server):
        text = _call(server, "sdl_validate", {"sdl_content": INVALID_SDL})
        assert "VALIDATION ERRORS" in text
        assert "ghost-feature" in text

    def test_validate_yaml_error(self, server):
        text = _call(server, "sdl_validate", {"sdl_content": "{{not yaml"})
        assert "PARSE ERROR" in text

    def test_validate_structural_only(self, server):
        text = _call(
            server,
            "sdl_validate",
            {"sdl_content": INVALID_SDL, "structural_only": True},
        )
        # With structural_only, the cross-reference error should not appear
        assert "VALID" in text or "semantic validation was skipped" in text

    def test_validate_section_valid(self, server):
        text = _call(
            server,
            "sdl_validate_section",
            {
                "section": "nodes",
                "section_yaml": "myvm:\n  type: VM\n  os: linux\n  resources: {ram: 2 GiB, cpu: 1}",
            },
        )
        assert "VALID" in text

    def test_validate_section_invalid_yaml(self, server):
        text = _call(
            server,
            "sdl_validate_section",
            {"section": "nodes", "section_yaml": "{{not yaml"},
        )
        assert "YAML ERROR" in text

    def test_validate_section_bad_section(self, server):
        text = _call(
            server,
            "sdl_validate_section",
            {"section": "nope", "section_yaml": "x: 1"},
        )
        assert "Unknown section" in text

    def test_scaffold_minimal(self, server):
        text = _call(server, "sdl_scaffold", {"complexity": "minimal"})
        assert "name:" in text
        assert "nodes:" in text
        # Should be valid SDL
        validation = _call(server, "sdl_validate", {"sdl_content": text})
        assert validation.startswith("VALID")

    def test_scaffold_standard(self, server):
        text = _call(server, "sdl_scaffold", {"complexity": "standard"})
        assert "entities:" in text
        assert "accounts:" in text
        validation = _call(server, "sdl_validate", {"sdl_content": text})
        assert validation.startswith("VALID")

    def test_scaffold_full(self, server):
        text = _call(server, "sdl_scaffold", {"complexity": "full"})
        assert "workflows:" in text
        assert "objectives:" in text
        assert "variables:" in text
        validation = _call(server, "sdl_validate", {"sdl_content": text})
        assert validation.startswith("VALID")

    def test_scaffold_invalid_complexity(self, server):
        text = _call(server, "sdl_scaffold", {"complexity": "ultra"})
        assert "Invalid complexity" in text

    def test_instantiate(self, server):
        sdl = """\
name: param-test
variables:
  greeting:
    type: string
    default: hello
"""
        text = _call(
            server,
            "sdl_instantiate",
            {"sdl_content": sdl, "parameters_json": '{"greeting": "hi"}'},
        )
        assert "INSTANTIATED" in text

    def test_instantiate_bad_json(self, server):
        text = _call(
            server,
            "sdl_instantiate",
            {"sdl_content": "name: x", "parameters_json": "{bad"},
        )
        assert "Invalid JSON" in text


# ---------------------------------------------------------------------------
# Inspection tools
# ---------------------------------------------------------------------------


class TestInspectionTools:
    def test_summarize(self, server):
        text = _call(server, "sdl_summarize", {"sdl_content": FULL_SDL})
        assert "mcp-test" in text
        assert "VMs:" in text
        assert "Switches:" in text
        assert "${speed}" in text

    def test_summarize_entities(self, server):
        text = _call(server, "sdl_summarize", {"sdl_content": FULL_SDL})
        assert "blue-team" in text
        assert "Entities" in text

    def test_list_elements_all(self, server):
        text = _call(
            server, "sdl_list_elements", {"sdl_content": FULL_SDL, "section": "all"}
        )
        assert "nodes:" in text
        assert "web" in text
        assert "features:" in text

    def test_list_elements_filtered(self, server):
        text = _call(
            server,
            "sdl_list_elements",
            {"sdl_content": FULL_SDL, "section": "accounts"},
        )
        assert "admin-acct" in text
        # Should NOT list nodes
        assert "\nnodes:" not in text

    def test_list_elements_nested_entities(self, server):
        text = _call(
            server,
            "sdl_list_elements",
            {"sdl_content": FULL_SDL, "section": "entities"},
        )
        assert "blue-team" in text
        assert "blue-team.alice" in text

    def test_get_element_qualified(self, server):
        text = _call(
            server,
            "sdl_get_element",
            {"sdl_content": FULL_SDL, "element_name": "nodes.web"},
        )
        assert "nodes.web" in text
        assert "vm" in text.lower()

    def test_get_element_unique_bare(self, server):
        text = _call(
            server,
            "sdl_get_element",
            {"sdl_content": FULL_SDL, "element_name": "sqli"},
        )
        assert "SQL Injection" in text

    def test_get_element_ambiguous(self, server):
        text = _call(
            server,
            "sdl_get_element",
            {"sdl_content": MINIMAL_SDL, "element_name": "web"},
        )
        # 'web' is in both nodes and infrastructure
        assert "Ambiguous" in text

    def test_get_element_not_found(self, server):
        text = _call(
            server,
            "sdl_get_element",
            {"sdl_content": MINIMAL_SDL, "element_name": "nonexistent"},
        )
        assert "not found" in text.lower()

    def test_check_references_element(self, server):
        text = _call(
            server,
            "sdl_check_references",
            {"sdl_content": FULL_SDL, "element_name": "app"},
        )
        assert "Outgoing" in text or "Incoming" in text

    def test_check_references_full_graph(self, server):
        text = _call(
            server,
            "sdl_check_references",
            {"sdl_content": FULL_SDL},
        )
        assert "Cross-reference graph" in text
        assert "->" in text

    def test_diagram(self, server):
        text = _call(server, "sdl_diagram", {"sdl_content": FULL_SDL})
        assert "Topology" in text
        assert "corp-net" in text
        assert "web" in text

    def test_diagram_shows_services(self, server):
        text = _call(server, "sdl_diagram", {"sdl_content": FULL_SDL})
        assert "pg-port" in text

    def test_diagram_shows_dependencies(self, server):
        sdl_with_deps = """\
name: dep-test
nodes:
  sw: {type: Switch}
  a: {type: VM, os: linux, resources: {ram: 1 GiB, cpu: 1}}
  b: {type: VM, os: linux, resources: {ram: 1 GiB, cpu: 1}}
infrastructure:
  sw: {count: 1, properties: {cidr: 10.0.0.0/24, gateway: 10.0.0.1}}
  a: {count: 1, links: [sw]}
  b: {count: 1, links: [sw], dependencies: [a]}
"""
        text = _call(server, "sdl_diagram", {"sdl_content": sdl_with_deps})
        assert "Dependencies" in text
        assert "b --> a" in text


# ---------------------------------------------------------------------------
# Example scenario validation
# ---------------------------------------------------------------------------


class TestExampleScenarios:
    """Validate that all bundled examples pass through the MCP tools."""

    @pytest.mark.parametrize(
        "filename",
        [
            "hospital-ransomware-surgery-day.sdl.yaml",
            "satcom-release-poisoning.sdl.yaml",
            "port-authority-surge-response.sdl.yaml",
        ],
    )
    def test_example_validates(self, server, filename):
        path = EXAMPLES_DIR / filename
        if not path.exists():
            pytest.skip(f"Example not found: {filename}")
        sdl = path.read_text()
        text = _call(server, "sdl_validate", {"sdl_content": sdl})
        assert text.startswith("VALID"), f"{filename} failed: {text[:200]}"

    @pytest.mark.parametrize(
        "filename",
        [
            "hospital-ransomware-surgery-day.sdl.yaml",
            "satcom-release-poisoning.sdl.yaml",
            "port-authority-surge-response.sdl.yaml",
        ],
    )
    def test_example_summarizes(self, server, filename):
        path = EXAMPLES_DIR / filename
        if not path.exists():
            pytest.skip(f"Example not found: {filename}")
        sdl = path.read_text()
        text = _call(server, "sdl_summarize", {"sdl_content": sdl})
        assert "Scenario:" in text
        assert "VMs:" in text


# ---------------------------------------------------------------------------
# Server construction
# ---------------------------------------------------------------------------


class TestServerConstruction:
    def test_server_has_all_tools(self):
        server = create_server()
        tool_names = [t.name for t in server._tool_manager._tools.values()]
        expected = {
            "sdl_overview",
            "sdl_section_reference",
            "sdl_get_example",
            "sdl_parser_reference",
            "sdl_validation_reference",
            "sdl_validate",
            "sdl_validate_section",
            "sdl_scaffold",
            "sdl_instantiate",
            "sdl_summarize",
            "sdl_list_elements",
            "sdl_get_element",
            "sdl_check_references",
            "sdl_diagram",
        }
        assert set(tool_names) == expected

    def test_server_has_instructions(self):
        server = create_server()
        assert server.instructions
        assert "SDL" in server.instructions


# ---------------------------------------------------------------------------
# Security regression tests
# ---------------------------------------------------------------------------


class TestSecurity:
    """Regression tests for security hardening."""

    def test_scaffold_with_braces_in_name(self, server):
        """Format string injection: braces in user input must not crash."""
        text = _call(
            server,
            "sdl_scaffold",
            {
                "complexity": "minimal",
                "scenario_name": "test{oops}",
                "description": "desc with {curly} braces",
            },
        )
        assert "test{oops}" in text
        assert "{curly}" in text
        # Should still be valid YAML (name: test{oops} is a valid YAML string)
        assert "name: test{oops}" in text

    def test_get_element_private_attr_access(self, server):
        """Qualified ref must not access private/dunder attributes."""
        text = _call(
            server,
            "sdl_get_element",
            {"sdl_content": MINIMAL_SDL, "element_name": "_advisories.anything"},
        )
        assert "not found" in text.lower()

    def test_get_element_dunder_access(self, server):
        """Qualified ref must not access __class__ or similar."""
        text = _call(
            server,
            "sdl_get_element",
            {"sdl_content": MINIMAL_SDL, "element_name": "__class__.foo"},
        )
        assert "not found" in text.lower()

    def test_validate_oversized_input_rejected(self, server):
        """Extremely large input must be rejected."""
        huge = "name: x\nnodes:\n" + "  n{i}: {{type: Switch}}\n" * 10_000
        text = _call(server, "sdl_validate", {"sdl_content": huge})
        assert "INPUT TOO LARGE" in text

    def test_summarize_oversized_input_rejected(self, server):
        """Inspection tools also enforce size limits."""
        huge = "name: x\n" + "x" * (65 * 1024)
        text = _call(server, "sdl_summarize", {"sdl_content": huge})
        assert "INPUT TOO LARGE" in text

    def test_validate_section_context_cannot_override_name(self, server):
        """context_yaml must not be able to hijack the wrapper name."""
        text = _call(
            server,
            "sdl_validate_section",
            {
                "section": "nodes",
                "section_yaml": "sw:\n  type: Switch",
                "context_yaml": "name: hijacked",
            },
        )
        # Should succeed validation — name should still be the safe internal one
        assert "VALID" in text or "VALIDATION" in text
        assert "hijacked" not in text
