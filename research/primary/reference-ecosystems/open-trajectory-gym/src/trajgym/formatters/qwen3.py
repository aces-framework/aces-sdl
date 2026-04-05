"""Qwen3 / Qwen2.5 / OpenThinker message formatter.

Qwen3 uses ChatML-style delimiters (``<|im_start|>`` / ``<|im_end|>``)
and is largely compatible with the OpenAI function-calling schema.

Tool calls are embedded as JSON inside assistant messages, and tool
results are returned as ``tool`` role messages.
"""

import json
from typing import Any

from .base import ModelFormatter
from .tool_registry import AGENT_TOOLS


class Qwen3Formatter(ModelFormatter):
    """Formatter for Qwen3, Qwen2.5, and OpenThinker models.

    If a HuggingFace tokenizer is provided, ``format_messages`` will
    delegate to ``tokenizer.apply_chat_template`` for maximum fidelity.
    Otherwise it falls back to a manual ChatML renderer.

    Example (manual rendering)::

        <|im_start|>system
        You are a helpful assistant.
        <|im_end|>
        <|im_start|>user
        Run nmap on 10.0.0.1
        <|im_end|>
        <|im_start|>assistant
        <tool_call>
        {"name": "shell_command", "arguments": {"command": "nmap 10.0.0.1"}}
        </tool_call>
        <|im_end|>
        <|im_start|>tool
        Starting Nmap 7.94 ...
        <|im_end|>
    """

    def format_messages(self, messages: list[dict[str, Any]]) -> str:
        """Format messages into Qwen3 ChatML.

        If a tokenizer with ``apply_chat_template`` is available, it is
        used directly. Otherwise the method builds the ChatML string
        manually.
        """
        if self.tokenizer is not None and hasattr(
            self.tokenizer, "apply_chat_template"
        ):
            return self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
                tools=[t["function"] for t in AGENT_TOOLS],
            )

        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Tool calls from the assistant are wrapped in <tool_call> tags.
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                tc_parts: list[str] = []
                for tc in tool_calls:
                    fn = tc.get("function", tc)
                    tc_parts.append(
                        "<tool_call>\n"
                        + json.dumps(
                            {"name": fn["name"], "arguments": fn.get("arguments", {})},
                            ensure_ascii=False,
                        )
                        + "\n</tool_call>"
                    )
                body = (content + "\n" if content else "") + "\n".join(tc_parts)
            else:
                body = content

            # Tool results carry an optional tool_call_id for traceability.
            if role == "tool":
                name = msg.get("name", "")
                header = "<|im_start|>tool"
                if name:
                    header += f" name={name}"
                parts.append(f"{header}\n{body}\n<|im_end|>")
            else:
                parts.append(f"<|im_start|>{role}\n{body}\n<|im_end|>")

        return "\n".join(parts)

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return tools in OpenAI function-calling format (Qwen3-native)."""
        return list(AGENT_TOOLS)
