#!/usr/bin/env python3
"""Open Trajectory Gym Evaluation CLI.

Run a model against the benchmark challenge suite and produce a report.

Usage:
    # Evaluate a model
    trajgym eval run \\
        --model ollama/nanbeige4.1-3b \\
        --output outputs/eval/base

    # Compare base vs fine-tuned
    trajgym eval compare \\
        --base outputs/eval/base/eval_report.json \\
        --tuned outputs/eval/finetuned/eval_report.json \\
        --output outputs/eval/comparison.md
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_CHALLENGES = (
    Path(__file__).resolve().parents[3] / "configs" / "challenges" / "eval_default.yaml"
)


def cmd_run(args: argparse.Namespace) -> None:
    """Run evaluation against all challenges."""
    from trajgym.eval.evaluator import ModelEvaluator

    ev = ModelEvaluator(
        model=args.model,
        challenges_yaml=args.challenges,
        platform=args.platform,
        strategy=args.strategy,
        max_turns=args.max_turns,
        max_time=args.max_time,
        traces_dir=args.traces_dir,
        reasoning_effort=args.reasoning_effort,
        attempts=args.attempts,
        agent=args.agent,
        challenge_registry=getattr(args, "challenge_registry", None),
        target_map=getattr(args, "target_map", None),
        host=getattr(args, "host", "localhost"),
    )

    report = ev.run_all()
    ev.save(report, args.output)

    print(
        f"\nSolve rate: {report.solved}/{report.total_challenges} "
        f"({report.solve_rate * 100:.1f}%)"
    )
    print(f"Avg turns:  {report.avg_turns}")
    print(f"Avg time:   {report.avg_time_seconds}s")
    print(f"\nReports saved to {args.output}/")


def cmd_compare(args: argparse.Namespace) -> None:
    """Compare two evaluation reports."""
    from trajgym.eval.evaluator import compare_reports

    md = compare_reports(args.base, args.tuned)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(md)
        print(f"Comparison saved to {args.output}")
    else:
        print(md)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open Trajectory Gym Model Evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command")

    # -- run (default) ---------------------------------------------------
    run_parser = subparsers.add_parser("run", help="Run evaluation")
    run_parser.add_argument("--model", "-m", required=True, help="LLM model identifier")
    run_parser.add_argument(
        "--output", "-o", required=True, help="Output directory for reports"
    )
    run_parser.add_argument(
        "--challenges",
        default=str(DEFAULT_CHALLENGES),
        help="Path to challenges YAML",
    )
    run_parser.add_argument(
        "--platform", default="xbow", help="Default platform (default: xbow)"
    )
    run_parser.add_argument(
        "--strategy", default="chat_tools", choices=["chat", "chat_tools"]
    )
    run_parser.add_argument("--max-turns", type=int, default=50)
    run_parser.add_argument(
        "--max-time", type=int, default=30, help="Max time per challenge (min)"
    )
    run_parser.add_argument("--traces-dir", default="./targets")
    run_parser.add_argument("--reasoning-effort", default="medium")
    run_parser.add_argument("--attempts", type=int, default=1)
    run_parser.add_argument(
        "--agent",
        default="boxpwnr",
        help="Agent to use: 'boxpwnr' (default) or 'custom:module.ClassName'",
    )
    run_parser.add_argument(
        "--challenge-registry",
        default=None,
        help="Challenge registry YAML for cybench runtime preflight.",
    )
    run_parser.add_argument(
        "--target-map",
        default=None,
        help="Optional challenge target override map for cybench preflight.",
    )
    run_parser.add_argument(
        "--host",
        default="localhost",
        help="Host used for registry target resolution in preflight.",
    )
    run_parser.set_defaults(func=cmd_run)

    # -- compare ---------------------------------------------------------
    cmp_parser = subparsers.add_parser("compare", help="Compare two reports")
    cmp_parser.add_argument(
        "--base", required=True, help="Path to base model eval_report.json"
    )
    cmp_parser.add_argument(
        "--tuned", required=True, help="Path to fine-tuned eval_report.json"
    )
    cmp_parser.add_argument("--output", "-o", default=None, help="Output markdown file")
    cmp_parser.set_defaults(func=cmd_compare)

    args = parser.parse_args()

    # Default to "run" if no subcommand and model is provided
    if args.command is None:
        if "--model" in sys.argv or "-m" in sys.argv:
            args = run_parser.parse_args(sys.argv[1:])
            args.func = cmd_run
        else:
            parser.print_help()
            sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
