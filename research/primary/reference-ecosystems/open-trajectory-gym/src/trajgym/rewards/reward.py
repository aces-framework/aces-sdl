"""CTF reward function for online RL training.

Physics-inspired scoring (8 configurable signals, sum to 1.0 + penalty):

  Primary (default weights):
  - Flag capture (0.85): Boundary condition -- did the trajectory reach the goal?
  - Efficiency (0.10): Least action -- step_ratio × action_novelty × temporal_decay.
  - Format compliance (0.05): Signal fidelity -- valid instrument readings only.

  Available but zeroed by default (reintroduce when >10% flag capture on hard challenges):
  - Recovery (0.0): Resilience -- trajectory pivots after stuck runs.
  - Progression (0.0): Phase space ordering -- RECON->ENUM->EXPLOIT trajectory.
  - Cognitive (0.0): Words-per-action -- optimal reasoning density (~42 WPA).
  - Exploration (0.0): Exponentially-decayed novelty -- early diversity > late.
  - Uniqueness (0.0): Information entropy -- repeated observations carry zero bits.
  - Hallucination penalty (0.0): Energy loss -- false claims decay trajectory progress.

Design principles:
  - **Principle of least action**: Efficiency score = step_ratio × novelty × time_decay.
    step_ratio = min(optimal/actual, 1.0) penalizes long trajectories.
    novelty = unique_actions/total_actions penalizes redundant commands.
    time_decay = exp(-λ × excess_steps) exponentially discounts late progress.
    Combined: the optimal trajectory reaches the flag via the shortest non-redundant path.
  - **Flag-dominant for RLOO**: Multi-signal reward compresses RLOO advantages
    → zero gradient. Flag at 0.85 maintains a solve/fail gap of ~0.90.
    Process signals (0.15 total) create within-group variance without compressing
    between-group gap.
  - **Temporal discounting on efficiency**: Earlier discoveries are exponentially
    more valuable (λ=0.3). A model that identifies the vulnerability at step 3 is
    better than one that finds it at step 15.
  - **Information specificity**: Only known CTF instruments carry signal.
    Set-based lookup, no regex.
  - **Online**: environment verification ("Correct! Flag verified") is authoritative.

Design rationale:
  - Flag-only (binary 1.0/0.0) crashes on all-solve batches (zero variance).
  - Too many process signals compress the RLOO solve/fail gap → zero gradient.
  - flag=0.85 + efficiency=0.10 + format=0.05 balances: ~0.90 RLOO gap,
    within-group variance from efficiency's 3 components prevents zero-variance crash.

"""

import collections
import json
import random
import threading
from typing import Any

from trajgym.rewards.constants import (
    _FLAG_PLACEHOLDERS,
    _KNOWN_TOOL_NAMES,
    _SHELL_WRAPPERS,
)
from trajgym.rewards.signals import (
    action_fingerprint,
    classify_phase,
    cognitive_score,
    efficiency_score,
    exploration_score,
    extract_command,
    flag_score,
    format_score,
    hallucination_score,
    is_known_tool,
    is_real_flag,
    progression_score,
    recovery_score,
    uniqueness_score,
)


