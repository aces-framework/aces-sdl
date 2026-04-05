# Examples

Training configurations and starter guides for Open Trajectory Gym.

## Pick Your Model

| Model | Params | GPU Required | Best For | Directory |
|-------|--------|-------------|----------|-----------|
| Qwen3.5-4B | 4B | 2x 140GB | Fast research iteration | `qwen35-4b/` |
| Qwen3.5-9B | 9B | 2x 140GB | Balanced quality/speed | `qwen35-9b/` |
| Qwen3.5-27B | 27B | 2x 140GB+ | Production training | `qwen35-27b/` |
| Devstral-24B | 24B | 2x 140GB | Alternative baseline | `devstral-24b/` |

## User Journey

1. **Setup** -- Install open-trajectory-gym: `pip install -e ".[sft,online-rl,dev]"`
2. **Pick a model** -- Start with `qwen35-4b/` for fast iteration, or `qwen35-27b/` for production training.
3. **Smoke test** -- Run `smoke-test/smoke_test.sh` to verify end-to-end training works.
4. **Full pipeline** -- SFT -> merge -> ONLINE_RL -> eval. Each model directory has the commands.
5. **Customize** -- Bring your own model, agent, benchmark, or reward function (see `bring-your-own/`).

## Customize

The `bring-your-own/` directory has guides for extending the platform:

- `bring-your-own/benchmark/` -- Add any benchmark (CTF, SWE, sysadmin, etc.) via YAML challenge registry
- `bring-your-own/model/` -- Add a new model with a training.yaml config
- `bring-your-own/agent/` -- Integrate an external agent framework (LangGraph, Autogen, etc.)

## Other Examples

| Directory / File | Purpose |
|-----------------|---------|
| `gepa/` | GEPA prompt evolution (Stage 3, no weight updates) |
| `smoke-test/` | 2-challenge end-to-end smoke test for online RL |
| `byo_runtime_example.py` | Minimal external runtime bridge for DefaultStepAgent |
