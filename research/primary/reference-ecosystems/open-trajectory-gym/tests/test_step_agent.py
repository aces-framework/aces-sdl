"""Tests for StepAgent protocol and DefaultStepAgent.

Validates:
- DefaultStepAgent satisfies StepAgent protocol
- Custom classes satisfy StepAgent protocol
- DefaultStepAgent.step() handles: no tool call → nudge, tool call → output, flag → done
- TrajGymTextEnv delegates to custom agent when agent_class is specified
"""

from pathlib import Path

from trajgym.agent.default_agent import DefaultStepAgent
from trajgym.agent.protocol import StepAgent, StepResult

# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestStepAgentProtocol:
    def test_default_agent_satisfies_protocol(self):
        """DefaultStepAgent should satisfy StepAgent via structural subtyping."""
        agent = DefaultStepAgent()
        assert isinstance(agent, StepAgent)

    def test_custom_class_satisfies_protocol(self):
        """Any class with matching reset/step/close satisfies StepAgent."""

        class MyAgent:
            def reset(self, target="", ground_truth_flag="", max_steps=30, **kw):
                pass

            def step(self, action: str) -> StepResult:
                return StepResult(observations=[], done=False)

            def close(self):
                pass

            @property
            def tools(self):
                return None

        agent = MyAgent()
        assert isinstance(agent, StepAgent)

    def test_class_without_step_fails_protocol(self):
        """Class without step() should NOT satisfy StepAgent."""

        class NotAnAgent:
            def reset(self, **kw):
                pass

            def close(self):
                pass

        assert not isinstance(NotAnAgent(), StepAgent)


# ---------------------------------------------------------------------------
# StepResult
# ---------------------------------------------------------------------------


class TestStepResult:
    def test_defaults(self):
        result = StepResult(observations=[], done=False)
        assert result.observations == []
        assert result.done is False
        assert result.info == {}

    def test_with_observations(self):
        obs = [{"role": "user", "content": "[Tool: shell_command]\noutput"}]
        result = StepResult(observations=obs, done=False, info={"step": 1})
        assert len(result.observations) == 1
        assert result.info["step"] == 1


# ---------------------------------------------------------------------------
# DefaultStepAgent behavior
# ---------------------------------------------------------------------------


class TestDefaultStepAgent:
    def test_no_tool_call_returns_nudge(self):
        """When LLM output has no tool calls, agent returns a nudge message."""
        agent = DefaultStepAgent()
        agent.reset(target="http://localhost:8080", max_steps=30)

        result = agent.step("I'm thinking about how to approach this...")
        assert not result.done
        assert len(result.observations) == 1
        assert "No tool call detected" in result.observations[0]["content"]
        assert agent.turns == 1

    def test_no_tool_call_at_max_steps_is_done(self):
        """When no tool call at max steps, agent returns done=True."""
        agent = DefaultStepAgent()
        agent.reset(target="http://localhost:8080", max_steps=1)

        result = agent.step("Just thinking...")
        assert result.done
        assert result.observations == []

    def test_reset_clears_state(self):
        """Reset should clear all episode state."""
        agent = DefaultStepAgent()
        agent.reset(target="http://localhost:8080", max_steps=30)

        # Take a step
        agent.step("Some text")
        assert agent.turns == 1

        # Reset
        agent.reset(target="http://localhost:9090", max_steps=10)
        assert agent.turns == 0
        assert agent.tool_calls_history == []
        assert agent.tool_outputs == []
        assert agent.all_text == ""
        assert not agent.episode_done
        assert agent.max_steps == 10

    def test_shell_tool_call_executes(self):
        """A shell_command tool call should execute and return output."""
        agent = DefaultStepAgent()
        agent.reset(target="http://localhost:8080", max_steps=30)

        action = '<tool_call>\n{"name": "shell_command", "arguments": {"command": "echo hello_world"}}\n</tool_call>'
        result = agent.step(action)

        assert not result.done
        assert len(result.observations) == 1
        assert "hello_world" in result.observations[0]["content"]
        assert result.observations[0]["role"] == "user"
        assert len(agent.tool_calls_history) == 1
        assert agent.tool_calls_history[0]["name"] == "shell_command"

    def test_close_releases_executor(self):
        """Close should release the executor."""
        agent = DefaultStepAgent()
        agent.reset(target="http://localhost:8080", max_steps=30)
        agent.close()
        assert agent._executor is None

    def test_root_challenge_paths_are_rewritten_to_active_workdir(self, tmp_path):
        """Commands hardcoding /root/challenge should run in per-episode workspace."""
        (tmp_path / "artifact.txt").write_text("ok\n", encoding="utf-8")
        agent = DefaultStepAgent()
        agent.reset(
            target=f"file://{tmp_path}/",
            max_steps=10,
            challenge_workdir=str(tmp_path),
        )

        action = (
            '<tool_call>{"name":"shell_command","arguments":'
            '{"command":"ls -1 /root/challenge"}}</tool_call>'
        )
        result = agent.step(action)
        assert not result.done
        assert "artifact.txt" in result.observations[0]["content"]
        assert str(tmp_path) in agent.tool_calls_history[0]["arguments"]

    def test_command_xml_parse_hint_uses_command_xml_format(self):
        """Parser recovery hint must match command_xml profile (no JSON tool_call)."""
        agent = DefaultStepAgent(tool_call_format="command_xml")
        agent.reset(target="http://localhost:8080", max_steps=10)

        result = agent.step("<COMMAND maxtime=30>enumerate target</COMMANDX>")
        assert not result.done
        assert len(result.observations) == 1
        hint = result.observations[0]["content"]
        assert "<COMMAND" in hint
        assert "<tool_call>" not in hint

    def test_fallback_shell_recovery_accepts_explicit_function_form(self):
        """Fallback shell recovery should work for explicit function-style emission."""
        agent = DefaultStepAgent()
        agent.reset(target="http://localhost:8080", max_steps=10)
        result = agent.step('shell_command(command="echo fallback_ok")')
        assert not result.done
        assert len(result.observations) == 1
        assert "fallback_ok" in result.observations[0]["content"]

    def test_fallback_shell_recovery_rejects_plain_prose(self):
        """Fallback shell recovery should not execute commands extracted from prose."""
        agent = DefaultStepAgent()
        agent.reset(target="http://localhost:8080", max_steps=10)
        result = agent.step(
            "I should maybe run curl -s http://localhost:8080, then continue."
        )
        assert not result.done
        assert len(result.observations) == 1
        assert "No tool call detected" in result.observations[0]["content"]

    def test_ground_truth_in_tool_output_does_not_mark_episode_done(self):
        """Only explicit tool completion should end the episode."""
        agent = DefaultStepAgent()
        agent.reset(
            target="http://localhost:8080",
            max_steps=10,
            ground_truth_flag="FLAG{do_not_autocomplete}",
        )
        action = (
            '<tool_call>{"name":"shell_command","arguments":'
            '{"command":"echo FLAG{do_not_autocomplete}"}}</tool_call>'
        )
        result = agent.step(action)
        assert not result.done
        assert agent.episode_done is False


