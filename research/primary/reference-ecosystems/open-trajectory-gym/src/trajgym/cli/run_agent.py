#!/usr/bin/env python3
"""Open Trajectory Gym Agent Runner (BoxPwnr-based).

Runs BoxPwnr's Solver against CTF challenges from the command line.

Usage:
    trajgym agent --platform xbow --target XBEN-003-24
    trajgym agent --platform xbow --target XBEN-003-24 --model ollama/nanbeige4.1-3b
    trajgym agent --check
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Run BoxPwnr agent against CTF challenges"
    )
    default_registry = (
        Path(__file__).resolve().parents[3] / "configs" / "challenges" / "cybench.yaml"
    )

    parser.add_argument(
        "--platform",
        "-p",
        default="xbow",
        choices=["xbow", "local", "htb", "portswigger", "cybench"],
        help="Target platform (default: xbow)",
    )
    parser.add_argument(
        "--target",
        "-t",
        help="Target identifier (e.g. XBEN-003-24 for xbow)",
    )
    parser.add_argument(
        "--challenge-registry",
        default=str(default_registry),
        help=f"Path to challenge registry YAML (default: {default_registry})",
    )
    parser.add_argument(
        "--target-map",
        default=None,
        help="Optional JSON/YAML challenge target override map.",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host used for registry target resolution checks (default: localhost).",
    )
    parser.add_argument(
        "--model",
        "-m",
        default="openrouter/openai/gpt-oss-120b",
        help="LLM model (default: openrouter/openai/gpt-oss-120b)",
    )
    parser.add_argument(
        "--strategy",
        "-s",
        default="chat_tools",
        choices=["chat", "chat_tools"],
        help="LLM strategy (default: chat_tools)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=50,
        help="Maximum conversation turns (default: 50)",
    )
    parser.add_argument(
        "--max-time",
        type=int,
        default=30,
        help="Maximum time in minutes (default: 30)",
    )
    parser.add_argument(
        "--max-cost",
        type=float,
        default=None,
        help="Maximum cost in USD",
    )
    parser.add_argument(
        "--traces-dir",
        default="./targets",
        help="Directory to store traces (default: ./targets)",
    )
    parser.add_argument(
        "--reasoning-effort",
        default="medium",
        choices=["minimal", "low", "medium", "high", "enabled", "disabled"],
        help="Reasoning effort for supported models (default: medium)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=1,
        help="Number of solve attempts (default: 1)",
    )
    parser.add_argument(
        "--keep-container",
        action="store_true",
        help="Keep Docker container after completion",
    )
    parser.add_argument(
        "--keep-target",
        action="store_true",
        help="Keep target running after completion",
    )
    parser.add_argument(
        "--custom-instructions",
        type=str,
        default=None,
        help="Additional instructions appended to system prompt",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check that BoxPwnr components can be imported",
    )

    args = parser.parse_args()

    from trajgym.integrations.boxpwnr_runner import AgentRunner

    runner = AgentRunner(
        platform=args.platform,
        model=args.model,
        strategy=args.strategy,
        max_turns=args.max_turns,
        max_time=args.max_time,
        max_cost=args.max_cost,
        traces_dir=args.traces_dir,
        debug=args.debug,
        keep_container=args.keep_container,
        keep_target=args.keep_target,
        reasoning_effort=args.reasoning_effort,
        attempts=args.attempts,
        custom_instructions=args.custom_instructions,
    )

    if args.check:
        sys.exit(0 if runner.check_setup() else 1)

    if not args.target:
        parser.error("--target is required (use --check to verify setup)")

    try:
        if args.platform == "cybench":
            from trajgym.challenges.preflight import (
                resolve_challenge_id_or_raise,
                validate_runtime_preflight,
            )
            from trajgym.challenges.registry import ChallengeRegistry

            registry = ChallengeRegistry(args.challenge_registry)
            if args.target_map:
                registry.load_target_overrides(args.target_map, strict=False)
            resolved_id = resolve_challenge_id_or_raise(registry, args.target)
            validate_runtime_preflight(
                registry,
                host=args.host,
                challenge_ids=[resolved_id],
                require_reachable=True,
                strict_container_check=True,
            )
            args.target = resolved_id

        runner.run(target=args.target)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
