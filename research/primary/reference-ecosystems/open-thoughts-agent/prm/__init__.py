from prm.base import (
    PRMJudgment,
    ProcessRewardModel,
    Trajectory,
    get_prm,
    list_prms,
    register_prm,
)

# Import PRM implementations so @register_prm decorators execute
from prm.thrashing_detector import ThrashingDetector  # noqa: F401
from prm.teacher_hint import TeacherHint  # noqa: F401

__all__ = [
    "PRMJudgment",
    "ProcessRewardModel",
    "TeacherHint",
    "Trajectory",
    "ThrashingDetector",
    "get_prm",
    "list_prms",
    "register_prm",
]
