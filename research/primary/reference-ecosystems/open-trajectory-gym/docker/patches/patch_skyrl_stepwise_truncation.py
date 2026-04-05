#!/usr/bin/env python3
"""Fix step-wise truncation in handle_filter_sampling.

Problem: When step_wise_trajectories=true, each generation produces N step entries
(not 1). The truncation at line 535 uses max_trajectories (batch_size * n_samples_per_prompt)
to cap the number of entries. With step_wise, this truncates to the first N entries
(e.g., first 4 steps of generation 1), losing the is_last_step=True entries at the
end of each generation. Result: postprocess_generator_output finds 0 last_steps,
producing empty rewards → ValueError.

Fix: When step_wise_trajectories=true, skip the max_trajectories truncation entirely.
The correct behavior is to keep ALL step entries for the selected prompts. The
postprocess_generator_output code already handles extracting last_steps correctly
when all entries are present.
"""
import sys

filepath = "/usr/local/lib/python3.12/dist-packages/skyrl_train/utils/trainer_utils.py"

try:
    with open(filepath) as f:
        content = f.read()
except FileNotFoundError:
    print(f"SKIP: {filepath} not found")
    sys.exit(0)

# Check if already patched
if (
    "skip truncation for step_wise" in content
    or "step_wise_trajectories" in content.split("max_trajectories")[1][:200]
    if "max_trajectories" in content
    else False
):
    print("patch_skyrl_stepwise_truncation: already applied")
    sys.exit(0)

old = """        if len(final_uids) > max_trajectories:
            final_output = filter_generator_output(final_output, list(range(max_trajectories)))
            final_uids = final_uids[:max_trajectories]

        return final_output, final_uids, False, None"""

new = """        # With step_wise_trajectories, entries are steps within trajectories
        # (not separate trajectories). Truncating by entry count would split
        # trajectories and lose is_last_step=True entries at the end.
        # Only truncate when NOT using step_wise_trajectories.
        _is_step_wise = bool(final_output.get("is_last_step"))
        if not _is_step_wise and len(final_uids) > max_trajectories:
            # skip truncation for step_wise — keep all steps for selected prompts
            final_output = filter_generator_output(final_output, list(range(max_trajectories)))
            final_uids = final_uids[:max_trajectories]

        return final_output, final_uids, False, None"""

if old not in content:
    print("ERROR: Could not find truncation code to patch")
    print("Looking for alternative pattern...")
    # Try to find it with different whitespace
    import re

    pattern = r"if len\(final_uids\) > max_trajectories:"
    if re.search(pattern, content):
        print(
            "Found the pattern but exact string mismatch. Attempting line-level fix..."
        )
        # Fall through to line-level replacement
        lines = content.split("\n")
        patched = False
        for i, line in enumerate(lines):
            if "if len(final_uids) > max_trajectories:" in line:
                indent = line[: len(line) - len(line.lstrip())]
                lines.insert(
                    i, f"{indent}_is_step_wise = bool(final_output.get('is_last_step'))"
                )
                lines[i + 1] = (
                    f"{indent}if not _is_step_wise and len(final_uids) > max_trajectories:"
                )
                patched = True
                break
        if patched:
            content = "\n".join(lines)
            with open(filepath, "w") as f:
                f.write(content)
            print("patch_skyrl_stepwise_truncation: applied (line-level)")
            sys.exit(0)
    print("ERROR: Could not patch")
    sys.exit(1)

content = content.replace(old, new)
with open(filepath, "w") as f:
    f.write(content)

print("patch_skyrl_stepwise_truncation: applied (step_wise truncation fix)")
