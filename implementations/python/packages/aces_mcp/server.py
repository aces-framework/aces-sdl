"""ACES SDL MCP Server — tools for understanding, authoring, and validating SDL scenarios.

Launch via:
    python -m aces_mcp
    # or
    aces mcp serve
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from aces_mcp.tools.authoring import register as register_authoring_tools
from aces_mcp.tools.inspection import register as register_inspection_tools
from aces_mcp.tools.reference import register as register_reference_tools

_INSTRUCTIONS = """\
You are connected to the ACES SDL (Scenario Description Language) server.

The SDL is a YAML-based language for specifying cyber-range scenarios — \
who (entities, accounts, agents), what (nodes, features, vulnerabilities, \
content), when (scripts, stories, events), and declarative experiment \
semantics (objectives, scoring, conditions, relationships, workflows, \
variables).

Start with `sdl_overview` to orient yourself, then use \
`sdl_section_reference` for any section you need to understand. \
Use `sdl_get_example` to see real-world annotated scenarios. \
Use `sdl_validate` to check any SDL YAML you write.\
"""


def create_server() -> FastMCP:
    """Build and return the configured MCP server instance."""
    mcp = FastMCP(
        name="aces-sdl",
        instructions=_INSTRUCTIONS,
    )
    register_reference_tools(mcp)
    register_authoring_tools(mcp)
    register_inspection_tools(mcp)
    return mcp


def main() -> None:
    """Console-script entry point for the `aces-mcp` command."""
    create_server().run()
