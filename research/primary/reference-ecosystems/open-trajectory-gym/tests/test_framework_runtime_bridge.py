"""Tests for src/trajgym/agent/framework_runtime_bridge.py."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE = REPO_ROOT / "src" / "trajgym" / "agent" / "framework_runtime_bridge.py"


def _run_bridge(payload: dict, env: dict[str, str] | None = None) -> dict:
    merged_env = dict(os.environ)
    merged_env["PYTHONPATH"] = str(REPO_ROOT / "src")
    if env is not None:
        merged_env.update(env)
    proc = subprocess.run(
        [sys.executable, str(BRIDGE)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=merged_env,
        check=True,
    )
    stdout = proc.stdout.strip().splitlines()[-1]
    return json.loads(stdout)


def test_bridge_tool_calls_mode_parses_action() -> None:
    payload = {
        "action": (
            '<tool_call>{"name":"shell_command","arguments":{"command":"echo ok"}}'
            "</tool_call>"
        ),
        "turn": 1,
        "runtime_state": {},
    }
    response = _run_bridge(
        payload,
        env={
            "TRAJGYM_AGENT_FRAMEWORK": "boxpwnr_langgraph",
            "TRAJGYM_AGENT_MODE": "tool_calls",
        },
    )
    assert response["protocol_version"] == "1.0"
    assert "tool_calls_response" in response
    tool_calls = response["tool_calls_response"]["tool_calls"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "shell_command"
    assert response["tool_calls_response"]["info"]["mode"] == "tool_calls"


def test_bridge_native_mode_wraps_simple_adapter_output(tmp_path: Path) -> None:
    adapter = tmp_path / "simple_adapter.py"
    adapter.write_text(
        """
import json, sys
_ = json.load(sys.stdin)
print(json.dumps({
    "done": False,
    "episode_done": False,
    "observations": [{"role": "user", "content": "native_adapter_ok"}],
    "state": {"adapter_turn": 1},
    "info": {"adapter": "simple"},
}))
""".strip()
        + "\n",
        encoding="utf-8",
    )

    cmd = f"{shlex.quote(sys.executable)} {shlex.quote(str(adapter))}"
    response = _run_bridge(
        {"action": "ignored", "turn": 1, "runtime_state": {}},
        env={
            "TRAJGYM_AGENT_FRAMEWORK": "langgraph",
            "TRAJGYM_AGENT_MODE": "native",
            "TRAJGYM_AGENT_CMD": cmd,
            "TRAJGYM_AGENT_CMD_TIMEOUT": "10",
        },
    )
    assert response["passthrough"] is True
    payload = response["passthrough_response"]
    assert payload["done"] is False
    assert payload["observations"][0]["content"] == "native_adapter_ok"
    assert payload["state"]["adapter_turn"] == 1
    assert payload["info"]["framework"] == "langgraph"
    assert payload["info"]["mode"] == "native"


def test_bridge_native_mode_preserves_protocol_passthrough_response() -> None:
    adapter = REPO_ROOT / "examples" / "bring-your-own" / "agent" / "boxpwnr_adapter.py"
    cmd = f"{shlex.quote(sys.executable)} {shlex.quote(str(adapter))}"
    response = _run_bridge(
        {
            "protocol_version": "1.0",
            "request_type": "step",
            "capabilities": [
                "tool_calls_response",
                "passthrough_response",
                "state_persistence",
            ],
            "action": (
                '<tool_call>{"name":"shell_command","arguments":{"command":"echo ok"}}'
                "</tool_call>"
            ),
            "turn": 2,
            "max_steps": 20,
            "runtime_state": {},
        },
        env={
            "TRAJGYM_AGENT_FRAMEWORK": "boxpwnr_langgraph",
            "TRAJGYM_AGENT_MODE": "native",
            "TRAJGYM_AGENT_CMD": cmd,
            "TRAJGYM_AGENT_CMD_TIMEOUT": "10",
        },
    )
    assert response["protocol_version"] == "1.0"
    assert response["passthrough"] is True
    assert "passthrough_response" in response
    payload = response["passthrough_response"]
    assert payload["observations"]
    assert payload["info"]["framework"] == "boxpwnr_langgraph"
    assert payload["info"]["mode"] == "native"


def test_bridge_defaults_framework_to_generic_when_unset() -> None:
    payload = {
        "action": (
            '<tool_call>{"name":"shell_command","arguments":{"command":"echo ok"}}'
            "</tool_call>"
        ),
        "turn": 1,
        "runtime_state": {},
    }
    response = _run_bridge(
        payload,
        env={
            "TRAJGYM_AGENT_FRAMEWORK": "",
            "TRAJGYM_AGENT_MODE": "tool_calls",
        },
    )
    info = response["tool_calls_response"]["info"]
    assert info["framework"] == "generic"


def test_bridge_rejects_invalid_declared_request_protocol() -> None:
    payload = {
        "protocol_version": "2.0",
        "request_type": "step",
        "capabilities": ["tool_calls_response", "state_persistence"],
        "action": "ignored",
        "turn": 1,
        "runtime_state": {},
    }
    response = _run_bridge(
        payload,
        env={
            "TRAJGYM_AGENT_FRAMEWORK": "generic",
            "TRAJGYM_AGENT_MODE": "tool_calls",
        },
    )
    info = response["tool_calls_response"]["info"]
    assert info["rollout_status"] == "parser_error"
    assert "invalid_runtime_request" in info["runtime_error"]
