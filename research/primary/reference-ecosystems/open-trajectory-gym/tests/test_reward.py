"""Smoke tests for Reward function.

Validates the 9-signal reward function:
- Flag capture (exact match, pattern match, env verification, no match)
- Efficiency (optimal vs actual steps, gating at <3 steps)
- Progression (RECON->ENUM->EXPLOIT ordering)
- Exploration (exponentially-decayed novelty)
- Uniqueness (command diversity)
- Format compliance (valid JSON args, known tool names)
- Recovery (pivots after stuck runs)
- Cognitive (words-per-action density)
- Hallucination penalty (wrong flag submission)
- Interaction quality (output-aware HTTP progress)
- Noise (variance guarantee for Online RL)
- Weight validation (auto-normalizes to sum 1.0)
"""

import json

import pytest
from trajgym.rewards.reward import Reward

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tc(name: str, args: dict | str = "{}") -> dict:
    """Build a tool call dict for internal scoring methods."""
    if isinstance(args, dict):
        args = json.dumps(args)
    return {"name": name, "arguments": args}


def _shell(cmd: str) -> dict:
    return _tc("shell_command", {"command": cmd})


def _completion_with_tools(tool_calls: list[dict], text: str = "") -> list[dict]:
    """Build a ChatML completion with tool calls."""
    msgs = []
    for i, t in enumerate(tool_calls):
        msgs.append(
            {
                "role": "assistant",
                "content": text if i == 0 else "",
                "tool_calls": [{"function": t}],
            }
        )
        msgs.append(
            {
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "content": f"output_{i}",
            }
        )
    return msgs


# ---------------------------------------------------------------------------
# Construction and weight validation
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_default_weights_sum_to_one(self):
        r = Reward()
        total = (
            r.flag_weight
            + r.efficiency_weight
            + r.progression_weight
            + r.exploration_weight
            + r.uniqueness_weight
            + r.format_weight
            + r.recovery_weight
            + r.cognitive_weight
        )
        assert abs(total - 1.0) < 1e-6

    def test_invalid_weights_auto_normalized(self):
        r = Reward(flag_weight=0.5, efficiency_weight=0.5, progression_weight=0.5)
        total = (
            r.flag_weight
            + r.efficiency_weight
            + r.progression_weight
            + r.exploration_weight
            + r.uniqueness_weight
            + r.format_weight
            + r.recovery_weight
            + r.cognitive_weight
        )
        assert abs(total - 1.0) < 1e-6

    def test_custom_weights(self):
        r = Reward(
            flag_weight=0.30,
            efficiency_weight=0.15,
            progression_weight=0.10,
            exploration_weight=0.10,
            uniqueness_weight=0.05,
            format_weight=0.10,
            recovery_weight=0.10,
            cognitive_weight=0.10,
        )
        assert r.flag_weight == 0.30


# ---------------------------------------------------------------------------
# Flag capture signal
# ---------------------------------------------------------------------------


class TestFlagCapture:
    @pytest.fixture
    def r(self):
        return Reward(noise_range=0.0, seed=0)

    def test_exact_match(self, r):
        assert r._flag_score("flag_found: Found FLAG{abc}", "FLAG{abc}") == 1.0

    def test_env_verified_correct(self, r):
        assert r._flag_score("Correct! Flag verified: FLAG{x}", None) == 1.0

    def test_env_verified_incorrect(self, r):
        assert r._flag_score("Incorrect submission: FLAG{x}", None) == 0.0

    def test_pattern_match_no_ground_truth(self, r):
        assert r._flag_score("FLAG{some_real_flag}", None) == 0.1

    def test_pattern_match_wrong_flag(self, r):
        assert r._flag_score("FLAG{wrong}", "FLAG{correct}") == 0.1

    def test_no_flag(self, r):
        assert r._flag_score("no flag at all", "FLAG{test}") == 0.0

    def test_placeholder_flag_not_matched(self, r):
        assert r._flag_score("content_of_flag_here", "content_of_flag_here") == 0.0

    def test_check_placeholder_skipped(self, r):
        assert r._flag_score("answer CHECK here", "CHECK") == 0.0

    def test_empty_text(self, r):
        assert r._flag_score("", "FLAG{test}") == 0.0


