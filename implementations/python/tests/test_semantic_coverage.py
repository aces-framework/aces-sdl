from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from tools.check_semantic_coverage import (
    ADR_RELATIVE_PATH,
    CANONICAL_PHASES,
    COVERAGE_NOTE_RELATIVE_PATH,
    VALID_STATUSES,
    CoverageParseError,
    evaluate_semantic_coverage,
    main,
    parse_coverage_rows,
)

# A stub ADR-016 that references the coverage note by its repo-relative path, so
# the ADR↔note linkage check passes in the seeded temp repo.
_GOOD_ADR = """# ADR-016: Semantic Layer Scope and Coverage Model

## Status
accepted

## Decision
The live coverage table lives in `docs/explain/reference/shared-semantic-integrity.md`,
which this ADR governs.
"""

# A minimal but well-formed coverage note: prose, then a Coverage Model section
# with a table whose paths exist under the (temp) repo root.
_GOOD_NOTE = """# Shared Semantic Integrity

Guardrails note for SEM-200. The scope and coverage model are governed by
ADR-016 (../../decisions/adrs/adr-016-semantic-layer-scope-and-coverage-model.md).

## Coverage Model

Lifecycle phases (canonical, fixed): authoring, validation, instantiation,
compilation, planning, execution, observation.

| Construct family | Owning requirement(s) | Phases covered | Realizing artifacts | Status |
| --- | --- | --- | --- | --- |
| Objective windows | SEM-202 | validation, compilation, planning | `specs/formal/objectives/README.md`, `implementations/python/tests/test_semantics_objectives.py` | active |
| Assessment semantics | SEM-206, DSL-110 | — | — | planned |

## Non-Goals
Nothing else here.
"""

_ACTIVE_ROW = (
    "| Objective windows | SEM-202 | validation, compilation, planning | "
    "`specs/formal/objectives/README.md`, `implementations/python/tests/test_semantics_objectives.py` | active |"
)
_ARTIFACTS = "`specs/formal/objectives/README.md`, `implementations/python/tests/test_semantics_objectives.py`"
_PLANNED_ROW = "| Assessment semantics | SEM-206, DSL-110 | — | — | planned |"

_ARTIFACTS_IN_GOOD_NOTE = (
    "specs/formal/objectives/README.md",
    "implementations/python/tests/test_semantics_objectives.py",
)


def _seed_repo(tmp_path: Path, note_body: str = _GOOD_NOTE, adr_body: str | None = _GOOD_ADR) -> Path:
    """Create a temp repo skeleton: the coverage note, its governing ADR, and the artifacts named in the note."""
    note_path = tmp_path / COVERAGE_NOTE_RELATIVE_PATH
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(note_body, encoding="utf-8")
    if adr_body is not None:
        adr_path = tmp_path / ADR_RELATIVE_PATH
        adr_path.parent.mkdir(parents=True, exist_ok=True)
        adr_path.write_text(adr_body, encoding="utf-8")
    for rel in _ARTIFACTS_IN_GOOD_NOTE:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("placeholder\n", encoding="utf-8")
    return tmp_path


def _flagged(failures, marker: str) -> bool:
    """True if some failure matches ``marker`` by rule id or by a substring of its rendered text."""
    needle = marker.lower()
    return any(f.rule_id == marker or needle in f.render().lower() for f in failures)


# (case id, mutated coverage note, marker the checker must flag)
_NOTE_DEFECT_CASES = [
    ("section-missing", _GOOD_NOTE.replace("## Coverage Model", "## Something Else"), "coverage model"),
    ("status-unknown", _GOOD_NOTE.replace("| active |", "| done |"), "done"),
    ("status-unknown-rule", _GOOD_NOTE.replace("| active |", "| done |"), "coverage-status"),
    ("phase-unknown", _GOOD_NOTE.replace("validation, compilation, planning", "validation, deployment"), "deployment"),
    (
        "phase-unknown-rule",
        _GOOD_NOTE.replace("validation, compilation, planning", "validation, deployment"),
        "coverage-phase",
    ),
    ("owner-bad-uid", _GOOD_NOTE.replace("| SEM-202 |", "| sem-202 |"), "sem-202"),
    (
        "artifact-missing",
        _GOOD_NOTE.replace("`specs/formal/objectives/README.md`", "`specs/formal/objectives/nope.md`"),
        "nope.md",
    ),
    (
        "artifact-missing-rule",
        _GOOD_NOTE.replace("`specs/formal/objectives/README.md`", "`specs/formal/objectives/nope.md`"),
        "coverage-artifact-missing",
    ),
    (
        "artifact-unsupported",
        _GOOD_NOTE.replace("`specs/formal/objectives/README.md`", "`pyproject.toml`"),
        "coverage-artifact-unsupported",
    ),
    (
        "artifact-escapes-root",
        _GOOD_NOTE.replace("`specs/formal/objectives/README.md`", "`specs/../../escape.md`"),
        "coverage-artifact-escape",
    ),
    (
        "active-no-artifacts",
        _GOOD_NOTE.replace(_ACTIVE_ROW, "| Objective windows | SEM-202 | validation | — | active |"),
        "coverage-incomplete",
    ),
    (
        "active-only-prose-artifact",
        _GOOD_NOTE.replace(_ARTIFACTS, "objective window semantics live in the validator"),
        "coverage-incomplete",
    ),
    (
        "active-no-test-artifact",
        _GOOD_NOTE.replace(_ARTIFACTS, "`specs/formal/objectives/README.md`"),
        "coverage-untested",
    ),
    (
        "active-only-test-artifact",
        _GOOD_NOTE.replace(_ARTIFACTS, "`implementations/python/tests/test_semantics_objectives.py`"),
        "coverage-incomplete",
    ),
    (
        "planned-has-artifacts",
        _GOOD_NOTE.replace(
            _PLANNED_ROW,
            "| Assessment semantics | SEM-206 | validation | `specs/formal/objectives/README.md` | planned |",
        ),
        "coverage-planned",
    ),
    (
        "planned-has-phases",
        _GOOD_NOTE.replace(_PLANNED_ROW, "| Assessment semantics | SEM-206 | validation | — | planned |"),
        "coverage-planned",
    ),
]


