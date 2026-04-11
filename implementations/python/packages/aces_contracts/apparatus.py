"""Shared apparatus declaration dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field

from .vocabulary import RealizationSupportMode


def _require_non_empty_strings(values: frozenset[str], *, field_name: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError(f"{field_name} must not contain empty strings")


@dataclass(frozen=True)
class ApparatusIdentity:
    """Stable identity for an apparatus surface."""

    name: str
    version: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ApparatusIdentity.name must be non-empty")
        if not self.version.strip():
            raise ValueError("ApparatusIdentity.version must be non-empty")


@dataclass(frozen=True)
class ConceptBinding:
    """Binds a vocabulary surface path to a canonical concept family."""

    scope: str
    family: str

    def __post_init__(self) -> None:
        if not self.scope.strip():
            raise ValueError("ConceptBinding.scope must be non-empty")
        if not self.family.strip():
            raise ValueError("ConceptBinding.family must be non-empty")


@dataclass(frozen=True)
class RealizationSupportDeclaration:
    """Declared realization-support and disclosure surface for one concern domain."""

    domain: str
    support_mode: RealizationSupportMode
    supported_constraint_kinds: frozenset[str] = frozenset()
    supported_exact_requirement_kinds: frozenset[str] = frozenset()
    disclosure_kinds: frozenset[str] = frozenset()
    constraints: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.domain.strip():
            raise ValueError("RealizationSupportDeclaration.domain must be non-empty")
        _require_non_empty_strings(self.supported_constraint_kinds, field_name="supported_constraint_kinds")
        _require_non_empty_strings(
            self.supported_exact_requirement_kinds,
            field_name="supported_exact_requirement_kinds",
        )
        _require_non_empty_strings(self.disclosure_kinds, field_name="disclosure_kinds")
        if not self.disclosure_kinds:
            raise ValueError("RealizationSupportDeclaration.disclosure_kinds must not be empty")
        if not (self.supported_constraint_kinds or self.supported_exact_requirement_kinds):
            raise ValueError(
                "RealizationSupportDeclaration must declare supported_constraint_kinds "
                "or supported_exact_requirement_kinds"
            )
        if self.support_mode == RealizationSupportMode.EXACT_ONLY and self.supported_constraint_kinds:
            raise ValueError("exact-only realization support must not declare supported_constraint_kinds")
