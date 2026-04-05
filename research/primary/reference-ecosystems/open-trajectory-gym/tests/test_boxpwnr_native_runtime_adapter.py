"""Tests for examples/bring-your-own/agent/boxpwnr_adapter.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = REPO_ROOT / "examples" / "bring-your-own" / "agent" / "boxpwnr_adapter.py"


def _run_adapter(payload: dict) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, str(ADAPTER)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def _base_request() -> dict:
    return {
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
        "turn": 1,
        "max_steps": 20,
        "runtime_state": {},
    }


def test_adapter_returns_protocol_passthrough_response() -> None:
    proc = _run_adapter(_base_request())
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data["protocol_version"] == "1.0"
    assert data["passthrough"] is True
    assert "passthrough_response" in data
    payload = data["passthrough_response"]
    assert payload["observations"]
    assert payload["info"]["framework"] == "boxpwnr_langgraph"
    assert payload["info"]["mode"] == "native"


def test_adapter_fails_fast_on_missing_required_capabilities() -> None:
    request = _base_request()
    request["capabilities"] = ["tool_calls_response"]
    proc = _run_adapter(request)
    assert proc.returncode != 0
    assert "missing required request capabilities" in proc.stderr


def test_adapter_fails_fast_on_bad_protocol_major() -> None:
    request = _base_request()
    request["protocol_version"] = "2.0"
    proc = _run_adapter(request)
    assert proc.returncode != 0
    assert "unsupported protocol_version" in proc.stderr


def test_adapter_parses_generic_xml_shell_command_tags() -> None:
    request = _base_request()
    request["action"] = '<shell_command maxtime=5>command="echo xml_ok"</shell_command>'
    proc = _run_adapter(request)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    payload = data["passthrough_response"]
    observations = payload.get("observations", [])
    assert observations
    assert "xml_ok" in observations[0].get("content", "")


def test_adapter_recovers_shell_command_from_malformed_tool_markup() -> None:
    request = _base_request()
    request[
        "action"
    ] = """
<exploit>
<tool_call>
shell_command(command="echo malformed_ok")
</tool_call>
</exploit>
"""
    proc = _run_adapter(request)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    payload = data["passthrough_response"]
    observations = payload.get("observations", [])
    assert observations
    assert "malformed_ok" in observations[0].get("content", "")
