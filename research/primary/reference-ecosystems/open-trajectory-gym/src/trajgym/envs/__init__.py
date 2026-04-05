"""Open Trajectory Gym environments."""

from .tool_executor import SubprocessExecutor

__all__ = ["SubprocessExecutor"]

# parse_tool_calls lives in trajgym.parsing but is re-exported here for
# backward compatibility with code that imports from trajgym.envs.
try:
    from trajgym.parsing import parse_tool_calls  # noqa: F401

    __all__.append("parse_tool_calls")
except ImportError:
    pass

# SkyRL env (optional)
try:
    from .skyrl.trajgym_env import TrajGymTextEnv  # noqa: F401

    __all__.append("TrajGymTextEnv")
except ImportError:
    pass
