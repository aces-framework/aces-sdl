"""Shared utilities for SFT data processing."""

from __future__ import annotations

import json
from typing import Any


def normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize messages for tokenizer.apply_chat_template().

    Fixes:
    - tool_calls[].function.arguments: JSON string -> dict
    - Missing content fields: None -> ""
    - tool role messages: ensure tool_call_id present
    """
    normalized = []
    for msg in messages:
        msg = dict(msg)  # shallow copy

        # Ensure content is a string (some traces have None)
        if msg.get("content") is None:
            msg["content"] = ""

        # Normalize tool_calls arguments from JSON strings to dicts
        if "tool_calls" in msg and msg["tool_calls"]:
            new_tool_calls = []
            for tc in msg["tool_calls"]:
                tc = dict(tc)
                if "function" in tc:
                    fn = dict(tc["function"])
                    args = fn.get("arguments")
                    if isinstance(args, str):
                        try:
                            fn["arguments"] = json.loads(args)
                        except (json.JSONDecodeError, TypeError):
                            fn["arguments"] = {"raw": args}
                    elif args is None:
                        fn["arguments"] = {}
                    tc["function"] = fn
                new_tool_calls.append(tc)
            msg["tool_calls"] = new_tool_calls

        normalized.append(msg)
    return normalized