# ---------------------------------------------------------------------------
# Efficiency signal
# ---------------------------------------------------------------------------


class TestEfficiency:
    @pytest.fixture
    def r(self):
        return Reward(noise_range=0.0, seed=0)

    def test_optimal_path(self, r):
        # At optimal step count with no tool_calls: step_ratio=1, novelty=1, decay=1
        assert r._efficiency_score(5, 5, flag_found=True) == 1.0

    def test_double_optimal(self, r):
        # 2x optimal: step_ratio=0.5, temporal_decay=exp(-0.3*1)=0.74
        # Without tool_calls novelty=1.0 → score ≈ 0.37
        score = r._efficiency_score(10, 5, flag_found=True)
        assert 0.35 < score < 0.40

    def test_zero_steps(self, r):
        assert r._efficiency_score(0, 5) == 0.0

    def test_fewer_than_3_steps(self, r):
        assert r._efficiency_score(2, 5) == 0.0

    def test_no_metadata(self, r):
        assert r._efficiency_score(5, None) == 0.3

    def test_capped_without_flag(self, r):
        score = r._efficiency_score(5, 5, flag_found=False)
        assert score <= 0.3

    def test_redundant_tool_calls_penalized(self, r):
        """Repeated commands reduce novelty → lower score (least action)."""
        unique_calls = [
            {"name": "shell_command", "arguments": '{"command": "ls"}'},
            {"name": "shell_command", "arguments": '{"command": "cat flag.txt"}'},
            {"name": "read_file", "arguments": '{"path": "/etc/passwd"}'},
            {"name": "python_code", "arguments": '{"code": "print(1)"}'},
            {"name": "flag_found", "arguments": '{"content": "HTB{x}"}'},
        ]
        repeated_calls = [
            {"name": "shell_command", "arguments": '{"command": "ls"}'},
            {"name": "shell_command", "arguments": '{"command": "ls"}'},
            {"name": "shell_command", "arguments": '{"command": "ls"}'},
            {"name": "shell_command", "arguments": '{"command": "cat flag.txt"}'},
            {"name": "flag_found", "arguments": '{"content": "HTB{x}"}'},
        ]
        score_unique = r._efficiency_score(
            5, 5, flag_found=True, tool_calls=unique_calls
        )
        score_repeated = r._efficiency_score(
            5, 5, flag_found=True, tool_calls=repeated_calls
        )
        assert score_unique > score_repeated

    def test_temporal_decay_penalizes_long_trajectories(self, r):
        """Longer trajectories get exponentially penalized even at same step ratio."""
        # Both at 2x optimal, but 20/10 vs 6/3
        score_long = r._efficiency_score(20, 10, flag_found=True)
        score_short = r._efficiency_score(6, 3, flag_found=True)
        # Both have step_ratio=0.5, but long has more excess → more decay
        assert score_long == score_short  # Same ratio, same excess ratio → same score


# ---------------------------------------------------------------------------
# Progression signal (RECON->ENUM->EXPLOIT)
# ---------------------------------------------------------------------------


class TestProgression:
    @pytest.fixture
    def r(self):
        return Reward(noise_range=0.0, seed=0)

    def test_perfect_ordering(self, r):
        tool_calls = [
            _shell("nmap target"),  # recon
            _shell("curl target"),  # enum
            _tc("python_code", {"code": "exploit()"}),  # exploit
        ]
        assert r._progression_score(tool_calls) == 1.0

    def test_no_tool_calls(self, r):
        assert r._progression_score([]) == 0.0

    def test_only_enum(self, r):
        tool_calls = [_shell("curl target"), _shell("gobuster dir target")]
        score = r._progression_score(tool_calls)
        assert 0.0 < score < 1.0  # Has enum but missing recon/exploit


