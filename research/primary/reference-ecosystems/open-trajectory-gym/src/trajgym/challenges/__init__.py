"""Challenge registry and lifecycle management."""

from .manager import ChallengeManager
from .registry import ChallengeInfo, ChallengeRegistry

__all__ = ["ChallengeInfo", "ChallengeManager", "ChallengeRegistry"]
