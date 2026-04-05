# AGENTS.md

Context for AI coding agents reviewing or contributing to this repository.

## What This Project Is

Open Trajectory Gym is a platform for post-training LLMs on multi-turn tool-use trajectories. It provides a 3-stage pipeline (SFT → online ONLINE_RL → GEPA) with pluggable agents, models, benchmarks, and reward functions. The featured example trains a CTF security agent on CyBench challenges.

## Architecture

```
src/trajgym/
├── agent/           # StepAgent + Agent protocols, runtime bridge for BYO agents
├── challenges/      # ChallengeRegistry (YAML) + ChallengeManager (Docker lifecycle)
├── cli/             # All CLI entry points (trajgym-train, trajgym-eval, etc.)
├── envs/            # ToolExecutor (13 tools, subprocess-based) + SkyRL env bridge
├── formatters/      # Per-model chat template formatters (Qwen3, GLM4, Devstral)
├── rewards/         # Reward function (8 signals + hallucination penalty)
├── training/        # SFT (TRL), online ONLINE_RL (SkyRL), GEPA (DSPy)
└── parsing/         # Tool call parsers (5 formats: Hermes, Qwen XML, bare JSON, etc.)
```

## Key Technical Context

- **Package name**: `trajgym` (import as `from trajgym.agent.protocol import StepAgent`)
- **CLI prefix**: All commands start with `trajgym-` (e.g., `trajgym-train`, `trajgym-eval`)
- **Environment variables**: All use `TRAJGYM_` prefix (e.g., `TRAJGYM_AGENT_MODE`)
- **Python**: 3.11+, type hints used throughout, `ruff` for linting
- **Tests**: `pytest` in `tests/`, run with `python -m pytest tests/ -v`
- **Config format**: YAML for challenges, training configs, and synthetic data manifests

## Extension Points (BYO)

| Seam | Entry Point | Guide |
|------|-------------|-------|
| Agent | `src/trajgym/agent/protocol.py` — implement `StepAgent` or `Agent` | `docs/byo_agent.md` |
| Model | `examples/<model>/training.yaml` + optional formatter | `examples/bring-your-own/model/` |
| Benchmark | `configs/challenges/<name>.yaml` | `examples/bring-your-own/benchmark/` |
| Reward | `src/trajgym/rewards/reward.py` — configurable weights or full replacement | `docs/architecture.md` |

## Important Files

| File | Purpose |
|------|---------|
| `src/trajgym/agent/protocol.py` | Agent contracts (StepAgent, Agent, StepResult, AgentResult) |
| `src/trajgym/envs/skyrl/trajgym_env.py` | SkyRL environment bridge |
| `src/trajgym/training/online_rl/runtime.py` | ONLINE_RL orchestration (~2500 lines, largest file) |
| `src/trajgym/rewards/reward.py` | 8-signal reward function |
| `src/trajgym/envs/tool_executor.py` | Subprocess-based tool execution (13 tools) |
| `src/trajgym/parsing/tool_calls.py` | Multi-format tool call parser |
| `configs/challenges/cybench.yaml` | 40 CyBench challenge definitions |
| `docker/patches/apply_all_patches.sh` | 20 compatibility patches for SkyRL + vLLM + Ray |

## Conventions

- Training configs live in `examples/<model>/training.yaml` (per-model)
- ONLINE_RL base templates live in `src/trajgym/training/online_rl_templates/<model>.yaml`
- Challenge registries are YAML files in `configs/challenges/`
- Adapter examples live in `examples/bring-your-own/agent/`
- The SkyRL fork branch is `open-ctf/v0.3.1-patched` (this is a git branch name, not a typo)

## Dependencies

The project has strict version requirements due to Qwen3.5 hybrid attention architecture:
- vLLM >= 0.16.0, transformers >= 5.2.0 (version conflict resolved via uv overrides)
- SkyRL 0.3.1 from patched fork (not on PyPI)
- 20 runtime patches bridge SkyRL + vLLM 0.16 + Ray 2.54 gaps
