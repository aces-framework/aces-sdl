#!/usr/bin/env python3
"""Move prompt length check to after re-tokenization to prevent vLLM crash.

Problem (Issue #48):
In agent_loop(), the length check at line 286 fires BEFORE re-tokenization
(lines 293-299). With retokenize_chat_history=True (custom chat templates),
input_ids are overwritten with a potentially longer re-tokenized result.
The check at 286 passes on the stale value, the re-tokenized value exceeds
max_input_length, and vLLM's input_processor hard-validates → ValueError.

Crashed ONLINE_RL v3 at step 12 (32850 > 32768) and v4 at step 2 (65594 > 65536).

Fix:
Move the length check from before re-tokenization to after it — one check,
right before the vLLM generate call, always sees the actual input_ids length.
Works for both retokenize and non-retokenize paths.
"""
from __future__ import annotations

import pathlib
import sys

TARGETS = [
    pathlib.Path(
        "/usr/local/lib/python3.12/dist-packages/skyrl_train/generators/skyrl_gym_generator.py"
    ),
    pathlib.Path(__file__).resolve().parent.parent
    / "references/SkyRL-westonbrown/skyrl-train/skyrl_train/generators/skyrl_gym_generator.py",
]

PATCH_MARKER = "# MOVED: length check after re-tokenization (Issue #48)"


def _apply(content: str) -> tuple[str, bool]:
    if PATCH_MARKER in content:
        return content, False

    # Remove the original pre-retokenization length check and add it
    # after re-tokenization, right before the vLLM generate call.
    old = (
        "        while not agent_loop_state.done:\n"
        "\n"
        "            if len(agent_loop_state.input_ids) > max_input_length:\n"
        "                stop_reason = \"length\"\n"
        "                break\n"
        "\n"
        "            # 1. Generate output\n"
        "            if is_step_wise or retokenize_chat_history:\n"
        "                # re-apply whole chat template so length check is correct\n"
        "                agent_loop_state.input_ids = self.tokenizer.apply_chat_template(\n"
        "                    chat_history,\n"
        "                    chat_template=self.custom_chat_template if retokenize_chat_history else None,\n"
        "                    add_generation_prompt=True,\n"
        "                    tokenize=True,\n"
        "                    **self.generator_cfg.chat_template_kwargs,\n"
        "                )\n"
        "                agent_loop_state.loss_mask = []\n"
        "                agent_loop_state.rollout_logprobs = None\n"
        "\n"
        "            engine_input = InferenceEngineInput("
    )

    new = (
        "        while not agent_loop_state.done:\n"
        "\n"
        "            # 1. Generate output\n"
        "            if is_step_wise or retokenize_chat_history:\n"
        "                # re-apply whole chat template so length check is correct\n"
        "                agent_loop_state.input_ids = self.tokenizer.apply_chat_template(\n"
        "                    chat_history,\n"
        "                    chat_template=self.custom_chat_template if retokenize_chat_history else None,\n"
        "                    add_generation_prompt=True,\n"
        "                    tokenize=True,\n"
        "                    **self.generator_cfg.chat_template_kwargs,\n"
        "                )\n"
        "                agent_loop_state.loss_mask = []\n"
        "                agent_loop_state.rollout_logprobs = None\n"
        "\n"
        "            # MOVED: length check after re-tokenization (Issue #48)\n"
        "            # Must check AFTER re-tokenization overwrites input_ids,\n"
        "            # not before — stale input_ids caused vLLM ValueError.\n"
        "            if len(agent_loop_state.input_ids) > max_input_length:\n"
        "                stop_reason = \"length\"\n"
        "                break\n"
        "\n"
        "            engine_input = InferenceEngineInput("
    )

    if old not in content:
        return content, False

    return content.replace(old, new, 1), True


def main() -> int:
    applied = False
    for target in TARGETS:
        if not target.exists():
            continue

        content = target.read_text()
        updated, changed = _apply(content)
        if changed:
            target.write_text(updated)
            print(f"patch_skyrl_prompt_length_guard: applied to {target}")
            applied = True
        else:
            print(f"patch_skyrl_prompt_length_guard: already applied or pattern not found in {target}")

    if not applied:
        print("patch_skyrl_prompt_length_guard: no targets found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
