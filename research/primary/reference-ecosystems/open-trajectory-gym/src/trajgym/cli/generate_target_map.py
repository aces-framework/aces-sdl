#!/usr/bin/env python3
"""Export challenge_id -> live target URL mapping from running Docker containers.

Run this on the machine where benchmark containers are running (for example DGX).
The output JSON can be consumed by online RL via:
  TRAJGYM_TARGET_MAP_PATH=/path/to/map.json
or:
  online_rl.target_map_path: /path/to/map.json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trajgym.challenges.registry import ChallengeInfo, ChallengeRegistry

logger = logging.getLogger("generate_live_target_map")


@dataclass
class PortBinding:
    host_port: int
    container_port: int


@dataclass
class ContainerRecord:
    name: str
    working_dir: str
    service: str
    project: str
    ports: list[PortBinding]


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _iter_tokens(value: str) -> set[str]:
    return {tok for tok in re.split(r"[^a-z0-9]+", (value or "").lower()) if tok}


def _parse_ports(raw_ports: str) -> list[PortBinding]:
    parsed: list[PortBinding] = []
    for match in re.finditer(r":(\d+)->(\d+)/tcp", raw_ports or ""):
        parsed.append(
            PortBinding(
                host_port=int(match.group(1)), container_port=int(match.group(2))
            )
        )
    return parsed


def _list_containers() -> list[ContainerRecord]:
    cmd = [
        "docker",
        "ps",
        "--format",
        '{{.Names}}\t{{.Label "com.docker.compose.project.working_dir"}}\t{{.Label "com.docker.compose.service"}}\t{{.Label "com.docker.compose.project"}}\t{{.Ports}}',
    ]
    try:
        out = subprocess.check_output(cmd, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("docker command not found on this host") from exc

    records: list[ContainerRecord] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        name, working_dir, service, project, ports_raw = parts[:5]
        ports = _parse_ports(ports_raw)
        records.append(
            ContainerRecord(
                name=name.strip(),
                working_dir=(working_dir or "").strip(),
                service=(service or "").strip(),
                project=(project or "").strip(),
                ports=ports,
            )
        )
    return records


def _load_metadata(path_hint: str | None, benchmark_root: Path) -> dict[str, Any]:
    if not path_hint:
        return {}
    root = Path(path_hint)
    if not root.is_absolute():
        root = benchmark_root / root

    candidates = [
        root / "metadata" / "metadata.json",
        root / "metadata.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return json.loads(candidate.read_text())
            except Exception:
                return {}
    return {}


def _target_hint_parts(metadata: dict[str, Any]) -> tuple[str, int | None]:
    raw = metadata.get("target_host")
    if not raw:
        return "", None
    raw_s = str(raw).strip()
    if not raw_s or raw_s.lower() == "none":
        return "", None
    if ":" in raw_s:
        host, port = raw_s.split(":", 1)
        if port.isdigit():
            return host.strip(), int(port)
        return host.strip(), None
    return raw_s, None


def _pick_binding(
    ports: list[PortBinding], container_port_hint: int | None
) -> PortBinding | None:
    if not ports:
        return None
    if container_port_hint is not None:
        for binding in ports:
            if binding.container_port == container_port_hint:
                return binding
    return sorted(ports, key=lambda b: b.host_port)[0]


def _resolve_from_path_matches(
    info: ChallengeInfo,
    matches: list[ContainerRecord],
    service_hint: str,
    container_port_hint: int | None,
) -> tuple[ContainerRecord, PortBinding, str] | None:
    service_hint_norm = _normalize(service_hint)

    # First preference: explicit service match with a published port.
    for record in matches:
        if service_hint_norm and service_hint_norm not in {
            _normalize(record.service),
            _normalize(record.name),
        }:
            continue
        binding = _pick_binding(record.ports, container_port_hint)
        if binding:
            return record, binding, "path+service"

    # Second preference: any path-matched container with published port.
    scored: list[tuple[int, ContainerRecord]] = []
    for record in matches:
        score = 0
        if _normalize(info.id) and _normalize(info.id) in _normalize(record.project):
            score += 120
        if _normalize(info.id) and _normalize(info.id) in _normalize(record.name):
            score += 100
        if service_hint_norm and service_hint_norm in _normalize(record.service):
            score += 80
        if record.ports:
            score += 20
        scored.append((score, record))

    for _, record in sorted(scored, key=lambda item: item[0], reverse=True):
        binding = _pick_binding(record.ports, container_port_hint)
        if binding:
            return record, binding, "path"

    # Last resort: target service has no published port (e.g., internal cache service).
    # Use sibling service in same compose project that has a published port.
    for record in matches:
        if not service_hint_norm:
            continue
        if service_hint_norm not in {
            _normalize(record.service),
            _normalize(record.name),
        }:
            continue
        siblings = [m for m in matches if m.project == record.project and m.ports]
        if not siblings:
            continue
        sibling = sorted(
            siblings,
            key=lambda r: _pick_binding(r.ports, container_port_hint).host_port,
        )[0]
        binding = _pick_binding(sibling.ports, container_port_hint)
        if binding:
            return sibling, binding, "path+sibling"

    return None


def _resolve_fallback(
    info: ChallengeInfo,
    containers: list[ContainerRecord],
    service_hint: str,
    container_port_hint: int | None,
) -> tuple[ContainerRecord, PortBinding, str] | None:
    query_tokens = (
        _iter_tokens(info.id) | _iter_tokens(info.name) | _iter_tokens(service_hint)
    )
    candidates: list[tuple[int, ContainerRecord]] = []

    for record in containers:
        if not record.ports:
            continue
        score = 0
        record_norm = _normalize(record.name)
        project_norm = _normalize(record.project)
        service_norm = _normalize(record.service)
        if _normalize(info.id) in {record_norm, project_norm, service_norm}:
            score += 240
        if _normalize(info.id) and _normalize(info.id) in record_norm:
            score += 120
        if _normalize(info.name) and _normalize(info.name) in record_norm:
            score += 90
        if service_hint and _normalize(service_hint) in {
            record_norm,
            service_norm,
            project_norm,
        }:
            score += 140
        if container_port_hint and any(
            p.container_port == container_port_hint for p in record.ports
        ):
            score += 40
        overlap = len(
            query_tokens & (_iter_tokens(record.name) | _iter_tokens(record.project))
        )
        if overlap:
            score += overlap * 25
        if score > 0:
            candidates.append((score, record))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    top_score, top_record = candidates[0]
    if len(candidates) > 1 and candidates[1][0] >= top_score - 15 and top_score < 220:
        return None
    binding = _pick_binding(top_record.ports, container_port_hint)
    if not binding:
        return None
    return top_record, binding, "fallback"


def _path_matches(
    path_hint: str | None, benchmark_root: Path, record: ContainerRecord
) -> bool:
    if not path_hint or not record.working_dir:
        return False
    hint_rel = str(Path(path_hint)).replace("\\", "/").strip("/")
    working = record.working_dir.replace("\\", "/")
    if hint_rel and hint_rel in working:
        return True

    hint_path = Path(path_hint)
    if not hint_path.is_absolute():
        hint_path = benchmark_root / hint_path
    try:
        hint_abs = str(hint_path.resolve()).replace("\\", "/")
    except Exception:
        hint_abs = str(hint_path).replace("\\", "/")
    return hint_abs in working


def build_live_target_map(
    registry: ChallengeRegistry,
    benchmark_root: Path,
    host: str,
    port_offset: int = 0,
) -> dict[str, Any]:
    containers = _list_containers()
    docker_challenges = registry.list_docker_challenges()

    mapping: dict[str, str] = {}
    details: list[dict[str, Any]] = []
    unmatched: list[str] = []

    for info in docker_challenges:
        metadata = _load_metadata(info.path_hint, benchmark_root=benchmark_root)
        service_hint, container_port_hint = _target_hint_parts(metadata)
        matches = [
            c for c in containers if _path_matches(info.path_hint, benchmark_root, c)
        ]

        resolved = _resolve_from_path_matches(
            info=info,
            matches=matches,
            service_hint=service_hint,
            container_port_hint=container_port_hint,
        )
        if resolved is None:
            resolved = _resolve_fallback(
                info=info,
                containers=containers,
                service_hint=service_hint,
                container_port_hint=container_port_hint,
            )

        if resolved is None:
            unmatched.append(info.id)
            continue

        record, binding, source = resolved
        mapped_port = binding.host_port + int(port_offset)
        target_url = f"http://{host}:{mapped_port}"
        mapping[info.id] = target_url
        details.append(
            {
                "id": info.id,
                "target_url": target_url,
                "source": source,
                "container_name": record.name,
                "compose_project": record.project,
                "compose_service": record.service,
                "working_dir": record.working_dir,
                "host_port": mapped_port,
                "host_port_source": binding.host_port,
                "container_port": binding.container_port,
                "target_host_hint": metadata.get("target_host"),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": host,
        "port_offset": int(port_offset),
        "docker_ps_container_count": len(containers),
        "docker_challenge_count": len(docker_challenges),
        "mapped_count": len(mapping),
        "unmapped_ids": sorted(unmatched),
        "challenge_targets": mapping,
        "challenges": sorted(details, key=lambda row: row["id"]),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        default="configs/challenges/cybench.yaml",
        help="Path to challenge registry YAML.",
    )
    parser.add_argument(
        "--benchmark-root",
        default=".",
        help="Root directory of benchmark repo (contains benchmark/...).",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host used in output target URLs (default: localhost).",
    )
    parser.add_argument(
        "--port-offset",
        type=int,
        default=0,
        help="Additive offset for published host ports (example: 10200 maps 32801->43001).",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output JSON path (default: stdout).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any docker challenge cannot be mapped.",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = _parse_args()
    registry = ChallengeRegistry(args.registry)
    payload = build_live_target_map(
        registry=registry,
        benchmark_root=Path(args.benchmark_root).resolve(),
        host=args.host,
        port_offset=int(args.port_offset),
    )

    text = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    if args.output == "-":
        print(text, end="")
    else:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text)
        logger.info("Wrote target map: %s", out_path)

    unmapped = payload["unmapped_ids"]
    logger.info(
        "Mapped %d/%d docker challenges",
        payload["mapped_count"],
        payload["docker_challenge_count"],
    )
    if unmapped:
        logger.warning("Unmapped docker challenge IDs: %s", ", ".join(unmapped))
        if args.strict:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
