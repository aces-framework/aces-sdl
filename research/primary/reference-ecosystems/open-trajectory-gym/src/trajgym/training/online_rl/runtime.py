"""SkyRL-backed stage-2 online RL implementation.

This module is the online-RL pipeline orchestrator: env registration,
trainer launch, and top-level ``train_online_rl`` entry point.

Sub-modules handle the heavy lifting:
- ``_utils``: shared constants and runtime-detection helpers
- ``config_builder``: SkyRL config dict construction
- ``data_converter``: Online RL JSONL → SkyRL format conversion
"""

import json
import logging
import os
from typing import Any

import yaml

from trajgym.training.online_rl._utils import (  # noqa: F401 — re-exported
    _DIFFICULTY_ORDER,
    _DIFFICULTY_RANK,
    _is_qwen3_5_config,
    _validate_qwen3_5_runtime_dependencies,
)
from trajgym.training.online_rl.config_builder import (  # noqa: F401 — re-exported
    _build_skyrl_config,
    _has_step_wise_resp_index_guard,
    _validate_step_wise_resp_index_guard,
)
from trajgym.training.online_rl.data_converter import _convert_online_rl_data  # noqa: F401

logger = logging.getLogger(__name__)


def _resolve_online_rl_cfg(config: dict[str, Any]) -> dict[str, Any]:
    """Return canonical ``online_rl`` config section."""
    preferred = config.get("online_rl")
    if isinstance(preferred, dict):
        return preferred
    return {}




