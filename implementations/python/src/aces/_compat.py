"""Helpers for transitional ``aces.*`` compatibility modules."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import Any


def package_version(distribution: str, default: str) -> str:
    """Return an installed package version with a local fallback."""

    try:
        return version(distribution)
    except PackageNotFoundError:
        return default


def reexport(namespace: dict[str, Any], target: str) -> None:
    """Populate ``namespace`` with the symbols from ``target``."""

    module = import_module(target)

    for name, value in module.__dict__.items():
        if name in {
            "__builtins__",
            "__cached__",
            "__file__",
            "__loader__",
            "__name__",
            "__package__",
            "__path__",
            "__spec__",
        }:
            continue
        namespace[name] = value

    namespace["__doc__"] = module.__doc__
    namespace["__target_module__"] = target
    namespace["__all__"] = list(
        getattr(module, "__all__", [name for name in module.__dict__ if not name.startswith("_")])
    )
