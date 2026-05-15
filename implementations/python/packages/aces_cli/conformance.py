"""Backend conformance commands.

Exposes ``aces conformance backend`` as the canonical CLI surface for the
backend conformance fixture suite. The legacy ``aces_conformance.runner``
module remains as a thin delegate for back-compat callers
(``python -m aces_conformance.runner``).
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from aces_conformance.conformance import (
    BackendCapabilityProfile,
    BackendConformanceReport,
    run_fixture_suite,
)
from aces_processor.models import Diagnostic

_DEFAULT_PROFILE_ID = BackendCapabilityProfile.ORCHESTRATION_EVALUATION.value
_KNOWN_PROFILE_HINT = ", ".join(sorted(profile.value for profile in BackendCapabilityProfile))

app = typer.Typer(help="Backend conformance suite and fixture corpus.")


def _serialize_diagnostic(diag: Diagnostic) -> dict[str, object]:
    """Serialize a :class:`Diagnostic` with its stable identifying fields.

    CI gates wired to ``aces conformance backend`` need to distinguish
    ``conformance.profile-load-failed`` from ``conformance.fixture-missing``
    from a case-level schema failure; flattening to ``message`` would force
    brittle string-matching. Preserve the structured envelope.
    """

    return {
        "code": diag.code,
        "domain": diag.domain,
        "address": diag.address,
        "severity": diag.severity.value if hasattr(diag.severity, "value") else str(diag.severity),
        "message": diag.message,
    }


def _report_payload(report: BackendConformanceReport) -> dict[str, object]:
    return {
        "profile": report.profile,
        "passed": report.passed,
        "cases": [
            {
                "name": case.name,
                "contract_name": case.contract_name,
                "valid": case.valid,
                "passed": case.passed,
                "diagnostics": [_serialize_diagnostic(diag) for diag in case.diagnostics],
            }
            for case in report.cases
        ],
        "diagnostics": [_serialize_diagnostic(diag) for diag in report.diagnostics],
    }


@app.command("backend")
def backend(
    profile: str = typer.Option(
        _DEFAULT_PROFILE_ID,
        "--profile",
        help=(
            "Backend profile id to validate. Resolves against the JSON corpus under "
            "--profiles-root (defaults to contracts/profiles/backend). Known runtime "
            f"surfaces: {_KNOWN_PROFILE_HINT}. Other ids load as long as their JSON "
            "exists in the corpus, so adding a new published profile does not require "
            "a Python-side enum edit."
        ),
    ),
    fixtures_root: Path | None = typer.Option(
        None,
        "--fixtures-root",
        help="Override the fixtures tree (defaults to contracts/fixtures).",
    ),
    profiles_root: Path | None = typer.Option(
        None,
        "--profiles-root",
        help="Override the backend profile tree (defaults to contracts/profiles/backend).",
    ),
) -> None:
    """Run the published backend conformance fixture suite for ``profile``.

    Reads the profile-to-contract requirements from
    ``contracts/profiles/backend/<profile>.json`` and the fixture corpus
    from ``contracts/fixtures/`` (or the supplied overrides). Exits non-zero
    when any case or top-level diagnostic fails so CI gates can wire it in.
    A missing/malformed/mislabeled profile JSON surfaces as a structured
    ``conformance.profile-load-failed`` diagnostic in the report.
    """

    report = run_fixture_suite(profile=profile, root=fixtures_root, profiles_root=profiles_root)
    typer.echo(json.dumps(_report_payload(report), indent=2))
    if not report.passed:
        raise typer.Exit(code=1)
