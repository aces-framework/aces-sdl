"""Backward-compatible ACES namespace."""

from aces._compat import package_version

__version__ = package_version("aces-sdl", default="0.1.0")

__all__ = ["__version__"]
