"""Shared apparatus declaration dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field

from .vocabulary import RealizationSupportMode


@dataclass(frozen=True)
class ApparatusIdentity:
    """Stable identity for an apparatus surface."""

    name: str
    version: str


@dataclass(frozen=True)
class ApparatusCompatibility:
    """Compatibility claims across apparatus surface families."""

    processors: frozenset[str] = frozenset()
    backends: frozenset[str] = frozenset()
    participant_implementations: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RealizationSupportDeclaration:
    """Declared realization-support and disclosure surface for one concern domain."""

    domain: str
    support_mode: RealizationSupportMode
    supported_constraint_kinds: frozenset[str] = frozenset()
    supported_exact_requirement_kinds: frozenset[str] = frozenset()
    disclosure_kinds: frozenset[str] = frozenset()
    constraints: dict[str, str] = field(default_factory=dict)
