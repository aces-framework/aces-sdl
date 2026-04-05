# Smoke Test

2-challenge end-to-end smoke test for the online RL pipeline. Verifies the full training stack works before committing to a production run.

## What it does

1. Generates 2-sample training data (web challenges only)
2. Starts vLLM server (if not already running)
3. Runs 3 ONLINE_RL training steps with full trajectory logging
4. Validates output: checkpoints, trajectories, rewards

**Challenges used**:
- [Very Easy] Flag Command (port 32810, web)
- [Easy] Labyrinth Linguist (port 32808, web)

**Expected runtime**: ~5-10 min on 2x high-memory GPUs.

## Usage

```bash
bash examples/smoke-test/smoke_test.sh --model /path/to/sft-merged-model
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--model PATH` | (required) | Path to merged SFT model |
| `--vllm-port PORT` | 18001 | vLLM server port |
| `--vllm-cuda-devices CSV` | 0 | CUDA_VISIBLE_DEVICES for vLLM |
| `--train-cuda-devices CSV` | 1 | CUDA_VISIBLE_DEVICES for training |
| `--local-inference` | off | Use local (colocated) vLLM engines; no external server |
| `--max-steps N` | 3 | Training steps |
| `--step-wise` | off | Enable step-wise rewards/trajectory splitting |
| `--native-boxpwnr` | off | Use native runtime mode with strict BoxPwnr adapter |
| `--skip-vllm` | off | Don't start/stop vLLM (use existing server) |
| `--skip-challenges` | off | Don't check if challenge containers are running |
| `--output-dir DIR` | auto-timestamped | Output directory |
| `--challenge-ids CSV` | Flag Command, Labyrinth Linguist | Comma-separated challenge IDs |
| `--include-static` | off | Include static challenges in generated dataset |
| `--target-map PATH` | auto/live | Use an explicit target-map JSON file |

## Prerequisites

- Merged SFT model (run `trajgym-train sft` then `trajgym-train merge` first)
- Challenge containers running (or use `--skip-challenges`)
- GPU available for vLLM and training

## What to check after

- `outputs/smoke_*/training.log` -- no ERROR lines
- `outputs/smoke_*/trajectories/` -- step files with tool calls and rewards
- `outputs/smoke_*/trajectories/step_summaries.jsonl` -- per-step reward progression
- HTTP requests present in trajectories (model is actually curling web challenges)
