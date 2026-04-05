# Data Collection

Two paths to training data: **real traces** from agents solving CyBench challenges, and **synthetic traces** from a teacher LLM + simulated environment.

```
Real:      Agent → CyBench Containers → Raw Traces ─┐
                                                      ├→ trajgym-convert → JSONL
Synthetic: YAML Manifest → Mock Executor → Teacher LLM ┘
```

## Real Traces

Run any agent against CyBench's 40 CTF challenges. BoxPwnr is the reference example.

### Setup

```bash
# Clone CyBench
cd benchmarks && git clone https://github.com/andyzorigin/cybench.git cybench && cd ..

# Verify challenges
cd references/boxpwnr && uv sync && uv run boxpwnr --platform cybench --list
```

### Collect

```bash
cd references/boxpwnr

# Single challenge
uv run boxpwnr --platform cybench \
  --target "[Very Easy] Dynastic" \
  --model gpt-4o \
  --max-turns 30 --max-cost 2.0

# Batch
for target in "[Very Easy] Dynastic" "[Easy] TimeKORP" "[Medium] Partial Tenacity"; do
  uv run boxpwnr --platform cybench --target "$target" --model gpt-4o --max-turns 30 --max-cost 2.0
done
```

**Cost estimates:** GPT-4o ~$0.50-2.00/challenge, Claude Sonnet ~$0.75-3.00, Claude Haiku ~$0.10-0.50, local models free. Start cheap for bulk, use frontier models for hard challenges.

### Verify

Good traces have 10-100 messages with mixed reasoning + tool calls. SFT needs `success: true`; Online RL uses both successes and failures.

```bash
cat targets/cybench/[Very Easy]\ Dynastic/stats.json | jq '{success, flag_found}'
```

## Synthetic Traces

Offline generation using YAML manifests + mock tool execution. 1000x faster than Docker containers, with randomized flags to prevent memorization.

```
WorldManifest (YAML)  →  SimulatedEnvironmentExecutor  →  LiteLLMAgentAdapter  →  JSONL
    (scenario def)          (mock 13 agent tools)          (teacher LLM loop)
```

### Generate

```bash
trajgym-synthetic-data \
    --config configs/synthetic_data_generation/default.yaml \
    --teacher-model "openrouter/openai/gpt-4o" \
    --num-traces 500 \
    --sft-out data/synthetic_sft.jsonl
```

The executor mocks all 13 agent tools (`shell_command`, `read_file`, `python_code`, `grep`, `file_search`, `flag_found`, etc.) using manifest-driven responses. Commands match against manifest `tool_responses` via regex, substring, or token fragment — longest pattern wins.

**Teacher models:** `azure/gpt-5.2-codex` (90-100% solve rate, best quality), `openrouter/openai/gpt-4o` (~75%), free models (~25%).

See `configs/synthetic_data_generation/README.md` for manifest authoring.

## Convert to Training Data

```bash
# Successful traces → SFT, all traces → Online RL
trajgym-convert \
  --input targets/cybench/ \
  --output data/sft.jsonl \
  --output-failure data/grpo_all.jsonl \
  --dedup

# Split by token budget
trajgym-split \
  --input data/sft.jsonl \
  --sft-output data/sft_final.jsonl \
  --online-rl-output data/online_rl_final.jsonl \
  --max-online-rl-tokens 32768

# Validate
trajgym-validate
```

## Collection Strategy

Collect in order of increasing difficulty. Ensure category diversity across web (30%), crypto (20%), pwn (20%), reversing (15%), misc (10%), forensics (5%).

| Training Stage | Minimum | Recommended |
|----------------|---------|-------------|
| **SFT** | 100 traces | 500+ traces |
| **Online RL** | 50 trajectories | 200+ trajectories |

## Next Steps

- [Training Guide](training.md) -- Train with the 3-stage pipeline
- [Architecture](architecture.md) -- Module overview and data flow
