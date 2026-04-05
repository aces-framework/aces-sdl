"""Smoke tests for BoxPwnrConverter.

Validates:
- Tool-calling format conversion preserves structure
- Chat-command format is converted to tool calls
- Output has correct ChatML roles (system/user/assistant/tool)
- Tool name normalization (aliases, corrupt names)
- Metadata and flag extraction
"""

import json

import pytest
from trajgym.data.converter import (
    BoxPwnrConverter,
    _extract_reasoning_and_text,
    _is_chat_command_format,
    normalize_tool_name,
)

# ---------------------------------------------------------------------------
# normalize_tool_name
# ---------------------------------------------------------------------------


class TestNormalizeToolName:
    def test_known_tools_pass_through(self):
        for name in ("shell_command", "flag_found", "python_code", "read_file"):
            assert normalize_tool_name(name) == name

    def test_alias_bash_to_shell_command(self):
        assert normalize_tool_name("bash") == "shell_command"
        assert normalize_tool_name("Bash") == "shell_command"

    def test_alias_tmux_to_pty(self):
        assert normalize_tool_name("tmux_send_and_read") == "write_stdin"
        assert normalize_tool_name("tmux_cancel_command") == "close_session"

    def test_todowrite_dropped(self):
        assert normalize_tool_name("TodoWrite") is None

    def test_unknown_tool_passes_through(self):
        assert normalize_tool_name("completely_unknown") == "completely_unknown"

    def test_tokenization_artifact_stripped(self):
        assert normalize_tool_name("shell_command<|channel|>json") == "shell_command"


# ---------------------------------------------------------------------------
# _extract_reasoning_and_text
# ---------------------------------------------------------------------------


class TestExtractReasoningAndText:
    def test_plain_string(self):
        reasoning, text = _extract_reasoning_and_text("hello world")
        assert reasoning == ""
        assert text == "hello world"

    def test_list_with_thinking(self):
        content = [
            {"type": "thinking", "thinking": "Let me think..."},
            {"type": "text", "text": "I found the answer."},
        ]
        reasoning, text = _extract_reasoning_and_text(content)
        assert reasoning == "Let me think..."
        assert text == "I found the answer."

    def test_empty_content(self):
        reasoning, text = _extract_reasoning_and_text("")
        assert reasoning == ""
        assert text == ""

    def test_none_content(self):
        reasoning, text = _extract_reasoning_and_text(None)
        assert reasoning == ""
        assert text == ""


# ---------------------------------------------------------------------------
# _is_chat_command_format
# ---------------------------------------------------------------------------


class TestFormatDetection:
    def test_tool_calling_detected(self, sample_tool_calling_messages):
        assert _is_chat_command_format(sample_tool_calling_messages) is False

    def test_chat_command_detected(self, sample_chat_command_messages):
        assert _is_chat_command_format(sample_chat_command_messages) is True


# ---------------------------------------------------------------------------
# BoxPwnrConverter.convert_trace (tool-calling format)
# ---------------------------------------------------------------------------


class TestConvertToolCallingTrace:
    def test_basic_conversion(self, tmp_path, sample_tool_calling_messages):
        trace_dir = tmp_path / "platform" / "challenge" / "traces" / "2024-01-01"
        trace_dir.mkdir(parents=True)

        conv_file = trace_dir / "conversation.json"
        conv_file.write_text(json.dumps({"messages": sample_tool_calling_messages}))

        stats_file = trace_dir / "stats.json"
        stats_file.write_text(
            json.dumps(
                {
                    "status": "success",
                    "flag": "FLAG{test_123}",
                    "total_turns": 5,
                }
            )
        )

        converter = BoxPwnrConverter()
        result = converter.convert_trace(trace_dir)

        assert result is not None
        msgs = result["messages"]

        # First message should be system (injected)
        assert msgs[0]["role"] == "system"

        # Verify all roles are valid ChatML
        valid_roles = {"system", "user", "assistant", "tool"}
        for msg in msgs:
            assert msg["role"] in valid_roles, f"Invalid role: {msg['role']}"

        # Verify tool calls have correct structure
        for msg in msgs:
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    assert "id" in tc
                    assert "type" in tc
                    assert tc["type"] == "function"
                    assert "function" in tc
                    assert "name" in tc["function"]
                    assert "arguments" in tc["function"]

        # Verify metadata extraction
        assert result["metadata"]["source"] == "boxpwnr"
        assert result["metadata"]["success"] is True
        assert result["ground_truth_flag"] == "FLAG{test_123}"
        assert result["optimal_steps"] >= 1

    def test_missing_conversation_json(self, tmp_path):
        trace_dir = tmp_path / "empty"
        trace_dir.mkdir()
        converter = BoxPwnrConverter()
        assert converter.convert_trace(trace_dir) is None

    def test_empty_messages(self, tmp_path):
        trace_dir = tmp_path / "empty_msgs"
        trace_dir.mkdir()
        (trace_dir / "conversation.json").write_text(json.dumps({"messages": []}))
        converter = BoxPwnrConverter()
        assert converter.convert_trace(trace_dir) is None


# ---------------------------------------------------------------------------
# BoxPwnrConverter.convert_trace (chat-command format)
# ---------------------------------------------------------------------------


