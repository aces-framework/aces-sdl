#!/usr/bin/env bash
# =============================================================================
# 2-Challenge E2E Smoke Test for Online RL Pipeline
# =============================================================================
#
# Verifies the full pipeline works before a production run:
#   1. Generates 2-sample training data (web challenges only)
#   2. Starts vLLM server (if not already running)
#   3. Runs 3 GRPO training steps with full trajectory logging
#   4. Validates output: checkpoints, trajectories, rewards
#
# Challenges used:
#   - [Very Easy] Flag Command   (port 32810, web)
#   - [Easy] Labyrinth Linguist  (port 32808, web)
#
# Usage:
#   bash examples/smoke-test/smoke_test.sh --model outputs/sft-nanbeige3b-merged
#
# Options:
#   --model PATH       Path to merged SFT model (required)
#   --vllm-port PORT   vLLM server port (default: 18001)
#   --vllm-cuda-devices CSV  CUDA_VISIBLE_DEVICES for vLLM (default: 0)
#   --train-cuda-devices CSV CUDA_VISIBLE_DEVICES for training (default: 1)
#   --local-inference  Use local (colocated) vLLM engines; no external server
#   --max-steps N      Training steps (default: 3)
#   --step-wise        Enable step-wise rewards/trajectory splitting
#   --episodic         Force episodic rewards (default)
#   --native-boxpwnr   Use native runtime mode with strict BoxPwnr adapter
#   --step-debug       Enable high-detail step-agent RCA logging (default)
#   --no-step-debug    Disable high-detail step-agent RCA logging
#   --skip-vllm        Don't start/stop vLLM (use existing server)
#   --skip-challenges  Don't check if challenge containers are running
#   --output-dir DIR   Output directory (default: outputs/smoke_2ch_TIMESTAMP)
#   --challenge-ids CSV  Comma-separated challenge IDs (default:
#                        "[Very Easy] Flag Command,[Easy] Labyrinth Linguist")
#   --include-static   Include static challenges in generated smoke dataset
#   --target-map PATH  Use an explicit target-map JSON file (skip live generation)
#
# Expected runtime: ~5-10 min on 2x high-memory GPUs
# =============================================================================

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────

MODEL_PATH=""
VLLM_PORT=18001
VLLM_CUDA_DEVICES="${VLLM_CUDA_DEVICES:-0}"
TRAIN_CUDA_DEVICES="${TRAIN_CUDA_DEVICES:-1}"
LOCAL_INFERENCE=false
MAX_STEPS=3
STEP_WISE=false
NATIVE_BOXPWNR=false
PROXY_BOXPWNR=false
STEP_DEBUG=true
SKIP_VLLM=false
SKIP_CHALLENGES=false
OUTPUT_DIR=""
CHALLENGE_IDS="[Very Easy] Flag Command,[Easy] Labyrinth Linguist"
INCLUDE_STATIC=false
CUSTOM_TARGET_MAP=""
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

resolve_project_dir() {
    if [[ -n "${TRAJGYM_PROJECT_DIR:-}" && -d "${TRAJGYM_PROJECT_DIR}/src/trajgym" ]]; then
        echo "${TRAJGYM_PROJECT_DIR}"
        return 0
    fi
    if git -C "$SCRIPT_DIR" rev-parse --show-toplevel >/dev/null 2>&1; then
        git -C "$SCRIPT_DIR" rev-parse --show-toplevel
        return 0
    fi
    local default_root="${TRAJGYM_ROOT:-$(pwd)}"
    if [[ -d "${default_root}/src/trajgym" ]]; then
        echo "${default_root}"
        return 0
    fi
    echo "$(cd "$SCRIPT_DIR/.." && pwd)"
}

PROJECT_DIR="$(resolve_project_dir)"
CONFIG="$PROJECT_DIR/examples/qwen35-27b/training_smoke.yaml"
REGISTRY="$PROJECT_DIR/configs/challenges/cybench.yaml"
SMOKE_DATA="$PROJECT_DIR/data/online_rl_smoke_2ch.jsonl"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
TARGET_MAP=""

