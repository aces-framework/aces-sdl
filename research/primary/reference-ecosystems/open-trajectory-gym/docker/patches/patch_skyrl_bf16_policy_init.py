#!/usr/bin/env python3
"""Patch SkyRL fsdp_worker.py to use configurable bf16 for train-time workers.

Problem:
SkyRL hardcodes ``bf16=False`` in policy/critic init callsites, forcing fp32
initialization and causing large transient memory spikes during FSDP2 state
loading.

Fix:
Rewrite ``bf16=False`` to ``bf16=self.cfg.trainer.bf16`` only inside
``FSDPPolicyWorkerBase`` and ``FSDPCriticWorkerBase``. Keep ref-worker behavior
unchanged.
"""
import pathlib

WORKER_PATH = pathlib.Path(
    "/usr/local/lib/python3.12/dist-packages/skyrl_train/workers/fsdp/fsdp_worker.py"
)


def main():
    if not WORKER_PATH.exists():
        print(f"   Patch (bf16 policy init): SKIP - {WORKER_PATH} not found")
        return

    content = WORKER_PATH.read_text()
    lines = content.splitlines()
    target_classes = {"FSDPPolicyWorkerBase", "FSDPCriticWorkerBase"}
    current_class = None
    changed_lines = []

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("class ") and "(" in stripped:
            current_class = stripped.split()[1].split("(")[0]

        if current_class in target_classes and "bf16=False" in line:
            lines[idx] = line.replace(
                "bf16=False",
                "bf16=self.cfg.trainer.bf16",
                1,
            )
            changed_lines.append(idx + 1)

    if changed_lines:
        WORKER_PATH.write_text("\n".join(lines) + "\n")
        print(
            "   Patch (bf16 policy init): APPLIED at lines "
            + ", ".join(str(n) for n in changed_lines)
        )
        return

    # Idempotent pass: nothing left to rewrite in targeted classes.
    print("   Patch (bf16 policy init): already applied or pattern not found")


if __name__ == "__main__":
    main()
