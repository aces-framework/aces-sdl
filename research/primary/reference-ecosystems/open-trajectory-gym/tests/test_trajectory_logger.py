"""Tests for TrajectoryLogger and Reward.compute_with_breakdown.

Validates:
- TrajectoryLogger writes valid JSONL per generation
- Step summaries aggregate correctly
- Challenge scoreboard accumulates results
- compute_with_breakdown returns correct structure
- Logging is opt-out (disabled mode)
- Thread safety (concurrent writes)
"""

import json
import os
import threading

from trajgym.rewards.reward import Reward
from trajgym.training.online_rl.trajectory_logger import TrajectoryLogger

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
                "name": t["name"],
            }
        )
    msgs.append({"role": "assistant", "content": text})
    return msgs


# ---------------------------------------------------------------------------
# TrajectoryLogger: basic operation
# ---------------------------------------------------------------------------


class TestTrajectoryLoggerBasic:
    """Basic TrajectoryLogger functionality."""

    def test_log_generation_creates_jsonl(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path))
        tl.log_generation(
            global_step=1,
            generation_idx=0,
            challenge_id="test_challenge",
            reward_total=0.42,
            flag_found=False,
        )

        filepath = tmp_path / "trajectories" / "step_1.jsonl"
        assert filepath.exists()

        with open(filepath) as f:
            lines = f.readlines()
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["global_step"] == 1
        assert entry["generation_idx"] == 0
        assert entry["challenge_id"] == "test_challenge"
        assert entry["reward_total"] == 0.42
        assert entry["flag_found"] is False
        assert "timestamp" in entry

    def test_log_generation_appends_to_same_step(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path))
        for idx in range(4):
            tl.log_generation(
                global_step=5,
                generation_idx=idx,
                challenge_id=f"challenge_{idx}",
                reward_total=0.1 * idx,
            )

        filepath = tmp_path / "trajectories" / "step_5.jsonl"
        with open(filepath) as f:
            lines = f.readlines()
        assert len(lines) == 4

        entries = [json.loads(line) for line in lines]
        assert [e["generation_idx"] for e in entries] == [0, 1, 2, 3]

    def test_log_generation_with_full_data(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path))
        tl.log_generation(
            global_step=10,
            generation_idx=2,
            challenge_id="forensics_urgent",
            category="forensics",
            difficulty="Medium",
            target="http://localhost:32769",
            prompt_messages=[{"role": "system", "content": "You are a CTF agent."}],
            model_output="Let me analyze this...",
            tool_calls=[
                {
                    "name": "shell_command",
                    "args": {"command": "ls"},
                    "output": "flag.txt",
                }
            ],
            reward_total=0.36,
            reward_breakdown={"flag": 0.0, "format": 0.15, "efficiency": 0.08},
            flag_found=False,
            flag_submitted=None,
            ground_truth_flag="FLAG{test}",
            response_length=3516,
            num_tool_calls=5,
        )

        filepath = tmp_path / "trajectories" / "step_10.jsonl"
        entry = json.loads(filepath.read_text().strip())
        assert entry["category"] == "forensics"
        assert entry["difficulty"] == "Medium"
        assert entry["target"] == "http://localhost:32769"
        assert entry["reward_breakdown"]["flag"] == 0.0
        assert entry["response_length"] == 3516

    def test_log_generation_disabled(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path), enabled=False)
        tl.log_generation(global_step=1, reward_total=0.5)

        trajectories_dir = tmp_path / "trajectories"
        assert not trajectories_dir.exists()

    def test_log_generation_truncates_long_output(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path))
        long_text = "x" * 100000
        tl.log_generation(
            global_step=1,
            model_output=long_text,
        )

        filepath = tmp_path / "trajectories" / "step_1.jsonl"
        entry = json.loads(filepath.read_text().strip())
        assert len(entry["model_output"]) < 100000
        assert "truncated" in entry["model_output"]


# ---------------------------------------------------------------------------
# TrajectoryLogger: step summaries
# ---------------------------------------------------------------------------


