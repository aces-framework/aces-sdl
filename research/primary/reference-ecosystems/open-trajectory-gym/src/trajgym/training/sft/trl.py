"""TRL-based Supervised Fine-Tuning (SFT) stage.

SFT backend for models that require ``transformers >= 5.2.0`` (e.g. Qwen3.5-27B).

Uses vanilla HuggingFace ``SFTTrainer`` (TRL) + ``peft`` LoRA.

Advantages:
  - No pinned ``transformers`` ceiling — works with any HF-supported model
  - Native ``tokenizer.apply_chat_template()`` formatting (model-specific)
  - Simpler dependency surface (trl + peft + transformers + torch)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from datasets import Dataset

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _load_model_config(model_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Resolve model-specific training config.

    Reads from config dict (loaded from training_*.yaml) or falls back to
    sensible defaults matching a high-memory GPU VRAM budget.
    """
    model_cfg = config.get("model", {})
    lora_cfg = config.get("lora", {})
    sft_cfg = config.get("sft", {})
    output_cfg = config.get("output", {})

    return {
        "model_name": model_cfg.get("name", model_id),
        "max_seq_length": model_cfg.get("max_seq_length", 8192),
        "load_in_4bit": model_cfg.get("load_in_4bit", False),
        "load_in_8bit": model_cfg.get("load_in_8bit", False),
        # LoRA
        "lora_r": lora_cfg.get("r", 64),
        "lora_alpha": lora_cfg.get("alpha", 128),
        "lora_dropout": lora_cfg.get("dropout", 0.0),
        "lora_target_modules": lora_cfg.get(
            "target_modules",
            [
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            ],
        ),
        "use_rslora": lora_cfg.get("use_rslora", False),
        # SFT hyperparameters
        "epochs": sft_cfg.get("epochs", 3),
        "batch_size": sft_cfg.get("batch_size", 1),
        "gradient_accumulation_steps": sft_cfg.get("gradient_accumulation_steps", 8),
        "learning_rate": sft_cfg.get("learning_rate", 2e-5),
        "warmup_steps": sft_cfg.get("warmup_steps", 1),
        "weight_decay": sft_cfg.get("weight_decay", 0.01),
        "lr_scheduler_type": sft_cfg.get("lr_scheduler_type", "cosine"),
        "packing": sft_cfg.get("packing", False),
        "flash_attn": sft_cfg.get("flash_attn", True),
        "gradient_checkpointing": sft_cfg.get("gradient_checkpointing", True),
        "tf32": sft_cfg.get("tf32", False),
        # Output
        "save_steps": output_cfg.get("save_steps", 25),
        "logging_steps": output_cfg.get("logging_steps", 1),
        "report_to": output_cfg.get("report_to", "none"),
    }


