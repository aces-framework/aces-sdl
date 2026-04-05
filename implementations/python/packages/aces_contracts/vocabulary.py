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


class WorkflowFeature(str, Enum):
    """Portable workflow control features that an orchestrator may support."""

    DECISION = "decision"
    SWITCH = "switch"
    RETRY = "retry"
    CALL = "call"
    PARALLEL_BARRIER = "parallel-barrier"
    FAILURE_TRANSITIONS = "failure-transitions"
    CANCELLATION = "cancellation"
    TIMEOUTS = "timeouts"
    COMPENSATION = "compensation"


class WorkflowStatePredicateFeature(str, Enum):
    """Portable workflow state-predicate features that an orchestrator may support."""

    OUTCOME_MATCHING = "outcome-matching"
    ATTEMPT_COUNTS = "attempt-counts"


class RealizationSupportMode(str, Enum):
    """How an apparatus can supply realizations for underspecified inputs."""

    EXACT_ONLY = "exact-only"
    CONSTRAINED = "constrained"
    OPEN_REALIZATION = "open-realization"


class ConceptProvenanceCategory(str, Enum):
    """How a concept family relates to its authority source."""

    ADOPTED = "adopted"
    ADAPTED = "adapted"
    NATIVE = "native"
