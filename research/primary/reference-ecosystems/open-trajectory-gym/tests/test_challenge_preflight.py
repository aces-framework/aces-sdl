"""Tests for shared challenge preflight collision checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from trajgym.challenges.preflight import (
    find_target_collisions,
    resolve_challenge_id_or_raise,
    run_runtime_preflight,
    validate_no_target_collisions,
    validate_runtime_preflight,
)
from trajgym.challenges.registry import ChallengeRegistry


def _write_registry(path: Path) -> Path:
    path.write_text(
        """
challenges:
  - id: ch-a
    category: web
    difficulty: easy
    infra_type: docker
    port: 32801
    ground_truth_flag: FLAG{a}
  - id: ch-b
    category: web
    difficulty: easy
    infra_type: docker
    port: 32801
    ground_truth_flag: FLAG{b}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def test_detects_target_collisions(tmp_path: Path) -> None:
    registry = ChallengeRegistry(str(_write_registry(tmp_path / "registry.yaml")))
    collisions = find_target_collisions(registry)
    assert "http://localhost:32801" in collisions
    assert set(collisions["http://localhost:32801"]) == {"ch-a", "ch-b"}


def test_validate_no_target_collisions_raises(tmp_path: Path) -> None:
    registry = ChallengeRegistry(str(_write_registry(tmp_path / "registry.yaml")))
    try:
        validate_no_target_collisions(registry)
    except ValueError as exc:
        assert "Target URL collisions" in str(exc)
    else:
        raise AssertionError("expected collision validation to raise")


def test_resolve_challenge_alias(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry_alias.yaml"
    registry_path.write_text(
        """
challenges:
  - id: canonical-id
    name: Friendly Name
    aliases: [friendly, name]
    category: web
    difficulty: easy
    infra_type: docker
    port: 32802
    ground_truth_flag: FLAG{x}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    registry = ChallengeRegistry(str(registry_path))
    assert resolve_challenge_id_or_raise(registry, "friendly") == "canonical-id"


def test_runtime_preflight_detects_registry_target_port_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    registry_path = tmp_path / "registry_port_mismatch.yaml"
    registry_path.write_text(
        """
challenges:
  - id: ch-port
    category: web
    difficulty: easy
    infra_type: docker
    port: 32801
    target_url: http://localhost:32802
""".strip()
        + "\n",
        encoding="utf-8",
    )
    registry = ChallengeRegistry(str(registry_path))

    monkeypatch.setattr(
        "trajgym.challenges.preflight._probe_target_reachability",
        lambda target, timeout_seconds: (True, "http", "http_status_200"),
    )

    report = run_runtime_preflight(
        registry,
        challenge_ids=["ch-port"],
        strict_container_check=False,
    )
    assert not report.ok
    assert any("registry port" in err for err in report.errors)


def test_runtime_preflight_detects_missing_container_port_mapping(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry_path = tmp_path / "registry_container_mismatch.yaml"
    registry_path.write_text(
        """
challenges:
  - id: ch-web
    category: web
    difficulty: easy
    infra_type: docker
    port: 32801
""".strip()
        + "\n",
        encoding="utf-8",
    )
    registry = ChallengeRegistry(str(registry_path))

    monkeypatch.setattr(
        "trajgym.challenges.preflight._probe_target_reachability",
        lambda target, timeout_seconds: (True, "http", "http_status_200"),
    )
    monkeypatch.setattr(
        "trajgym.challenges.preflight._docker_ports_snapshot",
        lambda timeout_seconds: ("0.0.0.0:39999->80/tcp\n", None),
    )

    report = run_runtime_preflight(registry, challenge_ids=["ch-web"])
    assert not report.ok
    assert any("expected docker published port 32801" in err for err in report.errors)


def test_runtime_preflight_allows_missing_docker_snapshot_when_reachable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry_path = tmp_path / "registry_reachable_no_docker.yaml"
    registry_path.write_text(
        """
challenges:
  - id: ch-web
    category: web
    difficulty: easy
    infra_type: docker
    port: 32801
""".strip()
        + "\n",
        encoding="utf-8",
    )
    registry = ChallengeRegistry(str(registry_path))

    monkeypatch.setattr(
        "trajgym.challenges.preflight._probe_target_reachability",
        lambda target, timeout_seconds: (True, "tcp", "tcp_connect_ok"),
    )
    monkeypatch.setattr(
        "trajgym.challenges.preflight._docker_ports_snapshot",
        lambda timeout_seconds: (None, "docker command not found"),
    )

    report = run_runtime_preflight(registry, challenge_ids=["ch-web"])
    assert report.ok
    assert report.warnings
    assert any(
        "Container port-binding verification unavailable" in msg
        for msg in report.warnings
    )


def test_runtime_preflight_raises_on_unreachable_target(
    tmp_path: Path, monkeypatch
) -> None:
    registry_path = tmp_path / "registry_unreachable.yaml"
    registry_path.write_text(
        """
challenges:
  - id: ch-web
    category: web
    difficulty: easy
    infra_type: docker
    port: 32801
""".strip()
        + "\n",
        encoding="utf-8",
    )
    registry = ChallengeRegistry(str(registry_path))

    monkeypatch.setattr(
        "trajgym.challenges.preflight._probe_target_reachability",
        lambda target, timeout_seconds: (False, "tcp", "timed out"),
    )
    monkeypatch.setattr(
        "trajgym.challenges.preflight._docker_ports_snapshot",
        lambda timeout_seconds: ("0.0.0.0:32801->80/tcp\n", None),
    )

    with pytest.raises(ValueError, match="Runtime preflight failed"):
        validate_runtime_preflight(registry, challenge_ids=["ch-web"])


def test_runtime_preflight_accepts_raw_tcp_target(tmp_path: Path, monkeypatch) -> None:
    registry_path = tmp_path / "registry_tcp.yaml"
    registry_path.write_text(
        """
challenges:
  - id: ch-tcp
    category: pwn
    difficulty: easy
    infra_type: docker
    port: 40100
    target_url: localhost:40100
""".strip()
        + "\n",
        encoding="utf-8",
    )
    registry = ChallengeRegistry(str(registry_path))

    monkeypatch.setattr(
        "trajgym.challenges.preflight._probe_target_reachability",
        lambda target, timeout_seconds: (True, "tcp", "tcp_connect_ok"),
    )
    monkeypatch.setattr(
        "trajgym.challenges.preflight._docker_ports_snapshot",
        lambda timeout_seconds: ("0.0.0.0:40100->1337/tcp\n", None),
    )

    report = validate_runtime_preflight(registry, challenge_ids=["ch-tcp"])
    assert report.ok