def _load_jsonl_messages(data_path: str) -> list[dict[str, Any]]:
    """Load JSONL data and return list of samples with 'messages' key."""
    samples = []
    with open(data_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            sample = json.loads(line)
            if "messages" in sample:
                samples.append(sample)
    logger.info("Loaded %d samples from %s", len(samples), data_path)
    return samples


def _format_dataset(
    samples: list[dict[str, Any]],
    tokenizer,
    max_seq_length: int,
    think_kwargs: dict[str, Any] | None = None,
) -> Dataset:
    """Format samples using the tokenizer's native chat template.

    Uses ``tokenizer.apply_chat_template()`` to produce the model's native
    format (ChatML for Qwen3, Mistral format for Devstral, etc.).  This
    ensures tool calls, thinking blocks, and special tokens are rendered
    correctly without manual template logic.

    Args:
        think_kwargs: Dict of template kwargs for thinking preservation
            (from ``_detect_thinking_support``). Empty dict or None to disable.

    Returns a HuggingFace Dataset with a ``text`` column.
    """
    from datasets import Dataset

    texts = []
    skipped = 0
    for sample in samples:
        messages = sample["messages"]

        # Normalize tool_calls arguments: some traces have JSON strings
        # instead of dicts (tokenizer.apply_chat_template expects dicts).
        messages = _normalize_messages(messages)

        try:
            # apply_chat_template with tokenize=False → raw text string
            # including all special tokens. SFTTrainer will tokenize.
            chat_kwargs = {"tokenize": False, "add_generation_prompt": False}
            if think_kwargs:
                chat_kwargs.update(think_kwargs)

            text = tokenizer.apply_chat_template(messages, **chat_kwargs)
            texts.append(text)
        except Exception as e:
            skipped += 1
            if skipped <= 5:
                logger.warning("Skipping sample (template error): %s", e)

    if skipped:
        logger.warning(
            "Skipped %d/%d samples due to template errors", skipped, len(samples)
        )

    logger.info("Formatted %d samples (skipped %d)", len(texts), skipped)
    return Dataset.from_dict({"text": texts})


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize messages for tokenizer.apply_chat_template().

    Delegates to the shared implementation in ``utils.py``.
    """
    from trajgym.training.sft.utils import normalize_messages

    return normalize_messages(messages)


def _resolve_attn_implementation(flash_attn_requested: bool) -> str:
    """Pick the best available attention implementation.

    When ``flash_attn=True`` is set in the training config, try the external
    ``flash-attn`` package (``flash_attention_2``).  If it's a stub or the
    CUDA extension fails to load, fall back to PyTorch SDPA which already
    dispatches to Flash SDP kernels on Hopper GPUs (``flash_sdp_enabled``).
    """
    if flash_attn_requested:
        try:
            import flash_attn as _fa

            if "stub" in _fa.__version__ or "fallback" in _fa.__version__:
                logger.info(
                    "flash_attn %s is a stub — falling back to SDPA "
                    "(uses Flash SDP kernels on Hopper)",
                    _fa.__version__,
                )
                return "sdpa"
            from flash_attn import flash_attn_func  # noqa: F401

            logger.info("Flash Attention 2 (%s) available", _fa.__version__)
            return "flash_attention_2"
        except (ImportError, OSError) as exc:
            logger.info(
                "flash_attn requested but not usable (%s) — "
                "falling back to SDPA (uses Flash SDP kernels on Hopper)",
                exc,
            )
            return "sdpa"
    return "sdpa"


def train_sft(
    model_id: str,
    data_path: str,
    output_dir: str,
    config: dict[str, Any],
    val_data_path: str | None = None,
    resume_from: str | None = None,
) -> str:
    """Run SFT training via TRL SFTTrainer + peft LoRA.

    Args:
        model_id: HuggingFace model identifier or local path.
        data_path: Path to JSONL training data (OpenAI messages format).
        output_dir: Directory for checkpoints and final adapter.
        config: Merged config dict from training.yaml.
        val_data_path: Optional path to validation JSONL.
        resume_from: Optional checkpoint path to resume from.

    Returns:
        Path to the saved LoRA adapter directory.
    """
    import torch
    from peft import LoraConfig, TaskType
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )
    from trl import SFTConfig, SFTTrainer

    # Reduce CUDA allocator fragmentation — must be set before any CUDA ops.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    # Liger CE global patch: replace nn.functional.cross_entropy with chunked
    # cross-entropy to avoid materializing the full vocab_size x seq_len logits
    # tensor.  Without this, 65K context x 248K vocab = 60.5 GiB float32 → OOM.
    # Liger 0.7.0 doesn't support qwen3_5_text model-specific monkey-patch, so
    # we patch at the PyTorch functional level (same approach Liger uses internally).
    try:
        import transformers.loss.loss_utils as _loss_utils
        from liger_kernel.transformers.functional import liger_cross_entropy

        _loss_utils.nn.functional.cross_entropy = liger_cross_entropy
        logger.info("Liger CE global patch applied — chunked cross-entropy enabled")
    except ImportError:
        logger.warning(
            "liger-kernel not installed — large-vocab models at long context "
            "will OOM from full logits materialization. Install with: "
            "pip install liger-kernel"
        )

    logger.info("=" * 60)
    logger.info("SFT TRAINING (TRL)")
    logger.info("  Model:  %s", model_id)
    logger.info("  Data:   %s", data_path)
    logger.info("  Output: %s", output_dir)
    logger.info("=" * 60)

    # 1. Resolve config
    cfg = _load_model_config(model_id, config)
    os.makedirs(output_dir, exist_ok=True)

    # Save resolved config for reproducibility
    config_path = os.path.join(output_dir, "trl_sft_config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)
    logger.info("Resolved config written to %s", config_path)

    # 2. Load tokenizer
    logger.info("Loading tokenizer: %s", model_id)
    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        trust_remote_code=True,
        padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        logger.info("Set pad_token = eos_token (%s)", tokenizer.eos_token)

    # 3. Load model
    logger.info("Loading model: %s", model_id)
    attn_impl = _resolve_attn_implementation(cfg["flash_attn"])
    logger.info("Using attention implementation: %s", attn_impl)

    # When running under FSDP (via accelerate launch), device_map must be None —
    # FSDP handles device placement.  Detect via ACCELERATE_USE_FSDP env var
    # or world_size > 1 from LOCAL_RANK / WORLD_SIZE env.
    use_fsdp = (
        os.environ.get("ACCELERATE_USE_FSDP", "").lower() in ("1", "true")
        or int(os.environ.get("WORLD_SIZE", "1")) > 1
    )
    if use_fsdp:
        logger.info("FSDP detected — device_map disabled, FSDP handles sharding")
        device_map = None
    else:
        device_map = "balanced"

    model_kwargs = {
        "trust_remote_code": True,
        "dtype": torch.bfloat16,
        "attn_implementation": attn_impl,
        "device_map": device_map,
        "low_cpu_mem_usage": True,
    }

    # Quantization (optional — not needed on high-memory GPUs but supported)
    if cfg["load_in_4bit"] or cfg["load_in_8bit"]:
        try:
            # Verify bitsandbytes can actually quantize by testing the native lib.
            # Import may succeed but CUDA binary may be missing/incompatible.
            import bitsandbytes as bnb

            # Create a small test tensor and try to quantize it
            test_tensor = torch.randn(16, 16, dtype=torch.float32, device="cuda")
            bnb.functional.quantize_4bit(test_tensor)
            del test_tensor
            torch.cuda.empty_cache()
        except Exception as e:
            logger.warning(
                "bitsandbytes 4-bit quantization not functional (%s), "
                "falling back to bf16. Model will use more memory but "
                "training quality is unaffected.",
                e,
            )
            cfg["load_in_4bit"] = False
            cfg["load_in_8bit"] = False

    if cfg["load_in_4bit"]:
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
    elif cfg["load_in_8bit"]:
        model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)

    model = AutoModelForCausalLM.from_pretrained(model_id, **model_kwargs)

    # 4. Configure LoRA (SFTTrainer applies it via peft_config)
    logger.info(
        "LoRA config: r=%d, alpha=%d, modules=%s",
        cfg["lora_r"],
        cfg["lora_alpha"],
        cfg["lora_target_modules"],
    )
    lora_config = LoraConfig(
        r=cfg["lora_r"],
        lora_alpha=cfg["lora_alpha"],
        lora_dropout=cfg["lora_dropout"],
        target_modules=cfg["lora_target_modules"],
        task_type=TaskType.CAUSAL_LM,
        use_rslora=cfg["use_rslora"],
        bias="none",
    )

    # 5. Format data
    logger.info("Formatting training data with tokenizer chat template...")
    train_samples = _load_jsonl_messages(data_path)

    # Detect thinking mode support and get template kwargs.
    # Returns dict of kwargs like {enable_thinking: True, keep_all_think: True}
    # or empty dict if model doesn't support <think> blocks.
    think_kwargs = _detect_thinking_support(tokenizer, model_id)
    logger.info("Thinking mode: %s", "enabled" if think_kwargs else "disabled")
    if think_kwargs:
        logger.info("Thinking kwargs: %s", think_kwargs)

    train_dataset = _format_dataset(
        train_samples,
        tokenizer,
        cfg["max_seq_length"],
        think_kwargs=think_kwargs,
    )

    eval_dataset = None
    if val_data_path and Path(val_data_path).exists():
        val_samples = _load_jsonl_messages(val_data_path)
        eval_dataset = _format_dataset(
            val_samples,
            tokenizer,
            cfg["max_seq_length"],
            think_kwargs=think_kwargs,
        )
        logger.info("Validation dataset: %d samples", len(eval_dataset))

    # 6. Configure SFTTrainer
    # Detect wandb availability
    from trajgym.training import check_wandb_available

    report_to = check_wandb_available(cfg["report_to"])

    sft_config = SFTConfig(
        output_dir=output_dir,
        # Training
        num_train_epochs=cfg["epochs"],
        per_device_train_batch_size=cfg["batch_size"],
        gradient_accumulation_steps=cfg["gradient_accumulation_steps"],
        learning_rate=cfg["learning_rate"],
        lr_scheduler_type=cfg["lr_scheduler_type"],
        warmup_steps=cfg["warmup_steps"],
        weight_decay=cfg["weight_decay"],
        bf16=True,
        tf32=cfg.get("tf32", False),
        optim="adamw_8bit",
        # Context — TRL 0.28+ uses max_length (not max_seq_length)
        max_length=cfg["max_seq_length"],
        packing=cfg["packing"],
        dataset_text_field="text",
        # Checkpointing
        save_steps=cfg["save_steps"],
        save_total_limit=5,
        save_only_model=True,
        # Logging
        logging_steps=cfg["logging_steps"],
        report_to=report_to,
        run_name="sft-trl",
        # Misc
        seed=42,
        gradient_checkpointing=cfg.get("gradient_checkpointing", True),
        gradient_checkpointing_kwargs=(
            {"use_reentrant": False}
            if cfg.get("gradient_checkpointing", True)
            else None
        ),
        dataloader_num_workers=0,  # Unified memory GPUs: fork overhead from workers causes OOM
        remove_unused_columns=True,
        # Evaluation
        eval_strategy="steps" if eval_dataset else "no",
        eval_steps=cfg["save_steps"] if eval_dataset else None,
        # Liger Kernel: fused cross-entropy avoids materializing full
        # vocab_size×seq_len float32 logits tensor. Disabled by default —
        # Liger 0.7.0 doesn't support qwen3_5_text. Use chunked CE patch
        # on transformers/loss/loss_utils.py instead for large-vocab models.
        use_liger_kernel=cfg.get("use_liger_kernel", False),
        # TRL 0.29 native: mask loss to assistant-only turns.
        # Replaces removed DataCollatorForCompletionOnlyLM.
        completion_only_loss=True,
    )

    if resume_from:
        sft_config.resume_from_checkpoint = resume_from

    data_collator = None

    # 7. Train
    logger.info("Starting SFT training...")
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        peft_config=lora_config,
        data_collator=data_collator,
    )
    trainer.train(resume_from_checkpoint=resume_from)

    # 8. Save final adapter
    final_dir = os.path.join(output_dir, "final")
    logger.info("Saving final LoRA adapter to %s", final_dir)
    trainer.save_model(final_dir)
    tokenizer.save_pretrained(final_dir)

    logger.info("SFT training complete (TRL backend). Output: %s", final_dir)
    return final_dir


def _detect_thinking_support(tokenizer, model_id: str) -> dict[str, Any]:
    """Detect thinking mode support and return kwargs to preserve ``<think>``.

    Different models use different template kwargs for thinking:
      - Qwen3/3.5: ``enable_thinking=True``
      - Nanbeige4.1: ``keep_all_think=True`` (preserves thinking in ALL turns)

    Returns a dict of kwargs to pass to ``apply_chat_template()`` for SFT.
    Empty dict means no thinking support detected.
    """
    vocab = tokenizer.get_vocab()
    if "<think>" not in vocab:
        return {}

    # Probe which thinking kwargs the template accepts.
    # For SFT we want ALL turns to preserve <think> so the model learns
    # reasoning patterns throughout multi-turn conversations.
    think_kwargs: dict[str, Any] = {}
    test_msgs = [{"role": "user", "content": "test"}]

    for kwarg in ("enable_thinking", "keep_all_think"):
        try:
            tokenizer.apply_chat_template(
                test_msgs,
                tokenize=False,
                add_generation_prompt=True,
                **{kwarg: True},
            )
            think_kwargs[kwarg] = True
        except (TypeError, Exception):
            pass

    if think_kwargs:
        logger.info("Thinking kwargs detected: %s", list(think_kwargs.keys()))
    else:
        logger.info(
            "<think> in vocab but no template kwargs accepted; "
            "inline <think> tags will be passed through as-is"
        )

    return think_kwargs
