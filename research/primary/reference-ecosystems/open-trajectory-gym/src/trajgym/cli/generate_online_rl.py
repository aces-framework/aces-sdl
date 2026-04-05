#!/usr/bin/env python3
"""Generate Online RL dataset from Cybench registry.

Reads the Cybench YAML registry, connects it to reachable targets (via target map),
and generates the initial dataset JSONL needed by Online RL.

Usage:
  python src/trajgym/cli/generate_online_rl.py \
    --registry configs/challenges/cybench.yaml \
    --target-map configs/challenges/cybench_target_map_runpod.json \
    --output data/online_rl_smoke.jsonl
"""

import argparse
import json
import logging
import socket
import urllib.request
from collections import defaultdict
from pathlib import Path

import yaml

from trajgym.prompts.composer import (
    build_registry_user_prompt,
    get_canonical_system_prompt,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _is_reachable(target_url: str, category: str, timeout: float = 3.0) -> bool:
    """Check if the target URL is reachable.

    For web challenges, performs an HTTP GET.
    For local/file URLs, assumes reachable.
    For everything else, performs a TCP connection probe.
    """
    if target_url.startswith("file://") or target_url.startswith("local://"):
        return True

    # Parse host:port
    clean_url = target_url.replace("http://", "").replace("https://", "")
    host_port = clean_url.split("/")[0]
    parts = host_port.split(":")

    # Skip resolution for placeholder DNS names that clearly won't resolve locally
    # unless mapping explicitly sets them.
    if len(parts) > 0 and parts[0] in ("placeholder", "target", "example.com"):
        return False

    if len(parts) == 1:
        host = parts[0]
        port = 80 if "http://" in target_url else 443
    else:
        host = parts[0]
        try:
            port = int(parts[1])
        except ValueError:
            return False

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))

        # If web, try to get an HTTP response to ensure service is actually up
        if category == "web" and ("http://" in target_url or "https://" in target_url):
            try:
                req = urllib.request.Request(target_url, method="GET")
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return response.status < 500
            except urllib.error.URLError as e:
                # 40x errors still mean the web server is reachable
                return bool(hasattr(e, "code") and e.code < 500)
        return True
    except Exception:
        return False
    finally:
        s.close()


def build_messages(
    challenge_id: str,
    target_url: str,
    category: str,
    difficulty: str,
    description: str | None = None,
) -> list[dict[str, str]]:
    """Build the prompt messages list using the centralized composer."""
    return [
        {"role": "system", "content": get_canonical_system_prompt()},
        {
            "role": "user",
            "content": build_registry_user_prompt(
                challenge_id=challenge_id,
                category=category,
                difficulty=difficulty,
                target_url=target_url,
                description=description,
            ),
        },
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry", type=str, required=True, help="Path to cybench.yaml"
    )
    parser.add_argument(
        "--target-map", type=str, required=True, help="Path to cybench_target_map.json"
    )
    parser.add_argument("--output", type=str, required=True, help="Output JSONL path")
    parser.add_argument(
        "--probe-targets",
        action="store_true",
        help="Probe TCP/HTTP to ensure targets are reachable",
    )
    parser.add_argument(
        "--strict-target-probe",
        action="store_true",
        help="Fail entirely if any target is unreachable",
    )
    parser.add_argument(
        "--difficulty-max",
        type=str,
        help="Max difficulty to include (very_easy, easy, medium, hard)",
    )
    parser.add_argument(
        "--include-static",
        action="store_true",
        help="Include pure static challenges (file:// targets)",
    )
    args = parser.parse_args()

    with open(args.registry) as f:
        registry = yaml.safe_load(f)

    with open(args.target_map) as f:
        target_map = json.load(f)

    # Difficulty thresholds
    diff_order = {"very_easy": 0, "easy": 1, "medium": 2, "hard": 3}
    max_diff_val = (
        diff_order.get(args.difficulty_max, 99) if args.difficulty_max else 99
    )

    challenges = registry.get("challenges", [])
    logger.info(f"Loaded {len(challenges)} challenges from registry")

    # Flatten map if necessary
    flat_map = {}
    if "domains" in target_map:
        for _domain, cmap in target_map["domains"].items():
            for cid, info in cmap.items():
                if "target_url" in info:
                    flat_map[cid] = info["target_url"]
    elif "challenge_targets" in target_map:
        flat_map = target_map["challenge_targets"]
    else:
        flat_map = target_map

    samples = []
    skipped = defaultdict(int)

    for chall in challenges:
        cid = chall["id"]
        category = chall["category"]
        diff = chall["difficulty"]

        # Check difficulty filter
        if diff_order.get(diff, 99) > max_diff_val:
            skipped["difficulty_too_high"] += 1
            continue

        target_url = flat_map.get(cid)
        if not target_url:
            skipped["missing_target_url"] += 1
            continue

        is_static = target_url.startswith("file://") or target_url.startswith(
            "local://"
        )
        if is_static and not args.include_static:
            skipped["excluded_static"] += 1
            continue

        if args.probe_targets and not _is_reachable(target_url, category):
            msg = f"Target unreachable for challenge {cid}: {target_url}"
            if args.strict_target_probe:
                raise RuntimeError(msg)
            logger.warning(msg)
            skipped["probe_unreachable"] += 1
            continue

        # Build message
        desc = chall.get("description")
        messages = build_messages(
            challenge_id=cid,
            target_url=target_url,
            category=category,
            difficulty=diff,
            description=desc,
        )

        samples.append(
            {
                "messages": messages,
                "ground_truth_flag": chall.get("flag", ""),
                "optimal_steps": chall.get("optimal_steps", 10),
                "metadata": {
                    "challenge_id": cid,
                    "category": category,
                    "difficulty": diff,
                    "infra_type": chall.get("infra_type", "docker"),
                    "path_hint": chall.get("path_hint"),
                },
            }
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w") as f:
        for sample in samples:
            f.write(json.dumps(sample) + "\n")

    logger.info(f"Generated {len(samples)} usable samples.")
    for reason, count in skipped.items():
        logger.info(f"  Skipped - {reason}: {count}")
    logger.info(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
