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


def _load_policy_guarded(repo_root: Path) -> tuple[dict | None, list[PolicyFailure]]:
    """Load ``adr_policy.yaml`` and confirm its root is a mapping. A parse
    error or a non-mapping root surfaces as ``policy-config-malformed``
    rather than a traceback, so a PR that breaks the policy file fails the
    gate cleanly instead of crashing CI (and instead of letting downstream
    checkers raise ``KeyError`` on a malformed mapping)."""
    fail = lambda msg: PolicyFailure("policy-config-malformed", msg, _POLICY_CONFIG_PATH)  # noqa: E731
    try:
        policy = load_policy(repo_root)
    except Exception:  # noqa: BLE001 — yaml.YAMLError / OSError / anything load_yaml raises; surface, don't echo
        return None, [fail(f"{_POLICY_CONFIG_PATH} could not be parsed (missing or invalid YAML)")]
    if not isinstance(policy, dict):
        return None, [fail(f"{_POLICY_CONFIG_PATH} root must be a YAML mapping; got {type(policy).__name__}")]
    return policy, []


def evaluate_repo_policy(
    repo_root: Path,
    changed: list[str],
    *,
    check_set: str = "full",
    structural_runner: StructuralPolicyRunner | None = None,
) -> list[PolicyFailure]:
    policy, policy_load_errs = _load_policy_guarded(repo_root)
    if policy_load_errs:
        return policy_load_errs
    assert policy is not None

    failures: list[PolicyFailure] = []

    # Drop any changed path that escapes the repository root (absolute,
    # parent-traversal, or a planted symlink that resolves outside the
    # tree) BEFORE any checker reads it. This is a single chokepoint:
    # every downstream checker that opens a changed file — the layering
    # scan, the size cap, the import-direction check, the compat-wrapper
    # check — receives an already-validated list, so none of them can be
    # tricked into reading an out-of-tree file. See ADR-015.
    safe_changed: list[str] = []
    for rel_path in changed:
        if _safe_repo_path(repo_root, rel_path) is None:
            failures.append(
                PolicyFailure(
                    "policy-path-unsafe",
                    f"changed path '{rel_path}' resolves outside the repository root; refusing to inspect",
                    rel_path,
                )
            )
        else:
            safe_changed.append(rel_path)
    changed = safe_changed

    if not changed:
        # No by-file changes to check (e.g. a deletion-only PR — the repo's
        # changed-paths helper excludes deletions). The ADR-015 config-wide
        # invariants (allowlist present + well-formed, allowlist ⊆ the
        # locked set, every initial oversized file either still
        # allow-listed-and-over-cap or genuinely split below it) must still
        # hold regardless, so run that portion before returning.
        failures.extend(_check_layering_and_oversized(repo_root, policy, []))
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
    failures.extend(_check_layering_and_oversized(repo_root, policy, changed))

    if check_set == "full":
        failures.extend(_check_adr_index(repo_root, policy, changed))

    if "CHANGELOG.md" in changed:
        failures.extend(_check_changelog_versioned(repo_root))

    return failures


# ──────────────────────────────────────────────────────────────────────────
# ADR-015: SDL→processor layering rule + 600-line source-file cap.
#
# These two gates catch unintentional regressions in normal contributions:
# a developer who accidentally writes `import aces_processor` in `aces_sdl/`,
# or one who pushes a >600-line file, or a split PR that forgets to drain
# its allowlist entry. The policy and its YAML config are PR-mutable; PR
# review (not this code) defends against deliberate weakening. See ADR-015.
# ──────────────────────────────────────────────────────────────────────────

_POLICY_CONFIG_PATH = "tools/policy/adr_policy.yaml"

