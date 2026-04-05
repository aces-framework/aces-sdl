"""Processor-level capability declarations."""

from dataclasses import dataclass, field
from enum import Enum


class ProcessorFeature(str, Enum):
    """Processing features that a processor may support."""

    COMPILATION = "compilation"
    PLANNING = "planning"
    ORCHESTRATION_COORDINATION = "orchestration-coordination"
    EVALUATION_COORDINATION = "evaluation-coordination"
    WORKFLOW_SEMANTICS = "workflow-semantics"
    OBJECTIVE_WINDOW_CONSISTENCY = "objective-window-consistency"
    DEPENDENCY_ORDERING = "dependency-ordering"
    RUNTIME_CONTROL_PLANE = "runtime-control-plane"


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
