"""Smoke tests for DatasetSplitter.

Validates:
- SFT/online-RL split logic (success → SFT, all → online RL)
- Online RL records have ground_truth_flag cross-referenced
- Token length filtering for online RL
- Optimal steps computation (min across successful traces)
- Chat-command normalization during split
"""

import json
from pathlib import Path

import pytest
from trajgym.data.splitter import DatasetSplitter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_trace(
    platform: str,
    challenge: str,
    success: bool,
    flag: str | None = None,
    num_assistant_turns: int = 3,
    content_size: int = 100,
) -> dict:
    """Build a minimal converted trace record."""
    messages = [
        {"role": "system", "content": "System prompt."},
        {"role": "user", "content": "Solve the challenge."},
    ]
    for i in range(num_assistant_turns):
        messages.append(
            {
                "role": "assistant",
                "content": "x" * content_size,
                "tool_calls": [
                    {
                        "id": f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": "shell_command",
                            "arguments": json.dumps({"command": f"cmd_{i}"}),
                        },
                    }
                ],
            }
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "name": "shell_command",
                "content": f"output_{i}",
            }
        )

    return {
        "messages": messages,
        "metadata": {
            "source": "boxpwnr",
            "platform": platform,
            "challenge": challenge,
            "success": success,
        },
        "ground_truth_flag": flag,
        "optimal_steps": num_assistant_turns,
    }


@pytest.fixture
def input_jsonl(tmp_path) -> Path:
    """Create a JSONL input file with a mix of success/failure traces."""
    records = [
        _make_trace("cybench", "web-1", True, "FLAG{web1}", num_assistant_turns=5),
        _make_trace("cybench", "web-1", True, "FLAG{web1}", num_assistant_turns=3),
        _make_trace("cybench", "web-1", False, None, num_assistant_turns=8),
        _make_trace(
            "cybench", "crypto-1", True, "FLAG{crypto1}", num_assistant_turns=4
        ),
        _make_trace("cybench", "crypto-1", False, None, num_assistant_turns=10),
    ]

    path = tmp_path / "input.jsonl"
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


# ---------------------------------------------------------------------------
# Split tests
# ---------------------------------------------------------------------------


class TestDatasetSplitter:
    def test_sft_only_successes(self, input_jsonl, tmp_path):
        sft_path = str(tmp_path / "sft.jsonl")
        online_rl_path = str(tmp_path / "online_rl.jsonl")

        splitter = DatasetSplitter()
        stats = splitter.split(str(input_jsonl), sft_path, online_rl_path)

        # SFT should have only successful traces
        assert stats["sft_count"] == 3  # 3 successes

        with open(sft_path) as f:
            sft_records = [json.loads(line) for line in f if line.strip()]
        for r in sft_records:
            assert r["metadata"]["success"] is True

    def test_online_rl_has_all_traces(self, input_jsonl, tmp_path):
        sft_path = str(tmp_path / "sft.jsonl")
        online_rl_path = str(tmp_path / "online_rl.jsonl")

        splitter = DatasetSplitter()
        stats = splitter.split(str(input_jsonl), sft_path, online_rl_path)

        # Online RL should have all traces (within token limit)
        assert stats["online_rl_count"] == 5

    def test_online_rl_records_have_ground_truth_flag(self, input_jsonl, tmp_path):
        sft_path = str(tmp_path / "sft.jsonl")
        online_rl_path = str(tmp_path / "online_rl.jsonl")

        splitter = DatasetSplitter()
        splitter.split(str(input_jsonl), sft_path, online_rl_path)

        with open(online_rl_path) as f:
            online_rl_records = [json.loads(line) for line in f if line.strip()]

        # All online-RL records for challenges with successful siblings should
        # have ground_truth_flag cross-referenced
        for r in online_rl_records:
            assert (
                r.get("ground_truth_flag") is not None
            ), f"online-RL record for {r['metadata']['challenge']} missing ground_truth_flag"

    def test_token_filtering(self, tmp_path):
        """Records exceeding max_online_rl_tokens should be filtered out."""
        # Create a record with very large content
        large = _make_trace(
            "p", "c", True, "FLAG{x}", num_assistant_turns=3, content_size=200000
        )
        small = _make_trace(
            "p", "c", True, "FLAG{x}", num_assistant_turns=2, content_size=50
        )

        path = tmp_path / "input.jsonl"
        with open(path, "w") as f:
            f.write(json.dumps(large) + "\n")
            f.write(json.dumps(small) + "\n")

        sft_path = str(tmp_path / "sft.jsonl")
        online_rl_path = str(tmp_path / "online_rl.jsonl")

        splitter = DatasetSplitter(max_online_rl_tokens=1000)
        stats = splitter.split(str(path), sft_path, online_rl_path)

        # Large record filtered, small kept
        assert stats["online_rl_filtered"] >= 1
        assert stats["online_rl_count"] >= 1

    def test_optimal_steps_cross_referenced(self, input_jsonl, tmp_path):
        """optimal_steps should be min across successful traces per challenge."""
        sft_path = str(tmp_path / "sft.jsonl")
        online_rl_path = str(tmp_path / "online_rl.jsonl")

        splitter = DatasetSplitter()
        splitter.split(str(input_jsonl), sft_path, online_rl_path)

        with open(online_rl_path) as f:
            online_rl_records = [json.loads(line) for line in f if line.strip()]

        # For web-1: two successes with 5 and 3 assistant turns → optimal = 3
        web1_records = [
            r for r in online_rl_records if r["metadata"]["challenge"] == "web-1"
        ]
        for r in web1_records:
            assert (
                r["optimal_steps"] == 3
            ), f"Expected optimal_steps=3 for web-1, got {r['optimal_steps']}"

    def test_stats_summary(self, input_jsonl, tmp_path):
        sft_path = str(tmp_path / "sft.jsonl")
        online_rl_path = str(tmp_path / "online_rl.jsonl")

        splitter = DatasetSplitter()
        stats = splitter.split(str(input_jsonl), sft_path, online_rl_path)

        assert "total_input" in stats
        assert "sft_count" in stats
        assert "online_rl_count" in stats
        assert "online_rl_filtered" in stats
        assert "online_rl_missing_flag" in stats
        assert "avg_turns_online_rl" in stats
        assert "tool_distribution" in stats
        assert stats["total_input"] == 5


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


class TestTokenEstimation:
    def test_estimate_tokens_basic(self):
        messages = [
            {"role": "user", "content": "a" * 400},  # 100 tokens
        ]
        est = DatasetSplitter._estimate_tokens(messages)
        assert est == 100

    def test_estimate_includes_reasoning(self):
        messages = [
            {"role": "assistant", "content": "a" * 200, "reasoning_content": "b" * 200},
        ]
        est = DatasetSplitter._estimate_tokens(messages)
        assert est == 100  # (200 + 200) / 4

    def test_estimate_includes_tool_args(self):
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"arguments": "a" * 400}},
                ],
            },
        ]
        est = DatasetSplitter._estimate_tokens(messages)
        assert est == 100
