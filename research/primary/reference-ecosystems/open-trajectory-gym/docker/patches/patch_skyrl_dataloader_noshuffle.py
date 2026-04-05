"""Patch SkyRL dataloader to disable shuffle for progressive difficulty ordering.

SkyRL's build_dataloader() in trainer_utils.py hardcodes shuffle=True for
training. This defeats progressive difficulty ordering where easy challenges
(Flag Command, It Has Begun) must be processed first to provide early flag
reward signal during LR warmup.

This patch changes shuffle=True to shuffle=False so challenges are processed
in the order they appear in the data file.

Issue: SkyRL processes hardest challenges first due to random shuffle, wasting
early training steps (with warmup LR) on unsolvable Expert challenges.
"""

import sys


def apply():
    try:
        import skyrl_train.utils.trainer_utils as tu
    except ImportError:
        print("   skyrl_train not installed — skipping")
        return True

    src_file = tu.__file__
    with open(src_file) as f:
        src = f.read()

    old = "shuffle=True if is_train else False"
    new = "shuffle=False"

    if old not in src:
        if "shuffle=False" in src:
            print("   Already patched (shuffle=False)")
            return True
        print(f"   Pattern not found in {src_file}")
        return False

    src = src.replace(old, new, 1)
    with open(src_file, "w") as f:
        f.write(src)

    print(f"   Patched {src_file}: shuffle=False for sequential difficulty ordering")
    return True


if __name__ == "__main__":
    success = apply()
    sys.exit(0 if success else 1)
