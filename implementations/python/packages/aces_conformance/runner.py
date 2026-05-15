#!/usr/bin/env python3
"""Compatibility delegate to the Typer ``aces conformance backend`` command.

Historic callers ran the backend conformance suite via
``python -m aces_conformance.runner``. The canonical CLI surface is now
``aces conformance backend`` in :mod:`aces_cli`; this module remains as a
thin entrypoint that forwards to it.
"""

from __future__ import annotations

import sys

from aces_cli.main import app


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    app(["conformance", "backend", *args], standalone_mode=True)


if __name__ == "__main__":
    main()
