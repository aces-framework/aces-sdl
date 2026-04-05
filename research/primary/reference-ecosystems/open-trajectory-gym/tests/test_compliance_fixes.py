"""Tests verifying OpenThoughts-Agent compliance fixes.

Covers 6 verification areas:
1. _all_text includes tool output (for reward signal visibility)
2. Observations use role="user" (SkyRL apply_chat_template compatibility)
3. Error classification works (tool execution failures handled)
4. Per-step reward range is [0.0, 0.20]
5. Bare JSON regex handles nested braces in arguments
6. RLOO-N config is generated correctly
"""

import json
from unittest.mock import MagicMock

import pytest
from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv
from trajgym.parsing import parse_tool_calls
from trajgym.training.online_rl.runtime import _build_skyrl_config
from trajgym.training.online_rl.step_reward import per_step_reward

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tc(name: str, args: dict | str = "{}") -> dict:
    """Build a tool call dict."""
    if isinstance(args, dict):
        args = json.dumps(args)
    return {"name": name, "arguments": args}


def _shell(cmd: str) -> dict:
    return _tc("shell_command", {"command": cmd})


def _make_env(**kwargs):
    """Create an TrajGymTextEnv with a mocked executor inside the agent.

    Overrides the agent's reset() to preserve the mock executor across
    init() calls. The mock is injected once and never replaced.
    """
    mock_exec = MagicMock()
    mock_exec.reset.return_value = {}
    mock_exec.close.return_value = None
    mock_exec.step.return_value = {"stdout": "", "stderr": "", "done": False}

    env = TrajGymTextEnv(
        extras={
            "ground_truth_flag": kwargs.get("ground_truth_flag", "FLAG{test}"),
            "optimal_steps": kwargs.get("optimal_steps", 5),
            "max_turns": kwargs.get("max_turns", 10),
        },
    )
    # Inject mock executor into the agent
    env._agent._executor = mock_exec

    # Override agent.reset() so it clears state without replacing the mock
    def _mock_reset(target="", ground_truth_flag="", max_steps=30, **kw):
        env._agent.tool_calls_history = []
        env._agent.tool_outputs = []
        env._agent.all_text = ""
        env._agent.episode_done = False
        env._agent.turns = 0
        env._agent.max_steps = max_steps

    env._agent.reset = _mock_reset

    # Alias for backward-compatible test access
    env._executor = mock_exec
    return env


# ===========================================================================
# 1. _all_text includes tool output
# ===========================================================================


class TestAllTextIncludesToolOutput:
    """Verify that _all_text accumulates both LLM action and tool output.

    Before fix: _all_text only had model output (action).
    After fix: _all_text += tool output, so reward can see
    'Correct! Flag verified' and other tool responses.
    """

    def test_tool_output_appended_to_all_text(self):
        env = _make_env()
        env._executor.step.return_value = {
            "stdout": "80/tcp open http",
            "stderr": "",
            "done": False,
        }

        prompt = [
            {"role": "system", "content": "You are a CTF agent."},
            {"role": "user", "content": "Scan the target."},
        ]
        env.init(prompt)

        action = '<tool_call>\n{"name": "shell_command", "arguments": {"command": "nmap target"}}\n</tool_call>'
        env.step(action)

        assert "80/tcp open http" in env._all_text
        assert "nmap target" in env._all_text  # action text also present

    def test_flag_verified_visible_in_all_text(self):
        """Reward function checks for 'Correct! Flag verified' in _all_text."""
        env = _make_env()
        env._executor.step.return_value = {
            "stdout": "Correct! Flag verified: FLAG{test}",
            "stderr": "",
            "done": True,
        }

        prompt = [
            {"role": "system", "content": "Agent."},
            {"role": "user", "content": "Find the flag."},
        ]
        env.init(prompt)

        action = '<tool_call>\n{"name": "flag_found", "arguments": {"content": "FLAG{test}"}}\n</tool_call>'
        env.step(action)

        assert "Correct! Flag verified" in env._all_text

    def test_multiple_tool_outputs_accumulated(self):
        env = _make_env()
        env._executor.step.side_effect = [
            {"stdout": "output_1", "stderr": "", "done": False},
            {"stdout": "output_2", "stderr": "", "done": False},
        ]

        prompt = [
            {"role": "system", "content": "Agent."},
            {"role": "user", "content": "Go."},
        ]
        env.init(prompt)

        action1 = '<tool_call>\n{"name": "shell_command", "arguments": {"command": "ls"}}\n</tool_call>'
        env.step(action1)

        action2 = '<tool_call>\n{"name": "shell_command", "arguments": {"command": "cat /etc/passwd"}}\n</tool_call>'
        env.step(action2)

        assert "output_1" in env._all_text
        assert "output_2" in env._all_text

    def test_stderr_included_in_all_text(self):
        env = _make_env()
        env._executor.step.return_value = {
            "stdout": "partial output",
            "stderr": "permission denied",
            "done": False,
        }

        prompt = [
            {"role": "system", "content": "Agent."},
            {"role": "user", "content": "Go."},
        ]
        env.init(prompt)

        action = '<tool_call>\n{"name": "shell_command", "arguments": {"command": "cat /etc/shadow"}}\n</tool_call>'
        env.step(action)

        assert "partial output" in env._all_text
        assert "permission denied" in env._all_text


