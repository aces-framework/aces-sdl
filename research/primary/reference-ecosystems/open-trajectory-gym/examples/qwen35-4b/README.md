# Qwen3.5-4B Training Configuration

Dense Qwen3.5 text model (4B params). Smallest Qwen3.5 variant with hybrid GDN+attention.

## Requirements

- 2x GPUs with 80GB+ VRAM each (H100, H200, or equivalent)
- ~8GB BF16 model weights -- 135GB free per GPU enables aggressive parameters

## Important Caveat

4B models have limited multi-step reasoning capacity. They can generate valid tool calls but fail at multi-hop exploitation chains (e.g., HTML -> JS -> API -> flag). Useful for fast iteration on training infrastructure. Monitor flag capture rate -- if below 5% after 50 ONLINE_RL steps, the model may lack capacity regardless of training quality.

## Quick Start

```bash
# SFT
trajgym-train sft \
  --config examples/qwen35-4b/training.yaml \
  --model Qwen/Qwen3.5-4B \
  --data data/sft.jsonl \
  --output outputs/sft_qwen35_4b

# Merge
trajgym-train merge \
  --base Qwen/Qwen3.5-4B \
  --adapter outputs/sft_qwen35_4b/final \
  --output outputs/sft_qwen35_4b-merged

# ONLINE_RL
trajgym-train rl \
  --config examples/qwen35-4b/training.yaml \
  --model outputs/sft_qwen35_4b-merged \
  --data data/online_rl.jsonl \
  --output outputs/grpo_4b
```

## Key Parameters

| Parameter | SFT | ONLINE_RL |
|-----------|-----|------|
| Max context | 32,768 | 65,536 prompt + 32,768 completion |
| LoRA rank | r=256, alpha=512 (RSLoRA) | Same |
| Batch size | 1 (effective 8) | 1 (effective 8) |
| Learning rate | 1.5e-5 | 8e-6 |
| Quantization | None (BF16) | None (BF16) |
| Generations | -- | 8 per prompt |
| vLLM context | -- | 131,072 |
