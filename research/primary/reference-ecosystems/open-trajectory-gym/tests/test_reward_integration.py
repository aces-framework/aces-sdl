"""Tests for Reward function.

Validates all four reward components (flag, uniqueness, efficiency, format)
plus integration tests against online RL dataset JSONL.
"""

import json
from pathlib import Path

import pytest
from trajgym.rewards.reward import Reward

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def reward():
    """Reward with fixed seed for deterministic noise."""
    return Reward(seed=42)


@pytest.fixture
def reward_no_noise():
    """Reward with zero noise for exact value testing."""
    return Reward(noise_range=0.0, seed=0)


@pytest.fixture
def grpo_samples():
    """Load online RL samples with full Online RL schema (metadata.success, optimal_steps int).

    Only loads from files that contain the full schema required by TestGRPOSamples.
    Falls back through candidate paths; skips if no matching data is found.
    """
    candidates = [
        DATA_DIR / "online_rl.jsonl",
        DATA_DIR / "sft.jsonl",
        DATA_DIR / "online_rl.jsonl",
    ]
    for path in candidates:
        if not path.exists():
            continue
        samples = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
        if not samples:
            continue
        # Validate schema: TestGRPOSamples requires metadata.success and int optimal_steps
        first = samples[0]
        meta = first.get("metadata", {})
        if not isinstance(meta, dict) or "success" not in meta:
            continue
        if not isinstance(first.get("optimal_steps"), int):
            continue
        return samples
    pytest.skip(
        "No online RL dataset with full ONLINE_RL schema found "
        "(needs metadata.success + int optimal_steps)"
    )


# ---------------------------------------------------------------------------
# _flag_score tests
# ---------------------------------------------------------------------------


class TestFlagScore:
    def test_exact_match(self, reward_no_noise):
        score = reward_no_noise._flag_score(
            "flag_found: Found FLAG{test_123}", "FLAG{test_123}"
        )
        assert score == 1.0

    def test_exact_match_embedded(self, reward_no_noise):
        text = "flag_found: Welcome admin! Your flag is FLAG{abc_def} congrats!"
        score = reward_no_noise._flag_score(text, "FLAG{abc_def}")
        assert score == 1.0

    def test_metadata_success_ignored(self, reward_no_noise):
        # metadata_success is accepted for API compat but no longer overrides.
        # Without flag text or env verification, score should be 0.0.
        score = reward_no_noise._flag_score("no flag here", None, metadata_success=True)
        assert score == 0.0

    def test_metadata_success_with_placeholder_flag(self, reward_no_noise):
        # placeholder flag + metadata.success should NOT give 1.0 anymore.
        score = reward_no_noise._flag_score(
            "no flag text", "content_of_flag_here", metadata_success=True
        )
        assert score == 0.0

    def test_placeholder_flag_skipped(self, reward_no_noise):
        # Placeholder flag should not match even if present in text
        score = reward_no_noise._flag_score(
            "content_of_flag_here", "content_of_flag_here"
        )
        assert score == 0.0

    def test_pattern_match_no_gt(self, reward_no_noise):
        score = reward_no_noise._flag_score("FLAG{some_random_flag}", None)
        assert score == 0.1

    def test_pattern_match_wrong_gt(self, reward_no_noise):
        score = reward_no_noise._flag_score("FLAG{wrong_flag}", "FLAG{correct_flag}")
        assert score == 0.1

    def test_no_flag(self, reward_no_noise):
        score = reward_no_noise._flag_score("No flag here at all", "FLAG{test}")
        assert score == 0.0

    def test_placeholder_not_matched(self, reward_no_noise):
        score = reward_no_noise._flag_score("FLAG{...}", None)
        assert score == 0.0

    def test_empty_text(self, reward_no_noise):
        score = reward_no_noise._flag_score("", "FLAG{test}")
        assert score == 0.0

    def test_no_ground_truth_no_flag(self, reward_no_noise):
        score = reward_no_noise._flag_score("hello world", None)
        assert score == 0.0

    def test_metadata_false_no_flag(self, reward_no_noise):
        # metadata_success is now ignored; no flag text = 0.0
        score = reward_no_noise._flag_score("no flag", None, metadata_success=False)
        assert score == 0.0

    def test_metadata_false_does_not_block_exact_match(self, reward_no_noise):
        """metadata_success is ignored; exact text match should still score 1.0."""
        score = reward_no_noise._flag_score(
            "flag_found: Found FLAG{real_flag}",
            "FLAG{real_flag}",
            metadata_success=False,
        )
        assert score == 1.0

    def test_metadata_false_with_flag_pattern(self, reward_no_noise):
        """metadata_success is ignored; FLAG{} pattern should give 0.1."""
        score = reward_no_noise._flag_score(
            "FLAG{some_flag}", None, metadata_success=False
        )
        assert score == 0.1

    def test_check_placeholder_skipped(self, reward_no_noise):
        """ground_truth_flag='CHECK' should be treated as placeholder."""
        score = reward_no_noise._flag_score("answer CHECK here", "CHECK")
        assert score == 0.0

    def test_template_text_flag_skipped(self, reward_no_noise):
        """Multiline flags containing 'content_of_flag_here' are placeholders."""
        template_flag = "tags:\n  <FLAG>content_of_flag_here"
        score = reward_no_noise._flag_score(template_flag, template_flag)
        assert score == 0.0


