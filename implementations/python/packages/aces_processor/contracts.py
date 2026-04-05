"""Compatibility re-export for neutral ACES external contracts."""

from aces._compat import reexport as _reexport

_reexport(globals(), "aces_contracts.contracts")

del _reexport
