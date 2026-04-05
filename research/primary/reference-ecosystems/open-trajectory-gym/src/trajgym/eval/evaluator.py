"""Model evaluation harness for CTF challenges.

Runs a model (base or fine-tuned) against a set of challenges using BoxPwnr's
Solver, collects per-challenge statistics, and produces a JSON report plus a
human-readable markdown summary table.

Usage (programmatic):
    from trajgym.eval import ModelEvaluator
    ev = ModelEvaluator(model="ollama/nanbeige4.1-3b")
    report = ev.run_all()
    ev.save(report, "outputs/eval")

See also ``trajgym.cli.evaluate`` for the CLI wrapper.
"""

import importlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).resolve().parent.parent  # src/trajgym/
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent  # repo root


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------


@dataclass
class ChallengeResult:
    """Result for a single challenge attempt."""

    challenge_id: str
    platform: str
    vuln_type: str
    difficulty: str
    solved: bool
    turns: int
    elapsed_seconds: float
    error: str | None = None


@dataclass
class EvalReport:
    """Aggregate evaluation report."""

    model: str
    strategy: str
    timestamp: str
    total_challenges: int
    solved: int
    solve_rate: float
    avg_turns: float
    avg_time_seconds: float
    results: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class ModelEvaluator:
    """Run BoxPwnr solver across a challenge set and collect metrics.

    Args:
        model: LLM model identifier (e.g. ``ollama/nanbeige4.1-3b``).
        challenges_yaml: Path to YAML file listing challenges.
        platform: Default platform for challenges (overridden per-challenge).
        strategy: BoxPwnr strategy name (``chat_tools`` or ``chat``).
        max_turns: Maximum conversation turns per challenge.
        max_time: Maximum time in minutes per challenge.
        traces_dir: Directory for BoxPwnr trace output.
        reasoning_effort: Reasoning effort level for supported models.
        attempts: Number of attempts per challenge.
    """

    def __init__(
        self,
        model: str = "openrouter/openai/gpt-oss-120b",
        challenges_yaml: str = str(
            _PROJECT_ROOT / "configs" / "challenges" / "eval_default.yaml"
        ),
        platform: str = "xbow",
        strategy: str = "chat_tools",
        max_turns: int = 50,
        max_time: int = 30,
        traces_dir: str = "./targets",
        reasoning_effort: str = "medium",
        attempts: int = 1,
        agent: str = "boxpwnr",
        challenge_registry: str | None = None,
        target_map: str | None = None,
        host: str = "localhost",
    ) -> None:
        self.model = model
        self.challenges_yaml = challenges_yaml
        self.platform = platform
        self.strategy = strategy
        self.max_turns = max_turns
        self.max_time = max_time
        self.traces_dir = traces_dir
        self.reasoning_effort = reasoning_effort
        self.attempts = attempts
        self.agent = agent
        self.challenge_registry = challenge_registry
        self.target_map = target_map
        self.host = host

    # ------------------------------------------------------------------
    # Challenge loading
    # ------------------------------------------------------------------

    def load_challenges(self) -> list[dict[str, Any]]:
        """Load challenge list from YAML config.

        Returns:
            List of challenge dicts with keys: id, platform, vuln_type, difficulty.
        """
        yaml_path = Path(self.challenges_yaml)
        if not yaml_path.is_absolute():
            yaml_path = _PACKAGE_DIR / yaml_path

        if not yaml_path.exists():
            raise FileNotFoundError(f"Challenges config not found: {yaml_path}")

        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}

        challenges = data.get("challenges", [])
        if not challenges:
            raise ValueError(f"No challenges found in {yaml_path}")

        logger.info("Loaded %d challenges from %s", len(challenges), yaml_path)
        return challenges

    # ------------------------------------------------------------------
    # Single challenge run
    # ------------------------------------------------------------------

    def run_challenge(self, challenge: dict[str, Any]) -> ChallengeResult:
        """Run a single challenge and return the result.

        Args:
            challenge: Dict with at least ``id``. Optional: ``platform``,
                ``vuln_type``, ``difficulty``.

        Returns:
            ChallengeResult with solve status, turns, and timing.
        """
        cid = challenge["id"]
        platform = challenge.get("platform", self.platform)
        vuln_type = challenge.get("vuln_type", "unknown")
        difficulty = challenge.get("difficulty", "unknown")

        logger.info("Running challenge %s (%s, %s)", cid, vuln_type, difficulty)

        start = time.time()
        solved = False
        turns = 0
        error_msg = None

        try:
            if str(self.agent).strip().lower() == "boxpwnr":
                from trajgym.integrations.boxpwnr_runner import AgentRunner

                runner = AgentRunner(
                    platform=platform,
                    model=self.model,
                    strategy=self.strategy,
                    max_turns=self.max_turns,
                    max_time=self.max_time,
                    traces_dir=self.traces_dir,
                    reasoning_effort=self.reasoning_effort,
                    attempts=self.attempts,
                )
                runner.run(target=cid)
                # Check trace output for success
                solved, turns = self._parse_trace(cid, platform)
            else:
                solved, turns = self._run_with_custom_agent(challenge, platform)
        except Exception as e:
            error_msg = str(e)
            logger.warning("Challenge %s failed: %s", cid, error_msg)

        elapsed = time.time() - start

        return ChallengeResult(
            challenge_id=cid,
            platform=platform,
            vuln_type=vuln_type,
            difficulty=difficulty,
            solved=solved,
            turns=turns,
            elapsed_seconds=round(elapsed, 1),
            error=error_msg,
        )

    def _run_with_custom_agent(
        self,
        challenge: dict[str, Any],
        platform: str,
    ) -> tuple[bool, int]:
        """Run evaluation with a custom Agent implementation."""
        from trajgym.agent.protocol import Agent

        agent_spec = str(self.agent or "").strip()
        if agent_spec.lower().startswith("custom:"):
            agent_spec = agent_spec.split(":", 1)[1].strip()
        if not agent_spec:
            raise ValueError("Custom agent spec is empty")

        module_name, _, class_name = agent_spec.rpartition(".")
        if not module_name or not class_name:
            raise ValueError(
                f"Invalid --agent value {self.agent!r}. "
                "Use 'boxpwnr' or 'custom:module.ClassName'."
            )

        module = importlib.import_module(module_name)
        agent_cls = getattr(module, class_name)
        agent = agent_cls(
            model=self.model,
            platform=platform,
            strategy=self.strategy,
            traces_dir=self.traces_dir,
            reasoning_effort=self.reasoning_effort,
            attempts=self.attempts,
        )
        if not isinstance(agent, Agent):
            raise TypeError(
                f"Resolved agent {agent_spec} does not satisfy Agent protocol"
            )

        cid = challenge["id"]
        target = (
            challenge.get("target")
            or challenge.get("target_url")
            or challenge.get("url")
            or cid
        )
        result = agent.solve(
            challenge=cid,
            target=str(target),
            max_steps=self.max_turns,
            timeout=max(1, int(self.max_time)) * 60,
        )
        solved = bool(getattr(result, "success", False))
        turns = int(getattr(result, "steps", 0) or 0)
        return solved, turns

    # ------------------------------------------------------------------
    # Batch run
    # ------------------------------------------------------------------

    def run_all(self) -> EvalReport:
        """Run all challenges and produce an evaluation report.

        Returns:
            EvalReport with aggregate statistics and per-challenge results.
        """
        challenges = self.load_challenges()
        self._run_runtime_preflight(challenges)
        results: list[ChallengeResult] = []

        for challenge in challenges:
            result = self.run_challenge(challenge)
            results.append(result)
            status = "SOLVED" if result.solved else "FAILED"
            logger.info(
                "  %s %s (turns=%d, time=%.1fs)",
                status,
                result.challenge_id,
                result.turns,
                result.elapsed_seconds,
            )

        solved_count = sum(1 for r in results if r.solved)
        total = len(results)
        avg_turns = sum(r.turns for r in results) / max(total, 1)
        avg_time = sum(r.elapsed_seconds for r in results) / max(total, 1)

        report = EvalReport(
            model=self.model,
            strategy=self.strategy,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            total_challenges=total,
            solved=solved_count,
            solve_rate=round(solved_count / max(total, 1), 4),
            avg_turns=round(avg_turns, 1),
            avg_time_seconds=round(avg_time, 1),
            results=[asdict(r) for r in results],
        )

        return report

    def _run_runtime_preflight(self, challenges: list[dict[str, Any]]) -> None:
        """Fail fast on registry/target/port/container mismatches for cybench runs."""
        cybench_ids = [
            str(challenge["id"])
            for challenge in challenges
            if str(challenge.get("platform", self.platform)).lower() == "cybench"
        ]
        if not cybench_ids:
            return

        registry_path = self.challenge_registry
        if not registry_path:
            default_registry = (
                Path(__file__).resolve().parents[3]
                / "configs"
                / "challenges"
                / "cybench.yaml"
            )
            if default_registry.exists():
                registry_path = str(default_registry)
        if not registry_path:
            raise ValueError(
                "Cybench evaluation requires a challenge registry "
                "(pass --challenge-registry)."
            )

        from trajgym.challenges.preflight import validate_runtime_preflight
        from trajgym.challenges.registry import ChallengeRegistry

        registry = ChallengeRegistry(str(registry_path))
        if self.target_map:
            registry.load_target_overrides(self.target_map, strict=False)
        validate_runtime_preflight(
            registry,
            host=self.host,
            challenge_ids=cybench_ids,
            require_reachable=True,
            strict_container_check=True,
        )

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def save(self, report: EvalReport, output_dir: str) -> None:
        """Save evaluation report as JSON and markdown.

        Args:
            report: EvalReport to save.
            output_dir: Directory to write report files.
        """
        os.makedirs(output_dir, exist_ok=True)

        # JSON
        json_path = os.path.join(output_dir, "eval_report.json")
        with open(json_path, "w") as f:
            json.dump(asdict(report), f, indent=2)
        logger.info("JSON report saved to %s", json_path)

        # Markdown
        md_path = os.path.join(output_dir, "eval_report.md")
        with open(md_path, "w") as f:
            f.write(self._format_markdown(report))
        logger.info("Markdown report saved to %s", md_path)

    @staticmethod
    def _format_markdown(report: EvalReport) -> str:
        """Format an EvalReport as a markdown table."""
        lines = [
            "# Evaluation Report",
            "",
            f"- **Model:** {report.model}",
            f"- **Strategy:** {report.strategy}",
            f"- **Timestamp:** {report.timestamp}",
            f"- **Challenges:** {report.total_challenges}",
            f"- **Solved:** {report.solved}/{report.total_challenges} "
            f"({report.solve_rate * 100:.1f}%)",
            f"- **Avg Turns:** {report.avg_turns}",
            f"- **Avg Time:** {report.avg_time_seconds}s",
            "",
            "## Per-Challenge Results",
            "",
            "| Challenge | Platform | Vuln Type | Difficulty | Solved | Turns | Time (s) | Error |",
            "|-----------|----------|-----------|------------|--------|-------|----------|-------|",
        ]

        for r in report.results:
            solved_str = "Yes" if r["solved"] else "No"
            error_str = r.get("error") or ""
            if len(error_str) > 40:
                error_str = error_str[:37] + "..."
            lines.append(
                f"| {r['challenge_id']} | {r['platform']} | {r['vuln_type']} "
                f"| {r['difficulty']} | {solved_str} | {r['turns']} "
                f"| {r['elapsed_seconds']} | {error_str} |"
            )

        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Trace parsing
    # ------------------------------------------------------------------

    def _parse_trace(self, challenge_id: str, platform: str) -> tuple:
        """Parse BoxPwnr trace directory for solve status and turn count.

        Returns:
            (solved: bool, turns: int)
        """
        trace_dir = Path(self.traces_dir) / platform / challenge_id
        if not trace_dir.exists():
            return False, 0

        # BoxPwnr writes a stats.json in the trace directory
        results_file = trace_dir / "stats.json"
        if results_file.exists():
            try:
                with open(results_file) as f:
                    data = json.load(f)
                solved = data.get("status") == "success"
                turns = data.get("total_turns", 0)
                return solved, turns
            except (json.JSONDecodeError, KeyError):
                pass

        # Fallback: scan for flag in conversation log
        conv_file = trace_dir / "conversation.json"
        if conv_file.exists():
            try:
                with open(conv_file) as f:
                    conv = json.load(f)
                turns = len([m for m in conv if m.get("role") == "assistant"])
                # Check if flag_found was called
                for msg in conv:
                    for tc in msg.get("tool_calls", []):
                        if tc.get("function", {}).get("name") == "flag_found":
                            return True, turns
            except (json.JSONDecodeError, KeyError):
                pass

        return False, 0


