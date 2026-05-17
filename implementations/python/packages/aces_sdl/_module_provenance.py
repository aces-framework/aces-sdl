"""Helpers for carrying capability-variable provenance across SDL module imports.

Lives next to ``composition.py`` rather than inside it so the composition file
stays within the repo-policy line cap, and so the provenance helpers can be
unit-tested or reused without pulling in the full module-expansion machinery.
The three helpers here are intentionally narrow:

* :func:`add_unique_provenance` rejects silent collisions on a shared
  provenance accumulator. Two imports that would map to the same generated
  private-prefixed key must fail at parse time, not silently shadow each
  other, otherwise the runtime planner can validate an imported node against
  the wrong ``allowed_values`` domain.
* :func:`dump_variable_spec` serializes the ``aces_sdl.variables.Variable``
  Pydantic model (or a plain-dict equivalent) into a stable shape consumed
  downstream by the runtime planner's ``model.variable_specs`` lookup.
* :func:`rename_variable_ref` applies the current composition level's
  namespace to a captured variable reference, handling both this level's
  local renames and deeper-import refs that already carry their own prefix.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._errors import SDLParseError


def add_unique_provenance(
    accumulator: dict[str, Any],
    key: str,
    value: Any,
    *,
    kind: str,
    source_path: Path,
) -> None:
    """Insert a generated provenance entry, rejecting silent collisions.

    The private-prefix namespace (``<ns>.__private.<name>``) is reserved for
    composition-generated names. Two imports producing the same generated
    key, or a deeper-import entry colliding with this level's local entry,
    would otherwise let one provenance record silently shadow the other and
    cause the planner to validate against the wrong ``allowed_values``
    domain. Raising here surfaces the bad import combination at parse time.
    """

    if key in accumulator:
        raise SDLParseError(
            (
                f"Module import would silently shadow {kind} '{key}'; "
                "rename one of the colliding imports to a distinct namespace."
            ),
            path=source_path,
        )
    accumulator[key] = value


def dump_variable_spec(variable: Any) -> dict[str, object]:
    """Serialize a Variable Pydantic model to a plain dict for storage."""

    if hasattr(variable, "model_dump"):
        return variable.model_dump(mode="python")
    if isinstance(variable, dict):
        return dict(variable)
    return {"value": variable}


def rename_variable_ref(
    ref: str | None,
    local_var_renames: Mapping[str, str],
    namespace: str,
    *,
    prefix: callable,  # type: ignore[valid-type]
) -> str | None:
    """Apply this composition level's namespace to a captured variable ref.

    Local imported variables are renamed via ``local_var_renames``. Refs
    that are already deeper-prefixed (because they came from a nested
    expansion) receive this level's namespace as an additional prefix so
    they line up with the prefixed specs in ``module_variable_specs``.
    ``prefix`` is the namespace-prefix function from ``composition.py``
    (``_prefix``); accepting it as a parameter avoids a circular import.
    """

    if ref is None:
        return None
    if ref in local_var_renames:
        return local_var_renames[ref]
    return prefix(namespace, ref)
