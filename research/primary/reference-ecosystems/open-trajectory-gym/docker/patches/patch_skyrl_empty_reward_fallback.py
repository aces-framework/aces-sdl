#!/usr/bin/env python3
"""Prevent ValueError on empty per_token_reward during step-wise trajectories.

Problem:
When step_wise_trajectories=true and a step produces empty response_ids
(model generates 0 tokens for that step), per_token_reward = [0.0] * 0 = [].
This empty list propagates to postprocess_generator_output which raises:
    ValueError: Token-level rewards must be a non-empty list.

Fix:
When per_token_reward is empty, replace it with [0.0] — a single-element
list with zero reward, preventing the ValueError while providing no learning
signal for that empty step (neutral).
"""
from __future__ import annotations

import pathlib
import sys

TARGET = pathlib.Path(
    "/usr/local/lib/python3.12/dist-packages/skyrl_train/generators/skyrl_gym_generator.py"
)
PATCH_MARKER = "Ensure per_token_reward is never empty"


def _apply(content: str) -> tuple[str, bool]:
    if PATCH_MARKER in content:
        return content, False

    old = "                # in-place update to per-token reward\n                per_step_output.reward = per_token_reward"

    new = (
        "                # Ensure per_token_reward is never empty (prevents ValueError\n"
        "                # in postprocess_generator_output when model generates no tokens for a step).\n"
        "                if not per_token_reward:\n"
        "                    per_token_reward = [0.0]\n"
        "                # in-place update to per-token reward\n"
        "                per_step_output.reward = per_token_reward"
    )

    if old not in content:
        return content, False

    return content.replace(old, new, 1), True


def main() -> int:
    if not TARGET.exists():
        print(f"SKIP: {TARGET} not found")
        return 0

    content = TARGET.read_text()
    updated, changed = _apply(content)
    if not changed:
        print("patch_skyrl_empty_reward_fallback: already applied or pattern not found")
        return 0

    TARGET.write_text(updated)
    print("patch_skyrl_empty_reward_fallback: applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
