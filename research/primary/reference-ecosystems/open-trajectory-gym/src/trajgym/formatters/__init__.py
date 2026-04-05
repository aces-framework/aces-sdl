"""Model-specific message formatters and canonical TrajGym tool registry.

Usage::

    from trajgym.formatters import get_formatter, AGENT_TOOLS

    formatter = get_formatter("Qwen/Qwen3-8B")
    text = formatter.format_messages(messages)
    tools = formatter.get_tool_definitions()
"""

from .base import ModelFormatter
from .tool_registry import AGENT_TOOLS, get_tool_by_name, get_tools_by_names


def get_formatter(model_id: str, tokenizer=None) -> ModelFormatter:
    """Auto-detect model family and return the appropriate formatter."""
    return ModelFormatter.from_model_id(model_id, tokenizer)


__all__ = [
    "ModelFormatter",
    "get_formatter",
    "AGENT_TOOLS",
    "get_tool_by_name",
    "get_tools_by_names",
]
