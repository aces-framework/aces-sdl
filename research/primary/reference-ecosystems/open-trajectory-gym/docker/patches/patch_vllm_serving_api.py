#!/usr/bin/env python3
"""Patch SkyRL vllm_engine.py for vLLM serving API signature drift.

SkyRL 0.3.x spans vLLM signatures where OpenAI-serving constructors changed:
- Newer vLLM: OpenAIServingModels(engine, base_model_paths)
- Older vLLM: OpenAIServingModels(engine, model_config, base_model_paths)

This patch:
1) Rewrites model-constructor logic to a safe try/except fallback.
2) Removes hardcoded ``model_config=...`` kwargs from Chat/Completion calls.
3) Ensures ``**legacy_kwargs`` is forwarded to Chat/Completion.
4) Verifies patched source compiles before writing.
"""

from __future__ import annotations

import pathlib
import re
import sys

VLLM_ENGINE_PATH = pathlib.Path(
    "/usr/local/lib/python3.12/dist-packages/skyrl_train/inference_engines/vllm/vllm_engine.py"
)

_MODELS_BLOCK = """        # PATCH: vLLM serving compatibility (OpenAIServingModels kwargs)
        # Prefer the vLLM>=0.11.2 signature and fall back to legacy when needed.
        legacy_kwargs = {}
        try:
            models = OpenAIServingModels(engine, base_model_paths)
        except TypeError:
            models = OpenAIServingModels(engine, model_config, base_model_paths)
            legacy_kwargs["model_config"] = model_config
"""


def _patch_models_constructor(content: str) -> tuple[str, bool]:
    changed = False

    # Replace any multi-line branch block (including malformed variants).
    block_pattern = re.compile(
        r"(?ms)^\s*# vllm >= 0\.11\.2 removed model_config from OpenAI serving APIs.*?"
        r"legacy_kwargs\[[\"']model_config[\"']\]\s*=\s*model_config\s*\n"
    )
    if block_pattern.search(content):
        content = block_pattern.sub(_MODELS_BLOCK, content, count=1)
        changed = True

    # Replace simple one-line legacy constructor if still present.
    old_line = "models = OpenAIServingModels(engine, model_config, base_model_paths)"
    if old_line in content and _MODELS_BLOCK.strip() not in content:
        content = content.replace(
            f"        {old_line}\n",
            _MODELS_BLOCK,
            1,
        )
        changed = True

    return content, changed


def _remove_model_config_kwargs(content: str) -> tuple[str, bool]:
    changed = False
    if "model_config=model_config," in content:
        content = content.replace("            model_config=model_config,\n", "")
        changed = True
    return content, changed


def _ensure_legacy_kwargs_forwarding(content: str) -> tuple[str, bool]:
    changed = False

    # Chat constructor: add **legacy_kwargs before **openai_kwargs when missing.
    chat_pattern = re.compile(
        r"(?ms)(self\.openai_serving_chat = OpenAIServingChat\(\n.*?chat_template_content_format=\"auto\",\n)"
        r"(\s*\*\*openai_kwargs,)"
    )
    m = chat_pattern.search(content)
    if m:
        block = m.group(0)
        if "**legacy_kwargs," not in block:
            replacement = m.group(1) + "            **legacy_kwargs,\n" + m.group(2)
            content = content[: m.start()] + replacement + content[m.end() :]
            changed = True

    # Completion constructor: add **legacy_kwargs when missing.
    completion_pattern = re.compile(
        r"(?ms)(self\.openai_serving_completion = OpenAIServingCompletion\(\n.*?request_logger=.*?,\n)(\s*\))"
    )
    m2 = completion_pattern.search(content)
    if m2:
        block = m2.group(0)
        if "**legacy_kwargs," not in block:
            replacement = m2.group(1) + "            **legacy_kwargs,\n" + m2.group(2)
            content = content[: m2.start()] + replacement + content[m2.end() :]
            changed = True

    return content, changed


def main() -> None:
    if not VLLM_ENGINE_PATH.exists():
        print(f"   Patch (vLLM serving API): SKIP - {VLLM_ENGINE_PATH} not found")
        return

    content = VLLM_ENGINE_PATH.read_text()
    original = content

    content, c1 = _patch_models_constructor(content)
    content, c2 = _remove_model_config_kwargs(content)
    content, c3 = _ensure_legacy_kwargs_forwarding(content)

    if not (c1 or c2 or c3):
        print("   Patch (vLLM serving API): already applied or patterns not found")
        return

    try:
        compile(content, str(VLLM_ENGINE_PATH), "exec")
    except SyntaxError as exc:
        print(f"   Patch (vLLM serving API): FAILED - syntax error after patch: {exc}")
        sys.exit(1)

    if content == original:
        print("   Patch (vLLM serving API): no-op")
        return

    VLLM_ENGINE_PATH.write_text(content)
    print("   Patch (vLLM serving API): APPLIED")


if __name__ == "__main__":
    main()