def _resolve_reward_config(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize reward config and enforce a dict payload."""
    reward_cfg = config.get("reward")
    if reward_cfg is None:
        logger.info("No reward config provided; using default Reward weights.")
        return {}
    if not isinstance(reward_cfg, dict):
        raise TypeError(
            f"config['reward'] must be a dict if provided, got {type(reward_cfg).__name__}."
        )
    return reward_cfg


def _should_force_legacy_inference(
    model_path: str,
    *,
    allow_qwen35_new_inference: bool = False,
) -> bool:
    """Return True when SkyRL new inference should be disabled for model config.

    SkyRL's new inference server path currently initializes vLLM renderers in a
    way that can mis-handle some HuggingFace text-wrapper configs (for example
    Qwen3_5TextConfig). When this happens, vLLM raises a config type mismatch in
    multimodal processor setup before training starts.
    """
    try:
        from transformers import AutoConfig

        hf_cfg = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
    except Exception as exc:
        logger.warning(
            "Could not inspect model config for inference backend selection: %s",
            exc,
        )
        return False

    cfg_cls_name = hf_cfg.__class__.__name__
    if cfg_cls_name.endswith("TextConfig"):
        logger.warning(
            "Model config class %s detected at %s. Forcing SkyRL legacy "
            "inference path (new inference is incompatible with text-wrapper configs).",
            cfg_cls_name,
            model_path,
        )
        return True
    if _is_qwen3_5_config(hf_cfg) and not allow_qwen35_new_inference:
        logger.warning(
            "Qwen3.5 config detected at %s. Forcing SkyRL legacy inference path "
            "(new inference shows intermittent /inference/v1/generate 400s and "
            "engine-core exits on this stack). Set "
            "online_rl.allow_new_inference_for_qwen35=true to override.",
            model_path,
        )
        return True
    return False


def _resolve_vllm_ready_model_path(model_path: str) -> str:
    """Resolve a vLLM-compatible model handoff path for online RL.

    Qwen3.5 merged checkpoints used for HF training can expose a text-wrapper
    config (for example ``model_type=qwen3_5_text``). SkyRL+vLLM runtime paths
    expect the vLLM-ready variant (for example sibling ``*_vllm`` directory).
    """
    try:
        from transformers import AutoConfig

        cfg = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
    except Exception as exc:
        logger.warning("Could not inspect model config at %s: %s", model_path, exc)
        return model_path

    cfg_cls_name = cfg.__class__.__name__
    cfg_model_type = str(getattr(cfg, "model_type", ""))
    looks_text_wrapper = cfg_cls_name.endswith("TextConfig") or cfg_model_type.endswith(
        "_text"
    )
    if not looks_text_wrapper:
        return model_path

    candidate = f"{model_path.rstrip('/')}_vllm"
    if os.path.isdir(candidate):
        try:
            from transformers import AutoConfig

            cand_cfg = AutoConfig.from_pretrained(candidate, trust_remote_code=True)
            cand_cls_name = cand_cfg.__class__.__name__
            cand_model_type = str(getattr(cand_cfg, "model_type", ""))
            cand_is_text_wrapper = cand_cls_name.endswith(
                "TextConfig"
            ) or cand_model_type.endswith("_text")
            if not cand_is_text_wrapper:
                logger.warning(
                    "Model path %s uses text-wrapper config (%s/%s). "
                    "Auto-switching ONLINE_RL runtime model to sibling vLLM-ready path: %s",
                    model_path,
                    cfg_model_type or "<unknown_model_type>",
                    cfg_cls_name,
                    candidate,
                )
                return candidate
        except Exception as exc:
            logger.warning(
                "Failed to validate sibling vLLM model path %s: %s", candidate, exc
            )

    logger.warning(
        "Model path %s appears to use text-wrapper config (%s/%s) and no validated "
        "sibling '*_vllm' path was found. ONLINE_RL runtime may fail in vLLM.",
        model_path,
        cfg_model_type or "<unknown_model_type>",
        cfg_cls_name,
    )
    return model_path


def _setup_persistent_logging(output_dir: str) -> None:
    """Configure file-based logging to ``{output_dir}/training.log``.

    Adds a FileHandler to the root logger so that all log output
    (including SkyRL, vLLM, and our own modules) is captured in a
    persistent file alongside the usual console output.
    """
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "training.log")
    handler = logging.FileHandler(log_path, mode="a")
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logging.getLogger().addHandler(handler)
    logger.info("Persistent training log: %s", log_path)


def train_online_rl(
    model_path: str,
    data_path: str,
    output_dir: str,
    config: dict[str, Any],
    resume_from: str | None = None,
    challenge_registry: str | None = None,
    agent_class: str | None = None,
) -> str:
    """Run stage-2 online RL training via SkyRL.

    Uses TrajGymTextEnv (SkyRL-Gym BaseTextEnv subclass) with ToolExecutor
    for direct tool execution (no HTTP server needed).

    The reward function is reconstructed inside each SkyRL env instance
    from ``config["reward"]`` (a serializable dict). This avoids passing
    non-serializable callables through Ray.

    Args:
        model_path: Path to the SFT model (merged directory).
        data_path: Path to online-RL JSONL data with ground_truth_flag.
        output_dir: Directory for checkpoints and final model.
        config: Merged config dict from training.yaml.
        resume_from: Optional checkpoint path to resume from.

    Returns:
        Path to the saved final model directory.
    """
    model_path = _resolve_vllm_ready_model_path(model_path)

    # Set up persistent file logging before any other output.
    os.makedirs(output_dir, exist_ok=True)
    _setup_persistent_logging(output_dir)

    logger.info("=" * 60)
    logger.info("ONLINE RL TRAINING (SkyRL)")
    logger.info("  Model:  %s", model_path)
    logger.info("  Data:   %s", data_path)
    logger.info("  Output: %s", output_dir)
    logger.info("=" * 60)

    # 1. Convert data to SkyRL format
    online_rl_cfg = _resolve_online_rl_cfg(config)
    registry = None
    target_map_path = (
        os.getenv("TRAJGYM_TARGET_MAP_PATH")
        or online_rl_cfg.get("target_map_path")
        or None
    )
    if challenge_registry:
        from trajgym.challenges.registry import ChallengeRegistry

        registry = ChallengeRegistry(challenge_registry)
        if target_map_path:
            strict_map = bool(int(os.getenv("TRAJGYM_TARGET_MAP_STRICT", "0"))) or bool(
                online_rl_cfg.get("target_map_strict", False)
            )
            registry.load_target_overrides(str(target_map_path), strict=strict_map)
    drop_unresolved = bool(online_rl_cfg.get("drop_unresolved_registry_samples", True))
    port_offset = int(
        os.getenv(
            "TRAJGYM_TARGET_PORT_OFFSET",
            str(online_rl_cfg.get("target_port_offset", 0)),
        )
    )
    host_override = (
        os.getenv("TRAJGYM_TARGET_HOST_OVERRIDE")
        or online_rl_cfg.get("target_host_override")
        or None
    )
    prefer_registry_target = bool(
        online_rl_cfg.get("prefer_registry_target", bool(target_map_path))
    )
    converted_data = _convert_online_rl_data(
        data_path,
        output_dir,
        registry=registry,
        drop_unresolved_registry_samples=drop_unresolved,
        drop_static_challenges=bool(online_rl_cfg.get("drop_static_challenges", True)),
        max_samples=online_rl_cfg.get("max_samples"),
        max_samples_per_challenge=online_rl_cfg.get("max_samples_per_challenge"),
        target_port_offset=port_offset,
        target_host_override=host_override,
        fail_on_target_collisions=bool(
            online_rl_cfg.get("fail_on_target_collisions", False)
        ),
        fail_on_flag_mismatch=bool(online_rl_cfg.get("fail_on_flag_mismatch", True)),
        fail_on_missing_registry_flag=bool(
            online_rl_cfg.get("fail_on_missing_registry_flag", True)
        ),
        require_all_registry_challenges=bool(
            online_rl_cfg.get("require_all_registry_challenges", False)
        ),
        prefer_registry_target=prefer_registry_target,
        difficulty_min=online_rl_cfg.get("difficulty_min"),
        difficulty_max=online_rl_cfg.get("difficulty_max"),
        exclude_challenge_ids=online_rl_cfg.get("exclude_challenge_ids"),
    )

    # 2. Build SkyRL config
    skyrl_config = _build_skyrl_config(model_path, output_dir, config, converted_data)

    if resume_from:
        skyrl_config["trainer"]["resume_path"] = resume_from
        skyrl_config["trainer"]["resume_mode"] = "from_path"

    # 3. Write config for reference
    os.makedirs(output_dir, exist_ok=True)
    config_path = os.path.join(output_dir, "skyrl_config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(skyrl_config, f, default_flow_style=False)
    logger.info("SkyRL config written to %s", config_path)

    # 4. Launch SkyRL training
    reward_config = _resolve_reward_config(config)
    use_new_inference = bool(online_rl_cfg.get("use_new_inference", False))
    allow_qwen35_new_inference = bool(
        online_rl_cfg.get("allow_new_inference_for_qwen35", False)
    )
    if use_new_inference and _should_force_legacy_inference(
        model_path,
        allow_qwen35_new_inference=allow_qwen35_new_inference,
    ):
        use_new_inference = False

    # Trajectory logging: pass output_dir through env kwargs (Ray-serializable string).
    logging_cfg = config.get("online_rl_logging", {})
    enable_trajectory_logging = bool(logging_cfg.get("enable_trajectory_logging", True))
    require_trajectory_files = bool(logging_cfg.get("require_trajectory_files", False))
    trajectory_output_dir = output_dir if enable_trajectory_logging else None

    # Agent class from CLI flag > config file > DefaultStepAgent fallback.
    resolved_agent_class = (
        agent_class
        or online_rl_cfg.get("agent_class")
        or "trajgym.agent.default_agent.DefaultStepAgent"
    )
    resolved_agent_kwargs = online_rl_cfg.get("agent_kwargs", {})
    if not isinstance(resolved_agent_kwargs, dict):
        resolved_agent_kwargs = {}
    else:
        resolved_agent_kwargs = dict(resolved_agent_kwargs)
    resolved_agent_kwargs.setdefault("tokenizer_name_or_path", str(model_path))
    if resolved_agent_class:
        logger.info("Using custom StepAgent class: %s", resolved_agent_class)
    if isinstance(resolved_agent_kwargs, dict) and resolved_agent_kwargs:
        logger.info(
            "Using StepAgent kwargs keys: %s",
            ", ".join(sorted(str(k) for k in resolved_agent_kwargs)),
        )
        runtime_cmd = resolved_agent_kwargs.get("runtime_cmd")
        if runtime_cmd:
            logger.info("Hybrid BYO runtime enabled via runtime_cmd: %s", runtime_cmd)
    pytorch_cuda_alloc_conf = online_rl_cfg.get("pytorch_cuda_alloc_conf")
    horizon_schedule = online_rl_cfg.get("horizon_schedule")
    hard_mask_statuses = online_rl_cfg.get("hard_mask_statuses")
    try:
        positive_only_until_step = int(
            online_rl_cfg.get("positive_only_until_step", 0) or 0
        )
    except (TypeError, ValueError):
        logger.warning(
            "Invalid online_rl.positive_only_until_step=%r; defaulting to 0.",
            online_rl_cfg.get("positive_only_until_step"),
        )
        positive_only_until_step = 0
    try:
        positive_only_reward_floor = float(
            online_rl_cfg.get("positive_only_reward_floor", 0.0) or 0.0
        )
    except (TypeError, ValueError):
        logger.warning(
            "Invalid online_rl.positive_only_reward_floor=%r; defaulting to 0.0.",
            online_rl_cfg.get("positive_only_reward_floor"),
        )
        positive_only_reward_floor = 0.0
    try:
        _run_skyrl_training(
            skyrl_config,
            reward_config,
            agent_class=resolved_agent_class,
            agent_kwargs=resolved_agent_kwargs,
            use_new_inference=use_new_inference,
            trajectory_output_dir=trajectory_output_dir,
            pytorch_cuda_alloc_conf=pytorch_cuda_alloc_conf,
            horizon_schedule=horizon_schedule,
            hard_mask_statuses=hard_mask_statuses,
            positive_only_until_step=positive_only_until_step,
            positive_only_reward_floor=positive_only_reward_floor,
        )
    except ImportError:
        logger.error(
            "SkyRL not installed. See docs/quickstart.md for fork installation instructions."
        )
        raise

    if trajectory_output_dir and require_trajectory_files:
        trajectories_dir = os.path.join(trajectory_output_dir, "trajectories")
        has_step_files = False
        has_summary = False
        if os.path.isdir(trajectories_dir):
            for name in os.listdir(trajectories_dir):
                if name.startswith("step_") and name.endswith(".jsonl"):
                    has_step_files = True
                elif name == "step_summaries.jsonl":
                    has_summary = True
        if not (has_step_files or has_summary):
            raise RuntimeError(
                "Trajectory logging enabled but no trajectory artifacts were produced "
                f"under {trajectories_dir}. This indicates an invalid training run."
            )

    # Save challenge scoreboard after training completes.
    if trajectory_output_dir:
        try:
            from .trajectory_logger import TrajectoryLogger

            tb_dir = os.environ.get("TENSORBOARD_LOGDIR")
            tl = TrajectoryLogger(trajectory_output_dir, tensorboard_dir=tb_dir)
            tl.save_scoreboard()
            latest_step = 0
            summary_path = os.path.join(
                trajectory_output_dir, "trajectories", "step_summaries.jsonl"
            )
            if os.path.exists(summary_path):
                with open(summary_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            latest_step = int(
                                json.loads(line).get("global_step", latest_step)
                            )
                        except (TypeError, ValueError, json.JSONDecodeError):
                            continue
            tl.flush_scoreboard_to_tensorboard(global_step=latest_step)
            tl.close()
        except Exception as exc:
            logger.warning("Failed to save final scoreboard: %s", exc)

    logger.info("Online RL training complete. Output: %s", output_dir)

    final_dir = os.path.join(output_dir, "final")
    if os.path.exists(final_dir):
        return final_dir
    return output_dir


def _run_skyrl_training(
    config: dict[str, Any],
    reward_config: dict[str, Any],
    agent_class: str | None = None,
    agent_kwargs: dict[str, Any] | None = None,
    use_new_inference: bool = False,
    trajectory_output_dir: str | None = None,
    pytorch_cuda_alloc_conf: str | None = None,
    horizon_schedule: dict[str, Any] | None = None,
    hard_mask_statuses: list[str] | None = None,
    positive_only_until_step: int = 0,
    positive_only_reward_floor: float = 0.0,
) -> None:
    """Launch SkyRL training with the given config.

    Uses SkyRL's Python API (BasePPOExp). The environment is registered
    inside a Ray remote task so Ray workers can access it.

    Args:
        config: SkyRL config dict.
        reward_config: Serializable reward weight dict (reconstructed
            into Reward inside each env instance).
        agent_class: Dotted path to a StepAgent class (Ray-safe string).
        agent_kwargs: Dict of primitives for the StepAgent constructor.
        trajectory_output_dir: Output directory for trajectory JSONL logs.
            Passed through as a string (Ray-serializable) to each env instance.

    Key: exp.run() already calls asyncio.run() internally -- do NOT wrap
    in another asyncio.run().
    """
    import ray
    from omegaconf import OmegaConf

    # Convert dict to OmegaConf DictConfig (SkyRL expects this)
    cfg = OmegaConf.create(config)

    # Import SkyRL utilities
    from skyrl_train.entrypoints.main_base import validate_cfg
    from skyrl_train.utils import initialize_ray

    def _build_trajgym_env_kwargs(
        cfg_obj: Any,
        reward_cfg: dict[str, Any],
        *,
        agent_cls: str | None,
        agent_kw: dict[str, Any] | None,
        trajectory_dir: str | None,
        horizon: dict[str, Any] | None,
        hard_mask: list[str] | None,
        positive_until_step: int,
        positive_reward_floor: float,
    ) -> dict[str, Any]:
        """Build serializable kwargs passed to TrajGymTextEnv registration."""
        generator_max_turns = int(getattr(cfg_obj.generator, "max_turns", 15))
        env_kwargs: dict[str, Any] = {
            "reward_config": reward_cfg,
            "max_turns": generator_max_turns,
            # Pass the generator's max_turns as the authoritative iteration
            # limit so the env can clamp its own max_turns to match.  This
            # prevents done=True from never firing when SkyRL's agent_loop
            # terminates on sequence length before the env reaches its own
            # max_turns threshold.
            "max_tool_calling_iterations": generator_max_turns,
            # Context-budget safety net: env proactively triggers done=True
            # when estimated tokens reach 85% of this budget, ensuring
            # terminal Reward fires BEFORE SkyRL's agent_loop length-break.
            "max_input_length": int(getattr(cfg_obj.generator, "max_input_length", 0)),
            "step_wise_trajectories": bool(
                getattr(cfg_obj.generator, "step_wise_trajectories", False)
            ),
            "native_tool_schemas": bool(
                getattr(cfg_obj.generator, "native_tool_schemas", False)
            ),
        }
        tool_call_format = str(
            getattr(cfg_obj.generator, "tool_call_format", "") or ""
        ).strip()
        if tool_call_format:
            env_kwargs["tool_call_format"] = tool_call_format
        if horizon:
            env_kwargs["horizon_schedule"] = horizon
        if hard_mask:
            env_kwargs["hard_mask_statuses"] = hard_mask
        if int(positive_until_step) > 0:
            env_kwargs["positive_only_until_step"] = int(positive_until_step)
            env_kwargs["positive_only_reward_floor"] = float(positive_reward_floor)
        if agent_cls:
            env_kwargs["agent_class"] = agent_cls
        if agent_kw:
            env_kwargs["agent_kwargs"] = agent_kw
        if trajectory_dir:
            env_kwargs["trajectory_output_dir"] = trajectory_dir
        return env_kwargs

    # Validate config against SkyRLConfig schema
    validate_cfg(cfg)

    # SkyRL's Ray actors should run vLLM V1 with in-process worker handling.
    # Keep multiprocess disabled to avoid Ray actor engine bootstrap issues.
    os.environ.setdefault("VLLM_USE_V1", "1")
    os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")
    if pytorch_cuda_alloc_conf:
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = str(pytorch_cuda_alloc_conf)
        logger.info("Set PYTORCH_CUDA_ALLOC_CONF=%s", pytorch_cuda_alloc_conf)
    # Use SkyRL's new HTTP inference layer when requested.
    # This avoids legacy Ray-wrapped vLLM LoRA startup issues on Qwen3.5.
    os.environ["_SKYRL_USE_NEW_INFERENCE"] = "1" if use_new_inference else "0"
    if use_new_inference:
        logger.info("Enabled SkyRL new inference layer (_SKYRL_USE_NEW_INFERENCE=1)")

    # Initialize Ray cluster.
    # GPU isolation: when CUDA_VISIBLE_DEVICES is set (e.g. "1"), Ray only
    # discovers those GPUs.  The legacy inference path creates a local vLLM
    # Ray actor that claims GPU 0 (via Ray's placement group), naturally
    # reserving GPU 1 for the trainer.  The new inference path with
    # external_server_urls does NOT create a vLLM actor, so the trainer is
    # the only GPU consumer and gets placed on whichever GPU Ray picks.
    _cuda_vis = os.environ.get("CUDA_VISIBLE_DEVICES")
    _external_urls = config.get("generator", {}).get("external_server_urls")
    print(
        f"[GPU_ISOLATION] CUDA_VISIBLE_DEVICES={_cuda_vis!r}, "
        f"external_urls={bool(_external_urls)}, "
        f"use_new_inference={use_new_inference}",
        flush=True,
    )
    initialize_ray(cfg)

    # Register env and run training inside a Ray remote task.
    # This ensures the env registration is visible to Ray workers.
    @ray.remote(num_cpus=1)
    def _skyrl_entrypoint(
        cfg_dict,
        reward_config,
        agent_class,
        agent_kwargs,
        use_new_inference,
        trajectory_output_dir,
        pytorch_cuda_alloc_conf,
        horizon_schedule,
        hard_mask_statuses,
        positive_only_until_step,
        positive_only_reward_floor,
    ):
        import os as _os

        _os.environ["VLLM_USE_V1"] = "1"
        _os.environ["VLLM_ENABLE_V1_MULTIPROCESSING"] = "0"
        if pytorch_cuda_alloc_conf:
            _os.environ["PYTORCH_CUDA_ALLOC_CONF"] = str(pytorch_cuda_alloc_conf)
        _os.environ["_SKYRL_USE_NEW_INFERENCE"] = "1" if use_new_inference else "0"

        from omegaconf import OmegaConf
        from skyrl_gym.envs import register
        from skyrl_train.entrypoints.main_base import BasePPOExp

        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        cfg = OmegaConf.create(cfg_dict)

        # Register TrajGymTextEnv with serializable kwargs only.
        # reward_config is a plain dict of floats -- JSON-safe for SkyRL's
        # EnvSpec._check_can_jsonify(). The env reconstructs Reward
        # from this config in __init__().
        # agent_class is a dotted path string (Ray-safe).
        # agent_kwargs is a dict of primitives (Ray-safe).
        env_kwargs = _build_trajgym_env_kwargs(
            cfg,
            reward_config,
            agent_cls=agent_class,
            agent_kw=agent_kwargs,
            trajectory_dir=trajectory_output_dir,
            horizon=horizon_schedule,
            hard_mask=hard_mask_statuses,
            positive_until_step=positive_only_until_step,
            positive_reward_floor=positive_only_reward_floor,
        )

        register(
            id="trajgym",
            entry_point=TrajGymTextEnv,
            kwargs=env_kwargs,
        )

        exp = BasePPOExp(cfg)
        exp.run()  # Already calls asyncio.run() internally

    # Convert back to dict for serialization through Ray
    cfg_dict = OmegaConf.to_container(cfg, resolve=True)
    ray.get(
        _skyrl_entrypoint.remote(
            cfg_dict,
            reward_config,
            agent_class,
            agent_kwargs or {},
            use_new_inference,
            trajectory_output_dir,
            pytorch_cuda_alloc_conf,
            horizon_schedule,
            hard_mask_statuses,
            positive_only_until_step,
            positive_only_reward_floor,
        )
    )
