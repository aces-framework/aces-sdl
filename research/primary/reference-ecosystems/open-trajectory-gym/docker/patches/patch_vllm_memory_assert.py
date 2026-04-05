#!/usr/bin/env python3
"""Patch vLLM v1 gpu_worker.py to tolerate free-memory increases during profiling.

On NVIDIA GB10 (DGX Spark) with unified memory, other processes (Docker containers,
Ray workers) may release GPU memory while vLLM is profiling during initialization.
This causes an AssertionError because vLLM expects free memory to only decrease
(due to model loading). We convert the hard assertion to a warning + adjustment.
"""

import pathlib
import sys


def _find_gpu_worker():
    """Dynamically locate vllm/v1/worker/gpu_worker.py."""
    try:
        import vllm

        return pathlib.Path(vllm.__file__).parent / "v1" / "worker" / "gpu_worker.py"
    except ImportError:
        return None


FILEPATH = _find_gpu_worker()
if FILEPATH is None or not FILEPATH.exists():
    print(
        "   Patch (vllm memory assert): SKIP - vllm not installed or gpu_worker.py not found"
    )
    sys.exit(0)

FILEPATH = str(FILEPATH)

MARKER = "Memory profiling: free memory increased"
ASSERT_NEEDLE = "assert self.init_snapshot.free_memory >= free_gpu_memory"

with open(FILEPATH) as f:
    lines = f.readlines()

# Check if already patched
content = "".join(lines)
if MARKER in content:
    print("Already patched!")
    sys.exit(0)

if ASSERT_NEEDLE not in content:
    print(f"ERROR: Could not find assertion needle in {FILEPATH}")
    sys.exit(1)

# Find the assertion block (starts at 'assert self.init_snapshot...' and ends at closing ')')
assert_start = None
assert_end = None
paren_depth = 0
for i, line in enumerate(lines):
    if ASSERT_NEEDLE in line:
        assert_start = i
        paren_depth = line.count("(") - line.count(")")
        if paren_depth <= 0:
            assert_end = i + 1
            break
        continue
    if assert_start is not None and assert_end is None:
        paren_depth += line.count("(") - line.count(")")
        if paren_depth <= 0:
            assert_end = i + 1
            break

if assert_start is None or assert_end is None:
    print("ERROR: Could not locate assertion block boundaries")
    sys.exit(1)

print(f"Found assertion at lines {assert_start+1}-{assert_end}")

# Get indentation from the assertion line
indent = lines[assert_start][
    : len(lines[assert_start]) - len(lines[assert_start].lstrip())
]

replacement = f"""{indent}if self.init_snapshot.free_memory < free_gpu_memory:
{indent}    # GB10 unified-memory fix: other processes may release memory
{indent}    # during profiling. Adjust snapshot so KV-cache math uses the
{indent}    # current (higher) free memory. This is safe.
{indent}    import logging as _lg
{indent}    _lg.getLogger("vllm").warning(
{indent}        "Memory profiling: free memory increased from %s GiB to "
{indent}        "%s GiB during model load (other process released memory). "
{indent}        "Adjusting init_snapshot.",
{indent}        format_gib(self.init_snapshot.free_memory),
{indent}        format_gib(free_gpu_memory),
{indent}    )
{indent}    # Update the snapshot's free_memory field
{indent}    snap = self.init_snapshot
{indent}    if hasattr(snap, '_replace'):
{indent}        self.init_snapshot = snap._replace(free_memory=free_gpu_memory)
{indent}    else:
{indent}        snap.free_memory = free_gpu_memory
"""

new_lines = lines[:assert_start] + [replacement] + lines[assert_end:]

with open(FILEPATH, "w") as f:
    f.writelines(new_lines)

print(
    f"PATCHED: Replaced assertion at lines {assert_start+1}-{assert_end} with warning+adjustment"
)
