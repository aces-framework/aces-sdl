# ruff: noqa: E402, I001
from __future__ import annotations

from pathlib import Path
import sys
from collections.abc import Iterable

import nox

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tool_versions import RUFF_TOOL_SPEC

PROJECT_ROOT = REPO_ROOT / "implementations" / "python"
RUFF_CONFIG = PROJECT_ROOT / "pyproject.toml"
TARGETED_POLICY_TESTS = [
    "implementations/python/tests/test_repo_policy_tools.py",
    "implementations/python/tests/test_requirement_governance.py",
]
CONTRACT_TRIGGER_PREFIXES = (
    "contracts/",
    "implementations/python/packages/aces_contracts/",
    "implementations/python/packages/aces_backend_protocols/",
    "implementations/python/packages/aces_processor/",
    "tools/generate_contract_schemas.py",
    "tools/check_json_artifacts.py",
)
FULL_TEST_TRIGGER_PREFIXES = ("implementations/python/",)
TOOLING_TEST_TRIGGER_PREFIXES = (
    "tools/",
    ".github/workflows/ci.yml",
    ".pre-commit-config.yaml",
    "noxfile.py",
)

nox.options.default_venv_backend = "none"
nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = ["verify"]


def _run(session: nox.Session, *args: str) -> None:
    session.run(*args, external=True)


def _sync_project(session: nox.Session) -> None:
    _run(session, "uv", "sync", "--project", str(PROJECT_ROOT), "--all-extras", "--frozen")


def _run_project_python(session: nox.Session, script: str, *args: str) -> None:
    _run(
        session,
        "uv",
        "run",
        "--project",
        str(PROJECT_ROOT),
        "--frozen",
        "python",
        script,
        *args,
    )


def _run_ruff(session: nox.Session, *args: str, project_relative: bool = False) -> None:
    command = [
        "uv",
        "tool",
        "run",
        "--from",
        RUFF_TOOL_SPEC,
        "ruff",
    ]
    if project_relative:
        with session.chdir(PROJECT_ROOT):
            _run(session, *command, *args)
        return
    _run(session, *command, "--config", str(RUFF_CONFIG), *args)


def _run_pytest(session: nox.Session, *args: str, coverage: bool = False) -> None:
    _sync_project(session)
    normalized_args = [
        str((REPO_ROOT / arg).relative_to(PROJECT_ROOT)) if arg.startswith("implementations/python/") else arg
        for arg in args
    ]
    if coverage:
        with session.chdir(PROJECT_ROOT):
            _run(session, "uv", "run", "--frozen", "coverage", "erase")
            _run(session, "uv", "run", "--frozen", "coverage", "run", "-m", "pytest", *normalized_args)
            _run(session, "uv", "run", "--frozen", "coverage", "xml")
            _run(session, "uv", "run", "--frozen", "coverage", "report", "--fail-under=50")
        return
    with session.chdir(PROJECT_ROOT):
        _run(session, "uv", "run", "--frozen", "python", "-m", "pytest", *normalized_args)


def _split_policy_session_args(posargs: list[str]) -> tuple[list[str], list[str], bool]:
    repo_args: list[str] = []
    requirement_args: list[str] = []
    skip_requirement = False
    index = 0
    while index < len(posargs):
        arg = posargs[index]
        if arg == "--skip-requirement":
            skip_requirement = True
            index += 1
            continue
        if arg == "--requirement-uid":
            requirement_args.extend([arg, posargs[index + 1]])
            index += 2
            continue
        if arg == "--base-rev":
            repo_args.extend([arg, posargs[index + 1]])
            requirement_args.extend([arg, posargs[index + 1]])
            index += 2
            continue
        repo_args.append(arg)
        requirement_args.append(arg)
        index += 1
    return repo_args, requirement_args, skip_requirement


def _run_policy(session: nox.Session, *args: str) -> None:
    _sync_project(session)
    _run(
        session,
        "uv",
        "run",
        "--project",
        str(PROJECT_ROOT),
        "--frozen",
        "python",
        "-c",
        "from tools.policy.conftest_tool import verify_conftest_policy; verify_conftest_policy()",
    )
    repo_args, requirement_args, skip_requirement = _split_policy_session_args(list(args))
    _run_project_python(session, "tools/check_repo_policy.py", *repo_args)
    if not skip_requirement:
        _run_project_python(session, "tools/check_requirement_governance.py", *requirement_args)


def _run_contracts(session: nox.Session, *args: str) -> None:
    _sync_project(session)
    _run_project_python(session, "tools/check_generated_schemas.py")
    _run_project_python(session, "tools/check_json_artifacts.py", *args)


def _run_lint(session: nox.Session) -> None:
    _run_ruff(session, "format", "--check", ".", project_relative=True)
    _run_ruff(session, "check", ".", project_relative=True)
    _run_ruff(session, "format", "--check", "tools", "noxfile.py")
    _run_ruff(session, "check", "tools", "noxfile.py")


def _run_tests(session: nox.Session, posargs: list[str] | None = None) -> None:
    args = list(posargs) if posargs else ["-q"]
    _run_pytest(session, *args, coverage=True)


def _run_fuzz(session: nox.Session) -> None:
    _run_pytest(session, "-m", "fuzz", "-v")


def _paths_trigger(paths: Iterable[str], prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefixes) or path in prefixes for path in paths)


def _run_changed_lint(session: nox.Session, paths: list[str]) -> None:
    prefix = "implementations/python/"
    project_paths = []
    for path in paths:
        if path.startswith(prefix) and path.endswith(".py"):
            project_paths.append(path[len(prefix) :])
    if project_paths:
        _run_ruff(session, "format", "--check", *project_paths, project_relative=True)
        _run_ruff(session, "check", *project_paths, project_relative=True)

    tooling_paths = [
        path for path in paths if (path.startswith("tools/") or path == "noxfile.py") and path.endswith(".py")
    ]
    if tooling_paths:
        _run_ruff(session, "format", "--check", *tooling_paths)
        _run_ruff(session, "check", *tooling_paths)


@nox.session
def policy(session: nox.Session) -> None:
    _run_policy(session, *session.posargs)


@nox.session
def lint(session: nox.Session) -> None:
    _run_lint(session)


@nox.session
def contracts(session: nox.Session) -> None:
    _run_contracts(session, *session.posargs)


@nox.session
def tests(session: nox.Session) -> None:
    _run_tests(session, list(session.posargs))


@nox.session
def fuzz(session: nox.Session) -> None:
    _run_fuzz(session)


@nox.session(name="hook-pre-commit")
def hook_pre_commit(session: nox.Session) -> None:
    changed = [arg for arg in session.posargs if not arg.startswith("-")]
    _run_policy(session, "--staged")
    _run_changed_lint(session, changed)
    if _paths_trigger(changed, CONTRACT_TRIGGER_PREFIXES):
        _run_contracts(session)
    if _paths_trigger(changed, FULL_TEST_TRIGGER_PREFIXES):
        _run_pytest(session, "-q")
    elif _paths_trigger(changed, TOOLING_TEST_TRIGGER_PREFIXES):
        _run_pytest(session, *TARGETED_POLICY_TESTS, "-q")


@nox.session(name="hook-pre-push")
def hook_pre_push(session: nox.Session) -> None:
    _run_policy(session)
    _run_lint(session)
    _run_contracts(session)
    _run_tests(session)
    _run_fuzz(session)


@nox.session
def verify(session: nox.Session) -> None:
    _run_policy(session, *session.posargs)
    _run_lint(session)
    _run_contracts(session)
    _run_tests(session)
