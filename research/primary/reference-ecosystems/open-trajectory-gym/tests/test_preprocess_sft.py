"""Tests for trajgym.data.preprocessor (formerly scripts/preprocess_sft_data.py)."""

from __future__ import annotations

from trajgym.data.preprocessor import (
    _fix_html_escapes,
    _fix_orphan_think,
    preprocess_sample,
)

# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


def test_html_unescape():
    assert _fix_html_escapes("&lt;think&gt;") == "<think>"
    assert _fix_html_escapes("a &amp; b") == "a & b"
    assert _fix_html_escapes("no entities") == "no entities"


def test_html_double_encoded():
    assert _fix_html_escapes("&amp;lt;") == "<"
    assert _fix_html_escapes("&amp;amp;") == "&"


def test_orphan_think():
    assert _fix_orphan_think("reasoning</think>") == "<think>reasoning</think>"
    assert _fix_orphan_think("<think>ok</think>") == "<think>ok</think>"
    assert _fix_orphan_think("no tags") == "no tags"


# ---------------------------------------------------------------------------
# Integration tests for preprocess_sample
# ---------------------------------------------------------------------------


def _make_sample(messages, ground_truth_flag="flag{test}"):
    return {
        "messages": messages,
        "ground_truth_flag": ground_truth_flag,
        "metadata": {"challenge": "test"},
    }


def test_strips_noncanonical_tools():
    """Non-canonical tools (Edit, Write, Task) should be removed."""
    msgs = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "shell_command",
                        "arguments": '{"command": "ls"}',
                    },
                },
                {
                    "id": "c2",
                    "type": "function",
                    "function": {"name": "Write", "arguments": '{"path": "/tmp/x"}'},
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "c1",
            "name": "shell_command",
            "content": "file.txt",
        },
        {"role": "tool", "tool_call_id": "c2", "name": "Write", "content": "ok"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c3",
                    "type": "function",
                    "function": {
                        "name": "flag_found",
                        "arguments": '{"content": "flag{test}"}',
                    },
                },
            ],
        },
    ]
    fixed, stats = preprocess_sample(_make_sample(msgs))
    assert stats["noncanonical_stripped"] == 1
    # Write tool call and its response should be removed
    tool_names = [
        tc["function"]["name"]
        for m in fixed["messages"]
        for tc in m.get("tool_calls", [])
    ]
    assert "Write" not in tool_names
    assert "shell_command" in tool_names


def test_injects_verification():
    """flag_found without verification should get one injected."""
    msgs = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "f1",
                    "type": "function",
                    "function": {
                        "name": "flag_found",
                        "arguments": '{"content": "flag{wrong}"}',
                    },
                },
            ],
        },
    ]
    fixed, stats = preprocess_sample(_make_sample(msgs))
    assert stats["verification_injected"] == 1
    # Should have an "Incorrect" verification
    verif = [
        m
        for m in fixed["messages"]
        if m.get("role") == "tool" and m.get("name") == "flag_found"
    ]
    assert len(verif) == 1
    assert "Incorrect" in verif[0]["content"]


def test_correct_flag_verification():
    """Correct flag gets 'Correct! Flag verified' response."""
    msgs = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "f1",
                    "type": "function",
                    "function": {
                        "name": "flag_found",
                        "arguments": '{"content": "flag{test}"}',
                    },
                },
            ],
        },
    ]
    fixed, stats = preprocess_sample(_make_sample(msgs))
    verif = [
        m
        for m in fixed["messages"]
        if m.get("role") == "tool" and m.get("name") == "flag_found"
    ]
    assert len(verif) == 1
    assert "Correct" in verif[0]["content"]


def test_adds_terminal_flag():
    """Samples without flag_found should get a terminal flag_found + verification."""
    msgs = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
        {
            "role": "assistant",
            "content": "I found the flag: flag{test}",
            "tool_calls": [
                {
                    "id": "s1",
                    "type": "function",
                    "function": {
                        "name": "shell_command",
                        "arguments": '{"command": "cat flag.txt"}',
                    },
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "s1",
            "name": "shell_command",
            "content": "flag{test}",
        },
    ]
    fixed, stats = preprocess_sample(_make_sample(msgs))
    assert stats["terminal_flag_added"] == 1
    # Last two messages should be flag_found call + verification
    assert fixed["messages"][-1]["role"] == "tool"
    assert "Correct" in fixed["messages"][-1]["content"]
    assert fixed["messages"][-2]["role"] == "assistant"
    assert fixed["messages"][-2]["tool_calls"][0]["function"]["name"] == "flag_found"


def test_fixes_html_in_content():
    """HTML entities should be unescaped."""
    msgs = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
        {
            "role": "assistant",
            "content": "&lt;think&gt;planning&lt;/think&gt;",
            "tool_calls": [
                {
                    "id": "f1",
                    "type": "function",
                    "function": {
                        "name": "flag_found",
                        "arguments": '{"content": "flag{test}"}',
                    },
                },
            ],
        },
    ]
    fixed, stats = preprocess_sample(_make_sample(msgs))
    assert stats["html_fixed"] > 0
    assistant_msg = [m for m in fixed["messages"] if m.get("role") == "assistant"][0]
    assert "<think>" in assistant_msg["content"]
    assert "&lt;" not in assistant_msg["content"]


