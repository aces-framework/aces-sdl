"""Shared fixtures for open-trajectory-gym smoke tests."""

from pathlib import Path

import pytest

# Project root (two levels up from tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def project_root():
    """Absolute path to the project root."""
    return PROJECT_ROOT


@pytest.fixture
def sample_tool_calling_messages():
    """Minimal BoxPwnr tool-calling format conversation."""
    return [
        {"role": "system", "content": "You are a CTF agent."},
        {"role": "user", "content": "Solve the challenge at http://target:8080"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "function": {
                        "name": "shell_command",
                        "arguments": '{"command": "nmap -sV target"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_abc123",
            "name": "shell_command",
            "content": "80/tcp open http\n443/tcp open https",
        },
        {
            "role": "assistant",
            "content": "Found flag: FLAG{test_123}",
            "tool_calls": [
                {
                    "id": "call_def456",
                    "function": {
                        "name": "flag_found",
                        "arguments": '{"content": "FLAG{test_123}"}',
                    },
                }
            ],
        },
    ]


@pytest.fixture
def sample_chat_command_messages():
    """Minimal BoxPwnr chat-command format conversation."""
    return [
        {"role": "system", "content": "You are a CTF agent."},
        {"role": "user", "content": "Solve the challenge."},
        {
            "role": "assistant",
            "content": "Let me scan the target.\n<COMMAND>nmap -sV target</COMMAND>",
        },
        {
            "role": "user",
            "content": "<OUTPUT><STDOUT>80/tcp open http</STDOUT></OUTPUT>",
        },
        {
            "role": "assistant",
            "content": "Found it!\n<FLAG>FLAG{chat_cmd_flag}</FLAG>",
        },
    ]


@pytest.fixture
def sample_sft_record(sample_tool_calling_messages):
    """A minimal SFT-style JSONL record."""
    return {
        "messages": sample_tool_calling_messages,
        "metadata": {
            "source": "boxpwnr",
            "platform": "cybench",
            "challenge": "test-challenge",
            "success": True,
        },
        "ground_truth_flag": "FLAG{test_123}",
        "optimal_steps": 2,
    }


@pytest.fixture
def sample_grpo_record(sample_tool_calling_messages):
    """A minimal Online RL-style JSONL record with ground_truth_flag."""
    return {
        "messages": sample_tool_calling_messages,
        "metadata": {
            "source": "boxpwnr",
            "platform": "cybench",
            "challenge": "test-challenge",
            "success": True,
        },
        "ground_truth_flag": "FLAG{test_123}",
        "optimal_steps": 2,
    }
