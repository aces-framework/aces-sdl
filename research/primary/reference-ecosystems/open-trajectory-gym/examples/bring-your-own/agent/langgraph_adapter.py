#!/usr/bin/env python3
"""LangGraph native runtime adapter (strict protocol, native bridge mode).

This adapter is framework-generic for LangGraph-compatible runtimes:
- parses generic command XML tokens (<COMMAND>, <FLAG>)
- executes commands directly (returning <OUTPUT> blocks)
- returns strict passthrough_response for TrajGym runtime protocol
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import urlparse

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trajgym.formatters.tool_registry import (  # noqa: E402
    RUNTIME_TOOL_NAMES,
    TOOL_SCHEMA_VERSION,
)
from trajgym.parsing import parse_tool_calls  # noqa: E402

PROTOCOL_VERSION = "1.0"
SUPPORTED_PROTOCOL_MAJOR = 1
REQUIRED_REQUEST_CAPABILITIES = {"tool_calls_response", "state_persistence"}
_XML_TOOL_ARG_KEY = {
    "shell_command": "command",
    "execute_command": "command",
    "python_code": "code",
    "read_file": "path",
    "grep": "pattern",
    "file_search": "query",
    "exec_command": "cmd",
    "submit_flag": "content",
    "flag_found": "content",
}


def _boxpwnr_available() -> bool:
    try:
        import boxpwnr  # noqa: F401

        return True
    except Exception:
        return False


def _fail(message: str) -> int:
    print(f"langgraph_adapter: {message}", file=sys.stderr)
    return 2


def _parse_protocol_major(version: str) -> int:
    text = str(version or "").strip()
    if not text:
        raise ValueError("missing protocol_version")
    head = text.split(".", 1)[0].strip()
    if not head.isdigit():
        raise ValueError(f"invalid protocol_version={version!r}")
    return int(head)


def _validate_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Fail fast on runtime protocol drift."""
    major = _parse_protocol_major(payload.get("protocol_version", ""))
    if major != SUPPORTED_PROTOCOL_MAJOR:
        raise ValueError(
            f"unsupported protocol_version={payload.get('protocol_version')!r}; "
            f"expected major {SUPPORTED_PROTOCOL_MAJOR}.x"
        )
    request_type = str(payload.get("request_type", "")).strip()
    if request_type != "step":
        raise ValueError(f"unsupported request_type={request_type!r}; expected 'step'")

    caps = payload.get("capabilities", [])
    if caps is None:
        caps = []
    if not isinstance(caps, list):
        raise ValueError("capabilities must be a list")
    normalized_caps = {str(c).strip() for c in caps if str(c).strip()}
    missing = sorted(REQUIRED_REQUEST_CAPABILITIES - normalized_caps)
    if missing:
        raise ValueError(f"missing required request capabilities: {missing}")
    return payload


def _normalize_tool_calls(
    raw_calls: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    allowed = set(RUNTIME_TOOL_NAMES)
    accepted: list[dict[str, Any]] = []
    rejected: list[str] = []
    for call in raw_calls:
        name = str(call.get("name", "")).strip()
        args = call.get("arguments", {})
        if not name:
            continue
        if name not in allowed:
            rejected.append(name)
            continue
        if not isinstance(args, dict):
            args = {}
        accepted.append({"name": name, "arguments": args})
    return accepted, rejected


class AgentState(TypedDict):
    action: str
    workdir: str
    parsed_commands: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]  # non-executable tool calls (like submit_flag)
    executed_tool_calls: list[dict[str, Any]]  # executed shell commands
    observations: list[dict[str, str]]
    rejected: list[str]
    status: str
    timeout_seconds: int


