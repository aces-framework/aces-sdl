"""Agent protocol — minimal interface for pluggable agents.

SkyRL owns generation during Online RL training. This protocol is for:
  - Evaluation (trajgym-eval)
  - GEPA trace collection
  - Standalone agent runs (trajgym-agent)

Any class implementing solve() satisfies Agent via structural subtyping.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# StepAgent — pluggable tool-execution agent for Online RL training loop
# ---------------------------------------------------------------------------


@dataclass
class StepResult:
    """Result of a single agent step (tool parsing + execution).

    The env owns reward computation (SkyRL contract). The agent returns
    observations and done status only.
    """

    observations: list[
        dict[str, str]
    ]  # [{role: "user", content: "[Tool: name]\noutput"}]
    done: bool
    info: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class StepAgent(Protocol):
    """Pluggable agent for the Online RL training loop.

    During Online RL training, SkyRL owns generation (vLLM). The StepAgent
    owns tool parsing + execution. This lets users swap in custom tool
    handlers, different parsing logic, or entirely different execution
    backends without touching the env or reward code.

    WARNING — Reward-critical attributes:
        The env (``trajgym_env.py``) reads the following 5 attributes via
        ``getattr(agent, attr, default)`` to feed into Reward scoring.
        If your agent does not expose them, 7 of 8 reward signals will
        silently degrade to zero. Use ``validate_step_agent(agent)`` after
        construction to check for missing attributes.

        - ``tool_calls_history`` (List[Dict[str, str]]): List of
          ``{"name": ..., "arguments": ...}`` dicts. Default: ``[]``.
          Used by: format, efficiency, exploration, uniqueness, recovery.
        - ``tool_outputs`` (List[str]): Raw tool output strings.
          Default: ``[]``.
          Used by: progression, cognitive, flag detection.
        - ``all_text`` (str): Concatenated LLM + tool output text.
          Default: ``""``.
          Used by: cognitive (words-per-action), hallucination detection.
        - ``episode_done`` (bool): Whether flag was successfully submitted.
          Default: ``False``.
          Used by: flag signal (exact match gating).
        - ``turns`` (int): Number of steps taken so far. Default: ``0``.
          Used by: efficiency signal.

    Example::

        class MyAgent:
            def reset(self, target="", ground_truth_flag="", max_steps=30, **kw):
                self.target = target
                # Initialize reward-visible attributes
                self.tool_calls_history = []
                self.tool_outputs = []
                self.all_text = ""
                self.episode_done = False
                self.turns = 0

            def step(self, action: str) -> StepResult:
                # Parse tool calls YOUR way
                # Execute tools YOUR way
                return StepResult(observations=[...], done=False)

            def close(self):
                pass

            @property
            def tools(self):
                # Return None to use defaults, or provide your own:
                return [{"type": "function", "function": {"name": "my_tool", ...}}]

        assert isinstance(MyAgent(), StepAgent)
    """

    def reset(
        self,
        target: str = "",
        ground_truth_flag: str = "",
        max_steps: int = 30,
        **kwargs: Any,
    ) -> None:
        """Reset agent state for a new episode."""
        ...

    def step(self, action: str) -> StepResult:
        """Parse tool calls from LLM output and execute them.

        Args:
            action: Raw LLM text output (may contain tool calls).

        Returns:
            StepResult with observations and done flag.
        """
        ...

    def close(self) -> None:
        """Release resources."""
        ...

    @property
    def tools(self) -> list[dict[str, Any]] | None:
        """Tool schemas for prompt injection (OpenAI function format).

        Return None to use the environment's default tool schemas.
        Return a list of tool dicts to override with your own tools.

        Each dict should follow OpenAI function calling format::

            {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
        """
        ...


# ---------------------------------------------------------------------------
# Agent — full protocol for eval/GEPA (owns generation too)
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Result of an agent solving a CTF challenge."""

    success: bool
    flag: str | None = None
    steps: int = 0
    messages: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Agent(Protocol):
    """Minimal protocol for pluggable CTF agents.

    Any class with a matching ``solve()`` signature satisfies this protocol.
    No base class inheritance required.

    Example::

        class MyAgent:
            def solve(self, challenge, target, ground_truth_flag="",
                      max_steps=30, timeout=300) -> AgentResult:
                # ... your logic ...
                return AgentResult(success=True, flag="FLAG{...}")

        assert isinstance(MyAgent(), Agent)
    """

    def solve(
        self,
        challenge: str,
        target: str,
        ground_truth_flag: str = "",
        max_steps: int = 30,
        timeout: int = 300,
    ) -> AgentResult:
        """Attempt to solve a CTF challenge.

        Args:
            challenge: Challenge identifier (e.g. "eval-me", "XBEN-003-24").
            target: Target URL or file path for the challenge.
            ground_truth_flag: Expected flag for validation (empty = unknown).
            max_steps: Maximum tool-use steps before giving up.
            timeout: Maximum wall-clock seconds.

        Returns:
            AgentResult with success status, captured flag, and metadata.
        """
        ...


# ---------------------------------------------------------------------------
# StepAgent validation helper
# ---------------------------------------------------------------------------

#: Attributes the env reads from StepAgent via getattr() for reward scoring.
_REWARD_CRITICAL_ATTRS = (
    "tool_calls_history",
    "tool_outputs",
    "all_text",
    "episode_done",
    "turns",
)


def validate_step_agent(agent: StepAgent) -> list[str]:
    """Check a StepAgent for reward-critical attributes. Returns list of warnings.

    Call this after constructing a BYO StepAgent to get immediate feedback
    about missing attributes that will silently degrade reward signals.
    """
    warnings = []
    for attr in _REWARD_CRITICAL_ATTRS:
        if not hasattr(agent, attr):
            warnings.append(f"Agent missing '{attr}' — reward signals will be degraded")
    return warnings


__all__ = [
    "AgentResult",
    "Agent",
    "StepAgent",
    "StepResult",
    "validate_step_agent",
]
