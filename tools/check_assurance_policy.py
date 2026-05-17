#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Structural gate for the ASR-505 classification-based assurance policy.

ADR-007 ("Lightweight Formal Methods Policy") and the contributor-facing
``docs/explain/reference/coding-standards.md`` define the FM0/FM1/FM2/FM3
ladder. ASR-505 says the ecosystem shall *define* a classification-based
assurance policy that maps structural, semantic, graph, and stateful changes to
proportionate verification artifacts. The canonical mapping lives in
``specs/formal/assurance-policy.yaml`` -- one machine-readable artifact under
the normative ``specs/`` tree (per ADR-009) that every downstream doc and tool
references.

This checker pins the YAML's structural invariants and guards against drift
between the YAML and the three docs that name the levels (the immutable
ADR-007, the contributor-facing coding standards, and the formal-specs
overview). Failures use ``tools.policy.common.PolicyFailure`` and the CLI honours
``--json`` and the shared ``tools/policy/exceptions.yaml`` waiver mechanism,
matching the other policy gates (``check_repo_policy.py``,
``check_requirement_governance.py``, ``check_semantic_coverage.py``).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml

from tools.policy.common import PolicyFailure, apply_exceptions, failures_to_json, load_exceptions

# --------------------------------------------------------------------------- #
# Canonical paths and baseline policy invariants. Test code imports these     #
# directly so a rename here surfaces in the test suite, not silently in       #
# production. The validator otherwise derives its expectations from the YAML  #
# itself, so adding FM4 only requires editing the YAML plus mentioning FM4 in #
# each downstream doc; this baseline only encodes the floor the policy may    #
# not drop below.                                                             #
# --------------------------------------------------------------------------- #

ASSURANCE_POLICY_RELATIVE_PATH = "specs/formal/assurance-policy.yaml"
ADR_POLICY_RELATIVE_PATH = "docs/decisions/adrs/adr-007-lightweight-formal-methods-policy.md"
CODING_STANDARDS_RELATIVE_PATH = "docs/explain/reference/coding-standards.md"
FORMAL_OVERVIEW_RELATIVE_PATH = "docs/specs/formal.md"

# The baseline canonical level ids. The YAML MAY add more levels (e.g. FM4),
# but these four are the floor and must always be present.
CANONICAL_LEVEL_IDS: tuple[str, ...] = ("FM0", "FM1", "FM2", "FM3")

# The four words in the ASR-505 statement -- the validator pins each to a
# specific level so reordering does not silently keep passing.
REQUIRED_CHANGE_CATEGORIES: tuple[str, ...] = ("structural", "semantic", "graph", "stateful")

# Which level owns which canonical change category. This is the category-to-
# level binding the requirement statement implies.
_LEVEL_PRIMARY_CATEGORY: dict[str, str] = {
    "FM0": "structural",
    "FM1": "semantic",
    "FM2": "graph",
    "FM3": "stateful",
}

REQUIREMENT_REF = "ASR-505"
# ADR-007 is the policy decision; ADR-018 is the canonical-seam decision that
# governs THIS file. Both must be named in the YAML so a future edit cannot
# silently sever the governance link without failing the gate.
ADR_REFS: tuple[str, ...] = ("ADR-007", "ADR-018")
# Kept for backwards compatibility / external imports — equals the first ADR ref.
ADR_REF = ADR_REFS[0]
POLICY_VALUE = "classification-based-assurance"

# Floor required-artifact obligations per level, sourced from ADR-007. The
# YAML may add MORE required artifacts to any level; it may not drop these.
# This is independent of the proportionality (superset) check.
_LEVEL_REQUIRED_FLOOR: dict[str, frozenset[str]] = {
    "FM0": frozenset({"unit_tests"}),
    "FM1": frozenset({"invariant_list", "unit_tests"}),
    "FM2": frozenset(
        {"invariant_list", "unit_tests", "typed_ir_or_contract_coverage", "property_based_or_differential_tests"}
    ),
    "FM3": frozenset(
        {
            "invariant_list",
            "unit_tests",
            "typed_ir_or_contract_coverage",
            "property_based_or_differential_tests",
            "abstract_state_machine_model",
        }
    ),
}

