#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Structural gate for the SEM-200 semantic-layer coverage model.

ADR-016 ("Semantic Layer Scope and Coverage Model") fixes the *model* — the
seven canonical lifecycle phases, the construct-family concept, the status
vocabulary, and SEM-200's definition of done — and is immutable once accepted.
The *live* coverage table itself is a mutable reference note,
``docs/explain/reference/shared-semantic-integrity.md``, which ADR-016 governs:
every ``SEM-2xx`` implementation PR moves its construct family's row toward
``active`` there, not in the ADR.

A coverage table that nothing checks rots within weeks. This checker enforces
exactly what it can prove from the filesystem (it never calls Ground Control, so
it cannot become flaky in CI); the *correctness* of a row's status against the
owning requirement's Ground Control state is a governance fact, not enforced
here. What is enforced:

* every row has the expected five columns, a recognised status, requirement-UID-
  shaped owners, and canonical lifecycle-phase tokens;
* every artifact-cell token that looks like a path (it contains ``/`` or ends in
  a source-file extension) resolves under the repository root, lies under a
  supported root, and exists on disk — an unsupported, escaping, or missing path
  is a failure, not silently treated as prose;
* an ``active`` row names at least one lifecycle phase, at least one existing
  *non-test* realizing artifact, and at least one existing
  ``implementations/python/tests/test_*.py`` test;
* a ``partial`` row names at least one lifecycle phase and at least one existing
  *non-test* realizing artifact;
* a ``planned`` row names no phases and no artifacts (if it has artifacts it is
  at least ``partial``);
* ADR-016 still exists and still references the coverage note by its repo-relative
  (or ADR-relative) path, so the ADR↔note linkage cannot silently rot.

Failures use ``tools.policy.common.PolicyFailure`` and the CLI honours ``--json``
and the shared ``tools/policy/exceptions.yaml`` waiver mechanism, like the other
``policy`` nox-stage entry points (``check_repo_policy.py``, ``check_requirement_governance.py``).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.policy.common import PolicyFailure, apply_exceptions, failures_to_json, load_exceptions

# The reference note that holds the live coverage table (mutable, ADR-governed).
COVERAGE_NOTE_RELATIVE_PATH = "docs/explain/reference/shared-semantic-integrity.md"
# The ADR that fixes the coverage model and governs the note (immutable).
ADR_RELATIVE_PATH = "docs/decisions/adrs/adr-016-semantic-layer-scope-and-coverage-model.md"

# The canonical lifecycle phases SEM-200 spans, in order. Kept in lockstep with
# ADR-016 and the coverage note.
CANONICAL_PHASES: tuple[str, ...] = (
    "authoring",
    "validation",
    "instantiation",
    "compilation",
    "planning",
    "execution",
    "observation",
)

# Coverage statuses. ``active`` = owning requirement ACTIVE in Ground Control,
# semantics realized in a shared helper/spec, named tests cover it (the GC state
# is reviewed, not gated here); ``partial`` = some realization exists but
# coverage or the owning requirement is incomplete; ``planned`` = no realization
# yet (owned by a DRAFT requirement, future work).
VALID_STATUSES: tuple[str, ...] = ("active", "partial", "planned")

# Repo-relative roots / exact files under which a path-like artifact token is
# allowed to live. A path-like token outside these is a failure, not prose.
_ARTIFACT_PATH_PREFIXES: tuple[str, ...] = (
    "specs/",
    "implementations/",
    "contracts/",
    "docs/",
    "tools/",
    "examples/",
)
_ARTIFACT_PATH_EXACT: frozenset[str] = frozenset({"noxfile.py", "Makefile", "Dockerfile"})
# Source-file extensions that, on a token with no spaces, mark it as path-like.
_PATHISH_SUFFIXES: tuple[str, ...] = (
    ".py",
    ".md",
    ".rst",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".rego",
    ".sh",
    ".sql",
)
_TEST_PATH_PREFIX = "implementations/python/tests/test_"

_EMPTY_CELL_TOKENS: frozenset[str] = frozenset({"", "-", "—", "–", "n/a", "none", "tbd"})

_REQUIREMENT_UID_RE = re.compile(r"^[A-Z]{2,4}-\d{3}$")
_HEADING_RE = re.compile(r"^#{1,6}\s")
_COVERAGE_HEADING_RE = re.compile(r"^#{2,4}\s+Coverage Model\s*$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-{2,}:?$")
_BACKTICK_SPAN_RE = re.compile(r"`([^`]+)`")

_EXPECTED_COLUMNS = 5


class CoverageParseError(ValueError):
    """The coverage note's Coverage Model section or table is missing or malformed."""


@dataclass(frozen=True)
class CoverageRow:
    family: str
    owners: list[str]
    phases: list[str]
    artifacts: list[str]
    status: str
    line_no: int


def _fail(rule_id: str, message: str, path: str | None) -> PolicyFailure:
    return PolicyFailure(rule_id, message, path)


