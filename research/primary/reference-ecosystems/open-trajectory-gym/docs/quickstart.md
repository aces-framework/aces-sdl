# Quick Start

Get up and running with Open Trajectory Gym in minutes.

## Prerequisites

- Docker and Docker Compose
- If running inside another container (for example a cloud GPU instance), Docker must have privileges to create networks and run nested containers (`docker network create` and `docker run` must work)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- An LLM backend (Ollama, llama.cpp, vLLM, or any OpenAI-compatible API)

## Installation

### uv (recommended)

```bash
git clone https://github.com/westonbrown/open-trajectory-gym.git
cd open-trajectory-gym

# Install all training deps (SFT + Online RL + dev tools)
uv sync --extra online-rl --extra sft --extra dev

# Install SkyRL-Train from our patched fork (not on PyPI):
git clone -b open-ctf/v0.3.1-patched https://github.com/westonbrown/SkyRL.git skyrl
sed -i 's/requires-python = "==3.12\.\*"/requires-python = ">=3.11"/' \
    skyrl/skyrl-train/pyproject.toml
uv pip install -e skyrl/skyrl-train --no-deps

# Apply vLLM/Ray compatibility patches (4 remaining runtime patches)
bash docker/patches/apply_all_patches.sh
```

### pip

```bash
git clone https://github.com/westonbrown/open-trajectory-gym.git
cd open-trajectory-gym

# Install core only
pip install -e .

# For SFT training (TRL)
pip install -e ".[sft]"

# For Online RL training (SkyRL + Ray + vLLM)
pip install -e ".[online-rl]"
# Force transformers 5.2.0 (vLLM pins <5 but Qwen3.5 needs >=5.2.0)
pip install 'transformers>=5.2.0' 'huggingface-hub>=1.4' --no-deps
# Install SkyRL-Train from our patched fork (not on PyPI):
git clone -b open-ctf/v0.3.1-patched https://github.com/westonbrown/SkyRL.git skyrl
sed -i 's/requires-python = "==3.12\.\*"/requires-python = ">=3.11"/' \
    skyrl/skyrl-train/pyproject.toml
pip install -e skyrl/skyrl-train --no-deps
# Apply vLLM/Ray compatibility patches
bash docker/patches/apply_all_patches.sh

# For GEPA prompt optimization (DSPy)
pip install -e ".[gepa]"

# For agent runner
pip install -e ".[agent]"
```

## Setup

```bash
# Clone BoxPwnr reference agent (optional — example agent with CyBench support)
git clone https://github.com/0ca/BoxPwnr.git references/boxpwnr

# Clone CyBench benchmarks (40 professional CTF challenges)
git clone https://github.com/andyzorigin/cybench.git benchmarks/cybench

# Copy environment config
cp env.example .env
# Edit .env with your API keys and preferences
```

## Verify Installation

```bash
trajgym-validate
```

This checks data format, reward functions, training scripts, tool registry, and model formatters without requiring a GPU.

## Common Workflows

### Run the Agent

```bash
# Against a CyBench challenge
trajgym-agent \
    --platform cybench \
    --target "[Very Easy] Dynastic" \
    --model openrouter/openai/gpt-oss-120b \
    --max-turns 30

# With a local Ollama model
trajgym-agent \
    --platform cybench \
    --target "[Easy] TimeKORP" \
    --model ollama/qwen3:8b
```

### Convert Traces to Training Data

```bash
# Convert and split traces
trajgym-convert \
    --input targets/ \
    --output data/all_traces.jsonl \
    --output-failure data/failed_traces.jsonl \
    --dedup

cat data/all_traces.jsonl data/failed_traces.jsonl > data/combined.jsonl
trajgym-split --input data/combined.jsonl
```

### Train a Model (3-Stage Pipeline)

```bash
# Stage 1: SFT via TRL
trajgym-train sft \
    --model Qwen/Qwen3.5-4B \
    --data data/sft.jsonl \
    --output outputs/sft

# Merge LoRA adapter into base model
trajgym-train merge \
    --adapter outputs/sft \
    --base-model Qwen/Qwen3.5-4B \
    --output outputs/sft-merged

# Stage 2: Online RL (RLOO/DAPO) via SkyRL
trajgym-train rl \
    --model outputs/sft-merged \
    --data data/online_rl.jsonl \
    --output outputs/online_rl \
    --config examples/qwen35-4b/training.yaml

# Stage 3: GEPA prompt optimization (no weight updates)
trajgym-train gepa \
    --model openai/ctf-agent \
    --data data/online_rl.jsonl \
    --output outputs/gepa \
    --reflection-model openai/ctf-reflection \
    --challenge-registry configs/challenges/cybench.yaml
```

Note: `trajgym-train rl` runs a preflight validation gate and, by default, requires `<data>.manifest.json` produced by `src/trajgym/cli/generate_online_rl.py`.

### Export for Deployment

```bash
trajgym-export \
    --adapter outputs/online_rl/final \
    --base-model Qwen/Qwen3.5-4B \
    --output models/ctf-agent.gguf \
    --quant Q4_K_M
```

## Docker Workflows

```bash
# Stage 1: SFT
docker compose run --rm sft

# Merge LoRA
docker compose run --rm merge

# Stage 2: Online RL (RLOO/DAPO)
docker compose run --rm online_rl

# Validate pipeline
docker compose run --rm validate

# Export to GGUF
docker compose run --rm export
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TRAJGYM_PROVIDER` | Model provider | `ollama` |
| `TRAJGYM_MODEL` | LLM model ID | `ollama/qwen3:8b` |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `TRAJGYM_OUTPUT_DIR` | Output directory | `./outputs` |

## Next Steps

- [Training Guide](training.md) -- Full 3-stage pipeline details
- [Deployment](architecture.md#deployment) -- Deploy trained models
- [Data Collection](data-collection.md) -- Real + synthetic training data
- [Architecture](architecture.md) -- Module overview and data flow
