"""Devstral / Mistral message formatter.

Devstral and Mistral models enforce **strict role alternation**:
user and assistant messages must alternate, except where tool calls
and tool results are interleaved.

Key differences from OpenAI format:
- Tool invocations use Mistral's ``[TOOL_CALLS]`` prefix followed by
  a JSON array of function calls.
- ``reasoning_content`` must be merged into main ``content`` (no
  separate field).
- Consecutive assistant messages require an empty user message
  inserted between them.
"""

import json
from typing import Any

from .base import ModelFormatter
from .tool_registry import AGENT_TOOLS


class DevstralFormatter(ModelFormatter):
    """Formatter for Devstral and Mistral-family models.

    Example rendering::

        [INST] You are a helpful assistant. [/INST]
        [INST] Scan the target at 10.0.0.1 [/INST]
        [TOOL_CALLS] [{"name": "shell_command", "arguments": {"command": "nmap 10.0.0.1"}, "id": "call_0"}]
        [TOOL_RESULTS] {"call_id": "call_0", "content": "Starting Nmap 7.94 ..."}[/TOOL_RESULTS]
        The scan reveals open ports 22 and 80.
    """

    def format_messages(self, messages: list[dict[str, Any]]) -> str:
        """Format messages into Devstral/Mistral chat template.

        If a tokenizer is provided, delegates to
        ``tokenizer.apply_chat_template``. Otherwise uses manual rendering
        with strict role alternation enforcement.
        """
        if self.tokenizer is not None and hasattr(
            self.tokenizer, "apply_chat_template"
        ):
            # Merge reasoning_content into content before passing to tokenizer.
            cleaned = self._merge_reasoning(messages)
            cleaned = self._enforce_alternation(cleaned)
            return self.tokenizer.apply_chat_template(
                cleaned,
                tokenize=False,
                add_generation_prompt=False,
                tools=[t["function"] for t in AGENT_TOOLS],
            )

        # Manual rendering.
        processed = self._merge_reasoning(messages)
        processed = self._enforce_alternation(processed)

        parts: list[str] = []
        for msg in processed:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system" or role == "user":
                parts.append(f"[INST] {content} [/INST]")

            elif role == "assistant":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    calls = []
                    for i, tc in enumerate(tool_calls):
                        fn = tc.get("function", tc)
                        call_id = tc.get("id", f"call_{i}")
                        calls.append(
                            {
                                "name": fn["name"],
                                "arguments": fn.get("arguments", {}),
                                "id": call_id,
                            }
                        )
                    parts.append(
                        "[TOOL_CALLS] " + json.dumps(calls, ensure_ascii=False)
                    )
                    if content:
                        parts.append(content)
                else:
                    parts.append(content)

            elif role == "tool":
                call_id = msg.get("tool_call_id", "call_0")
                tool_result = json.dumps(
                    {"call_id": call_id, "content": content},
                    ensure_ascii=False,
                )
                parts.append(f"[TOOL_RESULTS] {tool_result}[/TOOL_RESULTS]")

        return "\n".join(parts)

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return tools in OpenAI function-calling format.

        Mistral models accept the standard schema when served via vLLM
        with ``--tool-call-parser mistral``.
        """
        return list(AGENT_TOOLS)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _merge_reasoning(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge ``reasoning_content`` into ``content``.

        Devstral does not support a separate reasoning field; we prepend
        reasoning text to the main content wrapped in ``<think>`` tags.
        """
        out: list[dict[str, Any]] = []
        for msg in messages:
            msg = dict(msg)  # shallow copy
            reasoning = msg.pop("reasoning_content", None)
            if reasoning:
                content = msg.get("content", "")
                msg["content"] = f"<think>{reasoning}</think>\n{content}"
            out.append(msg)
        return out

    @staticmethod
    def _enforce_alternation(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Insert empty user messages to satisfy strict role alternation.

        Devstral requires user/assistant roles to alternate (tool calls
        and tool results are exempt). This inserts a minimal user turn
        between consecutive assistant messages when needed.
        """
        out: list[dict[str, Any]] = []
        prev_role: str | None = None
        for msg in messages:
            role = msg.get("role", "user")
            # tool messages don't break alternation
            if role in ("tool",):
                out.append(msg)
                continue
            if role == "assistant" and prev_role == "assistant":
                out.append({"role": "user", "content": ""})
            out.append(msg)
            prev_role = role
        return out