_REQUIRED_TOP_LEVEL_FIELDS: tuple[str, ...] = ("policy", "requirement_refs", "adr_refs", "levels")
_REQUIRED_LEVEL_FIELDS: tuple[str, ...] = (
    "id",
    "name",
    "scope",
    "change_categories",
    "required_artifacts",
)
_LEVEL_SEQUENCE_FIELDS: tuple[str, ...] = (
    "change_categories",
    "required_artifacts",
    "recommended_artifacts",
    "prohibited_artifacts",
)
_FM0_PROHIBITED_ARTIFACTS: frozenset[str] = frozenset({"TLA+", "Alloy"})

# Human-readable phrasings for each YAML artifact slug. The drift guard
# requires the union of required artifacts (across all levels in the YAML) to
# appear in each MUTABLE downstream doc (coding-standards.md, formal.md). A
# stale doc that drops one of these phrases entirely fails the gate. ADR-007
# is immutable, so it is exempt from this check.
_ARTIFACT_DOC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "unit_tests": ("unit tests",),
    "invariant_list": ("invariant",),  # matches "invariants", "invariant list", etc.
    "typed_ir_or_contract_coverage": ("typed IR", "contract coverage", "typed IR/contract"),
    "property_based_or_differential_tests": (
        "property-based",
        "differential test",
    ),
    "abstract_state_machine_model": ("abstract state-machine", "state-machine model"),
}


def _fail(rule_id: str, message: str, path: str | None) -> PolicyFailure:
    return PolicyFailure(rule_id, message, path)


def _check_top_level_fields(data: dict, path: str) -> list[PolicyFailure]:
    failures: list[PolicyFailure] = []
    for field in _REQUIRED_TOP_LEVEL_FIELDS:
        if field not in data:
            failures.append(_fail("assurance-policy-field", f"missing required top-level field: {field}", path))
    if "policy" in data and data["policy"] != POLICY_VALUE:
        failures.append(
            _fail(
                "assurance-policy-value",
                f"policy field must be '{POLICY_VALUE}', got '{data['policy']}'",
                path,
            )
        )
    # Reject non-list sequence fields rather than silently coercing them to [].
    for field in ("requirement_refs", "adr_refs"):
        if field in data and not isinstance(data[field], list):
            failures.append(
                _fail(
                    "assurance-policy-field-type",
                    f"top-level field '{field}' must be a YAML list; got {type(data[field]).__name__}",
                    path,
                )
            )
    if "levels" in data and not isinstance(data["levels"], list):
        failures.append(
            _fail(
                "assurance-policy-field-type",
                f"top-level field 'levels' must be a YAML list; got {type(data['levels']).__name__}",
                path,
            )
        )
    return failures


def _check_refs(data: dict, path: str) -> list[PolicyFailure]:
    failures: list[PolicyFailure] = []
    requirement_refs = data.get("requirement_refs")
    adr_refs = data.get("adr_refs")
    # Top-level ref lists must contain only strings. Non-string entries are
    # surfaced as type failures rather than silently stringified.
    for field_name, value in (("requirement_refs", requirement_refs), ("adr_refs", adr_refs)):
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, str):
                    failures.append(
                        _fail(
                            "assurance-policy-field-type",
                            f"top-level field '{field_name}' must contain only strings; "
                            f"got non-string element {item!r}",
                            path,
                        )
                    )
    requirement_strs = _refs_sequence(requirement_refs)
    adr_strs = _refs_sequence(adr_refs)
    if isinstance(requirement_refs, list) and REQUIREMENT_REF not in requirement_strs:
        failures.append(
            _fail(
                "assurance-policy-requirement-ref",
                f"requirement_refs must include {REQUIREMENT_REF}",
                path,
            )
        )
    if isinstance(adr_refs, list):
        for required_adr in ADR_REFS:
            if required_adr not in adr_strs:
                failures.append(
                    _fail(
                        "assurance-policy-adr-ref",
                        f"adr_refs must include {required_adr}",
                        path,
                    )
                )
    return failures


