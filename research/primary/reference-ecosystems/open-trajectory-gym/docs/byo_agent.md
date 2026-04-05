# BYO Agent Guide

Open Trajectory Gym uses a **two-protocol system** for pluggable agents. Which protocol you implement depends on your integration point:

| Protocol | Used By | You Own | SkyRL Owns |
|----------|---------|---------|------------|
| **StepAgent** | Online RL training | Tool parsing + execution | Generation (vLLM) |
| **Agent** | Evaluation, GEPA | Generation + execution | Nothing |

## Quick Start: StepAgent (Online RL Training)

Implement `reset`, `step`, `close`, and a `tools` property:

```python
from trajgym.agent.protocol import StepAgent, StepResult, validate_step_agent

class MyStepAgent:
    """Minimal StepAgent for Online RL training."""

    def reset(self, target="", ground_truth_flag="", max_steps=30, **kwargs):
        self.target = target
        # These 5 attributes are read by the env for reward scoring.
        # Missing any of them silently degrades 7 of 8 reward signals.
        self.tool_calls_history = []
        self.tool_outputs = []
        self.all_text = ""
        self.episode_done = False
        self.turns = 0

    def step(self, action: str) -> StepResult:
        self.turns += 1
        # Parse tool calls from `action` (raw LLM output)
        # Execute tools your way
        # Update self.tool_calls_history, self.tool_outputs, self.all_text
        return StepResult(
            observations=[{"role": "user", "content": "[Tool: shell_command]\n$ ls\nflag.txt"}],
            done=False,
        )

    def close(self):
        pass

    @property
    def tools(self):
        return None  # None = use environment defaults (13 CTF tools)

# Validate after construction
agent = MyStepAgent()
warnings = validate_step_agent(agent)
for w in warnings:
    print(f"WARNING: {w}")

assert isinstance(agent, StepAgent)  # Structural subtyping check
```

## Quick Start: Agent (Eval / GEPA)

Implement a single `solve` method:

```python
from trajgym.agent.protocol import Agent, AgentResult

class MyEvalAgent:
    """Minimal Agent for evaluation."""

    def solve(self, challenge, target, ground_truth_flag="",
              max_steps=30, timeout=300) -> AgentResult:
        # Your full agent loop: generate + parse + execute + repeat
        return AgentResult(success=True, flag="FLAG{found_it}", steps=5)

assert isinstance(MyEvalAgent(), Agent)
```

## Integration Options

| Method | Mode | Config | Best For |
|--------|------|--------|----------|
| **Direct class** | `tool_calls` | `agent_class: "my_module.MyAgent"` | Custom parsing/execution in Python |
| **Runtime bridge (tool_calls)** | `tool_calls` | `TRAJGYM_AGENT_MODE=tool_calls` | Default — TrajGym parses + executes |
| **Runtime bridge (native)** | `native` | `TRAJGYM_AGENT_MODE=native` | External framework owns execution |

### Direct Class (Recommended for Custom Agents)

Point the training config at your StepAgent class:

```yaml
online_rl:
  agent_class: my_module.MyStepAgent
```

### Runtime Bridge (tool_calls mode)

Default mode — TrajGym parses tool calls and executes them locally:

```yaml
agent_kwargs:
  runtime_cmd: "python src/trajgym/agent/framework_runtime_bridge.py"
  runtime_timeout_seconds: 20
  runtime_passthrough: false
  runtime_env:
    TRAJGYM_AGENT_FRAMEWORK: "generic"
    TRAJGYM_AGENT_MODE: "tool_calls"
```

### Runtime Bridge (native mode)

For frameworks like LangGraph that run as external processes and own tool execution:

```yaml
agent_kwargs:
  runtime_passthrough: true
  runtime_env:
    TRAJGYM_AGENT_FRAMEWORK: "langgraph"
    TRAJGYM_AGENT_MODE: "native"
    TRAJGYM_AGENT_CMD: "python examples/bring-your-own/agent/langgraph_adapter.py"
```