resolve_python_bin() {
    local explicit="${TRAJGYM_PYTHON:-}"
    if [[ -n "$explicit" && -x "$explicit" ]]; then
        echo "$explicit"
        return 0
    fi
    local venv_root="${TRAJGYM_VENV_ROOT:-/workspace}"
    local candidates=(
        "$PROJECT_DIR/.venv/bin/python"
        "${venv_root}/.venv-grpo-iso/bin/python"
        "${venv_root}/.venv-grpo/bin/python"
        "python3"
    )
    local c
    for c in "${candidates[@]}"; do
        if command -v "$c" >/dev/null 2>&1; then
            command -v "$c"
            return 0
        fi
    done
    echo "python3"
}
PYTHON_BIN="$(resolve_python_bin)"

# ── Parse args ────────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)        MODEL_PATH="$2"; shift 2 ;;
        --vllm-port)    VLLM_PORT="$2"; shift 2 ;;
        --vllm-cuda-devices) VLLM_CUDA_DEVICES="$2"; shift 2 ;;
        --train-cuda-devices) TRAIN_CUDA_DEVICES="$2"; shift 2 ;;
        --local-inference) LOCAL_INFERENCE=true; shift ;;
        --max-steps)    MAX_STEPS="$2"; shift 2 ;;
        --step-wise)    STEP_WISE=true; shift ;;
        --episodic)     STEP_WISE=false; shift ;;
        --native-boxpwnr) NATIVE_BOXPWNR=true; shift ;;
        --proxy-boxpwnr) PROXY_BOXPWNR=true; shift ;;
        --step-debug)   STEP_DEBUG=true; shift ;;
        --no-step-debug) STEP_DEBUG=false; shift ;;
        --skip-vllm)    SKIP_VLLM=true; shift ;;
        --skip-challenges) SKIP_CHALLENGES=true; shift ;;
        --output-dir)   OUTPUT_DIR="$2"; shift 2 ;;
        --challenge-ids) CHALLENGE_IDS="$2"; shift 2 ;;
        --include-static) INCLUDE_STATIC=true; shift ;;
        --target-map)   CUSTOM_TARGET_MAP="$2"; shift 2 ;;
        *)              echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [[ -z "$MODEL_PATH" ]]; then
    echo "ERROR: --model is required (path to merged SFT model)"
    echo "Usage: bash examples/smoke-test/smoke_test.sh --model outputs/sft-nanbeige3b-merged"
    exit 1
fi

if [[ ! -d "$MODEL_PATH" ]]; then
    echo "ERROR: Model directory not found: $MODEL_PATH"
    exit 1
fi

if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="$PROJECT_DIR/outputs/smoke_2ch_${TIMESTAMP}"
fi

VLLM_URL="http://localhost:${VLLM_PORT}"
VLLM_LOG="$OUTPUT_DIR/vllm_server.log"
TARGET_MAP="$OUTPUT_DIR/live_target_map.json"

echo "═══════════════════════════════════════════════════════════════"
echo "  2-Challenge Online RL Smoke Test"
echo "═══════════════════════════════════════════════════════════════"
echo "  Model:      $MODEL_PATH"
echo "  Config:     $CONFIG"
echo "  Output:     $OUTPUT_DIR"
echo "  vLLM:       $VLLM_URL"
echo "  vLLM GPU:   $VLLM_CUDA_DEVICES"
echo "  Train GPU:  $TRAIN_CUDA_DEVICES"
echo "  Inference:  $([[ \"$LOCAL_INFERENCE\" == \"true\" ]] && echo local || echo remote)"
echo "  Mode:       $([[ \"$STEP_WISE\" == \"true\" ]] && echo step-wise || echo episodic)"
echo "  Runtime:    $([[ \"$NATIVE_BOXPWNR\" == \"true\" ]] && echo native-boxpwnr || ([[ \"$PROXY_BOXPWNR\" == \"true\" ]] && echo proxy-boxpwnr || echo tool_calls))"
echo "  Step debug: $STEP_DEBUG"
echo "  Steps:      $MAX_STEPS"
echo "  Challenges: $CHALLENGE_IDS"
echo "  Static:     $INCLUDE_STATIC"
echo "  Target map: ${CUSTOM_TARGET_MAP:-auto/live}"
echo "  Python:     $PYTHON_BIN"
echo "  Timestamp:  $TIMESTAMP"
echo "═══════════════════════════════════════════════════════════════"

