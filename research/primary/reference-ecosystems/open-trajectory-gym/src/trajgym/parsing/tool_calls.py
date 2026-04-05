"""Model-agnostic tool call parsing for LLM output text.

Extracts structured tool calls from raw assistant text across 6 formats:
  1. Hermes/Qwen3/Nanbeige JSON: <tool_call>{"name":..., "arguments":...}</tool_call>
  2. Qwen3.5 Coder XML: <tool_call><function=name><parameter=k>v</parameter></function></tool_call>
  2b. Qwen3.5 Coder XML (bare func): <tool_call>name<parameter=k>v</parameter></tool_call>
  3. GLM-4 MoE XML: <tool_call>func<arg_key>k</arg_key><arg_value>v</arg_value></tool_call>
  4. Bare JSON fallback: {"name": "...", "arguments": {...}}
  5. Python-style calls: shell_command(command="ls -la")

This module is intentionally free of any SkyRL, environment, or agent
dependencies so it can be imported by any layer in the stack.
"""

import ast
import contextlib
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Hermes/Qwen3/Nanbeige: <tool_call>{"name": ..., "arguments": ...}</tool_call>
_HERMES_PATTERN = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)

# GLM-4 MoE XML: <tool_call>func_name<arg_key>k</arg_key><arg_value>v</arg_value>...</tool_call>
_GLM4_TC_PATTERN = re.compile(
    r"<tool_call>(\S+?)((?:<arg_key>.*?</arg_key><arg_value>.*?</arg_value>)*)\s*</tool_call>",
    re.DOTALL,
)
_GLM4_ARG_PATTERN = re.compile(
    r"<arg_key>(.*?)</arg_key><arg_value>(.*?)</arg_value>",
    re.DOTALL,
)

# Qwen3.5 Coder XML: <tool_call><function=func_name><parameter=k>v</parameter>...</function></tool_call>
_QWEN35_CODER_PATTERN = re.compile(
    r"<tool_call>\s*<function=([^>]+)>(.*?)</function>\s*</tool_call>",
    re.DOTALL,
)
_QWEN35_PARAM_PATTERN = re.compile(
    r"<parameter=([^>]+)>(.*?)</parameter>",
    re.DOTALL,
)

# Truncation-tolerant fallback: matches tool calls cut off by max_completion_length.
# Captures function name and first parameter even without closing tags.
_QWEN35_CODER_TRUNCATED_PATTERN = re.compile(
    r"<tool_call>\s*<function=([^>]+)>\s*<parameter=([^>]+)>(.*)",
    re.DOTALL,
)

# Bare-function-name variant: <tool_call>func_name<parameter=k>v</parameter>...</tool_call>
# Some models (e.g. Qwen3.5-9B SFT) drop the <function=...> wrapper but still use
# <parameter=...> tags.  Matches with optional </function> before </tool_call>.
_QWEN35_CODER_BARE_FUNC_PATTERN = re.compile(
    r"<tool_call>\s*([A-Za-z_]\w+)\s*((?:<parameter=[^>]+>.*?</parameter>\s*)*)\s*(?:</function>)?\s*</tool_call>",
    re.DOTALL,
)

# Bare JSON fallback: {"name": "...", "arguments": {...}}
# Supports one level of nested braces in arguments (e.g. {"headers": {"X-UserId": "10052"}})
_BARE_JSON_PATTERN = re.compile(
    r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{(?:[^{}]|\{[^{}]*\})*\})\s*\}',
    re.DOTALL,
)

# Thinking block pattern: <think>...</think> (Qwen3.5, Qwen3, DeepSeek-R1, etc.)
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)

# Python-style function call fallback (e.g. shell_command(command="ls -la"))
_PY_CALL_LINE_PATTERN = re.compile(r"^\s*([A-Za-z_]\w*)\((.*)\)\s*$")

# ---------------------------------------------------------------------------
# Known tool names and argument ordering
# ---------------------------------------------------------------------------

