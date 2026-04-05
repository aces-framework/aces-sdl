"""Unit tests for BYO runtime protocol helpers."""

from __future__ import annotations

import json

import pytest
from trajgym.agent.wire_protocol import (
    RuntimeProtocolError,
    build_runtime_request,
    normalize_runtime_request,
    normalize_runtime_response,
    parse_runtime_stdout,
)


def test_build_runtime_request_includes_protocol_fields() -> None:
    payload = build_runtime_request(
        action="test",
        turn=1,
        max_steps=20,
        target="http://localhost:32801",
        ground_truth_flag="FLAG{x}",
        tool_calls_history=[],
        tool_outputs=[],
        all_text="",
        runtime_state={"k": "v"},
        prompt_messages=[{"role": "user", "content": "hello"}],
        challenge_id="c1",
        category="web",
        difficulty="easy",
        infra_type="docker",
        objective="get flag",
    )
    assert payload["protocol_version"] == "1.0"
    assert payload["request_type"] == "step"
    assert "capabilities" in payload
    assert payload["challenge"]["id"] == "c1"
    assert payload["challenge"]["category"] == "web"
    assert payload["challenge"]["difficulty"] == "easy"
    assert payload["objective"] == "get flag"
    assert payload["prompt_messages"][0]["role"] == "user"


def test_parse_runtime_stdout_accepts_last_line_json() -> None:
    raw = "debug line\n" + json.dumps({"done": False, "tool_calls_response": {}})
    parsed = parse_runtime_stdout(raw)
    assert parsed["done"] is False


def test_normalize_runtime_response_sets_default_status() -> None:
    normalized = normalize_runtime_response(
        {
            "protocol_version": "1.0",
            "capabilities": ["tool_calls_response"],
            "tool_calls_response": {"tool_calls": []},
        }
    )
    assert normalized["info"]["rollout_status"] == "ok"


def test_normalize_runtime_response_rejects_bad_tool_calls_type() -> None:
    with pytest.raises(RuntimeProtocolError):
        normalize_runtime_response(
            {
                "protocol_version": "1.0",
                "capabilities": ["tool_calls_response"],
                "tool_calls_response": {"tool_calls": "bad"},
            }
        )


def test_normalize_runtime_response_requires_compatible_version() -> None:
    with pytest.raises(RuntimeProtocolError, match="unsupported protocol_version"):
        normalize_runtime_response(
            {
                "protocol_version": "2.0",
                "capabilities": ["tool_calls_response"],
                "tool_calls_response": {"tool_calls": []},
            }
        )


def test_normalize_runtime_response_requires_mode_payload_key() -> None:
    with pytest.raises(
        RuntimeProtocolError, match="missing required 'tool_calls_response'"
    ):
        normalize_runtime_response(
            {
                "protocol_version": "1.0",
                "capabilities": ["tool_calls_response"],
                "tool_calls": [],
            }
        )


def test_normalize_runtime_response_rejects_unknown_capabilities() -> None:
    with pytest.raises(RuntimeProtocolError, match="unsupported capabilities"):
        normalize_runtime_response(
            {
                "protocol_version": "1.0",
                "capabilities": ["tool_calls_response", "unknown_cap"],
                "tool_calls_response": {"tool_calls": []},
            }
        )


def test_parse_runtime_stdout_rejects_empty() -> None:
    with pytest.raises(RuntimeProtocolError):
        parse_runtime_stdout("")


def test_normalize_runtime_request_rejects_unsupported_protocol_major() -> None:
    with pytest.raises(RuntimeProtocolError, match="unsupported protocol_version"):
        normalize_runtime_request(
            {
                "protocol_version": "2.0",
                "request_type": "step",
                "capabilities": ["tool_calls_response", "state_persistence"],
                "action": "x",
            }
        )


def test_normalize_runtime_response_unknown_status_maps_to_runtime_error() -> None:
    normalized = normalize_runtime_response(
        {
            "protocol_version": "1.0",
            "capabilities": ["tool_calls_response"],
            "tool_calls_response": {
                "tool_calls": [],
                "info": {"rollout_status": "new_unrecognized_status"},
            },
        }
    )
    assert normalized["info"]["rollout_status"] == "runtime_error"
