#!/usr/bin/env bash
# =============================================================================
# GEPA Prompt Evolution — Flag Command Example
# =============================================================================
#
# Runs GEPA (Stage 3) against a single HackTheBox "[Very Easy] Flag Command"
# challenge to evolve a system prompt that helps the model solve:
#
#   HTML page  ->  discover JS import  ->  GET /api/options  ->
#   find secret command  ->  submit flag
#
# GEPA creates two dspy.LM objects pointing at the same vLLM endpoint:
#   - Agent LM:      temperature=0.7, max_tokens=4096
#   - Reflection LM: temperature=1.0, max_tokens=32000
# No second server needed.
#
# Prerequisites:
#   1. vLLM serving any supported model on port 8001
#   2. Flag Command container running on port 32810
#   3. pip install -e ".[gepa]"  (installs dspy>=3.1.0, gepa>=0.0.26)
#
# Usage (from repo root):
#   bash examples/gepa/run.sh --model openai/<your-model-id>
#
# Options:
#   --model MODEL_ID    Model identifier for dspy.LM (required)
#   --port PORT         vLLM server port (default: 8001)
#   --target-port PORT  Challenge container port (default: 32810)
#   --budget BUDGET     GEPA budget: light|medium|heavy (default: light)
#   --output DIR        Output directory (default: outputs/gepa_flag_command)
#
# Output:
#   outputs/gepa_flag_command/
#     optimized_prompt.txt   - The evolved system prompt
#     gepa_results.json      - Scores per candidate
#     gepa_logs/             - Optimizer traces
#
# =============================================================================

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────

MODEL_ID=""
REFLECTION_MODEL=""
VLLM_PORT=8001
TARGET_PORT=32810
BUDGET="light"
OUTPUT_DIR="outputs/gepa_flag_command"
AGENT_CLASS=""
SEED_PRESET=""
DISABLE_THINKING=""
THINKING_BUDGET=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ── Parse args ───────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case $1 in
        --model)            MODEL_ID="$2";         shift 2 ;;
        --reflection-model) REFLECTION_MODEL="$2";  shift 2 ;;
        --port|--vllm-port) VLLM_PORT="$2";        shift 2 ;;
        --target-port)      TARGET_PORT="$2";      shift 2 ;;
        --budget)           BUDGET="$2";           shift 2 ;;
        --output)           OUTPUT_DIR="$2";       shift 2 ;;
        --agent)            AGENT_CLASS="$2";      shift 2 ;;
        --seed-preset)      SEED_PRESET="$2";      shift 2 ;;
        --disable-thinking) DISABLE_THINKING="1";  shift 1 ;;
        --thinking-budget)  THINKING_BUDGET="$2";  shift 2 ;;
        -h|--help)
            head -n 38 "${BASH_SOURCE[0]}" | tail -n +2 | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "${MODEL_ID}" ]]; then
    echo "Error: --model is required"
    echo "Usage: bash examples/gepa/run.sh --model openai/qwen35-27b"
    exit 1
fi

# ── Preflight checks ────────────────────────────────────────────────────────

echo "============================================================"
echo "GEPA Flag Command Example"
echo "============================================================"
echo "  Agent model:      ${MODEL_ID}"
echo "  Reflection model: ${REFLECTION_MODEL:-"(same as agent)"}"
echo "  vLLM:             http://localhost:${VLLM_PORT}/v1"
echo "  Target:           http://localhost:${TARGET_PORT}"
echo "  Budget:           ${BUDGET}"
if [[ -n "${AGENT_CLASS}" ]]; then
    echo "  Agent:          ${AGENT_CLASS}"
fi
echo "  Output:           ${OUTPUT_DIR}"
echo "============================================================"

# Check vLLM server
echo ""
echo "[1/3] Checking vLLM server on port ${VLLM_PORT}..."
if curl -sf "http://localhost:${VLLM_PORT}/v1/models" > /dev/null 2>&1; then
    echo "  OK — vLLM is serving"
else
    echo "  FAIL — vLLM not reachable on port ${VLLM_PORT}"
    echo "  Start it with:"
    echo "    vllm serve <model_path> --port ${VLLM_PORT} --dtype bfloat16 \\"
    echo "      --gpu-memory-utilization 0.50 --trust-remote-code"
    exit 1
fi

# Check challenge container
echo "[2/3] Checking Flag Command on port ${TARGET_PORT}..."
if curl -sf "http://localhost:${TARGET_PORT}" > /dev/null 2>&1; then
    echo "  OK — Flag Command is running"