class Reward:
    """CTF reward for online RL training.

    Compatible with both SkyRL (via TrajGymTextEnv) and TRL-style trainers.

    The ``__call__`` signature matches the standard expectation:
        reward_fn(completions, prompts=None, **kwargs) -> list[float]

    Extra metadata (``ground_truth_flag``, ``optimal_steps``) is forwarded
    via ``**kwargs`` by the trainer when the dataset contains those columns.
    """

    # Trainers may access reward_func.__name__ for logging.
    __name__ = "reward_score"

    # GDPO (Group-Decoupled Policy Optimization) buffer
    _gdpo_stats: dict[str, collections.deque] = {
        "flag": collections.deque(maxlen=256),
        "efficiency": collections.deque(maxlen=256),
        "progression": collections.deque(maxlen=256),
        "exploration": collections.deque(maxlen=256),
        "uniqueness": collections.deque(maxlen=256),
        "format": collections.deque(maxlen=256),
        "recovery": collections.deque(maxlen=256),
        "cognitive": collections.deque(maxlen=256),
        "hallucination": collections.deque(maxlen=256),
    }
    _gdpo_lock = threading.Lock()

    def __init__(
        self,
        flag_weight: float = 0.40,
        efficiency_weight: float = 0.15,
        progression_weight: float = 0.08,
        exploration_weight: float = 0.05,
        uniqueness_weight: float = 0.05,
        format_weight: float = 0.10,
        recovery_weight: float = 0.09,
        cognitive_weight: float = 0.08,
        hallucination_penalty: float = 0.20,
        noise_range: float = 0.01,
        exploration_gamma: float = 0.95,
        seed: int | None = None,
        use_gdpo: bool = False,
    ) -> None:
        """Initialize reward configuration.

        The 8 primary weights must sum to 1.0.
        """
        total = (
            flag_weight
            + efficiency_weight
            + progression_weight
            + exploration_weight
            + uniqueness_weight
            + format_weight
            + recovery_weight
            + cognitive_weight
        )
        if abs(total - 1.0) > 1e-6:
            if total > 0:
                import logging

                _log = logging.getLogger(__name__)
                _log.warning(
                    "Reward weights sum to %.4f, auto-normalizing to 1.0 "
                    "(flag=%.3f eff=%.3f prog=%.3f expl=%.3f uniq=%.3f "
                    "fmt=%.3f rec=%.3f cog=%.3f)",
                    total,
                    flag_weight,
                    efficiency_weight,
                    progression_weight,
                    exploration_weight,
                    uniqueness_weight,
                    format_weight,
                    recovery_weight,
                    cognitive_weight,
                )
                scale = 1.0 / total
                flag_weight *= scale
                efficiency_weight *= scale
                progression_weight *= scale
                exploration_weight *= scale
                uniqueness_weight *= scale
                format_weight *= scale
                recovery_weight *= scale
                cognitive_weight *= scale
            else:
                raise ValueError(f"Reward weights must sum to 1.0, got {total:.4f}")
        self.flag_weight = flag_weight
        self.efficiency_weight = efficiency_weight
        self.progression_weight = progression_weight
        self.exploration_weight = exploration_weight
        self.uniqueness_weight = uniqueness_weight
        self.format_weight = format_weight
        self.recovery_weight = recovery_weight
        self.cognitive_weight = cognitive_weight
        self.hallucination_penalty = hallucination_penalty
        self.noise_range = noise_range
        self.exploration_gamma = exploration_gamma
        self.use_gdpo = use_gdpo
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def __call__(
        self,
        completions: list[Any],
        prompts: list[Any] | None = None,
        **kwargs: Any,
    ) -> list[float]:
        """Score a batch of completions.

        Args:
            completions: List of completions. Each element is either a raw
                string or a list of message dicts (ChatML).
            prompts: (unused) kept for TRL compatibility.
            **kwargs: May contain ``ground_truth_flag``, ``optimal_steps``,
                and ``metadata`` lists forwarded from dataset columns.

        Returns:
            List of float reward values, one per completion.
        """
        n = len(completions)
        ground_truth_flags: list[str | None] = kwargs.get(
            "ground_truth_flag", [None] * n
        )
        optimal_steps_list: list[int | None] = kwargs.get("optimal_steps", [None] * n)
        metadata_list: list[dict[str, Any] | None] = kwargs.get("metadata", [None] * n)

        rewards: list[float] = []
        for idx, completion in enumerate(completions):
            gt_flag = ground_truth_flags[idx] if idx < len(ground_truth_flags) else None
            opt_steps = (
                optimal_steps_list[idx] if idx < len(optimal_steps_list) else None
            )
            meta = metadata_list[idx] if idx < len(metadata_list) else None

            score, _ = self._score_one(completion, gt_flag, opt_steps, meta)
            rewards.append(score)

        return rewards

    def compute_with_breakdown(
        self,
        completions: list[Any],
        prompts: list[Any] | None = None,
        **kwargs: Any,
    ) -> list[tuple[float, dict[str, float]]]:
        """Score a batch of completions, returning per-signal breakdowns.

        Same interface as ``__call__`` but returns a list of
        ``(total_reward, breakdown_dict)`` tuples. The breakdown dict
        contains the raw (pre-noise) weighted contribution of each signal.

        This method does NOT modify the existing ``__call__`` contract.
        """
        n = len(completions)
        ground_truth_flags: list[str | None] = kwargs.get(
            "ground_truth_flag", [None] * n
        )
        optimal_steps_list: list[int | None] = kwargs.get("optimal_steps", [None] * n)
        metadata_list: list[dict[str, Any] | None] = kwargs.get("metadata", [None] * n)

        results: list[tuple[float, dict[str, float]]] = []
        for idx, completion in enumerate(completions):
            gt_flag = ground_truth_flags[idx] if idx < len(ground_truth_flags) else None
            opt_steps = (
                optimal_steps_list[idx] if idx < len(optimal_steps_list) else None
            )
            meta = metadata_list[idx] if idx < len(metadata_list) else None

            score, breakdown = self._score_one(completion, gt_flag, opt_steps, meta)
            results.append((score, breakdown))

        return results

    def _score_one(
        self,
        completion: Any,
        gt_flag: str | None,
        opt_steps: int | None,
        meta: dict[str, Any] | None,
    ) -> tuple[float, dict[str, float]]:
        """Score a single completion. Returns (total_score, breakdown_dict).

        The breakdown dict contains raw signal values (before weighting)
        keyed by signal name, plus the weighted contributions.
        """
        text, tool_calls = self._extract(completion)

        task_category = (
            meta.get("task_category", "web") if isinstance(meta, dict) else "web"
        )

        flag_sc = self._flag_score(text, gt_flag, tool_calls=tool_calls)

        # Compute process signals (all ungated for dual-mode support).
        eff_sc = self._efficiency_score(
            len(tool_calls),
            opt_steps,
            flag_found=(flag_sc >= 1.0),
            tool_calls=tool_calls,
        )
        prog_sc = self._progression_score(tool_calls)
        expl_sc = self._exploration_score(tool_calls)
        uniq_sc = self._uniqueness_score(tool_calls)
        fmt_sc = self._format_score(tool_calls)
        hall_sc = self._hallucination_score(tool_calls, flag_sc, gt_flag)
        recov_sc = self._recovery_score(tool_calls)
        cog_sc = self._cognitive_score(text, tool_calls)

        # Minimum work gate: prevent reward hacking via very short episodes.
        # If fewer than 3 tool calls, cap easily-gamed process signals.
        if len(tool_calls) < 3:
            _SHORT_CAP = 0.3
            fmt_sc = min(fmt_sc, _SHORT_CAP)
            uniq_sc = min(uniq_sc, _SHORT_CAP)
            recov_sc = min(recov_sc, _SHORT_CAP)

        # Entropy-scaled format: modulate format by information density.
        # Low uniqueness = low entropy = less format credit.
        info_density = max(uniq_sc, 0.5) if tool_calls else 0.0
        fmt_effective = fmt_sc * info_density

        # Hallucination as energy loss: wrong flag submission decays
        # process signals to 30% (full zeroing made flag_found
        # EV-negative for small models, discouraging all flag attempts).
        if hall_sc < 0:
            _HALL_DECAY = 0.3
            fmt_effective *= _HALL_DECAY
            expl_sc *= _HALL_DECAY
            prog_sc *= _HALL_DECAY
            recov_sc *= _HALL_DECAY
            cog_sc *= _HALL_DECAY
            eff_sc *= _HALL_DECAY
            uniq_sc *= _HALL_DECAY

        raw_signals = {
            "flag": flag_sc,
            "efficiency": eff_sc,
            "progression": prog_sc,
            "exploration": expl_sc,
            "uniqueness": uniq_sc,
            "format": fmt_effective,
            "recovery": recov_sc,
            "cognitive": cog_sc,
            "hallucination": hall_sc,
        }

        if self.use_gdpo:
            with self._gdpo_lock:
                normalized_signals = {}
                for k, v in raw_signals.items():
                    self._gdpo_stats[k].append(v)
                    history = list(self._gdpo_stats[k])
                    if len(history) > 1:
                        mean_val = sum(history) / len(history)
                        variance = sum((x - mean_val) ** 2 for x in history) / len(
                            history
                        )
                        std_val = (variance**0.5) + 1e-4
                        normalized_signals[k] = (v - mean_val) / std_val
                    else:
                        normalized_signals[k] = v - 0.5  # Rough center if no history
        else:
            normalized_signals = raw_signals

        # Dynamic weight redistribution:
        # Non-web challenges don't follow RECON->ENUM->EXPLOIT.
        current_prog_weight = self.progression_weight
        current_cog_weight = self.cognitive_weight
        current_eff_weight = self.efficiency_weight

        if str(task_category).lower() in (
            "crypto",
            "rev",
            "reverse",
            "forensics",
            "pwn",
        ):
            # Disable strict progression and redistribute its weight
            redistribute = current_prog_weight
            current_prog_weight = 0.0
            current_cog_weight += redistribute * 0.5
            current_eff_weight += redistribute * 0.5

        score = (
            self.flag_weight * normalized_signals["flag"]
            + current_eff_weight * normalized_signals["efficiency"]
            + current_prog_weight * normalized_signals["progression"]
            + self.exploration_weight * normalized_signals["exploration"]
            + self.uniqueness_weight * normalized_signals["uniqueness"]
            + self.format_weight * normalized_signals["format"]
            + self.recovery_weight * normalized_signals["recovery"]
            + current_cog_weight * normalized_signals["cognitive"]
            + normalized_signals["hallucination"]
        )

        # Guarantee variance for Online RL
        noise = self._rng.uniform(-self.noise_range, self.noise_range)
        score += noise

        # Build breakdown: raw signal values + their weighted contributions
        breakdown = {
            "flag": raw_signals["flag"],
            "efficiency": raw_signals["efficiency"],
            "progression": raw_signals["progression"],
            "exploration": raw_signals["exploration"],
            "uniqueness": raw_signals["uniqueness"],
            "format": raw_signals["format"],
            "recovery": raw_signals["recovery"],
            "cognitive": raw_signals["cognitive"],
            "hallucination": raw_signals["hallucination"],
            # Weighted contributions (what each signal added to the total)
            "flag_weighted": self.flag_weight * normalized_signals["flag"],
            "efficiency_weighted": current_eff_weight
            * normalized_signals["efficiency"],
            "progression_weighted": current_prog_weight
            * normalized_signals["progression"],
            "exploration_weighted": self.exploration_weight
            * normalized_signals["exploration"],
            "uniqueness_weighted": self.uniqueness_weight
            * normalized_signals["uniqueness"],
            "format_weighted": self.format_weight * normalized_signals["format"],
            "recovery_weighted": self.recovery_weight * normalized_signals["recovery"],
            "cognitive_weighted": current_cog_weight * normalized_signals["cognitive"],
            "hallucination_weighted": normalized_signals["hallucination"],
            "noise": noise,
        }

        return score, breakdown

    # ------------------------------------------------------------------
    # Component scorers
    # ------------------------------------------------------------------

    # Verification strings emitted by ToolExecutor flag_found handler.
    _FLAG_VERIFIED = "Correct! Flag verified"
    _FLAG_REJECTED = "Incorrect submission"

    # Delegate signal scoring to module-level functions in signals.py.
    # Methods kept as thin wrappers for backward compatibility with code
    # that calls ``reward._flag_score(...)`` etc.

    def _flag_score(
        self,
        text: str,
        ground_truth: str | None,
        metadata_success: bool | None = None,
        tool_calls: list[dict[str, str]] | None = None,
    ) -> float:
        return flag_score(
            text,
            ground_truth,
            flag_verified_marker=self._FLAG_VERIFIED,
            flag_rejected_marker=self._FLAG_REJECTED,
            metadata_success=metadata_success,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _is_real_flag(flag: str) -> bool:
        return is_real_flag(flag)

    def _uniqueness_score(self, tool_calls: list[dict[str, str]]) -> float:
        return uniqueness_score(tool_calls)

    @staticmethod
    def _extract_command(tc: dict[str, str]) -> str:
        return extract_command(tc)

    def _efficiency_score(
        self,
        actual_steps: int,
        optimal_steps: int | None,
        flag_found: bool = False,
        tool_calls: list[dict[str, str]] | None = None,
    ) -> float:
        return efficiency_score(actual_steps, optimal_steps, flag_found, tool_calls)

    def _format_score(self, tool_calls: list[dict[str, str]]) -> float:
        return format_score(tool_calls)

    @staticmethod
    def _is_known_tool(name: str) -> bool:
        return is_known_tool(name)

    def _progression_score(self, tool_calls: list[dict[str, str]]) -> float:
        return progression_score(tool_calls)

    @staticmethod
    def _classify_phase(tc: dict[str, str]) -> str | None:
        return classify_phase(tc)

    def _exploration_score(self, tool_calls: list[dict[str, str]]) -> float:
        return exploration_score(tool_calls, gamma=self.exploration_gamma)

    def _recovery_score(self, tool_calls: list[dict[str, str]]) -> float:
        return recovery_score(tool_calls)

    @staticmethod
    def _action_fingerprint(tc: dict[str, str]) -> str:
        return action_fingerprint(tc)

    def _cognitive_score(self, text: str, tool_calls: list[dict[str, str]]) -> float:
        return cognitive_score(text, tool_calls)

    def _hallucination_score(
        self,
        tool_calls: list[dict[str, str]],
        flag_sc: float,
        ground_truth: str | None = None,
    ) -> float:
        return hallucination_score(
            tool_calls, flag_sc, ground_truth, penalty=self.hallucination_penalty
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract(completion: Any) -> tuple[str, list[dict[str, str]]]:
        """Extract flat text and structured tool calls from a completion.

        Returns:
            (text, tool_calls) where tool_calls is a list of
            {"name": str, "arguments": str} dicts.
        """
        if isinstance(completion, str):
            return completion, []
        if isinstance(completion, dict):
            # Single message dict (not wrapped in a list)
            content = completion.get("content") or ""
            tool_calls = []
            for tc in completion.get("tool_calls") or []:
                func = tc.get("function", {})
                name = func.get("name", "")
                args = func.get("arguments", "")
                if isinstance(args, dict):
                    args = json.dumps(args)
                tool_calls.append({"name": name, "arguments": args or ""})
            return str(content), tool_calls
        if isinstance(completion, list):
            text_parts: list[str] = []
            tool_calls: list[dict[str, str]] = []
            for msg in completion:
                if not isinstance(msg, dict):
                    text_parts.append(str(msg))
                    continue
                content = msg.get("content") or ""
                text_parts.append(str(content))
                for tc in msg.get("tool_calls") or []:
                    func = tc.get("function", {}) if isinstance(tc, dict) else {}
                    name = func.get("name", "")
                    args = func.get("arguments", "")
                    if isinstance(args, dict):
                        args = json.dumps(args)
                    tool_calls.append({"name": name, "arguments": args or ""})
            return "\n".join(text_parts), tool_calls
        return str(completion), []
