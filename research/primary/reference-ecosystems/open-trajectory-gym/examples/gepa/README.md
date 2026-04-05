# GEPA Prompt Evolution

End-to-end example of **Stage 3 (GEPA)** in the Open Trajectory Gym training pipeline.

GEPA evolves the agent's system prompt — no weight updates — by reflecting on
execution traces and using Pareto selection across challenges.

```
SFT (weights) → ONLINE_RL (weights) → GEPA (prompt only) → Deploy
```

## How it works

GEPA runs a loop of **execute → score → reflect → mutate → select**:

```
                    ┌─────────────────────────────────┐
                    │  Seed prompt (web_ctf / default) │
                    └───────────────┬─────────────────┘
                                    ▼
               ┌─────────────────────────────────────────┐
           ┌──►│  Agent LM runs ReAct episode (tool loop) │
           │   └───────────────┬─────────────────────────┘
           │                   ▼
           │   ┌─────────────────────────────────────────┐
           │   │  Reward scores trajectory             │
           │   │  (flag capture + 7 shaping signals)      │
           │   └───────────────┬─────────────────────────┘
           │                   ▼
           │   ┌─────────────────────────────────────────┐
           │   │  Reflection LM analyzes traces           │
           │   │  → diagnoses failures                    │
           │   │  → proposes mutated prompt               │
           │   └───────────────┬─────────────────────────┘
           │                   ▼
           │   ┌─────────────────────────────────────────┐
           │   │  Pareto selection: keep prompts that     │
           │   │  are best on ≥1 challenge                │
           │   └───────────────┬─────────────────────────┘
           │                   │
           └───────────────────┘  (repeat until budget exhausted)
```

Each **ReAct episode** is a multi-turn tool-calling loop:

1. LLM generates a **Thought** (reasoning) and picks a **Tool** + **Args**
2. Tool executes via `SubprocessExecutor` (real `curl`, `python3`, etc.)
3. **Observation** (tool output) feeds back into the next LLM turn
4. Repeat up to `max_iters` times or until `flag_found` succeeds

The **metric** scores each episode using `Reward` (8 signals, flag=0.40 weight).
Tool observations — including the `flag_found` verification response — are included
in the scored trajectory so the flag signal fires correctly.

## Architecture

GEPA uses two LM roles hitting the same or different endpoints:

- **Agent LM** (e.g. Qwen3.5 on local vLLM) — runs ReAct tool-calling episodes.
  This is the model whose prompt is being optimized.
- **Reflection LM** (e.g. GPT-5.2 Codex on Azure, or same model) — analyzes
  execution traces, diagnoses why the agent failed, and proposes better prompts.

Using a stronger model for reflection produces higher-quality mutations.
Both can point at the same vLLM server (different temperature settings).

## Prerequisites

```bash
# 1. Install GEPA dependencies
pip install -e ".[gepa]"

# 2. Start vLLM with your model
vllm serve /path/to/model --port 8001 --dtype bfloat16 \
  --gpu-memory-utilization 0.50 --trust-remote-code

# 3. Start the challenge container
trajgym-challenges setup --challenge '[Very Easy] Flag Command'

# 4. (Optional) Set Azure credentials for GPT-5.2 reflection
export AZURE_API_KEY="your-key"
export AZURE_API_BASE="https://your-endpoint.cognitiveservices.azure.com"
export AZURE_API_VERSION="2025-04-01-preview"
```

## Quick start

All commands run from the repo root.

**With GPT-5.2 Codex reflection** (recommended):
```bash
bash examples/gepa/run.sh \
    --model openai/qwen35-27b \
    --reflection-model azure/gpt-5.2-codex
```

**Self-reflection** (same model for both roles):
```bash
bash examples/gepa/run.sh --model openai/qwen35-27b
```

**Python** (programmatic API):
```bash
export OPENAI_API_BASE=http://localhost:8001/v1
export OPENAI_API_KEY=dummy

python examples/gepa/run.py \
    --model openai/qwen35-27b \
    --reflection-model azure/gpt-5.2-codex
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | -- | Agent model on vLLM (e.g. `openai/qwen35-27b`) |
| `--reflection-model` | same as `--model` | Reflection LM (e.g. `azure/gpt-5.2-codex`) |
| `--budget` | `light` | GEPA iterations: `light` / `medium` / `heavy` |
| `--port` / `--vllm-port` | `8001` | vLLM server port |
| `--target-port` | `32810` | Challenge container port |
| `--output` | `outputs/gepa_flag_command` | Output directory |
| `--seed-preset` | `default` | Seed prompt preset: `default` / `web_ctf` |
| `--disable-thinking` | off | Suppress `<think>` blocks (required for smaller models) |
| `--thinking-budget` | -- | Cap thinking tokens per completion (e.g. `1024`) |

## Configuration

Key parameters in the `gepa:` config section:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_iters` | 15 | Tool calls per ReAct episode. More = deeper exploitation chains |
| `max_tokens` | 4096 | LLM response token budget per step. Must be large enough to avoid truncating tool call XML |
| `max_metric_calls` | auto | Total agent episodes. 2 for a fast demo, 10-20 for real optimization |
| `max_tool_response_chars` | 16000 | Max chars kept from tool stdout. Critical — default 4096 truncates large JS/HTML files before important content |
| `seed_prompt_preset` | `default` | Named seed prompt: `default` (generic) or `web_ctf` (OWASP methodology) |
| `disable_thinking` | false | Suppress `<think>` blocks via `chat_template_kwargs`. Required for models where vLLM ignores `thinking_token_budget` |
| `temperature` | 0.7 | Agent LM sampling temperature |
| `model_kwargs` | -- | Extra sampling params (e.g. `{top_k: 20, top_p: 0.95}`) |
| `reflection_temperature` | 1.0 | Reflection LM temperature. Set to `null` for models that don't support it (e.g. GPT-5.2 Codex) |
| `reflection_max_tokens` | 32000 | Reflection LM token budget |
| `num_threads` | 1 | Parallel episodes. Only safe with custom thread-safe tools (default ToolExecutor is a singleton) |

