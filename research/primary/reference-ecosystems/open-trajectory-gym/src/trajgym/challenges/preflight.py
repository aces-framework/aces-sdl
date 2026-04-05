"""Shared challenge preflight checks used across training and runtime CLIs."""

from __future__ import annotations

import contextlib
import http.client
import socket
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .registry import ChallengeRegistry

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


@dataclass(frozen=True)
class TargetCheckResult:
    """Per-challenge target preflight check result."""

    challenge_id: str
    infra_type: str
    target: str
    reachable: bool
    check_mode: str
    detail: str
    container_port_bound: bool | None = None


@dataclass
class RuntimePreflightReport:
    """Aggregated runtime preflight report."""

    challenge_ids: list[str] = field(default_factory=list)
    collisions: dict[str, list[str]] = field(default_factory=dict)
    checks: list[TargetCheckResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _resolve_selected_challenge_ids(
    registry: ChallengeRegistry,
    *,
    challenge_ids: Iterable[str] | None = None,
) -> list[str]:
    selected: list[str] = []
    if challenge_ids is None:
        selected = [info.id for info in registry.list_all()]
    else:
        for cid in challenge_ids:
            resolved = registry.resolve_id(str(cid))
            if resolved is not None:
                selected.append(resolved)

    deduped: list[str] = []
    seen: set[str] = set()
    for cid in selected:
        if cid in seen:
            continue
        seen.add(cid)
        deduped.append(cid)
    return deduped


def _extract_target_host_port(target: str) -> tuple[str | None, int | None, str]:
    """Return `(hostname, port, scheme)` for a target URL/endpoint."""
    text = str(target or "").strip()
    if not text:
        return None, None, ""
    if text.startswith("file://"):
        parsed = urlparse(text)
        return parsed.hostname, None, "file"

    # Raw host:port target.
    if "://" not in text and ":" in text and "/" not in text:
        host_part, port_part = text.rsplit(":", 1)
        try:
            return host_part, int(port_part), "tcp"
        except ValueError:
            return host_part, None, "tcp"

    parsed = urlparse(text)
    scheme = (parsed.scheme or "").lower()
    if scheme in {"http", "https"}:
        default_port = 443 if scheme == "https" else 80
        return parsed.hostname, parsed.port or default_port, scheme
    if parsed.hostname or parsed.port:
        return parsed.hostname, parsed.port, scheme
    return None, None, scheme


def _is_local_target(hostname: str | None) -> bool:
    if not hostname:
        return True
    return hostname.lower() in _LOCAL_HOSTS


def _probe_target_reachability(
    target: str, timeout_seconds: float
) -> tuple[bool, str, str]:
    """Probe target using HTTP first when possible, then raw TCP fallback."""
    text = str(target or "").strip()
    if not text:
        return False, "none", "empty target"
    if text.startswith("file://"):
        parsed = urlparse(text)
        path = parsed.path or ""
        exists = bool(path and Path(path).exists())
        if exists:
            return True, "file", "file_exists"
        return False, "file", f"file_missing:{path}"

    parsed = urlparse(text)
    scheme = (parsed.scheme or "").lower()
    host: str | None = None
    port: int | None = None

    if scheme in {"http", "https"}:
        host = parsed.hostname
        port = parsed.port or (443 if scheme == "https" else 80)
        if not host:
            return False, "http", f"invalid target:{text}"
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        conn_cls = (
            http.client.HTTPSConnection
            if scheme == "https"
            else http.client.HTTPConnection
        )
        for method in ("HEAD", "GET"):
            conn = conn_cls(host=host, port=port, timeout=timeout_seconds)
            try:
                conn.request(
                    method, path, headers={"User-Agent": "trajgym-preflight/1.0"}
                )
                resp = conn.getresponse()
                return True, "http", f"http_status_{resp.status}"
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
            finally:
                with contextlib.suppress(Exception):
                    conn.close()
        # Fall through to TCP fallback below.
    elif "://" not in text and ":" in text and "/" not in text:
        host_part, port_part = text.rsplit(":", 1)
        host = host_part
        try:
            port = int(port_part)
        except ValueError:
            return False, "tcp", f"invalid_port:{text}"
        last_err = "tcp_probe_failed"
    else:
        host, port, _ = _extract_target_host_port(text)
        last_err = "unsupported_target_format"

    if not host or not port:
        return False, "tcp", last_err
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_seconds):
            return True, "tcp", "tcp_connect_ok"
    except Exception as exc:  # noqa: BLE001
        return False, "tcp", str(exc)