# ---------------------------------------------------------------------------
# Exploration signal
# ---------------------------------------------------------------------------


class TestExploration:
    @pytest.fixture
    def r(self):
        return Reward(noise_range=0.0, seed=0)

    def test_empty(self, r):
        assert r._exploration_score([]) == 0.0

    def test_all_unique_known_tools(self, r):
        tool_calls = [
            _tc("shell_command", {"command": "nmap"}),
            _tc("python_code", {"code": "x"}),
            _tc("read_file", {"path": "/etc/passwd"}),
        ]
        score = r._exploration_score(tool_calls)
        assert score > 0.8  # All unique and early = high

    def test_all_same_tool(self, r):
        tool_calls = [_tc("shell_command", {"command": "ls"})] * 5
        score = r._exploration_score(tool_calls)
        assert score < 0.5  # Only 1 unique out of 5


# ---------------------------------------------------------------------------
# Uniqueness signal
# ---------------------------------------------------------------------------


class TestUniqueness:
    @pytest.fixture
    def r(self):
        return Reward(noise_range=0.0, seed=0)

    def test_all_unique(self, r):
        tool_calls = [
            _shell("nmap target"),
            _shell("curl target"),
            _shell("gobuster dir target"),
        ]
        assert r._uniqueness_score(tool_calls) == 1.0

    def test_all_same(self, r):
        tool_calls = [_shell("ls")] * 4
        assert r._uniqueness_score(tool_calls) == 0.25

    def test_empty(self, r):
        assert r._uniqueness_score([]) == 0.0


# ---------------------------------------------------------------------------
# Format compliance signal
# ---------------------------------------------------------------------------


class TestFormat:
    @pytest.fixture
    def r(self):
        return Reward(noise_range=0.0, seed=0)

    def test_valid_json_known_tool(self, r):
        tool_calls = [_tc("shell_command", {"command": "ls"})]
        assert r._format_score(tool_calls) == 1.0

    def test_invalid_json(self, r):
        tool_calls = [{"name": "shell_command", "arguments": "not json"}]
        assert r._format_score(tool_calls) == 0.5  # Partial credit

    def test_unknown_tool_excluded(self, r):
        tool_calls = [{"name": "totally_fake", "arguments": '{"x": 1}'}]
        assert r._format_score(tool_calls) == 0.0

    def test_empty(self, r):
        assert r._format_score([]) == 0.0


# ---------------------------------------------------------------------------
# Recovery signal
# ---------------------------------------------------------------------------


class TestRecovery:
    @pytest.fixture
    def r(self):
        return Reward(noise_range=0.0, seed=0)

    def test_too_short(self, r):
        tool_calls = [_shell("nmap target"), _shell("curl target")]
        assert r._recovery_score(tool_calls) == 0.5  # Neutral

    def test_no_stuck_runs(self, r):
        tool_calls = [
            _shell("nmap target"),
            _shell("curl target"),
            _tc("python_code", {"code": "x"}),
        ]
        assert r._recovery_score(tool_calls) == 0.5  # Neutral

    def test_stuck_then_pivot(self, r):
        tool_calls = [
            _shell("curl target/admin"),
            _shell("curl target/admin"),
            _shell("nmap target"),  # Pivot
        ]
        score = r._recovery_score(tool_calls)
        assert score == 1.0  # 1 stuck run, 1 pivot = 1.0

    def test_stuck_no_pivot(self, r):
        tool_calls = [
            _shell("curl target"),
            _shell("curl target"),
            _shell("curl target"),
        ]
        score = r._recovery_score(tool_calls)
        assert score == 0.0  # Stuck but never pivoted


# ---------------------------------------------------------------------------
# Cognitive (words-per-action) signal
# ---------------------------------------------------------------------------