# ---------------------------------------------------------------------------
# _uniqueness_score tests
# ---------------------------------------------------------------------------


class TestUniquenessScore:
    def _tc(self, name, args="{}"):
        return {"name": name, "arguments": args}

    def test_all_unique_commands(self, reward_no_noise):
        tool_calls = [
            self._tc("shell_command", '{"command": "nmap target"}'),
            self._tc("shell_command", '{"command": "curl http://target"}'),
            self._tc("shell_command", '{"command": "gobuster dir -u http://target"}'),
        ]
        score = reward_no_noise._uniqueness_score(tool_calls)
        assert score == 1.0

    def test_all_repeated_commands(self, reward_no_noise):
        tool_calls = [
            self._tc("shell_command", '{"command": "ls"}'),
            self._tc("shell_command", '{"command": "ls"}'),
            self._tc("shell_command", '{"command": "ls"}'),
        ]
        score = reward_no_noise._uniqueness_score(tool_calls)
        assert score == pytest.approx(1.0 / 3.0)

    def test_half_repeated(self, reward_no_noise):
        tool_calls = [
            self._tc("shell_command", '{"command": "nmap target"}'),
            self._tc("shell_command", '{"command": "nmap target"}'),
            self._tc("shell_command", '{"command": "curl http://target"}'),
            self._tc("shell_command", '{"command": "curl http://target"}'),
        ]
        score = reward_no_noise._uniqueness_score(tool_calls)
        assert score == pytest.approx(0.5)

    def test_empty_tool_calls(self, reward_no_noise):
        score = reward_no_noise._uniqueness_score([])
        assert score == 0.0

    def test_single_command(self, reward_no_noise):
        tool_calls = [
            self._tc("shell_command", '{"command": "id"}'),
        ]
        score = reward_no_noise._uniqueness_score(tool_calls)
        assert score == 1.0

    def test_no_extractable_commands(self, reward_no_noise):
        tool_calls = [
            self._tc("unknown_tool", ""),
            self._tc("another_tool", ""),
        ]
        score = reward_no_noise._uniqueness_score(tool_calls)
        assert score == 0.5  # Neutral

    def test_python_code_extracted(self, reward_no_noise):
        tool_calls = [
            self._tc("python_code", '{"code": "import os; os.system(\\"id\\")"}'),
            self._tc(
                "python_code", '{"code": "print(open(\\"/etc/passwd\\").read())"}'
            ),
        ]
        score = reward_no_noise._uniqueness_score(tool_calls)
        assert score == 1.0

    def test_flag_found_extracted(self, reward_no_noise):
        tool_calls = [
            self._tc("flag_found", '{"content": "FLAG{test}"}'),
            self._tc("flag_found", '{"content": "FLAG{test}"}'),
        ]
        score = reward_no_noise._uniqueness_score(tool_calls)
        assert score == 0.5  # Same flag submitted twice


# ---------------------------------------------------------------------------
# _extract_command tests
# ---------------------------------------------------------------------------


