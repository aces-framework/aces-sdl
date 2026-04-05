"""
Lossless BoxPwnr trace converter.

Converts BoxPwnr conversation traces (both tool-calling and chat-command formats)
into a unified OpenAI-compatible training format, preserving ALL native tool names.

Supported BoxPwnr tools (preserved as-is):
    shell_command, exec_command, write_stdin, python_code, flag_found,
    read_file, grep, file_search, apply_patch, web_search,
    list_sessions, close_session, execute_command

Legacy tmux tools are automatically mapped to PTY equivalents:
    tmux_send_and_read → write_stdin, tmux_read_output → write_stdin,
    tmux_wait_and_read → write_stdin, tmux_cancel_command → close_session
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from trajgym.prompts import get_canonical_system_prompt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt injected into every converted trace
# ---------------------------------------------------------------------------

CTF_SYSTEM_PROMPT = get_canonical_system_prompt()

# All known BoxPwnr tool names -- used for validation
KNOWN_TOOLS = frozenset(
    {
        "shell_command",
        "exec_command",
        "write_stdin",
        "python_code",
        "flag_found",
        "read_file",
        "grep",
        "file_search",
        "apply_patch",
        "web_search",
        "list_sessions",
        "close_session",
        "execute_command",
    }
)

# Map known corrupt/alias tool names to canonical BoxPwnr names.
# None = drop the tool call entirely (not a real tool).
TOOL_NAME_ALIASES: dict[str, str | None] = {
    # Corrupt / misspelled names
    "Bash": "shell_command",
    "bash": "shell_command",
    "shell_code": "shell_command",
    "write_kdin": "write_stdin",
    "ls_files": "file_search",
    "write_file": "apply_patch",
    "TodoWrite": None,  # Claude Code artifact, not a BoxPwnr tool
    # Legacy tmux tools → PTY equivalents
    "tmux_send_and_read": "write_stdin",
    "tmux_read_output": "write_stdin",
    "tmux_wait_and_read": "write_stdin",
    "tmux_cancel_command": "close_session",
}


def normalize_tool_name(name: str) -> str | None:
    """Normalize a tool name to its canonical BoxPwnr form.

    Returns:
        Canonical name, or None if the tool should be dropped.
    """
    # Strip tokenization artifacts like <|channel|>json suffix
    cleaned = re.sub(r"<\|[^|]+\|>.*$", "", name)
    if cleaned in KNOWN_TOOLS:
        return cleaned
    if cleaned in TOOL_NAME_ALIASES:
        return TOOL_NAME_ALIASES[cleaned]
    if name in TOOL_NAME_ALIASES:
        return TOOL_NAME_ALIASES[name]
    if name in KNOWN_TOOLS:
        return name
    logger.warning("Unknown tool name '%s' — passing through unchanged", name)
    return name


# Regex for <COMMAND ...>...</COMMAND> blocks (chat-command format)
_COMMAND_RE = re.compile(
    r"<COMMAND(?:\s+maxtime=(\d+))?>\s*\n?(.*?)\n?\s*</COMMAND>",
    re.DOTALL,
)

# Regex for <FLAG>...</FLAG> blocks
_FLAG_RE = re.compile(r"<FLAG>(.*?)</FLAG>", re.DOTALL)

# Regex for <OUTPUT>...</OUTPUT> blocks in user messages
_OUTPUT_RE = re.compile(r"<OUTPUT>(.*?)</OUTPUT>", re.DOTALL)
_STDOUT_RE = re.compile(r"<STDOUT>\s*\n?(.*?)\n?\s*</STDOUT>", re.DOTALL)
_COMMAND_ECHO_RE = re.compile(r"<COMMAND>(.*?)</COMMAND>", re.DOTALL)


# ---------------------------------------------------------------------------
# Helper: extract reasoning from Claude-style content lists
# ---------------------------------------------------------------------------


def _extract_reasoning_and_text(content: Any) -> tuple[str, str]:
    """Extract reasoning_content and text from assistant message content.

    Handles:
      - List content with {"type": "thinking", ...} items (Claude style)
      - List content with {"type": "text", ...} items
      - Plain string content
    Returns (reasoning_content, text_content).
    """
    if isinstance(content, str):
        return "", content

    if not isinstance(content, list):
        return "", str(content) if content else ""

    reasoning_parts: list[str] = []
    text_parts: list[str] = []

    for item in content:
        if isinstance(item, str):
            text_parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        item_type = item.get("type", "")
        if item_type == "thinking":
            thinking = item.get("thinking", "")
            if thinking:
                reasoning_parts.append(thinking)
        elif item_type == "text":
            text = item.get("text", "")
            if text:
                text_parts.append(text)

    return "\n".join(reasoning_parts), "\n".join(text_parts)


def _extract_user_content(content: Any) -> str:
    """Flatten user message content to a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content) if content else ""


