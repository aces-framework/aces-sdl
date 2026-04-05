"""Tests for BoxPwnr source resolution in AgentRunner."""

from __future__ import annotations

from pathlib import Path

from trajgym.integrations.boxpwnr_runner import _default_boxpwnr_source_candidates


def test_default_candidates_include_reference_paths(monkeypatch) -> None:
    monkeypatch.delenv("TRAJGYM_BOXPWNR_SRC", raising=False)
    monkeypatch.delenv("TRAJGYM_DEFAULT_AGENT_SRC", raising=False)

    candidates = [str(p) for p in _default_boxpwnr_source_candidates()]
    assert any(path.endswith("/references/boxpwnr/src") for path in candidates)
    assert any(path.endswith("/references/BoxPwnr/src") for path in candidates)


def test_candidates_respect_env_and_dedupe(monkeypatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom_boxpwnr_src"
    monkeypatch.setenv("TRAJGYM_BOXPWNR_SRC", str(custom))
    monkeypatch.setenv("TRAJGYM_DEFAULT_AGENT_SRC", str(custom))

    candidates = _default_boxpwnr_source_candidates()
    as_str = [str(p) for p in candidates]
    assert str(custom.resolve()) in as_str
    assert as_str.count(str(custom.resolve())) == 1