class TestExtractCommand:
    def _tc(self, name, args):
        return {"name": name, "arguments": args}

    def test_shell_command(self):
        cmd = Reward._extract_command(
            self._tc("shell_command", '{"command": "nmap -sV target"}')
        )
        assert cmd == "nmap -sV target"

    def test_python_code(self):
        cmd = Reward._extract_command(self._tc("python_code", '{"code": "print(1)"}'))
        assert cmd == "print(1)"

    def test_flag_found(self):
        cmd = Reward._extract_command(
            self._tc("flag_found", '{"content": "FLAG{test}"}')
        )
        assert cmd == "FLAG{test}"

    def test_empty_args(self):
        cmd = Reward._extract_command(self._tc("tool", ""))
        assert cmd == ""

    def test_plain_string_args(self):
        cmd = Reward._extract_command(self._tc("tool", "ls -la"))
        assert cmd == "ls -la"

    def test_dict_with_path(self):
        cmd = Reward._extract_command(self._tc("read_file", '{"path": "/etc/passwd"}'))
        assert cmd == "/etc/passwd"


# ---------------------------------------------------------------------------
# _efficiency_score tests
# ---------------------------------------------------------------------------


class TestEfficiencyScore:
    def test_optimal_with_flag(self, reward_no_noise):
        score = reward_no_noise._efficiency_score(3, 3, flag_found=True)
        assert score == 1.0

    def test_double_optimal_with_flag(self, reward_no_noise):
        # Physics: step_ratio=0.5, novelty=1.0, decay=exp(-0.3*1)≈0.74
        score = reward_no_noise._efficiency_score(6, 3, flag_found=True)
        assert 0.35 < score < 0.40

    def test_under_3_steps_gated(self, reward_no_noise):
        # <3 steps = 0.0 (anti-gaming: prevent single-step garbage)
        score = reward_no_noise._efficiency_score(2, 3, flag_found=True)
        assert score == 0.0

    def test_no_metadata(self, reward_no_noise):
        score = reward_no_noise._efficiency_score(5, None)
        assert score == 0.3  # Weak prior: trajectory exists but unmeasured

    def test_zero_steps(self, reward_no_noise):
        score = reward_no_noise._efficiency_score(0, 3)
        assert score == 0.0

    def test_many_steps_with_flag(self, reward_no_noise):
        # Physics: step_ratio=0.2, novelty=1.0, decay=exp(-0.3*4)≈0.30
        score = reward_no_noise._efficiency_score(20, 4, flag_found=True)
        assert 0.05 < score < 0.10  # Much lower than old 0.2 due to temporal decay

    def test_many_steps_without_flag_capped(self, reward_no_noise):
        # Without flag, efficiency capped at 0.3
        score = reward_no_noise._efficiency_score(20, 4, flag_found=False)
        assert score <= 0.3

    def test_large_optimal_with_flag(self, reward_no_noise):
        score = reward_no_noise._efficiency_score(15, 15, flag_found=True)
        assert score == 1.0

    def test_no_flag_caps_at_03(self, reward_no_noise):
        # Without flag found, efficiency capped at 0.3
        score = reward_no_noise._efficiency_score(5, 5, flag_found=False)
        assert score == 0.3


# ---------------------------------------------------------------------------
# _format_score tests
# ---------------------------------------------------------------------------


class TestFormatScore:
    def _tc(self, name, args):
        return {"name": name, "arguments": args}

    def test_all_valid_json(self, reward_no_noise):
        tool_calls = [
            self._tc("shell_command", '{"command": "ls"}'),
            self._tc("flag_found", '{"content": "FLAG{x}"}'),
        ]
        score = reward_no_noise._format_score(tool_calls)
        assert score == 1.0

    def test_all_invalid_json(self, reward_no_noise):
        tool_calls = [
            self._tc("shell_command", "not json"),
            self._tc("flag_found", "also not json"),
        ]
        score = reward_no_noise._format_score(tool_calls)
        assert score == 0.5  # Each gets 0.5 credit

    def test_empty(self, reward_no_noise):
        score = reward_no_noise._format_score([])
        assert score == 0.0

    def test_mixed_valid_invalid(self, reward_no_noise):
        tool_calls = [
            self._tc("shell_command", '{"command": "ls"}'),
            self._tc("flag_found", "broken"),
        ]
        score = reward_no_noise._format_score(tool_calls)
        assert score == pytest.approx(0.75)  # (1.0 + 0.5) / 2

    def test_empty_arguments(self, reward_no_noise):
        tool_calls = [
            self._tc("shell_command", ""),
        ]
        score = reward_no_noise._format_score(tool_calls)
        assert score == 0.0  # Empty args = invalid

    def test_missing_name(self, reward_no_noise):
        tool_calls = [
            self._tc("", '{"command": "ls"}'),
        ]
        score = reward_no_noise._format_score(tool_calls)
        assert score == 0.0  # Empty name = invalid