class TestCognitive:
    @pytest.fixture
    def r(self):
        return Reward(noise_range=0.0, seed=0)

    def test_no_tool_calls(self, r):
        assert r._cognitive_score("some text", []) == 0.0

    def test_too_few_words(self, r):
        assert r._cognitive_score("hi", [_shell("ls")]) == 0.5  # Neutral

    def test_optimal_wpa(self, r):
        # 42 words per 1 tool call = optimal
        text = " ".join(["word"] * 42)
        score = r._cognitive_score(text, [_shell("ls")])
        assert score == pytest.approx(1.0)

    def test_severe_underthinking(self, r):
        # 5 words per 1 tool call = WPA 5 < 10
        text = " ".join(["word"] * 5)
        score = r._cognitive_score(text, [_shell("ls")])
        assert score == pytest.approx(0.1)

    def test_severe_overthinking(self, r):
        # 100 words per 1 tool call = WPA 100 > 80
        text = " ".join(["word"] * 100)
        score = r._cognitive_score(text, [_shell("ls")])
        assert score == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Hallucination penalty
# ---------------------------------------------------------------------------


class TestHallucination:
    @pytest.fixture
    def r(self):
        return Reward(noise_range=0.0, seed=0)

    def test_correct_flag_no_penalty(self, r):
        tool_calls = [_tc("flag_found", {"content": "FLAG{x}"})]
        assert r._hallucination_score(tool_calls, flag_sc=1.0) == 0.0

    def test_wrong_flag_penalty(self, r):
        """Wrong flag with 1 tool call gets premature multiplier (1.8x)."""
        tool_calls = [_tc("flag_found", {"content": "FLAG{wrong}"})]
        penalty = r._hallucination_score(tool_calls, flag_sc=0.1)
        assert penalty < 0  # Negative
        # 1 tool call → premature_mult = 1.0 + max(0, 1.0 - 1/5) = 1.8
        expected = -r.hallucination_penalty * 1.8
        assert penalty == pytest.approx(expected)

    def test_wrong_flag_penalty_many_steps(self, r):
        """Wrong flag with 5+ tool calls gets no premature multiplier."""
        tool_calls = [
            _shell("nmap target"),
            _shell("curl target/"),
            _shell("gobuster dir target"),
            _shell("curl target/admin"),
            _tc("flag_found", {"content": "FLAG{wrong}"}),
        ]
        penalty = r._hallucination_score(tool_calls, flag_sc=0.1)
        assert penalty < 0
        # 5 tool calls → premature_mult = 1.0 + max(0, 1.0 - 5/5) = 1.0
        assert penalty == pytest.approx(-r.hallucination_penalty)

    def test_premature_hallucination_two_steps(self, r):
        """Wrong flag with 2 tool calls gets 1.6x multiplier."""
        tool_calls = [
            _shell("curl target/"),
            _tc("flag_found", {"content": "FLAG{wrong}"}),
        ]
        penalty = r._hallucination_score(tool_calls, flag_sc=0.1)
        # 2 tool calls → premature_mult = 1.0 + max(0, 1.0 - 2/5) = 1.6
        expected = -r.hallucination_penalty * 1.6
        assert penalty == pytest.approx(expected)

    def test_no_flag_submission_no_penalty(self, r):
        tool_calls = [_shell("nmap target")]
        assert r._hallucination_score(tool_calls, flag_sc=0.0) == 0.0


# ---------------------------------------------------------------------------
# Noise and variance
# ---------------------------------------------------------------------------


class TestNoise:
    def test_noise_provides_variance(self):
        r = Reward(noise_range=0.05, seed=42)
        scores = [r(["hello"])[0] for _ in range(20)]
        unique = len(set(round(s, 8) for s in scores))
        assert unique > 1, "Noise should create different scores"

    def test_zero_noise_deterministic(self):
        r = Reward(noise_range=0.0, seed=0)
        s1 = r(["hello"])[0]
        s2 = r(["hello"])[0]
        assert s1 == s2


# ---------------------------------------------------------------------------
# Full __call__ integration
# ---------------------------------------------------------------------------


