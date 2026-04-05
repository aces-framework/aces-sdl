from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Type


@dataclass
class PRMJudgment:
    """Result of a PRM evaluation on a trajectory."""

    adjusted_reward: float
    is_thrashing: bool = False
    productive_turns: int = 0
    reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# Type alias for trajectory messages (OpenAI chat format)
Trajectory = List[Dict[str, str]]


class ProcessRewardModel(ABC):
    """Abstract base class for Process Reward Models.

    Two modes:
    - Mid-trial (should_terminate): Called each turn via terminus-2 callback.
      Returns True to kill thrashing agents early.
    - Post-hoc (judge): Called after trial completes to adjust reward.
    """

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Registry name for YAML config lookup."""
        ...

    @abstractmethod
    def should_terminate(
        self,
        turn: int,
        trajectory_steps: list,
        messages: list,
    ) -> bool:
        """Mid-trial check: should the agent be stopped early?

        Called by terminus-2's turn_callback after each turn.

        Args:
            turn: Current turn number (0-indexed).
            trajectory_steps: List of Step objects (terminus-2 internal).
            messages: Full chat message history.

        Returns:
            True to terminate the trial early.
        """
        ...

    def judge(
        self,
        trajectory: Trajectory,
        reward: float,
        metadata: Dict[str, Any],
    ) -> PRMJudgment:
        """Post-hoc: judge a completed trajectory and adjust reward.

        Optional — default returns reward unchanged.

        Args:
            trajectory: Full chat history (OpenAI message format).
            reward: Original verifier reward.
            metadata: Trial metadata.

        Returns:
            PRMJudgment with adjusted reward.
        """
        return PRMJudgment(adjusted_reward=reward)

    def get_hint(
        self,
        turn: int,
        trajectory_steps: list,
        messages: list,
    ) -> str | None:
        """Mid-trial hint generation: return a hint string or None.

        Optional — default returns None (no hint). Override in subclasses
        that provide constructive feedback instead of (or in addition to)
        early termination.

        Args:
            turn: Current turn number (0-indexed).
            trajectory_steps: List of Step objects (terminus-2 internal).
            messages: Full chat message history.

        Returns:
            A hint string to inject into the student's next prompt,
            or None to do nothing.
        """
        return None

    def as_turn_callback(self) -> Callable:
        """Return a callable suitable for terminus-2's turn_callback kwarg.

        The callback may return:
        - ``True`` to terminate the trial early.
        - A non-empty ``str`` to inject a hint into the student's next prompt.
        - ``False`` / ``None`` / empty string to continue normally.
        """
        return self.should_terminate


# --- Registry ---

_PRM_REGISTRY: Dict[str, Type[ProcessRewardModel]] = {}


def register_prm(cls: Type[ProcessRewardModel]) -> Type[ProcessRewardModel]:
    _PRM_REGISTRY[cls.name()] = cls
    return cls


def get_prm(name: str, **kwargs) -> ProcessRewardModel:
    if name not in _PRM_REGISTRY:
        available = ", ".join(_PRM_REGISTRY.keys())
        raise ValueError(f"Unknown PRM '{name}'. Available: {available}")
    return _PRM_REGISTRY[name](**kwargs)


def list_prms() -> List[str]:
    return list(_PRM_REGISTRY.keys())
