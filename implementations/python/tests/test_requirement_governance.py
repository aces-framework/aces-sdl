from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.policy.requirement_governance import detect_requirement_uid, evaluate_requirement_governance


class FakeClient:
    def __init__(self, requirements: dict[str, dict], traceability: dict[str, list[dict]]) -> None:
        self.requirements = requirements
        self.traceability = traceability

    def get_requirement(self, project: str, uid: str) -> dict:
        return self.requirements[uid]

    def get_traceability(self, requirement_id: str) -> list[dict]:
        return self.traceability.get(requirement_id, [])


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def setup_policy_repo(tmp_path: Path) -> Path:
    policy_dir = tmp_path / "tools" / "policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "tools" / "policy" / "requirement_order.yaml", policy_dir / "requirement_order.yaml")
    return tmp_path


def make_client(*, requirement_status: str = "DRAFT", api_412_status: str = "DRAFT") -> FakeClient:
    requirements = {
        "GOV-918": {"id": "req-gov-918", "uid": "GOV-918", "status": requirement_status},
        "API-412": {"id": "req-api-412", "uid": "API-412", "status": api_412_status},
        "RUN-300": {"id": "req-run-300", "uid": "RUN-300", "status": "ACTIVE"},
        "RUN-313": {"id": "req-run-313", "uid": "RUN-313", "status": "DRAFT"},
        "GOV-917": {"id": "req-gov-917", "uid": "GOV-917", "status": "ACTIVE"},
        "GOV-919": {"id": "req-gov-919", "uid": "GOV-919", "status": "ACTIVE"},
        "GOV-920": {"id": "req-gov-920", "uid": "GOV-920", "status": "ACTIVE"},
        "GOV-921": {"id": "req-gov-921", "uid": "GOV-921", "status": "ACTIVE"},
        "GOV-922": {"id": "req-gov-922", "uid": "GOV-922", "status": "ACTIVE"},
    }
    traceability = {
        "req-gov-918": [
            {
                "artifact_identifier": "implementations/python/packages/aces_processor/bindings.py",
                "artifact_type": "CODE_FILE",
                "link_type": "IMPLEMENTS",
            },
            {
                "artifact_identifier": "implementations/python/tests/test_concept_authority.py",
                "artifact_type": "TEST",
                "link_type": "TESTS",
            },
        ],
        "req-api-412": [
            {
                "artifact_identifier": "implementations/python/packages/aces_processor/manifest.py",
                "artifact_type": "CODE_FILE",
                "link_type": "IMPLEMENTS",
            }
        ],
        "req-run-313": [],
    }
    return FakeClient(requirements=requirements, traceability=traceability)


def test_detect_requirement_uid_from_branch_name() -> None:
    assert detect_requirement_uid("feature/GOV-918-cross-artifact-binding") == "GOV-918"
    assert detect_requirement_uid("15-gov-918-cross-artifact-concept-binding") == "GOV-918"
    assert detect_requirement_uid("feature/no-uid-here") is None


def test_archived_requirements_are_rejected(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    client = make_client(requirement_status="ARCHIVED")

    failures = evaluate_requirement_governance(
        repo_root,
        ["implementations/python/packages/aces_processor/bindings.py"],
        client=client,
        requirement_uid="GOV-918",
    )

    assert [failure.rule_id for failure in failures] == ["requirement-invalid-status"]


def test_blocked_phase_requires_previous_phase_completion(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    client = make_client(api_412_status="DRAFT")
    write_text(
        repo_root / "implementations" / "python" / "packages" / "aces_processor" / "manifest.py",
        "VALUE = 1\n",
    )

    failures = evaluate_requirement_governance(
        repo_root,
        ["implementations/python/packages/aces_processor/manifest.py"],
        client=client,
        requirement_uid="API-412",
    )

    assert [failure.rule_id for failure in failures] == ["requirement-order-blocked"]


def test_ownership_mismatch_is_reported(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    client = make_client()
    write_text(
        repo_root / "implementations" / "python" / "packages" / "aces_sdl" / "parser.py",
        "VALUE = 1\n",
    )

    failures = evaluate_requirement_governance(
        repo_root,
        ["implementations/python/packages/aces_sdl/parser.py"],
        client=client,
        requirement_uid="GOV-918",
    )

    assert {failure.rule_id for failure in failures} == {
        "requirement-ownership-mismatch",
        "traceability-missing-implements",
    }


def test_missing_traceability_links_are_reported(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    client = make_client()
    write_text(
        repo_root / "implementations" / "python" / "packages" / "aces_processor" / "new_binding.py",
        "VALUE = 1\n",
    )
    write_text(
        repo_root / "implementations" / "python" / "tests" / "test_new_binding.py",
        "def test_value():\n    assert True\n",
    )

    failures = evaluate_requirement_governance(
        repo_root,
        [
            "implementations/python/packages/aces_processor/new_binding.py",
            "implementations/python/tests/test_new_binding.py",
        ],
        client=client,
        requirement_uid="RUN-313",
    )

    assert {failure.rule_id for failure in failures} == {
        "traceability-missing-implements",
        "traceability-missing-tests",
    }


def test_requirement_governance_passes_for_allowed_paths_and_traceability(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    client = make_client()
    write_text(
        repo_root / "implementations" / "python" / "packages" / "aces_processor" / "bindings.py",
        "VALUE = 1\n",
    )
    write_text(
        repo_root / "implementations" / "python" / "tests" / "test_concept_authority.py",
        "def test_value():\n    assert True\n",
    )

    failures = evaluate_requirement_governance(
        repo_root,
        [
            "implementations/python/packages/aces_processor/bindings.py",
            "implementations/python/tests/test_concept_authority.py",
        ],
        client=client,
        requirement_uid="GOV-918",
    )

    assert failures == []


def test_requirement_governance_accepts_camel_case_traceability_payload(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    requirements = {
        "GOV-918": {"id": "req-gov-918", "uid": "GOV-918", "status": "ACTIVE"},
    }
    client = FakeClient(
        requirements=requirements,
        traceability={
            "req-gov-918": [
                {
                    "artifactIdentifier": "implementations/python/packages/aces_contracts/contracts.py",
                    "artifactType": "CODE_FILE",
                    "linkType": "IMPLEMENTS",
                },
                {
                    "artifactIdentifier": "implementations/python/tests/test_requirement_governance.py",
                    "artifactType": "TEST",
                    "linkType": "TESTS",
                },
            ]
        },
    )
    write_text(
        repo_root / "implementations" / "python" / "packages" / "aces_contracts" / "contracts.py",
        "VALUE = 1\n",
    )
    write_text(
        repo_root / "implementations" / "python" / "tests" / "test_requirement_governance.py",
        "def test_value():\n    assert True\n",
    )

    failures = evaluate_requirement_governance(
        repo_root,
        [
            "implementations/python/packages/aces_contracts/contracts.py",
            "implementations/python/tests/test_requirement_governance.py",
        ],
        client=client,
        requirement_uid="GOV-918",
    )

    assert failures == []
