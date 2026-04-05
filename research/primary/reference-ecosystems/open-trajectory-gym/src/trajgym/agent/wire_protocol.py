"""Versioned BYO runtime protocol helpers for DefaultStepAgent."""

from __future__ import annotations

import json
from typing import Any

from .rollout_status import RolloutStatus, normalize_rollout_status

RUNTIME_PROTOCOL_VERSION = "1.0"
RUNTIME_REQUEST_CAPABILITIES = (
    "tool_calls_response",
    "passthrough_response",
    "state_persistence",
)
RUNTIME_REQUIRED_REQUEST_CAPABILITIES = {
    "tool_calls_response",
    "state_persistence",
}
RUNTIME_SUPPORTED_PROTOCOL_MAJOR = 1
RUNTIME_SUPPORTED_CAPABILITIES = {
    "tool_calls_response",
    "passthrough_response",
    "state_persistence",
}


class RuntimeProtocolError(ValueError):
    """Raised when runtime request/response violates the protocol schema."""


def _parse_protocol_major(version: str) -> int:
    """Parse semantic version major component."""
    text = str(version or "").strip()
    if not text:
        raise RuntimeProtocolError("runtime response missing protocol_version")
    head = text.split(".", 1)[0].strip()
    if not head.isdigit():
        raise RuntimeProtocolError(f"invalid protocol_version: {version!r}")
    return int(head)


def build_runtime_request(
    *,
    action: str,
    turn: int,
    max_steps: int,
    target: str,
    ground_truth_flag: str,
    tool_calls_history: list[dict[str, Any]],
    tool_outputs: list[str],
    all_text: str,
    runtime_state: dict[str, Any],
    prompt_messages: list[dict[str, Any]] | None = None,
    challenge_id: str = "",
    category: str = "",
    difficulty: str = "",
    infra_type: str = "",
    objective: str = "",
) -> dict[str, Any]:
    """Build protocol-versioned request payload for BYO runtime command."""
    prompt_messages = list(prompt_messages or [])
    return {
        "protocol_version": RUNTIME_PROTOCOL_VERSION,
        "request_type": "step",
        "capabilities": list(RUNTIME_REQUEST_CAPABILITIES),
        "action": str(action),
        "turn": int(turn),
        "max_steps": int(max_steps),
        "target": str(target),
        "ground_truth_flag": str(ground_truth_flag),
        "tool_calls_history": list(tool_calls_history),
        "tool_outputs": list(tool_outputs),
        "all_text": str(all_text),
        "runtime_state": dict(runtime_state),
        "prompt_messages": prompt_messages,
        "challenge": {
            "id": str(challenge_id),
            "category": str(category),
            "difficulty": str(difficulty),
            "infra_type": str(infra_type),
        },
        "objective": str(objective),
    }


def parse_runtime_stdout(stdout: str) -> dict[str, Any]:
    """Parse runtime stdout as JSON object (supports final-line JSON)."""
    text = (stdout or "").strip()
    if not text:
        raise RuntimeProtocolError("Runtime command returned empty stdout.")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    raise RuntimeProtocolError("Runtime stdout did not contain a JSON object.")


