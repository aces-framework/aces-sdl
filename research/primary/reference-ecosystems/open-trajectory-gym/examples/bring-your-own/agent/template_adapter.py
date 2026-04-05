#!/usr/bin/env python3
"""Generic template adapter for TRAJGYM_AGENT_MODE=native.

Copy this file and implement handle_step() with your framework's logic.
The adapter reads a JSON request from stdin and prints a JSON response
to stdout. The runtime bridge wraps the response into protocol v1.0.

Usage:
    echo '{"action":"test","turn":1,"runtime_state":{}}' | python template_runtime_adapter.py

Config:
    agent_kwargs:
      runtime_passthrough: true
      runtime_env:
        TRAJGYM_AGENT_MODE: "native"
        TRAJGYM_AGENT_CMD: "python examples/bring-your-own/agent/template_adapter.py"
"""

from __future__ import annotations

import json
import sys


def handle_step(request: dict) -> dict:
    """Process a single step from the runtime bridge.

    This is the function you customize. It receives the full runtime request
    and returns a response dict.

    Args:
        request: Runtime request with these fields:
            - action (str): Raw LLM output text (may contain tool calls)
            - turn (int): Current turn number in the episode
            - runtime_state (dict): Persistent state from previous steps
            - prompt_messages (list): Full conversation history
            - challenge (dict): {id, category, difficulty, infra_type}
            - objective (str): Challenge objective description
            - target (str): Target URL or file path
            - ground_truth_flag (str): Expected flag (if available)

    Returns:
        Response dict with:
            - done (bool): Whether the episode should end
            - episode_done (bool): Whether the flag was found
            - observations (list): Messages to append to conversation
            - state (dict): Updated state (passed back on next step)
            - info (dict): Metadata (rollout_status, etc.)
            - tool_calls (list, optional): Tool calls for the bridge to execute
    """
    action = request.get("action", "")
    turn = request.get("turn", 0)

    # --- Replace this section with your framework logic ---
    # Example: echo the action back as an observation
    return {
        "done": False,
        "episode_done": False,
        "observations": [
            {
                "role": "user",
                "content": f"[Template Adapter] Turn {turn}: received action ({len(action)} chars)",
            }
        ],
        "state": request.get("runtime_state", {}),
        "info": {"rollout_status": "ok"},
    }


def main() -> None:
    """Read request from stdin, process it, print response to stdout."""
    raw = sys.stdin.read().strip()
    if not raw:
        json.dump({"error": "empty input"}, sys.stdout)
        sys.stdout.write("\n")
        return

    try:
        request = json.loads(raw)
    except json.JSONDecodeError as e:
        json.dump({"error": f"invalid JSON: {e}"}, sys.stdout)
        sys.stdout.write("\n")
        return

    response = handle_step(request)
    json.dump(response, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
