"""SkyRL configuration builder for online RL training.

Handles all SkyRL config dict construction: vLLM parameters, LoRA setup,
generator topology, chat template resolution, FSDP wrapping, and final
config assembly with defaults merging.
"""

import importlib.util
import logging
import os
import re
from pathlib import Path
from typing import Any

from trajgym.training.online_rl._utils import (
    _CONFIGS_DIR,
    _as_float,
    _as_positive_int,
    _detect_visible_gpu_count,
    _flash_attn_available,
    _is_qwen3_5_config,
    _validate_qwen3_5_runtime_dependencies,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# LoRA helpers
# ------------------------------------------------------------------


def _parse_lora_rank(lora_cfg: dict[str, Any]) -> int:
    """Parse LoRA rank from config with a defensive fallback."""
    raw_rank = lora_cfg.get("r", 64)
    try:
        return int(raw_rank)
    except (TypeError, ValueError):
        logger.warning("Invalid lora.r=%r; defaulting to rank 64.", raw_rank)
        return 64


def _normalize_module_filter(raw_modules: Any, *, default: str | None) -> Any:
    """Normalize LoRA target/exclude module filters for SkyRL + PEFT."""
    if raw_modules is None:
        return default

    if isinstance(raw_modules, str):
        value = raw_modules.strip()
        if not value:
            return default
        if value == "all-linear":
            return value
        if "," in value:
            modules = [part.strip() for part in value.split(",") if part.strip()]
            return modules or default
        return [value]

    if isinstance(raw_modules, (list, tuple, set)):
        modules = [str(module).strip() for module in raw_modules if str(module).strip()]
        return modules or default

    value = str(raw_modules).strip()
    if not value:
        return default
    if value == "all-linear":
        return value
    return [value]


def _parse_lora_modules(lora_cfg: dict[str, Any]) -> tuple[Any, Any]:
    """Parse LoRA target/exclude module filters from config."""
    target_modules = _normalize_module_filter(
        lora_cfg.get("target_modules"),
        default="all-linear",
    )
    exclude_modules = _normalize_module_filter(
        lora_cfg.get("exclude_modules"),
        default=None,
    )
    return target_modules, exclude_modules


# ------------------------------------------------------------------
# Policy loss type
# ------------------------------------------------------------------


def _resolve_policy_loss_type(online_rl_cfg: dict[str, Any]) -> str:
    """Resolve SkyRL ``policy_loss_type`` with backward-compatible aliases."""
    raw_policy = online_rl_cfg.get("policy_loss_type")
    if raw_policy is not None and str(raw_policy).strip():
        return str(raw_policy).strip()

    raw_legacy = online_rl_cfg.get("loss_type")
    if raw_legacy is None:
        return "regular"

    legacy = str(raw_legacy).strip().lower()
    alias_map = {
        "dapo": "regular",
        "online_rl": "regular",
        "ppo": "regular",
    }
    mapped = alias_map.get(legacy, legacy)
    if mapped != legacy:
        logger.info(
            "Mapping online_rl.loss_type=%r -> policy_loss_type=%r for SkyRL compatibility.",
            raw_legacy,
            mapped,
        )
    return mapped


# ------------------------------------------------------------------
# Network / topology helpers
# ------------------------------------------------------------------


def _normalize_remote_url(url: str) -> str:
    """Normalize remote vLLM URL to SkyRL host:port format."""
    return re.sub(r"^https?://", "", str(url).strip()).rstrip("/")


def _resolve_generator_topology(
    online_rl_cfg: dict[str, Any], lora_rank: int
) -> dict[str, Any]:
    """Resolve SkyRL generator topology from config."""
    vllm_mode = str(online_rl_cfg.get("vllm_mode", "colocate")).strip().lower()
    requested_remote_url = online_rl_cfg.get("vllm_server_url")
    remote_requested = bool(requested_remote_url)

    local_disagg_modes = {
        "server",
        "disagg",
        "disaggregated",
        "non_colocate",
        "non-colocate",
    }
    valid_modes = {"colocate", "local"} | local_disagg_modes
    if vllm_mode not in valid_modes:
        logger.warning(
            "Unknown online_rl.vllm_mode=%r; defaulting to 'colocate'.", vllm_mode
        )
        vllm_mode = "colocate"

    allow_remote_lora = bool(online_rl_cfg.get("allow_remote_lora", False))
    if remote_requested and lora_rank > 0 and not allow_remote_lora:
        logger.warning(
            "online_rl.vllm_server_url=%r requested with LoRA rank=%d. "
            "SkyRL remote engines do not support NCCL LoRA weight sync; "
            "falling back to local non-colocated vLLM engines. "
            "Set online_rl.allow_remote_lora=true to keep remote mode "
            "(requires patch_skyrl_weight_sync.py for file-based sync).",
            requested_remote_url,
            lora_rank,
        )
        remote_requested = False
        vllm_mode = "server"
    elif remote_requested and lora_rank > 0 and allow_remote_lora:
        logger.info(
            "Remote vLLM + LoRA: using file-based weight sync "
            "(online_rl.allow_remote_lora=true). Ensure patch_skyrl_weight_sync.py "
            "is applied and vLLM server supports /v1/load_lora_adapter."
        )

    run_engines_locally = not remote_requested
    colocate_all = run_engines_locally and vllm_mode in {"colocate", "local"}
    remote_urls = (
        [_normalize_remote_url(requested_remote_url)]
        if remote_requested
        else ["127.0.0.1:8001"]
    )

    external_proxy = str(requested_remote_url).strip() if remote_requested else None
    external_servers = [str(requested_remote_url).strip()] if remote_requested else None

    return {
        "remote_vllm": remote_requested,
        "run_engines_locally": run_engines_locally,
        "colocate_all": colocate_all,
        "weight_sync_backend": "broadcast" if remote_requested else "nccl",
        "remote_inference_engine_urls": remote_urls,
        "external_proxy_url": external_proxy,
        "external_server_urls": external_servers,
    }


# ------------------------------------------------------------------
# SkyRL logger
# ------------------------------------------------------------------


def _resolve_skyrl_logger(report_to: str, output_dir: str) -> str:
    """Map our ``report_to`` config value to a SkyRL logger backend name."""
    import contextlib

    value = str(report_to).strip().lower()

    _VALID_SKYRL_LOGGERS = {"wandb", "mlflow", "swanlab", "tensorboard", "console"}

    if value in ("none", "", "null"):
        return "console"

    if value == "tensorboard":
        tb_dir = os.path.join(output_dir, "tensorboard")
        with contextlib.suppress(OSError):
            os.makedirs(tb_dir, exist_ok=True)
        os.environ["TENSORBOARD_DIR"] = tb_dir
        os.environ["TENSORBOARD_LOGDIR"] = tb_dir
        return "tensorboard"

    if value in _VALID_SKYRL_LOGGERS:
        return value

    logger.warning(
        "Unrecognized report_to=%r; falling back to 'console'. Valid options: %s",
        report_to,
        sorted(_VALID_SKYRL_LOGGERS),
    )
    return "console"


# ------------------------------------------------------------------
# Step-wise guard validation
# ------------------------------------------------------------------


def _has_step_wise_resp_index_guard(source: str) -> bool:
    """Return True when SkyRL step-wise reward writes are bounds-guarded."""
    guarded_patterns = [
        r"if\s+0\s*<=\s*resp_end_idx\s*<\s*len\(per_token_reward\)\s*:\s*[\r\n]+\s*per_token_reward\[resp_end_idx\]\s*=\s*float\(reward\)",
        r"per_token_reward\[\s*max\(\s*0\s*,\s*min\(\s*resp_end_idx\s*,\s*len\(per_token_reward\)\s*-\s*1\s*\)\s*\)\s*\]\s*=",
    ]
    for pattern in guarded_patterns:
        if re.search(pattern, source, flags=re.MULTILINE):
            return True

    return (
        re.search(r"per_token_reward\[resp_end_idx\]\s*=\s*float\(reward\)", source)
        is None
    )


def _validate_step_wise_resp_index_guard(
    online_rl_cfg: dict[str, Any],
    step_wise_trajectories: bool,
) -> None:
    """Fail fast if SkyRL lacks the step-wise reward index guard patch."""
    if not step_wise_trajectories:
        return

    strict = bool(online_rl_cfg.get("require_step_wise_index_guard", True))
    spec = importlib.util.find_spec("skyrl_train.generators.skyrl_gym_generator")
    origin = getattr(spec, "origin", None) if spec is not None else None
    if not origin:
        logger.warning(
            "Could not locate skyrl_train.generators.skyrl_gym_generator; "
            "skipping step-wise index guard validation."
        )
        return

    source_path = Path(origin)
    try:
        source = source_path.read_text()
    except Exception as exc:
        msg = (
            "Failed to read SkyRL generator source while validating step-wise "
            f"index guard ({source_path}): {exc}"
        )
        if strict:
            raise RuntimeError(msg) from exc
        logger.warning(
            "%s Proceeding because online_rl.require_step_wise_index_guard=false.",
            msg,
        )
        return

    if _has_step_wise_resp_index_guard(source):
        return

    msg = (
        "SkyRL step-wise reward index guard is missing. This can crash training "
        "with IndexError in skyrl_gym_generator.py when resp_end_idx exceeds "
        "per_token_reward bounds. Apply docker/patches/apply_all_patches.sh "
        "or set online_rl.require_step_wise_index_guard=false to bypass."
    )
    if strict:
        raise RuntimeError(msg)
    logger.warning(
        "%s Proceeding because online_rl.require_step_wise_index_guard=false.",
        msg,
    )


# ------------------------------------------------------------------
# SkyRL defaults loading
# ------------------------------------------------------------------


def _load_skyrl_defaults() -> dict[str, Any]:
    """Load SkyRL's default config as a base dict."""
    skyrl_defaults: dict[str, Any] = {}
    try:
        from dataclasses import asdict

        from skyrl_train.config.config import SkyRLConfig

        skyrl_defaults = asdict(SkyRLConfig())
    except (ImportError, ModuleNotFoundError):
        pass
    if not skyrl_defaults:
        try:
            import importlib.resources as pkg_resources

            from omegaconf import OmegaConf as _OC

            cfg_dir = Path(pkg_resources.files("skyrl_train") / "config")
            base_yaml = cfg_dir / "ppo_base_config.yaml"
            if base_yaml.exists():
                raw = _OC.load(base_yaml)
                skyrl_defaults = _OC.to_container(raw, resolve=False)
                logger.info("Loaded SkyRL base config from %s", base_yaml)
        except Exception as exc:
            logger.warning("Could not load SkyRL base config: %s", exc)
    return skyrl_defaults


# ------------------------------------------------------------------
# Resolve sub-config blocks
# ------------------------------------------------------------------


def _resolve_vllm_params(
    online_rl_cfg: dict[str, Any],
    model_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Resolve vLLM context-window, sequence, and batching parameters."""
    model_max_seq_length = _as_positive_int(
        "model.max_seq_length",
        model_cfg.get("max_seq_length"),
        8192,
    )
    max_completion_length = _as_positive_int(
        "online_rl.max_completion_length",
        online_rl_cfg.get("max_completion_length"),
        8192,
    )
    max_prompt_length = _as_positive_int(
        "online_rl.max_prompt_length",
        online_rl_cfg.get("max_prompt_length"),
        model_max_seq_length,
    )

    vllm_headroom_tokens = _as_positive_int(
        "online_rl.vllm_context_headroom_tokens",
        online_rl_cfg.get("vllm_context_headroom_tokens"),
        1024,
    )
    min_required_vllm_len = max_prompt_length + max_completion_length
    default_vllm_max_model_len = min(
        model_max_seq_length,
        min_required_vllm_len + vllm_headroom_tokens,
    )
    if default_vllm_max_model_len < min_required_vllm_len:
        default_vllm_max_model_len = min_required_vllm_len
    vllm_max_model_len = _as_positive_int(
        "online_rl.vllm_max_model_len",
        online_rl_cfg.get("vllm_max_model_len"),
        default_vllm_max_model_len,
    )
    if vllm_max_model_len < min_required_vllm_len:
        logger.warning(
            "online_rl.vllm_max_model_len=%d is smaller than max_prompt_length + "
            "max_completion_length (%d + %d = %d); overriding to %d.",
            vllm_max_model_len,
            max_prompt_length,
            max_completion_length,
            min_required_vllm_len,
            min_required_vllm_len,
        )
        vllm_max_model_len = min_required_vllm_len

    num_generations = _as_positive_int(
        "online_rl.num_generations",
        online_rl_cfg.get("num_generations"),
        8,
    )
    max_num_seqs = _as_positive_int(
        "online_rl.max_num_seqs",
        online_rl_cfg.get("max_num_seqs"),
        max(8, num_generations * 2),
    )
    if max_num_seqs < num_generations:
        logger.warning(
            "online_rl.max_num_seqs=%d is smaller than num_generations=%d; "
            "overriding max_num_seqs to %d.",
            max_num_seqs,
            num_generations,
            num_generations,
        )
        max_num_seqs = num_generations

    default_batched_tokens = min(
        32768,
        max(max_prompt_length, num_generations * max(1024, max_completion_length // 2)),
    )
    max_num_batched_tokens = _as_positive_int(
        "online_rl.max_num_batched_tokens",
        online_rl_cfg.get("max_num_batched_tokens"),
        default_batched_tokens,
    )
    if max_num_batched_tokens < max_prompt_length:
        logger.warning(
            "online_rl.max_num_batched_tokens=%d is smaller than max_prompt_length=%d; "
            "overriding to %d.",
            max_num_batched_tokens,
            max_prompt_length,
            max_prompt_length,
        )
        max_num_batched_tokens = max_prompt_length
    max_prefill_capacity = max_prompt_length * max_num_seqs
    if max_num_batched_tokens > max_prefill_capacity:
        logger.warning(
            "online_rl.max_num_batched_tokens=%d exceeds max_prefill_capacity=%d "
            "(max_prompt_length * max_num_seqs); clamping.",
            max_num_batched_tokens,
            max_prefill_capacity,
        )
        max_num_batched_tokens = max_prefill_capacity

    vllm_attention_backend = online_rl_cfg.get("vllm_attention_backend")
    if vllm_attention_backend is not None:
        vllm_attention_backend = str(vllm_attention_backend).strip() or None
    vllm_mm_encoder_attn_backend = online_rl_cfg.get("vllm_mm_encoder_attn_backend")
    if vllm_mm_encoder_attn_backend is not None:
        vllm_mm_encoder_attn_backend = str(vllm_mm_encoder_attn_backend).strip() or None

    return {
        "model_max_seq_length": model_max_seq_length,
        "max_completion_length": max_completion_length,
        "max_prompt_length": max_prompt_length,
        "vllm_max_model_len": vllm_max_model_len,
        "vllm_language_model_only": bool(
            online_rl_cfg.get("vllm_language_model_only", False)
        ),
        "vllm_attention_backend": vllm_attention_backend,
        "vllm_mm_encoder_attn_backend": vllm_mm_encoder_attn_backend,
        "num_generations": num_generations,
        "max_num_seqs": max_num_seqs,
        "max_num_batched_tokens": max_num_batched_tokens,
    }


def _resolve_generation_params(
    online_rl_cfg: dict[str, Any],
    remote_vllm: bool,
    chat_template_name: str | None,
) -> dict[str, Any]:
    """Resolve sampling / temperature / stop parameters for train and eval."""
    default_logprobs = None if remote_vllm else 0
    train_logprobs = online_rl_cfg.get("logprobs", default_logprobs)
    eval_logprobs = online_rl_cfg.get("eval_logprobs", train_logprobs)

    if chat_template_name and train_logprobs is not None:
        logger.warning(
            "Custom chat_template=%r set with logprobs=%r; forcing "
            "generator.sampling_params.logprobs=None for SkyRL compatibility.",
            chat_template_name,
            train_logprobs,
        )
        train_logprobs = None
    if chat_template_name and eval_logprobs is not None:
        logger.warning(
            "Custom chat_template=%r set with eval_logprobs=%r; forcing "
            "generator.eval_sampling_params.logprobs=None for SkyRL compatibility.",
            chat_template_name,
            eval_logprobs,
        )
        eval_logprobs = None

    generation_temperature = _as_float(
        "online_rl.generation_temperature",
        online_rl_cfg.get("generation_temperature"),
        1.0,
    )
    generation_top_p = _as_float(
        "online_rl.generation_top_p",
        online_rl_cfg.get("generation_top_p"),
        0.95,
    )
    generation_min_p = _as_float(
        "online_rl.generation_min_p",
        online_rl_cfg.get("generation_min_p"),
        0.0,
    )
    generation_top_k = int(online_rl_cfg.get("generation_top_k", -1))
    generation_stop = online_rl_cfg.get("generation_stop")
    if generation_stop is not None and not isinstance(generation_stop, list):
        generation_stop = [str(generation_stop)]

    eval_generation_temperature = _as_float(
        "online_rl.eval_generation_temperature",
        online_rl_cfg.get("eval_generation_temperature"),
        0.6,
    )
    eval_generation_top_p = _as_float(
        "online_rl.eval_generation_top_p",
        online_rl_cfg.get("eval_generation_top_p"),
        0.95,
    )
    eval_generation_min_p = _as_float(
        "online_rl.eval_generation_min_p",
        online_rl_cfg.get("eval_generation_min_p"),
        0.0,
    )
    eval_generation_top_k = int(online_rl_cfg.get("eval_generation_top_k", -1))
    eval_generation_stop = online_rl_cfg.get("eval_generation_stop")
    if eval_generation_stop is not None and not isinstance(eval_generation_stop, list):
        eval_generation_stop = [str(eval_generation_stop)]

    return {
        "train_logprobs": train_logprobs,
        "eval_logprobs": eval_logprobs,
        "train_sampling": {
            "temperature": generation_temperature,
            "top_p": generation_top_p,
            "min_p": generation_min_p,
            "top_k": generation_top_k,
            "stop": generation_stop,
        },
        "eval_sampling": {
            "temperature": eval_generation_temperature,
            "top_p": eval_generation_top_p,
            "min_p": eval_generation_min_p,
            "top_k": eval_generation_top_k,
            "stop": eval_generation_stop,
        },
    }


def _resolve_chat_template_and_tools(
    online_rl_cfg: dict[str, Any],
) -> tuple[str | None, dict[str, Any], bool, bool]:
    """Resolve chat template name, kwargs, native tool schema flag, and step-wise flag."""
    chat_template_name = online_rl_cfg.get("chat_template")
    chat_template_kwargs = online_rl_cfg.get("chat_template_kwargs", {})

    native_tool_schemas = bool(online_rl_cfg.get("native_tool_schemas", True))
    if native_tool_schemas and chat_template_name:
        logger.warning(
            "native_tool_schemas=True but custom chat_template=%r is set. "
            "SkyRL custom templates do NOT have {%% if tools %%} — tools "
            "would be silently dropped.  Auto-downgrading to "
            "native_tool_schemas=False (text injection via "
            "_inject_tool_schemas).  [Issue #38]",
            chat_template_name,
        )
        native_tool_schemas = False
    if native_tool_schemas and "tools" not in chat_template_kwargs:
        from trajgym.formatters.tool_registry import get_runtime_tools

        chat_template_kwargs = dict(chat_template_kwargs)
        chat_template_kwargs["tools"] = get_runtime_tools()
        logger.info(
            "Native tool schemas enabled: injecting %d tools into "
            "chat_template_kwargs (tokenizer will format per model template).",
            len(chat_template_kwargs["tools"]),
        )

    step_wise_trajectories = bool(online_rl_cfg.get("step_wise_trajectories", False))
    allow_step_wise_with_custom_template = bool(
        online_rl_cfg.get("allow_step_wise_with_custom_chat_template", False)
    )
    if (
        chat_template_name
        and step_wise_trajectories
        and not allow_step_wise_with_custom_template
    ):
        if bool(online_rl_cfg.get("step_wise_strict_compat", False)):
            raise ValueError(
                "online_rl.step_wise_trajectories=true is incompatible with "
                f"online_rl.chat_template={chat_template_name!r} in current SkyRL. "
                "Set online_rl.step_wise_trajectories=false, remove online_rl.chat_template, "
                "or set online_rl.step_wise_strict_compat=false to auto-disable."
            )
        logger.warning(
            "online_rl.step_wise_trajectories=true is incompatible with custom "
            "chat_template=%r in current SkyRL; auto-disabling step-wise "
            "trajectories for this run.",
            chat_template_name,
        )
        step_wise_trajectories = False
    elif (
        chat_template_name
        and step_wise_trajectories
        and allow_step_wise_with_custom_template
    ):
        logger.warning(
            "Using online_rl.allow_step_wise_with_custom_chat_template=true with "
            "chat_template=%r. Ensure SkyRL includes the step-wise + custom "
            "chat-template compatibility fix.",
            chat_template_name,
        )

    _validate_step_wise_resp_index_guard(online_rl_cfg, step_wise_trajectories)

    return (
        chat_template_name,
        chat_template_kwargs,
        native_tool_schemas,
        step_wise_trajectories,
    )


def _detect_transformer_layer_cls(
    model_path: str,
    online_rl_cfg: dict[str, Any],
) -> tuple[str | None, Any]:
    """Auto-detect the transformer decoder layer class name for FSDP wrapping."""
    _ARCH_TO_LAYER_CLS = {
        "LlamaForCausalLM": "LlamaDecoderLayer",
        "Qwen2ForCausalLM": "Qwen2DecoderLayer",
        "Qwen3ForCausalLM": "Qwen3DecoderLayer",
        "Qwen3_5ForConditionalGeneration": "Qwen3_5DecoderLayer",
        "Qwen3NextForCausalLM": "Qwen3_5DecoderLayer",
        "TransformersForCausalLM": None,
        "MistralForCausalLM": "MistralDecoderLayer",
        "GptOssForCausalLM": "GptOssDecoderLayer",
    }
    _MODEL_TYPE_TO_LAYER_CLS = {
        "qwen3_5_text": "Qwen3_5DecoderLayer",
        "qwen3_5": "Qwen3_5DecoderLayer",
    }
    auto_cfg = None
    transformer_layer_cls = None
    try:
        from transformers import AutoConfig

        auto_cfg = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
        arch = getattr(auto_cfg, "architectures", [None])[0]
        transformer_layer_cls = _ARCH_TO_LAYER_CLS.get(arch)
        if not transformer_layer_cls:
            model_type = getattr(auto_cfg, "model_type", None)
            transformer_layer_cls = _MODEL_TYPE_TO_LAYER_CLS.get(model_type)
        if not transformer_layer_cls and arch:
            base = arch.replace("ForCausalLM", "")
            transformer_layer_cls = f"{base}DecoderLayer"
    except Exception:
        pass
    if auto_cfg is not None:
        _validate_qwen3_5_runtime_dependencies(auto_cfg, online_rl_cfg)
    return transformer_layer_cls, auto_cfg


def _merge_skyrl_defaults(
    skyrl_config: dict[str, Any],
    skyrl_defaults: dict[str, Any],
) -> dict[str, Any]:
    """Deep-merge SkyRL defaults under our overrides, then sanitize."""
    if not skyrl_defaults:
        return skyrl_config

    _HYDRA_KEYS = {"defaults", "deepspeed_config", "megatron_config"}
    for k in _HYDRA_KEYS:
        skyrl_defaults.pop(k, None)

    def _strip_interpolations(d: Any) -> Any:
        if not isinstance(d, dict):
            return d
        cleaned = {}
        for k, v in d.items():
            if isinstance(v, str) and "${" in v:
                continue
            elif isinstance(v, dict):
                cleaned[k] = _strip_interpolations(v)
            else:
                cleaned[k] = v
        return cleaned

    skyrl_defaults = _strip_interpolations(skyrl_defaults)

    def _deep_merge(base: dict, override: dict) -> dict:
        result = dict(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = _deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    merged = _deep_merge(skyrl_defaults, skyrl_config)

    for k in ("defaults", "deepspeed_config", "megatron_config"):
        merged.pop(k, None)

    generator_cfg = merged.get("generator", {})
    for key in ("sampling_params", "eval_sampling_params"):
        sampling = generator_cfg.get(key)
        if isinstance(sampling, dict):
            sampling.pop("additional_kwargs", None)

    return merged


# ------------------------------------------------------------------
# Main config builder
# ------------------------------------------------------------------


def _build_skyrl_config(
    model_path: str,
    output_dir: str,
    config: dict[str, Any],
    data_path: str,
) -> dict[str, Any]:
    """Build a SkyRL config dict matching SkyRLConfig dataclass schema.

    Delegates to focused helpers for each configuration concern, then
    assembles the final dict.
    """
    from trajgym.training.online_rl._utils import _as_positive_int, _as_float

    skyrl_defaults = _load_skyrl_defaults()

    model_cfg = config.get("model", {})
    lora_cfg = config.get("lora", {})
    online_rl_cfg = config.get("online_rl", {})
    if not isinstance(online_rl_cfg, dict):
        online_rl_cfg = {}
    output_cfg = config.get("output", {})
    lora_rank = _parse_lora_rank(lora_cfg)
    lora_target_modules, lora_exclude_modules = _parse_lora_modules(lora_cfg)
    topology = _resolve_generator_topology(online_rl_cfg, lora_rank=lora_rank)
    remote_vllm = topology["remote_vllm"]
    requested_flash_attn = bool(online_rl_cfg.get("flash_attn", False))
    enable_flash_attn = requested_flash_attn and _flash_attn_available()
    if requested_flash_attn and not enable_flash_attn:
        logger.warning(
            "flash_attn requested but unavailable in this environment; falling back to SDPA."
        )
    use_sample_packing = bool(online_rl_cfg.get("use_sample_packing", False))
    if use_sample_packing and not enable_flash_attn:
        logger.warning(
            "use_sample_packing requested without flash_attn support; disabling sample packing."
        )
        use_sample_packing = False

    vllm = _resolve_vllm_params(online_rl_cfg, model_cfg)
    max_prompt_length = vllm["max_prompt_length"]
    max_completion_length = vllm["max_completion_length"]
    vllm_max_model_len = vllm["vllm_max_model_len"]
    num_generations = vllm["num_generations"]
    max_num_seqs = vllm["max_num_seqs"]
    max_num_batched_tokens = vllm["max_num_batched_tokens"]

    num_inference_engines = _as_positive_int(
        "online_rl.num_inference_engines",
        online_rl_cfg.get("num_inference_engines"),
        1,
    )
    inference_engine_tensor_parallel_size = _as_positive_int(
        "online_rl.inference_engine_tensor_parallel_size",
        online_rl_cfg.get("inference_engine_tensor_parallel_size"),
        1,
    )
    inference_engine_pipeline_parallel_size = _as_positive_int(
        "online_rl.inference_engine_pipeline_parallel_size",
        online_rl_cfg.get("inference_engine_pipeline_parallel_size"),
        1,
    )
    inference_engine_data_parallel_size = _as_positive_int(
        "online_rl.inference_engine_data_parallel_size",
        online_rl_cfg.get("inference_engine_data_parallel_size"),
        1,
    )
    inference_engine_expert_parallel_size = _as_positive_int(
        "online_rl.inference_engine_expert_parallel_size",
        online_rl_cfg.get("inference_engine_expert_parallel_size"),
        1,
    )

    max_tool_calling_iterations = _as_positive_int(
        "online_rl.max_tool_calling_iterations",
        online_rl_cfg.get("max_tool_calling_iterations"),
        15,
    )
    eval_interval = int(online_rl_cfg.get("eval_interval", -1))
    eval_before_train = bool(online_rl_cfg.get("eval_before_train", False))
    eval_batch_size = _as_positive_int(
        "online_rl.eval_batch_size",
        online_rl_cfg.get("eval_batch_size"),
        1,
    )
    strategy = str(online_rl_cfg.get("strategy", "fsdp2"))
    policy_loss_type = _resolve_policy_loss_type(online_rl_cfg)
    loss_reduction = str(online_rl_cfg.get("loss_reduction", "token_mean"))
    use_tis = bool(online_rl_cfg.get("use_tis", False))
    off_policy_correction = online_rl_cfg.get("off_policy_correction", {}) or {}
    if not isinstance(off_policy_correction, dict):
        off_policy_correction = {}
    fully_async_cfg = online_rl_cfg.get("fully_async", {}) or {}
    if not isinstance(fully_async_cfg, dict):
        fully_async_cfg = {}
    fully_async_max_staleness_steps = _as_positive_int(
        "online_rl.fully_async.max_staleness_steps",
        fully_async_cfg.get("max_staleness_steps"),
        4,
    )
    fully_async_num_workers = _as_positive_int(
        "online_rl.fully_async.num_parallel_generation_workers",
        fully_async_cfg.get("num_parallel_generation_workers"),
        1,
    )
    async_engine = bool(online_rl_cfg.get("async_engine", True))
    batched = bool(online_rl_cfg.get("batched", False))
    apply_overlong_filtering = bool(
        online_rl_cfg.get("apply_overlong_filtering", False)
    )
    tool_call_format = (
        str(online_rl_cfg.get("tool_call_format", "qwen3_coder")).strip()
        or "qwen3_coder"
    )

    val_data_cfg = online_rl_cfg.get("val_data", [])
    if isinstance(val_data_cfg, str) and val_data_cfg.strip():
        val_data = [val_data_cfg]
    elif isinstance(val_data_cfg, list):
        val_data = [str(v) for v in val_data_cfg if str(v).strip()]
    else:
        val_data = []
    max_env_workers = _as_positive_int(
        "online_rl.max_env_workers",
        online_rl_cfg.get("max_env_workers"),
        32,
    )

    use_ref_model = bool(
        online_rl_cfg.get("beta", 0.0) > 0.0
        or online_rl_cfg.get("use_kl_in_reward", False)
    )
    policy_num_gpus_per_node = _as_positive_int(
        "online_rl.policy_num_gpus_per_node",
        online_rl_cfg.get("policy_num_gpus_per_node"),
        1,
    )
    policy_num_nodes = _as_positive_int(
        "online_rl.policy_num_nodes",
        online_rl_cfg.get("policy_num_nodes"),
        1,
    )
    critic_model_path = online_rl_cfg.get("critic_model_path")
    if critic_model_path:
        critic_num_gpus_per_node = _as_positive_int(
            "online_rl.critic_num_gpus_per_node",
            online_rl_cfg.get("critic_num_gpus_per_node"),
            1,
        )
    else:
        critic_num_gpus_per_node = 0
    critic_num_nodes = _as_positive_int(
        "online_rl.critic_num_nodes",
        online_rl_cfg.get("critic_num_nodes"),
        1,
    )
    ref_num_nodes = _as_positive_int(
        "online_rl.ref_num_nodes",
        online_rl_cfg.get("ref_num_nodes"),
        policy_num_nodes,
    )
    ref_num_gpus_per_node = _as_positive_int(
        "online_rl.ref_num_gpus_per_node",
        online_rl_cfg.get("ref_num_gpus_per_node"),
        policy_num_gpus_per_node,
    )
    if not use_ref_model:
        ref_num_gpus_per_node = 0
    colocate_policy_ref = (
        bool(online_rl_cfg.get("colocate_policy_ref", True)) and use_ref_model
    )

    visible_gpu_count = _detect_visible_gpu_count()
    if (
        visible_gpu_count is not None
        and visible_gpu_count > 0
        and topology["run_engines_locally"]
        and not topology["colocate_all"]
    ):
        policy_gpus = policy_num_nodes * policy_num_gpus_per_node
        ref_gpus = ref_num_nodes * ref_num_gpus_per_node if use_ref_model else 0
        critic_gpus = (
            critic_num_nodes * critic_num_gpus_per_node if critic_model_path else 0
        )
        gpus_per_engine = (
            inference_engine_tensor_parallel_size
            * inference_engine_pipeline_parallel_size
            * inference_engine_data_parallel_size
        )
        required_gpus = (
            policy_gpus
            + ref_gpus
            + critic_gpus
            + (num_inference_engines * gpus_per_engine)
        )
        if required_gpus > visible_gpu_count:
            explicit_num_engines = "num_inference_engines" in online_rl_cfg
            available_for_inference = max(
                0, visible_gpu_count - policy_gpus - ref_gpus - critic_gpus
            )
            max_auto_engines = available_for_inference // max(1, gpus_per_engine)
            if not explicit_num_engines and max_auto_engines > 0:
                logger.warning(
                    "Local non-colocated topology requests %d GPUs but only %d are visible. "
                    "Auto-adjusting num_inference_engines from %d to %d.",
                    required_gpus,
                    visible_gpu_count,
                    num_inference_engines,
                    max_auto_engines,
                )
                num_inference_engines = max_auto_engines
            else:
                logger.warning(
                    "Local non-colocated topology requests %d GPUs (%d policy + %d ref + %d critic + "
                    "%d inference) but only %d are visible. Training may stall or OOM.",
                    required_gpus,
                    policy_gpus,
                    ref_gpus,
                    critic_gpus,
                    num_inference_engines * gpus_per_engine,
                    visible_gpu_count,
                )

    (
        chat_template_name,
        chat_template_kwargs,
        native_tool_schemas,
        step_wise_trajectories,
    ) = _resolve_chat_template_and_tools(online_rl_cfg)

    gen = _resolve_generation_params(online_rl_cfg, remote_vllm, chat_template_name)

    transformer_layer_cls, _ = _detect_transformer_layer_cls(model_path, online_rl_cfg)

    ref_model_path = config.get("ref_model_path", model_path)
    eps_clip_low = online_rl_cfg.get("epsilon_low", 0.2)
    eps_clip_high = online_rl_cfg.get("epsilon_high", eps_clip_low)

    warmup_ratio = float(online_rl_cfg.get("warmup_ratio", 0.0))
    if warmup_ratio > 0:
        total_episodes = int(online_rl_cfg.get("total_episodes", 100))
        num_warmup_steps = max(1, int(total_episodes * warmup_ratio))
        logger.info(
            "Warmup: ratio=%.3f, total_episodes=%d -> num_warmup_steps=%d",
            warmup_ratio,
            total_episodes,
            num_warmup_steps,
        )
    else:
        num_warmup_steps = int(online_rl_cfg.get("num_warmup_steps", 0))

    fsdp_wrap_policy = (
        {"transformer_layer_cls_to_wrap": [transformer_layer_cls]}
        if transformer_layer_cls
        else {}
    )

    # ===================================================================
    # Assemble the final SkyRL config dict
    # ===================================================================
    skyrl_config = {
        "data": {
            "train_data": [data_path],
            "val_data": val_data,
        },
        "trainer": {
            "strategy": strategy,
            "bf16": True,
            "gradient_checkpointing": True,
            "gradient_checkpointing_use_reentrant": False,
            "seed": 42,
            "sequence_parallel_backend": "ulysses",
            "epochs": online_rl_cfg.get("epochs", 1),
            "update_epochs_per_batch": _as_positive_int(
                "online_rl.update_epochs_per_batch",
                online_rl_cfg.get("update_epochs_per_batch"),
                1,
            ),
            "train_batch_size": online_rl_cfg.get("batch_size", 1),
            "policy_mini_batch_size": online_rl_cfg.get("batch_size", 1),
            "critic_mini_batch_size": online_rl_cfg.get("batch_size", 1),
            "micro_train_batch_size_per_gpu": 1,
            "micro_forward_batch_size_per_gpu": 1,
            "max_prompt_length": max_prompt_length,
            "max_response_length": max_completion_length,
            "use_sample_packing": use_sample_packing,
            "eval_batch_size": eval_batch_size,
            "eval_interval": eval_interval,
            "flash_attn": enable_flash_attn,
            "disable_fast_tokenizer": False,
            "update_ref_every_epoch": False,
            "resume_mode": None,
            "resume_path": None,
            "ckpt_path": output_dir,
            "max_ckpts_to_keep": -1,
            "hf_save_interval": -1,
            "ckpt_interval": output_cfg.get("save_steps", 50),
            "export_path": os.path.join(output_dir, "final"),
            "eval_before_train": eval_before_train,
            "project_name": "trajgym",
            "run_name": "online_rl",
            "logger": _resolve_skyrl_logger(
                output_cfg.get("report_to", "tensorboard"), output_dir
            ),
            "dump_data_batch": False,
            "dump_eval_results": False,
            "target_modules": None,
            "exclude_modules": None,
            "rope_scaling": None,
            "rope_theta": None,
            "placement": {
                "colocate_all": topology["colocate_all"],
                "colocate_policy_ref": colocate_policy_ref,
                "policy_num_nodes": policy_num_nodes,
                "policy_num_gpus_per_node": policy_num_gpus_per_node,
                "critic_num_nodes": critic_num_nodes,
                "critic_num_gpus_per_node": critic_num_gpus_per_node,
                "ref_num_nodes": ref_num_nodes,
                "ref_num_gpus_per_node": ref_num_gpus_per_node,
            },
            "fully_async": {
                "max_staleness_steps": fully_async_max_staleness_steps,
                "num_parallel_generation_workers": fully_async_num_workers,
            },
            "policy": {
                "model": {
                    "path": model_path,
                    "lora": {
                        "rank": lora_rank,
                        "alpha": lora_cfg.get("alpha", 128),
                        "dropout": lora_cfg.get("dropout", 0.0),
                        "target_modules": lora_target_modules,
                        "exclude_modules": lora_exclude_modules,
                        "lora_sync_path": os.path.join(output_dir, "lora_sync"),
                        "init_method": "kaiming",
                    },
                    "config_kwargs": {},
                },
                "model_config_kwargs": {},
                "fsdp_config": {
                    "cpu_offload": bool(online_rl_cfg.get("policy_cpu_offload", False)),
                    "reshard_after_forward": True,
                    "fsdp_size": -1,
                    "wrap_policy": fsdp_wrap_policy,
                },
                "sequence_parallel_size": 1,
                "use_torch_compile": False,
                "record_memory": False,
                "optimizer_config": {
                    "lr": online_rl_cfg.get("learning_rate", 5e-6),
                    "adam_betas": [0.9, 0.999],
                    "weight_decay": online_rl_cfg.get("weight_decay", 0.0),
                    "max_grad_norm": online_rl_cfg.get("max_grad_norm", 5.0),
                    "offload_after_step": True,
                    "num_warmup_steps": num_warmup_steps,
                    "scheduler": "constant_with_warmup",
                },
            },
            "ref": {
                "model": {
                    "path": ref_model_path,
                    "config_kwargs": {},
                },
                "model_config_kwargs": {},
                "sequence_parallel_size": 1,
                "fsdp_config": {
                    "cpu_offload": online_rl_cfg.get("beta", 0.0) == 0.0,
                    "reshard_after_forward": True,
                    "fsdp_size": -1,
                    "wrap_policy": fsdp_wrap_policy,
                },
            },
            "critic": {
                "model": {
                    "path": critic_model_path,
                    "lora": {
                        "rank": 0,
                        "alpha": 16,
                        "dropout": 0,
                        "target_modules": lora_target_modules,
                        "exclude_modules": lora_exclude_modules,
                        "init_method": "kaiming",
                    },
                },
                "model_config_kwargs": {},
                "sequence_parallel_size": 1,
                "fsdp_config": {
                    "cpu_offload": False,
                    "reshard_after_forward": True,
                    "fsdp_size": -1,
                },
                "optimizer_config": {
                    "lr": 5e-6,
                    "adam_betas": [0.9, 0.999],
                    "weight_decay": 0.01,
                    "max_grad_norm": 1.0,
                    "offload_after_step": True,
                    "num_warmup_steps": num_warmup_steps,
                    "scheduler": "constant_with_warmup",
                },
            },
            "algorithm": {
                "advantage_estimator": online_rl_cfg.get("advantage_estimator", "rloo"),
                "policy_loss_type": policy_loss_type,
                "kl_loss_coef": online_rl_cfg.get("beta", 0.0),
                "use_kl_loss": online_rl_cfg.get("beta", 0.0) > 0,
                "use_kl_in_reward": False,
                "kl_ctrl": {
                    "type": "fixed",
                    "kl_target": 0.1,
                    "horizon": 10000,
                },
                "kl_estimator_type": "k3",
                "use_kl_estimator_k3": False,
                "use_abs_kl": False,
                "use_entropy_loss": bool(online_rl_cfg.get("use_entropy_loss", False)),
                "entropy_loss_coef": float(
                    online_rl_cfg.get("entropy_loss_coef", 0.01)
                ),
                "advantage_batch_normalize": False,
                "value_head_prefix": "value_head",
                "loss_reduction": loss_reduction,
                "grpo_norm_by_std": True,
                "zero_variance_filter": bool(
                    online_rl_cfg.get("zero_variance_filter", False)
                ),
                "lambd": 1.0,
                "gamma": 1.0,
                "eps_clip_low": eps_clip_low,
                "eps_clip_high": eps_clip_high,
                "clip_ratio_c": 3.0,
                "tis_imp_ratio_cap": -1.0,
                "use_tis": use_tis,
                "off_policy_correction": {
                    "tis_ratio_type": off_policy_correction.get("tis_ratio_type"),
                    "token_tis_ratio_clip_high": float(
                        off_policy_correction.get("token_tis_ratio_clip_high", 2.0)
                    ),
                    "sequence_tis_ratio_clip_high": float(
                        off_policy_correction.get("sequence_tis_ratio_clip_high", 5.0)
                    ),
                    "sequence_mask_metric": off_policy_correction.get(
                        "sequence_mask_metric"
                    ),
                    "geo_mask_high": float(
                        off_policy_correction.get("geo_mask_high", 1.01)
                    ),
                    "geo_mask_low": float(
                        off_policy_correction.get("geo_mask_low", 0.99)
                    ),
                    "product_mask_high": float(
                        off_policy_correction.get("product_mask_high", 2.0)
                    ),
                    "product_mask_low": float(
                        off_policy_correction.get("product_mask_low", 0.5)
                    ),
                    "outlier_token_is_threshold_low": off_policy_correction.get(
                        "outlier_token_is_threshold_low"
                    ),
                    "outlier_token_is_threshold_high": off_policy_correction.get(
                        "outlier_token_is_threshold_high"
                    ),
                },
                "sapo": {"tau_pos": 1.0, "tau_neg": 1.05},
                "value_clip": 0.2,
                "dynamic_sampling": {
                    "type": online_rl_cfg.get("dynamic_sampling", {}).get("type", None),
                    "max_sample_batches": _as_positive_int(
                        "online_rl.dynamic_sampling.max_sample_batches",
                        online_rl_cfg.get("dynamic_sampling", {}).get(
                            "max_sample_batches"
                        ),
                        30,
                    ),
                    "min_replace_ratio": 0.3,
                },
                "clip_cov": {
                    "clip_ratio": 0.0002,
                    "clip_cov_lb": 1.0,
                    "clip_cov_ub": 5.0,
                },
                "kl_cov": {
                    "kl_cov_frac": 0.2,
                    "ppo_kl_coef": 1.0,
                },
                "cispo": {
                    "cispo_eps_clip_low": 0,
                    "cispo_eps_clip_high": 5,
                },
            },
        },
        "generator": {
            "model_name": model_path,
            "model_dtype": "bfloat16",
            "run_engines_locally": topology["run_engines_locally"],
            "num_inference_engines": num_inference_engines,
            "backend": "vllm",
            "weight_sync_backend": topology["weight_sync_backend"],
            "weight_transfer_threshold_cuda_ipc_GB": 1.0,
            "inference_engine_tensor_parallel_size": inference_engine_tensor_parallel_size,
            "inference_engine_pipeline_parallel_size": inference_engine_pipeline_parallel_size,
            "inference_engine_expert_parallel_size": inference_engine_expert_parallel_size,
            "inference_engine_data_parallel_size": inference_engine_data_parallel_size,
            "n_samples_per_prompt": num_generations,
            "async_engine": async_engine,
            "batched": batched,
            "max_input_length": vllm_max_model_len,
            "vllm_v1_disable_multiproc": True,
            "enable_prefix_caching": bool(
                online_rl_cfg.get("enable_prefix_caching", True)
            ),
            "enable_chunked_prefill": bool(
                online_rl_cfg.get("enable_chunked_prefill", True)
            ),
            "max_num_batched_tokens": max_num_batched_tokens,
            "enforce_eager": bool(online_rl_cfg.get("enforce_eager", True)),
            "fully_sharded_loras": False,
            "enable_ray_prometheus_stats": False,
            "gpu_memory_utilization": online_rl_cfg.get("gpu_memory_utilization", 0.4),
            "max_num_seqs": max_num_seqs,
            "remote_inference_engine_urls": topology["remote_inference_engine_urls"],
            "external_proxy_url": topology.get("external_proxy_url"),
            "external_server_urls": topology.get("external_server_urls"),
            "tool_call_format": tool_call_format,
            "enable_http_endpoint": False,
            "http_endpoint_host": "127.0.0.1",
            "http_endpoint_port": 8000,
            "served_model_name": None,
            "max_turns": max_tool_calling_iterations,
            "chat_template": {
                "source": "name",
                "name_or_path": chat_template_name,
            },
            "chat_template_kwargs": chat_template_kwargs,
            "engine_init_kwargs": {
                "max_model_len": vllm_max_model_len,
                **(
                    {"language_model_only": True}
                    if vllm["vllm_language_model_only"]
                    else {}
                ),
                **(
                    {"attention_backend": vllm["vllm_attention_backend"]}
                    if vllm["vllm_attention_backend"]
                    else {}
                ),
                **(
                    {"mm_encoder_attn_backend": vllm["vllm_mm_encoder_attn_backend"]}
                    if vllm["vllm_mm_encoder_attn_backend"]
                    else {}
                ),
            },
            "override_existing_update_group": "auto",
            "sampling_params": {
                "max_generate_length": max_completion_length,
                "repetition_penalty": online_rl_cfg.get("repetition_penalty", 1.0),
                **gen["train_sampling"],
                "logprobs": gen["train_logprobs"],
            },
            "use_conversation_multi_turn": True,
            "append_eos_token_after_stop_str_in_multi_turn": True,
            "eval_sampling_params": {
                "max_generate_length": max_completion_length,
                "repetition_penalty": online_rl_cfg.get("repetition_penalty", 1.0),
                **gen["eval_sampling"],
                "logprobs": gen["eval_logprobs"],
            },
            "eval_n_samples_per_prompt": 1,
            "zero_reward_on_non_stop": False,
            "apply_overlong_filtering": apply_overlong_filtering,
            "rope_scaling": None,
            "rope_theta": None,
            "step_wise_trajectories": step_wise_trajectories,
            "native_tool_schemas": native_tool_schemas,
        },
        "environment": {
            "env_class": "trajgym",
            "skyrl_gym": {
                "max_env_workers": max_env_workers,
            },
        },
    }

    return _merge_skyrl_defaults(skyrl_config, skyrl_defaults)
