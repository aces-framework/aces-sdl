#!/usr/bin/env python3
"""Convert OmegaConf containers in chat_template_kwargs before apply_chat_template.

Problem:
When tools are passed via chat_template_kwargs, they go through OmegaConf.create()
which converts dicts → DictConfig and lists → ListConfig. The transformers
apply_chat_template() validates tools with isinstance(tool, dict), which fails
for DictConfig objects:
    ValueError: Tools should either be a JSON schema, or a callable function
    with type hints and a docstring suitable for auto-conversion to a schema.

Fix:
Wrap the chat_template_kwargs unpacking in skyrl_gym_generator.py to convert
OmegaConf containers back to plain Python dicts/lists before passing to
apply_chat_template(). Uses OmegaConf.to_container() when available, with
a recursive fallback for non-OmegaConf environments.
"""
from __future__ import annotations

import pathlib
import sys

PATCH_MARKER = "# PATCH: Convert OmegaConf containers in chat_template_kwargs"

CANDIDATES = [
    pathlib.Path(
        "/usr/local/lib/python3.12/dist-packages/skyrl_train/generators/skyrl_gym_generator.py"
    ),
]

# Also check reference/editable install locations
for root in ["/workspace/open-trajectory-gym", "/workspace"]:
    ref = (
        pathlib.Path(root)
        / "references/SkyRL-westonbrown/skyrl-train/skyrl_train/generators/skyrl_gym_generator.py"
    )
    if ref.exists():
        CANDIDATES.append(ref)

# The helper function to inject at module level
HELPER_CODE = '''
# PATCH: Convert OmegaConf containers in chat_template_kwargs
def _resolve_chat_template_kwargs(kwargs):
    """Convert OmegaConf DictConfig/ListConfig to plain Python dicts/lists.

    transformers.apply_chat_template() validates tools with isinstance(tool, dict)
    which fails for OmegaConf DictConfig. This converts all nested containers.
    """
    try:
        from omegaconf import OmegaConf, DictConfig, ListConfig
        if any(isinstance(v, (DictConfig, ListConfig)) for v in kwargs.values()):
            return OmegaConf.to_container(OmegaConf.create(kwargs), resolve=True)
    except ImportError:
        pass
    return dict(kwargs)
'''

patched_count = 0

for filepath in CANDIDATES:
    if not filepath.exists():
        continue

    content = filepath.read_text()

    if PATCH_MARKER in content:
        print(f"patch_skyrl_chat_template_kwargs: already applied in {filepath}")
        patched_count += 1
        continue

    # 1. Inject the helper function after imports (before class definition)
    class_marker = "class SkyRLGymGenerator"
    if class_marker not in content:
        print(f"SKIP: Could not find {class_marker} in {filepath}")
        continue

    content = content.replace(class_marker, HELPER_CODE + "\n\n" + class_marker, 1)

    # 2. Replace all **self.generator_cfg.chat_template_kwargs with resolved version
    old_spread = "**self.generator_cfg.chat_template_kwargs"
    new_spread = (
        "**_resolve_chat_template_kwargs(self.generator_cfg.chat_template_kwargs)"
    )

    if old_spread not in content:
        print(f"SKIP: Could not find '{old_spread}' in {filepath}")
        continue

    content = content.replace(old_spread, new_spread)

    filepath.write_text(content)
    count = content.count(new_spread)
    print(
        f"patch_skyrl_chat_template_kwargs: applied to {filepath} ({count} call sites)"
    )
    patched_count += 1

if patched_count == 0:
    print("ERROR: Could not find any SkyRL skyrl_gym_generator.py to patch")
    sys.exit(1)
else:
    print(f"patch_skyrl_chat_template_kwargs: {patched_count} file(s) patched")