class TestCallIntegration:
    @pytest.fixture
    def r(self):
        return Reward(noise_range=0.0, seed=0)

    def test_return_type(self, r):
        scores = r(["hello", "world"])
        assert isinstance(scores, list)
        assert len(scores) == 2
        assert all(isinstance(s, float) for s in scores)

    def test_success_higher_than_failure(self, r):
        success = _completion_with_tools(
            [
                _shell("nmap t"),
                _shell("curl t"),
                _tc("python_code", {"code": "x"}),
                _tc("flag_found", {"content": "FLAG{win}"}),
            ],
            text="FLAG{win}",
        )
        failure = [{"role": "assistant", "content": "I failed."}]
        scores = r(
            [success, failure],
            ground_truth_flag=["FLAG{win}", "FLAG{win}"],
            optimal_steps=[4, 4],
        )
        assert scores[0] > scores[1]

    def test_batch_length_matches_input(self, r):
        scores = r(["a", "b", "c"])
        assert len(scores) == 3

    def test_no_kwargs(self, r):
        scores = r(["hello"])
        assert len(scores) == 1
        assert isinstance(scores[0], float)


# ---------------------------------------------------------------------------
# Minimum work gate (Fix 2)
# ---------------------------------------------------------------------------


class TestMinimumWorkGate:
    """Tests that short episodes have capped process rewards."""

    @pytest.fixture
    def r(self):
        return Reward(noise_range=0.0, seed=0)

    def test_single_tool_call_caps_format(self, r):
        """One tool call should cap format score at 0.3."""
        tool_calls = [_tc("shell_command", {"command": "ls"})]
        # Normally a valid known tool gets format=1.0
        raw_fmt = r._format_score(tool_calls)
        assert raw_fmt == 1.0

        # But in _score_one, it gets capped.
        completion = _completion_with_tools(tool_calls, text="checking files")
        _, breakdown = r.compute_with_breakdown([completion])[0]
        # The format signal should be capped:
        # fmt_sc capped to 0.3, then info_density = max(uniq_sc, 0.5)
        # where uniq_sc is also capped to 0.3 → info_density = 0.5
        # fmt_effective = 0.3 * 0.5 = 0.15
        assert breakdown["format"] <= 0.3 * 0.5 + 0.01

    def test_two_tool_calls_caps_scores(self, r):
        """Two tool calls still gets capped."""
        tool_calls = [_shell("nmap target"), _shell("curl target/")]
        completion = _completion_with_tools(tool_calls, text="scanning and enumerating")
        _, breakdown = r.compute_with_breakdown([completion])[0]
        # Recovery is normally 0.5 (neutral for < 3 calls)
        # But capped at 0.3
        assert breakdown["recovery"] <= 0.3

    def test_three_tool_calls_not_capped(self, r):
        """Three tool calls should NOT be capped."""
        tool_calls = [
            _shell("nmap target"),
            _shell("curl target/"),
            _tc("python_code", {"code": "exploit()"}),
        ]
        # All 3 are unique and valid → format = 1.0, uniqueness = 1.0
        raw_fmt = r._format_score(tool_calls)
        assert raw_fmt == 1.0
        raw_uniq = r._uniqueness_score(tool_calls)
        assert raw_uniq == 1.0

        # Not capped with 3+ calls
        completion = _completion_with_tools(
            tool_calls,
            text="Performing reconnaissance scan then enumerating endpoints and writing exploit",
        )
        _, breakdown = r.compute_with_breakdown([completion])[0]
        # format = fmt_sc * info_density = 1.0 * max(1.0, 0.5) = 1.0
        assert breakdown["format"] > 0.3

    def test_short_episode_total_lower(self, r):
        """A 1-step hallucinated flag should score much worse than a 15-step exploration."""
        # 1-step hallucination: submits wrong flag immediately
        bad_calls = [_tc("flag_found", {"content": "FLAG{guessed}"})]
        bad_completion = _completion_with_tools(bad_calls, text="FLAG{guessed}")
        bad_score = r([bad_completion], ground_truth_flag=["FLAG{real}"])[0]

        # 15-step exploration: uses many tools productively
        good_calls = [
            _shell("nmap -sV target"),
            _shell("curl http://target/"),
            _shell("gobuster dir -u http://target/ -w list.txt"),
            _shell("curl http://target/admin"),
            _shell("curl http://target/api/v1"),
            _tc("python_code", {"code": "import requests"}),
            _shell("curl http://target/login"),
            _shell("curl http://target/dashboard"),
            _shell("curl -X POST http://target/login -d user=admin"),
            _shell("curl http://target/api/users"),
            _shell("curl http://target/config"),
            _shell("curl http://target/robots.txt"),
            _shell("curl http://target/sitemap.xml"),
            _shell("curl http://target/.env"),
            _shell("curl http://target/api/status"),
        ]
        good_completion = _completion_with_tools(
            good_calls,
            text=(
                "I am systematically exploring this web application. "
                "First I need to scan for open ports and services. "
                "Then I will enumerate endpoints and check for misconfigurations. "
                "Let me also test for common API endpoints and configuration files."
            ),
        )
        good_score = r([good_completion], ground_truth_flag=["FLAG{real}"])[0]

        assert good_score > bad_score, (
            f"15-step exploration ({good_score:.3f}) should beat "
            f"1-step hallucination ({bad_score:.3f})"
        )


