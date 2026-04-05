"""Regression tests for DefaultStepAgent resilient mode control flow.

These tests validate the resilient_mode=True behavior that keeps rollouts
alive on missing/invalid tool calls.
"""

from __future__ import annotations

from trajgym.agent.default_agent import DefaultStepAgent


def test_resilient_agent_keeps_default_no_tool_threshold() -> None:
    """DefaultStepAgent should not silently override no-tool thresholds."""
    agent = DefaultStepAgent()
    assert agent.max_consecutive_no_tool_calls == 3
    assert agent.resilient_mode is True


def test_resilient_agent_recovers_non_fatal_no_tool_done() -> None:
    """No-tool terminal from base logic should be converted into a recoverable turn."""
    agent = DefaultStepAgent(max_consecutive_no_tool_calls=1)
    agent.reset(target="http://localhost:8080", max_steps=3)

    step1 = agent.step("thinking only")
    assert step1.done is False
    assert step1.info.get("rollout_status") == "no_tool_call"
    assert agent.turns == 1

    step2 = agent.step("still thinking")
    assert step2.done is False
    assert step2.info.get("rollout_status") == "no_tool_call"
    assert agent.turns == 2

    # On max_steps boundary, terminal behavior is preserved.
    step3 = agent.step("one more")
    assert step3.done is True
    assert agent.turns == 3


def test_resilient_mode_disabled_terminates_on_no_tool() -> None:
    """With resilient_mode=False, consecutive no-tool threshold terminates normally."""
    agent = DefaultStepAgent(max_consecutive_no_tool_calls=1, resilient_mode=False)
    agent.reset(target="http://localhost:8080", max_steps=10)

    step1 = agent.step("thinking only")
    assert step1.done is True