_TOOL_ARG_ORDER: dict[str, list[str]] = {
    "shell_command": ["command", "timeout"],
    "execute_command": ["command", "timeout"],
    "python_code": ["code", "timeout"],
    "read_file": ["file_path", "line_numbers"],
    "grep": ["pattern", "path", "include"],
    "file_search": ["pattern", "path"],
    "apply_patch": ["patch"],
    "flag_found": ["content"],
    "submit_flag": ["content"],
    "web_search": ["query"],
    "exec_command": ["cmd", "workdir", "yield_time"],
    "write_stdin": ["session_id", "chars", "yield_time"],
    "list_sessions": [],
    "close_session": ["session_id"],
}
_KNOWN_TOOL_NAMES = set(_TOOL_ARG_ORDER.keys())
_TOOL_CALL_HEAD_PATTERN = re.compile(r"\b([A-Za-z_]\w*)\s*\(")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _coerce_scalar(raw: str) -> Any:
    """Best-effort parse of scalar argument text."""
    text = raw.strip()
    if not text:
        return ""
    try:
        return ast.literal_eval(text)
    except Exception:
        pass
    try:
        return json.loads(text)
    except Exception:
        return text


def _parse_call_arguments(name: str, args_src: str) -> dict[str, Any]:
    """Parse python-style call arguments from raw source text."""
    args: dict[str, Any] = {}
    call_src = f"{name}({args_src})"
    try:
        parsed = ast.parse(call_src, mode="eval")
        expr = parsed.body
        if isinstance(expr, ast.Call):
            positional = []
            for node in expr.args:
                seg = ast.get_source_segment(call_src, node) or ""
                positional.append(_coerce_scalar(seg))
            ordered = _TOOL_ARG_ORDER.get(name, [])
            for idx, value in enumerate(positional):
                key = ordered[idx] if idx < len(ordered) else f"arg{idx}"
                args[key] = value
            for kw in expr.keywords:
                if kw.arg is None:
                    continue
                seg = ast.get_source_segment(call_src, kw.value) or ""
                args[kw.arg] = _coerce_scalar(seg)
            return args
    except Exception:
        pass

    # Fallback for malformed-but-common style: read_file(/path/file)
    if args_src:
        ordered = _TOOL_ARG_ORDER.get(name, [])
        key = ordered[0] if ordered else "arg0"
        args[key] = _coerce_scalar(args_src)
    return args


# Mapping from common model-generated parameter aliases to canonical names.
_PARAM_ALIASES: dict[str, dict[str, str]] = {
    "shell_command": {"param": "command", "cmd": "command", "input": "command"},
    "execute_command": {"param": "command", "cmd": "command", "input": "command"},
    "python_code": {"param": "code", "script": "code"},
    "flag_found": {"flag": "content", "value": "content", "submission": "content"},
    "submit_flag": {"flag": "content", "value": "content", "submission": "content"},
    "read_file": {"path": "file_path", "file": "file_path", "param": "file_path"},
}


def _normalize_param(tool_name: str, key: str) -> str:
    """Remap a model-generated parameter name to its canonical form."""
    return _PARAM_ALIASES.get(tool_name, {}).get(key, key)


def _looks_like_placeholder_tool_call(name: str, args: dict[str, Any]) -> bool:
    """Reject obvious instructional placeholders parsed as executable calls."""
    cmd = ""
    if name in {"shell_command", "execute_command"}:
        cmd = str(args.get("command", ""))
    elif name == "exec_command":
        cmd = str(args.get("cmd", ""))

    lower = cmd.lower()
    return bool("<target" in lower or "<target_url" in lower or "<your_" in lower)


def _scan_balanced_call(text: str, open_idx: int) -> tuple[str, int] | None:
    """Return ``(args_src, end_idx)`` for balanced ``(...)`` or ``None``."""
    if open_idx < 0 or open_idx >= len(text) or text[open_idx] != "(":
        return None
    depth = 0
    in_quote = ""
    escaped = False
    for idx in range(open_idx, len(text)):
        ch = text[idx]
        if in_quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_quote:
                in_quote = ""
            continue
        if ch in {'"', "'"}:
            in_quote = ch
            continue
        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : idx], idx + 1
    return None


