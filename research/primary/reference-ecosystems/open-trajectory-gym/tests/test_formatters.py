"""Smoke tests for model-specific message formatters.

Validates:
- Qwen3Formatter produces Hermes/ChatML format with <tool_call> tags
- GLM4Formatter produces <|observation|> role for tool results
- DevstralFormatter produces [TOOL_CALLS] and [TOOL_RESULTS] blocks
- ModelFormatter.from_model_id() auto-detects model families correctly
- Tool definitions are returned in correct format
"""

import json

import pytest
from trajgym.formatters.base import ModelFormatter
from trajgym.formatters.devstral import DevstralFormatter
from trajgym.formatters.glm4 import GLM4Formatter
from trajgym.formatters.qwen3 import Qwen3Formatter
from trajgym.formatters.tool_registry import (
    AGENT_TOOLS,
    get_tool_by_name,
    get_tools_by_names,
)

# ---------------------------------------------------------------------------
# Shared test messages
# ---------------------------------------------------------------------------


SAMPLE_MESSAGES = [
    {"role": "system", "content": "You are a CTF agent."},
    {"role": "user", "content": "Scan the target."},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "function": {
                    "name": "shell_command",
                    "arguments": {"command": "nmap 10.0.0.1"},
                },
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "call_1",
        "name": "shell_command",
        "content": "80/tcp open http",
    },
    {"role": "assistant", "content": "Port 80 is open."},
]


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


class TestAutoDetection:
    def test_qwen3_detected(self):
        f = ModelFormatter.from_model_id("Qwen/Qwen3-8B")
        assert isinstance(f, Qwen3Formatter)

    def test_openthinker_uses_qwen3(self):
        f = ModelFormatter.from_model_id("open-thoughts/OpenThinker-Agent-v1")
        assert isinstance(f, Qwen3Formatter)

    def test_nanbeige_uses_qwen3(self):
        f = ModelFormatter.from_model_id("Nanbeige/Nanbeige4.1-3B")
        assert isinstance(f, Qwen3Formatter)

    def test_glm4_detected(self):
        f = ModelFormatter.from_model_id("THUDM/glm-4-9b")
        assert isinstance(f, GLM4Formatter)

    def test_glm47_flash_detected(self):
        f = ModelFormatter.from_model_id("THUDM/GLM-4.7-Flash")
        assert isinstance(f, GLM4Formatter)

    def test_devstral_detected(self):
        f = ModelFormatter.from_model_id("mistralai/Devstral-Small-2")
        assert isinstance(f, DevstralFormatter)

    def test_mistral_detected(self):
        f = ModelFormatter.from_model_id("mistralai/Mistral-7B-v0.1")
        assert isinstance(f, DevstralFormatter)

    def test_unknown_model_defaults_to_qwen3(self):
        f = ModelFormatter.from_model_id("some/unknown-model")
        assert isinstance(f, Qwen3Formatter)


# ---------------------------------------------------------------------------
# Qwen3Formatter (Hermes / ChatML)
# ---------------------------------------------------------------------------


class TestQwen3Formatter:
    @pytest.fixture
    def formatter(self):
        return Qwen3Formatter()

    def test_format_produces_chatml_markers(self, formatter):
        text = formatter.format_messages(SAMPLE_MESSAGES)
        assert "<|im_start|>" in text
        assert "<|im_end|>" in text

    def test_format_includes_tool_call_tags(self, formatter):
        text = formatter.format_messages(SAMPLE_MESSAGES)
        assert "<tool_call>" in text
        assert "</tool_call>" in text

    def test_format_tool_role(self, formatter):
        text = formatter.format_messages(SAMPLE_MESSAGES)
        assert "<|im_start|>tool" in text

    def test_format_system_role(self, formatter):
        text = formatter.format_messages(SAMPLE_MESSAGES)
        assert "<|im_start|>system" in text

    def test_tool_call_json_valid(self, formatter):
        text = formatter.format_messages(SAMPLE_MESSAGES)
        # Extract JSON between <tool_call> and </tool_call>
        import re

        matches = re.findall(r"<tool_call>\n(.*?)\n</tool_call>", text, re.DOTALL)
        assert len(matches) >= 1
        for m in matches:
            parsed = json.loads(m)
            assert "name" in parsed
            assert "arguments" in parsed

    def test_get_tool_definitions(self, formatter):
        tools = formatter.get_tool_definitions()
        assert len(tools) > 0
        assert tools == list(AGENT_TOOLS)


