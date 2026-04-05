#!/usr/bin/env bash
# =============================================================================
# SFT Training → Merge → Eval Pipeline for Qwen3.5-27B
# =============================================================================
#
# End-to-end pipeline:
#   1. SFT via TRL (LoRA on BF16 model, 2x H200)
#   2. Merge LoRA adapter into base weights
#   3. Evaluate merged model on all 40 CyBench challenges via BoxPwnr
#   4. Compare against base model eval (if available)
#
# Usage:
#   bash scripts/run_sft_and_eval.sh
#
# Override defaults:
#   MODEL_PATH=/workspace/models/qwen35-27b \
#   DATA=data/sft.jsonl \
#   OUTPUT_DIR=/workspace/outputs/sft_qwen35_27b \
#   bash scripts/run_sft_and_eval.sh
#
# Skip stages:
#   SKIP_SFT=1 bash scripts/run_sft_and_eval.sh     # Skip SFT, merge existing adapter
#   SKIP_MERGE=1 bash scripts/run_sft_and_eval.sh    # Skip merge, eval existing merged model
#   SKIP_EVAL=1 bash scripts/run_sft_and_eval.sh     # Skip eval, only train + merge
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration (override via env vars)
# ---------------------------------------------------------------------------
MODEL="${MODEL:-${MODEL_PATH:-/workspace/models/qwen35-27b}}"
DATA="${DATA:-data/sft.jsonl}"
CONFIG="${CONFIG:-examples/qwen35-27b/training.yaml}"
OUTPUT="${OUTPUT:-${OUTPUT_DIR:-/workspace/outputs/sft_qwen35_27b}}"
MERGED="${MERGED:-${OUTPUT}-merged}"
EVAL_OUTPUT="${EVAL_OUTPUT:-${OUTPUT}-eval}"
CHALLENGES="${CHALLENGES:-configs/challenges/cybench.yaml}"
CHALLENGE_REGISTRY="${CHALLENGE_REGISTRY:-configs/challenges/cybench.yaml}"

# Eval settings
EVAL_PLATFORM="${EVAL_PLATFORM:-cybench}"
EVAL_MAX_TURNS="${EVAL_MAX_TURNS:-60}"
EVAL_MAX_TIME="${EVAL_MAX_TIME:-30}"
EVAL_AGENT="${EVAL_AGENT:-boxpwnr}"
EVAL_STRATEGY="${EVAL_STRATEGY:-chat_tools}"
EVAL_ATTEMPTS="${EVAL_ATTEMPTS:-1}"

# Optional: target map for port overrides (e.g., RunPod tunnels)
TARGET_MAP="${TARGET_MAP:-}"

# Skip flags
SKIP_SFT="${SKIP_SFT:-0}"
SKIP_MERGE="${SKIP_MERGE:-0}"
SKIP_EVAL="${SKIP_EVAL:-0}"

# Timestamp for logging
TS=$(date +%Y%m%d_%H%M%S)
LOG_DIR="${OUTPUT}/logs"
mkdir -p "${LOG_DIR}"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') | $*"; }

# ---------------------------------------------------------------------------
# Stage 1: SFT Training
# ---------------------------------------------------------------------------
if [ "${SKIP_SFT}" = "0" ]; then
    log "=========================================="
    log "STAGE 1: SFT Training"
    log "  Model:  ${MODEL}"
    log "  Data:   ${DATA}"
    log "  Config: ${CONFIG}"
    log "  Output: ${OUTPUT}"
    log "=========================================="

    # Verify prerequisites
    if [ ! -d "${MODEL}" ]; then
        log "ERROR: Model not found at ${MODEL}"
        exit 1
    fi
    if [ ! -f "${DATA}" ]; then
        log "ERROR: Training data not found at ${DATA}"
        exit 1
    fi
    if [ ! -f "${CONFIG}" ]; then
        log "ERROR: Config not found at ${CONFIG}"
        exit 1
    fi

    CUDA_VISIBLE_DEVICES=0,1 trajgym-train \
        --config "${CONFIG}" \
        sft \
        --model "${MODEL}" \
        --data "${DATA}" \
        --output "${OUTPUT}" \
        2>&1 | tee "${LOG_DIR}/sft_${TS}.log"

    log "SFT complete. Adapter saved to ${OUTPUT}/final/"
else
    log "Skipping SFT (SKIP_SFT=1)"