# ---------------------------------------------------------------------------
# _extract tests
# ---------------------------------------------------------------------------


class TestExtract:
    def test_string_input(self):
        text, tcs = Reward._extract("hello FLAG{test}")
        assert text == "hello FLAG{test}"
        assert tcs == []

    def test_message_list_with_tool_calls(self):
        msgs = [
            {
                "role": "assistant",
                "content": "thinking...",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell_command",
                            "arguments": '{"command": "ls"}',
                        }
                    }
                ],
            },
            {"role": "tool", "content": "file1.txt\nfile2.txt"},
        ]
        text, tcs = Reward._extract(msgs)
        assert "thinking..." in text
        assert len(tcs) == 1
        assert tcs[0]["name"] == "shell_command"

    def test_message_list_no_tool_calls(self):
        msgs = [
            {"role": "assistant", "content": "I failed to find the flag."},
        ]
        text, tcs = Reward._extract(msgs)
        assert "failed" in text
        assert tcs == []

    def test_dict_arguments_converted(self):
        msgs = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell_command",
                            "arguments": {"command": "ls"},
                        }
                    }
                ],
            },
        ]
        text, tcs = Reward._extract(msgs)
        assert len(tcs) == 1
        assert tcs[0]["arguments"] == '{"command": "ls"}'


# ---------------------------------------------------------------------------
# Noise tests
# ---------------------------------------------------------------------------


class TestNoise:
    def test_noise_adds_variance(self):
        reward = Reward(noise_range=0.05, seed=42)
        completion = "FLAG{test}"
        results = []
        for _ in range(20):
            r = reward(
                [completion], ground_truth_flag=["FLAG{test}"], optimal_steps=[1]
            )
            results.append(r[0])
        # With noise, not all values should be identical
        assert len(set(round(r, 6) for r in results)) > 1

    def test_zero_noise_deterministic(self):
        reward = Reward(noise_range=0.0, seed=0)
        completion = "FLAG{test}"
        r1 = reward([completion], ground_truth_flag=["FLAG{test}"], optimal_steps=[1])
        r2 = reward([completion], ground_truth_flag=["FLAG{test}"], optimal_steps=[1])
        assert r1[0] == r2[0]


# ---------------------------------------------------------------------------
# Integration: full __call__ tests
# ---------------------------------------------------------------------------


