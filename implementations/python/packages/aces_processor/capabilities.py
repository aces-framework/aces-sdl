"""Processor-level capability declarations."""

from __future__ import annotations

from dataclasses import dataclass

from aces_contracts.apparatus import (
    ApparatusCompatibility,
    ApparatusIdentity,
    RealizationSupportDeclaration,
)
from aces_contracts.vocabulary import ProcessorFeature


@dataclass(frozen=True)
class ProcessorCapabilitySet:
    """Processor-specific capability declarations."""

    supported_sdl_versions: frozenset[str] = frozenset()
    supported_features: frozenset[ProcessorFeature] = frozenset()


@dataclass(frozen=True, init=False)
class ProcessorManifest:
    """Processor identity, capability, and compatibility declaration."""

    identity: ApparatusIdentity
    supported_contract_versions: frozenset[str]
    compatibility: ApparatusCompatibility
    realization_support: tuple[RealizationSupportDeclaration, ...]
    constraints: dict[str, str]
    capabilities: ProcessorCapabilitySet

    def __init__(
        self,
        *,
        identity: ApparatusIdentity | None = None,
        supported_contract_versions: frozenset[str] = frozenset(),
        compatibility: ApparatusCompatibility | None = None,
        realization_support: tuple[RealizationSupportDeclaration, ...] = (),
        constraints: dict[str, str] | None = None,
        capabilities: ProcessorCapabilitySet | None = None,
        name: str | None = None,
        version: str = "0.0.0+unknown",
        supported_sdl_versions: frozenset[str] = frozenset(),
        supported_features: frozenset[ProcessorFeature] = frozenset(),
        compatible_backends: frozenset[str] = frozenset(),
    ) -> None:
        if identity is None:
            if name is None:
                raise ValueError("ProcessorManifest requires either identity or name.")
            identity = ApparatusIdentity(name=name, version=version)
        if compatibility is None:
            compatibility = ApparatusCompatibility(backends=frozenset(compatible_backends))
        if capabilities is None:
            capabilities = ProcessorCapabilitySet(
                supported_sdl_versions=frozenset(supported_sdl_versions),
                supported_features=frozenset(supported_features),
            )
        object.__setattr__(self, "identity", identity)
        object.__setattr__(self, "supported_contract_versions", frozenset(supported_contract_versions))
        object.__setattr__(self, "compatibility", compatibility)
        object.__setattr__(self, "realization_support", tuple(realization_support))
        object.__setattr__(self, "constraints", {} if constraints is None else dict(constraints))
        object.__setattr__(self, "capabilities", capabilities)

    @property
    def name(self) -> str:
        return self.identity.name

    @property
    def version(self) -> str:
        return self.identity.version

    @property
    def supported_sdl_versions(self) -> frozenset[str]:
        return self.capabilities.supported_sdl_versions

    @property
    def supported_features(self) -> frozenset[ProcessorFeature]:
        return self.capabilities.supported_features

    @property
    def compatible_backends(self) -> frozenset[str]:
        return self.compatibility.backends
