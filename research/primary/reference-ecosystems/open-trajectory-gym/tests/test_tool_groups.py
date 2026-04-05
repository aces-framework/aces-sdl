"""Smoke tests for canonical tool registry schemas.

Validates:
- All tools have required fields (name, description, parameters)
- Tool schemas are valid OpenAI function format
- Runtime tools are a subset of full registry
"""

from trajgym.formatters.tool_registry import (
    AGENT_TOOLS,
    get_runtime_tool_names,
    get_runtime_tools,
)

# ---------------------------------------------------------------------------
# Tool count and basic structure
# ---------------------------------------------------------------------------


class TestToolGroupBasics:
    def test_tools_defined(self):
        assert len(AGENT_TOOLS) == 13  # full registry (no tmux)
        assert len(get_runtime_tools()) == 14  # runtime tools (incl submit_flag alias)

    def test_all_are_dicts(self):
        for tool in AGENT_TOOLS:
            assert isinstance(tool, dict)

    def test_all_have_type_function(self):
        for tool in AGENT_TOOLS:
            assert tool["type"] == "function", f"Tool missing type=function: {tool}"

    def test_all_have_function_key(self):
        for tool in AGENT_TOOLS:
            assert "function" in tool


# ---------------------------------------------------------------------------
# OpenAI function schema compliance
# ---------------------------------------------------------------------------


class TestToolSchemaCompliance:
    def test_all_have_name(self):
        for tool in AGENT_TOOLS:
            fn = tool["function"]
            assert "name" in fn, f"Tool missing name: {fn}"
            assert isinstance(fn["name"], str)
            assert len(fn["name"]) > 0

    def test_all_have_description(self):
        for tool in AGENT_TOOLS:
            fn = tool["function"]
            assert (
                "description" in fn
            ), f"Tool {fn.get('name', '?')} missing description"
            assert isinstance(fn["description"], str)
            assert len(fn["description"]) > 0

    def test_all_have_parameters(self):
        for tool in AGENT_TOOLS:
            fn = tool["function"]
            assert "parameters" in fn, f"Tool {fn['name']} missing parameters"

    def test_parameters_type_is_object(self):
        for tool in AGENT_TOOLS:
            params = tool["function"]["parameters"]
            assert (
                params["type"] == "object"
            ), f"Tool {tool['function']['name']} parameters.type != object"

    def test_parameters_have_properties(self):
        for tool in AGENT_TOOLS:
            params = tool["function"]["parameters"]
            assert (
                "properties" in params
            ), f"Tool {tool['function']['name']} missing parameters.properties"

    def test_parameters_have_required(self):
        for tool in AGENT_TOOLS:
            params = tool["function"]["parameters"]
            assert (
                "required" in params
            ), f"Tool {tool['function']['name']} missing parameters.required"
            assert isinstance(params["required"], list)

    def test_required_fields_exist_in_properties(self):
        """Every required field should be listed in properties."""
        for tool in AGENT_TOOLS:
            fn = tool["function"]
            params = fn["parameters"]
            props = set(params["properties"].keys())
            for req in params["required"]:
                assert (
                    req in props
                ), f"Tool {fn['name']}: required field '{req}' not in properties"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    def test_get_runtime_tools_returns_list(self):
        result = get_runtime_tools()
        assert isinstance(result, list)
        assert len(result) == 14

    def test_runtime_tools_subset_of_full_registry(self):
        all_names = {t["function"]["name"] for t in AGENT_TOOLS}
        # submit_flag is a runtime alias for flag_found
        all_names.add("submit_flag")
        runtime_names = {t["function"]["name"] for t in get_runtime_tools()}
        assert runtime_names.issubset(all_names)

    def test_get_runtime_tool_names_returns_list(self):
        result = get_runtime_tool_names()
        assert isinstance(result, list)
        assert len(result) == 14

    def test_get_runtime_tool_names_all_strings(self):
        for name in get_runtime_tool_names():
            assert isinstance(name, str)
