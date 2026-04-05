"""Extracted helper functions for DefaultStepAgent.

Module-level utility functions that were previously methods on
DefaultStepAgent. Each function takes explicit parameters instead
of accessing ``self``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from typing import Any

from trajgym.agent.rollout_status import RolloutStatus, normalize_rollout_status
from trajgym.agent.wire_protocol import (
    RuntimeProtocolError,
    build_runtime_request,
    normalize_runtime_response,
    parse_runtime_stdout,
)

logger = logging.getLogger(__name__)

# Severity ordering for rollout statuses: higher index = more severe.
STATUS_SEVERITY: dict[str, int] = {
    RolloutStatus.OK.value: 0,
    RolloutStatus.NO_TOOL_CALL.value: 1,
    RolloutStatus.PARSER_ERROR.value: 2,
    RolloutStatus.EMPTY_ACTION_LOOP.value: 3,
    RolloutStatus.TOOL_ERROR.value: 4,
    RolloutStatus.TOOL_TIMEOUT.value: 5,
    RolloutStatus.INFRA_UNREACHABLE.value: 6,
    RolloutStatus.TARGET_MISMATCH.value: 7,
    RolloutStatus.RUNTIME_TIMEOUT.value: 8,
    RolloutStatus.RUNTIME_ERROR.value: 9,
    RolloutStatus.MAX_TURN_ABORT.value: 10,
    RolloutStatus.NON_TERMINAL_CLOSE.value: 11,
}


def upgrade_status(current: str, candidate: str) -> str:
    """Return the more severe of two rollout status strings."""
    cur_sev = STATUS_SEVERITY.get(current, 0)
    cand_sev = STATUS_SEVERITY.get(candidate, 0)
    return candidate if cand_sev > cur_sev else current


def looks_like_tool_call(text: str) -> bool:
    """Return True if text contains tool-call-like markers."""
    snippet = (text or "").strip()
    if not snippet:
        return False
    lowered = snippet.lower()
    signals = (
        "<tool_call>",
        "<function=",
        "<command",
        "<flag>",
        '"name"',
        "flag_found(",
        "submit_flag(",
        "shell_command(",
        "exec_command(",
        "python_code(",
    )
    return any(sig in lowered for sig in signals)


def status_from_tool_output(output: str) -> str | None:
    """Derive a rollout status from tool output content."""
    lowered = output.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return RolloutStatus.TOOL_TIMEOUT.value
    if (
        "connection refused" in lowered
        or "no route to host" in lowered
        or "name or service not known" in lowered
        or "temporary failure in name resolution" in lowered
        or "network is unreachable" in lowered
    ):
        return RolloutStatus.INFRA_UNREACHABLE.value
    if "target mismatch" in lowered:
        return RolloutStatus.TARGET_MISMATCH.value
    return None


def truncate_tool_output(output: str, max_chars: int) -> str:
    """Truncate tool output to max_chars with a truncation marker."""
    if max_chars <= 0:
        return output
    if len(output) <= max_chars:
        return output
    return output[:max_chars] + "\n...[tool output truncated]"


def rewrite_workspace_refs(payload: Any, workdir: str) -> Any:
    """Rewrite legacy /root/challenge paths to active challenge workdir."""
    if not workdir:
        return payload
    normalized = workdir.rstrip("/")
    if not normalized or normalized == "/root/challenge":
        return payload
    file_target = f"file://{normalized}/"

    if isinstance(payload, str):
        out = payload
        out = out.replace("file:///root/challenge/", file_target)
        out = out.replace("/root/challenge/", f"{normalized}/")
        out = out.replace("/root/challenge", normalized)
        return out
    if isinstance(payload, list):
        return [rewrite_workspace_refs(item, workdir) for item in payload]
    if isinstance(payload, dict):
        return {
            key: rewrite_workspace_refs(value, workdir)
            for key, value in payload.items()
        }
    return payload


def decode_token_ids(
    token_ids: list[int],
    tokenizer_name_or_path: str | None,
    cached_tokenizer: Any = None,
    step_debug: bool = False,
) -> tuple[str | None, Any]:
    """Decode token IDs to text using a lazily-loaded tokenizer.

    Returns (decoded_text, tokenizer) so caller can cache the tokenizer.
    """
    if not token_ids or not tokenizer_name_or_path:
        return None, cached_tokenizer
    try:
        tokenizer = cached_tokenizer
        if tokenizer is None:
            from transformers import AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_name_or_path,
                trust_remote_code=True,
            )
        decoded = tokenizer.decode(token_ids, skip_special_tokens=False)
        if isinstance(decoded, str) and decoded.strip():
            return decoded, tokenizer
    except Exception as exc:
        if step_debug:
            logger.info("Token-id decode failed: %s", exc)
    return None, cached_tokenizer


def normalize_action_text(
    action: Any,
    tokenizer_name_or_path: str | None,
    cached_tokenizer: Any = None,
    step_debug: bool = False,
) -> tuple[str, Any]:
    """Normalize model output into parseable text.

    Returns (text, tokenizer) so caller can cache the tokenizer.
    """
    if (
        isinstance(action, (list, tuple))
        and action
        and all(isinstance(x, int) for x in action)
    ):
        decoded, tok = decode_token_ids(
            list(action), tokenizer_name_or_path, cached_tokenizer, step_debug
        )
        if decoded is not None:
            return decoded, tok
        return str(action), tok

    text = str(action or "")
    stripped = text.strip()
    if re.fullmatch(r"\[\s*\d+(?:\s*,\s*\d+){8,}\s*\]", stripped):
        try:
            token_ids = [int(x) for x in re.findall(r"\d+", stripped)]
        except Exception:
            token_ids = []
        decoded, tok = decode_token_ids(
            token_ids, tokenizer_name_or_path, cached_tokenizer, step_debug
        )
        if decoded:
            return decoded, tok
        return text, tok
    return text, cached_tokenizer


def extract_fallback_shell_command(action: str) -> str | None:
    """Recover one explicit command when model skipped tool-call wrappers."""
    text = str(action or "")
    if not text.strip():
        return None

    def _quote_balanced(cmd: str) -> bool:
        single = re.sub(r"\\'", "", cmd).count("'")
        double = re.sub(r'\\"', "", cmd).count('"')
        return (single % 2 == 0) and (double % 2 == 0)

    def _clean(cmd: str) -> str | None:
        value = " ".join(str(cmd or "").split()).strip().rstrip(".,;")
        if not value:
            return None
        if "<target_url>" in value or "<url>" in value:
            return None
        if not _quote_balanced(value):
            return None
        return value

    function_patterns = (
        r"shell_command\s*\(\s*command\s*=\s*([\"'])(.+?)\1\s*\)",
        r"exec_command\s*\(\s*cmd\s*=\s*([\"'])(.+?)\1\s*\)",
    )
    for pattern in function_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            cleaned = _clean(match.group(2))
            if cleaned:
                return cleaned

    xml_match = re.search(
        r"<COMMAND(?:\s+maxtime=\d+)?>(.*?)</COMMAND>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if xml_match:
        return _clean(xml_match.group(1))

    return None


def format_hint_text(
    tool_call_format: str,
    *,
    parser_error: bool,
    target: str,
) -> str:
    """Return a format-specific tool-call hint for parser misses."""
    fmt = str(tool_call_format or "").strip().lower()
    if fmt == "command_xml":
        if parser_error:
            return (
                "Tool call parse failed. Reply with exactly one action tag and no prose:\n"
                f"<COMMAND maxtime=30>curl -s {target}</COMMAND>"
            )
        return (
            "No tool call detected. Reply with exactly one action tag:\n"
            "<COMMAND maxtime=30>command</COMMAND> or <FLAG>flag_value</FLAG>."
        )
    if fmt == "qwen3_coder":
        if parser_error:
            return (
                "Tool call parse failed. Reply with exactly one valid tool call and no prose:\n"
                f"<tool_call><function=shell_command><parameter=command>curl -s {target}</parameter></function></tool_call>"
            )
        return (
            "No tool call detected. Reply with one valid tool call in Qwen3 format:\n"
            "<tool_call><function=tool_name><parameter=arg>value</parameter></function></tool_call>"
        )
    if fmt == "glm4":
        if parser_error:
            return (
                "Tool call parse failed. Reply with exactly one valid tool call and no prose:\n"
                f"<tool_call>shell_command<arg_key>command</arg_key><arg_value>curl -s {target}</arg_value></tool_call>"
            )
        return (
            "No tool call detected. Reply with one valid tool call in GLM4 format:\n"
            "<tool_call>tool_name<arg_key>param</arg_key><arg_value>value</arg_value></tool_call>"
        )
    if parser_error:
        return (
            "Tool call parse failed. Reply with exactly one valid tool call and no prose:\n"
            f'<tool_call>{{"name":"shell_command","arguments":{{"command":"curl -s {target}"}}}}</tool_call>'
        )
    return "No tool call detected. Reply with one valid tool call in <tool_call>{...}</tool_call> format."


def run_external_runtime(
    *,
    runtime_cmd: str,
    action: str,
    turns: int,
    max_steps: int,
    target: str,
    ground_truth_flag: str,
    tool_calls_history: list[dict[str, str]],
    tool_outputs: list[str],
    all_text: str,
    runtime_state: dict[str, Any],
    prompt_messages: list[dict[str, Any]],
    challenge_id: str,
    category: str,
    difficulty: str,
    infra_type: str,
    objective: str,
    runtime_timeout_seconds: int,
    runtime_workdir: str | None,
    runtime_env: dict[str, str],
    runtime_fallback_to_parser: bool,
    challenge_workdir: str = "",
) -> tuple[dict[str, Any] | None, float]:
    """Run optional external runtime hook and return (payload, seconds)."""
    state = dict(runtime_state or {})
    if challenge_workdir:
        state.setdefault("agent_workdir", challenge_workdir)

    payload = build_runtime_request(
        action=action,
        turn=turns,
        max_steps=max_steps,
        target=target,
        ground_truth_flag=ground_truth_flag,
        tool_calls_history=tool_calls_history,
        tool_outputs=tool_outputs,
        all_text=all_text,
        runtime_state=state,
        prompt_messages=prompt_messages,
        challenge_id=challenge_id,
        category=category,
        difficulty=difficulty,
        infra_type=infra_type,
        objective=objective,
    )

    env = os.environ.copy()
    env.update(runtime_env)

    started = time.perf_counter()
    try:
        proc = subprocess.run(
            ["bash", "-c", runtime_cmd],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=runtime_timeout_seconds,
            cwd=runtime_workdir,
            env=env,
        )
    except subprocess.TimeoutExpired:
        seconds = time.perf_counter() - started
        msg = (
            f"External runtime timed out after {runtime_timeout_seconds}s: "
            f"{runtime_cmd}"
        )
        logger.warning(msg)
        if runtime_fallback_to_parser:
            return None, seconds
        return (
            {
                "passthrough": True,
                "done": True,
                "observations": [],
                "info": {
                    "rollout_status": RolloutStatus.RUNTIME_TIMEOUT.value,
                    "runtime_error": msg,
                },
            },
            seconds,
        )

    seconds = time.perf_counter() - started
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        msg = f"External runtime exited {proc.returncode}: {runtime_cmd}" + (
            f" | stderr: {stderr[:500]}" if stderr else ""
        )
        logger.warning(msg)
        if runtime_fallback_to_parser:
            return None, seconds
        return (
            {
                "passthrough": True,
                "done": True,
                "observations": [],
                "info": {
                    "rollout_status": RolloutStatus.RUNTIME_ERROR.value,
                    "runtime_error": msg,
                },
            },
            seconds,
        )

    try:
        parsed = parse_runtime_stdout(proc.stdout)
        response = normalize_runtime_response(parsed)
    except RuntimeProtocolError as exc:
        logger.warning("External runtime JSON parse failed: %s", exc)
        if runtime_fallback_to_parser:
            return None, seconds
        return (
            {
                "passthrough": True,
                "done": True,
                "observations": [],
                "info": {
                    "rollout_status": RolloutStatus.RUNTIME_ERROR.value,
                    "runtime_error": str(exc),
                },
            },
            seconds,
        )

    return response, seconds