Your adapter reads JSON from stdin and writes a response to stdout.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TRAJGYM_AGENT_MODE` | Yes | `tool_calls` (TrajGym parses + executes) or `native` (your framework owns execution) |
| `TRAJGYM_AGENT_FRAMEWORK` | No | Framework name for logging (default: `generic`) |
| `TRAJGYM_AGENT_CMD` | Native only | External adapter command (e.g. `python my_adapter.py`) |
| `TRAJGYM_AGENT_CMD_TIMEOUT` | No | Timeout in seconds for adapter subprocess |
| `TRAJGYM_AGENT_WORKDIR` | No | Working directory for adapter subprocess |

## Native Mode Adapter Contract

In `native` mode, your adapter receives a JSON request on stdin containing `action`, `turn`, `runtime_state`, `prompt_messages`, `challenge` metadata, and `objective`. Return either:

1. A full runtime protocol response (`protocol_version`, `capabilities`, etc.), or
2. A simplified object that the bridge wraps automatically:

```json
{
  "done": false,
  "episode_done": false,
  "observations": [{"role": "user", "content": "..." }],
  "state": {"k": "v"},
  "info": {"rollout_status": "ok"},
  "tool_calls": [{"name": "shell_command", "arguments": {"command": "echo hi"}}]
}
```

See `examples/bring-your-own/agent/template_adapter.py` for a copy-and-customize starting point.

## Reward-Critical Attributes

The env reads these 5 attributes from your StepAgent via `getattr(agent, attr, default)` after each step. **If any are missing, 7 of 8 reward signals silently degrade to zero.**

| Attribute | Type | Default | Reward Signals Affected |
|-----------|------|---------|------------------------|
| `tool_calls_history` | `list[dict[str, str]]` | `[]` | format, efficiency, exploration, uniqueness, recovery |
| `tool_outputs` | `list[str]` | `[]` | progression, cognitive, flag detection |
| `all_text` | `str` | `""` | cognitive (words-per-action), hallucination detection |
| `episode_done` | `bool` | `False` | flag signal (exact match gating) |
| `turns` | `int` | `0` | efficiency signal |

Initialize them in `reset()` and update them in `step()`. The env calls `validate_step_agent(agent)` automatically at startup and logs any warnings.

## Custom Tool Schemas

Return `None` from the `tools` property to use the environment's default 13 CTF tools. To override:

```python
@property
def tools(self):
    return [
        {
            "type": "function",
            "function": {
                "name": "my_tool",
                "description": "Custom tool",
                "parameters": {
                    "type": "object",
                    "properties": {"input": {"type": "string"}},
                    "required": ["input"],
                },
            },
        }
    ]
```

## Adapter Templates

Ready-to-use adapters in `examples/bring-your-own/agent/`:

| Adapter | Type | Description |
|---------|------|-------------|
| `template_adapter.py` | Generic | Copy-and-customize starting point for any framework |
| `langgraph_adapter.py` | Functional | Production LangGraph adapter |
| `langgraph_stub_adapter.py` | Stub | Lightweight LangGraph template for quick tests |
| `boxpwnr_adapter.py` | Functional | BoxPwnr compatibility shim |

## Testing and Validation

### Contract Validation

```python
from trajgym.agent.protocol import validate_step_agent

agent = MyStepAgent()
warnings = validate_step_agent(agent)
assert not warnings, f"Agent validation failed: {warnings}"
```

### Run Existing Tests

```bash
python -m pytest tests/test_agent_protocol.py tests/test_framework_runtime_bridge.py \
    tests/test_framework_runtime_adapters.py tests/test_runtime_protocol.py -v
```

### Test a Native Adapter

```bash
echo '{"action":"test","turn":1,"runtime_state":{}}' | python examples/bring-your-own/agent/template_adapter.py
```

## Further Reading

- **Adapter examples**: `examples/bring-your-own/agent/`
- **Training configuration**: `docs/training.md`
- **Protocol source**: `src/trajgym/agent/protocol.py`
- **Default agent implementation**: `src/trajgym/agent/default_agent.py`
- **Runtime bridge source**: `src/trajgym/agent/framework_runtime_bridge.py`
