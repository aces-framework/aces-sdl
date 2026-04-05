"""Agent protocols and generic implementations.

BoxPwnr-specific adapters (boxpwnr_runner, boxpwnr_adapter) are NOT imported
here — they are optional integrations, lazy-imported by the CLI/eval code that
needs them.
"""

from .default_agent import DefaultStepAgent
from .protocol import Agent, AgentResult, StepAgent, StepResult, validate_step_agent
from .rollout_status import RolloutStatus, normalize_rollout_status

__all__ = [
    "Agent",
    "AgentResult",
    "DefaultStepAgent",
    "RolloutStatus",
    "StepAgent",
    "StepResult",
    "normalize_rollout_status",
    "validate_step_agent",
]