# ---------------------------------------------------------------------------
# Comparison helper
# ---------------------------------------------------------------------------


def compare_reports(
    base_path: str,
    tuned_path: str,
) -> str:
    """Compare two evaluation reports and produce a markdown diff table.

    Args:
        base_path: Path to base model eval_report.json.
        tuned_path: Path to fine-tuned model eval_report.json.

    Returns:
        Markdown string with comparison table.
    """
    with open(base_path) as f:
        base = json.load(f)
    with open(tuned_path) as f:
        tuned = json.load(f)

    lines = [
        "# Model Comparison",
        "",
        "| Metric | Base | Fine-Tuned | Delta |",
        "|--------|------|------------|-------|",
    ]

    for key, label in [
        ("solve_rate", "Solve Rate"),
        ("avg_turns", "Avg Turns"),
        ("avg_time_seconds", "Avg Time (s)"),
    ]:
        b = base.get(key, 0)
        t = tuned.get(key, 0)
        delta = t - b
        if key == "solve_rate":
            lines.append(
                f"| {label} | {b*100:.1f}% | {t*100:.1f}% | {delta*100:+.1f}% |"
            )
        else:
            lines.append(f"| {label} | {b:.1f} | {t:.1f} | {delta:+.1f} |")

    # Per-challenge comparison
    base_results = {r["challenge_id"]: r for r in base.get("results", [])}
    tuned_results = {r["challenge_id"]: r for r in tuned.get("results", [])}
    all_ids = sorted(set(base_results) | set(tuned_results))

    lines.extend(
        [
            "",
            "## Per-Challenge",
            "",
            "| Challenge | Base | Fine-Tuned |",
            "|-----------|------|------------|",
        ]
    )

    for cid in all_ids:
        b_solved = "Yes" if base_results.get(cid, {}).get("solved") else "No"
        t_solved = "Yes" if tuned_results.get(cid, {}).get("solved") else "No"
        lines.append(f"| {cid} | {b_solved} | {t_solved} |")

    lines.append("")
    return "\n".join(lines)
