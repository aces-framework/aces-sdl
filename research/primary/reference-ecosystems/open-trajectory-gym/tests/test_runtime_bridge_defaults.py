"""Guardrails for default BoxPwnr runtime bridge wiring."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "examples" / "qwen35-27b"
SMOKE_SCRIPT = REPO_ROOT / "examples" / "smoke-test" / "smoke_test.sh"

EXPECTED_AGENT = "trajgym.agent.default_agent.DefaultStepAgent"
EXPECTED_RUNTIME_CMD = "python src/trajgym/agent/framework_runtime_bridge.py"
EXPECTED_FRAMEWORK = "boxpwnr_langgraph"
EXPECTED_MODE = "tool_calls"


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def test_all_training_configs_default_to_boxpwnr_bridge_profile() -> None:
    # Only check top-level training configs, not archive/
    paths = sorted(CONFIG_DIR.glob("training*.yaml"))
    assert paths, "No training*.yaml configs found"

    # Minimal smoke configs that skip bridge wiring entirely.
    SKIP_CONFIGS = {"training_e2e_smoke.yaml"}
    # Smoke configs with agent_class but no bridge subprocess.
    BRIDGE_OPT_OUT_CONFIGS = {"training_smoke_2ch.yaml"}

    checked = 0
    for path in paths:
        if path.name in SKIP_CONFIGS:
            continue
        cfg = _load_yaml(path)
        online_rl = cfg.get("online_rl")
        if not isinstance(online_rl, dict):
            continue
        checked += 1

        assert online_rl.get("agent_class") == EXPECTED_AGENT, path.name
        agent_kwargs = online_rl.get("agent_kwargs")
        assert isinstance(agent_kwargs, dict), path.name

        if path.name in BRIDGE_OPT_OUT_CONFIGS:
            # Opted-out configs must NOT have runtime_cmd and should enable
            # local fallback parsing.
            assert agent_kwargs.get("runtime_cmd") is None, path.name
            assert agent_kwargs.get("runtime_fallback_to_parser") is True, path.name
            continue

        assert agent_kwargs.get("runtime_cmd") == EXPECTED_RUNTIME_CMD, path.name
        assert agent_kwargs.get("runtime_passthrough") is False, path.name
        assert agent_kwargs.get("runtime_fallback_to_parser") is False, path.name

        runtime_env = agent_kwargs.get("runtime_env")
        assert isinstance(runtime_env, dict), path.name
        assert (
            runtime_env.get("TRAJGYM_AGENT_FRAMEWORK") == EXPECTED_FRAMEWORK
        ), path.name
        assert runtime_env.get("TRAJGYM_AGENT_MODE") == EXPECTED_MODE, path.name

    assert checked > 0, "No online_rl sections found in training configs"


def test_smoke_script_supports_native_boxpwnr_mode() -> None:
    text = SMOKE_SCRIPT.read_text(encoding="utf-8")
    assert "--native-boxpwnr" in text
    assert "TRAJGYM_AGENT_MODE" in text
    assert "TRAJGYM_AGENT_CMD" in text
    assert "langgraph_adapter.py" in text