else
    echo "  FAIL — Flag Command not reachable on port ${TARGET_PORT}"
    echo "  Start it with:"
    echo "    trajgym-challenges setup --challenge '[Very Easy] Flag Command'"
    exit 1
fi

# Check dependencies
echo "[3/3] Checking GEPA dependencies..."
if python3 -c "import dspy; import gepa" 2>/dev/null; then
    echo "  OK — dspy + gepa installed"
else
    echo "  FAIL — missing dependencies"
    echo "  Install with: pip install -e '.[gepa]'"
    exit 1
fi

# ── Patch target port in challenge data ──────────────────────────────────────

DATA_FILE="${SCRIPT_DIR}/challenge.jsonl"

CLEANUP_FILES=""

if [[ "${TARGET_PORT}" != "32810" ]]; then
    echo ""
    echo "Patching target port: 32810 -> ${TARGET_PORT}"
    TEMP_DATA=$(mktemp)
    sed "s|localhost:32810|localhost:${TARGET_PORT}|g" "${DATA_FILE}" > "${TEMP_DATA}"
    DATA_FILE="${TEMP_DATA}"
    CLEANUP_FILES="${TEMP_DATA}"
fi

# ── Write fast config ────────────────────────────────────────────────────────
# max_metric_calls=2 gives 1 seed eval + 1 reflection cycle (~15 min).
# Increase to 10-20 for more thorough optimization.

GEPA_CONFIG=$(mktemp)
cat > "${GEPA_CONFIG}" <<EOF
gepa:
  max_iters: 8
  max_tokens: 6144
  max_metric_calls: 3
EOF

# Seed prompt preset (e.g. web_ctf for web challenges).
if [[ -n "${SEED_PRESET}" ]]; then
    cat >> "${GEPA_CONFIG}" <<EOF
  seed_prompt_preset: ${SEED_PRESET}
EOF
fi

# Thinking control for smaller models where <think> blocks consume
# the entire token budget.
if [[ -n "${DISABLE_THINKING}" ]]; then
    cat >> "${GEPA_CONFIG}" <<EOF
  disable_thinking: true
EOF
elif [[ -n "${THINKING_BUDGET}" ]]; then
    cat >> "${GEPA_CONFIG}" <<EOF
  thinking_token_budget: ${THINKING_BUDGET}
EOF
fi

# When using a reasoning model for reflection (e.g. GPT-5.2 Codex),
# disable temperature (unsupported) and cap max_tokens.
if [[ -n "${REFLECTION_MODEL}" && "${REFLECTION_MODEL}" == azure/* ]]; then
    cat >> "${GEPA_CONFIG}" <<EOF
  reflection_temperature: null
  reflection_max_tokens: 16000
EOF
fi

CLEANUP_FILES="${CLEANUP_FILES} ${GEPA_CONFIG}"
trap "rm -f ${CLEANUP_FILES}" EXIT

# ── Run GEPA ─────────────────────────────────────────────────────────────────

echo ""
echo "Starting GEPA prompt evolution..."
echo ""

cd "${REPO_ROOT}"

# Build the CLI command
GEPA_CMD=(
    trajgym-train --config "${GEPA_CONFIG}" gepa
    --model "${MODEL_ID}"
    --data "${DATA_FILE}"
    --output "${OUTPUT_DIR}"
    --budget "${BUDGET}"
    --challenge-registry configs/challenges/cybench.yaml
)

if [[ -n "${AGENT_CLASS}" ]]; then
    GEPA_CMD+=(--agent "${AGENT_CLASS}")
fi

if [[ -n "${REFLECTION_MODEL}" ]]; then
    GEPA_CMD+=(--reflection-model "${REFLECTION_MODEL}")
fi

OPENAI_API_BASE="http://localhost:${VLLM_PORT}/v1" \
OPENAI_API_KEY="dummy" \
"${GEPA_CMD[@]}"

# ── Report ───────────────────────────────────────────────────────────────────

echo ""
echo "============================================================"
echo "GEPA complete"
echo "============================================================"

if [[ -f "${OUTPUT_DIR}/optimized_prompt.txt" ]]; then
    echo ""
    echo "Evolved prompt:"
    echo "------------------------------------------------------------"
    cat "${OUTPUT_DIR}/optimized_prompt.txt"
    echo ""
    echo "------------------------------------------------------------"
fi

if [[ -f "${OUTPUT_DIR}/gepa_results.json" ]]; then
    echo ""
    echo "Results: ${OUTPUT_DIR}/gepa_results.json"
fi

if [[ -d "${OUTPUT_DIR}/gepa_logs" ]]; then
    echo "Logs:    ${OUTPUT_DIR}/gepa_logs/"
fi

echo ""
echo "Done."