# The set of source files that were over the 600-line cap when ADR-015
# landed. The size-cap allowlist (tools/policy/oversized_allowlist.yaml) may
# only ever be a SUBSET of this set: entries are removed as child PRs of #3
# split their file, and no new entry may be added. This is a code constant —
# not config in adr_policy.yaml — so that "the allowlist only shrinks" is
# enforced against a fixed reference rather than against an input the same PR
# can edit. Adding a 15th oversized file therefore requires a diff to this
# module, which PR review scrutinises as policy, not as data noise.
_ADR015_INITIAL_OVERSIZED_FILES: frozenset[str] = frozenset(
    {
        "implementations/python/packages/aces_processor/models.py",
        "implementations/python/packages/aces_processor/manager.py",
        "implementations/python/packages/aces_processor/compiler.py",
        "implementations/python/packages/aces_sdl/validator.py",
        "implementations/python/packages/aces_contracts/contracts.py",
        "implementations/python/packages/aces_processor/planner.py",
        "implementations/python/packages/aces_processor/control_plane.py",
        "implementations/python/packages/aces_conformance/conformance.py",
        "implementations/python/packages/aces_backend_stubs/stubs.py",
        "implementations/python/packages/aces_sdl/module_registry.py",
        "implementations/python/packages/aces_processor/control_plane_api.py",
        "implementations/python/packages/aces_mcp/tools/authoring.py",
        "implementations/python/packages/aces_mcp/tools/inspection.py",
        "implementations/python/packages/aces_sdl/orchestration.py",
    }
)


def _is_str(value: object) -> bool:
    return isinstance(value, str)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _str_list_ok(value: object, *, allow_empty: bool) -> bool:
    if not isinstance(value, list):
        return False
    if not value and not allow_empty:
        return False
    return all(_is_str(item) for item in value)


def _safe_repo_path(repo_root: Path, rel_path: str) -> Path | None:
    """Resolve ``rel_path`` against ``repo_root`` and return the resolved
    path only if it stays inside the repository. Returns None for absolute
    paths, parent-traversal segments, or symlinks that resolve outside the
    repo. This guards every place the policy reads a path that ultimately
    comes from PR-controlled config or the changed-file list."""
    candidate = Path(rel_path)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        return None
    try:
        resolved = (repo_root / candidate).resolve()
        resolved.relative_to(repo_root.resolve())
    except (ValueError, OSError):
        return None
    return resolved


def _validate_oversized_config(
    config: object,
) -> tuple[dict | None, list[PolicyFailure]]:
    """Validate the ``oversized_source_files`` block. Returns
    ``(normalized_config, failures)``; ``normalized_config`` is None when
    the block is missing/malformed (with failures populated). Per ADR-015
    this block is required policy — an absent block is a malformation, not
    an opt-out, so the size cap can't be silently disabled."""
    fail = lambda msg: PolicyFailure("policy-config-malformed", msg, _POLICY_CONFIG_PATH)  # noqa: E731
    if config is None:
        return None, [fail("oversized_source_files block is required (ADR-015) but is absent")]
    if not isinstance(config, dict):
        return None, [fail(f"oversized_source_files must be a mapping; got {type(config).__name__}")]

    failures: list[PolicyFailure] = []
    line_cap = config.get("line_cap")
    if not _is_int(line_cap) or line_cap <= 0:
        failures.append(fail(f"oversized_source_files.line_cap must be a positive integer; got {line_cap!r}"))
    allowlist_path = config.get("allowlist_path")
    if not _is_str(allowlist_path) or not allowlist_path:
        failures.append(
            fail(f"oversized_source_files.allowlist_path must be a non-empty string; got {allowlist_path!r}")
        )
    scope_roots = config.get("scope_roots")
    if not _str_list_ok(scope_roots, allow_empty=False):
        failures.append(fail("oversized_source_files.scope_roots must be a non-empty list of strings"))
    file_extensions = config.get("file_extensions")
    if not _str_list_ok(file_extensions, allow_empty=False):
        failures.append(fail("oversized_source_files.file_extensions must be a non-empty list of strings"))
    excluded = config.get("excluded_path_prefixes", [])
    if excluded is None:
        excluded = []
    if not _str_list_ok(excluded, allow_empty=True):
        failures.append(fail("oversized_source_files.excluded_path_prefixes must be a list of strings"))

    if failures:
        return None, failures
    return (
        {
            "line_cap": line_cap,
            "allowlist_path": allowlist_path,
            "scope_roots": tuple(scope_roots),
            "file_extensions": tuple(file_extensions),
            "excluded_path_prefixes": tuple(excluded),
        },
        [],
    )


