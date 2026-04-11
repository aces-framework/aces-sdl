"""Helpers for loading shared reference model declarations."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import ReferenceModelCatalogModel


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def reference_model_catalog_path() -> Path:
    return _repo_root() / "contracts" / "concept-authority" / "reference-models-v1.json"


def load_reference_model_catalog() -> ReferenceModelCatalogModel:
    path = reference_model_catalog_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ReferenceModelCatalogModel.model_validate(payload)
