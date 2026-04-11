from __future__ import annotations

import ast
import re
from collections.abc import Callable
from pathlib import Path

from .common import PolicyFailure, load_yaml, path_matches_prefix
from .conftest_tool import run_conftest_policy

StructuralPolicyRunner = Callable[[dict], list[PolicyFailure]]


def load_policy(repo_root: Path) -> dict:
    return load_yaml(repo_root / "tools" / "policy" / "adr_policy.yaml")


def evaluate_repo_policy(
    repo_root: Path,
    changed: list[str],
    *,
    check_set: str = "full",
    structural_runner: StructuralPolicyRunner | None = None,
) -> list[PolicyFailure]:
    policy = load_policy(repo_root)
    failures: list[PolicyFailure] = []

    if not changed:
        return failures

    if structural_runner is None:

        def structural_runner(input_document: dict) -> list[PolicyFailure]:
            return run_conftest_policy(input_document, repo_root=repo_root)

    failures.extend(
        structural_runner(
            {
                "changed": changed,
                "check_set": check_set,
                "policy": policy,
            }
        )
    )
    failures.extend(_check_package_import_direction(repo_root, policy, changed))
    failures.extend(_check_compatibility_wrappers(repo_root, policy, changed))

    if check_set == "full":
        failures.extend(_check_adr_index(repo_root, policy, changed))

    if "CHANGELOG.md" in changed:
        failures.extend(_check_changelog_versioned(repo_root))

    return failures


def _check_package_import_direction(repo_root: Path, policy: dict, changed: list[str]) -> list[PolicyFailure]:
    failures: list[PolicyFailure] = []
    package_root = repo_root / policy["compatibility_layer"]["owning_root"]
    prefixes = tuple(policy["compatibility_layer"]["forbidden_import_prefixes"])
    for rel_path in changed:
        if not rel_path.endswith(".py") or not path_matches_prefix(
            rel_path, package_root.relative_to(repo_root).as_posix()
        ):
            continue
        path = repo_root / rel_path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(prefixes):
                        failures.append(
                            PolicyFailure(
                                "compatibility-import-direction",
                                "owning packages must not import from compatibility-only aces.* modules",
                                rel_path,
                            )
                        )
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(prefixes):
                failures.append(
                    PolicyFailure(
                        "compatibility-import-direction",
                        "owning packages must not import from compatibility-only aces.* modules",
                        rel_path,
                    )
                )
    return failures


def _check_compatibility_wrappers(repo_root: Path, policy: dict, changed: list[str]) -> list[PolicyFailure]:
    failures: list[PolicyFailure] = []
    compat_root = policy["compatibility_layer"]["root"]
    for rel_path in changed:
        if not rel_path.endswith(".py") or not path_matches_prefix(rel_path, compat_root):
            continue
        path = repo_root / rel_path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel_path)
        if not _is_wrapper_module(tree):
            failures.append(
                PolicyFailure(
                    "compatibility-wrapper-only",
                    "compatibility-layer modules must remain wrappers/re-exports only",
                    rel_path,
                )
            )
    return failures


def _is_wrapper_module(tree: ast.Module) -> bool:
    allowed_import_names = {"reexport", "package_version"}
    allowed_calls = {"_reexport", "package_version"}
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.ImportFrom):
            if node.module != "aces._compat":
                return False
            if any(alias.name not in allowed_import_names for alias in node.names):
                return False
            continue
        if isinstance(node, ast.Assign):
            if any(not isinstance(target, ast.Name) for target in node.targets):
                return False
            target_names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if target_names == {"__all__"} and isinstance(node.value, (ast.List, ast.Tuple)):
                continue
            if target_names == {"__version__"} and isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Name) and node.value.func.id in allowed_calls:
                    continue
            return False
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name) and node.value.func.id == "_reexport":
                continue
            return False
        if isinstance(node, ast.Delete):
            continue
        return False
    return True