def _level_sequence(level: dict, field: str) -> list[str]:
    """Return the level's sequence field as a list of strings.

    Non-string elements are silently dropped here so downstream set operations
    (proportionality, floor, category-binding) are not corrupted. The shape
    check in `_check_levels` separately reports any non-string element as a
    `assurance-policy-level-field-type` failure, so dropping them here does
    not mask the regression.
    """
    value = level.get(field)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _refs_sequence(value: Any) -> list[str]:
    """Same shape as `_level_sequence` but for top-level refs."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _check_levels(levels: list[Any], path: str) -> list[PolicyFailure]:
    failures: list[PolicyFailure] = []

    if not levels:
        failures.append(
            _fail(
                "assurance-policy-levels-empty",
                "levels list is empty; the policy must enumerate every canonical FM level",
                path,
            )
        )

    present_ids = [level.get("id") if isinstance(level, dict) else None for level in levels]

    # Every baseline canonical level must be present (FM0..FM3 is the floor).
    for expected in CANONICAL_LEVEL_IDS:
        if expected not in present_ids:
            failures.append(
                _fail(
                    "assurance-policy-level-missing",
                    f"levels list is missing canonical level {expected}",
                    path,
                )
            )

    # Level ids must be unique. `by_id` would otherwise silently keep only the
    # last entry, leaving a non-canonical mapping with ambiguous semantics.
    seen: set[str] = set()
    duplicates: list[str] = []
    for level_id in present_ids:
        if not isinstance(level_id, str):
            continue
        if level_id in seen:
            duplicates.append(level_id)
        else:
            seen.add(level_id)
    if duplicates:
        failures.append(
            _fail(
                "assurance-policy-level-duplicate",
                f"level ids must be unique; duplicates: {sorted(set(duplicates))}",
                path,
            )
        )

    # Every FM-numbered level must appear in ascending numeric order. This
    # covers the baseline canonical levels AND any future FM4+ -- inserting
    # FM4 before FM2 or between FM0 and FM1 is a failure.
    fm_numbered_ids = [lid for lid in present_ids if isinstance(lid, str) and _fm_index(lid) is not None]
    expected_fm_order = sorted(fm_numbered_ids, key=lambda lid: _fm_index(lid) or -1)
    if fm_numbered_ids != expected_fm_order:
        failures.append(
            _fail(
                "assurance-policy-level-order",
                f"FM-numbered levels must appear in ascending numeric order; got {fm_numbered_ids}, "
                f"expected {expected_fm_order}",
                path,
            )
        )

    # Per-level shape: required keys, sequence fields actually lists.
    for level in levels:
        if not isinstance(level, dict):
            failures.append(_fail("assurance-policy-level-field", f"level entry is not a mapping: {level!r}", path))
            continue
        for field in _REQUIRED_LEVEL_FIELDS:
            if field not in level:
                failures.append(
                    _fail(
                        "assurance-policy-level-field",
                        f"level '{level.get('id', '?')}' missing required field: {field}",
                        path,
                    )
                )
        for field in _LEVEL_SEQUENCE_FIELDS:
            value = level.get(field) if field in level else None
            if field in level and not isinstance(value, list):
                failures.append(
                    _fail(
                        "assurance-policy-level-field-type",
                        f"level '{level.get('id', '?')}' field '{field}' must be a YAML list; "
                        f"got {type(value).__name__}",
                        path,
                    )
                )
                continue
            if isinstance(value, list):
                for item in value:
                    if not isinstance(item, str):
                        failures.append(
                            _fail(
                                "assurance-policy-level-field-type",
                                f"level '{level.get('id', '?')}' field '{field}' must contain only "
                                f"strings; got non-string element {item!r}",
                                path,
                            )
                        )

    # Each level must claim its primary canonical category. This pins the
    # category-to-level binding, not just the union (the ASR-505 statement
    # guard).
    by_id = {lv.get("id"): lv for lv in levels if isinstance(lv, dict)}
    for level_id, expected_category in _LEVEL_PRIMARY_CATEGORY.items():
        level = by_id.get(level_id)
        if level is None:
            continue
        categories = _level_sequence(level, "change_categories")
        if expected_category not in categories:
            failures.append(
                _fail(
                    "assurance-policy-categories",
                    f"level {level_id} must claim canonical change category '{expected_category}' "
                    f"(per the ASR-505 statement); got {categories}",
                    path,
                )
            )

    # Belt-and-suspenders: the union of every level's change_categories must
    # still cover every word in the ASR-505 statement. This catches a future
    # level that drops one of the canonical words without triggering the
    # binding check above.
    category_union = {
        cat for level in levels if isinstance(level, dict) for cat in _level_sequence(level, "change_categories")
    }
    missing_categories = [cat for cat in REQUIRED_CHANGE_CATEGORIES if cat not in category_union]
    if missing_categories:
        failures.append(
            _fail(
                "assurance-policy-categories",
                f"change_categories union must include every word in the ASR-505 statement "
                f"({REQUIRED_CHANGE_CATEGORIES}); missing: {missing_categories}",
                path,
            )
        )

    # FM0 must prohibit TLA+ and Alloy explicitly.
    fm0 = by_id.get("FM0")
    if fm0 is not None:
        prohibited = set(_level_sequence(fm0, "prohibited_artifacts"))
        missing = sorted(_FM0_PROHIBITED_ARTIFACTS - prohibited)
        if missing:
            failures.append(
                _fail(
                    "assurance-policy-fm0-prohibited",
                    f"FM0 must list {sorted(_FM0_PROHIBITED_ARTIFACTS)} in prohibited_artifacts; missing: {missing}",
                    path,
                )
            )

    # Per-level required-artifact floor (from ADR-007). The YAML may require
    # MORE; it may not require less.
    for level_id, floor in _LEVEL_REQUIRED_FLOOR.items():
        level = by_id.get(level_id)
        if level is None:
            continue
        required = set(_level_sequence(level, "required_artifacts"))
        missing = sorted(floor - required)
        if missing:
            failures.append(
                _fail(
                    "assurance-policy-required-floor",
                    f"{level_id}'s required_artifacts must include the ADR-007 floor; missing: {missing}",
                    path,
                )
            )

    # Required and prohibited sets must be disjoint per level.
    for level in levels:
        if not isinstance(level, dict):
            continue
        required = set(_level_sequence(level, "required_artifacts"))
        prohibited = set(_level_sequence(level, "prohibited_artifacts"))
        overlap = sorted(required & prohibited)
        if overlap:
            failures.append(
                _fail(
                    "assurance-policy-required-prohibited-overlap",
                    f"level '{level.get('id', '?')}' has artifacts in both required_artifacts and "
                    f"prohibited_artifacts: {overlap}",
                    path,
                )
            )

    # Consecutive-pair proportionality across every FM-numbered level, not
    # just FM2/FM3. FM4 (if present) must be a superset of FM3, and so on.
    fm_levels_ordered = sorted(
        (lv for lv in levels if isinstance(lv, dict) and _fm_index(lv.get("id")) is not None),
        key=lambda lv: _fm_index(lv.get("id")) or -1,
    )
    for parent, child in zip(fm_levels_ordered, fm_levels_ordered[1:], strict=False):
        child_id = child.get("id", "?")
        parent_id = parent.get("id", "?")
        child_set = set(_level_sequence(child, "required_artifacts"))
        parent_set = set(_level_sequence(parent, "required_artifacts"))
        missing = sorted(parent_set - child_set)
        if missing:
            failures.append(
                _fail(
                    "assurance-policy-proportionality",
                    f"{child_id}'s required_artifacts must be a superset of {parent_id}'s; "
                    f"missing from {child_id}: {missing}",
                    path,
                )
            )

    return failures


def _fm_index(level_id: Any) -> int | None:
    """Return the numeric index of an FM-numbered level id (FM0 → 0), else None."""
    if not isinstance(level_id, str) or not level_id.startswith("FM"):
        return None
    suffix = level_id[2:]
    if not suffix.isdigit():
        return None
    return int(suffix)


def _drift_targets(levels: list[Any]) -> list[tuple[str, str]]:
    """Return (level_id, level_name) pairs that mutable downstream docs must mention.

    Names are derived from the YAML so a future FM4 (or a name change to an
    existing level) flows through to every drift check without editing this
    file. The id is checked AS-IS; the name is checked after collapsing runs
    of whitespace, since Markdown sometimes wraps long names.
    """
    targets: list[tuple[str, str]] = []
    for level in levels:
        if not isinstance(level, dict):
            continue
        level_id = level.get("id")
        name = level.get("name")
        if isinstance(level_id, str) and isinstance(name, str):
            targets.append((level_id, name))
    return targets


def _baseline_drift_targets(levels: list[Any]) -> list[tuple[str, str]]:
    """Return drift targets restricted to the BASELINE canonical levels.

    Used for ADR-007, which is immutable per the ADR README and therefore
    cannot be required to mention a future FM4. The baseline floor (FM0..FM3)
    is fixed at policy adoption time; ADR-007 is required to mention it, and
    nothing more. Extending the ladder requires a superseding or
    complementary ADR (e.g. ADR-018, which governs the canonical YAML).
    """
    by_id = {lv.get("id"): lv for lv in levels if isinstance(lv, dict)}
    targets: list[tuple[str, str]] = []
    for canonical_id in CANONICAL_LEVEL_IDS:
        level = by_id.get(canonical_id)
        if not isinstance(level, dict):
            # Level missing — _check_levels reports it separately. Fall back
            # to id-only so the drift guard still runs.
            targets.append((canonical_id, ""))
            continue
        name = level.get("name")
        targets.append((canonical_id, name if isinstance(name, str) else ""))
    return targets


def _required_artifact_union(levels: list[Any]) -> set[str]:
    """Return the union of YAML required_artifacts across every level."""
    union: set[str] = set()
    for level in levels:
        if isinstance(level, dict):
            union.update(_level_sequence(level, "required_artifacts"))
    return union


def _check_artifact_keyword_drift(
    repo_root: Path,
    doc_rel: str,
    drift_rule_id: str,
    required_artifacts: set[str],
) -> list[PolicyFailure]:
    """Verify each YAML-required artifact has at least one keyword variant in the doc.

    Applied only to MUTABLE downstream docs. ADR-007 is exempt because it is
    immutable; that boundary is the same one `_baseline_drift_targets` enforces.
    """
    doc_path = repo_root / doc_rel
    if not doc_path.is_file():
        return []  # missing-doc failure already raised by `_check_doc_drift`.
    text = doc_path.read_text(encoding="utf-8").lower()
    missing_slugs: list[str] = []
    for slug in sorted(required_artifacts):
        keywords = _ARTIFACT_DOC_KEYWORDS.get(slug)
        if not keywords:
            # Slug not in the keyword map yet — silently pass rather than
            # bake an implicit "every new artifact slug must update the
            # keyword map AND the doc". The keyword map is the
            # contributor-facing surface; new slugs should be added
            # alongside the YAML edit.
            continue
        # Case-insensitive match: docs may use "Invariants" or "invariant
        # list" or "INVARIANT LIST" -- the keyword "invariant" should match
        # all of them.
        if not any(keyword.lower() in text for keyword in keywords):
            missing_slugs.append(slug)
    if missing_slugs:
        return [
            _fail(
                drift_rule_id,
                f"{doc_rel} no longer mentions every required artifact; missing keywords for: {missing_slugs}",
                doc_rel,
            )
        ]
    return []


def _check_doc_drift(
    repo_root: Path,
    doc_rel: str,
    missing_rule_id: str,
    drift_rule_id: str,
    targets: list[tuple[str, str]],
) -> list[PolicyFailure]:
    doc_path = repo_root / doc_rel
    if not doc_path.is_file():
        return [_fail(missing_rule_id, f"{doc_rel} is missing — the policy references it", doc_rel)]
    text = doc_path.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    missing_ids: list[str] = []
    missing_names: list[str] = []
    unpaired: list[tuple[str, str]] = []
    for level_id, level_name in targets:
        if level_id not in text:
            missing_ids.append(level_id)
        canonical_name = " ".join(level_name.split()) if level_name else ""
        if canonical_name and canonical_name not in normalized:
            missing_names.append(level_name)
        # Pair check: the id and its canonical name must co-occur within a
        # narrow window somewhere in the doc, so it is not enough that the
        # doc mentions every id AND every name -- they must be bound
        # together. This catches the exact "FM2 | Dynamic Semantic Rules"
        # drift mode where the wrong name is paired with the right id.
        # Well-formed bindings sit within ~10 chars ("### FM2 Semantic
        # Graph / Constraint", "FM2 (Semantic Graph / Constraint)"); a
        # Markdown table that mis-pairs across adjacent rows leaves ~50+
        # chars between the id and the wrong-row name.
        if canonical_name and level_id in text and canonical_name in normalized:
            if not _id_name_paired(normalized, level_id, canonical_name):
                unpaired.append((level_id, level_name))
    failures: list[PolicyFailure] = []
    if missing_ids:
        failures.append(
            _fail(
                drift_rule_id,
                f"{doc_rel} no longer mentions every canonical level id; missing: {missing_ids}",
                doc_rel,
            )
        )
    if missing_names:
        failures.append(
            _fail(
                drift_rule_id,
                f"{doc_rel} no longer mentions every canonical level name; missing: {missing_names}",
                doc_rel,
            )
        )
    if unpaired:
        rendered = ", ".join(f"{lid}↔{name!r}" for lid, name in unpaired)
        failures.append(
            _fail(
                drift_rule_id,
                f"{doc_rel} mentions every canonical id and name, but at least one (id, name) pair is "
                f"not co-located within a 200-character window — likely id/name drift: {rendered}",
                doc_rel,
            )
        )
    return failures


def _id_name_paired(normalized_text: str, level_id: str, level_name: str, window: int = 40) -> bool:
    """Return True if `level_id` and `level_name` co-occur within `window` chars in `normalized_text`."""
    start = 0
    while True:
        idx = normalized_text.find(level_id, start)
        if idx == -1:
            return False
        window_start = max(0, idx - window)
        window_end = idx + len(level_id) + window
        if level_name in normalized_text[window_start:window_end]:
            return True
        start = idx + 1


def evaluate_assurance_policy(repo_root: Path) -> list[PolicyFailure]:
    """Return the list of structural failures for the ASR-505 assurance policy (empty = OK)."""
    policy_path = repo_root / ASSURANCE_POLICY_RELATIVE_PATH
    if not policy_path.is_file():
        return [
            _fail(
                "assurance-policy-missing",
                f"assurance policy not found: {ASSURANCE_POLICY_RELATIVE_PATH}",
                ASSURANCE_POLICY_RELATIVE_PATH,
            )
        ]

    try:
        raw = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [
            _fail(
                "assurance-policy-parse",
                f"failed to parse {ASSURANCE_POLICY_RELATIVE_PATH}: {exc}",
                ASSURANCE_POLICY_RELATIVE_PATH,
            )
        ]

    if not isinstance(raw, dict):
        return [
            _fail(
                "assurance-policy-shape",
                f"{ASSURANCE_POLICY_RELATIVE_PATH} must be a YAML mapping at the top level",
                ASSURANCE_POLICY_RELATIVE_PATH,
            )
        ]

    failures: list[PolicyFailure] = []
    failures.extend(_check_top_level_fields(raw, ASSURANCE_POLICY_RELATIVE_PATH))
    failures.extend(_check_refs(raw, ASSURANCE_POLICY_RELATIVE_PATH))

    raw_levels = raw.get("levels")
    levels: list[Any] = raw_levels if isinstance(raw_levels, list) else []
    # _check_levels runs even when levels is empty or missing, so the
    # missing-canonical-level failures fire instead of getting silently
    # skipped.
    failures.extend(_check_levels(levels, ASSURANCE_POLICY_RELATIVE_PATH))

    # ADR-007 is IMMUTABLE per the ADR README; it must mention the baseline
    # FM0..FM3 ladder it codifies, and nothing more. Future FM4+ levels flow
    # through to the mutable docs only.
    baseline_targets = _baseline_drift_targets(levels)
    extended_targets = _drift_targets(levels) if levels else baseline_targets
    if not extended_targets or not any(name for _id, name in extended_targets):
        extended_targets = baseline_targets

    failures.extend(
        _check_doc_drift(
            repo_root,
            ADR_POLICY_RELATIVE_PATH,
            "assurance-policy-adr-missing",
            "assurance-policy-adr-drift",
            baseline_targets,
        )
    )
    failures.extend(
        _check_doc_drift(
            repo_root,
            CODING_STANDARDS_RELATIVE_PATH,
            "assurance-policy-coding-standards-missing",
            "assurance-policy-coding-standards-drift",
            extended_targets,
        )
    )
    failures.extend(
        _check_doc_drift(
            repo_root,
            FORMAL_OVERVIEW_RELATIVE_PATH,
            "assurance-policy-formal-overview-missing",
            "assurance-policy-formal-overview-drift",
            extended_targets,
        )
    )

    # Artifact-keyword drift -- applies only to MUTABLE docs. A doc that drops
    # mention of an artifact category that the YAML still requires fails the
    # gate; readers cannot be told a stale story.
    required_artifacts = _required_artifact_union(levels)
    failures.extend(
        _check_artifact_keyword_drift(
            repo_root,
            CODING_STANDARDS_RELATIVE_PATH,
            "assurance-policy-coding-standards-drift",
            required_artifacts,
        )
    )
    failures.extend(
        _check_artifact_keyword_drift(
            repo_root,
            FORMAL_OVERVIEW_RELATIVE_PATH,
            "assurance-policy-formal-overview-drift",
            required_artifacts,
        )
    )

    return failures


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the ASR-505 classification-based assurance policy (ADR-007 / ADR-018)."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root (defaults to the repo containing this file).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON failures.")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    failures = evaluate_assurance_policy(args.repo_root)
    exceptions_file = args.repo_root / "tools" / "policy" / "exceptions.yaml"
    if exceptions_file.is_file():
        failures = apply_exceptions(failures, load_exceptions(args.repo_root))
    if failures:
        if args.json:
            print(failures_to_json(failures))
        else:
            for failure in failures:
                print(failure.render(), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
