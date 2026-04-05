"""Smoke tests for native framework adapter templates via runtime bridge."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE = REPO_ROOT / "src" / "trajgym" / "agent" / "framework_runtime_bridge.py"
ADAPTER_DIR = REPO_ROOT / "examples" / "bring-your-own" / "agent"


def _run_bridge_native(*, framework: str, adapter_path: Path) -> dict:
    cmd = f"{shlex.quote(sys.executable)} {shlex.quote(str(adapter_path))}"
    env = dict(os.environ)
    env.update(
        {
            "TRAJGYM_AGENT_FRAMEWORK": framework,
            "TRAJGYM_AGENT_MODE": "native",
            "TRAJGYM_AGENT_CMD": cmd,
            "TRAJGYM_AGENT_CMD_TIMEOUT": "10",
        }
    )
    request = {
        "action": "ignored",
        "turn": 2,
        "max_steps": 20,
        "target": "http://127.0.0.1:32810",
        "objective": "Find and submit the flag.",
        "challenge": {"id": "00-test", "difficulty": "very_easy"},
        "runtime_state": {},
    }
    proc = subprocess.run(
        [sys.executable, str(BRIDGE)],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize(
    ("framework", "adapter_name"),
    [
        ("langgraph", "langgraph_stub_adapter.py"),
    ],
)
def test_native_adapter_templates_bridge_contract(
    framework: str,
    adapter_name: str,
) -> None:
    response = _run_bridge_native(
        framework=framework,
        adapter_path=ADAPTER_DIR / adapter_name,
    )
    assert response["protocol_version"] == "1.0"
    assert response["passthrough"] is True

    payload = response["passthrough_response"]
    assert payload["done"] is False
    assert payload["episode_done"] is False
    assert isinstance(payload["observations"], list)
    assert payload["observations"]
    assert isinstance(payload["state"], dict)

    info = payload["info"]
    assert info["framework"] == framework
    assert info["mode"] == "native"
    assert info["runtime"] == "framework_runtime_bridge"
    assert "rollout_status" in info
