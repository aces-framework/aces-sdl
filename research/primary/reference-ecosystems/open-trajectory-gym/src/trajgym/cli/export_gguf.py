#!/usr/bin/env python3
"""Export a trained LoRA adapter to GGUF format.

Pipeline:
  1. Merge LoRA adapter into base model weights (PEFT)
  2. Convert merged HF model to GGUF via llama.cpp
  3. Quantize to the requested precision (default: Q4_K_M)

Requirements:
  - transformers + peft
  - llama.cpp built with `make` (for convert_hf_to_gguf.py and llama-quantize)

Usage:
    trajgym export \\
        --adapter outputs/sft/final \\
        --base-model Nanbeige/Nanbeige4.1-3B \\
        --output models/ctf-agent.gguf \\
        --quant Q4_K_M

    # Skip quantization (output F16 GGUF only):
    trajgym export \\
        --adapter outputs/sft/final \\
        --base-model Nanbeige/Nanbeige4.1-3B \\
        --output models/ctf-agent-f16.gguf \\
        --quant none

    # Custom llama.cpp path:
    trajgym export \\
        --adapter outputs/sft/final \\
        --base-model Nanbeige/Nanbeige4.1-3B \\
        --output models/ctf-agent.gguf \\
        --llama-cpp /opt/llama.cpp
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------
# Step 1: Merge LoRA into base model
# -----------------------------------------------------------------------


def merge_lora(adapter_path: str, base_model: str, output_dir: str) -> str:
    """Merge LoRA adapter into base model weights via PEFT merge_and_unload().

    Args:
        adapter_path: Path to the LoRA adapter directory (checkpoint or final).
        base_model: HuggingFace model identifier for the base model.
        output_dir: Directory to save the merged model.

    Returns:
        Path to the merged model directory.
    """
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    logger.info("Loading base model: %s", base_model)
    logger.info("Loading adapter:    %s", adapter_path)

    if not base_model:
        raise ValueError(
            "Merge requires --base-model "
            "(needed to load the base model before applying adapter)"
        )

    logger.info("Merging LoRA weights via PEFT merge_and_unload()...")
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(base, adapter_path)
    model = model.merge_and_unload()

    os.makedirs(output_dir, exist_ok=True)
    model.save_pretrained(output_dir, safe_serialization=True)
    tokenizer.save_pretrained(output_dir)
    logger.info("Merged model saved to %s", output_dir)

    return output_dir


# -----------------------------------------------------------------------
# Step 2: Convert HF model to GGUF
# -----------------------------------------------------------------------


def find_llama_cpp(hint: str | None = None) -> Path:
    """Locate llama.cpp installation directory.

    Search order:
      1. Explicit --llama-cpp argument
      2. LLAMA_CPP_DIR environment variable
      3. ~/llama.cpp
      4. llama-quantize on PATH (derive parent)
    """
    if hint:
        p = Path(hint)
        if p.is_dir():
            return p

    env = os.environ.get("LLAMA_CPP_DIR")
    if env:
        p = Path(env)
        if p.is_dir():
            return p

    home = Path.home() / "llama.cpp"
    if home.is_dir():
        return home

    which = shutil.which("llama-quantize")
    if which:
        return Path(which).parent.parent  # bin/../

    return Path("")


def convert_to_gguf(model_dir: str, output_path: str, llama_cpp_dir: Path) -> str:
    """Convert HF model to F16 GGUF using llama.cpp's convert script.

    Args:
        model_dir: Path to the merged HuggingFace model directory.
        output_path: Desired output GGUF file path.
        llama_cpp_dir: Path to llama.cpp repo/install directory.

    Returns:
        Path to the F16 GGUF file.
    """
    convert_script = llama_cpp_dir / "convert_hf_to_gguf.py"
    if not convert_script.exists():
        # Try alternative locations
        for candidate in [
            llama_cpp_dir / "scripts" / "convert_hf_to_gguf.py",
            llama_cpp_dir / "gguf-py" / "scripts" / "convert_hf_to_gguf.py",
        ]:
            if candidate.exists():
                convert_script = candidate
                break
        else:
            logger.error(
                "convert_hf_to_gguf.py not found in %s. "
                "Build llama.cpp first: git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp && make",
                llama_cpp_dir,
            )
            sys.exit(1)

    f16_path = (
        output_path.replace(".gguf", "-f16.gguf")
        if output_path.endswith(".gguf")
        else output_path + "-f16.gguf"
    )

    cmd = [
        sys.executable,
        str(convert_script),
        model_dir,
        "--outfile",
        f16_path,
        "--outtype",
        "f16",
    ]
    logger.info("Converting to GGUF: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    logger.info("F16 GGUF written to %s", f16_path)
    return f16_path


# -----------------------------------------------------------------------
# Step 3: Quantize GGUF
# -----------------------------------------------------------------------

QUANT_TYPES = [
    "Q2_K",
    "Q3_K_S",
    "Q3_K_M",
    "Q3_K_L",
    "Q4_0",
    "Q4_K_S",
    "Q4_K_M",
    "Q5_0",
    "Q5_K_S",
    "Q5_K_M",
    "Q6_K",
    "Q8_0",
    "IQ2_M",
    "IQ3_M",
    "none",
]


def quantize_gguf(
    f16_path: str, output_path: str, quant_type: str, llama_cpp_dir: Path
) -> str:
    """Quantize an F16 GGUF file.

    Args:
        f16_path: Path to the F16 GGUF file.
        output_path: Desired output path for the quantized GGUF.
        quant_type: Quantization type (e.g., Q4_K_M).
        llama_cpp_dir: Path to llama.cpp installation.

    Returns:
        Path to the quantized GGUF file.
    """
    if quant_type.lower() == "none":
        logger.info("Skipping quantization (--quant none)")
        return f16_path

    quantize_bin = llama_cpp_dir / "llama-quantize"
    if not quantize_bin.exists():
        # Try build directory
        quantize_bin = llama_cpp_dir / "build" / "bin" / "llama-quantize"
    if not quantize_bin.exists():
        which = shutil.which("llama-quantize")
        if which:
            quantize_bin = Path(which)
        else:
            logger.error(
                "llama-quantize not found. Build llama.cpp first: cd llama.cpp && make"
            )
            sys.exit(1)

    cmd = [str(quantize_bin), f16_path, output_path, quant_type]
    logger.info("Quantizing: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)

    # Report sizes
    f16_size = Path(f16_path).stat().st_size / (1024**3)
    quant_size = Path(output_path).stat().st_size / (1024**3)
    ratio = quant_size / f16_size * 100

    logger.info("Quantization complete:")
    logger.info("  F16:        %.2f GB", f16_size)
    logger.info("  %s:    %.2f GB (%.1f%%)", quant_type, quant_size, ratio)
    logger.info("  Output:     %s", output_path)

    return output_path


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export trained LoRA adapter to GGUF format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--adapter",
        required=True,
        help="Path to LoRA adapter directory (checkpoint or final)",
    )
    parser.add_argument(
        "--base-model",
        required=True,
        help="HuggingFace base model ID (e.g. Nanbeige/Nanbeige4.1-3B)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output GGUF file path (e.g. models/ctf-agent.gguf)",
    )
    parser.add_argument(
        "--quant",
        default="Q4_K_M",
        choices=QUANT_TYPES,
        help="Quantization type (default: Q4_K_M, use 'none' to skip)",
    )
    parser.add_argument(
        "--llama-cpp",
        default=None,
        help="Path to llama.cpp directory (auto-detected if not set)",
    )
    parser.add_argument(
        "--keep-intermediates",
        action="store_true",
        help="Keep intermediate files (merged model dir, F16 GGUF)",
    )

    args = parser.parse_args()

    # Validate
    if not Path(args.adapter).is_dir():
        logger.error("Adapter path does not exist: %s", args.adapter)
        sys.exit(1)

    llama_cpp_dir = find_llama_cpp(args.llama_cpp)
    if args.quant.lower() != "none" and not llama_cpp_dir.is_dir():
        logger.error(
            "llama.cpp not found. Either:\n"
            "  1. Set --llama-cpp /path/to/llama.cpp\n"
            "  2. Set LLAMA_CPP_DIR environment variable\n"
            "  3. Clone to ~/llama.cpp and run make\n"
            "  4. Use --quant none to skip quantization"
        )
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Merge LoRA
    with tempfile.TemporaryDirectory(prefix="octf_merge_") as merge_dir:
        merged_dir = (
            merge_dir
            if not args.keep_intermediates
            else str(output_path.parent / "merged")
        )
        merge_lora(args.adapter, args.base_model, merged_dir)

        # Step 2: Convert to GGUF
        f16_path = convert_to_gguf(merged_dir, str(output_path), llama_cpp_dir)

        # Step 3: Quantize
        if args.quant.lower() != "none":
            quantize_gguf(f16_path, str(output_path), args.quant, llama_cpp_dir)

            # Clean up F16 intermediate
            if (
                not args.keep_intermediates
                and Path(f16_path).exists()
                and f16_path != str(output_path)
            ):
                Path(f16_path).unlink()
                logger.info("Removed intermediate F16 GGUF")
        else:
            # F16 IS the final output
            if f16_path != str(output_path):
                shutil.move(f16_path, str(output_path))

    logger.info("=" * 60)
    logger.info("Export complete: %s", output_path)
    logger.info("=" * 60)

    # Print next steps
    print("\nNext steps:")
    print("  # Serve with llama.cpp:")
    print(f"  llama-server -m {output_path} --host 0.0.0.0 --port 8080 --jinja")
    print()
    print("  # Or create an Ollama model:")
    print(f"  echo 'FROM {output_path}' > Modelfile")
    print("  ollama create ctf-agent -f Modelfile")
    print("  ollama run ctf-agent")
    print()
    print("  # Or serve with vLLM (from merged HF model):")
    print(f"  vllm serve {args.base_model} --host 0.0.0.0 --port 8000 --dtype bfloat16")


if __name__ == "__main__":
    main()
