#!/usr/bin/env python3
"""Inject tool schemas into system message when custom chat template lacks tool support.

Problem (Issue #38):
SkyRL's custom chat templates (qwen3_without_thinking, qwen3_with_thinking) do
NOT have a ``{% if tools %}`` block.  When ``native_tool_schemas=True``, the
runtime passes ``tools=[...]`` via ``chat_template_kwargs``, but the custom
template silently ignores this variable.  Meanwhile, the env skips its text-based
``_inject_tool_schemas()`` because ``native_tool_schemas=True``.

Result: **the model never sees tool definitions or format instructions** — tools
are silently dropped from both injection paths.

Fix:
Patch ``skyrl_gym_generator.py`` to detect when a custom chat template is used
and ``tools`` is in ``chat_template_kwargs``.  If the custom template doesn't
reference the ``tools`` variable, move the tool schemas from kwargs into the
system message content as text.  This ensures the model sees tool definitions
regardless of which template is active.

This is a safety-net patch — the primary fix is ``native_tool_schemas: false``
in the training config + the auto-downgrade guard in ``runtime.py``.  But this
patch catches the case where someone sets ``native_tool_schemas: true`` with a
custom template on a fresh container.
"""
from __future__ import annotations

import pathlib

PATCH_MARKER = "# PATCH: Inject tools into system message for custom templates"

CANDIDATES = [
    pathlib.Path(
        "/usr/local/lib/python3.12/dist-packages/skyrl_train/generators/skyrl_gym_generator.py"
    ),
]

# Also check reference/editable install locations
for root in ["/workspace/open-trajectory-gym", "/workspace"]:
    ref = pathlib.Path(root) / (
        "references/SkyRL-westonbrown/skyrl-train/skyrl_train/"
        "generators/skyrl_gym_generator.py"
    )
    if ref.exists():
        CANDIDATES.append(ref)

# The helper function to inject at module level (before the class definition)
HELPER_CODE = '''
# PATCH: Inject tools into system message for custom templates
def _inject_tools_into_system_message(chat_history, chat_template_kwargs, custom_chat_template):
    """Move tools from kwargs into system message when custom template can't handle them.

    SkyRL's custom templates (qwen3_without_thinking, qwen3_with_thinking) don't
    have a {% if tools %} block.  If tools are in chat_template_kwargs and a
    custom template is active, inject them as text into the system message and
    remove from kwargs to avoid silent loss.

    Returns (possibly-modified chat_history, possibly-modified chat_template_kwargs).
    """
    if not custom_chat_template:
        return chat_history, chat_template_kwargs
    tools = chat_template_kwargs.get("tools")
    if not tools:
        return chat_history, chat_template_kwargs
    # Check if the custom template handles tools
    if "tools" in custom_chat_template:
        return chat_history, chat_template_kwargs
    # Custom template doesn't handle tools — inject as text into system message
    import logging
    _logger = logging.getLogger(__name__)
    _logger.warning(
        "Custom chat template does not handle tools= kwarg — injecting %d "
        "tool schemas as text into the system message. [Issue #38 safety net]",
        len(tools),
    )
    # Build a compact text representation of tool schemas
    tool_lines = []
    for tool_def in tools:
        fn = tool_def.get("function", tool_def) if isinstance(tool_def, dict) else {}
        name = fn.get("name", "unknown")
        desc = fn.get("description", "")
        params = fn.get("parameters", {})
        props = params.get("properties", {})
        required = params.get("required", [])
        param_parts = []
        for pname, pschema in props.items():
            ptype = pschema.get("type", "string")
            req = " [required]" if pname in required else ""
            param_parts.append(f"  - {pname}: {ptype}{req}")
        param_str = "\\n".join(param_parts) if param_parts else "  (no parameters)"
        tool_lines.append(f"- {name}: {desc}\\n{param_str}")
    tools_block = (
        "\\n\\n# Available Tools\\n\\n"
        "Call tools using: <tool_call><function=tool_name>"
        "<parameter=param>value</parameter>"
        "</function></tool_call>\\n\\n"
        + "\\n".join(tool_lines)
        + "\\n"
    )
    # Inject into system message
    import copy
    chat_history = copy.deepcopy(chat_history)
    if chat_history and chat_history[0].get("role") == "system":
        sys_content = chat_history[0].get("content", "")
        # Skip if tools already present in system message
        if "# Available Tools" not in sys_content and "<tools>" not in sys_content:
            chat_history[0] = {**chat_history[0], "content": sys_content + tools_block}
    else:
        chat_history.insert(0, {
            "role": "system",
            "content": "You are a helpful assistant." + tools_block,
        })
    # Remove tools from kwargs to avoid confusing the template
    chat_template_kwargs = dict(chat_template_kwargs)
    del chat_template_kwargs["tools"]
    return chat_history, chat_template_kwargs
'''

patched_count = 0

for filepath in CANDIDATES:
    if not filepath.exists():
        continue

    content = filepath.read_text()

    if PATCH_MARKER in content:
        print(f"patch_skyrl_custom_template_tools: already applied in {filepath}")
        patched_count += 1
        continue

    # 1. Inject the helper function after imports (before class definition)
    class_marker = "class SkyRLGymGenerator"
    if class_marker not in content:
        print(f"SKIP: Could not find {class_marker} in {filepath}")
        continue

    content = content.replace(class_marker, HELPER_CODE + "\n\n" + class_marker, 1)

    # 2. Patch agent_loop to call the helper before initial tokenization
    # Target: the env.init() call followed by initial apply_chat_template
    # We inject right after chat_history deepcopy and env.init()
    old_init_block = "chat_history, _ = await self._run_in_executor_if_available(env.init, chat_history)"
    if old_init_block not in content:
        print(f"SKIP: Could not find env.init call in {filepath}")
        continue

    new_init_block = (
        old_init_block
        + "\n        # PATCH: Inject tools into system message if custom template can't handle them\n"
        + "        chat_history, _patched_kwargs = _inject_tools_into_system_message(\n"
        + "            chat_history, self.generator_cfg.chat_template_kwargs, self.custom_chat_template\n"
        + "        )"
    )
    content = content.replace(old_init_block, new_init_block, 1)

    filepath.write_text(content)
    print(f"patch_skyrl_custom_template_tools: applied to {filepath}")
    patched_count += 1

if patched_count == 0:
    print("WARNING: Could not find any SkyRL skyrl_gym_generator.py to patch")
    print("  (This patch is a safety net — primary fix is native_tool_schemas: false)")
    # Don't exit(1) — this is an optional safety-net patch
else:
    print(f"patch_skyrl_custom_template_tools: {patched_count} file(s) patched")
