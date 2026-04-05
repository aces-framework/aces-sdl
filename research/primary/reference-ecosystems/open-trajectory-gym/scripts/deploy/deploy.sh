#!/usr/bin/env bash
# Run Qwen3.5 SFT on both B200 GPUs, then restart vLLM on GPU0 if SFT succeeds.

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/workspace/open-trajectory-gym}"
MODEL_PATH="${MODEL_PATH:-/workspace/models/qwen35-27b}"
RAW_DATA_PATH="${RAW_DATA_PATH:-${PROJECT_ROOT}/data/sft.jsonl}"
CURATED_DATA_PATH="${CURATED_DATA_PATH:-${PROJECT_ROOT}/data/sft.jsonl}"
DATA_PATH="${DATA_PATH:-${CURATED_DATA_PATH}}"
CHALLENGE_REGISTRY="${CHALLENGE_REGISTRY:-${PROJECT_ROOT}/configs/challenges/cybench.yaml}"
AUTO_CURATE_DATA="${AUTO_CURATE_DATA:-1}"
CURATE_MAX_CHARS="${CURATE_MAX_CHARS:-220000}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/workspace/outputs/sft_qwen35_27b_dualgpu}"
CONTEXT_CANDIDATES="${CONTEXT_CANDIDATES:-57344 49152 40960}"

EPOCHS="${EPOCHS:-3}"
GRAD_ACCUM="${GRAD_ACCUM:-8}"
USE_4BIT="${USE_4BIT:-0}"
USE_LIGER_KERNEL="${USE_LIGER_KERNEL:-1}"
MERGE_AFTER_SFT="${MERGE_AFTER_SFT:-1}"
TRAINING_CONFIG="${TRAINING_CONFIG:-${PROJECT_ROOT}/examples/qwen35-27b/training.yaml}"

START_VLLM_AFTER_SFT="${START_VLLM_AFTER_SFT:-1}"
VLLM_MODEL="${VLLM_MODEL:-}"
VLLM_PORT="${VLLM_PORT:-9000}"
VLLM_GPU_UTIL="${VLLM_GPU_UTIL:-0.70}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-24576}"
VLLM_MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-8}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_BASE="${OUTPUT_BASE:-/workspace/outputs}"
mkdir -p "${OUTPUT_ROOT}" "${OUTPUT_BASE}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

if [[ "${AUTO_CURATE_DATA}" == "1" ]]; then
    if [[ ! -f "${RAW_DATA_PATH}" ]]; then
        log "Missing raw SFT data: ${RAW_DATA_PATH}"
        exit 1
    fi
    log "Curating SFT data -> ${DATA_PATH} (platform=cybench, registry-filtered)"
    PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH:-}" \
    python3 "${PROJECT_ROOT}/src/trajgym/data/curate_sft_data.py" \
        --input "${RAW_DATA_PATH}" \
        --output "${DATA_PATH}" \
        --registry "${CHALLENGE_REGISTRY}" \
        --platform cybench \
        --max-chars "${CURATE_MAX_CHARS}"
fi

if [[ ! -f "${DATA_PATH}" ]]; then
    log "SFT data file not found: ${DATA_PATH}"
    exit 1
fi

if [[ "${USE_LIGER_KERNEL}" == "1" ]]; then
    if ! python3 -c "import liger_kernel" >/dev/null 2>&1; then
        log "liger-kernel not installed; disabling --use-liger-kernel."
        USE_LIGER_KERNEL="0"
    fi
fi

log "Stopping any existing vLLM/SkyRL servers before SFT ..."
pkill -f "vllm serve|trajgym.training.skyrl_vllm_server|vllm.entrypoints.openai.api_server" >/dev/null 2>&1 || true

SUCCESS_CTX=""
SUCCESS_OUTPUT=""

