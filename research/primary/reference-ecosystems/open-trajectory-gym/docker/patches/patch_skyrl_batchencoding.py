#!/usr/bin/env python3
"""Patch SkyRL tokenization call sites without runtime monkey patching.

Root issue:
Some tokenizers return ``BatchEncoding`` from
``apply_chat_template(..., tokenize=True)``. Naively calling ``list(...)`` on
that object yields dict keys (for example ``["input_ids", "attention_mask"]``),
which later gets sent to vLLM as token IDs and crashes generation.

Fix:
1. Add a local helper ``_to_token_ids(...)`` in ``skyrl_gym_generator.py``.
2. Rewrite token-id assignments to use ``_to_token_ids(...)``.
3. Normalize ``prompt_token_ids`` handling in remote clients before concatenation.
"""

from __future__ import annotations

import pathlib
import re
import sys

GEN_PATH = pathlib.Path(
    "/usr/local/lib/python3.12/dist-packages/skyrl_train/generators/skyrl_gym_generator.py"
)
CLIENT_PATHS = [
    pathlib.Path(
        "/usr/local/lib/python3.12/dist-packages/skyrl_train/inference_engines/remote_inference_client.py"
    ),
    pathlib.Path(
        "/usr/local/lib/python3.12/dist-packages/skyrl_train/inference_servers/remote_inference_client.py"
    ),
]

_HELPER_SNIPPET = """

def _to_token_ids(tokenized):
    \"\"\"Normalize tokenizer output to a plain list of token ids.

    Transformers may return either:
    - list[int]
    - BatchEncoding-like mapping with ``input_ids``
    \"\"\"
    if hasattr(tokenized, "get"):
        tokenized = tokenized.get("input_ids", tokenized)
    if hasattr(tokenized, "tolist"):
        tokenized = tokenized.tolist()
    if isinstance(tokenized, tuple):
        tokenized = list(tokenized)
    if isinstance(tokenized, list):
        return tokenized
    return list(tokenized)
""".rstrip(
    "\n"
)


def _find_call_end(content: str, call_start: int) -> int:
    """Return index right after the closing ')' for a call expression."""
    depth = 1
    idx = call_start
    while depth > 0 and idx < len(content):
        ch = content[idx]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        idx += 1
    if depth != 0:
        raise RuntimeError(
            "Unbalanced parentheses while patching apply_chat_template call"
        )
    return idx


def _rewrite_assignment(content: str, lhs: str) -> tuple[str, bool]:
    """Rewrite assignment to use `_to_token_ids(...)` idempotently."""
    helper_forms = [
        f"{lhs} = _to_token_ids(self.tokenizer.apply_chat_template(",
        f"{lhs} = _to_token_ids(tokenizer.apply_chat_template(",
    ]
    if any(form in content for form in helper_forms):
        return content, False

    # Upgrade old list(...) wrappers first (older patch versions).
    old_list_forms = [
        f"{lhs} = list(self.tokenizer.apply_chat_template(",
        f"{lhs} = list(tokenizer.apply_chat_template(",
    ]
    for form in old_list_forms:
        if form in content:
            return content.replace(f"{lhs} = list(", f"{lhs} = _to_token_ids(", 1), True

    # Patch plain unwrapped assignment.
    plain_forms = [
        f"{lhs} = self.tokenizer.apply_chat_template(",
        f"{lhs} = tokenizer.apply_chat_template(",
    ]
    matched: str | None = None
    for form in plain_forms:
        if form in content:
            matched = form
            break
    if matched is None:
        return content, False

    wrapped = matched.replace(" = ", " = _to_token_ids(", 1)
    content = content.replace(matched, wrapped, 1)
    call_end = _find_call_end(content, content.index(wrapped) + len(wrapped))
    content = content[:call_end] + ")" + content[call_end:]
    return content, True


def _ensure_helper(content: str) -> tuple[str, bool]:
    if "def _to_token_ids(tokenized):" in content:
        return content, False

    anchors = [
        "logger = logging.getLogger(__name__)\n",
        "from loguru import logger\n",
    ]
    for anchor in anchors:
        if anchor in content:
            return content.replace(anchor, anchor + _HELPER_SNIPPET + "\n\n", 1), True

    # Fallback for import layouts that do not expose a logger anchor.
    dataclass_marker = "\n\n@dataclass"
    if dataclass_marker in content:
        return (
            content.replace(
                dataclass_marker, "\n\n" + _HELPER_SNIPPET + dataclass_marker, 1
            ),
            True,
        )

    return content, False


