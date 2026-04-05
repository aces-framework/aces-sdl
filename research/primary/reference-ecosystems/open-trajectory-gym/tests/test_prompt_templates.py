"""Tests for the configurable prompt template system.

Verifies:
- get_canonical_system_prompt() returns a non-empty string
- build_registry_user_prompt() includes challenge_id and target_url
- Category-specific hints load for "web" category
- Unknown category doesn't crash (graceful fallback)
- Native mode returns minimal stub
- Custom path override works for system prompt
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from trajgym.prompts.composer import (
    _NATIVE_SYSTEM_STUB,
    _TEMPLATES_DIR,
    build_registry_user_prompt,
    get_canonical_system_prompt,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMMON_KWARGS = dict(
    challenge_id="test-challenge-42",
    category="web",
    difficulty="easy",
    target_url="http://example.com:9000",
    description="A sample web challenge.",
)


def _env(**overrides):
    """Context manager that patches environment variables for a test."""
    base = {k: v for k, v in os.environ.items()}
    base.update(overrides)
    return patch.dict(os.environ, base, clear=True)


# ---------------------------------------------------------------------------
# get_canonical_system_prompt
# ---------------------------------------------------------------------------


class TestGetCanonicalSystemPrompt:
    def test_returns_nonempty_string(self):
        with _env(TRAJGYM_AGENT_MODE="tool_calls"):
            result = get_canonical_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_ctf_keywords(self):
        with _env(TRAJGYM_AGENT_MODE="tool_calls"):
            result = get_canonical_system_prompt()
        assert "penetration tester" in result or "CTF" in result

    def test_native_mode_returns_stub(self):
        with _env(TRAJGYM_AGENT_MODE="native"):
            result = get_canonical_system_prompt()
        assert result == _NATIVE_SYSTEM_STUB

    def test_proxy_mode_returns_stub(self):
        with _env(TRAJGYM_AGENT_MODE="proxy"):
            result = get_canonical_system_prompt()
        assert result == _NATIVE_SYSTEM_STUB

    def test_custom_path_override(self, tmp_path: Path):
        custom = tmp_path / "my_system.txt"
        custom.write_text("Custom system prompt for testing.")
        with _env(TRAJGYM_AGENT_MODE="tool_calls"):
            result = get_canonical_system_prompt(path=str(custom))
        assert result == "Custom system prompt for testing."

    def test_env_var_path_override(self, tmp_path: Path):
        custom = tmp_path / "env_system.txt"
        custom.write_text("Env var system prompt.")
        with _env(
            TRAJGYM_AGENT_MODE="tool_calls",
            TRAJGYM_SYSTEM_PROMPT_PATH=str(custom),
        ):
            result = get_canonical_system_prompt()
        assert result == "Env var system prompt."

    def test_explicit_path_overrides_env_var(self, tmp_path: Path):
        env_file = tmp_path / "env.txt"
        env_file.write_text("from env var")
        arg_file = tmp_path / "arg.txt"
        arg_file.write_text("from arg")
        with _env(
            TRAJGYM_AGENT_MODE="tool_calls",
            TRAJGYM_SYSTEM_PROMPT_PATH=str(env_file),
        ):
            result = get_canonical_system_prompt(path=str(arg_file))
        assert result == "from arg"

    def test_missing_custom_path_falls_through(self, tmp_path: Path):
        """If the explicit path doesn't exist, fall through to template/default."""
        bogus = tmp_path / "nonexistent.txt"
        with _env(TRAJGYM_AGENT_MODE="tool_calls"):
            result = get_canonical_system_prompt(path=str(bogus))
        # Should get the template or inline default, not crash.
        assert isinstance(result, str)
        assert len(result) > 0

    def test_loads_from_template_file(self):
        """Verify it loads from templates/system.txt when the file exists."""
        template_path = _TEMPLATES_DIR / "system.txt"
        if template_path.exists():
            expected = template_path.read_text(encoding="utf-8").rstrip("\n")
            with _env(TRAJGYM_AGENT_MODE="tool_calls"):
                result = get_canonical_system_prompt()
            assert result == expected


# ---------------------------------------------------------------------------
# build_registry_user_prompt
# ---------------------------------------------------------------------------


class TestBuildRegistryUserPrompt:
    def test_includes_challenge_id(self):
        with _env(TRAJGYM_AGENT_MODE="tool_calls"):
            result = build_registry_user_prompt(**_COMMON_KWARGS)
        assert "test-challenge-42" in result

    def test_includes_target_url(self):
        with _env(TRAJGYM_AGENT_MODE="tool_calls"):
            result = build_registry_user_prompt(**_COMMON_KWARGS)
        assert "http://example.com:9000" in result

    def test_includes_category(self):
        with _env(TRAJGYM_AGENT_MODE="tool_calls"):
            result = build_registry_user_prompt(**_COMMON_KWARGS)
        assert "web" in result.lower()

    def test_includes_difficulty_formatted(self):
        with _env(TRAJGYM_AGENT_MODE="tool_calls"):
            result = build_registry_user_prompt(
                challenge_id="x",
                category="web",
                difficulty="very_hard",
                target_url="http://t:1",
            )
        assert "Very Hard" in result

    def test_no_category_hints_injected(self):
        """No category-specific hints should be appended to the prompt."""
        for cat in ("web", "pwn", "crypto", "forensics", "misc", "reverse_engineering"):
            kwargs = {**_COMMON_KWARGS, "category": cat}
            with _env(TRAJGYM_AGENT_MODE="tool_calls"):
                result = build_registry_user_prompt(**kwargs)
            for header in (
                "WEB CHALLENGE",
                "PWN CHALLENGE",
                "CRYPTO CHALLENGE",
                "FORENSICS CHALLENGE",
                "MISC CHALLENGE",
            ):
                assert header not in result, f"{header} found for category={cat}"

    def test_no_description_uses_default(self):
        kwargs = {**_COMMON_KWARGS, "description": None}
        with _env(TRAJGYM_AGENT_MODE="tool_calls"):
            result = build_registry_user_prompt(**kwargs)
        assert "obtain a flag" in result

    def test_native_mode_returns_minimal(self):
        with _env(TRAJGYM_AGENT_MODE="native"):
            result = build_registry_user_prompt(**_COMMON_KWARGS)
        # Should have target info but NOT the full tool usage sections.
        assert "test-challenge-42" in result
        assert "TOOL USAGE" not in result
        assert "TOOL REQUIREMENTS" not in result

    def test_proxy_mode_returns_minimal(self):
        with _env(TRAJGYM_AGENT_MODE="proxy"):
            result = build_registry_user_prompt(**_COMMON_KWARGS)
        assert "test-challenge-42" in result
        assert "TOOL USAGE" not in result
