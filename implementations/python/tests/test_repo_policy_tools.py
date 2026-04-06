from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.policy.repo_policy import evaluate_repo_policy


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def setup_policy_repo(tmp_path: Path) -> Path:
    policy_dir = tmp_path / "tools" / "policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "tools" / "policy" / "adr_policy.yaml", policy_dir / "adr_policy.yaml")

    adr_dir = tmp_path / "docs" / "decisions" / "adrs"
    adr_dir.mkdir(parents=True, exist_ok=True)
    write_text(
        adr_dir / "adr-001-example.md",
        "# ADR-001: Example ADR\n\n## Status\nAccepted\n\n## Date\n2026-04-05\n",
    )
    write_text(
        adr_dir / "README.md",
        "| Number | Title | Status | Date |\n"
        "| --- | --- | --- | --- |\n"
        "| [001](adr-001-example.md) | Example ADR | Accepted | 2026-04-05 |\n",
    )
    return tmp_path


def test_generated_schema_direct_edits_require_driver_changes(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    write_text(repo_root / "contracts" / "schemas" / "backend-manifest" / "schema.json", "{}\n")

    failures = evaluate_repo_policy(
        repo_root,
        ["contracts/schemas/backend-manifest/schema.json"],
    )

    assert [failure.rule_id for failure in failures] == ["generated-schema-direct-edit"]


def test_generated_schema_edits_pass_when_driver_changes_are_present(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    write_text(repo_root / "contracts" / "schemas" / "backend-manifest" / "schema.json", "{}\n")
    write_text(repo_root / "tools" / "generate_contract_schemas.py", "print('regen')\n")

    failures = evaluate_repo_policy(
        repo_root,
        [
            "contracts/schemas/backend-manifest/schema.json",
            "tools/generate_contract_schemas.py",
        ],
    )

    assert "generated-schema-direct-edit" not in {failure.rule_id for failure in failures}


def test_package_import_direction_blocks_aces_compatibility_imports(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    write_text(
        repo_root / "implementations" / "python" / "packages" / "aces_processor" / "planner.py",
        "from aces.runtime import legacy\n",
    )

    failures = evaluate_repo_policy(
        repo_root,
        ["implementations/python/packages/aces_processor/planner.py"],
        check_set="file-local",
    )

    assert [failure.rule_id for failure in failures] == ["compatibility-import-direction"]


def test_compatibility_layer_rejects_non_wrapper_logic(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    write_text(
        repo_root / "implementations" / "python" / "src" / "aces" / "runtime.py",
        "def build_runtime():\n    return 1\n",
    )

    failures = evaluate_repo_policy(
        repo_root,
        ["implementations/python/src/aces/runtime.py"],
        check_set="file-local",
    )

    assert [failure.rule_id for failure in failures] == ["compatibility-wrapper-only"]


def test_changelog_is_required_for_source_changes(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    write_text(
        repo_root / "implementations" / "python" / "packages" / "aces_processor" / "runtime.py",
        "VALUE = 1\n",
    )

    failures = evaluate_repo_policy(
        repo_root,
        ["implementations/python/packages/aces_processor/runtime.py"],
    )

    assert [failure.rule_id for failure in failures] == ["changelog-required"]


def test_concept_authority_tokens_are_reserved_to_allowed_surfaces(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    write_text(
        repo_root / "docs" / "drafts" / "concept-authority-notes.md",
        "# stray\n",
    )

    failures = evaluate_repo_policy(
        repo_root,
        ["docs/drafts/concept-authority-notes.md"],
        check_set="file-local",
    )

    assert [failure.rule_id for failure in failures] == ["concept-authority-reserved-path"]


def test_adr_readme_must_match_adr_documents(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    write_text(
        repo_root / "docs" / "decisions" / "adrs" / "README.md",
        "| Number | Title | Status | Date |\n"
        "| --- | --- | --- | --- |\n"
        "| [001](adr-001-example.md) | Wrong Title | Accepted | 2026-04-05 |\n",
    )

    failures = evaluate_repo_policy(
        repo_root,
        ["docs/decisions/adrs/adr-001-example.md"],
    )

    assert [failure.rule_id for failure in failures] == ["adr-index-sync"]