mkdir -p "$OUTPUT_DIR"

# ── Step 1: Generate 2-sample data ────────────────────────────────────────────

echo ""
echo "▸ Step 1/5: Generating 2-sample training data..."

if [[ -n "$CUSTOM_TARGET_MAP" ]]; then
    if [[ ! -f "$CUSTOM_TARGET_MAP" ]]; then
        echo "ERROR: --target-map file not found: $CUSTOM_TARGET_MAP"
        exit 1
    fi
    cp "$CUSTOM_TARGET_MAP" "$TARGET_MAP"
    echo "  Using custom target map: $CUSTOM_TARGET_MAP"
else
    echo "  Generating live target map..."
    BENCHMARK_ROOT="$PROJECT_DIR"
    local cybench_dir="${CYBENCH_ROOT:-$PROJECT_DIR/benchmarks/cybench}"
    if [[ -d "$cybench_dir" ]]; then
        BENCHMARK_ROOT="$cybench_dir"
    fi
    "$PYTHON_BIN" "$PROJECT_DIR/src/trajgym/cli/generate_target_map.py" \
        --registry "$REGISTRY" \
        --benchmark-root "$BENCHMARK_ROOT" \
        --output "$TARGET_MAP" \
        --strict \
        > "$OUTPUT_DIR/target_map.log" 2>&1 || {
        FALLBACK_TARGET_MAP="$PROJECT_DIR/configs/challenges/cybench_target_map.json"
        if [[ -f "$FALLBACK_TARGET_MAP" ]]; then
            cp "$FALLBACK_TARGET_MAP" "$TARGET_MAP"
            echo "  WARNING: live target-map generation failed (docker likely unavailable)."
            echo "  Using fallback map: $FALLBACK_TARGET_MAP"
        else
            echo "ERROR: Failed to generate strict target map (see $OUTPUT_DIR/target_map.log)"
            tail -40 "$OUTPUT_DIR/target_map.log" || true
            exit 1
        fi
    }
fi
echo "  ✓ Target map: $TARGET_MAP"

# Generate all easy docker challenges, then filter to our 2 target web challenges
SMOKE_DATA_RAW="${SMOKE_DATA}.raw"
"$PYTHON_BIN" "$PROJECT_DIR/src/trajgym/cli/generate_online_rl.py" \
    --registry "$REGISTRY" \
    --target-map "$TARGET_MAP" \
    --probe-targets \
    --output "$SMOKE_DATA_RAW" \
    --difficulty-max easy \
    $([[ "$INCLUDE_STATIC" == "true" ]] && echo "--include-static") \
    2>&1 | tee "$OUTPUT_DIR/data_generation.log"

# Filter to exactly the requested target challenge IDs
"$PYTHON_BIN" -c "
import json
TARGET_IDS = {cid.strip() for cid in '$CHALLENGE_IDS'.split(',') if cid.strip()}
if not TARGET_IDS:
    raise SystemExit('No challenge IDs provided (use --challenge-ids).')
seen = set()
with open('$SMOKE_DATA_RAW') as fin, open('$SMOKE_DATA', 'w') as fout:
    for line in fin:
        s = json.loads(line)
        cid = s['metadata']['challenge_id']
        if cid in TARGET_IDS:
            fout.write(line)
            seen.add(cid)
missing = sorted(TARGET_IDS - seen)
if missing:
    raise SystemExit(f'Missing target smoke challenges after filtering/probing: {missing}')
print(f'  Filtered: {len(seen)} samples (requested challenge IDs)')
"
rm -f "$SMOKE_DATA_RAW"

