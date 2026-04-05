#!/usr/bin/env python3
"""Validate reward function against real online RL data as a peer reviewer.

Loads actual trajectories from online RL JSONL and scores them, printing
component breakdowns to verify alignment with expected behavior.

Run: pytest tests/test_reward_real_data.py -v -s
"""

import json
from pathlib import Path
from typing import Any

import pytest
from trajgym.rewards.reward import Reward

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

ONLINE_RL_PATHS = [
    Path(__file__).parent.parent / "data" / "sft.jsonl",
    Path(__file__).parent.parent / "data" / "online_rl.jsonl",
    Path(__file__).parent.parent / "data" / "online_rl_pre_clean.jsonl",
]


def load_online_rl_samples(max_samples: int = 50) -> list[dict[str, Any]]:
    """Load real online RL samples from the first available data file."""
    for path in ONLINE_RL_PATHS:
        if path.exists():
            samples = []
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    samples.append(json.loads(line))
                    if len(samples) >= max_samples:
                        break
            return samples
    pytest.skip("No online RL data files found")


def extract_completion_from_sample(sample: dict[str, Any]) -> list[dict]:
    """Extract assistant completion messages from an online RL sample."""
    messages = sample.get("messages", [])
    # Return all messages after the system+user prompt as the completion
    completion = []
    past_prompt = False
    for msg in messages:
        role = msg.get("role", "")
        if role in ("assistant", "tool") and past_prompt:
            completion.append(msg)
        elif role == "user":
            past_prompt = True
    return completion if completion else messages


# ---------------------------------------------------------------------------
# Peer review: component breakdown on real data
# ---------------------------------------------------------------------------