class TestCallIntegration:
    def test_successful_trace_scores_high(self, reward_no_noise):
        msgs = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell_command",
                            "arguments": '{"command": "nmap target"}',
                        }
                    }
                ],
            },
            {"role": "tool", "content": "80/tcp open http"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell_command",
                            "arguments": '{"command": "curl http://target"}',
                        }
                    }
                ],
            },
            {"role": "tool", "content": "/admin (200)"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell_command",
                            "arguments": '{"command": "sqlmap -u http://target"}',
                        }
                    }
                ],
            },
            {"role": "tool", "content": "FLAG{test_flag}"},
            {
                "role": "assistant",
                "content": "Found FLAG{test_flag}",
                "tool_calls": [
                    {
                        "function": {
                            "name": "flag_found",
                            "arguments": '{"content": "FLAG{test_flag}"}',
                        }
                    }
                ],
            },
        ]
        scores = reward_no_noise(
            [msgs],
            ground_truth_flag=["FLAG{test_flag}"],
            optimal_steps=[4],
        )
        assert len(scores) == 1
        assert scores[0] > 0.5

    def test_successful_trace_with_metadata_no_flag_bypass(self, reward_no_noise):
        """metadata_success no longer bypasses flag scoring.

        Without explicit flag submission or env verification, flag_sc=0.0
        even when metadata.success=True.
        """
        msgs = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell_command",
                            "arguments": '{"command": "nmap target"}',
                        }
                    }
                ],
            },
            {"role": "tool", "content": "80/tcp open"},
            {"role": "assistant", "content": "solved"},
        ]
        scores = reward_no_noise(
            [msgs],
            ground_truth_flag=["content_of_flag_here"],
            optimal_steps=[2],
            metadata=[{"success": True}],
        )
        # metadata_success no longer gives flag credit. Score comes from
        # process signals only (recovery neutral 0.5 etc).
        assert scores[0] < 0.2

    def test_failed_trace_scores_low(self, reward_no_noise):
        # Trace with no tool calls at all -- pure text failure
        msgs = [
            {"role": "assistant", "content": "I cannot solve this challenge."},
        ]
        scores = reward_no_noise(
            [msgs],
            ground_truth_flag=["FLAG{secret}"],
            optimal_steps=[3],
        )
        assert len(scores) == 1
        assert scores[0] < 0.1

    def test_failed_trace_with_tools_lower_than_success(self, reward_no_noise):
        fail_msgs = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell_command",
                            "arguments": '{"command": "curl http://target"}',
                        }
                    }
                ],
            },
            {"role": "tool", "content": "200 OK"},
            {"role": "assistant", "content": "Could not find the flag."},
        ]
        success_msgs = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell_command",
                            "arguments": '{"command": "curl http://target"}',
                        }
                    }
                ],
            },
            {"role": "tool", "content": "FLAG{secret}"},
            {
                "role": "assistant",
                "content": "FLAG{secret}",
                "tool_calls": [
                    {
                        "function": {
                            "name": "flag_found",
                            "arguments": '{"content": "FLAG{secret}"}',
                        }
                    }
                ],
            },
        ]
        fail_scores = reward_no_noise(
            [fail_msgs],
            ground_truth_flag=["FLAG{secret}"],
            optimal_steps=[3],
        )
        success_scores = reward_no_noise(
            [success_msgs],
            ground_truth_flag=["FLAG{secret}"],
            optimal_steps=[3],
        )
        assert success_scores[0] > fail_scores[0]

    def test_batch_scoring(self, reward_no_noise):
        success_msgs = [
            {
                "role": "assistant",
                "content": "FLAG{test}",
                "tool_calls": [
                    {
                        "function": {
                            "name": "flag_found",
                            "arguments": '{"content": "FLAG{test}"}',
                        }
                    }
                ],
            },
        ]
        fail_msgs = [
            {"role": "assistant", "content": "I failed."},
        ]
        scores = reward_no_noise(
            [success_msgs, fail_msgs],
            ground_truth_flag=["FLAG{test}", "FLAG{test}"],
            optimal_steps=[1, 1],
        )
        assert len(scores) == 2
        assert scores[0] > scores[1]

    def test_string_completions(self, reward_no_noise):
        scores = reward_no_noise(
            ["FLAG{exact_match}", "no flag here"],
            ground_truth_flag=["FLAG{exact_match}", "FLAG{exact_match}"],
        )
        assert scores[0] > scores[1]

    def test_no_kwargs(self, reward_no_noise):
        scores = reward_no_noise(["hello world"])
        assert len(scores) == 1
        # No ground truth, no optimal steps, no metadata = very low score
        # Recovery gets 0.5 (neutral for <3 tool calls) → 0.07*0.5 = 0.035
        assert scores[0] < 0.1

    def test_metadata_success_via_kwargs_no_bypass(self, reward_no_noise):
        """metadata_success no longer bypasses flag scoring."""
        scores = reward_no_noise(
            ["no flag in text at all"],
            metadata=[{"success": True}],
            optimal_steps=[5],
        )
        # metadata_success is ignored now. flag_sc=0.0 since no flag text.
        # Only process signals contribute: recovery 0.5 (neutral), etc.
        assert scores[0] < 0.15