def patch_generator() -> int:
    if not GEN_PATH.exists():
        print("   skyrl_train generator file not found, skipping")
        return 0

    content = GEN_PATH.read_text()
    changes = 0

    content, helper_changed = _ensure_helper(content)
    if helper_changed:
        changes += 1
        print("   Added _to_token_ids helper in skyrl_gym_generator.py")

    assignments = [
        "self.base_conversation_token_ids",
        "initial_input_ids",
        "agent_loop_state.input_ids",
        "obs_ids_to_add",
        "prompt_token_ids",
    ]
    for lhs in assignments:
        content, changed = _rewrite_assignment(content, lhs)
        if changed:
            changes += 1
            print(f"   Normalized token-id conversion for: {lhs}")

    if changes:
        GEN_PATH.write_text(content)
        print(f"   Patch (generator token normalization): APPLIED ({changes} edits)")
    else:
        print(
            "   Patch (generator token normalization): already applied or patterns not found"
        )
    return changes


def patch_client() -> bool:
    """Patch remote client prompt-token normalization for BatchEncoding safety."""
    changed = False
    new_block = """            # Normalize prompt token IDs from list or BatchEncoding-like mappings.
            if hasattr(prompt_token_ids, "get"):
                prompt_ids_obj = prompt_token_ids.get("input_ids", prompt_token_ids)
            else:
                prompt_ids_obj = prompt_token_ids
            if hasattr(prompt_ids_obj, "tolist"):
                prompt_ids_obj = prompt_ids_obj.tolist()
            if isinstance(prompt_ids_obj, list) and prompt_ids_obj and isinstance(prompt_ids_obj[0], list):
                prompt_ids_obj = prompt_ids_obj[0]
            new_prompt_ids = list(prompt_ids_obj) + accum_token_ids"""

    old_line_pattern = re.compile(
        r"(?P<indent>\s*)# New prompt = original \+ accumulated tokens\s*\n"
        r"(?:(?P=indent).*\n)*?"
        r"(?P=indent)new_prompt_ids = .*?\+ accum_token_ids",
        re.MULTILINE,
    )

    found_any = False
    for client_path in CLIENT_PATHS:
        if not client_path.exists():
            continue
        found_any = True
        content = client_path.read_text()

        if (
            'prompt_ids_obj = prompt_token_ids.get("input_ids", prompt_token_ids)'
            in content
        ):
            print(
                f"   Patch (remote client token normalization): already applied ({client_path})"
            )
            continue

        replaced = False
        if old_line_pattern.search(content):
            content = old_line_pattern.sub(new_block, content, count=1)
            replaced = True
        else:
            old_blocks = [
                "            # New prompt = original + accumulated tokens\n            new_prompt_ids = prompt_token_ids + accum_token_ids",
                "            # New prompt = original + accumulated tokens\n            new_prompt_ids = list(prompt_token_ids) + accum_token_ids",
            ]
            for old in old_blocks:
                if old in content:
                    content = content.replace(old, new_block, 1)
                    replaced = True
                    break

        if not replaced:
            print(
                f"   Patch (remote client token normalization): pattern not found ({client_path})"
            )
            continue

        client_path.write_text(content)
        print(f"   Patch (remote client token normalization): APPLIED ({client_path})")
        changed = True

    if not found_any:
        print("   remote_inference_client file not found in known locations, skipping")
    return changed


def verify() -> None:
    if not GEN_PATH.exists():
        return
    content = GEN_PATH.read_text()
    if "def _to_token_ids(tokenized):" not in content:
        print("   Verification failed: _to_token_ids helper missing")
        sys.exit(1)
    if (
        "_to_token_ids(self.tokenizer.apply_chat_template(" not in content
        and "_to_token_ids(tokenizer.apply_chat_template(" not in content
    ):
        print("   Verification failed: call-site normalization missing")
        sys.exit(1)
    for client_path in CLIENT_PATHS:
        if not client_path.exists():
            continue
        client_content = client_path.read_text()
        if (
            'prompt_ids_obj = prompt_token_ids.get("input_ids", prompt_token_ids)'
            not in client_content
        ):
            print(
                f"   Verification failed: client token normalization missing ({client_path})"
            )
            sys.exit(1)
    print("   Verification passed: token normalization helper and call sites present")


if __name__ == "__main__":
    patch_generator()
    patch_client()
    verify()
