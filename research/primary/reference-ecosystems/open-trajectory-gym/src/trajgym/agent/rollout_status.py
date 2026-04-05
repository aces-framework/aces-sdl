"""Canonical rollout status taxonomy for online RL trajectories."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)
_UNKNOWN_STATUS_WARNED: set[str] = set()


class RolloutStatus(str, Enum):
    """Canonical status values emitted by step agents and envs."""

    OK = "ok"
    NO_TOOL_CALL = "no_tool_call"
    PARSER_ERROR = "parser_error"
    EMPTY_ACTION_LOOP = "empty_action_loop"
    TOOL_ERROR = "tool_error"
    TOOL_TIMEOUT = "tool_timeout"
    INFRA_UNREACHABLE = "infra_unreachable"
    TARGET_MISMATCH = "target_mismatch"
    RUNTIME_TIMEOUT = "runtime_timeout"
    RUNTIME_ERROR = "runtime_error"
    MAX_TURN_ABORT = "max_turn_abort"
    NON_TERMINAL_CLOSE = "non_terminal_close"


def normalize_rollout_status(
    value: Any, default: RolloutStatus = RolloutStatus.RUNTIME_ERROR
) -> str:
    """Normalize arbitrary status input to a known rollout-status string."""
    if isinstance(value, RolloutStatus):
        return value.value
    text = str(value or "").strip().lower()
    if not text:
        return default.value
    for status in RolloutStatus:
        if text == status.value:
            return status.value
    if text and text not in _UNKNOWN_STATUS_WARNED:
        _UNKNOWN_STATUS_WARNED.add(text)
        logger.warning("Unknown rollout_status %r, coercing to %s", text, default.value)
    return default.value
