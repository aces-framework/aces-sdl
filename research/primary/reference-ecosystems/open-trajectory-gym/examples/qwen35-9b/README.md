# Qwen3.5-9B Training Configuration

Dense Qwen3.5 text model (9B params, same hybrid GDN+attention family as 27B).

## Requirements

- 2x GPUs with 80GB+ VRAM each (H100, H200, or equivalent)
- ~19GB BF16 model weights -- significantly smaller footprint than 27B (~54GB)
- 100+ GB headroom per GPU enables higher LoRA rank and longer context

## Key Advantages Over 27B

- 65K SFT context covers 100% of training data (zero truncation vs 27B's 16K/65%)
- LoRA r=128 (2x the 27B's r=64) for more expressive adapters
- 6 ONLINE_RL generations (vs 27B's 8) with 131K vLLM context
- Double the completion length (16K vs 8K)

## Quick Start

```bash
# SFT
trajgym-train sft \
  --config examples/qwen35-9b/training.yaml \
  --model Qwen/Qwen3.5-9B \
  --data data/sft.jsonl \
  --output outputs/sft_qwen35_9b

# Merge
trajgym-train merge \
  --base Qwen/Qwen3.5-9B \
  --adapter outputs/sft_qwen35_9b/final \
  --output outputs/sft_qwen35_9b-merged

# ONLINE_RL
trajgym-train rl \
  --config examples/qwen35-9b/training.yaml \
  --model outputs/sft_qwen35_9b-merged \
  --data data/online_rl.jsonl \
  --output outputs/grpo_9b
```

## Key Parameters

| Parameter | SFT | ONLINE_RL |
|-----------|-----|------|
| Max context | 65,536 | 65,536 prompt + 16,384 completion |
| LoRA rank | r=128, alpha=256 | Same |
| Batch size | 1 (effective 8) | 1 (effective 6) |
| Learning rate | 2e-5 | 5e-6 |
| Quantization | None (BF16) | None (BF16) |
| Generations | -- | 6 per prompt |
| vLLM context | -- | 131,072 |
