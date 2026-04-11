# ruff: noqa: E402, I001
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
import subprocess
import sys
import tempfile

import nox

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.gitleaks_tool import ensure_gitleaks
from tools.tool_versions import PRE_COMMIT_HOOKS_TOOL_SPEC, RUFF_TOOL_SPEC

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
EXCLUDED_PREFIXES = ("research/",)
PRIVATE_KEY_EXCLUDE_PREFIXES = ("implementations/python/tests/",)
MAX_LARGE_FILE_KB = "500"

nox.options.default_venv_backend = "none"
nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = ["verify"]


@dataclass(frozen=True)
class StageResult:
    name: str
    status: str
    detail: str = ""
    duration_s: float | None = None


@dataclass(frozen=True)
class HygieneSelection:
    paths: list[str]
    source: str


class SessionReporter:
    def __init__(self, session: nox.Session, session_name: str) -> None:
        self.session = session
        self.session_name = session_name
        self.results: list[StageResult] = []

    def run(self, name: str, func: Callable[[], None], *, detail: str = "") -> None:
        self._log("START", name, detail)
        started = perf_counter()
        try:
            func()
        except Exception:
            duration_s = perf_counter() - started
            self.results.append(StageResult(name=name, status="FAIL", detail=detail, duration_s=duration_s))
            self._log("FAIL", name, detail, duration_s)
            raise
        duration_s = perf_counter() - started
        self.results.append(StageResult(name=name, status="PASS", detail=detail, duration_s=duration_s))
        self._log("PASS", name, detail, duration_s)

    def skip(self, name: str, reason: str) -> None:
        self.results.append(StageResult(name=name, status="SKIP", detail=reason))
        self._log("SKIP", name, reason)

    def summary(self) -> None:
        self.session.log(f"[{self.session_name}] stage summary:")
        if not self.results:
            self.session.log(f"[{self.session_name}]   SKIP no stages executed")
            return
        for result in self.results:
            duration = f" ({result.duration_s:.2f}s)" if result.duration_s is not None else ""
            detail = f" :: {result.detail}" if result.detail else ""
            self.session.log(f"[{self.session_name}]   {result.status:<4} {result.name}{duration}{detail}")

    def _log(self, status: str, name: str, detail: str, duration_s: float | None = None) -> None:
        duration = f" ({duration_s:.2f}s)" if duration_s is not None else ""
        suffix = f" :: {detail}" if detail else ""
        self.session.log(f"[{self.session_name}] {status}: {name}{duration}{suffix}")


def _run(session: nox.Session, *args: str, silent: bool = False) -> None:
    session.run(*args, external=True, silent=silent)


def _git_lines(*args: str) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _changed_paths(*, staged: bool = False, base_rev: str | None = None) -> list[str]:
    if staged:
        return _normalize_paths(_git_lines("diff", "--name-only", "--diff-filter=d", "--cached"))
    if base_rev:
        return _normalize_paths(_git_lines("diff", "--name-only", "--diff-filter=d", base_rev, "HEAD"))
    return _normalize_paths(_git_lines("diff", "--name-only", "--diff-filter=d", "HEAD"))


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


def _run_uv_tool(session: nox.Session, spec: str, *args: str) -> None:
    _run(session, "uv", "tool", "run", "--from", spec, *args)


def _run_external_subprocess(*args: str) -> None:
    proc = subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode == 0:
        return
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    raise RuntimeError(f"{Path(args[0]).name} failed with exit code {proc.returncode}")


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


def _parse_hygiene_posargs(posargs: Sequence[str], *, default_all_files: bool) -> HygieneSelection:
    staged = False
    base_rev: str | None = None
    all_files = default_all_files
    explicit_paths: list[str] = []
    index = 0
    values = list(posargs)
    while index < len(values):
        arg = values[index]
        if arg == "--staged":
            staged = True
            all_files = False
            index += 1
            continue
        if arg == "--all-files":
            all_files = True
            staged = False
            base_rev = None
            index += 1
            continue
        if arg == "--base-rev":
            base_rev = values[index + 1]
            all_files = False
            index += 2
            continue
        explicit_paths.append(arg)
        all_files = False
        index += 1
    if explicit_paths:
        return HygieneSelection(paths=_normalize_paths(explicit_paths), source="explicit path selection")
    if staged:
        return HygieneSelection(
            paths=_changed_paths(staged=True),
            source="staged tracked files",
        )
    if base_rev:
        return HygieneSelection(
            paths=_changed_paths(base_rev=base_rev),
            source=f"changes since {base_rev}",
        )
    if all_files:
        return HygieneSelection(paths=_tracked_repo_paths(), source="tracked repository files")
    return HygieneSelection(paths=_changed_paths(), source="working tree changes")