def _validate_layering_rules(rules: object) -> tuple[list[dict], list[PolicyFailure]]:
    """Validate the ``layering_rules`` list. Returns ``(rules, failures)``;
    on any malformation ``failures`` is populated and ``rules`` is empty.
    Per ADR-015 at least one layering rule is required — an absent or empty
    list is a malformation, not an opt-out."""
    fail = lambda msg: PolicyFailure("policy-config-malformed", msg, _POLICY_CONFIG_PATH)  # noqa: E731
    if rules is None:
        return [], [fail("layering_rules is required (ADR-015) but is absent")]
    if not isinstance(rules, list):
        return [], [fail(f"layering_rules must be a list; got {type(rules).__name__}")]
    if not rules:
        return [], [fail("layering_rules must contain at least one rule (ADR-015)")]

    failures: list[PolicyFailure] = []
    validated: list[dict] = []
    seen_ids: set[str] = set()
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            failures.append(fail(f"layering_rules[{index}] must be a mapping; got {type(rule).__name__}"))
            continue
        rule_id = rule.get("id")
        scope_root = rule.get("scope_root")
        forbidden = rule.get("forbidden_top_level")
        ok = True
        if not _is_str(rule_id) or not rule_id:
            failures.append(fail(f"layering_rules[{index}].id must be a non-empty string; got {rule_id!r}"))
            ok = False
        elif rule_id in seen_ids:
            failures.append(fail(f"layering_rules[{index}].id '{rule_id}' is duplicated"))
            ok = False
        if not _is_str(scope_root) or not scope_root:
            failures.append(fail(f"layering_rules[{index}].scope_root must be a non-empty string; got {scope_root!r}"))
            ok = False
        if not _is_str(forbidden) or not forbidden:
            failures.append(
                fail(f"layering_rules[{index}].forbidden_top_level must be a non-empty string; got {forbidden!r}")
            )
            ok = False
        if ok:
            seen_ids.add(rule_id)
            validated.append(
                {
                    "id": rule_id,
                    "scope_root": scope_root,
                    "forbidden_top_level": forbidden,
                }
            )
    if failures:
        return [], failures
    return validated, []


def _validate_allowlist(repo_root: Path, allowlist_path: str) -> tuple[frozenset[str] | None, list[PolicyFailure]]:
    """Read and validate the allowlist YAML at ``allowlist_path``. Returns
    ``(files, failures)``; ``files`` is None on a missing/malformed/unsafe
    file. ``allowlist_path`` comes from PR-controlled config, so it is
    validated to stay inside the repo before any I/O, and a parse error
    does not echo the file's content into the failure message."""
    fail = lambda msg: PolicyFailure("policy-config-malformed", msg, allowlist_path)  # noqa: E731
    safe = _safe_repo_path(repo_root, allowlist_path)
    if safe is None:
        return None, [
            PolicyFailure(
                "policy-path-unsafe",
                (
                    f"oversized_source_files.allowlist_path '{allowlist_path}' is not a safe "
                    "repo-relative path (absolute, parent-traversal, or resolves outside the repo)"
                ),
                _POLICY_CONFIG_PATH,
            )
        ]
    if not safe.is_file():
        return None, [fail(f"{allowlist_path} is missing or is not a regular file")]
    try:
        data = load_yaml(safe)
    except Exception:  # noqa: BLE001 — yaml.YAMLError + anything load_yaml raises; do not echo content
        return None, [fail(f"{allowlist_path} could not be parsed (invalid YAML)")]
    if not isinstance(data, dict):
        return None, [fail(f"{allowlist_path} root must be a YAML mapping; got {type(data).__name__}")]
    files = data.get("files", [])
    if files is None:
        files = []
    if not _str_list_ok(files, allow_empty=True):
        return None, [fail(f"{allowlist_path} 'files' must be a list of repo-relative path strings")]
    return frozenset(files), []