# ---------------------------------------------------------------------------
# Chat-command format parsing
# ---------------------------------------------------------------------------


def _parse_chat_command_assistant(
    text: str,
) -> tuple[str, list[dict] | None, str | None]:
    """Parse a chat-command format assistant message.

    Returns (reasoning_text, tool_calls_or_None, flag_or_None).
    """
    # Check for flag submission
    flag_match = _FLAG_RE.search(text)
    found_flag = flag_match.group(1).strip() if flag_match else None

    # Extract command
    cmd_match = _COMMAND_RE.search(text)

    if cmd_match:
        timeout = cmd_match.group(1)  # may be None
        command = cmd_match.group(2).strip()

        # Everything before the <COMMAND> tag is reasoning
        reasoning = text[: cmd_match.start()].strip()

        args: dict[str, Any] = {"command": command}
        if timeout:
            args["timeout"] = int(timeout)

        tool_call = {
            "id": f"call_{uuid.uuid4().hex[:12]}",
            "type": "function",
            "function": {
                "name": "shell_command",
                "arguments": json.dumps(args),
            },
        }
        return reasoning, [tool_call], found_flag

    if found_flag:
        # Flag-only message (no command)
        reasoning = _FLAG_RE.sub("", text).strip()
        tool_call = {
            "id": f"call_{uuid.uuid4().hex[:12]}",
            "type": "function",
            "function": {
                "name": "flag_found",
                "arguments": json.dumps({"content": found_flag}),
            },
        }
        return reasoning, [tool_call], found_flag

    # No command and no flag -- pure text response
    return text.strip(), None, None


def _parse_chat_command_output(text: str, tool_call_id: str) -> dict:
    """Parse the <OUTPUT> block from a user message in chat-command format.

    Returns a tool-role message.
    """
    output_match = _OUTPUT_RE.search(text)
    if output_match:
        output_block = output_match.group(1)
        stdout_match = _STDOUT_RE.search(output_block)
        stdout = stdout_match.group(1).strip() if stdout_match else output_block.strip()
    else:
        # Fallback: entire text is the output
        stdout = text.strip()

    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": "shell_command",
        "content": stdout,
    }


# ---------------------------------------------------------------------------
# Core message conversion
# ---------------------------------------------------------------------------


def _is_chat_command_format(messages: list[dict]) -> bool:
    """Detect whether a trace uses chat-command format (vs tool-calling)."""
    for m in messages:
        if m.get("role") == "assistant" or m.get("type") == "AIMessage":
            # If any assistant message has tool_calls, it's tool-calling format
            if "tool_calls" in m and m["tool_calls"]:
                return False
            # If any assistant message has <COMMAND> tags, it's chat-command
            content = m.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if (
                        isinstance(item, dict)
                        and item.get("type") == "text"
                        and _COMMAND_RE.search(item.get("text", ""))
                    ):
                        return True
            elif isinstance(content, str) and _COMMAND_RE.search(content):
                return True
    return False