def _tracked_repo_paths() -> list[str]:
    return _normalize_paths(_git_lines("ls-files", "--cached", "--others", "--exclude-standard"))


def _normalize_paths(paths: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in paths:
        path = Path(raw).as_posix().strip("/")
        if not path or path.startswith(EXCLUDED_PREFIXES):
            continue
        absolute = REPO_ROOT / path
        if not absolute.is_file() or path in seen:
            continue
        seen.add(path)
        normalized.append(path)
    return normalized


def _text_paths(paths: list[str]) -> list[str]:
    text_paths: list[str] = []
    for path in paths:
        try:
            sample = (REPO_ROOT / path).read_bytes()[:8192]
        except OSError:
            continue
        if b"\x00" in sample:
            continue
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError:
            continue
        text_paths.append(path)
    return text_paths


def _suffix_paths(paths: list[str], suffixes: tuple[str, ...]) -> list[str]:
    suffix_set = {suffix.lower() for suffix in suffixes}
    return [path for path in paths if Path(path).suffix.lower() in suffix_set]


def _chunked(paths: Sequence[str], *, size: int = 200) -> list[list[str]]:
    return [list(paths[index : index + size]) for index in range(0, len(paths), size)]


def _paths_trigger(paths: Iterable[str], prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefixes) or path in prefixes for path in paths)


def _run_pre_commit_hook(_session: nox.Session, command: str, *args: str, paths: list[str]) -> None:
    for batch in _chunked(paths):
        _run_external_subprocess("uv", "tool", "run", "--from", PRE_COMMIT_HOOKS_TOOL_SPEC, command, *args, *batch)


def _run_gitleaks_dir_scan(session: nox.Session, paths: list[str]) -> None:
    binary = ensure_gitleaks(REPO_ROOT)
    with tempfile.TemporaryDirectory(prefix="aces-gitleaks-") as tmpdir:
        scan_root = Path(tmpdir) / "scan"
        scan_root.mkdir()
        for path in paths:
            source = (REPO_ROOT / path).resolve()
            target = scan_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source)
        _run_external_subprocess(
            str(binary),
            "dir",
            "--follow-symlinks",
            "--no-banner",
            "--redact",
            "--log-level",
            "warn",
            str(scan_root),
        )


def _run_hygiene(
    session: nox.Session, reporter: SessionReporter, *, posargs: Sequence[str], default_all_files: bool
) -> None:
    selection = _parse_hygiene_posargs(posargs, default_all_files=default_all_files)
    paths = selection.paths
    detail = f"{len(paths)} files from {selection.source}"
    if not paths:
        reporter.skip("hygiene / candidate path resolution", f"no files selected from {selection.source}")
        return

    text_paths = _text_paths(paths)
    yaml_paths = _suffix_paths(paths, (".yaml", ".yml"))
    json_paths = _suffix_paths(paths, (".json",))
    private_key_paths = [path for path in paths if not path.startswith(PRIVATE_KEY_EXCLUDE_PREFIXES)]

    reporter.run(
        "hygiene / trailing whitespace",
        lambda: _run_pre_commit_hook(session, "trailing-whitespace-fixer", paths=text_paths),
        detail=f"{len(text_paths)} text files from {selection.source}",
    ) if text_paths else reporter.skip("hygiene / trailing whitespace", "no text files selected")

    reporter.run(
        "hygiene / eof newline",
        lambda: _run_pre_commit_hook(session, "end-of-file-fixer", paths=text_paths),
        detail=f"{len(text_paths)} text files from {selection.source}",
    ) if text_paths else reporter.skip("hygiene / eof newline", "no text files selected")

    reporter.run(
        "hygiene / yaml syntax",
        lambda: _run_pre_commit_hook(session, "check-yaml", "--unsafe", paths=yaml_paths),
        detail=f"{len(yaml_paths)} YAML files from {selection.source}",
    ) if yaml_paths else reporter.skip("hygiene / yaml syntax", "no YAML files selected")

    reporter.run(
        "hygiene / json syntax",
        lambda: _run_pre_commit_hook(session, "check-json", paths=json_paths),
        detail=f"{len(json_paths)} JSON files from {selection.source}",
    ) if json_paths else reporter.skip("hygiene / json syntax", "no JSON files selected")

    reporter.run(
        "hygiene / added large files",
        lambda: _run_pre_commit_hook(session, "check-added-large-files", "--maxkb", MAX_LARGE_FILE_KB, paths=paths),
        detail=detail,
    )

    reporter.run(
        "hygiene / merge conflict markers",
        lambda: _run_pre_commit_hook(session, "check-merge-conflict", paths=text_paths),
        detail=f"{len(text_paths)} text files from {selection.source}",
    ) if text_paths else reporter.skip("hygiene / merge conflict markers", "no text files selected")

    reporter.run(
        "hygiene / private key detection",
        lambda: _run_pre_commit_hook(session, "detect-private-key", paths=private_key_paths),
        detail=f"{len(private_key_paths)} files from {selection.source}",
    ) if private_key_paths else reporter.skip("hygiene / private key detection", "no eligible files selected")

    reporter.run(
        "hygiene / gitleaks",
        lambda: _run_gitleaks_dir_scan(session, paths),
        detail=detail,
    )


