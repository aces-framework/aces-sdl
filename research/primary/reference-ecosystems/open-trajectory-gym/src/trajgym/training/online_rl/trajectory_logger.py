"""Structured trajectory logging for Online RL training post-run analysis.

Provides per-generation JSONL logging, step summaries, and a challenge
scoreboard so that after a training run you can:
  1. Replay what the model generated per step
  2. See which reward signals fired and how much each contributed
  3. Know which challenges the model is learning to solve vs struggling with

All data is written to ``{output_dir}/trajectories/`` as JSONL files.
The scoreboard is saved as ``{output_dir}/challenge_scoreboard.json``.

When ``tensorboard_dir`` is provided, additional scalars are written
alongside SkyRL's native training metrics (loss, KL, gradients).

No external dependencies beyond stdlib + json.  TensorBoard writing is
optional and gracefully degrades if ``tensorboard`` is not installed.
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TrajectoryLogger:
    """Saves per-generation Online RL data as structured JSONL.

    Thread-safe: multiple SkyRL env workers may call log_generation()
    concurrently from different threads.

    Usage::

        tl = TrajectoryLogger("/path/to/output")
        tl.log_generation(
            global_step=34,
            generation_idx=2,
            challenge_id="forensics_urgent",
            prompt_messages=[...],
            model_output="...",
            tool_calls=[{"name": "shell_command", "args": {...}, "output": "..."}],
            reward_total=0.36,
            reward_breakdown={"flag": 0.0, "format": 0.15, ...},
            flag_found=False,
            ground_truth_flag="FLAG{...}",
        )
        tl.log_step_summary(global_step=34, rewards=[0.36, 0.12, 0.0, 0.0])
        tl.save_scoreboard()
    """

    def __init__(
        self,
        output_dir: str,
        enabled: bool = True,
        tensorboard_dir: str | None = None,
    ) -> None:
        self._output_dir = output_dir
        self._enabled = enabled
        self._trajectories_dir = os.path.join(output_dir, "trajectories")
        self._lock = threading.Lock()
        # Challenge scoreboard: {challenge_id: {attempts, solves, rewards, ...}}
        self._scoreboard: dict[str, dict[str, Any]] = {}
        # Per-step aggregates built incrementally from log_generation().
        # This lets us emit step_summaries.jsonl and TensorBoard charts
        # without requiring a separate reducer pass.
        self._step_aggregates: dict[int, dict[str, Any]] = {}
        self._tb_writer = None

        if self._enabled:
            os.makedirs(self._trajectories_dir, exist_ok=True)
            logger.info("TrajectoryLogger initialized: %s", self._trajectories_dir)

        # Optional TensorBoard writer for training scalars.
        if tensorboard_dir:
            try:
                from torch.utils.tensorboard import SummaryWriter

                self._tb_writer = SummaryWriter(log_dir=tensorboard_dir)
                logger.info("TensorBoard metrics: %s", tensorboard_dir)
            except ImportError:
                logger.info("tensorboard not installed; scalars disabled")

    @property
    def enabled(self) -> bool:
        return self._enabled

    @staticmethod
    def _sanitize_tag(value: str) -> str:
        return (
            str(value)
            .strip()
            .replace(" ", "_")
            .replace("/", "_")
            .replace(":", "_")
            .replace(".", "_")
        )

    def _ensure_step_state_locked(self, step: int) -> dict[str, Any]:
        state = self._step_aggregates.get(step)
        if state is not None:
            return state
        state = {
            "total_generations": 0,
            "flag_found_count": 0,
            "reward_sum": 0.0,
            "reward_sq_sum": 0.0,
            "min_reward": None,
            "max_reward": None,
            "tool_calls_sum": 0.0,
            "response_length_sum": 0.0,
            "challenge_ids": set(),
            "signal_sums": {},
            "tool_usage": {},
            "status_counts": {},
            "timing_sums": {},
            "timing_counts": {},
            # Straggler detection: individual total_s values for median calc.
            "timing_total_values": [],
            "straggler_count": 0,
            # Loop detection: track consecutive repeated tool commands.
            "tool_command_runs": {},  # {gen_idx: max_consecutive_same}
        }
        self._step_aggregates[step] = state
        return state

    def _update_step_aggregate_locked(
        self,
        *,
        global_step: int,
        challenge_id: str | None,
        reward_total: float,
        reward_breakdown: dict[str, float] | None,
        flag_found: bool,
        num_tool_calls: int,
        response_length: int,
        tool_calls: list[dict[str, Any]] | None,
        rollout_status: str | None,
        timing: dict[str, Any] | None,
    ) -> dict[str, Any]:
        state = self._ensure_step_state_locked(global_step)

        state["total_generations"] += 1
        if flag_found:
            state["flag_found_count"] += 1

        reward_value = float(reward_total)
        state["reward_sum"] += reward_value
        state["reward_sq_sum"] += reward_value * reward_value
        if state["min_reward"] is None:
            state["min_reward"] = reward_value
            state["max_reward"] = reward_value
        else:
            state["min_reward"] = min(float(state["min_reward"]), reward_value)
            state["max_reward"] = max(float(state["max_reward"]), reward_value)

        state["tool_calls_sum"] += float(num_tool_calls)
        state["response_length_sum"] += float(response_length)
        if challenge_id:
            state["challenge_ids"].add(challenge_id)

        if isinstance(reward_breakdown, dict):
            for key, value in reward_breakdown.items():
                try:
                    v = float(value)
                except (TypeError, ValueError):
                    continue
                state["signal_sums"][key] = (
                    float(state["signal_sums"].get(key, 0.0)) + v
                )

        for tc in tool_calls or []:
            name = str(tc.get("name", "")).strip()
            if not name:
                continue
            state["tool_usage"][name] = int(state["tool_usage"].get(name, 0)) + 1

        status_value = str(rollout_status or "ok").strip() or "ok"
        state["status_counts"][status_value] = (
            int(state["status_counts"].get(status_value, 0)) + 1
        )

        if isinstance(timing, dict):
            for key, value in timing.items():
                try:
                    v = float(value)
                except (TypeError, ValueError):
                    continue
                state["timing_sums"][key] = (
                    float(state["timing_sums"].get(key, 0.0)) + v
                )
                state["timing_counts"][key] = (
                    int(state["timing_counts"].get(key, 0)) + 1
                )
            # Track individual total_s for straggler detection.
            try:
                total_s = float(timing.get("total_s", 0.0))
                if total_s > 0:
                    state["timing_total_values"].append(total_s)
                    self._check_straggler(state, total_s, global_step, challenge_id)
            except (TypeError, ValueError):
                pass

        # Loop detection: count max consecutive repeated tool calls.
        if tool_calls:
            max_run = self._max_consecutive_same_tool(tool_calls)
            if max_run >= 10:
                logger.warning(
                    "[step=%d] Loop detected: same tool repeated %d times "
                    "(challenge=%s)",
                    global_step,
                    max_run,
                    challenge_id,
                )

        return self._build_step_summary_locked(global_step, state)

    @staticmethod
    def _check_straggler(
        state: dict[str, Any],
        total_s: float,
        global_step: int,
        challenge_id: str | None,
    ) -> None:
        """Warn when a rollout exceeds 3x the running median for this step."""
        values = state["timing_total_values"]
        if len(values) < 3:
            return
        sorted_vals = sorted(values[:-1])  # median of previous values
        mid = len(sorted_vals) // 2
        if len(sorted_vals) % 2 == 0:
            median = (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
        else:
            median = sorted_vals[mid]
        if median > 0 and total_s > 3.0 * median:
            state["straggler_count"] += 1
            logger.warning(
                "[step=%d] Straggler rollout: %.1fs (median=%.1fs, %.1fx) "
                "challenge=%s",
                global_step,
                total_s,
                median,
                total_s / median,
                challenge_id,
            )

    @staticmethod
    def _max_consecutive_same_tool(
        tool_calls: list[dict[str, Any]],
    ) -> int:
        """Return the longest run of consecutive identical tool name+command."""
        if not tool_calls:
            return 0
        max_run = 1
        current_run = 1
        prev_key = ""
        for tc in tool_calls:
            if not isinstance(tc, dict):
                prev_key = ""
                current_run = 1
                continue
            name = str(tc.get("name", ""))
            args = tc.get("args", {})
            if isinstance(args, str):
                try:
                    parsed_args = json.loads(args)
                    args = parsed_args if isinstance(parsed_args, dict) else {}
                except Exception:
                    args = {}
            elif not isinstance(args, dict):
                args = {}
            # Fingerprint: tool name + first 80 chars of command/code arg.
            cmd = str(args.get("command", args.get("code", "")))[:80]
            key = f"{name}:{cmd}"
            if key == prev_key:
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 1
            prev_key = key
        return max_run

    def _build_step_summary_locked(
        self, global_step: int, state: dict[str, Any]
    ) -> dict[str, Any]:
        total = int(state["total_generations"])
        if total <= 0:
            total = 1
        avg_reward = float(state["reward_sum"]) / total
        min_reward = (
            float(state["min_reward"]) if state["min_reward"] is not None else 0.0
        )
        max_reward = (
            float(state["max_reward"]) if state["max_reward"] is not None else 0.0
        )
        if total > 1:
            variance = (
                float(state["reward_sq_sum"])
                - (float(state["reward_sum"]) ** 2) / total
            ) / (total - 1)
            reward_std = max(0.0, variance) ** 0.5
        else:
            reward_std = 0.0

        signal_avg = {
            key: float(value) / total
            for key, value in sorted(state["signal_sums"].items())
        }
        timing_avg = {}
        for key, value in sorted(state["timing_sums"].items()):
            count = int(state["timing_counts"].get(key, 0))
            if count > 0:
                timing_avg[key] = float(value) / count

        # Straggler stats.
        timing_values = state.get("timing_total_values", [])
        if timing_values:
            sorted_tv = sorted(timing_values)
            mid = len(sorted_tv) // 2
            timing_median = (
                (sorted_tv[mid - 1] + sorted_tv[mid]) / 2.0
                if len(sorted_tv) % 2 == 0 and len(sorted_tv) >= 2
                else sorted_tv[mid]
            )
            timing_max = sorted_tv[-1]
        else:
            timing_median = 0.0
            timing_max = 0.0

        summary = {
            "global_step": global_step,
            "total_generations": int(state["total_generations"]),
            "flag_found_count": int(state["flag_found_count"]),
            "flag_found_rate": (
                float(state["flag_found_count"]) / float(state["total_generations"])
                if state["total_generations"] > 0
                else 0.0
            ),
            "avg_reward": avg_reward,
            "min_reward": min_reward,
            "max_reward": max_reward,
            "reward_std": reward_std,
            "avg_tool_calls": float(state["tool_calls_sum"]) / total,
            "avg_response_length": float(state["response_length_sum"]) / total,
            "unique_challenges": len(state["challenge_ids"]),
            "signal_avg": signal_avg,
            "tool_usage": dict(sorted(state["tool_usage"].items())),
            "rollout_status_counts": dict(sorted(state["status_counts"].items())),
            "timing_avg": timing_avg,
            "timing_median_s": timing_median,
            "timing_max_s": timing_max,
            "straggler_count": int(state.get("straggler_count", 0)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return summary

    def _emit_step_summary_to_tensorboard(self, summary: dict[str, Any]) -> None:
        if self._tb_writer is None:
            return
        step = int(summary.get("global_step", 0))
        total = float(summary.get("total_generations", 0.0) or 0.0)

        self._tb_writer.add_scalar(
            "reward/avg", float(summary.get("avg_reward", 0.0)), step
        )
        self._tb_writer.add_scalar(
            "reward/min", float(summary.get("min_reward", 0.0)), step
        )
        self._tb_writer.add_scalar(
            "reward/max", float(summary.get("max_reward", 0.0)), step
        )
        self._tb_writer.add_scalar(
            "reward/std", float(summary.get("reward_std", 0.0)), step
        )
        self._tb_writer.add_scalar(
            "flag/found_rate", float(summary.get("flag_found_rate", 0.0)), step
        )
        self._tb_writer.add_scalar(
            "tools/avg_calls", float(summary.get("avg_tool_calls", 0.0)), step
        )
        self._tb_writer.add_scalar(
            "response/avg_length",
            float(summary.get("avg_response_length", 0.0)),
            step,
        )

        signal_avg = summary.get("signal_avg") or {}
        if isinstance(signal_avg, dict):
            for key, value in signal_avg.items():
                self._tb_writer.add_scalar(
                    f"signal/{self._sanitize_tag(str(key))}",
                    float(value),
                    step,
                )

        status_counts = summary.get("rollout_status_counts") or {}
        if isinstance(status_counts, dict) and total > 0:
            for key, value in status_counts.items():
                self._tb_writer.add_scalar(
                    f"rollout_status/{self._sanitize_tag(str(key))}_rate",
                    float(value) / total,
                    step,
                )

        tool_usage = summary.get("tool_usage") or {}
        if isinstance(tool_usage, dict) and total > 0:
            for key, value in tool_usage.items():
                self._tb_writer.add_scalar(
                    f"tool_usage/{self._sanitize_tag(str(key))}_per_generation",
                    float(value) / total,
                    step,
                )

        timing_avg = summary.get("timing_avg") or {}
        if isinstance(timing_avg, dict):
            for key, value in timing_avg.items():
                self._tb_writer.add_scalar(
                    f"latency/{self._sanitize_tag(str(key))}",
                    float(value),
                    step,
                )

        # Straggler observability: median, max, and count per step.
        if summary.get("timing_median_s", 0.0) > 0:
            self._tb_writer.add_scalar(
                "latency/median_s", float(summary["timing_median_s"]), step
            )
            self._tb_writer.add_scalar(
                "latency/max_s", float(summary.get("timing_max_s", 0.0)), step
            )
        straggler_count = int(summary.get("straggler_count", 0))
        if straggler_count > 0:
            self._tb_writer.add_scalar("latency/straggler_count", straggler_count, step)

    def log_generation(
        self,
        global_step: int,
        generation_idx: int = 0,
        challenge_id: str | None = None,
        category: str | None = None,
        difficulty: str | None = None,
        target: str | None = None,
        prompt_messages: list[dict[str, Any]] | None = None,
        model_output: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        reward_total: float = 0.0,
        reward_breakdown: dict[str, float] | None = None,
        flag_found: bool = False,
        flag_submitted: str | None = None,
        ground_truth_flag: str | None = None,
        response_length: int = 0,
        num_tool_calls: int = 0,
        **extra: Any,
    ) -> None:
        """Log a single generation (one rollout) to the step JSONL file.

        Args:
            global_step: Current training step number.
            generation_idx: Index within the step's generation batch.
            challenge_id: Challenge identifier.
            category: Challenge category (web, forensics, crypto, etc.).
            difficulty: Challenge difficulty level.
            target: Target URL.
            prompt_messages: Input prompt messages.
            model_output: Raw model output text.
            tool_calls: List of {name, args, output} dicts.
            reward_total: Total reward score.
            reward_breakdown: Per-signal reward breakdown.
            flag_found: Whether the flag was found.
            flag_submitted: Flag string that was submitted, if any.
            ground_truth_flag: Expected flag string.
            response_length: Length of model response in characters.
            num_tool_calls: Number of tool calls executed.
            **extra: Additional fields to include in the log entry.
        """
        if not self._enabled:
            return

        entry = {
            "global_step": global_step,
            "generation_idx": generation_idx,
            "challenge_id": challenge_id,
            "category": category,
            "difficulty": difficulty,
            "target": target,
            "prompt_messages": prompt_messages,
            "model_output": _truncate(model_output, max_len=50000),
            "tool_calls": tool_calls,
            "reward_total": reward_total,
            "reward_breakdown": reward_breakdown,
            "flag_found": flag_found,
            "flag_submitted": flag_submitted,
            "ground_truth_flag": ground_truth_flag,
            "response_length": response_length,
            "num_tool_calls": num_tool_calls,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            entry.update(extra)

        filepath = os.path.join(self._trajectories_dir, f"step_{global_step}.jsonl")
        line = json.dumps(entry, default=str, ensure_ascii=False) + "\n"

        with self._lock:
            with open(filepath, "a") as f:
                f.write(line)
            summary = self._update_step_aggregate_locked(
                global_step=global_step,
                challenge_id=challenge_id,
                reward_total=reward_total,
                reward_breakdown=reward_breakdown,
                flag_found=flag_found,
                num_tool_calls=num_tool_calls,
                response_length=response_length,
                tool_calls=tool_calls,
                rollout_status=entry.get("rollout_status"),
                timing=(
                    entry.get("timing")
                    if isinstance(entry.get("timing"), dict)
                    else None
                ),
            )
            summary_path = os.path.join(self._trajectories_dir, "step_summaries.jsonl")
            with open(summary_path, "a") as f:
                f.write(json.dumps(summary, default=str, ensure_ascii=False) + "\n")

        self._emit_step_summary_to_tensorboard(summary)

    def log_step_summary(
        self,
        global_step: int,
        rewards: list[float] | None = None,
        flag_found_count: int = 0,
        total_generations: int = 0,
        avg_tool_calls: float = 0.0,
        avg_response_length: float = 0.0,
        challenge_ids: list[str] | None = None,
        **extra: Any,
    ) -> None:
        """Log aggregate statistics for a training step.

        Written to ``{trajectories_dir}/step_summaries.jsonl``.
        """
        if not self._enabled:
            return

        rewards = rewards or []
        avg_reward = sum(rewards) / len(rewards) if rewards else 0.0
        min_reward = min(rewards) if rewards else 0.0
        max_reward = max(rewards) if rewards else 0.0
        reward_std = _std(rewards) if len(rewards) > 1 else 0.0

        summary = {
            "global_step": global_step,
            "total_generations": total_generations,
            "flag_found_count": flag_found_count,
            "flag_found_rate": (
                flag_found_count / total_generations if total_generations > 0 else 0.0
            ),
            "avg_reward": avg_reward,
            "min_reward": min_reward,
            "max_reward": max_reward,
            "reward_std": reward_std,
            "avg_tool_calls": avg_tool_calls,
            "avg_response_length": avg_response_length,
            "unique_challenges": (len(set(challenge_ids)) if challenge_ids else 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            summary.update(extra)

        filepath = os.path.join(self._trajectories_dir, "step_summaries.jsonl")
        line = json.dumps(summary, default=str, ensure_ascii=False) + "\n"

        with self._lock, open(filepath, "a") as f:
            f.write(line)

        self._emit_step_summary_to_tensorboard(summary)

    def log_challenge_result(
        self,
        challenge_id: str,
        category: str | None = None,
        difficulty: str | None = None,
        reward: float = 0.0,
        flag_found: bool = False,
    ) -> None:
        """Accumulate a result for the challenge scoreboard.

        Thread-safe. Call save_scoreboard() at training end to persist.
        """
        if not self._enabled or not challenge_id:
            return

        with self._lock:
            if challenge_id not in self._scoreboard:
                self._scoreboard[challenge_id] = {
                    "attempts": 0,
                    "solves": 0,
                    "rewards": [],
                    "category": category,
                    "difficulty": difficulty,
                }
            entry = self._scoreboard[challenge_id]
            entry["attempts"] += 1
            if flag_found:
                entry["solves"] += 1
            entry["rewards"].append(reward)
            # Update category/difficulty if not set
            if category and not entry.get("category"):
                entry["category"] = category
            if difficulty and not entry.get("difficulty"):
                entry["difficulty"] = difficulty

    def save_scoreboard(self) -> str | None:
        """Write the challenge scoreboard to JSON.

        Returns:
            Path to the scoreboard file, or None if disabled/empty.
        """
        if not self._enabled:
            return None

        with self._lock:
            if not self._scoreboard:
                rebuilt = self._rebuild_scoreboard_from_logs_locked()
                if rebuilt:
                    self._scoreboard = rebuilt
                else:
                    return None

            scoreboard = {}
            for cid, data in self._scoreboard.items():
                rewards = data["rewards"]
                scoreboard[cid] = {
                    "attempts": data["attempts"],
                    "solves": data["solves"],
                    "solve_rate": (
                        data["solves"] / data["attempts"]
                        if data["attempts"] > 0
                        else 0.0
                    ),
                    "avg_reward": (sum(rewards) / len(rewards) if rewards else 0.0),
                    "best_reward": max(rewards) if rewards else 0.0,
                    "worst_reward": min(rewards) if rewards else 0.0,
                    "category": data.get("category"),
                    "difficulty": data.get("difficulty"),
                }

        filepath = os.path.join(self._output_dir, "challenge_scoreboard.json")
        with open(filepath, "w") as f:
            json.dump(scoreboard, f, indent=2, default=str, ensure_ascii=False)

        logger.info(
            "Challenge scoreboard saved: %s (%d challenges)",
            filepath,
            len(scoreboard),
        )
        return filepath

    def _rebuild_scoreboard_from_logs_locked(self) -> dict[str, dict[str, Any]]:
        """Rebuild challenge scoreboard from persisted per-step JSONL logs."""
        rebuilt: dict[str, dict[str, Any]] = {}
        for step_file in sorted(Path(self._trajectories_dir).glob("step_*.jsonl")):
            try:
                with open(step_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        row = json.loads(line)
                        cid = row.get("challenge_id")
                        if not cid:
                            continue
                        entry = rebuilt.setdefault(
                            cid,
                            {
                                "attempts": 0,
                                "solves": 0,
                                "rewards": [],
                                "category": row.get("category"),
                                "difficulty": row.get("difficulty"),
                            },
                        )
                        entry["attempts"] += 1
                        if bool(row.get("flag_found", False)):
                            entry["solves"] += 1
                        try:
                            entry["rewards"].append(float(row.get("reward_total", 0.0)))
                        except (TypeError, ValueError):
                            entry["rewards"].append(0.0)
                        if not entry.get("category") and row.get("category"):
                            entry["category"] = row.get("category")
                        if not entry.get("difficulty") and row.get("difficulty"):
                            entry["difficulty"] = row.get("difficulty")
            except (OSError, json.JSONDecodeError):
                continue
        return rebuilt

    def get_scoreboard(self) -> dict[str, dict[str, Any]]:
        """Return a copy of the current scoreboard data."""
        with self._lock:
            result = {}
            for cid, data in self._scoreboard.items():
                rewards = data["rewards"]
                result[cid] = {
                    "attempts": data["attempts"],
                    "solves": data["solves"],
                    "solve_rate": (
                        data["solves"] / data["attempts"]
                        if data["attempts"] > 0
                        else 0.0
                    ),
                    "avg_reward": (sum(rewards) / len(rewards) if rewards else 0.0),
                    "best_reward": max(rewards) if rewards else 0.0,
                    "category": data.get("category"),
                    "difficulty": data.get("difficulty"),
                }
            return result

    def flush_scoreboard_to_tensorboard(self, global_step: int = 0) -> None:
        """Write per-challenge solve rates to TensorBoard as a bar chart."""
        if self._tb_writer is None:
            return
        with self._lock:
            for cid, data in self._scoreboard.items():
                attempts = data["attempts"]
                if attempts == 0:
                    continue
                solve_rate = data["solves"] / attempts
                avg_r = (
                    sum(data["rewards"]) / len(data["rewards"])
                    if data["rewards"]
                    else 0.0
                )
                safe_cid = cid.replace("/", "_").replace(" ", "_")
                self._tb_writer.add_scalar(
                    f"challenge/{safe_cid}/solve_rate", solve_rate, global_step
                )
                self._tb_writer.add_scalar(
                    f"challenge/{safe_cid}/avg_reward", avg_r, global_step
                )

    def close(self) -> None:
        """Flush and close TensorBoard writer if active."""
        if self._tb_writer is not None:
            self._tb_writer.flush()
            self._tb_writer.close()
            self._tb_writer = None


def _truncate(text: str | None, max_len: int = 50000) -> str | None:
    """Truncate text to max_len characters with an indicator."""
    if text is None or len(text) <= max_len:
        return text
    return text[:max_len] + f"... [truncated, {len(text)} total chars]"


def _std(values: list[float]) -> float:
    """Compute sample standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return variance**0.5