def _docker_ports_snapshot(timeout_seconds: float) -> tuple[str | None, str | None]:
    """Return docker port mappings text from `docker ps`, or an error string."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Ports}}"],
            capture_output=True,
            text=True,
            timeout=max(5, int(timeout_seconds) + 5),
        )
    except FileNotFoundError:
        return None, "docker command not found"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        return None, f"docker ps failed: {stderr or 'unknown error'}"
    return result.stdout or "", None


def find_target_collisions(
    registry: ChallengeRegistry,
    *,
    host: str = "localhost",
    challenge_ids: Iterable[str] | None = None,
) -> dict[str, list[str]]:
    """Return target URL collisions for selected challenges.

    Collisions are ignored for static/file-based targets because they
    intentionally share a local workspace path.
    """
    selected = _resolve_selected_challenge_ids(
        registry,
        challenge_ids=challenge_ids,
    )

    target_to_ids: dict[str, list[str]] = {}
    for cid in selected:
        info = registry.get(cid)
        target = registry.get_target_url(cid, host=host)
        if not target:
            continue
        if info.infra_type == "static" or target.startswith("file://"):
            continue
        target_to_ids.setdefault(str(target), []).append(info.id)

    collisions: dict[str, list[str]] = {}
    for target, ids in target_to_ids.items():
        deduped = sorted(set(ids))
        if len(deduped) > 1:
            collisions[target] = deduped
    return collisions


def validate_no_target_collisions(
    registry: ChallengeRegistry,
    *,
    host: str = "localhost",
    challenge_ids: Iterable[str] | None = None,
) -> None:
    """Raise ValueError when multiple challenge IDs share one non-static target."""
    collisions = find_target_collisions(
        registry,
        host=host,
        challenge_ids=challenge_ids,
    )
    if not collisions:
        return

    top = sorted(collisions.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    raise ValueError(
        "Target URL collisions detected (multiple challenge IDs share one target). "
        f"Top collisions: {top}. Update registry/target-map mappings."
    )


def run_runtime_preflight(
    registry: ChallengeRegistry,
    *,
    host: str = "localhost",
    challenge_ids: Iterable[str] | None = None,
    timeout_seconds: float = 2.0,
    require_reachable: bool = True,
    strict_container_check: bool = True,
) -> RuntimePreflightReport:
    """Run runtime checks for registry/target/port/container/reachability mismatches."""
    selected = _resolve_selected_challenge_ids(
        registry,
        challenge_ids=challenge_ids,
    )
    report = RuntimePreflightReport(challenge_ids=selected)

    collisions = find_target_collisions(
        registry,
        host=host,
        challenge_ids=selected,
    )
    if collisions:
        report.collisions = collisions
        top = sorted(collisions.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        report.errors.append(
            "Target URL collisions detected (multiple challenge IDs share one target). "
            f"Top collisions: {top}."
        )

    docker_ports_text: str | None = None
    docker_snapshot_error: str | None = None
    if strict_container_check:
        needs_local_docker_check = False
        for cid in selected:
            info = registry.get(cid)
            if info.infra_type != "docker":
                continue
            target = registry.get_target_url(cid, host=host)
            target_host, _, _ = _extract_target_host_port(str(target or ""))
            if _is_local_target(target_host):
                needs_local_docker_check = True
                break
        if needs_local_docker_check:
            docker_ports_text, docker_snapshot_error = _docker_ports_snapshot(
                timeout_seconds
            )
            if docker_ports_text is None:
                report.warnings.append(
                    "Container port-binding verification unavailable; "
                    "continuing with reachability checks only: "
                    f"{docker_snapshot_error or 'unknown error'}"
                )

    for cid in selected:
        info = registry.get(cid)
        target = registry.get_target_url(cid, host=host)
        if not target:
            if info.infra_type == "static":
                report.warnings.append(
                    f"Challenge {info.id}: static challenge without explicit target."
                )
                continue
            report.errors.append(
                f"Challenge {info.id}: missing target URL/port mapping in registry."
            )
            continue

        target_host, target_port, _ = _extract_target_host_port(target)

        if info.infra_type == "docker":
            if info.port is None and target_port is None:
                report.errors.append(
                    f"Challenge {info.id}: docker challenge missing explicit port in registry/target."
                )
            elif (
                info.port is not None
                and target_port is not None
                and info.port != target_port
            ):
                report.errors.append(
                    f"Challenge {info.id}: registry port ({info.port}) != target port ({target_port}) "
                    f"for target {target}."
                )

        container_port_bound: bool | None = None
        if (
            strict_container_check
            and info.infra_type == "docker"
            and _is_local_target(target_host)
        ):
            expected_port = info.port or target_port
            if expected_port is not None and docker_ports_text is not None:
                expected_token = f":{expected_port}->"
                container_port_bound = expected_token in docker_ports_text
                if not container_port_bound:
                    report.errors.append(
                        f"Challenge {info.id}: expected docker published port {expected_port} "
                        "is not present in `docker ps` output."
                    )
            elif expected_port is not None and docker_snapshot_error:
                container_port_bound = None

        reachable = True
        check_mode = "none"
        detail = "reachability check disabled"
        if require_reachable:
            reachable, check_mode, detail = _probe_target_reachability(
                target, timeout_seconds
            )
            if not reachable:
                report.errors.append(
                    f"Challenge {info.id}: target unreachable ({target}) via {check_mode}: {detail}"
                )

        report.checks.append(
            TargetCheckResult(
                challenge_id=info.id,
                infra_type=info.infra_type,
                target=target,
                reachable=reachable,
                check_mode=check_mode,
                detail=detail,
                container_port_bound=container_port_bound,
            )
        )

    return report


def validate_runtime_preflight(
    registry: ChallengeRegistry,
    *,
    host: str = "localhost",
    challenge_ids: Iterable[str] | None = None,
    timeout_seconds: float = 2.0,
    require_reachable: bool = True,
    strict_container_check: bool = True,
) -> RuntimePreflightReport:
    """Raise ValueError when runtime preflight finds mismatches."""
    report = run_runtime_preflight(
        registry,
        host=host,
        challenge_ids=challenge_ids,
        timeout_seconds=timeout_seconds,
        require_reachable=require_reachable,
        strict_container_check=strict_container_check,
    )
    if report.ok:
        return report

    preview = "; ".join(report.errors[:8])
    raise ValueError(
        f"Runtime preflight failed with {len(report.errors)} error(s) "
        f"across {len(report.challenge_ids)} challenge(s): {preview}"
    )


def resolve_challenge_id_or_raise(
    registry: ChallengeRegistry, challenge_id: str
) -> str:
    """Resolve challenge alias/name/id to canonical id with clear failure text."""
    resolved = registry.resolve_id(challenge_id)
    if resolved is None:
        raise KeyError(f"Challenge not found or ambiguous: {challenge_id}")
    return resolved
