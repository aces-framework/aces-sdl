# Bring Your Own

Open Trajectory Gym is designed around four extension points. Swap any component without touching the rest.

## Extension Points

| What | Directory | Effort | Description |
|------|-----------|--------|-------------|
| **Benchmark** | `benchmark/` | Low | Add any benchmark — CTF, SWE, sysadmin, data analysis — via a YAML challenge registry |
| **Model** | `model/` | Low | Add any HuggingFace model with a training.yaml config |
| **Agent** | `agent/` | Medium | Integrate an external agent framework (LangGraph, Autogen, ADK, etc.) |
| **Reward** | — | Low | Configure signal weights via YAML, or replace entirely with any callable |

## How It Works

- **Benchmark**: Create a YAML challenge registry defining tasks, infrastructure type (docker service or static files), and ground truth answers. The same registry drives data generation, training, and evaluation. See `benchmark/README.md` for a full walkthrough with examples across domains.

- **Model**: Create a `training.yaml` with model name, LoRA settings, SFT/ONLINE_RL parameters. Optionally add a formatter for custom tool-call formats. See `model/training_template.yaml` for an annotated blank config.

- **Agent**: Implement either the `StepAgent` protocol (for ONLINE_RL training) or the `Agent` protocol (for eval/GEPA). Or use the runtime bridge with `TRAJGYM_AGENT_MODE=native` to shell out to any external process.

- **Reward**: The default reward function has 8 configurable signals with YAML-tunable weights. Override weights in your training config, or replace the function entirely — any callable matching `__call__(completions, **kwargs) -> list[float]`. See [`docs/architecture.md`](../../docs/architecture.md#ctf-reward-function).
