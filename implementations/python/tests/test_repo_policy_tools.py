from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.check_json_artifacts import collect_validation_targets, should_run_full_validation
from tools.policy.common import PolicyFailure
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


def structural_runner_stub(_: dict) -> list[PolicyFailure]:
    return []


def test_structural_policy_runner_receives_policy_input(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    captured: dict = {}

    def runner(input_document: dict) -> list[PolicyFailure]:
        captured.update(input_document)
        return [PolicyFailure("structural-check", "blocked", "contracts/schemas/backend-manifest/schema.json")]

    failures = evaluate_repo_policy(
        repo_root,
        ["contracts/schemas/backend-manifest/schema.json"],
        structural_runner=runner,
    )

    assert captured["changed"] == ["contracts/schemas/backend-manifest/schema.json"]
    assert captured["check_set"] == "full"
    assert "generated_contracts" in captured["policy"]
    assert [failure.rule_id for failure in failures] == ["structural-check"]


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
        structural_runner=structural_runner_stub,
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
        structural_runner=structural_runner_stub,
    )

    assert [failure.rule_id for failure in failures] == ["compatibility-wrapper-only"]


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
        structural_runner=structural_runner_stub,
    )

    assert [failure.rule_id for failure in failures] == ["adr-index-sync"]


def test_adr_index_accepts_legacy_inline_status_and_date_fields(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    write_text(
        repo_root / "docs" / "decisions" / "adrs" / "adr-001-example.md",
        "# ADR-001: Example ADR\n\n**Status:** Accepted\n**Date:** 2026-04-05\n",
    )

    failures = evaluate_repo_policy(
        repo_root,
        ["docs/decisions/adrs/adr-001-example.md"],
        structural_runner=structural_runner_stub,
    )

    assert failures == []


def setup_json_validation_repo(tmp_path: Path) -> Path:
    write_text(
        tmp_path / "contracts" / "schemas" / "concept-authority" / "concept-families-v1.json",
        "{}\n",
    )
    write_text(
        tmp_path / "contracts" / "schemas" / "profiles" / "semantic-profile-v1.json",
        "{}\n",
    )
    write_text(
        tmp_path / "contracts" / "schemas" / "backend-manifest" / "backend-manifest-v2.json",
        "{}\n",
    )
    write_text(
        tmp_path / "contracts" / "concept-authority" / "concept-families-v1.json",
        '{"schema_version": "concept-families-v1"}\n',
    )
    write_text(
        tmp_path / "contracts" / "profiles" / "semantic" / "reference-stack-v1.json",
        '{"schema_version": "semantic-profile-v1"}\n',
    )
    write_text(
        tmp_path / "contracts" / "fixtures" / "backend-manifest" / "backend-manifest-v2" / "valid" / "stub.json",
        "{}\n",
    )
    write_text(
        tmp_path / "contracts" / "fixtures" / "backend-manifest" / "backend-manifest-v2" / "invalid" / "broken.json",
        "{}\n",
    )
    return tmp_path


def test_should_run_full_validation_for_schema_driver_paths() -> None:
    assert should_run_full_validation(["tools/generate_contract_schemas.py"]) is True
    assert should_run_full_validation(["implementations/python/packages/aces_contracts/contracts.py"]) is True
    assert should_run_full_validation(["contracts/concept-authority/concept-families-v1.json"]) is False


def test_collect_validation_targets_includes_only_schema_governed_artifacts(tmp_path: Path) -> None:
    repo_root = setup_json_validation_repo(tmp_path)

    targets = collect_validation_targets(repo_root)

    observed = {(target.path, target.schema_path, target.mode) for target in targets}

    assert ("contracts/schemas/backend-manifest/backend-manifest-v2.json", None, "metaschema") in observed
    assert (
        "contracts/concept-authority/concept-families-v1.json",
        "contracts/schemas/concept-authority/concept-families-v1.json",
        "schema",
    ) in observed
    assert (
        "contracts/profiles/semantic/reference-stack-v1.json",
        "contracts/schemas/profiles/semantic-profile-v1.json",
        "schema",
    ) in observed
    assert (
        "contracts/fixtures/backend-manifest/backend-manifest-v2/valid/stub.json",
        "contracts/schemas/backend-manifest/backend-manifest-v2.json",
        "schema",
    ) in observed
    assert all("/invalid/" not in target.path for target in targets)


def test_collect_validation_targets_runs_full_scan_when_schema_drivers_change(tmp_path: Path) -> None:
    repo_root = setup_json_validation_repo(tmp_path)

    targets = collect_validation_targets(
        repo_root,
        paths=["implementations/python/packages/aces_contracts/contracts.py"],
    )

    assert any(target.path == "contracts/concept-authority/concept-families-v1.json" for target in targets)
