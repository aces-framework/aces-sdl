"""Tests for BYO runtime hook in DefaultStepAgent.

The runtime protocol is:
  - agent sends JSON payload on stdin
  - runtime prints JSON response on stdout
"""

from __future__ import annotations

import sys
from pathlib import Path

from trajgym.agent.default_agent import DefaultStepAgent


def _write_runtime_script(path: Path, body: str) -> str:
    path.write_text(body, encoding="utf-8")
    return f"{sys.executable} {path}"


def test_runtime_tool_call_mode_executes_local_tools(tmp_path: Path) -> None:
    script = _write_runtime_script(
        tmp_path / "runtime_tool_calls.py",
        """import json, sys
req = json.load(sys.stdin)
resp = {
    "protocol_version": "1.0",
    "capabilities": ["tool_calls_response", "state_persistence"],
    "tool_calls_response": {
        "tool_calls": [
            {"name": "shell_command", "arguments": {"command": "echo runtime_hook_ok"}}
        ],
        "state": {"last_turn": req.get("turn")},
        "info": {"runtime_source": "test_runtime_tool_calls"},
    },
}
print(json.dumps(resp))
""",
    )

    agent = DefaultStepAgent(
        runtime_cmd=script,
        runtime_fallback_to_parser=False,
        runtime_timeout_seconds=5,
    )
    agent.reset(target="http://localhost:8080", max_steps=10)

    result = agent.step("no native tool call in this text")
    assert result.done is False
    assert result.observations
    assert "runtime_hook_ok" in result.observations[0]["content"]
    assert result.info["runtime_source"] == "test_runtime_tool_calls"
    assert agent._runtime_state.get("last_turn") == 1
    assert len(agent.tool_calls_history) == 1
    assert agent.tool_calls_history[0]["name"] == "shell_command"


def test_runtime_passthrough_mode(tmp_path: Path) -> None:
    script = _write_runtime_script(
        tmp_path / "runtime_passthrough.py",
        """import json, sys
_ = json.load(sys.stdin)
resp = {
    "protocol_version": "1.0",
    "capabilities": ["passthrough_response", "state_persistence"],
    "passthrough": True,
    "passthrough_response": {
        "done": False,
        "observations": [{"role": "user", "content": "runtime_passthrough_obs"}],
        "tool_calls": [
            {"name": "shell_command", "arguments": {"command": "echo passthrough"}}
        ],
        "info": {"rollout_status": "ok", "runtime_source": "passthrough"},
    },
}
print(json.dumps(resp))
""",
    )

    agent = DefaultStepAgent(
        runtime_cmd=script,
        runtime_passthrough=True,
        runtime_fallback_to_parser=False,
        runtime_timeout_seconds=5,
    )
    agent.reset(target="http://localhost:8080", max_steps=10)

    result = agent.step("any action")
    assert result.done is False
    assert len(result.observations) == 1
    assert result.observations[0]["content"] == "runtime_passthrough_obs"
    assert result.info["runtime_source"] == "passthrough"
    assert result.info["rollout_status"] == "ok"
    assert len(agent.tool_calls_history) == 1
    assert agent.tool_calls_history[0]["name"] == "shell_command"
    assert any("runtime_passthrough_obs" in out for out in agent.tool_outputs)


def test_runtime_failure_falls_back_to_native_parser(tmp_path: Path) -> None:
    failing_script = _write_runtime_script(
        tmp_path / "runtime_fail.py",
        """import sys
print("forced failure", file=sys.stderr)
sys.exit(2)
""",
    )

    agent = DefaultStepAgent(
        runtime_cmd=failing_script,
        runtime_fallback_to_parser=True,
        runtime_timeout_seconds=5,
    )
    agent.reset(target="http://localhost:8080", max_steps=10)

    # Native parser should kick in and execute this tool call.
    action = '<tool_call>{"name":"shell_command","arguments":{"command":"echo fallback_ok"}}</tool_call>'
    result = agent.step(action)
    assert result.done is False
    assert result.observations
    assert "fallback_ok" in result.observations[0]["content"]
    assert len(agent.tool_calls_history) == 1


def test_runtime_failure_without_fallback_terminates_step(tmp_path: Path) -> None:
    failing_script = _write_runtime_script(
        tmp_path / "runtime_fail_hard.py",
        """import sys
print("forced hard failure", file=sys.stderr)
sys.exit(3)
""",
    )

    agent = DefaultStepAgent(
        runtime_cmd=failing_script,
        runtime_fallback_to_parser=False,
        runtime_timeout_seconds=5,
    )
    agent.reset(target="http://localhost:8080", max_steps=10)

    result = agent.step("anything")
    assert result.done is True
    assert result.observations == []
    assert result.info["rollout_status"] == "runtime_error"
    assert "runtime_error" in result.info


def test_runtime_no_tool_calls_respects_no_fallback_parser(tmp_path: Path) -> None:
    script = _write_runtime_script(
        tmp_path / "runtime_no_tools.py",
        """import json, sys
_ = json.load(sys.stdin)
resp = {
    "protocol_version": "1.0",
    "capabilities": ["tool_calls_response", "state_persistence"],
    "tool_calls_response": {
        "tool_calls": [],
        "state": {},
        "info": {"rollout_status": "no_tool_call", "runtime_source": "no_tools"},
    },
}
print(json.dumps(resp))
""",
    )

    agent = DefaultStepAgent(
        runtime_cmd=script,
        runtime_fallback_to_parser=False,
        runtime_timeout_seconds=5,
    )
    agent.reset(target="http://localhost:8080", max_steps=10)

    action = '<tool_call>{"name":"shell_command","arguments":{"command":"echo should_not_run"}}</tool_call>'
    result = agent.step(action)
    assert result.done is False
    assert result.info["rollout_status"] == "no_tool_call"
    assert result.info["runtime_source"] == "no_tools"
    assert agent.tool_calls_history == []
    assert all(
        "should_not_run" not in obs.get("content", "") for obs in result.observations
    )
