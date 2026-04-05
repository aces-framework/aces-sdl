"""Training modules for SFT, online RL, and GEPA stages.

Imports are lazy to avoid requiring all dependencies (e.g. trl,
skyrl, dspy) when only one training stage is used.

SFT:  TRL-based supervised fine-tuning
online RL: SkyRL-based online reinforcement learning (Online RL/RLOO variants)
GEPA: DSPy-based prompt evolution (no weight updates)
"""

import logging

__all__ = [
    "train_sft",
    "train_online_rl",
    "run_gepa",
    "check_wandb_available",
]

logger = logging.getLogger(__name__)


def check_wandb_available(report_to: str) -> str:
    """Validate the ``report_to`` backend is usable, fall back to ``"none"``.

    - ``"none"`` / ``"tensorboard"`` / ``"console"``: always returned as-is.
    - ``"wandb"``: validated (import + API key check); falls back to ``"none"``.
    """
    if report_to in ("none", "tensorboard", "console"):
        return report_to
    if report_to == "wandb":
        try:
            import wandb

            if not wandb.api.api_key:
                logger.info("wandb installed but no API key configured, disabling")
                return "none"
        except (ImportError, AttributeError):
            logger.info("wandb not available, disabling")
            return "none"
    return report_to


def _import_online_rl():
    from .online_rl import train_online_rl

    return train_online_rl


def __getattr__(name):
    if name == "train_sft":
        from .sft import train_sft

        return train_sft
    if name == "train_online_rl":
        train_online_rl = _import_online_rl()
        return train_online_rl
    if name == "run_gepa":
        from .gepa import run_gepa

        return run_gepa
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
