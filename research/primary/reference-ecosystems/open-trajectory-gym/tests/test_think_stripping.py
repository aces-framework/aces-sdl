"""Tests for <think> block stripping in TrajGymTextEnv.

Validates that <think>...</think> reasoning blocks are stripped from
LLM output before tool-call parsing, preventing the parser from
picking up tool references inside the model's chain-of-thought.
"""

import re

from trajgym.parsing import parse_tool_calls

# The same pattern used in trajgym_env.py — imported here so we test
# the exact regex behavior, not just the env integration.
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think(text: str) -> str:
    """Simulate the stripping logic from TrajGymTextEnv.step()."""
    return _THINK_PATTERN.sub("", text).strip()


class TestThinkBlockStripping:
    """Test 1: Think blocks stripped before parsing."""

    def test_think_then_tool_call(self):
        action = (
            "<think>Let me analyze this</think>"
            "<tool_call>\n"
            '{"name": "shell_command", "arguments": {"command": "ls"}}\n'
            "</tool_call>"
        )
        stripped = _strip_think(action)
        calls = parse_tool_calls(stripped)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
        assert calls[0]["arguments"]["command"] == "ls"


class TestThinkBlockWithToolReference:
    """Test 2: Think blocks containing tool references (should be stripped)."""

    def test_only_real_tool_call_parsed(self):
        action = (
            '<think>I\'ll try shell_command("ls")</think>'
            "<tool_call>\n"
            '{"name": "read_file", "arguments": {"file_path": "/etc/passwd"}}\n'
            "</tool_call>"
        )
        stripped = _strip_think(action)
        calls = parse_tool_calls(stripped)
        assert len(calls) == 1
        assert calls[0]["name"] == "read_file"
        assert calls[0]["arguments"]["file_path"] == "/etc/passwd"


class TestNoThinkBlocks:
    """Test 3: No think blocks (passthrough)."""

    def test_passthrough(self):
        action = (
            "<tool_call>\n"
            '{"name": "shell_command", "arguments": {"command": "ls"}}\n'
            "</tool_call>"
        )
        stripped = _strip_think(action)
        calls = parse_tool_calls(stripped)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
        # Stripping should not modify the text beyond whitespace
        assert "<tool_call>" in stripped


class TestThinkBlockOnly:
    """Test 4: Think block only (no tool call)."""

    def test_think_only_yields_no_tool_calls(self):
        action = "<think>I'm stuck, let me think more...</think>"
        stripped = _strip_think(action)
        calls = parse_tool_calls(stripped)
        assert len(calls) == 0
        assert stripped == ""


class TestMultipleThinkBlocks:
    """Test 5: Multiple think blocks with a tool call between them."""

    def test_two_think_blocks_one_tool_call(self):
        action = (
            "<think>First, let me enumerate the target.</think>\n"
            "<tool_call>\n"
            '{"name": "shell_command", "arguments": {"command": "nmap -sV target"}}\n'
            "</tool_call>\n"
            "<think>After that I should check the results.</think>"
        )
        stripped = _strip_think(action)
        calls = parse_tool_calls(stripped)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
        assert calls[0]["arguments"]["command"] == "nmap -sV target"


class TestMultilineThinkBlock:
    """Think blocks can span multiple lines."""

    def test_multiline_think_stripped(self):
        action = (
            "<think>\n"
            "Let me analyze this step by step.\n"
            "1. First I need to find the web server\n"
            "2. Then enumerate endpoints\n"
            "3. Look for SSTI vulnerabilities\n"
            "</think>\n"
            "<tool_call>\n"
            '{"name": "shell_command", "arguments": {"command": "curl http://target/"}}\n'
            "</tool_call>"
        )
        stripped = _strip_think(action)
        calls = parse_tool_calls(stripped)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
        # The multiline think block should be fully removed
        assert "<think>" not in stripped
        assert "</think>" not in stripped


class TestStripThinkDisabled:
    """When strip_think is False, action passes through unchanged."""

    def test_no_stripping_when_disabled(self):
        action = (
            "<think>Some reasoning</think>"
            "<tool_call>\n"
            '{"name": "shell_command", "arguments": {"command": "ls"}}\n'
            "</tool_call>"
        )
        # Simulate strip_think=False path: no stripping
        calls = parse_tool_calls(action)
        # parse_tool_calls should still find the tool call even with
        # think blocks present (the tags don't break the regex)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
