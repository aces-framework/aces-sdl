#!/usr/bin/env python3
"""Open Trajectory Gym Challenge Management CLI.

Launch, monitor, and stop Docker containers for benchmark challenges.

Usage:
    trajgym-challenges setup
    trajgym-challenges setup --id eval-me
    trajgym-challenges status
    trajgym-challenges teardown
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

DEFAULT_REGISTRY = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "configs"
    / "challenges"
    / "cybench.yaml"
)


def cmd_setup(args: argparse.Namespace) -> None:
    """Launch challenge containers."""
    from trajgym.challenges.manager import ChallengeManager
    from trajgym.challenges.preflight import validate_no_target_collisions
    from trajgym.challenges.registry import ChallengeRegistry

    registry = ChallengeRegistry(args.registry)
    validate_no_target_collisions(
        registry,
        host=args.host,
        challenge_ids=[args.id] if args.id else None,
    )
    manager = ChallengeManager(
        registry=registry,
        bench_dir=args.bench_dir,
        host=args.host,
    )

    try:
        if args.id:
            url = manager.setup(args.id)
            print(f"  {args.id}: {url}")
            if manager.health_check(args.id):
                print("  Health check: OK")
            else:
                print("  Health check: PENDING (service may still be starting)")
        else:
            results = manager.setup_all()
            for cid, url in results.items():
                status = "OK" if manager.health_check(cid) else "PENDING"
                print(f"  {cid}: {url} [{status}]")
            print(f"\nLaunched {len(results)} challenges")
    except Exception as exc:
        logger.error("Challenge setup failed: %s", exc)
        raise SystemExit(1) from exc


def cmd_status(args: argparse.Namespace) -> None:
    """Show running challenge containers."""
    from trajgym.challenges.manager import ChallengeManager
    from trajgym.challenges.registry import ChallengeRegistry

    registry = ChallengeRegistry(args.registry)
    manager = ChallengeManager(
        registry=registry,
        bench_dir=args.bench_dir,
        host=args.host,
    )

    docker_challenges = registry.list_docker_challenges()
    print(f"Docker challenges: {len(docker_challenges)}")
    print(f"Static challenges: {len(registry.list_static_challenges())}")
    print()

    for info in docker_challenges:
        url = registry.get_target_url(info.id, host=args.host)
        healthy = manager.health_check(info.id)
        status = "UP" if healthy else "DOWN"
        print(f"  [{status}] {info.id}: {url}")


def cmd_teardown(args: argparse.Namespace) -> None:
    """Stop challenge containers."""
    from trajgym.challenges.manager import ChallengeManager
    from trajgym.challenges.registry import ChallengeRegistry

    registry = ChallengeRegistry(args.registry)
    manager = ChallengeManager(
        registry=registry,
        bench_dir=args.bench_dir,
        host=args.host,
    )

    if args.id:
        manager.teardown(args.id)
        print(f"Stopped: {args.id}")
    else:
        # Teardown all docker challenges
        for info in registry.list_docker_challenges():
            try:
                manager.teardown(info.id)
                print(f"  Stopped: {info.id}")
            except Exception as exc:
                print(f"  Failed: {info.id} ({exc})")
        print("All challenges stopped")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open Trajectory Gym Challenge Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help=f"Path to challenge registry YAML (default: {DEFAULT_REGISTRY})",
    )
    parser.add_argument(
        "--bench-dir",
        default=".",
        help="Path to benchmark repo root (default: current directory)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host for target URLs (default: localhost)",
    )

    subparsers = parser.add_subparsers(dest="command")

    # -- setup ---------------------------------------------------------------
    setup_parser = subparsers.add_parser("setup", help="Launch challenge containers")
    setup_parser.add_argument(
        "--id", default=None, help="Specific challenge ID to launch"
    )
    setup_parser.set_defaults(func=cmd_setup)

    # -- status --------------------------------------------------------------
    status_parser = subparsers.add_parser("status", help="Show challenge status")
    status_parser.set_defaults(func=cmd_status)

    # -- teardown ------------------------------------------------------------
    teardown_parser = subparsers.add_parser(
        "teardown", help="Stop challenge containers"
    )
    teardown_parser.add_argument(
        "--id", default=None, help="Specific challenge ID to stop"
    )
    teardown_parser.set_defaults(func=cmd_teardown)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