# ===========================================================================
# 2. Observations use role="user"
# ===========================================================================


class TestObservationRole:
    """Verify observations use role='user' for SkyRL compatibility.

    SkyRL's apply_chat_template expects role alternation:
      user -> assistant -> user -> assistant
    All built-in SkyRL envs return observations with role='user'.
    """

    def test_tool_output_observation_has_user_role(self):
        env = _make_env()
        env._executor.step.return_value = {
            "stdout": "scan results",
            "stderr": "",
            "done": False,
        }

        prompt = [
            {"role": "system", "content": "Agent."},
            {"role": "user", "content": "Go."},
        ]
        env.init(prompt)

        action = '<tool_call>\n{"name": "shell_command", "arguments": {"command": "nmap target"}}\n</tool_call>'
        result = env.step(action)

        obs = result["observations"]
        assert len(obs) >= 1
        for msg in obs:
            assert (
                msg["role"] == "user"
            ), f"Expected role='user', got role='{msg['role']}'"

    def test_no_tool_call_observation_has_user_role(self):
        env = _make_env()

        prompt = [
            {"role": "system", "content": "Agent."},
            {"role": "user", "content": "Go."},
        ]
        env.init(prompt)

        # Plain text (no tool call)
        result = env.step("I'm thinking about the approach...")

        obs = result["observations"]
        if obs:  # Non-terminal step with no tool call returns guidance
            for msg in obs:
                assert msg["role"] == "user"

    def test_observation_content_includes_tool_name(self):
        """Observations embed tool name in content for context."""
        env = _make_env()
        env._executor.step.return_value = {
            "stdout": "file contents here",
            "stderr": "",
            "done": False,
        }

        prompt = [
            {"role": "system", "content": "Agent."},
            {"role": "user", "content": "Go."},
        ]
        env.init(prompt)

        action = '<tool_call>\n{"name": "read_file", "arguments": {"file_path": "/etc/passwd"}}\n</tool_call>'
        result = env.step(action)

        obs = result["observations"]
        assert len(obs) == 1
        assert "[Tool: read_file]" in obs[0]["content"]
        assert "file contents here" in obs[0]["content"]

    def test_multiple_tool_calls_all_user_role(self):
        env = _make_env()
        env._executor.step.side_effect = [
            {"stdout": "result1", "stderr": "", "done": False},
            {"stdout": "result2", "stderr": "", "done": False},
        ]

        prompt = [
            {"role": "system", "content": "Agent."},
            {"role": "user", "content": "Go."},
        ]
        env.init(prompt)

        action = (
            '<tool_call>\n{"name": "shell_command", "arguments": {"command": "ls"}}\n</tool_call>\n'
            '<tool_call>\n{"name": "read_file", "arguments": {"file_path": "/etc/hosts"}}\n</tool_call>'
        )
        result = env.step(action)

        obs = result["observations"]
        assert len(obs) == 2
        for msg in obs:
            assert msg["role"] == "user"


# ===========================================================================
# 3. Error classification works
# ===========================================================================