### Recommended configs

**27B model** (thinking enabled):
```yaml
gepa:
  max_iters: 15
  max_tokens: 6144
  max_metric_calls: 4
  max_tool_response_chars: 16000
  reflection_temperature: null       # for GPT-5.2 Codex
  reflection_max_tokens: 16000
```

**9B model** (thinking disabled):
```yaml
gepa:
  max_iters: 10
  max_tokens: 4096
  max_metric_calls: 4
  seed_prompt_preset: web_ctf
  disable_thinking: true             # required — vLLM ignores thinking_token_budget
  temperature: 0.5
  max_tool_response_chars: 16000
  model_kwargs: {top_k: 20, top_p: 0.95}
  reflection_temperature: null
  reflection_max_tokens: 16000
```

## Output

```
outputs/gepa_flag_command/
  optimized_prompt.txt      # The evolved system prompt (CTF instructions only)
  optimized_prompt_raw.txt  # Raw prompt with DSPy ReAct framing
  gepa_results.json         # Scores per candidate
  gepa_logs/                # Full optimizer traces
  optimized_agent.json      # Saved DSPy module (reusable)
```

## Scoring

Each episode is scored by `Reward` using 8 weighted signals:

| Signal | Weight | What it measures |
|--------|--------|------------------|
| Flag | 0.40 | Exact flag match (1.0), pattern match (0.1), none (0.0) |
| Efficiency | 0.15 | `min(optimal_steps / actual_steps, 1.0)` |
| Format | 0.10 | Valid tool calls and reasoning structure |
| Recovery | 0.09 | Pivots from stuck states |
| Progression | 0.08 | RECON → ENUM → EXPLOIT phase ordering |
| Cognitive | 0.08 | Reasoning density (optimal: 42 words per action) |
| Exploration | 0.05 | Novelty with temporal decay |
| Uniqueness | 0.05 | Information entropy of unique commands |

The metric includes all **tool observations** (stdout from each tool call) in the
scored text, so the flag verification signal (`"Correct! Flag verified"`) from
`flag_found` is visible to the reward function. Without observations, flag capture
goes undetected and all scores collapse to near-zero.

A wrong flag submission triggers a **hallucination penalty** (-0.20) that decays
all other signals to 30%.

## Troubleshooting

**All scores are 0.0 / "No valid predictions found"**
- Check `max_tokens` — too low truncates the model's response mid-tool-call,
  breaking DSPy's ReAct format parser. Use at least 4096.
- Check `max_tool_response_chars` — default 4096 truncates large files (JS source,
  HTML) before critical content like API endpoints. Use 16000 for web challenges.
- Check `OPENAI_API_KEY` and `OPENAI_API_BASE` are set (even `dummy` for local vLLM).

**Scores are low (~2-5%) despite the model solving the challenge**
- The metric may not see tool observations. Verify you're on a version that
  includes `pred.trajectory` observations in the scored completion text.

**`disable_thinking` vs `thinking_token_budget`**
- vLLM 0.16 ignores `thinking_token_budget` (warning: "field was present but ignored").
  Use `disable_thinking: true` instead, which passes `chat_template_kwargs:
  {"enable_thinking": false}` via `extra_body`.
- Without this fix, smaller models (9B) generate verbose `<think>` blocks consuming
  80%+ of the token budget, leaving too few tokens for tool calls.

**Flag found but score is low**
- The model may alter leetspeak characters when transcribing the flag (e.g. `b35t` → `b3st`).
  The `web_ctf` seed preset includes explicit flag-copy instructions to prevent this.

**Episodes take 15+ minutes**
- With thinking enabled on 9B models, episodes can take 16+ minutes. Use
  `disable_thinking: true` to drop to ~75 seconds per episode.
- Three concurrent GEPA runs share the same vLLM endpoint — contention slows all.

## Files

| File | Purpose |
|------|---------|
| `challenge.jsonl` | Single-challenge JSONL data (Flag Command) |
| `run.sh` | Shell wrapper with preflight checks and env setup |
| `run.py` | Python script using the `run_gepa()` API directly |