def _check_layering_and_oversized(repo_root: Path, policy: dict, changed: list[str]) -> list[PolicyFailure]:
    layering_rules, layering_errs = _validate_layering_rules(policy.get("layering_rules"))
    oversized_cfg, oversized_errs = _validate_oversized_config(policy.get("oversized_source_files"))
    config_errs = layering_errs + oversized_errs
    if config_errs:
        # No point checking against malformed config.
        return config_errs
    assert oversized_cfg is not None  # validator returned no errors

    failures: list[PolicyFailure] = []
    failures.extend(_check_layering(repo_root, layering_rules, changed))
    allowlist, allowlist_errs = _validate_allowlist(repo_root, oversized_cfg["allowlist_path"])
    if allowlist_errs:
        return [*failures, *allowlist_errs]
    assert allowlist is not None
    failures.extend(_check_oversized(repo_root, oversized_cfg, allowlist, changed))
    failures.extend(_check_drain(allowlist, oversized_cfg["allowlist_path"]))
    failures.extend(_check_oversized_debt_consistency(repo_root, oversized_cfg, allowlist))
    return failures


def _check_oversized_debt_consistency(repo_root: Path, config: dict, allowlist: frozenset[str]) -> list[PolicyFailure]:
    """Reconcile every ADR-015 initial-oversized path against the allowlist
    and the file on disk. This is a config-wide check (it does not look at
    the changed set) because both relevant mutations — splitting the file
    (which deletes the original) and draining the allowlist entry — can be
    invisible to a changed-paths helper that excludes deletions.

    For each path in ``_ADR015_INITIAL_OVERSIZED_FILES``:

    - If it is still allow-listed, it must resolve to a regular repo file
      that is still over the cap. A file that has been split/shrunk/deleted
      but left in the allowlist is a stale entry (``oversized-allowlist-
      stale-entry``); one replaced by an out-of-tree symlink is
      ``policy-path-unsafe``.
    - If it has been removed from the allowlist (i.e. claimed "drained"),
      the file must actually have been split: it may not still be a regular
      repo file over the cap. If it is, that is a premature drain
      (``oversized-source-file``) — the allowlist shrank without the work
      being done.
    """
    line_cap = config["line_cap"]
    allowlist_path = config["allowlist_path"]
    failures: list[PolicyFailure] = []
    for path in sorted(_ADR015_INITIAL_OVERSIZED_FILES):
        safe = _safe_repo_path(repo_root, path)
        allow_listed = path in allowlist
        if safe is None:
            if allow_listed:
                failures.append(
                    PolicyFailure(
                        "policy-path-unsafe",
                        (
                            f"allowlist entry '{path}' resolves outside the repository root "
                            "(replaced with a symlink?); remove the allowlist entry"
                        ),
                        allowlist_path,
                    )
                )
            continue
        line_count = _file_line_count(safe)
        if allow_listed:
            if line_count is None:
                failures.append(
                    PolicyFailure(
                        "oversized-allowlist-stale-entry",
                        (
                            f"'{path}' is in {allowlist_path} but no regular file exists at that path "
                            "(split or deleted?); remove the allowlist entry"
                        ),
                        allowlist_path,
                    )
                )
            elif line_count <= line_cap:
                failures.append(
                    PolicyFailure(
                        "oversized-allowlist-stale-entry",
                        (
                            f"'{path}' is in {allowlist_path} but is now {line_count} lines (≤ {line_cap}); "
                            "remove the allowlist entry — it is no longer over-cap debt"
                        ),
                        allowlist_path,
                    )
                )
        else:  # claimed drained — the file must really have been split
            if line_count is not None and line_count > line_cap:
                failures.append(
                    PolicyFailure(
                        "oversized-source-file",
                        (
                            f"'{path}' was removed from {allowlist_path} but is still {line_count} lines, "
                            f"over the {line_cap}-line cap — the allowlist may only shrink once the file has "
                            "actually been split; either split it below the cap or restore the allowlist entry"
                        ),
                        path,
                    )
                )
    return failures


def _file_line_count(path: Path) -> int | None:
    """Line count of ``path``, or None if it is not a readable regular file."""
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return None