def _convert_tool_calling_messages(messages: list[dict]) -> list[dict]:
    """Convert tool-calling format messages, preserving native tool names."""
    converted: list[dict] = []

    # Inject system prompt
    converted.append({"role": "system", "content": CTF_SYSTEM_PROMPT})

    for m in messages:
        role = m.get("role", m.get("type", ""))

        # Normalize role from BoxPwnr type field
        if role == "HumanMessage":
            role = "user"
        elif role == "AIMessage":
            role = "assistant"
        elif role == "ToolMessage":
            role = "tool"

        if role == "system":
            # Skip original system prompt (we injected ours)
            continue

        elif role == "user":
            content = _extract_user_content(m.get("content", ""))
            if content:
                converted.append({"role": "user", "content": content})

        elif role == "assistant":
            new_msg: dict[str, Any] = {"role": "assistant"}
            content = m.get("content", "")

            # Extract reasoning
            reasoning, text = _extract_reasoning_and_text(content)
            if reasoning:
                new_msg["reasoning_content"] = reasoning
            new_msg["content"] = text if text else ""

            # Preserve tool calls with name normalization
            if "tool_calls" in m and m["tool_calls"]:
                new_msg["tool_calls"] = []
                for tc in m["tool_calls"]:
                    raw_name = tc["function"]["name"]
                    canonical = normalize_tool_name(raw_name)
                    if canonical is None:
                        # Tool should be dropped (e.g. TodoWrite)
                        logger.info("Dropping non-BoxPwnr tool call: %s", raw_name)
                        continue
                    new_tc = {
                        "id": tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                        "type": "function",
                        "function": {
                            "name": canonical,
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    new_msg["tool_calls"].append(new_tc)

            # Skip empty messages with no tool calls and no content
            if (
                not new_msg.get("tool_calls")
                and not new_msg.get("content")
                and not new_msg.get("reasoning_content")
            ):
                continue

            converted.append(new_msg)

        elif role == "tool":
            # Resolve tool name (from message or look back)
            if "name" in m:
                resolved_name = m["name"]
            else:
                resolved_name = _find_tool_name(converted, m.get("tool_call_id", ""))
            # Normalize the tool response name too
            canonical_name = normalize_tool_name(resolved_name)
            if canonical_name is None:
                # Skip tool responses for dropped tools
                logger.info(
                    "Dropping tool response for non-BoxPwnr tool: %s", resolved_name
                )
                continue

            tool_msg: dict[str, Any] = {
                "role": "tool",
                "content": m.get("content", ""),
                "name": canonical_name,
            }
            if "tool_call_id" in m:
                tool_msg["tool_call_id"] = m["tool_call_id"]
            converted.append(tool_msg)

    return converted


def _convert_chat_command_messages(messages: list[dict]) -> list[dict]:
    """Convert chat-command format messages to tool-calling format."""
    converted: list[dict] = []

    # Inject system prompt
    converted.append({"role": "system", "content": CTF_SYSTEM_PROMPT})

    # Track the last tool_call_id so we can pair outputs
    pending_tool_call_id: str | None = None
    pending_tool_name: str | None = None

    for m in messages:
        role = m.get("role", m.get("type", ""))
        if role == "HumanMessage":
            role = "user"
        elif role == "AIMessage":
            role = "assistant"

        if role == "system":
            continue

        elif role == "assistant":
            content = m.get("content", "")
            reasoning_from_list, text_from_list = _extract_reasoning_and_text(content)

            # If content was a list, use extracted text for command parsing
            text_to_parse = (
                text_from_list
                if text_from_list
                else (content if isinstance(content, str) else "")
            )

            reasoning, tool_calls, flag = _parse_chat_command_assistant(text_to_parse)

            # Merge reasoning from Claude thinking blocks
            if reasoning_from_list:
                reasoning = (
                    (reasoning_from_list + "\n\n" + reasoning).strip()
                    if reasoning
                    else reasoning_from_list
                )

            new_msg: dict[str, Any] = {"role": "assistant"}
            if reasoning:
                new_msg["reasoning_content"] = reasoning
            new_msg["content"] = ""

            if tool_calls:
                new_msg["tool_calls"] = tool_calls
                pending_tool_call_id = tool_calls[0]["id"]
                pending_tool_name = tool_calls[0]["function"]["name"]
            else:
                pending_tool_call_id = None
                pending_tool_name = None

            converted.append(new_msg)

        elif role == "user":
            content = _extract_user_content(m.get("content", ""))

            # Check if this user message is an OUTPUT response
            if pending_tool_call_id and "<OUTPUT>" in content:
                tool_msg = _parse_chat_command_output(content, pending_tool_call_id)
                tool_msg["name"] = pending_tool_name or "shell_command"
                converted.append(tool_msg)
                pending_tool_call_id = None
                pending_tool_name = None
            else:
                converted.append({"role": "user", "content": content})
                pending_tool_call_id = None
                pending_tool_name = None

    return converted


def _find_tool_name(messages: list[dict], tool_call_id: str) -> str:
    """Walk backwards through messages to find the tool name for a tool_call_id."""
    if not tool_call_id:
        return "unknown"
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                if tc.get("id") == tool_call_id:
                    return tc["function"]["name"]
    return "unknown"


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------


def _extract_metadata(
    trace_path: Path,
    stats: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build metadata dict from path structure and stats.json."""
    meta: dict[str, Any] = {"source": "boxpwnr"}

    # Extract platform and challenge from path
    # Expected: .../Platform/Challenge/traces/Timestamp
    parts = list(trace_path.parts)
    if "traces" in parts:
        idx = parts.index("traces")
        meta["challenge"] = parts[idx - 1] if idx >= 1 else "unknown"
        meta["platform"] = parts[idx - 2] if idx >= 2 else "unknown"
    else:
        logger.debug(
            "Trace path does not contain 'traces' directory, "
            "defaulting challenge/platform to 'unknown': %s",
            trace_path,
        )
        meta["challenge"] = "unknown"
        meta["platform"] = "unknown"

    if stats:
        meta["success"] = stats.get("status") == "success"
        meta["total_turns"] = stats.get("total_turns")
        meta["model"] = stats.get("model")
        meta["start_time"] = stats.get("start_time")
        meta["total_duration"] = stats.get("total_duration")

    return meta


def _extract_flag(stats: dict[str, Any] | None, messages: list[dict]) -> str | None:
    """Extract ground truth flag from stats or from FLAG tags in messages."""
    if stats:
        flag = stats.get("flag") or stats.get("ground_truth_flag")
        if flag:
            return flag

    # Scan assistant messages for <FLAG>...</FLAG>
    # (skip user/system messages — they contain the template placeholder)
    for m in messages:
        if m.get("role") != "assistant":
            continue
        content = m.get("content", "")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    match = _FLAG_RE.search(item.get("text", ""))
                    if match:
                        return match.group(1).strip()
        elif isinstance(content, str):
            match = _FLAG_RE.search(content)
            if match:
                return match.group(1).strip()

    # Scan for flag_found tool calls
    for m in messages:
        if m.get("role") == "assistant" and "tool_calls" in m:
            for tc in m.get("tool_calls", []):
                if tc.get("function", {}).get("name") == "flag_found":
                    try:
                        args = json.loads(tc["function"]["arguments"])
                        return args.get("content", "")
                    except (json.JSONDecodeError, KeyError):
                        pass

    return None


def _count_tool_steps(messages: list[dict]) -> int:
    """Count assistant messages that contain tool_calls (after conversion)."""
    return sum(
        1 for m in messages if m.get("role") == "assistant" and m.get("tool_calls")
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class BoxPwnrConverter:
    """Lossless converter for BoxPwnr traces.

    Usage::

        converter = BoxPwnrConverter()
        result = converter.convert_trace(Path("path/to/trace_dir"))
        # result is a dict with messages, metadata, ground_truth_flag, optimal_steps
    """

    def convert_trace(self, trace_path: Path) -> dict[str, Any] | None:
        """Convert a single trace directory to training format.

        Args:
            trace_path: Path to directory containing conversation.json
                        (and optionally stats.json).

        Returns:
            Converted trace dict, or None if conversion fails.
        """
        conv_file = trace_path / "conversation.json"
        stats_file = trace_path / "stats.json"

        if not conv_file.exists():
            logger.warning("No conversation.json in %s", trace_path)
            return None

        try:
            with open(conv_file) as f:
                conv = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load %s: %s", conv_file, exc)
            return None

        raw_messages = conv.get("messages", [])
        if not raw_messages:
            logger.warning("Empty messages in %s", conv_file)
            return None

        # Load stats
        stats: dict[str, Any] | None = None
        if stats_file.exists():
            try:
                with open(stats_file) as f:
                    stats = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        # Detect format and convert
        if _is_chat_command_format(raw_messages):
            messages = _convert_chat_command_messages(raw_messages)
        else:
            messages = _convert_tool_calling_messages(raw_messages)

        # Extract metadata
        metadata = _extract_metadata(trace_path, stats)

        # Extract flag
        ground_truth_flag = _extract_flag(stats, raw_messages)

        # Count tool steps for optimal_steps.
        # Only set for successful traces -- failure traces get None because
        # their step count is misleading (the splitter overwrites with the
        # min across successful siblings when available, and the reward
        # function treats None as a weak prior of 0.3).
        is_success = metadata.get("success", False)
        optimal_steps = _count_tool_steps(messages) if is_success else None

        return {
            "messages": messages,
            "metadata": metadata,
            "ground_truth_flag": ground_truth_flag,
            "optimal_steps": optimal_steps,
        }

    def convert_directory(
        self,
        input_dir: Path,
        *,
        success_only: bool = False,
        dedup: bool = False,
    ) -> tuple[list[dict], list[dict]]:
        """Convert all traces under input_dir.

        Args:
            input_dir: Root directory to scan for conversation.json files.
            success_only: If True, only return successful traces.
            dedup: If True, keep only the shortest successful trace per challenge.

        Returns:
            (success_traces, failure_traces)
        """
        # Find all conversation.json files
        conv_files = sorted(input_dir.rglob("conversation.json"))
        logger.info("Found %d conversation files under %s", len(conv_files), input_dir)

        successes: list[dict] = []
        failures: list[dict] = []
        challenge_groups: dict[str, list[dict]] = {}

        for conv_file in conv_files:
            trace_dir = conv_file.parent
            result = self.convert_trace(trace_dir)
            if result is None:
                continue

            is_success = result["metadata"].get("success", False)

            if success_only and not is_success:
                continue

            if is_success:
                if dedup:
                    key = f"{result['metadata']['platform']}:{result['metadata']['challenge']}"
                    challenge_groups.setdefault(key, []).append(result)
                else:
                    successes.append(result)
            else:
                failures.append(result)

        # Dedup: keep shortest per challenge
        if dedup:
            for _key, traces in challenge_groups.items():
                best = min(traces, key=lambda t: t.get("optimal_steps") or 9999)
                successes.append(best)

        logger.info(
            "Converted %d successes, %d failures",
            len(successes),
            len(failures),
        )
        return successes, failures