class TestRealDataComponentBreakdown:
    """Score real online RL trajectories and verify component distributions."""

    @pytest.fixture
    def reward(self):
        return Reward(seed=42, noise_range=0.0)

    @pytest.fixture
    def samples(self):
        return load_online_rl_samples(50)

    def test_score_distribution(self, reward, samples):
        """Verify scores span a reasonable range across real trajectories."""
        if len(samples) < 15:
            pytest.skip(
                f"Need >= 15 samples for distribution test, got {len(samples)}"
            )
        completions = []
        gt_flags = []
        opt_steps = []
        for s in samples:
            completions.append(extract_completion_from_sample(s))
            gt_flags.append(s.get("ground_truth_flag"))
            opt_steps.append(s.get("optimal_steps"))

        scores = reward(
            completions, ground_truth_flag=gt_flags, optimal_steps=opt_steps
        )

        mean_sc = sum(scores) / len(scores)
        std_sc = (sum((s - mean_sc) ** 2 for s in scores) / len(scores)) ** 0.5
        mn, mx = min(scores), max(scores)

        print(f"\n{'='*70}")
        print(f"REAL DATA SCORE DISTRIBUTION ({len(scores)} samples)")
        print(f"{'='*70}")
        print(f"  mean={mean_sc:.4f}  std={std_sc:.4f}  min={mn:.4f}  max={mx:.4f}")
        print(f"  range={mx-mn:.4f}")

        # Online RL needs: nonzero variance, reasonable range
        assert std_sc > 0.01, f"Score std too low for online RL: {std_sc:.4f}"
        assert mx - mn > 0.1, f"Score range too narrow: {mx-mn:.4f}"

    def test_component_breakdown(self, reward, samples):
        """Print full component breakdown for first 20 real samples."""
        stats = {
            "total": [],
            "flag": [],
            "eff": [],
            "prog": [],
            "expl": [],
            "uniq": [],
            "fmt": [],
            "hall": [],
            "recov": [],
            "cog": [],
        }

        print(f"\n{'='*70}")
        print(f"COMPONENT BREAKDOWN (first {min(20, len(samples))} samples)")
        print(f"{'='*70}")

        for i, s in enumerate(samples[:20]):
            comp = extract_completion_from_sample(s)
            gt = s.get("ground_truth_flag")
            opt = s.get("optimal_steps")

            text, tool_calls = reward._extract(comp)
            flag_sc = reward._flag_score(text, gt, None, tool_calls=tool_calls)
            eff_sc = reward._efficiency_score(
                len(tool_calls), opt, flag_found=(flag_sc >= 1.0)
            )
            prog_sc = reward._progression_score(tool_calls)
            expl_sc = reward._exploration_score(tool_calls)
            uniq_sc = reward._uniqueness_score(tool_calls)
            fmt_sc = reward._format_score(tool_calls)
            hall_sc = reward._hallucination_score(tool_calls, flag_sc)
            recov_sc = reward._recovery_score(tool_calls)
            cog_sc = reward._cognitive_score(text, tool_calls)

            total = reward([comp], ground_truth_flag=[gt], optimal_steps=[opt])[0]

            # Tool names summary
            tc_names = [tc.get("name", "?") for tc in tool_calls[:8]]
            tc_summary = ", ".join(tc_names)
            if len(tool_calls) > 8:
                tc_summary += f"... (+{len(tool_calls)-8})"

            # Words-per-action
            words = len(text.split()) if text else 0
            wpa = words / len(tool_calls) if tool_calls else 0

            # Source info
            meta = s.get("metadata", {})
            source = meta.get("source", "?") if isinstance(meta, dict) else "?"

            print(
                f"\n  [{i:2d}] total={total:+.3f} | flag={flag_sc:.2f} eff={eff_sc:.2f} "
                f"prog={prog_sc:.2f} expl={expl_sc:.2f} uniq={uniq_sc:.2f} "
                f"fmt={fmt_sc:.2f} hall={hall_sc:+.2f} recov={recov_sc:.2f} cog={cog_sc:.2f}"
            )
            print(
                f"       {len(tool_calls)} tools | {words} words | WPA={wpa:.0f} | "
                f"src={source} | gt_flag={'yes' if gt else 'no'}"
            )
            print(f"       tools: [{tc_summary}]")

            stats["total"].append(total)
            stats["flag"].append(flag_sc)
            stats["eff"].append(eff_sc)
            stats["prog"].append(prog_sc)
            stats["expl"].append(expl_sc)
            stats["uniq"].append(uniq_sc)
            stats["fmt"].append(fmt_sc)
            stats["hall"].append(hall_sc)
            stats["recov"].append(recov_sc)
            stats["cog"].append(cog_sc)

        # Summary table
        print(f"\n{'='*70}")
        print(f"COMPONENT STATISTICS (n={min(20, len(samples))})")
        print(f"{'='*70}")
        print(
            f"  {'Component':<10} {'Mean':>8} {'Std':>8} {'Min':>8} {'Max':>8} {'NonZero':>10}"
        )
        for name, vals in stats.items():
            if vals:
                mean = sum(vals) / len(vals)
                std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
                mn, mx = min(vals), max(vals)
                nz = sum(1 for v in vals if abs(v) > 0.001)
                print(
                    f"  {name:<10} {mean:>8.4f} {std:>8.4f} {mn:>8.4f} {mx:>8.4f} "
                    f"{nz:>4d}/{len(vals)}"
                )

    def test_success_vs_failure_gap(self, reward, samples):
        """Verify successful traces score higher than failures."""
        successes = []
        failures = []

        for s in samples:
            comp = extract_completion_from_sample(s)
            gt = s.get("ground_truth_flag")
            opt = s.get("optimal_steps")
            score = reward([comp], ground_truth_flag=[gt], optimal_steps=[opt])[0]

            text, _ = reward._extract(comp)
            if gt and gt in text:
                successes.append(score)
            else:
                failures.append(score)

        print(f"\n{'='*70}")
        print("SUCCESS vs FAILURE GAP")
        print(f"{'='*70}")
        if successes:
            s_mean = sum(successes) / len(successes)
            print(f"  Success: n={len(successes)}, mean={s_mean:.4f}")
        else:
            print("  Success: n=0 (no exact flag matches in text)")
            s_mean = None
        if failures:
            f_mean = sum(failures) / len(failures)
            print(f"  Failure: n={len(failures)}, mean={f_mean:.4f}")
        else:
            print("  Failure: n=0")
            f_mean = None

        if s_mean is not None and f_mean is not None:
            gap = s_mean - f_mean
            print(f"  Gap: {gap:.4f}")
            assert gap > 0.1, f"Success-failure gap too small: {gap:.4f}"

    def test_no_reward_collapse(self, reward, samples):
        """Verify no single component dominates all scores."""
        if len(samples) < 15:
            pytest.skip(
                f"Need >= 15 samples for collapse test, got {len(samples)}"
            )
        completions = []
        gt_flags = []
        opt_steps = []
        for s in samples:
            completions.append(extract_completion_from_sample(s))
            gt_flags.append(s.get("ground_truth_flag"))
            opt_steps.append(s.get("optimal_steps"))

        scores = reward(
            completions, ground_truth_flag=gt_flags, optimal_steps=opt_steps
        )

        # Check that not all scores are identical
        unique_scores = len(set(round(s, 4) for s in scores))
        print(f"\n  Unique scores (4 dp): {unique_scores}/{len(scores)}")
        assert (
            unique_scores > len(scores) * 0.3
        ), f"Too many identical scores ({unique_scores}/{len(scores)}) -- reward collapse"

    def test_recovery_signal_on_real_data(self, reward, samples):
        """Verify recovery signal differentiates stuck vs. pivoting traces."""
        recovery_scores = []
        for s in samples:
            comp = extract_completion_from_sample(s)
            _, tool_calls = reward._extract(comp)
            recov = reward._recovery_score(tool_calls)
            recovery_scores.append(recov)

        nonzero = sum(1 for r in recovery_scores if abs(r - 0.5) > 0.01)
        print(
            f"\n  Recovery: {nonzero}/{len(recovery_scores)} non-neutral "
            f"({100*nonzero/len(recovery_scores):.0f}%)"
        )
        mean_r = sum(recovery_scores) / len(recovery_scores)
        print(f"  Recovery mean: {mean_r:.3f}")

    def test_cognitive_signal_on_real_data(self, reward, samples):
        """Verify cognitive WPA signal produces meaningful variance."""
        cog_scores = []
        wpas = []
        for s in samples:
            comp = extract_completion_from_sample(s)
            text, tool_calls = reward._extract(comp)
            cog = reward._cognitive_score(text, tool_calls)
            cog_scores.append(cog)
            if tool_calls:
                words = len(text.split()) if text else 0
                wpas.append(words / len(tool_calls))

        if wpas:
            mean_wpa = sum(wpas) / len(wpas)
            print(
                f"\n  WPA: mean={mean_wpa:.1f}, "
                f"min={min(wpas):.1f}, max={max(wpas):.1f}"
            )
        mean_c = sum(cog_scores) / len(cog_scores)
        std_c = (sum((c - mean_c) ** 2 for c in cog_scores) / len(cog_scores)) ** 0.5
        nonzero = sum(1 for c in cog_scores if abs(c - 0.5) > 0.01)
        print(
            f"  Cognitive: mean={mean_c:.3f}, std={std_c:.3f}, "
            f"non-neutral={nonzero}/{len(cog_scores)}"
        )

    def test_exploration_exponential_decay(self, reward, samples):
        """Verify exponential decay differentiates early vs late novelty."""
        if len(samples) < 15:
            pytest.skip(
                f"Need >= 15 samples for exploration variance test, got {len(samples)}"
            )
        expl_scores = []
        for s in samples:
            comp = extract_completion_from_sample(s)
            _, tool_calls = reward._extract(comp)
            expl = reward._exploration_score(tool_calls)
            expl_scores.append(expl)

        nonzero = sum(1 for e in expl_scores if e > 0.001)
        mean_e = sum(expl_scores) / len(expl_scores)
        std_e = (sum((e - mean_e) ** 2 for e in expl_scores) / len(expl_scores)) ** 0.5
        print(
            f"\n  Exploration: mean={mean_e:.3f}, std={std_e:.3f}, "
            f"active={nonzero}/{len(expl_scores)}"
        )
        assert std_e > 0.001, f"Exploration std too low: {std_e}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