class TestTrajectoryLoggerStepSummary:
    """Step summary logging."""

    def test_log_step_summary(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path))
        tl.log_step_summary(
            global_step=5,
            rewards=[0.1, 0.3, 0.5, 0.0],
            flag_found_count=1,
            total_generations=4,
            avg_tool_calls=8.5,
            avg_response_length=2500.0,
            challenge_ids=["c1", "c2", "c1", "c3"],
        )

        filepath = tmp_path / "trajectories" / "step_summaries.jsonl"
        assert filepath.exists()

        entry = json.loads(filepath.read_text().strip())
        assert entry["global_step"] == 5
        assert entry["total_generations"] == 4
        assert entry["flag_found_count"] == 1
        assert entry["flag_found_rate"] == 0.25
        assert abs(entry["avg_reward"] - 0.225) < 1e-6
        assert entry["min_reward"] == 0.0
        assert entry["max_reward"] == 0.5
        assert entry["reward_std"] > 0
        assert entry["unique_challenges"] == 3

    def test_log_step_summary_empty_rewards(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path))
        tl.log_step_summary(global_step=1, rewards=[])

        filepath = tmp_path / "trajectories" / "step_summaries.jsonl"
        entry = json.loads(filepath.read_text().strip())
        assert entry["avg_reward"] == 0.0
        assert entry["reward_std"] == 0.0


# ---------------------------------------------------------------------------
# TrajectoryLogger: challenge scoreboard
# ---------------------------------------------------------------------------


class TestTrajectoryLoggerScoreboard:
    """Challenge scoreboard accumulation and persistence."""

    def test_log_challenge_result_and_save(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path))

        tl.log_challenge_result("c1", "web", "easy", 0.8, True)
        tl.log_challenge_result("c1", "web", "easy", 0.2, False)
        tl.log_challenge_result("c2", "crypto", "hard", 0.0, False)
        tl.log_challenge_result("c2", "crypto", "hard", 1.0, True)
        tl.log_challenge_result("c2", "crypto", "hard", 0.5, False)

        path = tl.save_scoreboard()
        assert path is not None
        assert os.path.exists(path)

        with open(path) as f:
            scoreboard = json.load(f)

        assert "c1" in scoreboard
        assert "c2" in scoreboard

        c1 = scoreboard["c1"]
        assert c1["attempts"] == 2
        assert c1["solves"] == 1
        assert c1["solve_rate"] == 0.5
        assert abs(c1["avg_reward"] - 0.5) < 1e-6
        assert c1["best_reward"] == 0.8
        assert c1["category"] == "web"

        c2 = scoreboard["c2"]
        assert c2["attempts"] == 3
        assert c2["solves"] == 1
        assert abs(c2["solve_rate"] - 1 / 3) < 1e-6
        assert c2["best_reward"] == 1.0

    def test_save_scoreboard_empty(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path))
        path = tl.save_scoreboard()
        assert path is None

    def test_get_scoreboard(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path))
        tl.log_challenge_result("c1", "web", "easy", 0.5, True)
        tl.log_challenge_result("c1", "web", "easy", 0.3, False)

        sb = tl.get_scoreboard()
        assert "c1" in sb
        assert sb["c1"]["attempts"] == 2
        assert sb["c1"]["solves"] == 1

    def test_log_challenge_result_disabled(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path), enabled=False)
        tl.log_challenge_result("c1", "web", "easy", 0.5, True)
        assert tl.save_scoreboard() is None


# ---------------------------------------------------------------------------
# TrajectoryLogger: thread safety
# ---------------------------------------------------------------------------


class TestTrajectoryLoggerThreadSafety:
    """Concurrent writes from multiple threads."""

    def test_concurrent_log_generation(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path))
        errors = []

        def write_entries(start_idx, count):
            try:
                for i in range(count):
                    tl.log_generation(
                        global_step=1,
                        generation_idx=start_idx + i,
                        challenge_id=f"challenge_{start_idx}",
                        reward_total=0.1 * i,
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=write_entries, args=(i * 10, 10)) for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"

        filepath = tmp_path / "trajectories" / "step_1.jsonl"
        with open(filepath) as f:
            lines = f.readlines()
        assert len(lines) == 50

        # Verify all entries are valid JSON
        for line in lines:
            entry = json.loads(line)
            assert "global_step" in entry

    def test_concurrent_scoreboard_updates(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path))
        errors = []

        def update_scoreboard(cid, count):
            try:
                for i in range(count):
                    tl.log_challenge_result(cid, "web", "easy", 0.1 * i, i % 3 == 0)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=update_scoreboard, args=(f"c{i}", 20))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        sb = tl.get_scoreboard()
        assert len(sb) == 5
        for _cid, data in sb.items():
            assert data["attempts"] == 20


# ---------------------------------------------------------------------------
# Reward.compute_with_breakdown
# ---------------------------------------------------------------------------