def _run_policy(session: nox.Session, reporter: SessionReporter, *args: str) -> None:
    _sync_project(session)
    reporter.run(
        "policy / conftest self-verify",
        lambda: _run(
            session,
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "--frozen",
            "python",
            "-c",
            "from tools.policy.conftest_tool import verify_conftest_policy; verify_conftest_policy()",
        ),
    )
    repo_args, requirement_args, skip_requirement = _split_policy_session_args(list(args))
    reporter.run(
        "policy / repo policy",
        lambda: _run_project_python(session, "tools/check_repo_policy.py", *repo_args),
    )
    if skip_requirement:
        reporter.skip("policy / requirement governance", "skipped by --skip-requirement")
    else:
        reporter.run(
            "policy / requirement governance",
            lambda: _run_project_python(session, "tools/check_requirement_governance.py", *requirement_args),
        )


def _run_contracts(session: nox.Session, reporter: SessionReporter, *args: str) -> None:
    _sync_project(session)
    reporter.run(
        "contracts / generated schema drift",
        lambda: _run_project_python(session, "tools/check_generated_schemas.py"),
    )
    reporter.run(
        "contracts / json artifact validation",
        lambda: _run_project_python(session, "tools/check_json_artifacts.py", *args),
    )


def _run_lint(session: nox.Session, reporter: SessionReporter) -> None:
    reporter.run(
        "lint / ruff format (project)",
        lambda: _run_ruff(session, "format", "--check", ".", project_relative=True),
    )
    reporter.run(
        "lint / ruff check (project)",
        lambda: _run_ruff(session, "check", ".", project_relative=True),
    )
    reporter.run(
        "lint / ruff format (tooling)",
        lambda: _run_ruff(session, "format", "--check", "tools", "noxfile.py"),
    )
    reporter.run(
        "lint / ruff check (tooling)",
        lambda: _run_ruff(session, "check", "tools", "noxfile.py"),
    )


def _run_changed_lint(session: nox.Session, reporter: SessionReporter, paths: list[str]) -> None:
    prefix = "implementations/python/"
    project_paths = []
    for path in paths:
        if path.startswith(prefix) and path.endswith(".py"):
            project_paths.append(path[len(prefix) :])
    if project_paths:
        reporter.run(
            "lint / ruff format (changed project files)",
            lambda: _run_ruff(session, "format", "--check", *project_paths, project_relative=True),
            detail=f"{len(project_paths)} files",
        )
        reporter.run(
            "lint / ruff check (changed project files)",
            lambda: _run_ruff(session, "check", *project_paths, project_relative=True),
            detail=f"{len(project_paths)} files",
        )
    else:
        reporter.skip("lint / ruff format (changed project files)", "no changed project Python files")
        reporter.skip("lint / ruff check (changed project files)", "no changed project Python files")

    tooling_paths = [
        path for path in paths if (path.startswith("tools/") or path == "noxfile.py") and path.endswith(".py")
    ]
    if tooling_paths:
        reporter.run(
            "lint / ruff format (changed tooling files)",
            lambda: _run_ruff(session, "format", "--check", *tooling_paths),
            detail=f"{len(tooling_paths)} files",
        )
        reporter.run(
            "lint / ruff check (changed tooling files)",
            lambda: _run_ruff(session, "check", *tooling_paths),
            detail=f"{len(tooling_paths)} files",
        )
    else:
        reporter.skip("lint / ruff format (changed tooling files)", "no changed tooling Python files")
        reporter.skip("lint / ruff check (changed tooling files)", "no changed tooling Python files")


