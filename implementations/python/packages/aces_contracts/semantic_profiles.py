"""Helpers for loading shared semantic profile declarations."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import SemanticProfileModel


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def semantic_profiles_root() -> Path:
    return _repo_root() / "contracts" / "profiles" / "semantic"


def semantic_profile_path(profile_id: str) -> Path:
    return semantic_profiles_root() / f"{profile_id}.json"


def load_semantic_profile(profile_id: str) -> SemanticProfileModel:
    path = semantic_profile_path(profile_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SemanticProfileModel.model_validate(payload)