# ---------------------------------------------------------------------------
# GLM4Formatter
# ---------------------------------------------------------------------------


class TestGLM4Formatter:
    @pytest.fixture
    def formatter(self):
        return GLM4Formatter()

    def test_observation_role_for_tool_results(self, formatter):
        text = formatter.format_messages(SAMPLE_MESSAGES)
        assert "<|observation|>" in text

    def test_format_assistant_with_tool_call(self, formatter):
        text = formatter.format_messages(SAMPLE_MESSAGES)
        # GLM4 uses <|assistant|>tool_name format for tool calls
        assert "<|assistant|>shell_command" in text

    def test_format_system_role(self, formatter):
        text = formatter.format_messages(SAMPLE_MESSAGES)
        assert "<|system|>" in text

    def test_format_user_role(self, formatter):
        text = formatter.format_messages(SAMPLE_MESSAGES)
        assert "<|user|>" in text

    def test_get_tool_definitions(self, formatter):
        tools = formatter.get_tool_definitions()
        assert len(tools) > 0


# ---------------------------------------------------------------------------
# DevstralFormatter
# ---------------------------------------------------------------------------


class TestDevstralFormatter:
    @pytest.fixture
    def formatter(self):
        return DevstralFormatter()

    def test_tool_calls_block(self, formatter):
        text = formatter.format_messages(SAMPLE_MESSAGES)
        assert "[TOOL_CALLS]" in text

    def test_tool_results_block(self, formatter):
        text = formatter.format_messages(SAMPLE_MESSAGES)
        assert "[TOOL_RESULTS]" in text
        assert "[/TOOL_RESULTS]" in text

    def test_inst_markers(self, formatter):
        text = formatter.format_messages(SAMPLE_MESSAGES)
        assert "[INST]" in text
        assert "[/INST]" in text

    def test_reasoning_content_merged(self, formatter):
        msgs = [
            {"role": "user", "content": "test"},
            {
                "role": "assistant",
                "content": "Found it.",
                "reasoning_content": "Let me think...",
            },
        ]
        text = formatter.format_messages(msgs)
        assert "<think>Let me think...</think>" in text
        assert "Found it." in text

    def test_alternation_enforced(self, formatter):
        """Consecutive assistant messages should get empty user inserted."""
        msgs = [
            {"role": "user", "content": "start"},
            {"role": "assistant", "content": "first"},
            {"role": "assistant", "content": "second"},
        ]
        processed = formatter._enforce_alternation(msgs)
        roles = [m["role"] for m in processed]
        # Should have user between two assistants
        for i in range(1, len(roles)):
            if roles[i] == "assistant" and roles[i - 1] == "assistant":
                pytest.fail("Consecutive assistant messages not separated")


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_boxpwnr_tools_not_empty(self):
        assert len(AGENT_TOOLS) > 0

    def test_required_tools_present(self):
        names = {t["function"]["name"] for t in AGENT_TOOLS}
        required = {"shell_command", "flag_found", "python_code", "read_file", "grep"}
        for tool in required:
            assert tool in names, f"Required tool '{tool}' missing from registry"

    def test_tool_schema_structure(self):
        for tool in AGENT_TOOLS:
            assert tool["type"] == "function"
            fn = tool["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            assert fn["parameters"]["type"] == "object"

    def test_get_tool_by_name(self):
        t = get_tool_by_name("shell_command")
        assert t is not None
        assert t["function"]["name"] == "shell_command"

    def test_get_tool_by_name_not_found(self):
        assert get_tool_by_name("nonexistent") is None

    def test_get_tools_by_names(self):
        tools = get_tools_by_names(["shell_command", "flag_found"])
        assert len(tools) == 2

    def test_get_tools_by_names_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown tool"):
            get_tools_by_names(["shell_command", "totally_fake_tool"])