def test_fixes_orphan_think():
    """Orphan </think> should get opening tag prepended."""
    msgs = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
        {
            "role": "assistant",
            "content": "reasoning here</think>action",
            "tool_calls": [
                {
                    "id": "f1",
                    "type": "function",
                    "function": {
                        "name": "flag_found",
                        "arguments": '{"content": "flag{test}"}',
                    },
                },
            ],
        },
    ]
    fixed, stats = preprocess_sample(_make_sample(msgs))
    assert stats["think_fixed"] == 1
    assistant_msg = [m for m in fixed["messages"] if m.get("role") == "assistant"][0]
    assert assistant_msg["content"].startswith("<think>")


def test_preserves_existing_verification():
    """Existing proper verification responses should not be replaced."""
    msgs = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "f1",
                    "type": "function",
                    "function": {
                        "name": "flag_found",
                        "arguments": '{"content": "flag{test}"}',
                    },
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "f1",
            "name": "flag_found",
            "content": "Correct! Flag verified: flag{test}",
        },
    ]
    fixed, stats = preprocess_sample(_make_sample(msgs))
    assert stats["verification_injected"] == 0
    assert stats["verification_replaced"] == 0
    verif = [
        m
        for m in fixed["messages"]
        if m.get("role") == "tool" and m.get("name") == "flag_found"
    ]
    assert len(verif) == 1
    assert "Correct!" in verif[0]["content"]


def test_replaces_echo_response():
    """Echo responses ('Flag found: X') should be replaced with proper verification."""
    msgs = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "f1",
                    "type": "function",
                    "function": {
                        "name": "flag_found",
                        "arguments": '{"content": "flag{test}"}',
                    },
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "f1",
            "name": "flag_found",
            "content": "Flag found: flag{test}",
        },
    ]
    fixed, stats = preprocess_sample(_make_sample(msgs))
    assert stats["verification_replaced"] == 1
    verif = [
        m
        for m in fixed["messages"]
        if m.get("role") == "tool" and m.get("name") == "flag_found"
    ]
    assert len(verif) == 1
    assert "Correct!" in verif[0]["content"]


def test_replaces_wrong_echo_with_incorrect():
    """Echo of wrong flag should become 'Incorrect submission'."""
    msgs = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "f1",
                    "type": "function",
                    "function": {
                        "name": "flag_found",
                        "arguments": '{"content": "flag{wrong}"}',
                    },
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "f1",
            "name": "flag_found",
            "content": "Flag found: flag{wrong}",
        },
    ]
    fixed, stats = preprocess_sample(_make_sample(msgs))
    assert stats["verification_replaced"] == 1
    verif = [
        m
        for m in fixed["messages"]
        if m.get("role") == "tool" and m.get("name") == "flag_found"
    ]
    assert len(verif) == 1
    assert "Incorrect" in verif[0]["content"]


def test_drops_tiny_samples():
    """Samples with < 4 messages after processing should be dropped."""
    msgs = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
    ]
    fixed, stats = preprocess_sample(_make_sample(msgs, ground_truth_flag=""))
    assert stats["dropped"] is True
    assert fixed is None


def test_no_ground_truth_skips_terminal_flag():
    """Without ground_truth_flag, don't add terminal flag_found."""
    msgs = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
        {
            "role": "assistant",
            "content": "investigating...",
            "tool_calls": [
                {
                    "id": "s1",
                    "type": "function",
                    "function": {
                        "name": "shell_command",
                        "arguments": '{"command": "ls"}',
                    },
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "s1",
            "name": "shell_command",
            "content": "files",
        },
    ]
    fixed, stats = preprocess_sample(_make_sample(msgs, ground_truth_flag=""))
    assert stats["terminal_flag_added"] == 0
