#!/usr/bin/env python3
"""Patch SkyRL's filter_generator_output to propagate step-wise trajectory keys.

Problem: When step_wise_trajectories=true AND dynamic_sampling.type="filter",
filter_generator_output() drops 'is_last_step' and 'trajectory_ids' keys.
postprocess_generator_output() then crashes with KeyError: 'is_last_step'.

Fix: Propagate both keys through the filter if they exist in the input.
"""
import sys

filepath = "/usr/local/lib/python3.12/dist-packages/skyrl_train/utils/trainer_utils.py"

try:
    with open(filepath) as f:
        lines = f.readlines()
except FileNotFoundError:
    print(f"SKIP: {filepath} not found")
    sys.exit(0)

# Find the return statement in filter_generator_output
in_filter_fn = False
insert_idx = None
for i, line in enumerate(lines):
    if "def filter_generator_output" in line:
        in_filter_fn = True
    if in_filter_fn and line.strip() == "return filtered":
        insert_idx = i
        break

if insert_idx is None:
    print("ERROR: Could not find return statement in filter_generator_output")
    sys.exit(1)

# Check if already patched
if any("is_last_step" in line for line in lines[insert_idx - 5 : insert_idx]):
    print("patch_skyrl_filter_stepwise: already applied")
    sys.exit(0)

patch_lines = [
    "\n",
    "    # Propagate step-wise trajectory keys (needed when step_wise_trajectories=true)\n",
    '    if output.get("is_last_step") is not None:\n',
    '        filtered["is_last_step"] = [output["is_last_step"][i] for i in kept_indices]\n',
    '    if output.get("trajectory_ids") is not None:\n',
    '        filtered["trajectory_ids"] = [output["trajectory_ids"][i] for i in kept_indices]\n',
]

lines = lines[:insert_idx] + patch_lines + lines[insert_idx:]

with open(filepath, "w") as f:
    f.writelines(lines)

print("patch_skyrl_filter_stepwise: applied")
