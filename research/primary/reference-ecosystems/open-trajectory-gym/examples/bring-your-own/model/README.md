# How to Add a New Model

Add any HuggingFace model to Open Trajectory Gym by creating a training config.

## Steps

### 1. Create training.yaml

Copy the annotated template and fill in your model's values:

```bash
cp examples/bring-your-own/model/training_template.yaml \
   examples/my-model/training.yaml
```

At minimum, set:
- `model.name` -- HuggingFace model ID (e.g., `meta-llama/Llama-3.1-8B-Instruct`)
- `model.max_seq_length` -- Training context window
- `model.load_in_4bit` -- Enable QLoRA for smaller GPUs
- `lora.target_modules` -- Modules to apply LoRA to (typically q/k/v/o/gate/up/down proj)

### 2. (Optional) Add a tool-call formatter

If your model uses a non-standard tool-call format, add a formatter at `src/trajgym/formatters/<model>.py`. The default Hermes format (`<tool_call> JSON </tool_call>`) works for most models.

Existing formats:
- `hermes` -- Hermes JSON (Nanbeige, Qwen3, most ChatML models)
- `qwen3_coder` -- Qwen3.5 XML (`<tool_call><function=name>...</function></tool_call>`)
- `glm4` -- GLM-4 XML format

### 3. Run smoke test

```bash
# Quick SFT to verify config is valid
trajgym-train sft \
  --config examples/my-model/training.yaml \
  --model <your-model-id> \
  --data data/sft.jsonl \
  --output outputs/sft_my_model \
  --max-steps 5

# If SFT works, merge and run ONLINE_RL smoke test
trajgym-train merge \
  --base <your-model-id> \
  --adapter outputs/sft_my_model/final \
  --output outputs/sft_my_model-merged

bash examples/smoke-test/smoke_test.sh --model outputs/sft_my_model-merged
```

### 4. Validate

```bash
trajgym-validate --config examples/my-model/training.yaml
```

## Tips

- Start with QLoRA 4-bit (`load_in_4bit: true`) on smaller GPUs -- it works for all dense models.
- MoE models (Mixtral, DeepSeek-V3, GLM-4.7-Flash) have known QLoRA issues. Use BF16 if possible.
- Set `flash_attn: false` if you see illegal memory access errors during gradient checkpointing.
- Dense models under 10B typically need 5 SFT epochs; larger models converge in 3.

## Reference Configs

See the sibling directories for working examples:
- `examples/qwen35-4b/` -- 4B dense, fast iteration
- `examples/qwen35-9b/` -- 9B dense, balanced quality/speed
- `examples/qwen35-27b/` -- 27B dense, BF16, 2x 140GB+ GPUs
- `examples/devstral-24b/` -- 24B dense, alternative baseline