@pytest.mark.parametrize(
    ("note_body", "marker"), [(n, m) for _, n, m in _NOTE_DEFECT_CASES], ids=[c for c, _, _ in _NOTE_DEFECT_CASES]
)
def test_note_defect_is_flagged(tmp_path: Path, note_body: str, marker: str) -> None:
    failures = evaluate_semantic_coverage(_seed_repo(tmp_path, note_body))
    assert _flagged(failures, marker)


# (case id, ADR-016 body — or None to omit the file entirely, expected rule id)
_ADR_LINKAGE_CASES = [
    ("adr-absent", None, "coverage-adr-missing"),
    ("adr-no-reference", "# ADR-016: Something\n\n## Status\naccepted\n", "coverage-adr-unlinked"),
    (
        "adr-basename-only",
        "# ADR-016: X\n\n## Status\naccepted\n\nSee shared-semantic-integrity.md.\n",
        "coverage-adr-unlinked",
    ),
]


@pytest.mark.parametrize(
    ("adr_body", "rule_id"), [(b, r) for _, b, r in _ADR_LINKAGE_CASES], ids=[c for c, _, _ in _ADR_LINKAGE_CASES]
)
def test_adr_linkage_defect_is_flagged(tmp_path: Path, adr_body: str | None, rule_id: str) -> None:
    failures = evaluate_semantic_coverage(_seed_repo(tmp_path, adr_body=adr_body))
    assert any(f.rule_id == rule_id for f in failures)


def test_well_formed_note_passes(tmp_path: Path) -> None:
    assert evaluate_semantic_coverage(_seed_repo(tmp_path)) == []


def test_missing_note_fails(tmp_path: Path) -> None:
    failures = evaluate_semantic_coverage(tmp_path)
    assert any(f.rule_id == "coverage-note-missing" for f in failures)


def test_malformed_row_column_count_fails(tmp_path: Path) -> None:
    repo = _seed_repo(
        tmp_path, _GOOD_NOTE.replace(_PLANNED_ROW, "| Assessment semantics | SEM-206, DSL-110 | — | planned |")
    )
    failures = evaluate_semantic_coverage(repo)
    assert any(f.rule_id == "coverage-model-parse" for f in failures)


def test_no_table_raises_parse_error() -> None:
    with pytest.raises(CoverageParseError):
        parse_coverage_rows("# Note\n\n## Coverage Model\n\nNo table here.\n\n## Next\nDone.\n")


def test_missing_section_raises_parse_error() -> None:
    with pytest.raises(CoverageParseError):
        parse_coverage_rows("# Note\n\nNothing relevant.\n")


def test_parse_rows_returns_expected_count() -> None:
    rows = parse_coverage_rows(_GOOD_NOTE)
    assert len(rows) == 2
    assert rows[0].family == "Objective windows"
    assert rows[0].owners == ["SEM-202"]
    assert rows[0].phases == ["validation", "compilation", "planning"]
    assert rows[0].status == "active"
    assert rows[1].owners == ["SEM-206", "DSL-110"]
    assert rows[1].phases == []
    assert rows[1].status == "planned"


def test_row_line_number_accounts_for_prose_before_table() -> None:
    body = (
        "# Reference Note\n"  # line 1
        "\n"  # line 2
        "Intro paragraph.\n"  # line 3
        "\n"  # line 4
        "## Coverage Model\n"  # line 5
        "\n"  # line 6
        "Lifecycle phases: authoring, validation.\n"  # line 7
        "Some more prose before the table.\n"  # line 8
        "\n"  # line 9
        "| Construct family | Owning requirement(s) | Phases covered | Realizing artifacts | Status |\n"  # line 10
        "| --- | --- | --- | --- | --- |\n"  # line 11
        "| Objective windows | SEM-202 | validation | `specs/x.md` | active |\n"  # line 12
        "| Future thing | SEM-999 | — | — | planned |\n"  # line 13
        "\n"
        "## Next Section\nDone.\n"
    )
    rows = parse_coverage_rows(body)
    assert [row.line_no for row in rows] == [12, 13]


def test_cli_returns_nonzero_on_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--repo-root", str(tmp_path)]) == 1
    assert capsys.readouterr().err.strip()


def test_cli_returns_zero_when_clean(tmp_path: Path) -> None:
    assert main(["--repo-root", str(_seed_repo(tmp_path))]) == 0


def test_repo_coverage_note_is_well_formed() -> None:
    """The real SEM-200 coverage note must pass the structural coverage gate."""
    assert evaluate_semantic_coverage(REPO_ROOT) == []


def test_constants_are_sane() -> None:
    assert "validation" in CANONICAL_PHASES
    assert set(VALID_STATUSES) == {"active", "partial", "planned"}
    assert COVERAGE_NOTE_RELATIVE_PATH.endswith("shared-semantic-integrity.md")
    assert ADR_RELATIVE_PATH.endswith("adr-016-semantic-layer-scope-and-coverage-model.md")
