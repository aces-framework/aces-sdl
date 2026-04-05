#!/usr/bin/env python3
"""Minimal external runtime bridge for DefaultStepAgent.

Reads a JSON payload from stdin and returns:
  {
    "protocol_version": "1.0",
    "capabilities": ["tool_calls_response", "state_persistence"],
    "tool_calls_response": {
      "tool_calls": [{"name": "...", "arguments": {...}}],
      "state": {...},
      "info": {...}
    }
  }

This keeps TrajGym's local tool execution path intact while exercising
the hybrid BYO runtime hook.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trajgym.parsing import parse_tool_calls  # noqa: E402


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        print(
            json.dumps(
                {
                    "protocol_version": "1.0",
                    "capabilities": ["tool_calls_response", "state_persistence"],
                    "tool_calls_response": {
                        "tool_calls": [],
                        "info": {"runtime": "byo_example"},
                    },
                }
            )
        )
        return 0

    payload: dict[str, Any] = json.loads(raw)
    action = str(payload.get("action", ""))
    tool_calls = parse_tool_calls(action)

    state = payload.get("runtime_state")
    if not isinstance(state, dict):
        state = {}
    state["last_turn"] = payload.get("turn", 0)
    state["last_tool_calls"] = len(tool_calls)

    print(
        json.dumps(
            {
                "protocol_version": "1.0",
                "capabilities": ["tool_calls_response", "state_persistence"],
                "tool_calls_response": {
                    "tool_calls": tool_calls,
                    "state": state,
                    "info": {
                        "runtime": "byo_example",
                        "tool_calls": len(tool_calls),
                    },
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