CHANGELOG_HEADING_RE = re.compile(r"^## \[(.+?)\]", re.MULTILINE)
SECTION_CONTENT_RE = re.compile(r"^###\s", re.MULTILINE)


def _check_changelog_versioned(repo_root: Path) -> list[PolicyFailure]:
    changelog = repo_root / "CHANGELOG.md"
    if not changelog.exists():
        return []
    text = changelog.read_text(encoding="utf-8")
    for match in CHANGELOG_HEADING_RE.finditer(text):
        label = match.group(1)
        if label.lower() == "unreleased":
            heading_end = match.end()
            next_heading = CHANGELOG_HEADING_RE.search(text, heading_end)
            section_text = text[heading_end : next_heading.start()] if next_heading else text[heading_end:]
            if SECTION_CONTENT_RE.search(section_text):
                return [
                    PolicyFailure(
                        "changelog-unreleased-content",
                        "CHANGELOG.md has content under [Unreleased]; assign a version number and date",
                        "CHANGELOG.md",
                    )
                ]
    return []


ADR_HEADER_RE = re.compile(r"^# ADR-(\d{3}): (.+)$", re.MULTILINE)
README_ROW_RE = re.compile(r"^\| \[(\d{3})\]\(([^)]+)\) \| (.+?) \| (.+?) \| (\d{4}-\d{2}-\d{2}) \|$", re.MULTILINE)


def _parse_adr_file(path: Path) -> tuple[str, str, str, str]:
    text = path.read_text(encoding="utf-8")
    header = ADR_HEADER_RE.search(text)
    if not header:
        raise ValueError(f"{path} is missing ADR header")
    status = _normalize_adr_status(_extract_markdown_section(text, "Status"))
    date = _extract_markdown_section(text, "Date")
    return header.group(1), header.group(2).strip(), status.strip(), date.strip()


def _extract_markdown_section(text: str, section: str) -> str:
    marker = f"## {section}"
    start = text.find(marker)
    if start != -1:
        body = text[start + len(marker) :]
        body = body.lstrip()
        next_header = body.find("\n## ")
        if next_header != -1:
            body = body[:next_header]
        return body.strip().splitlines()[0].strip()

    legacy_marker = re.search(rf"^\*\*{re.escape(section)}:\*\*\s*(.+)$", text, re.MULTILINE)
    if legacy_marker:
        return legacy_marker.group(1).strip()

    raise ValueError(f"missing {section} section")


def _normalize_adr_status(status: str) -> str:
    normalized = " ".join(status.split())
    lowered = normalized.lower()
    if lowered in {"accepted", "proposed", "deprecated"}:
        return lowered
    superseded = re.fullmatch(r"superseded by (adr-\d{3})", lowered)
    if superseded:
        return f"superseded by {superseded.group(1).upper()}"
    return normalized


def _check_adr_index(repo_root: Path, policy: dict, changed: list[str]) -> list[PolicyFailure]:
    index_path = policy["adr_index"]["index_path"]
    if not any(path.startswith("docs/decisions/adrs/") for path in changed):
        return []

    adr_dir = repo_root / "docs" / "decisions" / "adrs"
    adr_files = sorted(path for path in adr_dir.glob("adr-*.md") if path.name != "README.md")
    expected: dict[str, tuple[str, str, str, str]] = {}
    for adr_file in adr_files:
        number, title, status, date_value = _parse_adr_file(adr_file)
        expected[number] = (adr_file.name, title, status, date_value)

    readme_text = (repo_root / index_path).read_text(encoding="utf-8")
    actual = {
        number: (Path(link).name, title.strip(), _normalize_adr_status(status), date_value)
        for number, link, title, status, date_value in README_ROW_RE.findall(readme_text)
    }

    if expected != actual:
        return [
            PolicyFailure(
                "adr-index-sync",
                "ADR index is out of sync with the ADR documents",
                index_path,
            )
        ]
    return []
