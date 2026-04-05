# Devstral-24B Training Configuration

Alternative baseline: Devstral-Small-2-24B-Instruct (24B dense MistralForCausalLM).

Strong code and tool-calling model. Fits on a single H100 for inference. Not yet validated end-to-end on the Open Trajectory Gym pipeline -- use as a starting point for experiments.

## Requirements

- 2x GPUs with 80GB+ VRAM each
- ~48GB BF16 model weights

## Quick Start

```bash
# SFT
trajgym-train sft \
  --config examples/devstral-24b/training.yaml \
  --model mistralai/Devstral-Small-2507 \
  --data data/sft.jsonl \
  --output outputs/sft_devstral

# Merge
trajgym-train merge \
  --base mistralai/Devstral-Small-2507 \
  --adapter outputs/sft_devstral/final \
  --output outputs/sft_devstral-merged

# ONLINE_RL
trajgym-train rl \
  --config examples/devstral-24b/training.yaml \
  --model outputs/sft_devstral-merged \
  --data data/online_rl.jsonl \
  --output outputs/grpo_devstral
```

## Key Parameters

| Parameter | SFT | ONLINE_RL |
|-----------|-----|------|
| Max context | 32,768 | 32,768 prompt + 8,192 completion |
| LoRA rank | r=64, alpha=128 | Same |
| Batch size | 1 (effective 8) | 1 (effective 8) |
| Learning rate | 2e-5 | 2e-6 |
| Quantization | None (BF16) | None (BF16) |
| Generations | -- | 8 per prompt |
