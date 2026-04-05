"""BoxPwnr adapter implementing the Agent protocol.

Wraps the existing AgentRunner to satisfy the Agent interface,
enabling BoxPwnr to be used interchangeably with other agents.
"""

import logging
import time
from typing import Any

from trajgym.agent.protocol import AgentResult

logger = logging.getLogger(__name__)


class BoxPwnrAgent:
    """Adapter wrapping BoxPwnr's AgentRunner to implement Agent protocol.

    Usage::

        agent = BoxPwnrAgent(model="ollama/nanbeige4.1-3b")
        result = agent.solve(challenge="eval-me", target="http://localhost:32805")
    """

    def __init__(
        self,
        model: str = "openrouter/openai/gpt-oss-120b",
        platform: str = "cybench",
        strategy: str = "chat_tools",
        traces_dir: str = "./targets",
        reasoning_effort: str = "medium",
        custom_instructions: str | None = None,
        **kwargs: Any,
    ):
        self.model = model
        self.platform = platform
        self.strategy = strategy
        self.traces_dir = traces_dir
        self.reasoning_effort = reasoning_effort
        self.custom_instructions = custom_instructions
        self._extra_kwargs = kwargs

    def solve(
        self,
        challenge: str,
        target: str,
        ground_truth_flag: str = "",
        max_steps: int = 30,
        timeout: int = 300,
        custom_instructions: str | None = None,
    ) -> AgentResult:
        """Solve a challenge using BoxPwnr's AgentRunner.

        Args:
            challenge: Challenge identifier (used as BoxPwnr target name).
            target: Target URL (currently informational — BoxPwnr resolves targets via platform).
            ground_truth_flag: Expected flag (for post-run validation).
            max_steps: Maximum conversation turns.
            timeout: Maximum time in seconds (converted to minutes for BoxPwnr).
            custom_instructions: Override instance custom_instructions for this solve.

        Returns:
            AgentResult with success/failure and metadata.
        """
        from .boxpwnr_runner import AgentRunner

        start = time.monotonic()
        max_time_min = max(1, timeout // 60)
        effective_instructions = custom_instructions if custom_instructions is not None else self.custom_instructions

        runner = AgentRunner(
            platform=self.platform,
            model=self.model,
            strategy=self.strategy,
            max_turns=max_steps,
            max_time=max_time_min,
            traces_dir=self.traces_dir,
            reasoning_effort=self.reasoning_effort,
            custom_instructions=effective_instructions,
            **self._extra_kwargs,
        )

        try:
            stats = runner.run(target=challenge) or {}
            elapsed = time.monotonic() - start
            if not isinstance(stats, dict):
                stats = {}
            status = str(stats.get("status", "")).strip().lower()
            success = status == "success"
            steps = int(stats.get("total_turns", 0) or 0)
            flag = (
                stats.get("flag")
                or stats.get("user_flag_value")
                or stats.get("root_flag_value")
            )
            return AgentResult(
                success=success,
                flag=str(flag) if flag else None,
                steps=steps,
                duration_seconds=elapsed,
                metadata={
                    "model": self.model,
                    "platform": self.platform,
                    "challenge": challenge,
                    "target": target,
                    "status": status or "unknown",
                },
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error("BoxPwnr solve failed for %s: %s", challenge, exc)
            return AgentResult(
                success=False,
                flag=None,
                steps=0,
                duration_seconds=elapsed,
                metadata={"error": str(exc), "challenge": challenge},
            )