for CTX in ${CONTEXT_CANDIDATES}; do
    RUN_OUTPUT="${OUTPUT_ROOT}/ctx${CTX}_${TIMESTAMP}"
    LOG_PATH="${OUTPUT_BASE}/sft_qwen35_ctx${CTX}_${TIMESTAMP}.log"
    log "Starting SFT attempt at context ${CTX} (output: ${RUN_OUTPUT})"

    USE_4BIT_FLAG="--load-in-4bit"
    if [[ "${USE_4BIT}" != "1" ]]; then
        USE_4BIT_FLAG="--no-load-in-4bit"
    fi

    LIGER_FLAG=""
    if [[ "${USE_LIGER_KERNEL}" == "1" ]]; then
        LIGER_FLAG="--use-liger-kernel"
    fi

    set +e
    CUDA_VISIBLE_DEVICES=0,1 \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    TOKENIZERS_PARALLELISM=false \
    python3 "${PROJECT_ROOT}/scripts/run_sft_qwen35_dual_b200.py" \
        --model "${MODEL_PATH}" \
        --data "${DATA_PATH}" \
        --output "${RUN_OUTPUT}" \
        --max-length "${CTX}" \
        --epochs "${EPOCHS}" \
        --gradient-accumulation-steps "${GRAD_ACCUM}" \
        --max-memory-gpu0 "175GiB" \
        --max-memory-gpu1 "175GiB" \
        --attn-impl "sdpa" \
        ${USE_4BIT_FLAG} \
        ${LIGER_FLAG} \
        2>&1 | tee "${LOG_PATH}"
    RC=${PIPESTATUS[0]}
    set -e

    if [[ ${RC} -eq 0 ]]; then
        SUCCESS_CTX="${CTX}"
        SUCCESS_OUTPUT="${RUN_OUTPUT}"
        log "SFT succeeded at context ${CTX}"
        break
    fi

    if grep -Eiq "out of memory|cuda out of memory|torch\.outofmemoryerror" "${LOG_PATH}"; then
        log "OOM at context ${CTX}; trying next candidate."
        continue
    fi

    log "SFT failed for non-OOM reason at context ${CTX}. See ${LOG_PATH}"
    exit ${RC}
done

if [[ -z "${SUCCESS_CTX}" ]]; then
    log "All context candidates failed."
    exit 1
fi

log "Final SFT output: ${SUCCESS_OUTPUT}"
echo "SFT_CONTEXT=${SUCCESS_CTX}" > "${SUCCESS_OUTPUT}/run_summary.env"
echo "SFT_OUTPUT=${SUCCESS_OUTPUT}" >> "${SUCCESS_OUTPUT}/run_summary.env"

SERVE_MODEL_PATH="${SUCCESS_OUTPUT}/final"
if [[ "${MERGE_AFTER_SFT}" == "1" ]]; then
    MERGED_OUTPUT="${SUCCESS_OUTPUT}_merged_vllm"
    log "Merging SFT adapter -> ${MERGED_OUTPUT}"
    CUDA_VISIBLE_DEVICES=0,1 \
    PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH:-}" \
    python3 -m trajgym.cli.train --config "${TRAINING_CONFIG}" merge \
        --adapter "${SUCCESS_OUTPUT}/final" \
        --base-model "${MODEL_PATH}" \
        --output "${MERGED_OUTPUT}"
    SERVE_MODEL_PATH="${MERGED_OUTPUT}"
fi

if [[ -n "${VLLM_MODEL}" ]]; then
    SERVE_MODEL_PATH="${VLLM_MODEL}"
fi

if [[ "${START_VLLM_AFTER_SFT}" != "1" ]]; then
    log "START_VLLM_AFTER_SFT=0, leaving vLLM stopped."
    exit 0
fi

VLLM_LOG="${OUTPUT_BASE}/vllm_after_sft_${TIMESTAMP}.log"
log "Starting vLLM on GPU0 with model ${SERVE_MODEL_PATH} ..."

CUDA_VISIBLE_DEVICES=0 \
nohup vllm serve "${SERVE_MODEL_PATH}" \
    --host 0.0.0.0 \
    --port "${VLLM_PORT}" \
    --max-model-len "${VLLM_MAX_MODEL_LEN}" \
    --dtype bfloat16 \
    --gpu-memory-utilization "${VLLM_GPU_UTIL}" \
    --max-num-seqs "${VLLM_MAX_NUM_SEQS}" \
    --trust-remote-code \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --reasoning-parser qwen3 \
    --language-model-only \
    --enforce-eager \
    > "${VLLM_LOG}" 2>&1 &
VLLM_PID=$!
log "vLLM PID=${VLLM_PID} log=${VLLM_LOG}"

for _ in {1..60}; do
    if curl -fsS "http://127.0.0.1:${VLLM_PORT}/health" >/dev/null 2>&1; then
        log "vLLM health check passed on port ${VLLM_PORT}"
        exit 0
    fi
    if ! kill -0 "${VLLM_PID}" >/dev/null 2>&1; then
        log "vLLM process exited unexpectedly. Check ${VLLM_LOG}"
        exit 1
    fi
    sleep 5
done

log "vLLM did not become healthy within timeout. Check ${VLLM_LOG}"
exit 1
