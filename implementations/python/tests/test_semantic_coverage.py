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

# A stub ADR-016 that references the coverage note by basename, so the
# ADR↔note linkage check passes in the seeded temp repo.
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


def test_well_formed_note_passes(tmp_path: Path) -> None:
    assert evaluate_semantic_coverage(_seed_repo(tmp_path)) == []


def test_missing_note_fails(tmp_path: Path) -> None:
    failures = evaluate_semantic_coverage(tmp_path)
    assert any(f.rule_id == "coverage-note-missing" for f in failures)


def test_missing_governing_adr_fails(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, adr_body=None)
    failures = evaluate_semantic_coverage(repo)
    assert any(f.rule_id == "coverage-adr-missing" for f in failures)
    assert any("adr-016" in f.render().lower() for f in failures)


def test_adr_not_referencing_note_fails(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, adr_body="# ADR-016: Something\n\n## Status\naccepted\n")
    failures = evaluate_semantic_coverage(repo)
    assert any(f.rule_id == "coverage-adr-unlinked" for f in failures)


def test_adr_basename_only_reference_fails(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, adr_body="# ADR-016: X\n\n## Status\naccepted\n\nSee shared-semantic-integrity.md.\n")
    failures = evaluate_semantic_coverage(repo)
    assert any(f.rule_id == "coverage-adr-unlinked" for f in failures)


def test_missing_coverage_section_fails(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, _GOOD_NOTE.replace("## Coverage Model", "## Something Else"))
    failures = evaluate_semantic_coverage(repo)
    assert any("coverage model" in f.render().lower() for f in failures)


def test_unknown_status_fails(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, _GOOD_NOTE.replace("| active |", "| done |"))
    failures = evaluate_semantic_coverage(repo)
    assert any("status" in f.render().lower() and "done" in f.render().lower() for f in failures)


def test_unknown_phase_fails(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, _GOOD_NOTE.replace("validation, compilation, planning", "validation, deployment"))
    failures = evaluate_semantic_coverage(repo)
    assert any("phase" in f.render().lower() and "deployment" in f.render().lower() for f in failures)


def test_dangling_artifact_path_fails(tmp_path: Path) -> None:
    repo = _seed_repo(
        tmp_path,
        _GOOD_NOTE.replace("`specs/formal/objectives/README.md`", "`specs/formal/objectives/does-not-exist.md`"),
    )
    failures = evaluate_semantic_coverage(repo)
    assert any("does-not-exist" in f.render() for f in failures)


def test_active_row_without_artifacts_fails(tmp_path: Path) -> None:
    repo = _seed_repo(
        tmp_path,
        _GOOD_NOTE.replace(
            "| Objective windows | SEM-202 | validation, compilation, planning | "
            "`specs/formal/objectives/README.md`, `implementations/python/tests/test_semantics_objectives.py` | active |",
            "| Objective windows | SEM-202 | validation | — | active |",
        ),
    )
    failures = evaluate_semantic_coverage(repo)
    assert any(f.rule_id == "coverage-incomplete" for f in failures)


def test_active_row_with_only_prose_artifact_fails(tmp_path: Path) -> None:
    repo = _seed_repo(
        tmp_path,
        _GOOD_NOTE.replace(
            "`specs/formal/objectives/README.md`, `implementations/python/tests/test_semantics_objectives.py`",
            "objective window semantics live in the validator",
        ),
    )
    failures = evaluate_semantic_coverage(repo)
    assert any(f.rule_id == "coverage-incomplete" for f in failures)


def test_active_row_without_test_artifact_fails(tmp_path: Path) -> None:
    repo = _seed_repo(
        tmp_path,
        _GOOD_NOTE.replace(
            "`specs/formal/objectives/README.md`, `implementations/python/tests/test_semantics_objectives.py`",
            "`specs/formal/objectives/README.md`",
        ),
    )
    failures = evaluate_semantic_coverage(repo)
    assert any(f.rule_id == "coverage-untested" for f in failures)


def test_active_row_with_only_test_artifacts_fails(tmp_path: Path) -> None:
    repo = _seed_repo(
        tmp_path,
        _GOOD_NOTE.replace(
            "`specs/formal/objectives/README.md`, `implementations/python/tests/test_semantics_objectives.py`",
            "`implementations/python/tests/test_semantics_objectives.py`",
        ),
    )
    failures = evaluate_semantic_coverage(repo)
    assert any(f.rule_id == "coverage-incomplete" for f in failures)


def test_unsupported_path_artifact_fails(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, _GOOD_NOTE.replace("`specs/formal/objectives/README.md`", "`pyproject.toml`"))
    failures = evaluate_semantic_coverage(repo)
    assert any(f.rule_id == "coverage-artifact-unsupported" for f in failures)


def test_planned_row_with_artifacts_fails(tmp_path: Path) -> None:
    repo = _seed_repo(
        tmp_path,
        _GOOD_NOTE.replace(
            "| Assessment semantics | SEM-206, DSL-110 | — | — | planned |",
            "| Assessment semantics | SEM-206, DSL-110 | validation | "
            "`implementations/python/tests/test_semantics_objectives.py` | planned |",
        ),
    )
    failures = evaluate_semantic_coverage(repo)
    assert any(f.rule_id == "coverage-planned" for f in failures)


def test_bad_requirement_uid_fails(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, _GOOD_NOTE.replace("| SEM-202 |", "| sem-202 |"))
    failures = evaluate_semantic_coverage(repo)
    assert any("sem-202" in f.render().lower() for f in failures)


def test_malformed_row_column_count_fails(tmp_path: Path) -> None:
    repo = _seed_repo(
        tmp_path,
        _GOOD_NOTE.replace(
            "| Assessment semantics | SEM-206, DSL-110 | — | — | planned |",
            "| Assessment semantics | SEM-206, DSL-110 | — | planned |",
        ),
    )
    failures = evaluate_semantic_coverage(repo)
    assert failures


def test_no_table_raises_parse_error() -> None:
    body = "# Note\n\n## Coverage Model\n\nNo table here.\n\n## Next\nDone.\n"
    with pytest.raises(CoverageParseError):
        parse_coverage_rows(body)


def test_missing_section_raises_parse_error() -> None:
    with pytest.raises(CoverageParseError):
        parse_coverage_rows("# Note\n\nNothing relevant.\n")


def test_parse_rows_returns_expected_count() -> None:
    rows = parse_coverage_rows(_GOOD_NOTE)
    assert len(rows) == 2
    assert rows[0].family == "Objective windows"
    assert rows[0].owners == ["SEM-202"]
    assert rows[0].status == "active"
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
