"""Main entry point for the ACES SDL CLI."""

from importlib.metadata import PackageNotFoundError, version

import typer

from aces_cli import processor, sdl

app = typer.Typer(
    name="aces",
    help="ACES SDL and runtime CLI",
    no_args_is_help=True,
)

app.add_typer(sdl.app, name="sdl")
app.add_typer(processor.app, name="processor")


def _version_callback(value: bool) -> None:
    if value:
        try:
            current_version = version("aces-sdl")
        except PackageNotFoundError:
            current_version = "0.1.0"
        typer.echo(f"aces {current_version}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """ACES SDL and runtime CLI."""
