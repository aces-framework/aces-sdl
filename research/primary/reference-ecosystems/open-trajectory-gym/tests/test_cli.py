"""Smoke tests for CLI entry points.

Validates:
- CLI entry points are registered in pyproject.toml
- trajgym-validate runs without error (no GPU needed)
- Key modules import cleanly
"""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# pyproject.toml entry point registration
# ---------------------------------------------------------------------------


class TestEntryPointRegistration:
    def test_pyproject_has_scripts(self):
        """pyproject.toml should define CLI entry points."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        assert pyproject.exists(), "pyproject.toml not found"

        content = pyproject.read_text()
        assert "[project.scripts]" in content, "No [project.scripts] section"

    def test_expected_entry_points(self):
        """All expected CLI commands should be registered."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()

        expected = [
            "trajgym-train",
            "trajgym-convert",
            "trajgym-split",
            "trajgym-validate",
            "trajgym-export",
            "trajgym-eval",
        ]
        for cmd in expected:
            assert cmd in content, f"Entry point '{cmd}' not in pyproject.toml"


# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------


class TestModuleImports:
    """Verify key modules can be imported without GPU or external services."""

    @pytest.mark.parametrize(
        "module",
        [
            "trajgym.data.converter",
            "trajgym.data.splitter",
            "trajgym.rewards.reward",
            "trajgym.formatters",
            "trajgym.formatters.base",
            "trajgym.formatters.qwen3",
            "trajgym.formatters.glm4",
            "trajgym.formatters.devstral",
            "trajgym.formatters.tool_registry",
            "trajgym.cli.validate_pipeline",
        ],
    )
    def test_import(self, module):
        importlib.import_module(module)


# ---------------------------------------------------------------------------
# validate_pipeline smoke test
# ---------------------------------------------------------------------------


class TestValidatePipeline:
    def test_validate_runs(self):
        """trajgym-validate should run and exit (may have warnings)."""
        result = subprocess.run(
            [sys.executable, "-m", "trajgym.cli.validate_pipeline"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
            env={
                **__import__("os").environ,
                "PYTHONPATH": str(PROJECT_ROOT / "src"),
            },
        )
        # Exit code 0 = all checks passed, 1 = some checks failed (acceptable
        # in CI where data files may not exist). Either is fine for smoke test.
        assert result.returncode in (0, 1), (
            f"validate_pipeline crashed with code {result.returncode}:\n"
            f"stdout: {result.stdout[:1000]}\n"
            f"stderr: {result.stderr[:1000]}"
        )
        # Should produce visible output (not crash silently)
        assert len(result.stdout) > 0, "validate_pipeline produced no output"
