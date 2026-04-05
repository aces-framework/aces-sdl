"""Tests for trajgym.cli.evaluate wiring."""

from __future__ import annotations

import types
from argparse import Namespace

import yaml


def test_cmd_run_forwards_agent_argument(monkeypatch, tmp_path):
    """`trajgym eval run --agent ...` should reach ModelEvaluator."""
    from trajgym.cli import evaluate as cli_evaluate

    captured = {}

    class StubEvaluator:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_all(self):
            return types.SimpleNamespace(
                solved=1,
                total_challenges=1,
                solve_rate=1.0,
                avg_turns=3.0,
                avg_time_seconds=2.5,
            )

        def save(self, report, output_dir):
            del report
            (tmp_path / "saved.txt").write_text(str(output_dir), encoding="utf-8")

    fake_mod = types.SimpleNamespace(ModelEvaluator=StubEvaluator)
    monkeypatch.setitem(__import__("sys").modules, "trajgym.eval.evaluator", fake_mod)

    args = Namespace(
        model="Nanbeige/Nanbeige4.1-3B",
        output=str(tmp_path / "out"),
        challenges="configs/challenges/cybench.yaml",
        platform="cybench",
        strategy="chat_tools",
        max_turns=20,
        max_time=10,
        traces_dir=str(tmp_path / "traces"),
        reasoning_effort="medium",
        attempts=1,
        agent="custom:demo_agent.MyAgent",
    )
    cli_evaluate.cmd_run(args)

    assert captured["agent"] == "custom:demo_agent.MyAgent"


def test_model_evaluator_custom_agent_path(tmp_path, monkeypatch):
    """ModelEvaluator should execute custom Agent paths in eval mode."""
    from trajgym.eval.evaluator import ModelEvaluator

    module_path = tmp_path / "demo_agent_mod.py"
    module_path.write_text(
        "from trajgym.agent.protocol import AgentResult\n"
        "class DemoAgent:\n"
        "    def __init__(self, **kwargs):\n"
        "        self.kwargs = kwargs\n"
        "    def solve(self, challenge, target, ground_truth_flag='', max_steps=30, timeout=300):\n"
        "        return AgentResult(success=True, flag='FLAG{demo}', steps=2)\n",
        encoding="utf-8",
    )

    config_path = tmp_path / "challenges.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "challenges": [
                    {
                        "id": "demo-challenge",
                        "platform": "cybench",
                        "vuln_type": "misc",
                        "difficulty": "very_easy",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    evaluator = ModelEvaluator(
        model="Nanbeige/Nanbeige4.1-3B",
        challenges_yaml=str(config_path),
        agent="custom:demo_agent_mod.DemoAgent",
        traces_dir=str(tmp_path / "traces"),
        max_turns=10,
        max_time=1,
    )

    result = evaluator.run_challenge(
        {
            "id": "demo-challenge",
            "platform": "cybench",
            "vuln_type": "misc",
            "difficulty": "very_easy",
            "target": "http://localhost:32805",
        }
    )
    assert result.solved is True
    assert result.turns == 2
