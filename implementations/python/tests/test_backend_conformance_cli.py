"""Tests for the ``aces conformance backend`` Typer subcommand."""

from __future__ import annotations

import json
from pathlib import Path

from aces_cli.main import app
from typer.testing import CliRunner


def test_backend_conformance_cli_passes_for_provisioning_only_profile():
    runner = CliRunner()
    result = runner.invoke(app, ["conformance", "backend", "--profile", "provisioning-only"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["profile"] == "provisioning-only"
    assert payload["passed"] is True
    contract_names = {case["contract_name"] for case in payload["cases"]}
    assert contract_names == {
        "backend-manifest-v2",
        "operation-receipt-v1",
        "operation-status-v1",
        "runtime-snapshot-v1",
    }


def test_backend_conformance_cli_passes_for_full_remote_control_plane_profile():
    runner = CliRunner()
    result = runner.invoke(app, ["conformance", "backend", "--profile", "full-remote-control-plane"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["passed"] is True
    contract_names = {case["contract_name"] for case in payload["cases"]}
    assert "participant-episode-state-envelope-v1" in contract_names
    assert "participant-episode-history-event-stream-v1" in contract_names


def test_backend_conformance_cli_exits_non_zero_when_fixtures_missing(tmp_path: Path):
    """Pointing the CLI at an empty fixtures root must surface the failure
    via exit code and the JSON report's ``conformance.fixture-missing``
    diagnostics — so CI gates wired up to ``aces conformance backend`` can
    catch the regression directly."""

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "conformance",
            "backend",
            "--profile",
            "provisioning-only",
            "--fixtures-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["passed"] is False
    assert payload["diagnostics"], "missing fixture root must populate top-level diagnostics"
    codes = {diag["code"] for diag in payload["diagnostics"]}
    assert codes == {"conformance.fixture-missing"}
    for diag in payload["diagnostics"]:
        assert diag["domain"] == "conformance"
        assert diag["severity"] == "error"
        assert "Missing valid fixture directory" in diag["message"]


def test_backend_conformance_cli_emits_structured_profile_load_diagnostics(tmp_path: Path):
    """Codex review (issue #66, finding 2 of cycle 2): the CLI must serialize
    diagnostic ``code``/``domain``/``address``/``severity`` so CI gates can
    distinguish ``conformance.profile-load-failed`` from
    ``conformance.fixture-missing`` without parsing prose."""

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "conformance",
            "backend",
            "--profile",
            "provisioning-only",
            "--profiles-root",
            str(backend_dir),
        ],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    codes = {diag["code"] for diag in payload["diagnostics"]}
    assert codes == {"conformance.profile-load-failed"}


def test_backend_conformance_cli_respects_profiles_root_override(tmp_path: Path):
    """The CLI must thread ``--profiles-root`` through to the runner so the
    published profile JSON is provably the authority end-to-end."""

    synthetic = {
        "schema_version": "backend-profile/v1",
        "profile": "provisioning-only",
        "required_contracts": ["backend-manifest-v2"],
    }
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "provisioning-only.json").write_text(json.dumps(synthetic) + "\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "conformance",
            "backend",
            "--profile",
            "provisioning-only",
            "--profiles-root",
            str(backend_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    contract_names = {case["contract_name"] for case in payload["cases"]}
    assert contract_names == {"backend-manifest-v2"}


def test_backend_conformance_cli_accepts_unknown_profile_id_from_corpus(tmp_path: Path):
    """ASR-502 + codex review (issue #66, finding 1 of cycle 3): the CLI must
    accept any profile id discoverable from the JSON corpus, not only the
    Python-enum members. Adding a new ``contracts/profiles/backend/<id>.json``
    must work without a coordinated enum edit."""

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "future-control-plane.json").write_text(
        json.dumps(
            {
                "schema_version": "backend-profile/v1",
                "profile": "future-control-plane",
                "required_contracts": ["backend-manifest-v2"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "conformance",
            "backend",
            "--profile",
            "future-control-plane",
            "--profiles-root",
            str(backend_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["profile"] == "future-control-plane"
    assert payload["passed"] is True