def _parse_inline_python_calls(text: str) -> list[dict[str, Any]]:
    """Parse inline python-style calls embedded in prose."""
    calls: list[dict[str, Any]] = []
    seen_signatures: set[tuple[str, str]] = set()
    for match in _TOOL_CALL_HEAD_PATTERN.finditer(text):
        name = match.group(1).strip()
        if name not in _KNOWN_TOOL_NAMES:
            continue
        open_idx = match.end() - 1
        scanned = _scan_balanced_call(text, open_idx)
        if scanned is None:
            continue
        args_src, _ = scanned
        signature = (name, args_src.strip())
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        args = _parse_call_arguments(name, args_src.strip())
        if _looks_like_placeholder_tool_call(name, args):
            continue
        calls.append({"name": name, "arguments": args})
    return calls


# ---------------------------------------------------------------------------
# Parse strategy functions
# ---------------------------------------------------------------------------


def _parse_hermes_json(text: str) -> list[dict[str, Any]]:
    """Parse Hermes/Qwen3/Nanbeige JSON: <tool_call>{"name":..., "arguments":...}</tool_call>."""
    calls = []
    for m in _HERMES_PATTERN.finditer(text):
        try:
            d = json.loads(m.group(1))
            name = d.get("name", "")
            args = d.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if name in _KNOWN_TOOL_NAMES:
                calls.append({"name": name, "arguments": args})
        except json.JSONDecodeError:
            continue
    return calls


def _parse_qwen35_coder_xml(text: str) -> list[dict[str, Any]]:
    """Parse Qwen3.5 Coder XML: <tool_call><function=name><parameter=k>v</parameter></function></tool_call>.

    Also handles:
    - Bare-function-name variant: ``<tool_call>func_name<parameter=k>v</parameter></tool_call>``
      (9B models often drop the ``<function=...>`` wrapper after SFT)
    - Truncated tool calls where max_completion_length cut off
      the output before the closing tags were generated.
    """
    calls = []
    for m in _QWEN35_CODER_PATTERN.finditer(text):
        name = m.group(1).strip()
        args = {}
        for pm in _QWEN35_PARAM_PATTERN.finditer(m.group(2)):
            key = _normalize_param(name, pm.group(1).strip())
            val = pm.group(2).strip()
            with contextlib.suppress(ValueError, json.JSONDecodeError):
                val = json.loads(val)
            args[key] = val
        if name in _KNOWN_TOOL_NAMES:
            calls.append({"name": name, "arguments": args})

    # Bare-function-name fallback: <tool_call>func_name<parameter=k>v</parameter>...</tool_call>
    # Models (especially 9B SFT) sometimes drop <function=...> but keep <parameter=...>.
    if not calls:
        for m in _QWEN35_CODER_BARE_FUNC_PATTERN.finditer(text):
            name = m.group(1).strip()
            args = {}
            for pm in _QWEN35_PARAM_PATTERN.finditer(m.group(2)):
                key = _normalize_param(name, pm.group(1).strip())
                val = pm.group(2).strip()
                with contextlib.suppress(ValueError, json.JSONDecodeError):
                    val = json.loads(val)
                args[key] = val
            if name in _KNOWN_TOOL_NAMES:
                calls.append({"name": name, "arguments": args})
                logger.debug(
                    "Recovered bare-func qwen3_coder tool call: %s(%s)",
                    name,
                    list(args.keys()),
                )

    # Truncation recovery: if the text has more <tool_call> opens than
    # closes, the last tool call was likely truncated by max_completion_length.
    # Try to salvage the function name and first parameter value.
    opens = text.count("<tool_call>")
    closes = text.count("</tool_call>")
    if opens > closes:
        # Find the LAST unmatched <tool_call> block
        last_open = text.rfind("<tool_call>")
        tail = text[last_open:]
        m = _QWEN35_CODER_TRUNCATED_PATTERN.match(tail)
        if m:
            name = m.group(1).strip()
            key = m.group(2).strip()
            # Strip any trailing closing tags that might partially exist
            val = m.group(3).strip()
            for tag in ("</parameter>", "</function>", "</tool_call>"):
                val = val.split(tag)[0]
            val = val.strip()
            if name in _KNOWN_TOOL_NAMES and val:
                args = {key: val}
                calls.append({"name": name, "arguments": args})
                logger.debug(
                    "Recovered truncated qwen3_coder tool call: %s(%s=<%d chars>)",
                    name,
                    key,
                    len(val),
                )
    return calls