# ---------------------------------------------------------------------------
# TrajGymTextEnv delegation
# ---------------------------------------------------------------------------


class TestEnvDelegation:
    def test_env_uses_default_agent(self):
        """TrajGymTextEnv should use DefaultStepAgent by default."""
        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        env = TrajGymTextEnv(extras={"target": "http://localhost:8080"})
        assert isinstance(env._agent, DefaultStepAgent)

    def test_env_delegates_step_to_agent(self):
        """TrajGymTextEnv.step() should delegate to the agent."""
        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        env = TrajGymTextEnv(
            extras={"target": "http://localhost:8080", "max_turns": 30},
        )
        # init() resets the agent
        prompt = [{"role": "user", "content": "Solve the challenge"}]
        env.init(prompt)

        # Step with no tool call
        result = env.step("Just thinking...")
        assert result["done"] is False
        assert len(result["observations"]) == 1
        assert "No tool call detected" in result["observations"][0]["content"]

    def test_env_accepts_custom_agent_class(self):
        """TrajGymTextEnv should accept agent_class kwarg."""
        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        class MockAgent:
            def __init__(self, **kwargs):
                self.reset_called = False
                self.step_called = False
                self.tool_calls_history = []
                self.tool_outputs = []
                self.all_text = ""
                self.episode_done = False

            def reset(self, target="", ground_truth_flag="", max_steps=30, **kw):
                self.reset_called = True

            def step(self, action: str) -> StepResult:
                self.step_called = True
                return StepResult(
                    observations=[{"role": "user", "content": "custom output"}],
                    done=False,
                    info={"custom": True},
                )

            def close(self):
                pass

        # Pass class directly (not as dotpath string, for testing)
        env = TrajGymTextEnv(
            extras={"target": "http://localhost:8080"},
        )
        # Replace agent manually (simulates what _resolve_class would do)
        env._agent = MockAgent()

        prompt = [{"role": "user", "content": "test"}]
        env.init(prompt)
        assert env._agent.reset_called

        result = env.step("some action")
        assert env._agent.step_called
        assert result["observations"][0]["content"] == "custom output"
        assert result["metadata"]["custom"] is True

    def test_env_shell_tool_end_to_end(self):
        """Full end-to-end: env → agent → executor → shell → result."""
        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        env = TrajGymTextEnv(
            extras={"target": "http://localhost:8080", "max_turns": 30},
        )
        prompt = [{"role": "user", "content": "Solve it"}]
        env.init(prompt)

        action = '<tool_call>\n{"name": "shell_command", "arguments": {"command": "echo test123"}}\n</tool_call>'
        result = env.step(action)

        assert result["done"] is False
        assert len(result["observations"]) == 1
        assert "test123" in result["observations"][0]["content"]

    def test_env_passes_tool_call_format_into_agent(self):
        """Env/agent parser hints should align with env tool_call_format."""
        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        env = TrajGymTextEnv(
            extras={
                "target": "http://localhost:8080",
                "tool_call_format": "command_xml",
            },
        )
        assert getattr(env._agent, "_tool_call_format", "") == "command_xml"

    def test_static_env_uses_isolated_workspace_and_rewrites_prompt(self, tmp_path):
        """Static episodes should stage files in a unique workspace per env."""
        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        source = tmp_path / "registry" / "sample_static"
        payload = source / "release"
        payload.mkdir(parents=True)
        (payload / "readme.txt").write_text("hello\n", encoding="utf-8")

        env = TrajGymTextEnv(
            extras={
                "infra_type": "static",
                "challenge_id": "sample-static",
                "path_hint": str(source),
                "ground_truth_flag": "FLAG{test}",
                "max_turns": 5,
            }
        )
        prompt = [
            {
                "role": "user",
                "content": "Inspect /root/challenge/ and file:///root/challenge/.",
            }
        ]
        workspace = ""
        try:
            prompt_out, _ = env.init(prompt)
            workspace = env._challenge_workdir
            assert workspace != "/root/challenge"
            assert env._target.startswith("file://")
            assert Path(workspace, "readme.txt").exists()
            assert "/root/challenge" not in str(prompt_out[0]["content"])
        finally:
            workspace = workspace or env._challenge_workdir
            env.close()

        assert workspace
        assert not Path(workspace).exists()
