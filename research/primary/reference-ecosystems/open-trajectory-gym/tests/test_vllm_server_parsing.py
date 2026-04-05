"""Tests for vLLM server tool call parsing.

Validates that the /v1/chat/completions endpoint correctly parses tool calls
across all supported formats (Hermes JSON, Qwen3.5 Coder XML, GLM-4 XML)
and strips <think> blocks from content.
"""

import json
import re
import uuid

from trajgym.training.skyrl_vllm_server import _parse_tool_calls_for_chat

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# The OLD Hermes-only regex (copied from the code before the fix) to
# demonstrate that it fails on Qwen3.5 XML format.
_OLD_HERMES_PATTERN = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)


def _old_hermes_parse(text):
    """Reproduce the OLD Hermes-only parsing logic."""
    calls = []
    for m in _OLD_HERMES_PATTERN.finditer(text):
        try:
            tc = json.loads(m.group(1))
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": tc.get("name", ""),
                        "arguments": json.dumps(tc.get("arguments", {})),
                    },
                }
            )
        except json.JSONDecodeError:
            pass
    return calls


def _strip_think(text):
    """Strip <think> blocks the same way the server does."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ---------------------------------------------------------------------------
# Test 1: Reproduce failure -- Qwen3.5 XML not parsed by old regex
# ---------------------------------------------------------------------------


class TestReproduceQwen35Failure:
    """Prove the bug: old Hermes-only regex cannot parse Qwen3.5 Coder XML."""

    def test_old_regex_fails_on_qwen35_xml(self):
        text = (
            "<tool_call><function=shell_command>"
            "<parameter=command>ls</parameter>"
            "</function></tool_call>"
        )
        old_result = _old_hermes_parse(text)
        assert len(old_result) == 0, (
            "OLD Hermes-only regex should produce 0 tool_calls for Qwen3.5 XML "
            f"but got {len(old_result)}"
        )


# ---------------------------------------------------------------------------
# Test 2: Hermes JSON still works
# ---------------------------------------------------------------------------


class TestHermesJsonParsing:
    """Hermes/Qwen3 JSON format must still be parsed correctly."""

    def test_hermes_json_parsed(self):
        text = '<tool_call>{"name": "shell_command", "arguments": {"command": "ls"}}</tool_call>'
        content = _strip_think(text)
        result = _parse_tool_calls_for_chat(text, content, "auto", uuid)
        assert len(result) == 1
        tc = result[0]
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "shell_command"
        args = json.loads(tc["function"]["arguments"])
        assert args["command"] == "ls"
        assert tc["id"].startswith("call_")

    def test_hermes_mode_explicit(self):
        text = '<tool_call>{"name": "shell_command", "arguments": {"command": "whoami"}}</tool_call>'
        content = _strip_think(text)
        result = _parse_tool_calls_for_chat(text, content, "hermes", uuid)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "shell_command"
        args = json.loads(result[0]["function"]["arguments"])
        assert args["command"] == "whoami"


# ---------------------------------------------------------------------------
# Test 3: Qwen3.5 XML now works
# ---------------------------------------------------------------------------


class TestQwen35CoderXml:
    """Qwen3.5 Coder XML format must be parsed correctly."""

    def test_qwen35_xml_parsed_auto(self):
        text = (
            "<tool_call><function=shell_command>"
            "<parameter=command>ls</parameter>"
            "</function></tool_call>"
        )
        content = _strip_think(text)
        result = _parse_tool_calls_for_chat(text, content, "auto", uuid)
        assert len(result) == 1
        tc = result[0]
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "shell_command"
        args = json.loads(tc["function"]["arguments"])
        assert args["command"] == "ls"

    def test_qwen35_xml_parsed_explicit_mode(self):
        text = (
            "<tool_call><function=read_file>"
            "<parameter=file_path>/etc/passwd</parameter>"
            "</function></tool_call>"
        )
        content = _strip_think(text)
        result = _parse_tool_calls_for_chat(text, content, "qwen3_coder", uuid)
        assert len(result) == 1
        tc = result[0]
        assert tc["function"]["name"] == "read_file"
        args = json.loads(tc["function"]["arguments"])
        assert args["file_path"] == "/etc/passwd"

    def test_qwen35_xml_multiple_params(self):
        text = (
            "<tool_call><function=shell_command>"
            "<parameter=command>cat /etc/hosts</parameter>"
            "<parameter=timeout>30</parameter>"
            "</function></tool_call>"
        )
        content = _strip_think(text)
        result = _parse_tool_calls_for_chat(text, content, "auto", uuid)
        assert len(result) == 1
        args = json.loads(result[0]["function"]["arguments"])
        assert args["command"] == "cat /etc/hosts"
        assert args["timeout"] == 30 or args["timeout"] == "30"


# ---------------------------------------------------------------------------
# Test 4: GLM-4 XML works
# ---------------------------------------------------------------------------


class TestGlm4Xml:
    """GLM-4 MoE XML format must be parsed."""

    def test_glm4_xml_parsed(self):
        text = (
            "<tool_call>shell_command"
            "<arg_key>command</arg_key><arg_value>ls</arg_value>"
            "</tool_call>"
        )
        content = _strip_think(text)
        result = _parse_tool_calls_for_chat(text, content, "auto", uuid)
        assert len(result) == 1
        tc = result[0]
        assert tc["function"]["name"] == "shell_command"
        args = json.loads(tc["function"]["arguments"])
        assert args["command"] == "ls"


# ---------------------------------------------------------------------------
# Test 5: Mixed <think> + tool calls
# ---------------------------------------------------------------------------


class TestThinkBlockStripping:
    """<think> blocks must be stripped from content, tool calls still parsed."""

    def test_think_stripped_tool_calls_preserved(self):
        text = (
            "<think>I should check the filesystem</think>"
            '<tool_call>{"name": "shell_command", "arguments": {"command": "ls"}}</tool_call>'
        )
        content = _strip_think(text)

        # Verify <think> is gone from content
        assert "<think>" not in content

        # Tool call still parsed
        result = _parse_tool_calls_for_chat(text, content, "auto", uuid)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "shell_command"

    def test_think_with_qwen35_xml(self):
        text = (
            "<think>Let me enumerate the target</think>"
            "<tool_call><function=shell_command>"
            "<parameter=command>nmap -sV 10.0.0.1</parameter>"
            "</function></tool_call>"
        )
        content = _strip_think(text)
        assert "<think>" not in content

        result = _parse_tool_calls_for_chat(text, content, "auto", uuid)
        assert len(result) == 1
        args = json.loads(result[0]["function"]["arguments"])
        assert "nmap" in args["command"]

    def test_multiline_think_stripped(self):
        text = (
            "<think>\nI need to:\n1. Read the source\n2. Find the vuln\n</think>\n"
            '<tool_call>{"name": "read_file", "arguments": {"file_path": "/app/server.py"}}</tool_call>'
        )
        content = _strip_think(text)
        assert "<think>" not in content
        assert "I need to" not in content

        result = _parse_tool_calls_for_chat(text, content, "auto", uuid)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "read_file"


# ---------------------------------------------------------------------------
# Test 6: No tool calls (plain text)
# ---------------------------------------------------------------------------


class TestNoToolCalls:
    """Plain text with no tool calls must return empty list, content preserved."""

    def test_plain_text_no_tool_calls(self):
        text = "I don't know how to solve this"
        content = _strip_think(text)
        result = _parse_tool_calls_for_chat(text, content, "auto", uuid)
        assert len(result) == 0

    def test_none_mode_always_empty(self):
        text = '<tool_call>{"name": "shell_command", "arguments": {"command": "ls"}}</tool_call>'
        content = _strip_think(text)
        result = _parse_tool_calls_for_chat(text, content, "none", uuid)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Test 7: Multiple tool calls
# ---------------------------------------------------------------------------


class TestMultipleToolCalls:
    """Multiple tool calls in one response must all be parsed."""

    def test_two_hermes_calls(self):
        text = (
            '<tool_call>{"name": "shell_command", "arguments": {"command": "id"}}</tool_call>\n'
            '<tool_call>{"name": "shell_command", "arguments": {"command": "whoami"}}</tool_call>'
        )
        content = _strip_think(text)
        result = _parse_tool_calls_for_chat(text, content, "auto", uuid)
        assert len(result) == 2
        names = {tc["function"]["name"] for tc in result}
        assert names == {"shell_command"}
        cmds = {json.loads(tc["function"]["arguments"])["command"] for tc in result}
        assert cmds == {"id", "whoami"}

    def test_two_qwen35_calls(self):
        text = (
            "<tool_call><function=shell_command>"
            "<parameter=command>id</parameter>"
            "</function></tool_call>\n"
            "<tool_call><function=read_file>"
            "<parameter=file_path>/etc/shadow</parameter>"
            "</function></tool_call>"
        )
        content = _strip_think(text)
        result = _parse_tool_calls_for_chat(text, content, "auto", uuid)
        assert len(result) == 2
        names = {tc["function"]["name"] for tc in result}
        assert names == {"shell_command", "read_file"}

    def test_unique_ids_per_call(self):
        text = (
            '<tool_call>{"name": "shell_command", "arguments": {"command": "ls"}}</tool_call>\n'
            '<tool_call>{"name": "shell_command", "arguments": {"command": "pwd"}}</tool_call>'
        )
        content = _strip_think(text)
        result = _parse_tool_calls_for_chat(text, content, "auto", uuid)
        assert len(result) == 2
        ids = [tc["id"] for tc in result]
        assert ids[0] != ids[1], "Each tool call must have a unique ID"


# ---------------------------------------------------------------------------
# Test: OpenAI response format validation
# ---------------------------------------------------------------------------


class TestOpenAIFormat:
    """Verify tool_calls match OpenAI's expected schema."""

    def test_openai_format_fields(self):
        text = '<tool_call>{"name": "shell_command", "arguments": {"command": "ls"}}</tool_call>'
        content = _strip_think(text)
        result = _parse_tool_calls_for_chat(text, content, "auto", uuid)
        assert len(result) == 1
        tc = result[0]
        # Required fields
        assert "id" in tc
        assert tc["type"] == "function"
        assert "function" in tc
        assert "name" in tc["function"]
        assert "arguments" in tc["function"]
        # arguments must be a JSON string, not a dict
        assert isinstance(tc["function"]["arguments"], str)
        # Must be valid JSON
        parsed_args = json.loads(tc["function"]["arguments"])
        assert isinstance(parsed_args, dict)
