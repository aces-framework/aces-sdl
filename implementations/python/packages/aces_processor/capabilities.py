"""Processor-level capability declarations."""

from dataclasses import dataclass, field

from aces_contracts.vocabulary import ProcessorFeature


@dataclass(frozen=True)
class ProcessorManifest:
    """Processor identity, capability, and compatibility declaration."""

    name: str
    version: str
    supported_sdl_versions: frozenset[str] = frozenset()
    supported_contract_versions: frozenset[str] = frozenset()
    supported_features: frozenset[ProcessorFeature] = frozenset()
    compatible_backends: frozenset[str] = frozenset()
    constraints: dict[str, str] = field(default_factory=dict)