SAMPLE_COUNT=$(wc -l < "$SMOKE_DATA" | tr -d ' ')
echo "  Generated: $SAMPLE_COUNT samples"

EXPECTED_COUNT=$("$PYTHON_BIN" -c "print(len([cid for cid in '$CHALLENGE_IDS'.split(',') if cid.strip()]))")
if [[ "$SAMPLE_COUNT" -ne "$EXPECTED_COUNT" ]]; then
    echo "ERROR: Expected exactly $EXPECTED_COUNT samples, got $SAMPLE_COUNT"
    exit 1
fi

# Show what we generated
echo "  Challenges:"
"$PYTHON_BIN" -c "
import json
with open('$SMOKE_DATA') as f:
    for line in f:
        s = json.loads(line)
        m = s['metadata']
        print(f\"    - {m['challenge_id']} ({m['category']}, {m['difficulty']})  flag={s['ground_truth_flag'][:30]}...\")
"

# ── Step 2: Check challenges are running ──────────────────────────────────────

echo ""
echo "▸ Step 2/5: Checking challenge availability..."

if [[ "$SKIP_CHALLENGES" == "true" ]]; then
    echo "  Skipped (--skip-challenges)"
else
    "$PYTHON_BIN" -c "
import json, socket, sys, urllib.request

with open('$SMOKE_DATA') as f:
    for line in f:
        s = json.loads(line)
        cid = s['metadata']['challenge_id']
        category = str(s.get('metadata', {}).get('category', '')).lower()
        # Extract target from user prompt
        user_msg = s['messages'][1]['content']
        target = ''
        for l in user_msg.split('\n'):
            if '**Connection**:' in l:
                target = l.split('**Connection**:')[1].strip()
                break
        if not target:
            print(f'  WARN: No target found for {cid}')
            continue
        if target.startswith('file://'):
            print(f'  ✓ {cid}: {target} — static target (no network probe)')
            continue

        # Parse host:port
        host = target.replace('http://', '').replace('https://', '')
        if '/' in host:
            host = host.split('/')[0]
        parts = host.split(':')
        h, p = parts[0], int(parts[1]) if len(parts) > 1 else 80

        # TCP probe first
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.settimeout(3.0)
        try:
            s2.connect((h, p))
            if category == 'web':
                req = urllib.request.Request(target, method='GET')
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    code = getattr(resp, 'status', 200)
                print(f'  ✓ {cid}: {target} — reachable HTTP {code}')
            else:
                print(f'  ✓ {cid}: {target} — reachable (tcp)')
        except Exception as e:
            print(f'  ✗ {cid}: {target} — UNREACHABLE ({e})')
            sys.exit(1)
        finally:
            s2.close()
" 2>&1 || {
        echo ""
        echo "  WARNING: Some challenges are unreachable."
        echo "  Start them with: trajgym-challenges setup --registry $REGISTRY"
        echo "  Or use --skip-challenges to proceed anyway (tool calls will fail but pipeline runs)."
        echo ""
        read -p "  Continue anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    }
fi

# ── Step 3: Start vLLM server ────────────────────────────────────────────────

echo ""
echo "▸ Step 3/5: Setting up vLLM server..."

if [[ "$LOCAL_INFERENCE" == "true" ]]; then
    echo "  Using local inference engines (no external vLLM server)"
    SKIP_VLLM=true
elif [[ "$SKIP_VLLM" == "true" ]]; then
    echo "  Skipped (--skip-vllm)"
else
    # Check if already running
    if curl -s "${VLLM_URL}/health" > /dev/null 2>&1; then
        echo "  vLLM already running at $VLLM_URL"
        SKIP_VLLM=true  # Don't stop it later
    else
        echo "  Starting vLLM server (model: $MODEL_PATH, port: $VLLM_PORT)..."
        CUDA_VISIBLE_DEVICES="$VLLM_CUDA_DEVICES" VLLM_ENABLE_V1_MULTIPROCESSING=0 nohup "$PYTHON_BIN" -m trajgym.training.skyrl_vllm_server \
            --model "$MODEL_PATH" \
            --host 0.0.0.0 --port "$VLLM_PORT" \
            --max-model-len 65536 \
            --dtype bfloat16 \
            --kv-cache-dtype fp8 \
            --calculate-kv-scales \
            --gpu-memory-utilization 0.50 \
            --max-num-seqs 4 \
            --enforce-eager \
            --trust-remote-code \
            --language-model-only \
            > "$VLLM_LOG" 2>&1 &
        VLLM_PID=$!
        echo "  vLLM PID: $VLLM_PID"

        # Wait for server to be ready (up to 120s)
        echo "  Waiting for vLLM to start..."
        for i in $(seq 1 60); do
            if curl -s "${VLLM_URL}/health" > /dev/null 2>&1; then
                echo "  vLLM ready after ${i}×2s"
                break
            fi
            if ! kill -0 "$VLLM_PID" 2>/dev/null; then
                echo "  ERROR: vLLM process died. Check $VLLM_LOG"
                tail -20 "$VLLM_LOG"
                exit 1
            fi
            sleep 2
        done

        if ! curl -s "${VLLM_URL}/health" > /dev/null 2>&1; then
            echo "  ERROR: vLLM failed to start within 120s. Check $VLLM_LOG"
            tail -20 "$VLLM_LOG"
            exit 1
        fi
    fi
fi

# ── Step 4: Run GRPO training ────────────────────────────────────────────────

echo ""
echo "▸ Step 4/5: Running online RL training ($MAX_STEPS steps)..."
echo "  Data:   $SMOKE_DATA"
echo "  Config: $CONFIG"
echo "  Output: $OUTPUT_DIR"
echo ""

# Set environment for SkyRL
export RAY_memory_monitor_refresh_ms=0
export _SKYRL_USE_NEW_INFERENCE=1
export VLLM_ENABLE_V1_MULTIPROCESSING=0
export TRANSFORMERS_NO_TORCHVISION=1
export TRAJGYM_TARGET_MAP_PATH="$TARGET_MAP"
export TRAJGYM_TARGET_MAP_STRICT=1
if [[ "$STEP_DEBUG" == "true" ]]; then
    export TRAJGYM_STEP_DEBUG=1
fi

if [[ "$STEP_WISE" == "true" ]]; then
    STEP_WISE_PY=True
else
    STEP_WISE_PY=False
fi

if [[ "$INCLUDE_STATIC" == "true" ]]; then
    DROP_STATIC_PY=False
else
    DROP_STATIC_PY=True
fi

# Create the training launch script (spawn guard for multiprocessing)
cat > "$OUTPUT_DIR/run_training.py" << PYEOF
import multiprocessing, os, sys

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    os.environ.setdefault("RAY_memory_monitor_refresh_ms", "0")
    os.environ.setdefault("_SKYRL_USE_NEW_INFERENCE", "1")
    os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")
    os.environ.setdefault("TRANSFORMERS_NO_TORCHVISION", "1")

    sys.path.insert(0, "$PROJECT_DIR")
    sys.path.insert(0, "$PROJECT_DIR/src")

    import yaml
    from trajgym.training.online_rl import train_online_rl

    with open("$CONFIG") as f:
        config = yaml.safe_load(f)

    # Override vLLM URL and epochs from CLI
    rl_key = "grpo" if "grpo" in config else ("online_rl" if "online_rl" in config else None)
    if rl_key:
        model_name = str(config.get("model", {}).get("name", "$MODEL_PATH"))
        model_lower = model_name.lower()
        config[rl_key]["target_map_path"] = "$TARGET_MAP"
        config[rl_key]["target_map_strict"] = True
        config[rl_key]["prefer_registry_target"] = True
        config[rl_key]["fail_on_target_collisions"] = True
        config[rl_key]["drop_static_challenges"] = $DROP_STATIC_PY
        config[rl_key]["agent_class"] = "trajgym.agent.default_agent.DefaultStepAgent"
        # Keep 20-turn episodes for baseline parity on easy smoke targets.
        config[rl_key]["step_wise_trajectories"] = $STEP_WISE_PY
        config[rl_key]["max_tool_calling_iterations"] = 20
        config[rl_key].setdefault("agent_kwargs", {})
        config[rl_key]["agent_kwargs"].setdefault("runtime_cmd", "python src/trajgym/agent/framework_runtime_bridge.py")
        config[rl_key]["agent_kwargs"].setdefault("runtime_timeout_seconds", 20)
        config[rl_key]["agent_kwargs"].setdefault("runtime_passthrough", False)
        config[rl_key]["agent_kwargs"].setdefault("runtime_fallback_to_parser", False)
        config[rl_key]["agent_kwargs"].setdefault("runtime_env", {})
        config[rl_key]["agent_kwargs"]["runtime_env"].setdefault("TRAJGYM_AGENT_FRAMEWORK", "boxpwnr_langgraph")
        config[rl_key]["agent_kwargs"]["runtime_env"].setdefault("TRAJGYM_AGENT_MODE", "tool_calls")
        if "$NATIVE_BOXPWNR".lower() == "true":
            config[rl_key]["agent_kwargs"]["runtime_env"]["TRAJGYM_AGENT_MODE"] = "native"
            config[rl_key]["agent_kwargs"]["runtime_env"]["TRAJGYM_AGENT_CMD"] = (
                "python examples/bring-your-own/agent/langgraph_adapter.py"
            )
            config[rl_key]["agent_kwargs"]["runtime_env"].setdefault(
                "TRAJGYM_AGENT_CMD_TIMEOUT", "20"
            )
            # Native adapter owns command execution and returns protocol
            # passthrough observations in BoxPwnr-style <OUTPUT> blocks.
            config[rl_key]["agent_kwargs"]["runtime_passthrough"] = True
            config[rl_key]["agent_kwargs"]["runtime_fallback_to_parser"] = False
            # Keep tool-call contract aligned with model defaults/config.
            # For Nanbeige/Qwen this should stay Hermes-style <tool_call>.
            selected_format = str(config[rl_key].get("tool_call_format", "")).strip().lower()
            if not selected_format:
                if "glm" in model_lower:
                    selected_format = "glm4"
                elif "qwen" in model_lower or "nanbeige" in model_lower or "openthinker" in model_lower:
                    selected_format = "hermes"
                else:
                    selected_format = "hermes"
            config[rl_key]["tool_call_format"] = selected_format
            if selected_format == "command_xml":
                config[rl_key]["generation_stop"] = ["</COMMAND>", "</FLAG>", "<|im_end|>"]
            elif selected_format in {"hermes", "qwen3_coder", "glm4"}:
                config[rl_key]["generation_stop"] = ["</tool_call>", "<|im_end|>"]
            config[rl_key]["agent_kwargs"]["runtime_env"]["TRAJGYM_TOOL_CALL_FORMAT"] = selected_format
            # Fail faster on repeated no-action loops during smoke RCA.
            config[rl_key]["agent_kwargs"]["max_consecutive_no_tool_calls"] = 6
        elif "$PROXY_BOXPWNR".lower() == "true":
            config[rl_key]["agent_kwargs"]["runtime_env"]["TRAJGYM_AGENT_MODE"] = "proxy"
            config[rl_key]["agent_class"] = "trajgym.agent.proxy_step_agent.ProxyStepAgent"
            config[rl_key]["agent_kwargs"]["agent_cmd"] = "python src/trajgym/cli/run_proxy.py"
            # Set generation stops to BoxPwnr tags
            config[rl_key]["generation_stop"] = ["</COMMAND>", "</FLAG>", "<|im_end|>"]
        if "$LOCAL_INFERENCE".lower() == "true":
            config[rl_key].pop("vllm_server_url", None)
            config[rl_key]["vllm_mode"] = "colocate"
            config[rl_key]["allow_remote_lora"] = False
        else:
            config[rl_key]["vllm_server_url"] = "$VLLM_URL"
            config[rl_key]["vllm_mode"] = "server"
            config[rl_key]["allow_remote_lora"] = True
    # Override epochs to control training steps (steps = epochs × samples / effective_batch)
    max_steps = $MAX_STEPS
    if max_steps > 0 and rl_key:
        config[rl_key]["epochs"] = max_steps  # 1 step per epoch with 2 samples, batch=1, accum=2
    glog_key = "grpo_logging" if "grpo_logging" in config else "online_rl_logging"
    glog = config.setdefault(glog_key, {})
    glog["enable_trajectory_logging"] = True
    glog["require_trajectory_files"] = True

    result = train_online_rl(
        model_path="$MODEL_PATH",
        data_path="$SMOKE_DATA",
        output_dir="$OUTPUT_DIR",
        config=config,
        challenge_registry="$REGISTRY",
    )
    print(f"Training complete. Output: {result}")
PYEOF

cd "$PROJECT_DIR"
CUDA_VISIBLE_DEVICES="$TRAIN_CUDA_DEVICES" TRAJGYM_STEP_DEBUG="${TRAJGYM_STEP_DEBUG:-0}" "$PYTHON_BIN" "$OUTPUT_DIR/run_training.py" 2>&1 | tee "$OUTPUT_DIR/training.log"
TRAIN_EXIT=$?

# ── Step 5: Validate results ─────────────────────────────────────────────────

echo ""
echo "▸ Step 5/5: Validating results..."
echo ""

"$PYTHON_BIN" -c "
import json, os, sys, glob

output_dir = '$OUTPUT_DIR'
errors = []
warnings = []
flag_rows = 0

# Check training log exists
log_file = os.path.join(output_dir, 'training.log')
if os.path.exists(log_file):
    with open(log_file) as f:
        log_content = f.read()
    print(f'  ✓ Training log: {len(log_content)} bytes')

    # Check for errors
    error_lines = [l for l in log_content.split('\n') if 'ERROR' in l.upper() and 'error_classification' not in l.lower()]
    if error_lines:
        warnings.append(f'{len(error_lines)} error lines in training log')
        for el in error_lines[:5]:
            print(f'    WARN: {el[:120]}')
else:
    errors.append('No training.log found')

# Check trajectory files
traj_dir = os.path.join(output_dir, 'trajectories')
if os.path.isdir(traj_dir):
    step_files = sorted(glob.glob(os.path.join(traj_dir, 'step_*.jsonl')))
    summary_file = os.path.join(traj_dir, 'step_summaries.jsonl')

    print(f'  ✓ Trajectory dir: {len(step_files)} step files')

    # Parse step summaries
    if os.path.exists(summary_file):
        with open(summary_file) as f:
            summaries = [json.loads(l) for l in f if l.strip()]
        print(f'  ✓ Step summaries: {len(summaries)} steps logged')

        for s in summaries:
            step = s.get('global_step', '?')
            reward = s.get('avg_reward', 0)
            flags = s.get('flag_found_count', 0)
            total = s.get('total_generations', 0)
            tools = s.get('avg_tool_calls', 0)
            print(f'    Step {step}: reward={reward:.4f}, flags={flags}/{total}, avg_tools={tools:.1f}')
    else:
        warnings.append('No step_summaries.jsonl found')

    # Count solved trajectories across all step files and check no_tool_call ratio.
    total_turns = 0
    no_tool_turns = 0
    for sf in step_files:
        with open(sf) as f:
            gens = [json.loads(l) for l in f if l.strip()]
        for g in gens:
            if g.get('flag_found'):
                flag_rows += 1
            status_counts = g.get('status_counts', {})
            total_turns += sum(status_counts.values())
            no_tool_turns += status_counts.get('no_tool_call', 0)

    if total_turns > 0:
        no_tool_ratio = no_tool_turns / total_turns
        if no_tool_ratio > 0.5:
            errors.append(f'Too many no_tool_call turns ({no_tool_turns}/{total_turns} = {no_tool_ratio:.2f} > 0.5). Model is failing to generate valid tools.')
        else:
            print(f'  ✓ Tool generation reliability: {no_tool_turns}/{total_turns} no_tool_call ({no_tool_ratio:.2f})')

    # Parse individual step files for tool call details
    for sf in step_files[:3]:
        with open(sf) as f:
            gens = [json.loads(l) for l in f if l.strip()]
        step_name = os.path.basename(sf)
        tool_types = {}
        for g in gens:
            for tc in g.get('tool_calls', []):
                t = tc.get('name', 'unknown')
                tool_types[t] = tool_types.get(t, 0) + 1
        if tool_types:
            top_tools = ', '.join(f'{k}={v}' for k, v in sorted(tool_types.items(), key=lambda x: -x[1])[:5])
            print(f'    {step_name}: tools used = {top_tools}')

    # Check for HTTP requests (the whole point of the v8_r9 fix)
    http_found = False
    for sf in step_files:
        with open(sf) as f:
            content = f.read()
        if 'curl' in content.lower() or 'http://' in content:
            http_found = True
            break
    if http_found:
        print(f'  ✓ HTTP requests detected in trajectories (curl/http://)')
    else:
        warnings.append('No HTTP requests found in trajectories — model may not be curling web challenges')
    if flag_rows > 0:
        print(f'  ✓ Flags captured in trajectories: {flag_rows}')
    else:
        errors.append('No flags captured in trajectories (expected at least one on easy smoke targets)')
else:
    errors.append('No trajectories/ directory found')

# Check checkpoints
ckpt_dirs = sorted(glob.glob(os.path.join(output_dir, 'checkpoint*')))
if not ckpt_dirs:
    ckpt_dirs = sorted(glob.glob(os.path.join(output_dir, 'global_step_*')))
if ckpt_dirs:
    print(f'  ✓ Checkpoints: {len(ckpt_dirs)} saved')
    for cd in ckpt_dirs:
        print(f'    {os.path.basename(cd)}')
else:
    warnings.append('No checkpoints found')

# Check scoreboard (saved at output root by TrajectoryLogger.save_scoreboard()).
scoreboard = os.path.join(output_dir, 'challenge_scoreboard.json')
if not os.path.exists(scoreboard) and os.path.isdir(traj_dir):
    # Backward-compatible fallback for older layouts.
    scoreboard = os.path.join(traj_dir, 'challenge_scoreboard.json')
if os.path.exists(scoreboard):
    with open(scoreboard) as f:
        sb = json.load(f)
    print(f'  ✓ Challenge scoreboard: {len(sb)} challenges')
    for cid, stats in sb.items():
        attempts = stats.get('attempts', 0)
        solved = stats.get('solved', stats.get('solves', 0))
        print(f'    {cid}: {solved}/{attempts} solved')

# Summary
print()
if errors:
    print(f'  ERRORS: {len(errors)}')
    for e in errors:
        print(f'    ✗ {e}')
if warnings:
    print(f'  WARNINGS: {len(warnings)}')
    for w in warnings:
        print(f'    ⚠ {w}')
if not errors:
    print('  ════════════════════════════════════')
    print('  ✓ SMOKE TEST PASSED')
    print('  ════════════════════════════════════')
else:
    print('  ════════════════════════════════════')
    print('  ✗ SMOKE TEST FAILED')
    print('  ════════════════════════════════════')
    sys.exit(1)
"

# ── Cleanup ───────────────────────────────────────────────────────────────────

if [[ "$SKIP_VLLM" == "false" ]] && [[ -n "${VLLM_PID:-}" ]]; then
    echo ""
    echo "Stopping vLLM server (PID: $VLLM_PID)..."
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Smoke test complete. Results in: $OUTPUT_DIR"
echo "  Trajectory logs: $OUTPUT_DIR/trajectories/"
echo "  Training log:    $OUTPUT_DIR/training.log"
echo "═══════════════════════════════════════════════════════════════"