def _parse_command_xml(
    action: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse generic command XML tool format (<COMMAND>, <FLAG>)."""
    commands: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []

    # Priority 1: Commands
    if "</COMMAND>" in action and "<COMMAND" in action:
        for match in re.finditer(
            r"<COMMAND(?:\s+maxtime=['\"]?(\d+)['\"]?)?\s*>(.*?)</COMMAND>",
            action,
            re.DOTALL,
        ):
            timeout: int | None = None
            timeout_raw = match.group(1)
            if timeout_raw:
                try:
                    timeout = int(timeout_raw)
                except ValueError:
                    timeout = None
            command = _normalize_command_text(str(match.group(2) or ""))
            if command and _is_plausible_shell_command(command):
                commands.append({"command": command, "timeout": timeout})

    # Priority 2: Flag submission (only when command is absent).
    if not commands and "<FLAG>" in action:
        flag_matches = re.finditer(r"<FLAG>([^<\n\r]*)</FLAG>", action)
        for flag_match in flag_matches:
            flag_content = str(flag_match.group(1) or "").strip()
            if _is_placeholder_flag(flag_content):
                continue
            flags.append(
                {"name": "submit_flag", "arguments": {"content": flag_content}}
            )
            break

    return commands, flags


def _normalize_command_text(raw: str) -> str:
    """Normalize command payloads like `command=\"ls -la\"` -> `ls -la`."""
    text = str(raw or "").strip()
    if not text:
        return ""

    fn_match = re.match(
        r"^(?:shell_command|execute_command)\s*\(\s*(?P<body>.+?)\s*\)\s*$",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fn_match:
        text = str(fn_match.group("body") or "").strip()

    patterns = (
        r'^(?:command|cmd)\s*=\s*"(?P<value>.*)"\s*$',
        r"^(?:command|cmd)\s*=\s*'(?P<value>.*)'\s*$",
    )
    for pattern in patterns:
        m = re.match(pattern, text, re.DOTALL)
        if m:
            text = str(m.group("value") or "").strip()
            break
    return _sanitize_command_text(text)


def _sanitize_command_text(command: str) -> str:
    """Trim malformed suffixes from model-generated command text."""
    text = str(command or "").strip()
    if not text:
        return ""

    if "<" in text:
        text = text.split("<", 1)[0].strip()
    text = text.rstrip("`;,")

    if text.endswith('"') and text.count('"') % 2 == 1:
        text = text[:-1].strip()
    if text.endswith("'") and text.count("'") % 2 == 1:
        text = text[:-1].strip()
    return text


def _is_plausible_shell_command(command: str) -> bool:
    """Reject prose fragments that should not be executed as shell commands."""
    text = _sanitize_command_text(command)
    if not text:
        return False
    lowered = text.lower()
    if any(
        phrase in lowered
        for phrase in (
            " to explore ",
            " target url",
            "api endpoints",
            " to send a ",
            "request to",
            "try to ",
        )
    ):
        return False

    parts = text.split()
    if not parts:
        return False
    token = parts[0].lower()
    if token not in {
        "curl",
        "wget",
        "python",
        "python3",
        "bash",
        "sh",
        "ls",
        "cat",
        "grep",
        "find",
        "unzip",
        "zip",
        "nmap",
        "echo",
    }:
        return False
    if token == "curl" and not re.search(
        r"https?://|localhost|127\\.0\\.0\\.1|\\s-[a-zA-Z]", text
    ):
        return False
    if token == "unzip" and not re.match(
        r"^unzip(\s+-\S+)*\s+\S+\.zip(\s+-d\s+\S+)?$", text
    ):
        return False
    return not (
        token == "zip" and not re.match(r"^zip(\s+-\S+)*\s+\S+\.zip\s+\S+", text)
    )


def _parse_xml_tool_tags(
    action: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse generic XML tool tags like <shell_command>...</shell_command>."""
    commands: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for match in re.finditer(
        r"<([A-Za-z_][A-Za-z0-9_]*)\b([^>]*)>(.*?)</\1>", action, re.DOTALL
    ):
        name = str(match.group(1) or "").strip()
        attrs = str(match.group(2) or "")
        body = str(match.group(3) or "").strip()
        if not body:
            continue
        if name in {"COMMAND", "FLAG"}:
            continue
        key = name.lower()
        if key not in _XML_TOOL_ARG_KEY:
            continue
        signature = (key, body)
        if signature in seen:
            continue
        seen.add(signature)

        timeout: int | None = None
        if key in {"shell_command", "execute_command"}:
            m = re.search(r"maxtime\s*=\s*['\"]?(\d+)", attrs, re.IGNORECASE)
            if m:
                try:
                    timeout = int(m.group(1))
                except ValueError:
                    timeout = None
            command_text = _normalize_command_text(body)
            if command_text and _is_plausible_shell_command(command_text):
                commands.append({"command": command_text, "timeout": timeout})
            continue

        arg_key = _XML_TOOL_ARG_KEY[key]
        tool_calls.append({"name": key, "arguments": {arg_key: body}})
    return commands, tool_calls


def _extract_fallback_shell_commands(action: str) -> list[str]:
    """Best-effort recovery for malformed tool-call markup."""
    text = str(action or "")
    commands: list[str] = []
    seen: set[str] = set()

    # Recover function-style calls emitted in prose blocks.
    for m in re.finditer(
        r"tool\s*call:\s*(?:shell_command|execute_command)\s+with\s+command:\s*`([^`]+)`",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        cmd = _normalize_command_text(str(m.group(1) or ""))
        if cmd and cmd not in seen and _is_plausible_shell_command(cmd):
            commands.append(cmd)
            seen.add(cmd)

    for m in re.finditer(
        r"(?:shell_command|execute_command)\s*\(\s*command\s*=\s*([\"'])(.+?)\1\s*\)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        cmd = _normalize_command_text(str(m.group(2) or ""))
        if cmd and cmd not in seen and _is_plausible_shell_command(cmd):
            commands.append(cmd)
            seen.add(cmd)

    # Recover common command-line probes even without wrapper tags.
    for pattern in (
        r"\bcurl\b[^\n`]+",
        r"\bnmap\s+[^\n`]+",
        r"\bzip\s+[^\n`]+",
        r"\bunzip\s+[^\n`]+",
        r"\bls\s+-[^\n`]+",
    ):
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            cmd = _normalize_command_text(str(m.group(0) or "").strip().rstrip(".,;"))
            if (
                cmd
                and cmd not in seen
                and "<target_url>" not in cmd.lower()
                and _is_plausible_shell_command(cmd)
            ):
                commands.append(cmd)
                seen.add(cmd)

    return commands


def _extract_latest_assistant_span(action: str) -> str:
    """Use only the newest assistant block to avoid prompt/example contamination."""
    text = str(action or "")
    marker = "<|im_start|> assistant"
    if marker not in text:
        return text
    latest = text.rsplit(marker, 1)[-1]
    if "<|im_start|> user" in latest:
        latest = latest.split("<|im_start|> user", 1)[0]
    return latest.strip()


def _is_placeholder_flag(value: str) -> bool:
    s = str(value or "").strip()
    if not s:
        return True
    lowered = s.lower()
    placeholder_tokens = (
        "...",
        "flag_value",
        "your_flag_here",
        "example",
        "placeholder",
    )
    return any(token in lowered for token in placeholder_tokens)


def _resolve_workdir(payload: dict[str, Any], state_in: dict[str, Any]) -> str:
    """Resolve per-episode workdir from runtime state or file:// target."""
    runtime_workdir = str(state_in.get("agent_workdir", "")).strip()
    if runtime_workdir:
        return runtime_workdir
    target = str(payload.get("target", "")).strip()
    if target.startswith("file://"):
        parsed = urlparse(target)
        if parsed.path:
            return parsed.path.rstrip("/") or parsed.path
    return "/root/challenge"


def _safe_timeout_seconds(state_in: dict[str, Any]) -> int:
    raw = state_in.get("agent_timeout_seconds", 30)
    try:
        timeout = int(raw)
    except (TypeError, ValueError):
        timeout = 30
    return max(1, timeout)


def _ensure_workdir(path: str) -> str:
    """Ensure adapter has a writable workdir across hosts/test sandboxes."""
    candidate = str(path or "").strip() or "/root/challenge"
    if os.path.isdir(candidate):
        return candidate
    try:
        os.makedirs(candidate, exist_ok=True)
        return candidate
    except OSError:
        pass

    fallback = os.path.join(tempfile.gettempdir(), "trajgym-runtime")
    os.makedirs(fallback, exist_ok=True)
    return fallback


def planner_node(state: AgentState) -> AgentState:
    action = _extract_latest_assistant_span(state["action"])

    # 1. Try generic command XML format first
    commands, flags = _parse_command_xml(action)

    # 2. If nothing found natively, fallback to TrajGym parser (for compatibility)
    tool_calls = flags
    rejected = []
    if not commands and not tool_calls:
        xml_commands, xml_calls = _parse_xml_tool_tags(action)
        if xml_commands or xml_calls:
            commands.extend(xml_commands)
            tool_calls.extend(xml_calls)
            state["parsed_commands"] = commands
            state["tool_calls"] = tool_calls
            state["rejected"] = rejected
            state["status"] = "ok"
            return state

        fallback_parsed = parse_tool_calls(action)
        valid_calls, rej = _normalize_tool_calls(fallback_parsed)
        rejected = rej
        for call in valid_calls:
            if call["name"] in ("shell_command", "execute_command"):
                cmd = _normalize_command_text(str(call["arguments"].get("command", "")))
                timeout = call["arguments"].get("timeout")
                if cmd and _is_plausible_shell_command(cmd):
                    commands.append({"command": cmd, "timeout": timeout})
            else:
                tool_calls.append(call)

    if not commands and not tool_calls:
        for cmd in _extract_fallback_shell_commands(action):
            commands.append({"command": cmd, "timeout": None})

    status = "ok" if (commands or tool_calls) else "no_tool_call"

    state["parsed_commands"] = commands
    state["tool_calls"] = tool_calls
    state["rejected"] = rejected
    state["status"] = status
    return state


def executor_node(state: AgentState) -> AgentState:
    commands = state.get("parsed_commands", [])
    observations = state.get("observations", [])
    executed_tool_calls = state.get("executed_tool_calls", [])
    workdir = state.get("workdir") or "/root/challenge"
    default_timeout = state.get("timeout_seconds", 30)

    for cmd_info in commands:
        command_str = cmd_info.get("command", "")
        timeout = cmd_info.get("timeout") or default_timeout
        executed_tool_calls.append(
            {
                "name": "shell_command",
                "arguments": {
                    "command": command_str,
                    "timeout": int(timeout),
                },
            }
        )

        start_t = time.monotonic()
        try:
            proc = subprocess.run(
                ["bash", "-c", command_str],
                capture_output=True,
                text=True,
                cwd=workdir,
                timeout=timeout,
            )
            stdout = proc.stdout + (proc.stderr if proc.stderr else "")
            exit_code = proc.returncode
            timeout_reason = ""
            status = "success" if exit_code == 0 else "failed"
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if exc.stdout else ""
            if exc.stderr:
                stdout += "\n" + exc.stderr.decode()
            exit_code = 124
            timeout_reason = "Command timed out"
            status = "timeout"
        except Exception as exc:
            stdout = str(exc)
            exit_code = 1
            timeout_reason = ""
            status = "error"

        duration = time.monotonic() - start_t

        # Keep command-output framing stable for prompt conditioning.
        output_content = (
            "<OUTPUT>\n"
            f"<COMMAND>{command_str}</COMMAND>\n"
            f"<STDOUT>\n{stdout}</STDOUT>\n"
            f"<EXIT_CODE>{exit_code}</EXIT_CODE>\n"
            f"<DURATION>{duration:.2f}s</DURATION>\n"
            f"<STATUS>{status}</STATUS>\n"
        )
        if timeout_reason:
            output_content += f"<MESSAGE>{timeout_reason}</MESSAGE>\n"
        output_content += "</OUTPUT>"

        observations.append({"role": "user", "content": output_content})

    state["observations"] = observations
    state["executed_tool_calls"] = executed_tool_calls
    return state


def run_planner_graph(
    action: str, workdir: str, timeout_seconds: int
) -> tuple[list[dict[str, str]], list[dict[str, Any]], str, list[str]]:

    initial_state: AgentState = {
        "action": action,
        "workdir": workdir,
        "parsed_commands": [],
        "tool_calls": [],
        "executed_tool_calls": [],
        "observations": [],
        "rejected": [],
        "status": "pending",
        "timeout_seconds": timeout_seconds,
    }

    if LANGGRAPH_AVAILABLE:
        workflow = StateGraph(AgentState)
        workflow.add_node("planner", planner_node)
        workflow.add_node("executor", executor_node)

        workflow.set_entry_point("planner")
        # Go to executor if commands were parsed, else END
        workflow.add_conditional_edges(
            "planner",
            lambda s: "executor" if s.get("parsed_commands") else END,
            {"executor": "executor", END: END},
        )
        workflow.add_edge("executor", END)

        app = workflow.compile()
        final_state = app.invoke(initial_state)
    else:
        # Fallback if bare-metal execution doesn't have langgraph
        s1 = planner_node(initial_state)
        final_state = executor_node(s1) if s1.get("parsed_commands") else s1

    return (
        final_state.get("observations", []),
        list(final_state.get("executed_tool_calls", []))
        + list(final_state.get("tool_calls", [])),
        final_state.get("status", "error"),
        final_state.get("rejected", []),
    )


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return _fail("empty stdin payload")

    try:
        payload: dict[str, Any] = json.loads(raw)
        payload = _validate_request(payload)
    except Exception as exc:
        return _fail(f"invalid JSON input: {exc}")

    action = str(payload.get("action", ""))

    state_in = payload.get("runtime_state")
    if not isinstance(state_in, dict):
        state_in = {}
    workdir = _ensure_workdir(_resolve_workdir(payload, state_in))
    timeout_seconds = _safe_timeout_seconds(state_in)

    # Execute the native planner graph
    observations, tool_calls, status, rejected = run_planner_graph(
        action, workdir, timeout_seconds
    )
    done = False
    episode_done = False
    submitted_flag: str | None = None

    for call in tool_calls:
        name = str(call.get("name", "")).strip()
        if name in {"submit_flag", "flag_found"}:
            args = call.get("arguments", {})
            if isinstance(args, dict):
                submitted_flag = str(args.get("content", "")).strip()
            else:
                submitted_flag = str(args).strip()
            break

    ground_truth = str(payload.get("ground_truth_flag", "")).strip()
    max_steps = max(1, int(payload.get("max_steps", 1) or 1))
    turn = max(0, int(payload.get("turn", 0) or 0))
    if submitted_flag is not None:
        if ground_truth and submitted_flag == ground_truth:
            observations.append(
                {
                    "role": "user",
                    "content": f"Correct! Flag verified: {submitted_flag}",
                }
            )
            episode_done = True
            done = True
        else:
            observations.append(
                {
                    "role": "user",
                    "content": f"Incorrect submission: {submitted_flag}",
                }
            )
            done = turn >= max_steps

    if turn >= max_steps:
        done = True
        if status == "ok" and not episode_done:
            status = "max_turn_abort"

    state = dict(state_in)
    state["last_turn"] = int(payload.get("turn", 0) or 0)
    state["last_tool_calls"] = len(tool_calls)
    state["rejected_calls"] = len(rejected)
    framework_name = (
        str(os.getenv("TRAJGYM_AGENT_FRAMEWORK", "langgraph")).strip() or "langgraph"
    )
    adapter_name = (
        str(os.getenv("TRAJGYM_AGENT_ADAPTER", "langgraph_adapter")).strip()
        or "langgraph_adapter"
    )
    state["framework"] = framework_name
    state["adapter"] = adapter_name

    info: dict[str, Any] = {
        "runtime": adapter_name,
        "framework": framework_name,
        "mode": "native",
        "rollout_status": status,
        "boxpwnr_available": _boxpwnr_available(),
        "tool_schema_version": TOOL_SCHEMA_VERSION,
        "accepted_calls": len(tool_calls),
        "rejected_calls": len(rejected),
    }
    if rejected:
        info["unsupported_tools"] = sorted(set(rejected))

    if status == "no_tool_call" and not observations:
        observations = [
            {
                "role": "user",
                "content": (
                    "No actionable command found. Reply with exactly one "
                    "<COMMAND maxtime=30>...</COMMAND> or <FLAG>...</FLAG>."
                ),
            }
        ]

    # Return passthrough_response because this adapter owns command execution.
    response = {
        "protocol_version": PROTOCOL_VERSION,
        "capabilities": ["passthrough_response", "state_persistence"],
        "passthrough": True,
        "passthrough_response": {
            "done": bool(done),
            "episode_done": bool(episode_done),
            "observations": observations,
            "tool_calls": tool_calls,
            "state": state,
            "info": info,
        },
    }

    print(json.dumps(response, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