fi

# ---------------------------------------------------------------------------
# Stage 2: Merge LoRA adapter into base weights
# ---------------------------------------------------------------------------
ADAPTER_DIR="${OUTPUT}/final"

if [ "${SKIP_MERGE}" = "0" ]; then
    log "=========================================="
    log "STAGE 2: Merge LoRA → Full Weights"
    log "  Adapter: ${ADAPTER_DIR}"
    log "  Base:    ${MODEL}"
    log "  Output:  ${MERGED}"
    log "=========================================="

    if [ ! -d "${ADAPTER_DIR}" ]; then
        log "ERROR: Adapter not found at ${ADAPTER_DIR}"
        log "  Did SFT complete successfully?"
        exit 1
    fi

    trajgym-train \
        --config "${CONFIG}" \
        merge \
        --adapter "${ADAPTER_DIR}" \
        --base-model "${MODEL}" \
        --output "${MERGED}" \
        2>&1 | tee "${LOG_DIR}/merge_${TS}.log"

    log "Merge complete. Model saved to ${MERGED}/"
else
    log "Skipping merge (SKIP_MERGE=1)"
fi

# ---------------------------------------------------------------------------
# Stage 3: Evaluate on all 40 CyBench challenges
# ---------------------------------------------------------------------------
if [ "${SKIP_EVAL}" = "0" ]; then
    log "=========================================="
    log "STAGE 3: Evaluate on CyBench (40 challenges)"
    log "  Model:      ${MERGED}"
    log "  Challenges: ${CHALLENGES}"
    log "  Agent:      ${EVAL_AGENT}"
    log "  Max turns:  ${EVAL_MAX_TURNS}"
    log "  Max time:   ${EVAL_MAX_TIME}min"
    log "  Output:     ${EVAL_OUTPUT}"
    log "=========================================="

    if [ ! -d "${MERGED}" ]; then
        log "ERROR: Merged model not found at ${MERGED}"
        log "  Did merge complete successfully?"
        exit 1
    fi

    EVAL_CMD=(
        trajgym-eval run
        --model "${MERGED}"
        --output "${EVAL_OUTPUT}"
        --challenges "${CHALLENGES}"
        --platform "${EVAL_PLATFORM}"
        --strategy "${EVAL_STRATEGY}"
        --max-turns "${EVAL_MAX_TURNS}"
        --max-time "${EVAL_MAX_TIME}"
        --agent "${EVAL_AGENT}"
        --attempts "${EVAL_ATTEMPTS}"
    )

    # Add optional flags
    if [ -n "${CHALLENGE_REGISTRY}" ]; then
        EVAL_CMD+=(--challenge-registry "${CHALLENGE_REGISTRY}")
    fi
    if [ -n "${TARGET_MAP}" ]; then
        EVAL_CMD+=(--target-map "${TARGET_MAP}")
    fi

    "${EVAL_CMD[@]}" 2>&1 | tee "${LOG_DIR}/eval_${TS}.log"

    log "=========================================="
    log "EVALUATION COMPLETE"
    log "  Report: ${EVAL_OUTPUT}/eval_report.json"
    log "=========================================="

    # Print summary if report exists
    if [ -f "${EVAL_OUTPUT}/eval_report.json" ]; then
        python3 -c "
import json
with open('${EVAL_OUTPUT}/eval_report.json') as f:
    r = json.load(f)
print()
print('=== EVALUATION SUMMARY ===')
print(f'Solved: {r.get(\"solved\", \"?\")}/{r.get(\"total_challenges\", \"?\")}')
print(f'Solve rate: {r.get(\"solve_rate\", 0)*100:.1f}%')
print(f'Avg turns: {r.get(\"avg_turns\", \"?\")}')
print(f'Avg time: {r.get(\"avg_time_seconds\", \"?\")}s')
if 'per_challenge' in r:
    print()
    print('Per-challenge results:')
    for c in r['per_challenge']:
        status = 'SOLVED' if c.get('solved') else 'FAILED'
        print(f'  [{status}] {c.get(\"challenge_id\", \"?\")} ({c.get(\"turns\", \"?\")} turns, {c.get(\"time_seconds\", \"?\"):.0f}s)')
" 2>/dev/null || true
    fi
else
    log "Skipping eval (SKIP_EVAL=1)"
fi

log "Pipeline complete."