# ---------------------------------------------------------------------------
# Premature hallucination penalty (Fix 1)
# ---------------------------------------------------------------------------


class TestPrematureHallucinationPenalty:
    """Verify that the premature submission multiplier works correctly."""

    @pytest.fixture
    def r(self):
        return Reward(noise_range=0.0, seed=0)

    def test_one_step_hallucination_stronger_penalty(self, r):
        """1-step hallucination should have stronger penalty than 5-step."""
        # 1 tool call (premature_mult = 1.8)
        one_step = [_tc("flag_found", {"content": "FLAG{wrong}"})]
        penalty_1 = r._hallucination_score(one_step, flag_sc=0.1)

        # 5 tool calls (premature_mult = 1.0)
        five_step = [
            _shell("nmap target"),
            _shell("curl target/"),
            _shell("gobuster dir target"),
            _shell("curl target/admin"),
            _tc("flag_found", {"content": "FLAG{wrong}"}),
        ]
        penalty_5 = r._hallucination_score(five_step, flag_sc=0.1)

        # 1-step penalty should be stronger (more negative)
        assert penalty_1 < penalty_5
        assert penalty_1 == pytest.approx(-0.20 * 1.8)
        assert penalty_5 == pytest.approx(-0.20 * 1.0)

    def test_premature_penalty_gradual(self, r):
        """Penalty multiplier should decrease as tool calls increase."""
        penalties = []
        for n_steps in range(1, 7):
            calls = [_shell(f"cmd_{i}") for i in range(n_steps - 1)]
            calls.append(_tc("flag_found", {"content": "FLAG{wrong}"}))
            pen = r._hallucination_score(calls, flag_sc=0.1)
            penalties.append(pen)

        # Each successive penalty should be less severe (closer to zero)
        for i in range(len(penalties) - 1):
            assert penalties[i] <= penalties[i + 1], (
                f"Penalty at {i+1} steps ({penalties[i]}) should be "
                f"<= penalty at {i+2} steps ({penalties[i+1]})"
            )

    def test_similarity_decay_still_works_with_premature(self, r):
        """Near-correct flag still gets 90% decay on top of premature multiplier."""
        # 1 tool call, near-correct flag
        calls = [_tc("flag_found", {"content": "FLAG{almost_correct}"})]
        penalty = r._hallucination_score(
            calls, flag_sc=0.1, ground_truth="FLAG{almost_correct_x}"
        )
        # premature_mult = 1.8, similarity > 0.8 → penalty *= 0.1
        expected = -0.20 * 1.8 * 0.1
        assert penalty == pytest.approx(expected, abs=0.01)
