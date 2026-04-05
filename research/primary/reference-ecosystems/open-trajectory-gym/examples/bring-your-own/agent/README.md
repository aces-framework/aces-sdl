# Bring Your Own Agent

Integrate any external agent framework with Open Trajectory Gym training and eval.

## Integration Modes

### tool_calls mode (default)

TrajGym parses tool calls from LLM output and executes them locally. No adapter needed.

```yaml
agent_kwargs:
  runtime_env:
    TRAJGYM_AGENT_MODE: "tool_calls"
```

### native mode

Your external adapter owns tool execution. Each adapter reads JSON from stdin and prints JSON to stdout.

```yaml
agent_kwargs:
  runtime_passthrough: true
  runtime_env:
    TRAJGYM_AGENT_MODE: "native"
    TRAJGYM_AGENT_CMD: "python examples/bring-your-own/agent/my_adapter.py"
```

## Quick Start

Test an adapter with a request:

```bash
echo '{"action":"test","turn":1,"runtime_state":{}}' \
  | python examples/bring-your-own/agent/template_adapter.py
```

Use in training by setting the runtime env in your config:

```yaml
agent_kwargs:
  runtime_passthrough: true
  runtime_env:
    TRAJGYM_AGENT_MODE: "native"
    TRAJGYM_AGENT_CMD: "python examples/bring-your-own/agent/template_adapter.py"
```

## Available Adapters

| Adapter | Status | Purpose |
|---------|--------|---------|
| `template_adapter.py` | Template | Generic copy-and-customize starting point for any framework |
| `langgraph_adapter.py` | Functional | Production LangGraph adapter with strict request validation |
| `langgraph_stub_adapter.py` | Stub | Lightweight LangGraph stub for quick integration tests |
| `boxpwnr_adapter.py` | Functional | BoxPwnr compatibility shim (delegates to langgraph_adapter) |

## Creating a New Adapter

1. Copy the template:
   ```bash
   cp examples/bring-your-own/agent/template_adapter.py \
      examples/bring-your-own/agent/my_adapter.py
   ```

2. Implement the `handle_step` function with your framework's logic. The function receives the full runtime request and returns a response dict.

3. Test it:
   ```bash
   echo '{"action":"test","turn":1,"runtime_state":{}}' \
     | python examples/bring-your-own/agent/my_adapter.py
   ```

4. Wire it into training config:
   ```yaml
   agent_kwargs:
     runtime_passthrough: true
     runtime_env:
       TRAJGYM_AGENT_MODE: "native"
       TRAJGYM_AGENT_CMD: "python examples/bring-your-own/agent/my_adapter.py"
   ```

## Minimal Response Shape

```json
{
  "done": false,
  "episode_done": false,
  "observations": [{"role": "user", "content": "..."}],
  "state": {},
  "info": {"rollout_status": "ok"}
}
```

## Testing

Run the contract smoke tests to verify protocol compliance:

```bash
python -m pytest tests/test_framework_runtime_adapters.py \
    tests/test_framework_runtime_bridge.py \
    tests/test_runtime_protocol.py -v
```

## Further Reading

- Runtime bridge details: `src/trajgym/agent/framework_runtime_bridge.py`
- Protocol source: `src/trajgym/agent/protocol.py`
- BYO runtime example: `examples/byo_runtime_example.py`