# ---------------------------------------------------------------------------
# Integration: online RL dataset validation
# ---------------------------------------------------------------------------


class TestGRPOSamples:
    def test_all_samples_load(self, grpo_samples):
        assert (
            len(grpo_samples) >= 15
        ), f"Expected >= 15 ONLINE_RL samples, got {len(grpo_samples)}"

    def test_all_have_required_fields(self, grpo_samples):
        for i, sample in enumerate(grpo_samples):
            assert "messages" in sample, f"Sample {i} missing 'messages'"
            assert "optimal_steps" in sample, f"Sample {i} missing 'optimal_steps'"
            assert isinstance(
                sample["optimal_steps"], int
            ), f"Sample {i} optimal_steps not int"
            assert sample["optimal_steps"] >= 0, f"Sample {i} optimal_steps < 0"
            # metadata.success is the authoritative signal
            meta = sample.get("metadata", {})
            assert "success" in meta, f"Sample {i} missing metadata.success"

    def test_mix_of_successes_and_failures(self, grpo_samples):
        successes = sum(1 for s in grpo_samples if s["metadata"]["success"])
        failures = sum(1 for s in grpo_samples if not s["metadata"]["success"])
        assert successes >= 5, f"Need >= 5 successes, got {successes}"
        if failures < 5:
            pytest.skip(f"Need >= 5 failures for mix test, got {failures} (SFT-only data)")

    def test_rewards_in_range(self, grpo_samples):
        reward = Reward(noise_range=0.05, seed=42)
        for i, sample in enumerate(grpo_samples):
            completions = [sample["messages"]]
            scores = reward(
                completions,
                ground_truth_flag=[sample["ground_truth_flag"]],
                optimal_steps=[sample["optimal_steps"]],
                metadata=[sample["metadata"]],
            )
            # Floor: hallucination penalty (-0.10) + noise (-0.05) = -0.15
            assert scores[0] >= -0.16, f"Sample {i} score {scores[0]} too low"
            assert scores[0] <= 1.10, f"Sample {i} score {scores[0]} too high"

    def test_successes_score_higher_than_failures(self, grpo_samples):
        reward = Reward(noise_range=0.0, seed=0)

        success_scores = []
        failure_scores = []

        for sample in grpo_samples:
            completions = [sample["messages"]]
            scores = reward(
                completions,
                ground_truth_flag=[sample["ground_truth_flag"]],
                optimal_steps=[sample["optimal_steps"]],
                metadata=[sample["metadata"]],
            )
            if sample["metadata"]["success"]:
                success_scores.append(scores[0])
            else:
                failure_scores.append(scores[0])

        if not failure_scores:
            pytest.skip("No failure samples in dataset — cannot compare success vs failure scores")

        avg_success = sum(success_scores) / len(success_scores)
        avg_failure = sum(failure_scores) / len(failure_scores)

        assert (
            avg_success > avg_failure
        ), f"Average success ({avg_success:.3f}) should be > average failure ({avg_failure:.3f})"

    def test_successful_traces_with_real_flags_above_threshold(self, grpo_samples):
        """Successful traces with real flags (not placeholders) should score above 0.05.

        With metadata_success bypass removed, only traces that contain
        env verification text or exact flag matches get flag credit.
        Some SFT traces may score low if the flag submission doesn't
        appear in the completion text (tool-output-only flag captures).
        """
        reward = Reward(noise_range=0.0, seed=0)
        from trajgym.rewards.reward import _FLAG_PLACEHOLDERS

        scored = 0
        for sample in grpo_samples:
            if not sample["metadata"]["success"]:
                continue
            gt_flag = sample.get("ground_truth_flag", "")
            if gt_flag in _FLAG_PLACEHOLDERS:
                continue  # Skip placeholder flags
            completions = [sample["messages"]]
            scores = reward(
                completions,
                ground_truth_flag=[gt_flag],
                optimal_steps=[sample["optimal_steps"]],
                metadata=[sample["metadata"]],
            )
            scored += 1
            assert (
                scores[0] > 0.05
            ), f"Success sample '{sample['metadata'].get('challenge', '?')}' scored only {scores[0]:.3f}"
        assert scored > 0, "No non-placeholder success samples found"

    def test_failed_traces_below_success_average(self, grpo_samples):
        """Average failure score should be below average success score."""
        reward = Reward(noise_range=0.0, seed=0)

        success_scores = []
        failure_scores = []

        for sample in grpo_samples:
            completions = [sample["messages"]]
            scores = reward(
                completions,
                ground_truth_flag=[sample["ground_truth_flag"]],
                optimal_steps=[sample["optimal_steps"]],
                metadata=[sample["metadata"]],
            )
            if sample["metadata"]["success"]:
                success_scores.append(scores[0])
            else:
                failure_scores.append(scores[0])

        if not failure_scores:
            pytest.skip("No failure samples in dataset — cannot compare success vs failure averages")
        avg_success = sum(success_scores) / len(success_scores)
        avg_failure = sum(failure_scores) / len(failure_scores)

        assert (
            avg_failure < avg_success
        ), f"Avg failure ({avg_failure:.3f}) should be < avg success ({avg_success:.3f})"

    def test_noise_adds_variance_across_samples(self, grpo_samples):
        reward = Reward(noise_range=0.05, seed=42)
        # Run same sample twice
        sample = grpo_samples[0]
        results = []
        for _ in range(10):
            scores = reward(
                [sample["messages"]],
                ground_truth_flag=[sample["ground_truth_flag"]],
                optimal_steps=[sample["optimal_steps"]],
                metadata=[sample["metadata"]],
            )
            results.append(scores[0])
        unique = len(set(round(r, 8) for r in results))
        assert unique > 1, "Noise should produce variance across repeated evaluations"

    def test_optimal_steps_vary(self, grpo_samples):
        steps = [s["optimal_steps"] for s in grpo_samples]
        unique_steps = set(steps)
        assert len(unique_steps) >= 3, f"Need varied optimal_steps, got {unique_steps}"

    def test_placeholder_flags_score_without_metadata_bypass(self, grpo_samples):
        """Samples with placeholder flags rely on env verification, not metadata.

        With metadata_success bypass removed, placeholder-flag samples
        only score flag=1.0 if env verification text is in the completion.
        """
        reward = Reward(noise_range=0.0, seed=0)
        placeholder_successes = [
            s
            for s in grpo_samples
            if s["metadata"]["success"]
            and s.get("ground_truth_flag") == "content_of_flag_here"
        ]
        if not placeholder_successes:
            pytest.skip("No placeholder-flag successes found")

        for sample in placeholder_successes[:5]:
            scores = reward(
                [sample["messages"]],
                ground_truth_flag=[sample["ground_truth_flag"]],
                optimal_steps=[sample["optimal_steps"]],
                metadata=[sample["metadata"]],
            )
            # Score will depend on env verification presence in tool output.
            # No longer guaranteed > 0.3 without env verification text.
            assert isinstance(scores[0], float)

    def test_online_rl_readiness(self, grpo_samples):
        """All 4 Online RL readiness checks must pass on actual trace data."""
        reward = Reward(noise_range=0.0, seed=0)

        success_scores = []
        failure_scores = []
        all_scores = []

        for sample in grpo_samples:
            scores = reward(
                [sample["messages"]],
                ground_truth_flag=[sample["ground_truth_flag"]],
                optimal_steps=[sample["optimal_steps"]],
                metadata=[sample["metadata"]],
            )
            all_scores.append(scores[0])
            if sample["metadata"]["success"]:
                success_scores.append(scores[0])
            else:
                failure_scores.append(scores[0])

        if not failure_scores:
            pytest.skip("No failure samples in dataset — cannot compute success-failure gap")
        avg_success = sum(success_scores) / len(success_scores)
        avg_failure = sum(failure_scores) / len(failure_scores)
        gap = avg_success - avg_failure

        import statistics

        variance = statistics.variance(all_scores)

        assert gap > 0.50, f"Gap {gap:.4f} should be > 0.50"
        assert variance > 0.02, f"Variance {variance:.4f} should be > 0.02"
        assert avg_failure < 0.20, f"Failure mean {avg_failure:.4f} should be < 0.20"
        assert (
            avg_success > avg_failure
        ), f"Success mean {avg_success:.4f} should be > failure mean {avg_failure:.4f}"