def _check_layering(repo_root: Path, layering_rules: list[dict], changed: list[str]) -> list[PolicyFailure]:
    """For each layering rule, walk the AST of every changed ``.py`` file
    under ``scope_root`` and reject any ``import <forbidden>[…]`` or
    ``from <forbidden>[…] import …`` statement. ``changed`` has already
    been filtered to in-repo paths by ``evaluate_repo_policy``."""
    failures: list[PolicyFailure] = []
    for rule in layering_rules:
        scope_root = rule["scope_root"]
        forbidden = rule["forbidden_top_level"]
        forbidden_dotted = forbidden + "."
        message = f"{scope_root} must not import {forbidden} (rule: {rule['id']})"
        for rel_path in changed:
            if not rel_path.endswith(".py") or not path_matches_prefix(rel_path, scope_root):
                continue
            path = repo_root / rel_path
            if not path.is_file():
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.name
                        if name == forbidden or name.startswith(forbidden_dotted):
                            failures.append(PolicyFailure("layering-rule-violation", message, rel_path))
                elif isinstance(node, ast.ImportFrom):
                    module = node.module
                    if module and (module == forbidden or module.startswith(forbidden_dotted)):
                        failures.append(PolicyFailure("layering-rule-violation", message, rel_path))
    return failures


def _check_oversized(
    repo_root: Path, config: dict, allowlist: frozenset[str], changed: list[str]
) -> list[PolicyFailure]:
    """Reject any changed file under ``scope_roots`` (and not under an
    ``excluded_path_prefixes`` entry, and matching ``file_extensions``)
    that exceeds ``line_cap`` lines and is not in the allowlist.

    The ADR-015 initial-oversized paths are NOT checked here even when
    changed — they are reconciled config-wide by
    ``_check_oversized_debt_consistency`` (which owns both the
    "still allow-listed and over cap" and "drained but not split" cases),
    so this checker only catches *new* over-cap files.

    ``changed`` has already been filtered to in-repo paths by
    ``evaluate_repo_policy``."""
    line_cap = config["line_cap"]
    scope_roots = config["scope_roots"]
    excluded = config["excluded_path_prefixes"]
    extensions = config["file_extensions"]
    allowlist_path = config["allowlist_path"]
    failures: list[PolicyFailure] = []
    for rel_path in changed:
        if extensions and not rel_path.endswith(tuple(extensions)):
            continue
        if not any(path_matches_prefix(rel_path, root) for root in scope_roots):
            continue
        if any(path_matches_prefix(rel_path, prefix) for prefix in excluded):
            continue
        if rel_path in allowlist or rel_path in _ADR015_INITIAL_OVERSIZED_FILES:
            continue
        line_count = _file_line_count(repo_root / rel_path)
        if line_count is None:
            continue
        if line_count > line_cap:
            failures.append(
                PolicyFailure(
                    "oversized-source-file",
                    (
                        f"file is {line_count} lines, exceeding the {line_cap}-line cap; "
                        f"split it into subdomain modules (do not add it to {allowlist_path}; "
                        "the allowlist only shrinks)"
                    ),
                    rel_path,
                )
            )
    return failures


def _check_drain(allowlist: frozenset[str], allowlist_path: str) -> list[PolicyFailure]:
    """The allowlist must be a subset of ``_ADR015_INITIAL_OVERSIZED_FILES``
    (a code constant, not config). Entries can be removed (the drain
    mechanism) but not added — a file over the cap that wasn't one of the
    initial oversized files must be split, not allow-listed."""
    return [
        PolicyFailure(
            "oversized-allowlist-locked",
            (
                f"'{path}' is in {allowlist_path} but is not one of the files that were over the "
                "600-line cap when ADR-015 landed (_ADR015_INITIAL_OVERSIZED_FILES in "
                "tools/policy/repo_policy.py); the allowlist may only shrink — split the file instead of adding it"
            ),
            allowlist_path,
        )
        for path in sorted(allowlist - _ADR015_INITIAL_OVERSIZED_FILES)
    ]


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
README_ROW_RE = re.compile(
    r"^\| \[(\d{3})\]\(([^)]+)\) \| (.+?) \| (.+?) \| (\d{4}-\d{2}-\d{2}) \|$",
    re.MULTILINE,
)


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
        number: (
            Path(link).name,
            title.strip(),
            _normalize_adr_status(status),
            date_value,
        )
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
