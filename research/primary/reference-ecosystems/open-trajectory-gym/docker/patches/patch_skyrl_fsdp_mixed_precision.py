#!/usr/bin/env python3
"""Patch SkyRL fsdp_utils.py to export MixedPrecisionPolicy.

SkyRL 0.3.1's fsdp_strategy.py imports MixedPrecisionPolicy from fsdp_utils,
but fsdp_utils only imports CPUOffloadPolicy, FSDPModule, fully_shard from
PyTorch.  This patch adds MixedPrecisionPolicy to the conditional imports.
"""
import pathlib
import sys

FSDP_UTILS_PATH = pathlib.Path(
    "/usr/local/lib/python3.12/dist-packages/skyrl_train/distributed/fsdp_utils.py"
)


def main():
    if not FSDP_UTILS_PATH.exists():
        print(f"   Patch (MixedPrecisionPolicy): SKIP - {FSDP_UTILS_PATH} not found")
        return

    content = FSDP_UTILS_PATH.read_text()

    if "MixedPrecisionPolicy" in content:
        print("   Patch (MixedPrecisionPolicy): already applied")
        return

    # Add MixedPrecisionPolicy to the >= 2.6 import branch
    old1 = (
        "from torch.distributed.fsdp import CPUOffloadPolicy, FSDPModule, fully_shard"
    )
    new1 = "from torch.distributed.fsdp import CPUOffloadPolicy, MixedPrecisionPolicy, FSDPModule, fully_shard"

    # Add to the >= 2.4 import branch
    old2 = "from torch.distributed._composable.fsdp import CPUOffloadPolicy, FSDPModule, fully_shard"
    new2 = "from torch.distributed._composable.fsdp import CPUOffloadPolicy, MixedPrecisionPolicy, FSDPModule, fully_shard"

    # Add to the fallback
    old3 = "fully_shard, FSDPModule, CPUOffloadPolicy = None, None, None"
    new3 = "fully_shard, FSDPModule, CPUOffloadPolicy, MixedPrecisionPolicy = None, None, None, None"

    patched = False
    if old1 in content:
        content = content.replace(old1, new1, 1)
        patched = True
    if old2 in content:
        content = content.replace(old2, new2, 1)
        patched = True
    if old3 in content:
        content = content.replace(old3, new3, 1)

    if patched:
        FSDP_UTILS_PATH.write_text(content)
        print("   Patch (MixedPrecisionPolicy): APPLIED")
    else:
        print("   Patch (MixedPrecisionPolicy): FAILED - import patterns not found")
        sys.exit(1)


if __name__ == "__main__":
    main()