def _run_tests(session: nox.Session, reporter: SessionReporter, posargs: list[str] | None = None) -> None:
    args = list(posargs) if posargs else ["-q"]
    reporter.run(
        "tests / pytest",
        lambda: _run_pytest(session, *args, coverage=True),
        detail=" ".join(args),
    )


def _run_fuzz(session: nox.Session, reporter: SessionReporter) -> None:
    reporter.run(
        "tests / pytest fuzz",
        lambda: _run_pytest(session, "-m", "fuzz", "-v"),
    )


@nox.session
def hygiene(session: nox.Session) -> None:
    reporter = SessionReporter(session, "hygiene")
    try:
        _run_hygiene(session, reporter, posargs=session.posargs, default_all_files=True)
    finally:
        reporter.summary()


@nox.session
def policy(session: nox.Session) -> None:
    reporter = SessionReporter(session, "policy")
    try:
        _run_policy(session, reporter, *session.posargs)
    finally:
        reporter.summary()


@nox.session
def lint(session: nox.Session) -> None:
    reporter = SessionReporter(session, "lint")
    try:
        _run_lint(session, reporter)
    finally:
        reporter.summary()


@nox.session
def contracts(session: nox.Session) -> None:
    reporter = SessionReporter(session, "contracts")
    try:
        _run_contracts(session, reporter, *session.posargs)
    finally:
        reporter.summary()


@nox.session
def tests(session: nox.Session) -> None:
    reporter = SessionReporter(session, "tests")
    try:
        _run_tests(session, reporter, list(session.posargs))
    finally:
        reporter.summary()


@nox.session
def fuzz(session: nox.Session) -> None:
    reporter = SessionReporter(session, "fuzz")
    try:
        _run_fuzz(session, reporter)
    finally:
        reporter.summary()


@nox.session(name="hook-pre-commit")
def hook_pre_commit(session: nox.Session) -> None:
    reporter = SessionReporter(session, "hook-pre-commit")
    changed = [Path(arg).as_posix() for arg in session.posargs if not arg.startswith("-")]
    try:
        _run_hygiene(session, reporter, posargs=changed, default_all_files=False)
        _run_policy(session, reporter, "--staged")
        _run_changed_lint(session, reporter, changed)
        if _paths_trigger(changed, CONTRACT_TRIGGER_PREFIXES):
            _run_contracts(session, reporter)
        else:
            reporter.skip("contracts / generated schema drift", "no contract-bearing changes")
            reporter.skip("contracts / json artifact validation", "no contract-bearing changes")
        if _paths_trigger(changed, FULL_TEST_TRIGGER_PREFIXES):
            reporter.run("tests / pytest", lambda: _run_pytest(session, "-q"), detail="full implementation test sweep")
        elif _paths_trigger(changed, TOOLING_TEST_TRIGGER_PREFIXES):
            reporter.run(
                "tests / targeted tooling tests",
                lambda: _run_pytest(session, *TARGETED_POLICY_TESTS, "-q"),
                detail=" ".join(TARGETED_POLICY_TESTS),
            )
        else:
            reporter.skip("tests / pytest", "no implementation or tooling test trigger paths changed")
    finally:
        reporter.summary()


@nox.session(name="hook-pre-push")
def hook_pre_push(session: nox.Session) -> None:
    reporter = SessionReporter(session, "hook-pre-push")
    try:
        _run_hygiene(session, reporter, posargs=["--all-files"], default_all_files=True)
        _run_policy(session, reporter)
        _run_lint(session, reporter)
        _run_contracts(session, reporter)
        _run_tests(session, reporter)
        _run_fuzz(session, reporter)
    finally:
        reporter.summary()


@nox.session
def verify(session: nox.Session) -> None:
    reporter = SessionReporter(session, "verify")
    try:
        _run_hygiene(session, reporter, posargs=session.posargs or ["--all-files"], default_all_files=True)
        _run_policy(session, reporter, *session.posargs)
        _run_lint(session, reporter)
        _run_contracts(session, reporter)
        _run_tests(session, reporter)
    finally:
        reporter.summary()
