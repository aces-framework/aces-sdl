#!/usr/bin/env python3
"""Patch #39: Free sharded_sd GPU tensor references after load_state_dict.

After model.load_state_dict(sharded_sd, assign=True), the sharded_sd dict
still holds GPU tensor references.  Without explicit cleanup, the offload/reload
cycle in fsdp2_load_full_state_dict doubles GPU memory usage (model + dict).

This patch inserts `del sharded_sd; gc.collect(); torch.cuda.empty_cache()`
immediately after load_state_dict, before the offload cycle.
"""
import importlib.util
import sys


def patch():
    # Find SkyRL's fsdp_utils.py
    spec = importlib.util.find_spec("skyrl_train.distributed.fsdp_utils")
    if spec is None or spec.origin is None:
        print("SKIP: skyrl_train.distributed.fsdp_utils not found")
        return False

    fpath = spec.origin
    with open(fpath) as f:
        content = f.read()

    # Check if already patched
    if "OPEN-CTF PATCH" in content and "del sharded_sd" in content:
        print(f"SKIP: {fpath} already patched (Issue #39)")
        return True

    # Find the target: model.load_state_dict(sharded_sd, assign=True) followed by comment
    target = "model.load_state_dict(sharded_sd, assign=True)\n"
    idx = content.find(target)
    if idx < 0:
        print(f"SKIP: Could not find target in {fpath}")
        return False

    # Insert cleanup after the load_state_dict line
    insert_after = idx + len(target)

    patch_code = (
        "\n"
        "    # [OPEN-CTF PATCH Issue #39] Free state dict GPU tensors before offload/reload cycle.\n"
        "    # Without this, sharded_sd holds refs to GPU tensors preventing memory reclaim.\n"
        "    del sharded_sd\n"
        "    import gc; gc.collect()\n"
        "    torch.cuda.empty_cache()\n"
    )

    new_content = content[:insert_after] + patch_code + content[insert_after:]

    with open(fpath, "w") as f:
        f.write(new_content)

    print(f"APPLIED: Issue #39 patch to {fpath}")
    return True


if __name__ == "__main__":
    success = patch()
    sys.exit(0 if success else 1)