class TestErrorClassification:
    """Verify tool execution errors are handled gracefully."""

    def test_executor_exception_returns_error_message(self):
        env = _make_env()
        env._executor.step.side_effect = RuntimeError("Container not running")

        prompt = [
            {"role": "system", "content": "Agent."},
            {"role": "user", "content": "Go."},
        ]
        env.init(prompt)

        action = '<tool_call>\n{"name": "shell_command", "arguments": {"command": "ls"}}\n</tool_call>'
        result = env.step(action)

        obs = result["observations"]
        assert len(obs) == 1
        assert "[ERROR]" in obs[0]["content"]
        assert "Container not running" in obs[0]["content"]
        assert not result["done"]  # Error doesn't end episode

    def test_executor_error_still_accumulates_in_all_text(self):
        env = _make_env()
        env._executor.step.side_effect = ConnectionError("Connection refused")

        prompt = [
            {"role": "system", "content": "Agent."},
            {"role": "user", "content": "Go."},
        ]
        env.init(prompt)

        action = '<tool_call>\n{"name": "shell_command", "arguments": {"command": "curl target"}}\n</tool_call>'
        env.step(action)

        assert "[ERROR]" in env._all_text
        assert "Connection refused" in env._all_text

    def test_error_observation_has_user_role(self):
        env = _make_env()
        env._executor.step.side_effect = TimeoutError("Command timed out")

        prompt = [
            {"role": "system", "content": "Agent."},
            {"role": "user", "content": "Go."},
        ]
        env.init(prompt)

        action = '<tool_call>\n{"name": "shell_command", "arguments": {"command": "sleep 999"}}\n</tool_call>'
        result = env.step(action)

        obs = result["observations"]
        assert len(obs) == 1
        assert obs[0]["role"] == "user"


# ===========================================================================
# 4. Per-step reward is always 0.0 (binary terminal reward)
# ===========================================================================


class TestPerStepRewardRange:
    """Verify per_step_reward always returns 0.0.

    All reward signal comes from the terminal Reward computation.
    Intermediate rewards are zero to avoid diluting the RLOO-N advantage
    signal (OpenThoughts-Agent methodology).
    """

    def test_empty_tool_calls_returns_zero(self):
        assert per_step_reward([], 1) == 0.0

    def test_single_tool_returns_zero(self):
        tool_calls = [_shell("nmap target")]
        assert per_step_reward(tool_calls, 1) == 0.0

    def test_diverse_tools_returns_zero(self):
        diverse = [
            _shell("nmap target"),
            _tc("python_code", {"code": "x"}),
            _tc("read_file", {"path": "/tmp/x"}),
            _tc("grep", {"pattern": "flag"}),
            _shell("curl target"),
            _tc("flag_found", {"content": "FLAG{x}"}),
        ]
        assert per_step_reward(diverse, 5) == 0.0

    def test_all_steps_return_zero(self):
        tool_calls = [_shell("ls")]
        for step in range(1, 20):
            assert per_step_reward(tool_calls, step) == 0.0

    def test_max_diversity_returns_zero(self):
        """Even with maximum diversity, intermediate reward is 0.0."""
        max_diverse = [
            _tc("web_search", {"query": "vuln"}),
            _tc("read_file", {"path": "/etc/passwd"}),
            _tc("python_code", {"code": "exploit()"}),
            _tc("grep", {"pattern": "flag"}),
            _tc("file_search", {"pattern": "*.txt"}),
            _shell("nmap target"),
            _tc("apply_patch", {"patch": "..."}),
        ]
        assert per_step_reward(max_diverse, 7) == 0.0


# ===========================================================================
# 5. Bare JSON regex handles nested braces
# ===========================================================================


class TestBareJSONNestedBraces:
    """Verify _BARE_JSON_PATTERN handles nested braces in arguments.

    Before fix: pattern used [^{}]* which failed on {"command": "echo {hello}"}
    After fix: pattern uses (?:[^{}]|\\{[^{}]*\\})* to allow one nesting level.
    """

    def test_simple_bare_json(self):
        text = '{"name": "shell_command", "arguments": {"command": "ls -la"}}'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
        assert calls[0]["arguments"]["command"] == "ls -la"

    def test_nested_braces_in_arguments(self):
        """Command containing braces like echo {hello} should parse."""
        text = '{"name": "shell_command", "arguments": {"command": "echo {hello}"}}'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
        assert calls[0]["arguments"]["command"] == "echo {hello}"

    def test_json_in_command(self):
        """Command with JSON-like content should parse."""
        text = '{"name": "shell_command", "arguments": {"command": "curl -d {\\"key\\": \\"val\\"}"}}'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"

    def test_python_code_with_braces(self):
        """Python code containing dict literals should parse."""
        text = '{"name": "python_code", "arguments": {"code": "d = {1: 2}"}}'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "python_code"

    def test_hermes_format_still_preferred_over_bare_json(self):
        """Hermes format takes priority even when bare JSON would also match."""
        text = (
            '<tool_call>\n{"name": "shell_command", "arguments": {"command": "echo {test}"}}\n</tool_call>\n'
            '{"name": "read_file", "arguments": {"path": "/tmp"}}'
        )
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
        assert calls[0]["arguments"]["command"] == "echo {test}"


