"""Consistency checks for the canonical tool registry."""

from __future__ import annotations

from trajgym.formatters.tool_registry import (
    AGENT_TOOLS,
    TOOL_SCHEMA_VERSION,
    get_runtime_tool_names,
    get_runtime_tools,
)


def test_tool_schema_version_is_set() -> None:
    assert isinstance(TOOL_SCHEMA_VERSION, str)
    assert len(TOOL_SCHEMA_VERSION) > 0


def test_runtime_tools_are_subset_of_agent_tools() -> None:
    all_names = {t["function"]["name"] for t in AGENT_TOOLS}
    # submit_flag is a runtime alias for flag_found
    all_names.add("submit_flag")
    runtime_names = set(get_runtime_tool_names())
    assert runtime_names.issubset(
        all_names
    ), f"Runtime tools not in AGENT_TOOLS: {runtime_names - all_names}"


def test_runtime_tool_schema_count_is_stable() -> None:
    assert len(get_runtime_tools()) == 14


def test_runtime_tool_schemas_consistent() -> None:
    tools = get_runtime_tools()
    tool_names = [tool["function"]["name"] for tool in tools]
    assert "submit_flag" in tool_names
    assert not any(name.startswith("tmux_") for name in tool_names)