class TestComputeWithBreakdown:
    """Verify compute_with_breakdown returns correct structure."""

    def test_returns_tuple_list(self):
        reward = Reward(seed=42)
        completions = [
            _completion_with_tools(
                [
                    _shell("nmap -sV target"),
                    _shell("curl target/"),
                    _shell("python3 exploit.py"),
                ],
                text="Let me scan and exploit this target",
            ),
        ]
        results = reward.compute_with_breakdown(
            completions,
            ground_truth_flag=["FLAG{test}"],
            optimal_steps=[5],
        )

        assert len(results) == 1
        score, breakdown = results[0]
        assert isinstance(score, float)
        assert isinstance(breakdown, dict)

    def test_breakdown_has_all_signals(self):
        reward = Reward(seed=42)
        completions = [
            _completion_with_tools(
                [
                    _shell("nmap target"),
                    _shell("curl target/"),
                    _shell("python3 exploit.py"),
                ],
                text="Scanning the target then exploiting the vulnerability I found",
            ),
        ]
        results = reward.compute_with_breakdown(completions)

        _, breakdown = results[0]
        expected_raw = {
            "flag",
            "efficiency",
            "progression",
            "exploration",
            "uniqueness",
            "format",
            "recovery",
            "cognitive",
            "hallucination",
        }
        expected_weighted = {f"{s}_weighted" for s in expected_raw}
        expected_keys = expected_raw | expected_weighted | {"noise"}

        assert set(breakdown.keys()) == expected_keys

    def test_breakdown_values_are_floats(self):
        reward = Reward(seed=42)
        completions = [
            _completion_with_tools(
                [_shell("ls"), _shell("cat flag.txt")],
                text="Let me check the filesystem",
            ),
        ]
        results = reward.compute_with_breakdown(completions)
        _, breakdown = results[0]

        for key, value in breakdown.items():
            assert isinstance(value, (int, float)), f"{key} is {type(value)}"

    def test_score_matches_call(self):
        """compute_with_breakdown and __call__ should return the same score."""
        reward = Reward(seed=42, noise_range=0.0)  # Zero noise for comparison
        completions = [
            _completion_with_tools(
                [_shell("nmap target"), _shell("curl target/")],
                text="Running reconnaissance against the target system",
            ),
        ]
        kwargs = {"ground_truth_flag": ["FLAG{x}"], "optimal_steps": [3]}

        scores = reward(completions, **kwargs)

        reward2 = Reward(seed=42, noise_range=0.0)
        results = reward2.compute_with_breakdown(completions, **kwargs)

        assert abs(scores[0] - results[0][0]) < 1e-6

    def test_flag_found_breakdown(self):
        """When flag is found, the flag signal should be 1.0."""
        reward = Reward(seed=42)
        text = "Found the flag: Correct! Flag verified: FLAG{test}"
        completions = [
            _completion_with_tools(
                [
                    _shell("nmap target"),
                    _shell("curl target/"),
                    _tc("flag_found", {"content": "FLAG{test}"}),
                ],
                text=text,
            ),
        ]
        results = reward.compute_with_breakdown(
            completions,
            ground_truth_flag=["FLAG{test}"],
        )
        _, breakdown = results[0]
        assert breakdown["flag"] == 1.0

    def test_multiple_completions(self):
        reward = Reward(seed=42)
        completions = [
            _completion_with_tools([_shell("ls")], text="listing files"),
            _completion_with_tools(
                [_shell("nmap target"), _shell("curl target/")],
                text="scanning and enumerating",
            ),
        ]
        results = reward.compute_with_breakdown(completions)
        assert len(results) == 2
        for score, breakdown in results:
            assert isinstance(score, float)
            assert isinstance(breakdown, dict)


# ---------------------------------------------------------------------------
# Integration: TrajectoryLogger + Reward breakdown
# ---------------------------------------------------------------------------


class TestTrajectoryLoggerRewardIntegration:
    """Verify that reward breakdowns can be logged through TrajectoryLogger."""

    def test_log_reward_breakdown(self, tmp_path):
        tl = TrajectoryLogger(str(tmp_path))
        reward = Reward(seed=42)

        completions = [
            _completion_with_tools(
                [_shell("nmap target"), _shell("curl target/")],
                text="Scanning the target for vulnerabilities",
            ),
        ]
        results = reward.compute_with_breakdown(completions)
        score, breakdown = results[0]

        tl.log_generation(
            global_step=1,
            generation_idx=0,
            challenge_id="test",
            reward_total=score,
            reward_breakdown=breakdown,
            flag_found=False,
            num_tool_calls=2,
        )

        filepath = tmp_path / "trajectories" / "step_1.jsonl"
        entry = json.loads(filepath.read_text().strip())
        assert entry["reward_breakdown"] is not None
        assert "flag" in entry["reward_breakdown"]
        assert "flag_weighted" in entry["reward_breakdown"]
        assert abs(entry["reward_total"] - score) < 1e-6
