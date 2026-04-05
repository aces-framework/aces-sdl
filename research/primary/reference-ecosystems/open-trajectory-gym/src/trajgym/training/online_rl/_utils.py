"""Shared utilities for online RL training modules.

Constants, config parsers, and runtime detection helpers used across
config_builder, data_converter, and the runtime orchestrator.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Canonical difficulty ordering for curriculum filtering.
_DIFFICULTY_ORDER: list[str] = [
    "very_easy",
    "easy",
    "medium",
    "hard",
    "expert",
    "master",
]
_DIFFICULTY_RANK: dict[str, int] = {d: i for i, d in enumerate(_DIFFICULTY_ORDER)}

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_CONFIGS_DIR = _PROJECT_ROOT / "src" / "trajgym" / "training" / "online_rl_templates"


def _as_positive_int(name: str, raw_value: Any, default: int) -> int:
    """Parse a positive int config value with warning-backed fallback."""
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r; defaulting to %d.", name, raw_value, default)
        return default
    if value <= 0:
        logger.warning(
            "Invalid %s=%r (must be >0); defaulting to %d.", name, raw_value, default
        )
        return default
    return value


def _as_float(name: str, raw_value: Any, default: float) -> float:
    """Parse a float config value with warning-backed fallback."""
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r; defaulting to %s.", name, raw_value, default)
        return default


def _detect_visible_gpu_count() -> int | None:
    """Best-effort count of GPUs visible to the current process."""
    visible = os.getenv("CUDA_VISIBLE_DEVICES")
    if visible is not None:
        stripped = visible.strip()
        if not stripped or stripped == "-1":
            return 0
        devices = [chunk.strip() for chunk in stripped.split(",") if chunk.strip()]
        if devices:
            return len(devices)

    try:
        import torch
    except Exception:
        return None

    try:
        if not torch.cuda.is_available():
            return 0
        return int(torch.cuda.device_count())
    except Exception:
        return None


def _flash_attn_available() -> bool:
    """Return True if flash-attn exports the symbols Transformers expects."""
    try:
        import flash_attn  # type: ignore
    except Exception:
        return False
    return all(
        hasattr(flash_attn, attr)
        for attr in ("flash_attn_func", "flash_attn_varlen_func")
    )


def _is_qwen3_5_config(hf_cfg: Any) -> bool:
    """Return True if a HF config appears to be Qwen3.5."""
    model_type = str(getattr(hf_cfg, "model_type", "")).lower()
    cfg_cls_name = str(hf_cfg.__class__.__name__).lower()
    architectures = [
        str(arch).lower() for arch in (getattr(hf_cfg, "architectures", None) or [])
    ]
    return (
        "qwen3_5" in model_type
        or "qwen3_5" in cfg_cls_name
        or any("qwen3_5" in arch for arch in architectures)
    )


def _missing_qwen3_5_fast_path_deps() -> list[str]:
    """Return missing Qwen3.5 linear-attention fast-path dependencies.

    Qwen3.5 uses flash linear attention (`fla`) and causal-conv1d for
    optimized linear-attention blocks. If missing, Transformers falls back
    to a slow torch path (`torch_chunk_gated_delta_rule`) that is unstable
    for long-horizon online RL workloads.
    """
    missing = []
    try:
        from transformers.utils.import_utils import (
            is_causal_conv1d_available,
            is_flash_linear_attention_available,
        )

        if not is_flash_linear_attention_available():
            missing.append("flash-linear-attention (module: fla)")
        if not is_causal_conv1d_available():
            missing.append("causal-conv1d")
        return missing
    except Exception:
        # Fallback for older Transformers that may not expose these helpers.
        if importlib.util.find_spec("fla") is None:
            missing.append("flash-linear-attention (module: fla)")
        if importlib.util.find_spec("causal_conv1d") is None:
            missing.append("causal-conv1d")
        return missing


def _validate_qwen3_5_runtime_dependencies(
    hf_cfg: Any,
    online_rl_cfg: dict[str, Any],
) -> None:
    """Fail fast when Qwen3.5 runtime dependencies are missing."""
    if not _is_qwen3_5_config(hf_cfg):
        return

    missing = _missing_qwen3_5_fast_path_deps()
    if not missing:
        return

    missing_str = ", ".join(missing)
    msg = (
        "Qwen3.5 detected but required linear-attention runtime deps are "
        f"missing: {missing_str}. Install with: "
        "`uv sync --extra online_rl --frozen` (preferred) or "
        "`pip install --no-deps flash-linear-attention==0.4.1 causal-conv1d==1.6.0`. "
        "Without these libs, Transformers falls back to torch linear-attention "
        "kernels that are unstable for long-context online RL."
    )
    strict = bool(online_rl_cfg.get("require_fast_linear_attention", True))
    if strict:
        raise RuntimeError(
            msg
            + " To bypass temporarily, set online_rl.require_fast_linear_attention=false "
            "(not recommended for production)."
        )
    logger.warning(
        "%s Proceeding because online_rl.require_fast_linear_attention=false.",
        msg,
    )
