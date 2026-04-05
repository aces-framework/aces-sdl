"""Tests for rollout status normalization behavior."""

from __future__ import annotations

import logging

from trajgym.agent.rollout_status import RolloutStatus, normalize_rollout_status


def test_normalize_known_value():
    assert normalize_rollout_status("tool_timeout") == RolloutStatus.TOOL_TIMEOUT.value


def test_normalize_unknown_logs_once(caplog):
    caplog.set_level(logging.WARNING)

    out1 = normalize_rollout_status("my_custom_status")
    out2 = normalize_rollout_status("my_custom_status")

    assert out1 == RolloutStatus.RUNTIME_ERROR.value
    assert out2 == RolloutStatus.RUNTIME_ERROR.value

    warnings = [r for r in caplog.records if "Unknown rollout_status" in r.getMessage()]
    assert len(warnings) == 1
