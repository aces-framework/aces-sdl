# Qwen3.5-27B Training Configuration

Production training config for Qwen3.5-27B (27B dense, hybrid GDN+attention).

## Requirements

- 2x GPUs with 140GB+ VRAM each (H200 SXM, B200, or equivalent)
- GPU 0: vLLM server (BF16 model ~51GB + KV cache)
- GPU 1: FSDP2 trainer (BF16 model ~54GB + LoRA + optimizer)
- ~300GB total VRAM across both GPUs

## Quick Start

All commands run from the repo root.

**1. Smoke test** (verify pipeline before committing to full training):

```bash
bash examples/smoke-test/smoke_test.sh --model /path/to/sft-merged
```

**2. SFT** (supervised fine-tuning on expert CTF traces):

```bash
trajgym-train sft \
  --config examples/qwen35-27b/training.yaml \
  --model Qwen/Qwen3.5-27B \
  --data data/sft.jsonl \
  --output outputs/sft_qwen35_27b
```

**3. Merge** (LoRA adapter into full model):

```bash
trajgym-train merge \
  --base Qwen/Qwen3.5-27B \
  --adapter outputs/sft_qwen35_27b/final \
  --output outputs/sft_qwen35_27b-merged
```

**4. ONLINE_RL** (online RL with live tool execution):

```bash
trajgym-train rl \
  --config examples/qwen35-27b/training.yaml \
  --model outputs/sft_qwen35_27b-merged \
  --data data/online_rl.jsonl \
  --output outputs/grpo
```

**5. Eval** (evaluate against CyBench):

```bash
trajgym-eval \
  --model outputs/grpo/final \
  --challenge-registry configs/challenges/cybench.yaml
```

## Config Files

| File | Purpose |
|------|---------|
| `training.yaml` | Full training config (SFT + ONLINE_RL + reward) |
| `training_smoke.yaml` | Reduced config for 2-challenge smoke tests |

## Key Parameters

| Parameter | SFT | ONLINE_RL |
|-----------|-----|------|
| Max context | 16,384 | 32,768 prompt + 8,192 completion |
| LoRA rank | r=64, alpha=128 | Same (synced between vLLM and trainer) |
| Batch size | 1 (effective 8 with grad_accum) | 1 (effective 8 with grad_accum) |
| Learning rate | 2e-5 | 5e-5 |
| Quantization | None (BF16) | None (BF16) |
| Generations | -- | 8 per prompt (RLOO advantage) |
| Reward | -- | Binary (flag_weight=1.0, all others 0.0) |

## Expected Results

- **SFT**: Loss 5.85 -> 0.49, accuracy 88.8%, 63 optimizer steps, ~84 min on 2x H200
- **SFT eval**: 8/40 CyBench challenges solved (20.0%)
- **ONLINE_RL**: Flag Command 3/4 solved at step 3, policy_loss non-zero, training functional
- **Base model (pre-SFT)**: 6/32 challenges solved (18.8%)
