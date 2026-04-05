#!/usr/bin/env python3
"""Diagnostic + fix patch: log loss_mask stats and fall back to action_mask when all-zero.

Purpose: Root-cause AND fix policy_loss=0.0 and policy_entropy=0.0.

Both policy_loss and policy_entropy use masked_mean(tensor, loss_mask).
When loss_mask is all zeros, masked_mean returns 0.0 (clamp(min=1.0) denominator).
This patch:
  1. Logs tensor stats for diagnosis (LOSS_DIAG)
  2. Falls back to action_mask when loss_mask is all zeros (FIX)

The fallback is safe: action_mask has 1s for ALL response tokens (output + obs),
while loss_mask has 1s only for model-output tokens. Training on obs tokens
is suboptimal but far better than zero gradient.

Applied to _forward_backward_micro() right before the policy loss function call.
Handles both pip-installed and editable/reference SkyRL installs.
"""
import os
import sys

MARKER = "# DIAG: loss_mask/advantages stats"

# Search both pip-installed and reference locations
CANDIDATES = [
    "/usr/local/lib/python3.12/dist-packages/skyrl_train/workers/worker.py",
    # Reference copy (editable install / local dev)
]

# Dynamically find the reference copy
for root in ["/workspace/open-trajectory-gym", "/workspace"]:
    ref = os.path.join(
        root, "references/SkyRL-westonbrown/skyrl-train/skyrl_train/workers/worker.py"
    )
    if os.path.exists(ref):
        CANDIDATES.append(ref)

# All possible target patterns
TARGET_PATTERNS = [
    "policy_loss, loss_metrics = current_loss_fn(",
    "policy_loss, clip_ratio = self.policy_loss_fn(",
]

patched_count = 0

for filepath in CANDIDATES:
    if not os.path.exists(filepath):
        continue

    with open(filepath) as f:
        content = f.read()

    if MARKER in content:
        print(f"patch_skyrl_loss_diagnostics: already applied in {filepath}")
        patched_count += 1
        continue

    # Find target line
    target = None
    for pattern in TARGET_PATTERNS:
        for indent_str in ["            ", "        ", "                "]:
            candidate = f"{indent_str}{pattern}"
            if candidate in content:
                target = candidate
                break
        if target:
            break

    if target is None:
        print(f"SKIP: could not find policy_loss line in {filepath}")
        continue

    indent = target[: len(target) - len(target.lstrip())]

    # Check if action_mask is extracted as a local variable
    has_local_action_mask = "action_mask = experience.action_mask" in content
    am_ref = (
        "action_mask"
        if has_local_action_mask
        else "(experience.action_mask if hasattr(experience, 'action_mask') and experience.action_mask is not None else None)"
    )

    diag_code = f"""{indent}{MARKER}
{indent}import logging as _diag_logging
{indent}_diag_logger = _diag_logging.getLogger("skyrl_train.workers.loss_diag")
{indent}_action_mask = {am_ref}
{indent}_lm_sum = loss_mask.sum().item() if loss_mask is not None else "None"
{indent}_lm_shape = tuple(loss_mask.shape) if loss_mask is not None else "None"
{indent}_lm_any = bool(loss_mask.any().item()) if loss_mask is not None else "None"
{indent}_am_sum = _action_mask.sum().item() if _action_mask is not None else "None"
{indent}_adv_sum = advantages.sum().item() if advantages is not None else "None"
{indent}_adv_abs_max = advantages.abs().max().item() if advantages is not None else "None"
{indent}_adv_shape = tuple(advantages.shape) if advantages is not None else "None"
{indent}_old_lp_shape = tuple(old_action_log_probs.shape) if old_action_log_probs is not None else "None"
{indent}_num_act = num_actions
{indent}_diag_logger.warning(
{indent}    "LOSS_DIAG: loss_mask sum=%s shape=%s any_nonzero=%s action_mask_sum=%s | "
{indent}    "advantages sum=%s abs_max=%s shape=%s | "
{indent}    "num_actions=%s old_lp_shape=%s",
{indent}    _lm_sum, _lm_shape, _lm_any, _am_sum,
{indent}    _adv_sum, _adv_abs_max, _adv_shape,
{indent}    _num_act, _old_lp_shape,
{indent})
{indent}# FIX: Fall back to action_mask when loss_mask is all zeros.
{indent}# This prevents masked_mean from returning 0.0 (zero gradient).
{indent}if loss_mask is not None and not loss_mask.any():
{indent}    if _action_mask is not None and _action_mask.any():
{indent}        _diag_logger.warning(
{indent}            "LOSS_DIAG_FIX: loss_mask all-zero, falling back to action_mask "
{indent}            "(sum=%s). This micro-batch would have produced zero gradient.",
{indent}            _am_sum,
{indent}        )
{indent}        loss_mask = _action_mask.float()
"""

    content = content.replace(target, diag_code + target)

    with open(filepath, "w") as f:
        f.write(content)

    print(f"patch_skyrl_loss_diagnostics: applied to {filepath}")
    patched_count += 1

if patched_count == 0:
    print("ERROR: Could not find any SkyRL worker.py to patch")
    sys.exit(1)
else:
    print(f"patch_skyrl_loss_diagnostics: {patched_count} file(s) patched")