def _parse_glm4_xml(text: str) -> list[dict[str, Any]]:
    """Parse GLM-4 MoE XML: <tool_call>func<arg_key>k</arg_key><arg_value>v</arg_value></tool_call>."""
    calls = []
    for m in _GLM4_TC_PATTERN.finditer(text):
        name = m.group(1).strip()
        args = {}
        for am in _GLM4_ARG_PATTERN.finditer(m.group(2)):
            key = am.group(1).strip()
            val = am.group(2).strip()
            with contextlib.suppress(ValueError, json.JSONDecodeError):
                val = json.loads(val)
            args[key] = val
        if name in _KNOWN_TOOL_NAMES:
            calls.append({"name": name, "arguments": args})
    return calls


def _parse_bare_json(text: str) -> list[dict[str, Any]]:
    """Parse bare JSON fallback: {"name": "...", "arguments": {...}}."""
    calls = []
    for m in _BARE_JSON_PATTERN.finditer(text):
        name = m.group(1)
        try:
            args = json.loads(m.group(2))
        except json.JSONDecodeError:
            args = {}
        if name in _KNOWN_TOOL_NAMES:
            calls.append({"name": name, "arguments": args})
    return calls


def _parse_python_style_calls(text: str) -> list[dict[str, Any]]:
    """Parse python-style tool calls from assistant text.

    Supports lines like:
      shell_command(command="ls -la")
      read_file("/root/challenge/index.php")
      flag_found(content="HTB{...}")
    """
    calls: list[dict[str, Any]] = []
    seen_signatures: set[tuple[str, str]] = set()
    cleaned = text.replace("```python", "").replace("```json", "").replace("```", "")
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = line.lstrip("-*").strip()
        m = _PY_CALL_LINE_PATTERN.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        if name not in _TOOL_ARG_ORDER:
            continue
        args_src = m.group(2).strip()
        args = _parse_call_arguments(name, args_src)
        signature = (name, json.dumps(args, sort_keys=True))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        if _looks_like_placeholder_tool_call(name, args):
            continue
        calls.append({"name": name, "arguments": args})

    for call in _parse_inline_python_calls(cleaned):
        name = str(call.get("name", ""))
        args_src = json.dumps(call.get("arguments", {}), sort_keys=True)
        signature = (name, args_src)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        calls.append(call)

    return calls


# Ordered list of parsing strategies. Each returns List[Dict] or [].
# First match wins -- strategies are tried from most structured (Hermes JSON)
# to least structured (Python-style calls).
_PARSE_STRATEGIES = [
    _parse_hermes_json,
    _parse_qwen35_coder_xml,
    _parse_glm4_xml,
    _parse_bare_json,
    _parse_python_style_calls,
]


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    """Extract tool calls from LLM output text.

    Strips ``<think>...</think>`` blocks first to prevent regex confusion
    when thinking content contains tool-call-like patterns. The original
    text is not modified -- only the copy used for parsing is cleaned.

    Tries 5 strategies in priority order (first non-empty result wins):
    Hermes JSON, Qwen3.5 Coder XML, GLM4 XML, bare JSON, Python-style calls.

    Returns list of {"name": str, "arguments": dict} dicts.
    """
    text = _THINK_PATTERN.sub("", text)

    for strategy in _PARSE_STRATEGIES:
        calls = strategy(text)
        if calls:
            return calls

    return []
