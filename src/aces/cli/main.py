"""Main entry point for the ACES SDL CLI."""

from typing import Optional

import typer

import aces
from aces.cli import sdl

app = typer.Typer(
    name="aces",
    help="ACES SDL and runtime CLI",
    no_args_is_help=True,
)

app.add_typer(sdl.app, name="sdl")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aces {aces.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """ACES SDL and runtime CLI."""
