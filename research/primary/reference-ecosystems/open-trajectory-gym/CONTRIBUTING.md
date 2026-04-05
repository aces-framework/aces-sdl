# Contributing to Open Trajectory Gym

Open Trajectory Gym is a pipeline for post-training security LLMs on CTF challenge trajectories. It combines TRL for supervised fine-tuning, SkyRL for online reinforcement learning with live tool execution, and GEPA for prompt evolution -- producing locally deployable security agents from open-weight models.

## Development Setup

```bash
git clone https://github.com/westonbrown/open-trajectory-gym.git
cd open-trajectory-gym
pip install -e ".[dev]"
```

For training stages, install the relevant extras:

```bash
pip install -e ".[sft]"    # Stage 1: TRL SFT
pip install -e ".[online_rl]"   # Stage 2: SkyRL ONLINE_RL
pip install -e ".[gepa]"   # Stage 3: GEPA prompt evolution
```

## Running Tests

```bash
pytest tests/
```

All tests should pass without a GPU. Tests that require a GPU or running challenge containers are skipped automatically.

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check .
ruff format .
```

## Architecture Overview

The project has three training stages, each backed by a dedicated framework:

| Stage | Framework | Purpose |
|-------|-----------|---------|
| **SFT** | [TRL](https://github.com/huggingface/trl) | Supervised fine-tuning on expert CTF traces |
| **ONLINE_RL** | [SkyRL](https://github.com/westonbrown/SkyRL/tree/open-ctf/v0.3.1-patched) | Online reinforcement learning with live tool execution |
| **GEPA** | [DSPy](https://github.com/stanfordnlp/dspy) + [GEPA](https://arxiv.org/abs/2507.19457) | Prompt evolution (no weight updates) |

The `ToolExecutor` provides 13 tools (shell, Python, file ops, flag submission) via direct subprocess execution. During online ONLINE_RL, the model generates tool calls that execute against live Docker containers — no HTTP server required.

## Adding a New Model

1. Create a training config at `examples/<model>/training.yaml`.
2. Configure the TRL SFT parameters and SkyRL ONLINE_RL parameters.
3. If the model uses a non-standard chat template, add a formatter in `src/trajgym/formatters/`.
4. Test with the validation pipeline: `trajgym-validate`.

See existing configs (e.g., `examples/qwen35-27b/training.yaml`) for reference.

## Adding a New Benchmark

1. Add challenge entries to a YAML registry in `configs/challenges/` (docker or static type, with ID, flag, and difficulty).
2. Create ONLINE_RL training data with `ground_truth_flag` fields pointing to your challenges.
3. Pass the registry via `--challenge-registry configs/challenges/<name>.yaml`.

No changes to the reward function, tool definitions, or training loop are needed.

## Pull Request Process

1. Fork the repository and create a feature branch from `main`.
2. Make your changes with clear, descriptive commits.
3. Run `pytest tests/` and `ruff check .` to verify nothing is broken.
4. Open a PR against `main` with a description of what changed and why.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](./LICENSE).
