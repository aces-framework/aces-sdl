#!/bin/bash
# Apply runtime patches for non-SkyRL dependencies (vLLM, Ray, flash_attn).
#
# SkyRL-specific fixes are baked into the fork:
# https://github.com/westonbrown/SkyRL (branch: open-ctf/v0.3.1-patched).
# This script only patches the remaining external packages.
#
# Usage: bash docker/patches/apply_all_patches.sh

PATCH_DIR="$(cd "$(dirname "$0")" && pwd)"

PASS=0
FAIL=0
CRITICAL_FAIL=0

run_patch() {
    local label="$1"
    local critical="$2"  # "critical" or "optional"
    shift 2
    if "$@"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "   *** FAILED: $label ***"
        if [ "$critical" = "critical" ]; then
            CRITICAL_FAIL=$((CRITICAL_FAIL + 1))
        fi
    fi
}

echo "Applying runtime patches from $PATCH_DIR..."
echo ""

# --- vLLM compatibility ---

# 6. vLLM 0.16+ compat shims (SkyRL expects 0.13-0.15 import paths)
run_patch "vllm_compat_shims" critical python3 "$PATCH_DIR/patch_vllm_compat_shims.py"

# 17. vLLM memory profiling assertion (unified memory GPUs: other processes
#     release memory during profiling, causing false AssertionError)
run_patch "vllm_memory_assert" critical python3 "$PATCH_DIR/patch_vllm_memory_assert.py"

# --- Ray compatibility ---

# 8. Ray 2.54+ compat (ray.experimental.collective.util removed)
run_patch "ray_collective_compat" optional python3 "$PATCH_DIR/patch_ray_collective_compat.py"

# --- Stub packages ---

# 9. flash_attn stub (real flash_attn not compiled for target GPU arch)
run_patch "flash_attn_stub" optional python3 "$PATCH_DIR/patch_flash_attn_stub.py"

# --- SkyRL generator ---

# 48. Post-retokenization prompt length guard (prevents vLLM crash when
#     re-tokenized input_ids exceed max_input_length after custom template)
run_patch "skyrl_prompt_length_guard" critical python3 "$PATCH_DIR/patch_skyrl_prompt_length_guard.py"

# --- SkyRL dataloader ---

# 10. Disable dataloader shuffle for progressive difficulty ordering
run_patch "skyrl_dataloader_noshuffle" optional python3 "$PATCH_DIR/patch_skyrl_dataloader_noshuffle.py"

# --- Cleanup ---
echo ""
echo "Clearing __pycache__..."
SITE_PACKAGES="$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))' 2>/dev/null || echo '/usr/local/lib/python3.12/dist-packages')"
for pkg in vllm ray flash_attn; do
    find "$SITE_PACKAGES/$pkg" -name "*.pyc" -delete 2>/dev/null || true
done
echo "   Done"

# --- Summary ---
echo ""
TOTAL=$((PASS + FAIL))
echo "Patch summary: $PASS/$TOTAL passed, $FAIL failed ($CRITICAL_FAIL critical)"
if [ "$CRITICAL_FAIL" -gt 0 ]; then
    echo "ERROR: $CRITICAL_FAIL critical patch(es) failed — training may not work."
    exit 1
elif [ "$FAIL" -gt 0 ]; then
    echo "WARNING: $FAIL optional patch(es) failed — check logs above."
else
    echo "All patches applied successfully."
fi
