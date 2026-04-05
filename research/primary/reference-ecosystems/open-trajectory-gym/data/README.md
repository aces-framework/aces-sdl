# Training Data

Datasets used by the 3-stage training pipeline. Generated files (synthetic traces, split outputs) are gitignored — only seed data is committed.

## Files

| File | Stage | Description |
|------|-------|-------------|
| `sft.jsonl` | SFT | Expert trajectories in ChatML format (system/user/assistant/tool messages). |
| `online_rl.jsonl` | ONLINE_RL | Challenge prompts + ground-truth flags that seed live online RL episodes. |
| `online_rl.jsonl.manifest.json` | ONLINE_RL | Source hashes and challenge coverage for preflight validation. |

## Data Formats

### SFT (`sft.jsonl`)

Each line is a complete solved trajectory:

```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "name": "shell_command", "content": "..."}
  ],
  "metadata": {"source": "boxpwnr", "challenge": "...", "success": true},
  "ground_truth_flag": "FLAG{...}",
  "optimal_steps": 8
}
```

### Online RL (`online_rl.jsonl`)

Each line is a challenge seed (not a trajectory). The model generates actions live during ONLINE_RL training, tools execute against real targets, and rewards are computed from rollout behavior + flag verification.

```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "ground_truth_flag": "FLAG{...}",
  "optimal_steps": null,
  "metadata": {"challenge": "...", "category": "pwn", "difficulty": "medium", "infra_type": "docker"}
}
```

## Generating Online RL Data

Online RL data is a generated artifact from your challenge registry, not a hand-edited file:

```bash
trajgym-generate-rl \
  --registry configs/challenges/cybench.yaml \
  --output data/online_rl.jsonl
```

Validate before training:

```bash
trajgym-validate --mode online_rl-preflight \
  --online-rl-data data/online_rl.jsonl \
  --challenge-registry configs/challenges/cybench.yaml
```

## Synthetic Data

Generate offline traces to supplement real agent data for SFT:

```bash
trajgym-synthetic-data \
  --config configs/synthetic_data_generation/default.yaml \
  --num-traces 500 \
  --sft-out data/synthetic_sft.jsonl
```

Output uses the same ChatML format as `sft.jsonl`. See [`docs/data-collection.md`](../docs/data-collection.md) for the full data pipeline.
