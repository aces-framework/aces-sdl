from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from .common import PolicyFailure, load_yaml, path_matches_any


UID_RE = re.compile(r"\b([A-Z]{3}-\d{3})\b", re.IGNORECASE)


def load_policy(repo_root: Path) -> dict:
    return load_yaml(repo_root / "tools" / "policy" / "requirement_order.yaml")


class RequirementClient(Protocol):
    def get_requirement(self, project: str, uid: str) -> dict: ...

    def get_traceability(self, requirement_id: str) -> list[dict]: ...


class GroundControlHttpClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _request(self, path: str, *, params: dict[str, str] | None = None) -> dict | list:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        request = Request(url, headers={"X-Actor": "repo-policy"})
        try:
            with urlopen(request) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{exc.code}: {body}") from exc
        except URLError as exc:
            raise RuntimeError(str(exc.reason)) from exc

    def get_requirement(self, project: str, uid: str) -> dict:
        return self._request(f"/api/v1/requirements/uid/{uid}", params={"project": project})

    def get_traceability(self, requirement_id: str) -> list[dict]:
        return self._request(f"/api/v1/requirements/{requirement_id}/traceability")


@dataclass(frozen=True)
class PhaseMatch:
    phase_id: str
    phase: dict


def _traceability_value(link: dict, snake_case: str, camel_case: str) -> str | None:
    value = link.get(snake_case)
    if value is not None:
        return value
    raw_value = link.get(camel_case)
    return raw_value if isinstance(raw_value, str) else None


def detect_requirement_uid(branch_name: str | None) -> str | None:
    if not branch_name:
        return None
    match = UID_RE.search(branch_name)
    return match.group(1).upper() if match else None


def evaluate_requirement_governance(
    repo_root: Path,
    changed: list[str],
    *,
    client: RequirementClient,
    requirement_uid: str,
) -> list[PolicyFailure]:
    policy = load_policy(repo_root)
    project = policy["project"]
    failures: list[PolicyFailure] = []

    requirement = client.get_requirement(project, requirement_uid)
    status = requirement["status"]
    if status in {"ARCHIVED", "DEPRECATED"}:
        return [
            PolicyFailure(
                "requirement-invalid-status",
                f"{requirement_uid} is {status} and is not valid for implementation work",
            )
        ]

    phase_match = match_phase(policy, requirement_uid)
    if phase_match is None:
        return [
            PolicyFailure(
                "requirement-policy-missing",
                f"{requirement_uid} is not mapped in tools/policy/requirement_order.yaml",
            )
        ]

    failures.extend(_check_phase_predecessors(policy, client, phase_match))
    failures.extend(_check_path_ownership(policy, phase_match, changed))
    failures.extend(_check_traceability(client, requirement, policy, changed))

    return failures


def match_phase(policy: dict, requirement_uid: str) -> PhaseMatch | None:
    for phase in policy.get("phases", []):
        if requirement_uid in phase.get("requirements", []):
            return PhaseMatch(phase["id"], phase)
        for pattern in phase.get("patterns", []):
            if re.match(pattern, requirement_uid):
                return PhaseMatch(phase["id"], phase)
    return None


def _check_phase_predecessors(
    policy: dict,
    client: RequirementClient,
    match: PhaseMatch,
) -> list[PolicyFailure]:
    failures: list[PolicyFailure] = []
    blocked_until = match.phase.get("blocked_until", [])
    project = policy["project"]
    for phase_id in blocked_until:
        phase = next(phase for phase in policy["phases"] if phase["id"] == phase_id)
        if phase.get("manual_release"):
            failures.append(
                PolicyFailure(
                    "requirement-order-blocked",
                    f"{match.phase_id} remains deferred until {phase_id} is explicitly released",
                )
            )
            continue
        incomplete: list[str] = []
        for uid in phase.get("requirements", []):
            status = client.get_requirement(project, uid)["status"]
            if status != "ACTIVE":
                incomplete.append(f"{uid} ({status})")
        if incomplete:
            failures.append(
                PolicyFailure(
                    "requirement-order-blocked",
                    f"{match.phase_id} is blocked until {phase_id} is complete; incomplete prerequisites: {', '.join(incomplete)}",
                )
            )
    return failures


def _check_path_ownership(policy: dict, match: PhaseMatch, changed: list[str]) -> list[PolicyFailure]:
    allowed = policy.get("ownership", {}).get(match.phase_id, [])
    if not allowed:
        return []
    failures: list[PolicyFailure] = []
    relevant = [
        path
        for path in changed
        if path.startswith("implementations/")
        or path.startswith("contracts/")
        or path.startswith("specs/")
        or path.startswith("docs/")
    ]
    for path in relevant:
        if not path_matches_any(path, allowed):
            failures.append(
                PolicyFailure(
                    "requirement-ownership-mismatch",
                    f"{match.phase_id} changes must stay within the mapped ownership roots for that phase",
                    path,
                )
            )
    return failures


def _check_traceability(
    client: RequirementClient,
    requirement: dict,
    policy: dict,
    changed: list[str],
) -> list[PolicyFailure]:
    traceability = client.get_traceability(requirement["id"])
    code_links = {
        artifact_identifier
        for link in traceability
        if _traceability_value(link, "artifact_type", "artifactType") == "CODE_FILE"
        and _traceability_value(link, "link_type", "linkType") == "IMPLEMENTS"
        and (artifact_identifier := _traceability_value(link, "artifact_identifier", "artifactIdentifier")) is not None
    }
    test_links = {
        artifact_identifier
        for link in traceability
        if _traceability_value(link, "artifact_type", "artifactType") == "TEST"
        and _traceability_value(link, "link_type", "linkType") == "TESTS"
        and (artifact_identifier := _traceability_value(link, "artifact_identifier", "artifactIdentifier")) is not None
    }
    failures: list[PolicyFailure] = []
    required_code_roots = policy["traceability"]["required_code_roots"]
    required_test_roots = policy["traceability"]["required_test_roots"]

    for path in changed:
        if path_matches_any(path, required_code_roots) and path.endswith(".py") and path not in code_links:
            failures.append(
                PolicyFailure(
                    "traceability-missing-implements",
                    f"{requirement['uid']} is missing an IMPLEMENTS traceability link for this code file",
                    path,
                )
            )
        if path_matches_any(path, required_test_roots) and path.endswith(".py") and path not in test_links:
            failures.append(
                PolicyFailure(
                    "traceability-missing-tests",
                    f"{requirement['uid']} is missing a TESTS traceability link for this test file",
                    path,
                )
            )
    return failures


def requirement_uid_from_context(branch_name: str | None, explicit_uid: str | None) -> str | None:
    return explicit_uid or os.environ.get("ACES_REQUIREMENT_UID") or detect_requirement_uid(branch_name)