def _cells(line: str) -> list[str]:
    """Split a Markdown table row into trimmed cells, dropping the edge empties."""
    parts = [part.strip() for part in line.strip().split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _is_empty_cell(cell: str) -> bool:
    return cell.strip().lower() in _EMPTY_CELL_TOKENS


def _split_simple_tokens(cell: str) -> list[str]:
    if _is_empty_cell(cell):
        return []
    return [token.strip() for token in cell.split(",") if token.strip()]


def _split_phase_tokens(cell: str) -> list[str]:
    return [token.lower() for token in _split_simple_tokens(cell)]


def _extract_artifact_tokens(cell: str) -> list[str]:
    if _is_empty_cell(cell):
        return []
    spans = _BACKTICK_SPAN_RE.findall(cell)
    tokens = spans if spans else cell.split(",")
    return [token.strip() for token in tokens if token.strip() and not _is_empty_cell(token)]


def _looks_path_like(token: str) -> bool:
    if token in _ARTIFACT_PATH_EXACT:
        return True
    if " " in token:
        return False
    return "/" in token or token.endswith(_PATHISH_SUFFIXES)


def _is_supported_repo_path(token: str) -> bool:
    return token in _ARTIFACT_PATH_EXACT or token.startswith(_ARTIFACT_PATH_PREFIXES)


def _is_test_path(token: str) -> bool:
    return token.startswith(_TEST_PATH_PREFIX) and token.endswith(".py")


def _resolve_within(repo_root: Path, rel: str) -> Path | None:
    """Resolve ``rel`` under ``repo_root``; return None if it escapes the root."""
    root = repo_root.resolve()
    candidate = (root / rel).resolve()
    if candidate == root or root in candidate.parents:
        return candidate
    return None


def parse_coverage_rows(note_text: str) -> list[CoverageRow]:
    """Parse the Coverage Model table out of the coverage note's text.

    Raises:
        CoverageParseError: if the section heading is absent, no table follows
            it, the header/separator are malformed, or a data row has the wrong
            number of cells.
    """
    lines = note_text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if _COVERAGE_HEADING_RE.match(line.strip()):
            start = index + 1
            break
    if start is None:
        raise CoverageParseError("coverage note is missing the '## Coverage Model' section")

    table_lines: list[tuple[int, str]] = []
    in_table = False
    for offset, line in enumerate(lines[start:], start=start):
        if _HEADING_RE.match(line):
            break
        if line.lstrip().startswith("|"):
            in_table = True
            table_lines.append((offset, line))
        elif in_table:
            break
    if len(table_lines) < 3:
        raise CoverageParseError(
            "coverage note's Coverage Model section has no table (need header, separator, >=1 row)"
        )

    header = _cells(table_lines[0][1])
    if len(header) != _EXPECTED_COLUMNS:
        raise CoverageParseError(
            f"Coverage Model table header must have {_EXPECTED_COLUMNS} columns, found {len(header)}: {header}"
        )
    separator = _cells(table_lines[1][1])
    if len(separator) != _EXPECTED_COLUMNS or not all(_SEPARATOR_CELL_RE.match(cell) for cell in separator):
        raise CoverageParseError(f"Coverage Model table separator row is malformed: {separator}")

    rows: list[CoverageRow] = []
    for source_index, raw in table_lines[2:]:
        cells = _cells(raw)
        if len(cells) != _EXPECTED_COLUMNS:
            raise CoverageParseError(
                f"Coverage Model row at line {source_index + 1} has {len(cells)} cells, "
                f"expected {_EXPECTED_COLUMNS}: {raw.strip()}"
            )
        rows.append(
            CoverageRow(
                family=cells[0],
                owners=_split_simple_tokens(cells[1]),
                phases=_split_phase_tokens(cells[2]),
                artifacts=_extract_artifact_tokens(cells[3]),
                status=cells[4].strip().lower(),
                line_no=source_index + 1,
            )
        )
    return rows


def _supported_roots_phrase() -> str:
    return ", ".join((*_ARTIFACT_PATH_PREFIXES, *sorted(_ARTIFACT_PATH_EXACT)))


def _check_artifacts(repo_root: Path, row: CoverageRow, where: str, note: str) -> tuple[list[PolicyFailure], int, int]:
    """Validate the artifact cell; return (failures, existing non-test count, existing test count)."""
    failures: list[PolicyFailure] = []
    realization_paths = 0
    test_paths = 0
    for token in row.artifacts:
        if not _looks_path_like(token):
            continue  # descriptive prose, not a checkable artifact
        if not _is_supported_repo_path(token):
            failures.append(
                _fail(
                    "coverage-artifact-unsupported",
                    f"{where}: artifact '{token}' looks like a path but is not under a supported root ({_supported_roots_phrase()})",
                    note,
                )
            )
            continue
        resolved = _resolve_within(repo_root, token)
        if resolved is None:
            failures.append(
                _fail("coverage-artifact-escape", f"{where}: artifact path escapes the repo root: {token}", note)
            )
            continue
        if not resolved.exists():
            failures.append(_fail("coverage-artifact-missing", f"{where}: artifact path does not exist: {token}", note))
            continue
        if _is_test_path(token):
            test_paths += 1
        else:
            realization_paths += 1
    return failures, realization_paths, test_paths


def _check_row(repo_root: Path, row: CoverageRow) -> list[PolicyFailure]:
    failures: list[PolicyFailure] = []
    note = COVERAGE_NOTE_RELATIVE_PATH
    where = f"row '{row.family}' (line {row.line_no})"

    if not row.family:
        failures.append(_fail("coverage-family", f"line {row.line_no}: construct family cell is empty", note))

    if not row.owners:
        failures.append(_fail("coverage-owner", f"{where}: no owning requirement UID", note))
    for owner in row.owners:
        if not _REQUIREMENT_UID_RE.match(owner):
            failures.append(_fail("coverage-owner", f"{where}: invalid requirement UID '{owner}'", note))

    for phase in row.phases:
        if phase not in CANONICAL_PHASES:
            failures.append(
                _fail(
                    "coverage-phase",
                    f"{where}: unknown lifecycle phase '{phase}' (expected one of {', '.join(CANONICAL_PHASES)})",
                    note,
                )
            )

    artifact_failures, realization_paths, test_paths = _check_artifacts(repo_root, row, where, note)
    failures.extend(artifact_failures)

    if row.status not in VALID_STATUSES:
        failures.append(
            _fail(
                "coverage-status",
                f"{where}: unknown status '{row.status}' (expected one of {', '.join(VALID_STATUSES)})",
                note,
            )
        )
        return failures

    if row.status in ("active", "partial"):
        if not row.phases:
            failures.append(
                _fail(
                    "coverage-incomplete", f"{where}: status '{row.status}' requires at least one lifecycle phase", note
                )
            )
        if realization_paths == 0:
            failures.append(
                _fail(
                    "coverage-incomplete",
                    f"{where}: status '{row.status}' requires at least one existing non-test realizing artifact (spec/helper/code)",
                    note,
                )
            )
        if row.status == "active" and test_paths == 0:
            failures.append(
                _fail(
                    "coverage-untested",
                    f"{where}: status 'active' requires at least one existing test under {_TEST_PATH_PREFIX}*.py",
                    note,
                )
            )
    elif row.status == "planned":
        if row.phases:
            failures.append(
                _fail("coverage-planned", f"{where}: status 'planned' must not list lifecycle phases", note)
            )
        if row.artifacts:
            failures.append(
                _fail("coverage-planned", f"{where}: status 'planned' must not list realizing artifacts", note)
            )
    return failures


def _check_adr_links_note(repo_root: Path) -> list[PolicyFailure]:
    adr_path = repo_root / ADR_RELATIVE_PATH
    if not adr_path.is_file():
        return [
            _fail(
                "coverage-adr-missing",
                f"ADR-016 not found at {ADR_RELATIVE_PATH}; the coverage note must be governed by an ADR",
                ADR_RELATIVE_PATH,
            )
        ]
    adr_text = adr_path.read_text(encoding="utf-8")
    rel_from_adr = os.path.relpath(COVERAGE_NOTE_RELATIVE_PATH, str(Path(ADR_RELATIVE_PATH).parent))
    if COVERAGE_NOTE_RELATIVE_PATH not in adr_text and rel_from_adr not in adr_text:
        return [
            _fail(
                "coverage-adr-unlinked",
                f"{ADR_RELATIVE_PATH} no longer references the coverage note "
                f"by path ({COVERAGE_NOTE_RELATIVE_PATH} or {rel_from_adr})",
                ADR_RELATIVE_PATH,
            )
        ]
    return []


def evaluate_semantic_coverage(repo_root: Path, note_relative_path: str | None = None) -> list[PolicyFailure]:
    """Return the list of structural failures for the SEM-200 coverage model (empty = OK)."""
    rel = note_relative_path or COVERAGE_NOTE_RELATIVE_PATH
    note_path = repo_root / rel
    if not note_path.is_file():
        return [_fail("coverage-note-missing", f"coverage note not found: {rel}", rel)]

    failures: list[PolicyFailure] = list(_check_adr_links_note(repo_root))

    try:
        rows = parse_coverage_rows(note_path.read_text(encoding="utf-8"))
    except CoverageParseError as exc:
        failures.append(_fail("coverage-model-parse", str(exc), rel))
        return failures

    if not rows:
        failures.append(_fail("coverage-model-empty", "Coverage Model table has no rows", rel))
        return failures

    for row in rows:
        failures.extend(_check_row(repo_root, row))
    return failures


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the SEM-200 semantic-layer coverage model (ADR-016).")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root (defaults to the repo containing this file).",
    )
    parser.add_argument(
        "--note-path",
        default=None,
        help="Repo-relative path to the coverage note (defaults to the canonical location).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON failures.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    failures = evaluate_semantic_coverage(args.repo_root, args.note_path)
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
