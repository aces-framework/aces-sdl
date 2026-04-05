"""Processor declaration commands."""

from __future__ import annotations

import json

import typer
from aces_processor.manifest import reference_processor_manifest_payload

app = typer.Typer(help="Processor declarations and compatibility surfaces.")


@app.command("manifest")
def manifest() -> None:
    """Print the reference processor manifest."""

    typer.echo(json.dumps(reference_processor_manifest_payload(), indent=2, sort_keys=True))
