#!/usr/bin/env python3
"""Create compatibility shim modules for SkyRL 0.3.1 ↔ vLLM 0.16+ import paths.

SkyRL 0.3.1 imports from vLLM 0.13-0.15 paths that were restructured in 0.16.
This script creates shim modules at the old paths that re-export from the new paths.

Mapping:
  OLD (SkyRL expects)                              → NEW (vLLM 0.16)
  vllm.entrypoints.openai.serving_chat             → vllm.entrypoints.openai.chat_completion.serving
  vllm.entrypoints.openai.serving_completion       → vllm.entrypoints.openai.completion.serving
  vllm.entrypoints.openai.serving_models           → vllm.entrypoints.openai.models.{serving,protocol}
  vllm.entrypoints.openai.protocol                 → vllm.entrypoints.openai.{chat_completion,completion,engine}.protocol
"""
import pathlib
import sys


def _find_vllm_openai_dir():
    """Dynamically locate vllm/entrypoints/openai using importlib."""
    try:
        import vllm

        return pathlib.Path(vllm.__file__).parent / "entrypoints" / "openai"
    except ImportError:
        return None


def main():
    OPENAI_DIR = _find_vllm_openai_dir()
    if OPENAI_DIR is None or not OPENAI_DIR.exists():
        print("ERROR: vllm/entrypoints/openai not found (vllm not installed?)")
        sys.exit(1)

    created = 0

    # 1. serving_chat.py shim
    shim_path = OPENAI_DIR / "serving_chat.py"
    if not shim_path.exists():
        shim_path.write_text(
            '"""Compatibility shim: SkyRL 0.3.1 → vLLM 0.16+"""\n'
            "from vllm.entrypoints.openai.chat_completion.serving import *  # noqa\n"
            "from vllm.entrypoints.openai.chat_completion.serving import OpenAIServingChat  # noqa\n"
        )
        created += 1
        print(f"   Created shim: {shim_path}")
    else:
        print(f"   Shim exists: {shim_path}")

    # 2. serving_completion.py shim
    shim_path = OPENAI_DIR / "serving_completion.py"
    if not shim_path.exists():
        shim_path.write_text(
            '"""Compatibility shim: SkyRL 0.3.1 → vLLM 0.16+"""\n'
            "from vllm.entrypoints.openai.completion.serving import *  # noqa\n"
            "from vllm.entrypoints.openai.completion.serving import OpenAIServingCompletion  # noqa\n"
        )
        created += 1
        print(f"   Created shim: {shim_path}")
    else:
        print(f"   Shim exists: {shim_path}")

    # 3. serving_models.py shim
    shim_path = OPENAI_DIR / "serving_models.py"
    if not shim_path.exists():
        shim_path.write_text(
            '"""Compatibility shim: SkyRL 0.3.1 → vLLM 0.16+"""\n'
            "from vllm.entrypoints.openai.models.serving import *  # noqa\n"
            "from vllm.entrypoints.openai.models.serving import OpenAIServingModels  # noqa\n"
            "from vllm.entrypoints.openai.models.protocol import BaseModelPath  # noqa\n"
        )
        created += 1
        print(f"   Created shim: {shim_path}")
    else:
        print(f"   Shim exists: {shim_path}")

    # 4. protocol.py shim (aggregates from multiple new locations)
    shim_path = OPENAI_DIR / "protocol.py"
    if not shim_path.exists():
        shim_path.write_text(
            '"""Compatibility shim: SkyRL 0.3.1 → vLLM 0.16+"""\n'
            "from vllm.entrypoints.openai.chat_completion.protocol import (  # noqa\n"
            "    ChatCompletionRequest,\n"
            "    ChatCompletionResponse,\n"
            ")\n"
            "from vllm.entrypoints.openai.completion.protocol import (  # noqa\n"
            "    CompletionRequest,\n"
            "    CompletionResponse,\n"
            ")\n"
            "from vllm.entrypoints.openai.engine.protocol import (  # noqa\n"
            "    ErrorResponse,\n"
            ")\n"
        )
        created += 1
        print(f"   Created shim: {shim_path}")
    else:
        print(f"   Shim exists: {shim_path}")

    if created > 0:
        print(f"   vLLM compat shims: {created} created")
    else:
        print("   vLLM compat shims: all already exist")


if __name__ == "__main__":
    main()