# ===========================================================================
# 6. RLOO-N config is generated correctly
# ===========================================================================


class TestRLOONConfig:
    """Verify _build_skyrl_config generates RLOO-N advantage estimator."""

    @pytest.fixture
    def base_config(self):
        return {
            "model": {"max_seq_length": 8192},
            "lora": {
                "r": 64,
                "alpha": 128,
                "dropout": 0.0,
                "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
            },
            "online_rl": {
                "learning_rate": 5e-6,
                "num_generations": 8,
                "max_completion_length": 4096,
                "max_tool_calling_iterations": 15,
                "batch_size": 1,
                "epochs": 1,
                "beta": 0.0,
            },
            "output": {"save_steps": 50, "report_to": "none"},
        }

    def test_default_advantage_estimator_is_rloo(self, base_config):
        """Default should be rloo (SkyRL 0.3.1 compatible)."""
        result = _build_skyrl_config("/model", "/out", base_config, "/data.jsonl")
        algo = result["trainer"]["algorithm"]
        assert algo["advantage_estimator"] == "rloo"

    def test_explicit_rloo_n_from_config(self, base_config):
        """Explicit rloo_n in config should pass through."""
        base_config["online_rl"]["advantage_estimator"] = "rloo_n"
        result = _build_skyrl_config("/model", "/out", base_config, "/data.jsonl")
        algo = result["trainer"]["algorithm"]
        assert algo["advantage_estimator"] == "rloo_n"

    def test_explicit_grpo_from_config(self, base_config):
        """Explicit online RL in config should override default."""
        base_config["online_rl"]["advantage_estimator"] = "online_rl"
        result = _build_skyrl_config("/model", "/out", base_config, "/data.jsonl")
        algo = result["trainer"]["algorithm"]
        assert algo["advantage_estimator"] == "online_rl"

    def test_n_samples_per_prompt_defaults_to_8(self, base_config):
        """OpenThoughts uses 8 samples per prompt (vs old default of 4)."""
        result = _build_skyrl_config("/model", "/out", base_config, "/data.jsonl")
        assert result["generator"]["n_samples_per_prompt"] == 8

    def test_kl_disabled_when_beta_zero(self, base_config):
        """KL loss should be disabled when beta=0.0."""
        base_config["online_rl"]["beta"] = 0.0
        result = _build_skyrl_config("/model", "/out", base_config, "/data.jsonl")
        algo = result["trainer"]["algorithm"]
        assert algo["use_kl_loss"] is False
        assert algo["kl_loss_coef"] == 0.0

    def test_kl_enabled_when_beta_positive(self, base_config):
        """KL loss should be enabled when beta > 0."""
        base_config["online_rl"]["beta"] = 0.001
        result = _build_skyrl_config("/model", "/out", base_config, "/data.jsonl")
        algo = result["trainer"]["algorithm"]
        assert algo["use_kl_loss"] is True
        assert algo["kl_loss_coef"] == 0.001

    def test_loss_reduction_is_token_mean(self, base_config):
        """Loss reduction should be token_mean (not sequence_mean)."""
        result = _build_skyrl_config("/model", "/out", base_config, "/data.jsonl")
        algo = result["trainer"]["algorithm"]
        assert algo["loss_reduction"] == "token_mean"

    def test_ref_model_defaults_to_policy_model(self, base_config):
        """Reference model should default to the policy model path."""
        result = _build_skyrl_config("/model", "/out", base_config, "/data.jsonl")
        assert result["trainer"]["ref"]["model"]["path"] == "/model"

    def test_ref_model_override(self, base_config):
        """ref_model_path should override the reference model."""
        base_config["ref_model_path"] = "/ref_model"
        result = _build_skyrl_config("/model", "/out", base_config, "/data.jsonl")
        assert result["trainer"]["ref"]["model"]["path"] == "/ref_model"