class TestConvertChatCommandTrace:
    def test_chat_command_conversion(self, tmp_path, sample_chat_command_messages):
        trace_dir = tmp_path / "plat" / "chall" / "traces" / "2024-01-01"
        trace_dir.mkdir(parents=True)

        conv_file = trace_dir / "conversation.json"
        conv_file.write_text(json.dumps({"messages": sample_chat_command_messages}))

        converter = BoxPwnrConverter()
        result = converter.convert_trace(trace_dir)

        assert result is not None
        msgs = result["messages"]

        # System prompt injected
        assert msgs[0]["role"] == "system"

        # <COMMAND> should be converted to tool_calls
        has_tool_calls = any(m.get("tool_calls") for m in msgs)
        assert has_tool_calls, "Chat-command <COMMAND> should produce tool_calls"

        # <OUTPUT> should be converted to tool role
        has_tool_msg = any(m["role"] == "tool" for m in msgs)
        assert has_tool_msg, "Chat-command <OUTPUT> should produce tool role message"

        # Flag should be extracted
        assert result["ground_truth_flag"] == "FLAG{chat_cmd_flag}"


# ---------------------------------------------------------------------------
# Tool name normalization in conversion
# ---------------------------------------------------------------------------


class TestToolNameNormalizationInConversion:
    def test_alias_normalized_during_conversion(self, tmp_path):
        """Bash alias should be normalized to shell_command in output."""
        messages = [
            {"role": "user", "content": "test"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "Bash",
                            "arguments": '{"command": "ls"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "Bash",
                "content": "file.txt",
            },
        ]

        trace_dir = tmp_path / "traces" / "test"
        trace_dir.mkdir(parents=True)
        (trace_dir / "conversation.json").write_text(json.dumps({"messages": messages}))

        converter = BoxPwnrConverter()
        result = converter.convert_trace(trace_dir)
        assert result is not None

        # Find assistant message with tool_calls
        for msg in result["messages"]:
            if msg.get("tool_calls"):
                assert msg["tool_calls"][0]["function"]["name"] == "shell_command"


# ---------------------------------------------------------------------------
# ChatML role ordering validation
# ---------------------------------------------------------------------------

VALID_ROLES = {"system", "user", "assistant", "tool"}


class TestChatMLRoleOrdering:
    """Validate that converted traces have proper ChatML role structure."""

    def _convert(self, tmp_path, messages, stats=None):
        trace_dir = tmp_path / "platform" / "challenge" / "traces" / "2024-01-01"
        trace_dir.mkdir(parents=True)
        (trace_dir / "conversation.json").write_text(json.dumps({"messages": messages}))
        if stats:
            (trace_dir / "stats.json").write_text(json.dumps(stats))
        converter = BoxPwnrConverter()
        return converter.convert_trace(trace_dir)

    def test_all_roles_are_valid(self, tmp_path, sample_tool_calling_messages):
        result = self._convert(tmp_path, sample_tool_calling_messages)
        assert result is not None
        for msg in result["messages"]:
            assert msg["role"] in VALID_ROLES, f"Invalid role: {msg['role']}"

    def test_first_message_is_system(self, tmp_path, sample_tool_calling_messages):
        result = self._convert(tmp_path, sample_tool_calling_messages)
        assert result is not None
        assert result["messages"][0]["role"] == "system"

    def test_tool_messages_follow_assistant_with_tool_calls(
        self, tmp_path, sample_tool_calling_messages
    ):
        """Tool messages must be preceded by an assistant message with tool_calls."""
        result = self._convert(tmp_path, sample_tool_calling_messages)
        assert result is not None
        msgs = result["messages"]
        for i, msg in enumerate(msgs):
            if msg["role"] == "tool":
                # Walk back to find the nearest assistant with tool_calls
                found_assistant = False
                for j in range(i - 1, -1, -1):
                    if msgs[j]["role"] == "assistant" and msgs[j].get("tool_calls"):
                        found_assistant = True
                        break
                    if msgs[j]["role"] in ("user", "system"):
                        break
                assert (
                    found_assistant
                ), f"Tool message at index {i} not preceded by assistant with tool_calls"

    def test_messages_have_content_or_tool_calls(
        self, tmp_path, sample_tool_calling_messages
    ):
        """All messages should have non-empty content or be tool responses."""
        result = self._convert(tmp_path, sample_tool_calling_messages)
        assert result is not None
        for msg in result["messages"]:
            has_content = bool(msg.get("content"))
            has_tool_calls = bool(msg.get("tool_calls"))
            has_reasoning = bool(msg.get("reasoning_content"))
            is_tool_response = msg["role"] == "tool"
            assert (
                has_content or has_tool_calls or has_reasoning or is_tool_response
            ), f"Message with role '{msg['role']}' has no content, tool_calls, or reasoning"

    def test_chat_command_format_also_valid(
        self, tmp_path, sample_chat_command_messages
    ):
        """Chat-command format should also produce valid ChatML ordering."""
        result = self._convert(tmp_path, sample_chat_command_messages)
        assert result is not None
        msgs = result["messages"]

        # All roles valid
        for msg in msgs:
            assert msg["role"] in VALID_ROLES

        # First is system
        assert msgs[0]["role"] == "system"

        # Tool messages preceded by assistant
        for i, msg in enumerate(msgs):
            if msg["role"] == "tool":
                found_assistant = False
                for j in range(i - 1, -1, -1):
                    if msgs[j]["role"] == "assistant" and msgs[j].get("tool_calls"):
                        found_assistant = True
                        break
                    if msgs[j]["role"] in ("user", "system"):
                        break
                assert found_assistant

    def test_no_consecutive_user_messages_after_tool_calling(
        self, tmp_path, sample_tool_calling_messages
    ):
        """In tool-calling format, user messages shouldn't appear consecutively."""
        result = self._convert(tmp_path, sample_tool_calling_messages)
        assert result is not None
        msgs = result["messages"]
        for i in range(1, len(msgs)):
            if msgs[i]["role"] == "user" and msgs[i - 1]["role"] == "user":
                pytest.fail(f"Consecutive user messages at indices {i-1} and {i}")
