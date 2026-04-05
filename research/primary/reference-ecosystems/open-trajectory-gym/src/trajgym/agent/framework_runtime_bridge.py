#!/usr/bin/env python3
"""Generic BYO-agent runtime bridge for TrajGym online RL.

Modes:
- tool_calls (default): parse LLM action into tool calls for local execution.
- native: delegate to an external framework runtime command and return
  passthrough observations/done (ROCK-style process-runtime integration).

The bridge always speaks TrajGym runtime protocol v1.0.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trajgym.agent.wire_protocol import (  # noqa: E402
    RuntimeProtocolError,
    normalize_runtime_request,
    parse_runtime_stdout,
)
from trajgym.formatters.tool_registry import (  # noqa: E402
    RUNTIME_TOOL_NAMES,
    TOOL_SCHEMA_VERSION,
)
from trajgym.parsing import parse_tool_calls  # noqa: E402

PROTOCOL_VERSION = "1.0"
MODE_TOOL_CALLS = "tool_calls"
MODE_NATIVE = "native"
DEFAULT_FRAMEWORK = "generic"


def _env(key: str, default: str = "") -> str:
    return str(os.getenv(key, default) or "").strip()


def _boxpwnr_available() -> bool:
    try:
        import boxpwnr  # noqa: F401

        return True
    except Exception:
        return False


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def _normalize_mode(raw: str) -> str:
    text = str(raw or "").strip().lower()
    if text in {"native", "passthrough"}:
        return MODE_NATIVE
    return MODE_TOOL_CALLS


def _request_settings(payload: dict[str, Any]) -> dict[str, Any]:
    state = payload.get("runtime_state")
    if not isinstance(state, dict):
        state = {}

    mode = _normalize_mode(
        state.get("agent_mode") or _env("TRAJGYM_AGENT_MODE", MODE_TOOL_CALLS)
    )
    framework = (
        str(
            state.get("agent_framework")
            or _env("TRAJGYM_AGENT_FRAMEWORK", DEFAULT_FRAMEWORK)
        ).strip()
        or DEFAULT_FRAMEWORK
    )
    cmd = str(state.get("agent_cmd") or _env("TRAJGYM_AGENT_CMD", "")).strip()
    # Runtime command working directory is distinct from challenge workspace.
    # Challenge workspace is carried in runtime_state.agent_workdir for the
    # adapter itself; using it as process cwd breaks relative adapter paths.
    workdir = str(
        state.get("agent_cmd_workdir") or _env("TRAJGYM_AGENT_CMD_WORKDIR", "")
    ).strip()
    timeout_raw = state.get("agent_timeout_seconds") or _env(
        "TRAJGYM_AGENT_CMD_TIMEOUT", "120"
    )
    try:
        timeout_seconds = max(1, int(timeout_raw))
    except (TypeError, ValueError):
        timeout_seconds = 120

    runtime_env = state.get("agent_env")
    if not isinstance(runtime_env, dict):
        runtime_env = {}
    runtime_env = {str(k): str(v) for k, v in runtime_env.items() if str(k).strip()}
    return {
        "mode": mode,
        "framework": framework,
        "cmd": cmd,
        "workdir": workdir,
        "timeout_seconds": timeout_seconds,
        "runtime_env": runtime_env,
    }


def _normalize_tool_calls(
    raw_calls: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    allowed = set(RUNTIME_TOOL_NAMES)
    normalized: list[dict[str, Any]] = []
    rejected: list[str] = []

    for call in raw_calls:
        name = str(call.get("name", "")).strip()
        arguments = call.get("arguments", {})
        if not name:
            continue
        if name not in allowed:
            rejected.append(name)
            continue
        if not isinstance(arguments, dict):
            arguments = {}
        normalized.append({"name": name, "arguments": arguments})
    return normalized, rejected


def _tool_calls_response(
    *,
    tool_calls: list[dict[str, Any]],
    state: dict[str, Any],
    info: dict[str, Any],
) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "capabilities": ["tool_calls_response", "state_persistence"],
        "tool_calls_response": {
            "tool_calls": tool_calls,
            "state": state,
            "info": info,
        },
    }


def _passthrough_response(
    *,
    observations: list[dict[str, str]],
    done: bool,
    episode_done: bool,
    state: dict[str, Any],
    info: dict[str, Any],
    tool_calls: list[dict[str, Any]] | None = None,
    all_text_append: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "done": bool(done),
        "episode_done": bool(episode_done),
        "observations": observations,
        "state": state,
        "info": info,
    }
    if tool_calls:
        payload["tool_calls"] = tool_calls
    if all_text_append:
        payload["all_text_append"] = str(all_text_append)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "capabilities": ["passthrough_response", "state_persistence"],
        "passthrough": True,
        "passthrough_response": payload,
    }


def _run_external_framework(
    payload: dict[str, Any],
    settings: dict[str, Any],
) -> dict[str, Any]:
    cmd = settings["cmd"]
    if not cmd:
        raise RuntimeError(
            "native mode requires TRAJGYM_AGENT_CMD (or runtime_state.agent_cmd)"
        )

    env = os.environ.copy()
    env.update(settings.get("runtime_env", {}))
    workdir = settings.get("workdir") or str(ROOT)
    timeout_seconds = int(settings.get("timeout_seconds", 120))

    proc = subprocess.run(
        ["bash", "-c", cmd],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        cwd=workdir,
        env=env,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(
            f"external framework command exited {proc.returncode}: {cmd}"
            + (f" | stderr: {stderr[:500]}" if stderr else "")
        )
    raw = parse_runtime_stdout(proc.stdout)

    # If adapter already returned protocol response, preserve shape and merge info.
    if isinstance(raw, dict) and raw.get("protocol_version"):
        if "passthrough_response" in raw and isinstance(
            raw["passthrough_response"], dict
        ):
            info = raw["passthrough_response"].get("info") or {}
            if not isinstance(info, dict):
                info = {}
            info.setdefault("runtime", "framework_runtime_bridge")
            info.setdefault("framework", settings["framework"])
            info.setdefault("mode", MODE_NATIVE)
            info.setdefault("tool_schema_version", TOOL_SCHEMA_VERSION)
            raw["passthrough_response"]["info"] = info
        elif "tool_calls_response" in raw and isinstance(
            raw["tool_calls_response"], dict
        ):
            info = raw["tool_calls_response"].get("info") or {}
            if not isinstance(info, dict):
                info = {}
            info.setdefault("runtime", "framework_runtime_bridge")
            info.setdefault("framework", settings["framework"])
            info.setdefault("mode", MODE_NATIVE)
            info.setdefault("tool_schema_version", TOOL_SCHEMA_VERSION)
            raw["tool_calls_response"]["info"] = info
        return raw

    observations = raw.get("observations", []) if isinstance(raw, dict) else []
    if not isinstance(observations, list):
        observations = []
    normalized_obs: list[dict[str, str]] = []
    for item in observations:
        if isinstance(item, dict):
            normalized_obs.append(
                {
                    "role": str(item.get("role", "user")),
                    "content": str(item.get("content", "")),
                }
            )

    state = raw.get("state", {}) if isinstance(raw, dict) else {}
    if not isinstance(state, dict):
        state = {}
    done = bool(raw.get("done", False)) if isinstance(raw, dict) else False
    episode_done = (
        bool(raw.get("episode_done", False)) if isinstance(raw, dict) else False
    )
    all_text_append = (
        str(raw.get("all_text_append", ""))
        if isinstance(raw, dict) and raw.get("all_text_append")
        else None
    )

    tool_calls_raw = raw.get("tool_calls", []) if isinstance(raw, dict) else []
    if not isinstance(tool_calls_raw, list):
        tool_calls_raw = []
    tool_calls, rejected = _normalize_tool_calls(tool_calls_raw)

    info = raw.get("info", {}) if isinstance(raw, dict) else {}
    if not isinstance(info, dict):
        info = {}
    info.setdefault("runtime", "framework_runtime_bridge")
    info.setdefault("framework", settings["framework"])
    info.setdefault("mode", MODE_NATIVE)
    info.setdefault("tool_schema_version", TOOL_SCHEMA_VERSION)
    if rejected:
        info["unsupported_tools"] = sorted(set(rejected))
    info.setdefault("rollout_status", "ok")

    return _passthrough_response(
        observations=normalized_obs,
        done=done,
        episode_done=episode_done,
        state=state,
        info=info,
        tool_calls=tool_calls,
        all_text_append=all_text_append,
    )


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        info = {
            "runtime": "framework_runtime_bridge",
            "framework": _env("TRAJGYM_AGENT_FRAMEWORK", DEFAULT_FRAMEWORK),
            "mode": _normalize_mode(_env("TRAJGYM_AGENT_MODE", MODE_TOOL_CALLS)),
            "boxpwnr_available": _boxpwnr_available(),
            "tool_schema_version": TOOL_SCHEMA_VERSION,
            "rollout_status": "no_tool_call",
        }
        return _emit(
            _tool_calls_response(
                tool_calls=[],
                state={"last_turn": 0, "tool_calls": 0},
                info=info,
            )
        )

    try:
        payload = json.loads(raw)
    except Exception as exc:
        info = {
            "runtime": "framework_runtime_bridge",
            "framework": _env("TRAJGYM_AGENT_FRAMEWORK", DEFAULT_FRAMEWORK),
            "mode": _normalize_mode(_env("TRAJGYM_AGENT_MODE", MODE_TOOL_CALLS)),
            "boxpwnr_available": _boxpwnr_available(),
            "tool_schema_version": TOOL_SCHEMA_VERSION,
            "rollout_status": "parser_error",
            "runtime_error": f"invalid_request_json: {exc}",
        }
        return _emit(
            _tool_calls_response(
                tool_calls=[],
                state={},
                info=info,
            )
        )

    try:
        payload = normalize_runtime_request(payload)
    except RuntimeProtocolError as exc:
        info = {
            "runtime": "framework_runtime_bridge",
            "framework": _env("TRAJGYM_AGENT_FRAMEWORK", DEFAULT_FRAMEWORK),
            "mode": _normalize_mode(_env("TRAJGYM_AGENT_MODE", MODE_TOOL_CALLS)),
            "boxpwnr_available": _boxpwnr_available(),
            "tool_schema_version": TOOL_SCHEMA_VERSION,
            "rollout_status": "parser_error",
            "runtime_error": f"invalid_runtime_request: {exc}",
        }
        return _emit(
            _tool_calls_response(
                tool_calls=[],
                state={},
                info=info,
            )
        )

    settings = _request_settings(payload)
    state = payload.get("runtime_state")
    if not isinstance(state, dict):
        state = {}
    state = dict(state)
    state["last_turn"] = int(payload.get("turn", 0) or 0)

    if settings["mode"] == MODE_NATIVE:
        try:
            response = _run_external_framework(payload, settings)
            return _emit(response)
        except subprocess.TimeoutExpired:
            info = {
                "runtime": "framework_runtime_bridge",
                "framework": settings["framework"],
                "mode": MODE_NATIVE,
                "boxpwnr_available": _boxpwnr_available(),
                "tool_schema_version": TOOL_SCHEMA_VERSION,
                "rollout_status": "runtime_timeout",
                "runtime_error": (
                    f"external framework command timed out after "
                    f"{settings['timeout_seconds']}s"
                ),
            }
            return _emit(
                _passthrough_response(
                    observations=[],
                    done=True,
                    episode_done=False,
                    state=state,
                    info=info,
                )
            )
        except Exception as exc:
            info = {
                "runtime": "framework_runtime_bridge",
                "framework": settings["framework"],
                "mode": MODE_NATIVE,
                "boxpwnr_available": _boxpwnr_available(),
                "tool_schema_version": TOOL_SCHEMA_VERSION,
                "rollout_status": "runtime_error",
                "runtime_error": str(exc),
            }
            return _emit(
                _passthrough_response(
                    observations=[],
                    done=True,
                    episode_done=False,
                    state=state,
                    info=info,
                )
            )

    # MODE_TOOL_CALLS: parse action text and return normalized tool calls.
    action = str(payload.get("action", ""))
    parsed_calls = parse_tool_calls(action)
    tool_calls, rejected = _normalize_tool_calls(parsed_calls)
    state["tool_calls"] = len(tool_calls)
    state["rejected_calls"] = len(rejected)

    status = "ok" if tool_calls else "no_tool_call"
    if parsed_calls and not tool_calls:
        status = "parser_error"

    info = {
        "runtime": "framework_runtime_bridge",
        "framework": settings["framework"],
        "mode": MODE_TOOL_CALLS,
        "boxpwnr_available": _boxpwnr_available(),
        "tool_schema_version": TOOL_SCHEMA_VERSION,
        "parsed_calls": len(parsed_calls),
        "accepted_calls": len(tool_calls),
        "rejected_calls": len(rejected),
        "rollout_status": status,
    }
    if rejected:
        info["unsupported_tools"] = sorted(set(rejected))

    return _emit(_tool_calls_response(tool_calls=tool_calls, state=state, info=info))


if __name__ == "__main__":
    raise SystemExit(main())
