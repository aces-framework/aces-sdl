"""Public vocabulary used by external ACES contracts."""

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


class ConceptProvenanceCategory(str, Enum):
    """How a concept family relates to its authority source."""

    ADOPTED = "adopted"
    ADAPTED = "adapted"
    NATIVE = "native"
