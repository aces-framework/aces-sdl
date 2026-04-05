"""GLM-4.7 message formatter.

GLM-4 uses a distinctive chat template with ``<|assistant|>``,
``<|user|>``, ``<|system|>``, and ``<|observation|>`` role tokens.

Key differences from OpenAI format:
- Tool results use the ``observation`` role instead of ``tool``.
- Function calls use ``<|assistant|>tool_name\\n{json_args}`` format.
- Interleaved thinking uses a dedicated section.
"""

import json
from typing import Any

from .base import ModelFormatter
from .tool_registry import AGENT_TOOLS


class GLM4Formatter(ModelFormatter):
    """Formatter for GLM-4.7 and related ChatGLM models.

    Example rendering::

        <|system|>
        You are a helpful assistant.
        <|user|>
        Scan the target at 10.0.0.1
        <|assistant|>shell_command
        {"command": "nmap 10.0.0.1"}
        <|observation|>
        Starting Nmap 7.94 ...
        <|assistant|>
        The scan reveals open ports 22 and 80.
    """

    def format_messages(self, messages: list[dict[str, Any]]) -> str:
        """Format messages into GLM-4 chat template.

        If a tokenizer is provided, delegates to
        ``tokenizer.apply_chat_template``. Otherwise uses manual rendering.
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

            # Map tool results to GLM's observation role.
            if role == "tool":
                parts.append(f"<|observation|>\n{content}")
                continue

            # Assistant messages with tool calls use the function-call format.
            tool_calls = msg.get("tool_calls")
            if role == "assistant" and tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", tc)
                    name = fn["name"]
                    args = fn.get("arguments", {})
                    args_str = json.dumps(args, ensure_ascii=False)
                    parts.append(f"<|assistant|>{name}\n{args_str}")
                # If the message also has content (e.g. reasoning), append it.
                if content:
                    parts.append(f"<|assistant|>\n{content}")
                continue

            # Regular messages.
            glm_role = {
                "system": "system",
                "user": "user",
                "assistant": "assistant",
            }.get(role, role)
            parts.append(f"<|{glm_role}|>\n{content}")

        return "\n".join(parts)

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return tools in OpenAI function-calling format.

        GLM-4 accepts the standard schema when tools are passed via API.
        """
        return list(AGENT_TOOLS)
