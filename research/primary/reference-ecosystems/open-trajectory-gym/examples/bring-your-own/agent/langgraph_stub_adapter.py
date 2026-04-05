#!/usr/bin/env python3
"""LangGraph stub adapter (lightweight template).

This adapter is dependency-light and protocol-safe for quick integration tests.
For strict/production behavior, use `langgraph_adapter.py`.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def main() -> int:
    request: dict[str, Any] = json.load(sys.stdin)
    challenge = request.get("challenge", {}) if isinstance(request, dict) else {}
    challenge_id = str(challenge.get("id", "")).strip() or "unknown"
    target = str(request.get("target", "")).strip()
    objective = str(request.get("objective", "")).strip()
    turn = int(request.get("turn", 0) or 0)

    response = {
        "done": False,
        "episode_done": False,
        "observations": [
            {
                "role": "user",
                "content": (
                    "LangGraph lightweight adapter active. "
                    f"challenge={challenge_id} target={target} objective_chars={len(objective)}"
                ),
            }
        ],
        "state": {"adapter": "langgraph", "last_turn": turn},
        "info": {"rollout_status": "no_tool_call", "adapter": "langgraph_lightweight"},
    }
    print(json.dumps(response, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
