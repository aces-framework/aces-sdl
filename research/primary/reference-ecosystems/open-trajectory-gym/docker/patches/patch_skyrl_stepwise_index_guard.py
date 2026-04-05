#!/usr/bin/env python3
"""Guard SkyRL step-wise reward writes against out-of-range token indices.

Problem:
SkyRL's step-wise reward path writes:
    per_token_reward[resp_end_idx] = float(reward)
When malformed/edge trajectories yield a resp_end_idx outside the
current token list bounds, generation crashes with:
    IndexError: list assignment index out of range

Additionally, when the model generates empty/special-token-only output
(e.g. only <|im_end|>), the vLLM server decodes with skip_special_tokens=True
and SkyRL re-encodes the empty text to output_ids=[], yielding
resp_end_idx = len([]) - 1 = -1.

With the old "skip" behavior, the reward was silently dropped.  In step-wise
mode, the LAST turn of each episode is typically the one with empty output,
and `avg_final_rewards` only counts last-step rewards.  Skipping last-step
rewards zeroes out ALL RLOO advantages (they are broadcast from last-step
to all turns), making policy_loss = 0.0 permanently.

Fix (v2):
Instead of skipping, write the reward at the last valid position in
per_token_reward.  This preserves the reward signal for gradient flow.
"""

from __future__ import annotations

import pathlib
import re
import sys

CANDIDATES = [
    pathlib.Path(
        "/usr/local/lib/python3.12/dist-packages/skyrl_train/generators/skyrl_gym_generator.py"
    ),
]

# Dynamically find reference copies
for root in ["/workspace/open-trajectory-gym", "/workspace"]:
    ref = (
        pathlib.Path(root)
        / "references/SkyRL-westonbrown/skyrl-train/skyrl_train/generators/skyrl_gym_generator.py"
    )
    if ref.exists():
        CANDIDATES.append(ref)

PATCH_MARKER = "PATCH: guard step-wise per_token_reward index"
V2_MARKER = "v2: fallback, never skip"


def _apply(content: str) -> tuple[str, int]:
    pattern = re.compile(
        r"(?P<indent>[ \t]*)per_token_reward\[resp_end_idx\]\s*=\s*float\(reward\)"
    )

    def repl(match: re.Match[str]) -> str:
        indent = match.group("indent")
        return (
            f"{indent}# {PATCH_MARKER} ({V2_MARKER})\n"
            f"{indent}if 0 <= resp_end_idx < len(per_token_reward):\n"
            f"{indent}    per_token_reward[resp_end_idx] = float(reward)\n"
            f"{indent}elif per_token_reward:\n"
            f"{indent}    # Fallback: write reward at the last valid position.\n"
            f"{indent}    # This happens when the model generates empty/special-token-only\n"
            f"{indent}    # output (resp_end_idx=-1) or overshoots the list bounds.\n"
            f"{indent}    # Skipping would zero out the reward signal entirely.\n"
            f"{indent}    fallback_idx = len(per_token_reward) - 1  # always last valid position\n"
            f"{indent}    per_token_reward[fallback_idx] = float(reward)\n"
            f"{indent}    logger.warning(\n"
            f'{indent}        "Fallback step-wise reward write: resp_end_idx=%s -> fallback_idx=%s "\n'
            f'{indent}        "len(per_token_reward)=%s reward=%s",\n'
            f"{indent}        resp_end_idx,\n"
            f"{indent}        fallback_idx,\n"
            f"{indent}        len(per_token_reward),\n"
            f"{indent}        reward,\n"
            f"{indent}    )\n"
            f"{indent}else:\n"
            f"{indent}    logger.warning(\n"
            f'{indent}        "Skipping step-wise reward write: per_token_reward empty, "\n'
            f'{indent}        "resp_end_idx=%s reward=%s",\n'
            f"{indent}        resp_end_idx,\n"
            f"{indent}        reward,\n"
            f"{indent}    )"
        )

    return pattern.subn(repl, content)


def main() -> int:
    patched_count = 0

    for filepath in CANDIDATES:
        if not filepath.exists():
            continue

        content = filepath.read_text()

        if V2_MARKER in content:
            print(f"patch_skyrl_stepwise_index_guard: v2 already applied in {filepath}")
            patched_count += 1
            continue

        # If v1 was applied, we need to replace it
        if PATCH_MARKER in content:
            print(f"patch_skyrl_stepwise_index_guard: upgrading v1 -> v2 in {filepath}")
            # Remove v1 patch to get back to original pattern
            # v1 replaced the single line with an if/else block
            # We need to find and replace the v1 block
            v1_pattern = re.compile(
                r"(?P<indent>[ \t]*)# PATCH: guard step-wise per_token_reward index\n"
                r"(?P=indent)if 0 <= resp_end_idx < len\(per_token_reward\):\n"
                r"(?P=indent)    per_token_reward\[resp_end_idx\] = float\(reward\)\n"
                r"(?P=indent)else:\n"
                r"(?P=indent)    (?:import logging as _lg\n(?P=indent)    _lg\.getLogger\(__name__\)|logger)\.warning\(\n"
                r'(?P=indent)        "Skipping step-wise reward write: resp_end_idx=%s len\(per_token_reward\)=%s",\n'
                r"(?P=indent)        resp_end_idx,\n"
                r"(?P=indent)        len\(per_token_reward\),\n"
                r"(?P=indent)    \)"
            )

            def v1_to_original(match: re.Match[str]) -> str:
                indent = match.group("indent")
                return f"{indent}per_token_reward[resp_end_idx] = float(reward)"

            content = v1_pattern.sub(v1_to_original, content)

        updated, count = _apply(content)
        if count == 0:
            print(
                f"patch_skyrl_stepwise_index_guard: pattern not found in {filepath} (no changes)"
            )
            continue

        filepath.write_text(updated)
        print(
            f"patch_skyrl_stepwise_index_guard: v2 applied to {filepath} ({count} replacements)"
        )
        patched_count += 1

    if patched_count == 0:
        print("ERROR: Could not find any SkyRL generator to patch")
        return 1

    print(f"patch_skyrl_stepwise_index_guard: {patched_count} file(s) patched (v2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