def normalize_runtime_request(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize BYO runtime request payload.

    Compatibility behavior:
    - If protocol fields are absent, treat as legacy request and inject
      protocol defaults.
    - If protocol fields are present, enforce strict validation.
    """
    if not isinstance(raw, dict):
        raise RuntimeProtocolError("runtime request must be a JSON object")

    has_protocol_fields = any(
        key in raw for key in ("protocol_version", "request_type", "capabilities")
    )
    if not has_protocol_fields:
        normalized = dict(raw)
        normalized["protocol_version"] = RUNTIME_PROTOCOL_VERSION
        normalized["request_type"] = "step"
        normalized["capabilities"] = list(RUNTIME_REQUEST_CAPABILITIES)
        return normalized

    protocol_version = str(raw.get("protocol_version") or "").strip()
    protocol_major = _parse_protocol_major(protocol_version)
    if protocol_major != RUNTIME_SUPPORTED_PROTOCOL_MAJOR:
        raise RuntimeProtocolError(
            f"unsupported protocol_version={protocol_version!r}; "
            f"expected major {RUNTIME_SUPPORTED_PROTOCOL_MAJOR}.x"
        )

    request_type = str(raw.get("request_type") or "").strip().lower()
    if request_type != "step":
        raise RuntimeProtocolError(
            f"unsupported request_type={request_type!r}; expected 'step'"
        )

    capabilities = raw.get("capabilities", [])
    if capabilities is None:
        capabilities = []
    if not isinstance(capabilities, list):
        raise RuntimeProtocolError("runtime request 'capabilities' must be a list")
    normalized_capabilities = [str(x).strip() for x in capabilities if str(x).strip()]
    unknown_capabilities = [
        cap
        for cap in normalized_capabilities
        if cap not in RUNTIME_SUPPORTED_CAPABILITIES
    ]
    if unknown_capabilities:
        raise RuntimeProtocolError(
            f"runtime request has unsupported capabilities: {unknown_capabilities}"
        )

    missing_required = sorted(
        cap
        for cap in RUNTIME_REQUIRED_REQUEST_CAPABILITIES
        if cap not in normalized_capabilities
    )
    if missing_required:
        raise RuntimeProtocolError(
            f"runtime request missing required capabilities: {missing_required}"
        )

    normalized = dict(raw)
    normalized["protocol_version"] = protocol_version
    normalized["request_type"] = "step"
    normalized["capabilities"] = normalized_capabilities
    return normalized


def _normalize_observations(raw: Any) -> list[dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise RuntimeProtocolError("runtime response 'observations' must be a list")

    observations: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise RuntimeProtocolError("runtime observation must be an object")
        role = str(item.get("role", "user"))
        content = str(item.get("content", ""))
        observations.append({"role": role, "content": content})
    return observations


def _normalize_tool_calls(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise RuntimeProtocolError("runtime response 'tool_calls' must be a list")

    tool_calls: list[dict[str, Any]] = []
    for call in raw:
        if not isinstance(call, dict):
            raise RuntimeProtocolError("runtime tool_call must be an object")
        name = str(call.get("name", "")).strip()
        if not name:
            raise RuntimeProtocolError("runtime tool_call.name must be non-empty")
        arguments = call.get("arguments", {})
        if not isinstance(arguments, dict):
            raise RuntimeProtocolError("runtime tool_call.arguments must be an object")
        tool_calls.append({"name": name, "arguments": arguments})
    return tool_calls


def normalize_runtime_response(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize BYO runtime response payload."""
    if not isinstance(raw, dict):
        raise RuntimeProtocolError("runtime response must be a JSON object")

    protocol_version = str(raw.get("protocol_version") or "").strip()
    protocol_major = _parse_protocol_major(protocol_version)
    if protocol_major != RUNTIME_SUPPORTED_PROTOCOL_MAJOR:
        raise RuntimeProtocolError(
            f"unsupported protocol_version={protocol_version!r}; "
            f"expected major {RUNTIME_SUPPORTED_PROTOCOL_MAJOR}.x"
        )
    capabilities = raw.get("capabilities", [])
    if capabilities is None:
        capabilities = []
    if not isinstance(capabilities, list):
        raise RuntimeProtocolError("runtime response 'capabilities' must be a list")
    normalized_capabilities = [str(x).strip() for x in capabilities if str(x).strip()]
    unknown_capabilities = [
        cap
        for cap in normalized_capabilities
        if cap not in RUNTIME_SUPPORTED_CAPABILITIES
    ]
    if unknown_capabilities:
        raise RuntimeProtocolError(
            f"runtime response has unsupported capabilities: {unknown_capabilities}"
        )

    passthrough = bool(raw.get("passthrough", False))
    if passthrough and "passthrough_response" not in normalized_capabilities:
        raise RuntimeProtocolError(
            "runtime response uses passthrough=true but omits capability "
            "'passthrough_response'"
        )
    if (not passthrough) and "tool_calls_response" not in normalized_capabilities:
        raise RuntimeProtocolError(
            "runtime response omits capability 'tool_calls_response'"
        )

    payload_key = "passthrough_response" if passthrough else "tool_calls_response"
    if payload_key not in raw:
        raise RuntimeProtocolError(
            f"runtime response missing required '{payload_key}' object"
        )
    payload = raw.get(payload_key)
    if not isinstance(payload, dict):
        raise RuntimeProtocolError(
            f"runtime response '{payload_key}' must be an object"
        )

    info = payload.get("info") or {}
    if not isinstance(info, dict):
        raise RuntimeProtocolError(f"{payload_key}.info must be an object")

    observations = _normalize_observations(payload.get("observations"))
    tool_calls = _normalize_tool_calls(payload.get("tool_calls"))
    state = payload.get("state")
    if state is None:
        state = {}
    if not isinstance(state, dict):
        raise RuntimeProtocolError(f"{payload_key}.state must be an object")
    done = bool(payload.get("done", False))
    episode_done = bool(payload.get("episode_done", False))

    all_text_append = payload.get("all_text_append")
    if all_text_append is not None:
        all_text_append = str(all_text_append)

    normalized_info = dict(info)
    raw_status = normalized_info.get("rollout_status")
    status_default = (
        RolloutStatus.OK if raw_status in (None, "") else RolloutStatus.RUNTIME_ERROR
    )
    normalized_info["runtime_protocol_version"] = protocol_version
    normalized_info["runtime_capabilities"] = list(normalized_capabilities)
    normalized_info["rollout_status"] = normalize_rollout_status(
        raw_status,
        default=status_default,
    )

    return {
        "protocol_version": protocol_version,
        "capabilities": list(normalized_capabilities),
        "passthrough": passthrough,
        "done": done,
        "episode_done": episode_done,
        "observations": observations,
        "tool_calls": tool_calls,
        "state": state,
        "all_text_append": all_text_append,
        "info": normalized_info,
    }
