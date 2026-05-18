from __future__ import annotations

import shutil
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
import tools.check_generated_schemas as check_generated_schemas
from tools.check_generated_schemas import _extra_published_schema_paths
from tools.check_json_artifacts import collect_validation_targets, should_run_full_validation
from tools.check_schema_publication import validate_schema_publication_manifest
from tools.gitleaks_tool import _checksums_asset_name, _release_asset_name, gitleaks_binary_path
from tools.policy.common import PolicyFailure
from tools.policy.repo_policy import evaluate_repo_policy


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def setup_policy_repo(tmp_path: Path) -> Path:
    policy_dir = tmp_path / "tools" / "policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "tools" / "policy" / "adr_policy.yaml", policy_dir / "adr_policy.yaml")
    # The ADR-015 size-cap gate reads tools/policy/oversized_allowlist.yaml;
    # seed an empty allowlist by default so tests that don't exercise the
    # allowlist don't trip the missing-config failure. Tests that target
    # allowlist behavior overwrite this file.
    write_text(policy_dir / "oversized_allowlist.yaml", "files: []\n")

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


# ── ADR-015: SDL→processor layering rule ────────────────────────────────


def _aces_sdl_file(repo_root: Path, name: str, content: str) -> str:
    """Write a synthetic file under aces_sdl/ and return its repo-relative path."""
    rel = f"implementations/python/packages/aces_sdl/{name}"
    write_text(repo_root / rel, content)
    return rel


@pytest.mark.parametrize(
    "import_line",
    [
        "import aces_processor",
        "import aces_processor.compiler",
        "from aces_processor import compiler",
        "from aces_processor.compiler import compile_runtime_model",
    ],
)
def test_layering_rule_rejects_aces_processor_imports(tmp_path: Path, import_line: str) -> None:
    repo_root = setup_policy_repo(tmp_path)
    rel = _aces_sdl_file(repo_root, "_uses_processor.py", import_line + "\n")

    failures = evaluate_repo_policy(repo_root, [rel], check_set="file-local", structural_runner=structural_runner_stub)

    assert [f.rule_id for f in failures] == ["layering-rule-violation"], (
        f"import line {import_line!r} should fire layering-rule-violation; got {[f.rule_id for f in failures]}"
    )


def test_layering_rule_does_not_match_prefix_only_package(tmp_path: Path) -> None:
    """A package merely starting with `aces_processor` (e.g. a
    hypothetical `aces_processor_extra`) is not the forbidden package."""
    repo_root = setup_policy_repo(tmp_path)
    rel = _aces_sdl_file(repo_root, "_uses_other.py", "from aces_processor_extra import thing\n")

    failures = evaluate_repo_policy(repo_root, [rel], check_set="file-local", structural_runner=structural_runner_stub)

    assert failures == []


def test_layering_rule_allows_aces_sdl_importing_other_packages(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    rel = _aces_sdl_file(
        repo_root,
        "_normal.py",
        "from aces_contracts.contracts import Scenario\nfrom aces_sdl.semantics.objectives import analyze_objective_window\n",
    )

    failures = evaluate_repo_policy(repo_root, [rel], check_set="file-local", structural_runner=structural_runner_stub)

    assert failures == []


def test_layering_rule_does_not_check_files_outside_scope(tmp_path: Path) -> None:
    """An `import aces_processor` inside aces_processor itself (or any
    package other than aces_sdl) is not a layering violation."""
    repo_root = setup_policy_repo(tmp_path)
    rel = "implementations/python/packages/aces_processor/internal.py"
    write_text(repo_root / rel, "import aces_processor.models\n")

    failures = evaluate_repo_policy(repo_root, [rel], check_set="file-local", structural_runner=structural_runner_stub)

    assert failures == []


# ── ADR-015: 600-line source-file cap ───────────────────────────────────

# A path that is in _ADR015_INITIAL_OVERSIZED_FILES (the code constant in
# tools/policy/repo_policy.py), so the allowlist-subset (drain) check passes
# when we put it in the allowlist.
_LOCKED_PATH = "implementations/python/packages/aces_processor/models.py"


def test_oversized_source_file_over_cap_is_rejected(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    rel = "implementations/python/packages/aces_processor/big_new_file.py"
    write_text(repo_root / rel, "x = 1\n" * 700)

    failures = evaluate_repo_policy(repo_root, [rel], check_set="file-local", structural_runner=structural_runner_stub)

    assert [f.rule_id for f in failures] == ["oversized-source-file"]


def test_oversized_source_file_in_allowlist_passes(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    write_text(repo_root / "tools" / "policy" / "oversized_allowlist.yaml", f"files:\n  - {_LOCKED_PATH}\n")
    write_text(repo_root / _LOCKED_PATH, "x = 1\n" * 700)

    failures = evaluate_repo_policy(
        repo_root, [_LOCKED_PATH], check_set="file-local", structural_runner=structural_runner_stub
    )

    assert failures == []


def test_oversized_source_file_under_cap_passes(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    rel = "implementations/python/packages/aces_processor/small.py"
    write_text(repo_root / rel, "x = 1\n" * 100)

    failures = evaluate_repo_policy(repo_root, [rel], check_set="file-local", structural_runner=structural_runner_stub)

    assert failures == []


def test_oversized_cap_excludes_test_files(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    rel = "implementations/python/tests/test_huge.py"
    write_text(repo_root / rel, "x = 1\n" * 700)

    failures = evaluate_repo_policy(repo_root, [rel], check_set="file-local", structural_runner=structural_runner_stub)

    assert failures == []


def test_oversized_cap_only_checks_python_files(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    rel = "implementations/python/packages/aces_processor/data.txt"
    write_text(repo_root / rel, "line\n" * 700)

    failures = evaluate_repo_policy(repo_root, [rel], check_set="file-local", structural_runner=structural_runner_stub)

    assert failures == []


# ── ADR-015: allowlist drain (must be a subset of the code constant) ────


def test_allowlist_entry_not_in_locked_set_is_rejected(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    bogus = "implementations/python/packages/aces_processor/not_a_locked_file.py"
    write_text(repo_root / "tools" / "policy" / "oversized_allowlist.yaml", f"files:\n  - {bogus}\n")

    failures = evaluate_repo_policy(
        repo_root,
        ["tools/policy/oversized_allowlist.yaml"],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert [f.rule_id for f in failures] == ["oversized-allowlist-locked"]


def test_allowlist_subset_of_locked_set_passes(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    # A strict subset of the 14 initial oversized entries — the drained state.
    write_text(repo_root / "tools" / "policy" / "oversized_allowlist.yaml", f"files:\n  - {_LOCKED_PATH}\n")
    write_text(repo_root / _LOCKED_PATH, "x = 1\n" * 700)

    failures = evaluate_repo_policy(
        repo_root,
        ["tools/policy/oversized_allowlist.yaml"],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert failures == []


def test_growing_locked_set_via_config_does_not_relax_drain_check(tmp_path: Path) -> None:
    """The drain check diffs against the *code* constant, not config. Adding
    a new oversized file to the allowlist (and even re-introducing a
    `locked_initial_files` block in adr_policy.yaml) must not make it pass —
    the locked reference set is not config the same PR can edit."""
    repo_root = setup_policy_repo(tmp_path)
    sneaky = "implementations/python/packages/aces_processor/sneaky_new_big_file.py"
    write_text(repo_root / "tools" / "policy" / "oversized_allowlist.yaml", f"files:\n  - {sneaky}\n")
    write_text(repo_root / sneaky, "x = 1\n" * 700)
    # Re-add a config-level locked_initial_files block listing the sneaky file.
    config = (repo_root / "tools" / "policy" / "adr_policy.yaml").read_text()
    config += f"  locked_initial_files:\n    - {sneaky}\n"
    write_text(repo_root / "tools" / "policy" / "adr_policy.yaml", config)

    failures = evaluate_repo_policy(
        repo_root,
        ["tools/policy/oversized_allowlist.yaml", sneaky],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert "oversized-allowlist-locked" in [f.rule_id for f in failures], [f.message for f in failures]


def test_unsafe_locked_allowlist_entry_is_rejected(tmp_path: Path) -> None:
    """An allowlisted (and locked) path that has been replaced by a symlink
    pointing out of the tree is reported as policy-path-unsafe rather than
    silently accepted as still-over-cap debt."""
    repo_root = setup_policy_repo(tmp_path)
    write_text(repo_root / "tools" / "policy" / "oversized_allowlist.yaml", f"files:\n  - {_LOCKED_PATH}\n")
    outside = tmp_path.parent / "outside_big.py"
    write_text(outside, "x = 1\n" * 700)
    target = repo_root / _LOCKED_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(outside)

    failures = evaluate_repo_policy(
        repo_root,
        ["docs/decisions/adrs/adr-001-example.md"],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert "policy-path-unsafe" in [f.rule_id for f in failures], [f.message for f in failures]


# ── ADR-015: schema validation (malformed config → structured failure) ──


@pytest.mark.parametrize(
    ("mutation", "marker"),
    [
        ('oversized_source_files:\n  line_cap: "nope"\n', "line_cap"),
        ("oversized_source_files: notamapping\n", "must be a mapping"),
        ("layering_rules: notalist\n", "layering_rules must be a list"),
        ("layering_rules:\n  - {}\n", "layering_rules[0].id"),
    ],
)
def test_malformed_policy_config_produces_structured_failure(tmp_path: Path, mutation: str, marker: str) -> None:
    repo_root = setup_policy_repo(tmp_path)
    # Replace the whole adr_policy.yaml with a minimal-but-malformed config.
    # Keep the keys other parts of the policy need (compatibility_layer,
    # adr_index, source_roots, generated_contracts, concept_authority) by
    # appending the mutation onto the real config.
    base = (REPO_ROOT / "tools" / "policy" / "adr_policy.yaml").read_text()
    # Drop the real layering_rules / oversized_source_files blocks so the
    # mutation is what gets validated. Cheap approach: only the mutation
    # blocks matter; strip from the first occurrence of "layering_rules:".
    cut = base.split("\nlayering_rules:", 1)[0]
    write_text(repo_root / "tools" / "policy" / "adr_policy.yaml", cut + "\n" + mutation)

    failures = evaluate_repo_policy(
        repo_root,
        ["tools/policy/adr_policy.yaml"],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    rule_ids = [f.rule_id for f in failures]
    assert "policy-config-malformed" in rule_ids, f"expected policy-config-malformed, got {rule_ids}"
    assert any(marker in f.message for f in failures if f.rule_id == "policy-config-malformed"), (
        f"expected a failure mentioning {marker!r}; got {[f.message for f in failures]}"
    )


def test_missing_allowlist_file_produces_structured_failure(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    (repo_root / "tools" / "policy" / "oversized_allowlist.yaml").unlink()

    failures = evaluate_repo_policy(
        repo_root,
        ["docs/decisions/adrs/adr-001-example.md"],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    rule_ids = [f.rule_id for f in failures]
    assert "policy-config-malformed" in rule_ids, f"expected policy-config-malformed, got {rule_ids}"


# ── ADR-015: stale allowlist entry (file no longer over the cap) ─────────


def test_stale_allowlist_entry_below_cap_is_rejected(tmp_path: Path) -> None:
    """An allowlist entry that was split (so the file is now small) but
    whose entry the split PR forgot to drain is flagged on the next run,
    even though the file's deletion/shrink isn't in the changed set."""
    repo_root = setup_policy_repo(tmp_path)
    write_text(repo_root / "tools" / "policy" / "oversized_allowlist.yaml", f"files:\n  - {_LOCKED_PATH}\n")
    write_text(repo_root / _LOCKED_PATH, "x = 1\n" * 100)  # well under the 600-line cap

    failures = evaluate_repo_policy(
        repo_root,
        ["docs/decisions/adrs/adr-001-example.md"],  # unrelated change
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert [f.rule_id for f in failures] == ["oversized-allowlist-stale-entry"]
    assert "100 lines" in failures[0].message


def test_stale_allowlist_entry_missing_file_is_rejected(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    write_text(repo_root / "tools" / "policy" / "oversized_allowlist.yaml", f"files:\n  - {_LOCKED_PATH}\n")
    # _LOCKED_PATH file is never created.

    failures = evaluate_repo_policy(
        repo_root,
        ["docs/decisions/adrs/adr-001-example.md"],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert [f.rule_id for f in failures] == ["oversized-allowlist-stale-entry"]
    assert "no regular file exists" in failures[0].message


def test_allowlist_entry_still_over_cap_passes(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    write_text(repo_root / "tools" / "policy" / "oversized_allowlist.yaml", f"files:\n  - {_LOCKED_PATH}\n")
    write_text(repo_root / _LOCKED_PATH, "x = 1\n" * 700)  # still over the cap → legitimate debt

    failures = evaluate_repo_policy(
        repo_root,
        ["docs/decisions/adrs/adr-001-example.md"],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert failures == []


# ── ADR-015: required blocks + unsafe paths ─────────────────────────────


def _write_policy_without_adr015_blocks(repo_root: Path, *, extra: str = "") -> None:
    """Rewrite adr_policy.yaml dropping the layering_rules and
    oversized_source_files blocks, optionally appending `extra`."""
    base = (REPO_ROOT / "tools" / "policy" / "adr_policy.yaml").read_text()
    cut = base.split("\nlayering_rules:", 1)[0]
    write_text(repo_root / "tools" / "policy" / "adr_policy.yaml", cut + "\n" + extra)


def test_absent_layering_rules_block_is_malformed(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    # Re-add a valid oversized_source_files block so only layering_rules is absent.
    real = (REPO_ROOT / "tools" / "policy" / "adr_policy.yaml").read_text()
    oversized_block = "oversized_source_files:" + real.split("\noversized_source_files:", 1)[1]
    _write_policy_without_adr015_blocks(repo_root, extra=oversized_block)

    failures = evaluate_repo_policy(
        repo_root,
        ["tools/policy/adr_policy.yaml"],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert any(
        f.rule_id == "policy-config-malformed" and "layering_rules is required" in f.message for f in failures
    ), [f.message for f in failures]


def test_absent_oversized_block_is_malformed(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    # Re-add a valid layering_rules block so only oversized_source_files is absent.
    real = (REPO_ROOT / "tools" / "policy" / "adr_policy.yaml").read_text()
    layering_block = "layering_rules:" + real.split("\nlayering_rules:", 1)[1].split("\noversized_source_files:", 1)[0]
    _write_policy_without_adr015_blocks(repo_root, extra=layering_block)

    failures = evaluate_repo_policy(
        repo_root,
        ["tools/policy/adr_policy.yaml"],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert any(
        f.rule_id == "policy-config-malformed" and "oversized_source_files block is required" in f.message
        for f in failures
    ), [f.message for f in failures]


@pytest.mark.parametrize(
    "bad_content",
    [
        "[unclosed flow sequence\n",  # parse error (never-closed flow sequence)
        "- just\n- a\n- list\n",  # parses, but root is a list not a mapping
        "42\n",  # parses to a scalar
    ],
)
def test_unparseable_or_non_mapping_adr_policy_is_malformed(tmp_path: Path, bad_content: str) -> None:
    repo_root = setup_policy_repo(tmp_path)
    write_text(repo_root / "tools" / "policy" / "adr_policy.yaml", bad_content)

    failures = evaluate_repo_policy(
        repo_root,
        ["docs/decisions/adrs/adr-001-example.md"],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert [f.rule_id for f in failures] == ["policy-config-malformed"], [f.message for f in failures]


@pytest.mark.parametrize("bad_path", ["/etc/passwd", "../../../etc/passwd"])
def test_unsafe_allowlist_path_is_rejected(tmp_path: Path, bad_path: str) -> None:
    repo_root = setup_policy_repo(tmp_path)
    config = (repo_root / "tools" / "policy" / "adr_policy.yaml").read_text()
    config = config.replace("allowlist_path: tools/policy/oversized_allowlist.yaml", f"allowlist_path: {bad_path}")
    write_text(repo_root / "tools" / "policy" / "adr_policy.yaml", config)

    failures = evaluate_repo_policy(
        repo_root,
        ["tools/policy/adr_policy.yaml"],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert [f.rule_id for f in failures] == ["policy-path-unsafe"], [f.message for f in failures]


def test_unsafe_changed_path_is_rejected(tmp_path: Path) -> None:
    """A changed path that escapes the repo root (e.g. via a planted
    symlink) is reported as policy-path-unsafe rather than being read."""
    repo_root = setup_policy_repo(tmp_path)
    outside = tmp_path.parent / "outside_secret.py"
    write_text(outside, "import aces_processor\n")
    link_rel = "implementations/python/packages/aces_sdl/_link.py"
    (repo_root / "implementations" / "python" / "packages" / "aces_sdl").mkdir(parents=True, exist_ok=True)
    (repo_root / link_rel).symlink_to(outside)

    failures = evaluate_repo_policy(
        repo_root, [link_rel], check_set="file-local", structural_runner=structural_runner_stub
    )

    assert "policy-path-unsafe" in [f.rule_id for f in failures], [f.message for f in failures]
    assert "layering-rule-violation" not in [f.rule_id for f in failures]


# ── ADR-015: drain requires the file to actually have been split ────────


def test_premature_drain_is_rejected(tmp_path: Path) -> None:
    """Removing an initial oversized file from the allowlist while the file
    itself is unchanged (still over the cap) is a premature drain — the
    debt list shrank without the work being done. Caught config-wide even
    though the (unchanged, undeleted) file is not in the changed set."""
    repo_root = setup_policy_repo(tmp_path)
    # Default allowlist is empty -> _LOCKED_PATH is "claimed drained".
    write_text(repo_root / _LOCKED_PATH, "x = 1\n" * 700)  # but the file is still over cap

    failures = evaluate_repo_policy(
        repo_root,
        ["docs/decisions/adrs/adr-001-example.md"],  # unrelated change
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert [f.rule_id for f in failures] == ["oversized-source-file"], [f.message for f in failures]
    assert "removed from" in failures[0].message and "700" in failures[0].message


def test_legitimate_drain_passes(tmp_path: Path) -> None:
    """An initial oversized file that has been removed from the allowlist
    AND actually split below the cap passes."""
    repo_root = setup_policy_repo(tmp_path)
    write_text(repo_root / _LOCKED_PATH, "x = 1\n" * 120)  # genuinely split below the cap

    failures = evaluate_repo_policy(
        repo_root,
        ["docs/decisions/adrs/adr-001-example.md"],
        check_set="file-local",
        structural_runner=structural_runner_stub,
    )

    assert failures == []


# ── ADR-015: config-wide checks run even when nothing changed ────────────


def test_empty_changed_still_runs_config_wide_adr015_checks(tmp_path: Path) -> None:
    """A deletion-only PR (the repo's changed-paths helper excludes
    deletions) can hand an empty changed list to the policy. The ADR-015
    config-wide invariants must still be evaluated — here, a stale allowlist
    entry is flagged with no changed files at all."""
    repo_root = setup_policy_repo(tmp_path)
    write_text(repo_root / "tools" / "policy" / "oversized_allowlist.yaml", f"files:\n  - {_LOCKED_PATH}\n")
    write_text(repo_root / _LOCKED_PATH, "x = 1\n" * 100)

    failures = evaluate_repo_policy(repo_root, [], check_set="file-local", structural_runner=structural_runner_stub)

    assert [f.rule_id for f in failures] == ["oversized-allowlist-stale-entry"], [f.message for f in failures]


def test_empty_changed_detects_deleted_allowlist_file(tmp_path: Path) -> None:
    repo_root = setup_policy_repo(tmp_path)
    (repo_root / "tools" / "policy" / "oversized_allowlist.yaml").unlink()

    failures = evaluate_repo_policy(repo_root, [], check_set="file-local", structural_runner=structural_runner_stub)

    assert "policy-config-malformed" in [f.rule_id for f in failures], [f.message for f in failures]


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


def write_schema_publication_manifest(repo_root: Path, entries: list[dict[str, str]]) -> None:
    import json

    write_text(
        repo_root / "contracts" / "schema-publication-manifest.json",
        json.dumps({"schema_version": "schema-publication-manifest/v1", "schemas": entries}, indent=2) + "\n",
    )


def test_should_run_full_validation_for_schema_driver_paths() -> None:
    assert should_run_full_validation(["tools/generate_contract_schemas.py"]) is True
    assert should_run_full_validation(["implementations/python/packages/aces_contracts/contracts.py"]) is True
    # aces_sdl supplies the Scenario Pydantic model exposed by schema_bundle();
    # a change there must trigger full schema validation just like aces_contracts.
    assert should_run_full_validation(["implementations/python/packages/aces_sdl/agents.py"]) is True
    assert should_run_full_validation(["contracts/concept-authority/concept-families-v1.json"]) is False


def test_schema_publication_manifest_accepts_complete_current_schema_inventory(tmp_path: Path) -> None:
    repo_root = tmp_path
    write_text(repo_root / "contracts" / "schemas" / "sdl" / "sdl-authoring-input-v1.json", "{}\n")
    write_text(repo_root / "contracts" / "schemas" / "control-plane" / "operation-status-v1.json", "{}\n")
    write_schema_publication_manifest(
        repo_root,
        [
            {
                "contract_id": "operation-status-v1",
                "schema_path": "contracts/schemas/control-plane/operation-status-v1.json",
            },
            {
                "contract_id": "sdl-authoring-input-v1",
                "schema_path": "contracts/schemas/sdl/sdl-authoring-input-v1.json",
            },
        ],
    )

    assert validate_schema_publication_manifest(repo_root) == []


def test_schema_publication_manifest_rejects_missing_published_schema_entry(tmp_path: Path) -> None:
    repo_root = tmp_path
    write_text(repo_root / "contracts" / "schemas" / "sdl" / "sdl-authoring-input-v1.json", "{}\n")
    write_text(repo_root / "contracts" / "schemas" / "control-plane" / "operation-status-v1.json", "{}\n")
    write_schema_publication_manifest(
        repo_root,
        [
            {
                "contract_id": "sdl-authoring-input-v1",
                "schema_path": "contracts/schemas/sdl/sdl-authoring-input-v1.json",
            },
        ],
    )

    assert validate_schema_publication_manifest(repo_root) == [
        "schema manifest is missing published schema: contracts/schemas/control-plane/operation-status-v1.json"
    ]


def test_schema_publication_manifest_rejects_paths_outside_contract_schemas(tmp_path: Path) -> None:
    repo_root = tmp_path
    write_text(repo_root / "schemas" / "legacy.json", "{}\n")
    write_schema_publication_manifest(
        repo_root,
        [
            {
                "contract_id": "legacy",
                "schema_path": "schemas/legacy.json",
            },
        ],
    )

    assert validate_schema_publication_manifest(repo_root) == [
        "schema manifest path must be under contracts/schemas/: schemas/legacy.json"
    ]


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


def test_gitleaks_release_asset_names_match_platform_conventions(monkeypatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("platform.machine", lambda: "x86_64")

    assert _release_asset_name("8.30.1") == "gitleaks_8.30.1_linux_x64.tar.gz"
    assert _checksums_asset_name("8.30.1") == "gitleaks_8.30.1_checksums.txt"


def test_gitleaks_binary_path_uses_repo_local_cache(tmp_path: Path) -> None:
    assert gitleaks_binary_path(tmp_path, version="8.30.1") == (
        tmp_path / ".cache" / "aces-sdl" / "tooling" / "gitleaks" / "8.30.1" / "gitleaks"
    )


def test_extra_published_schema_paths_detects_stale_generated_files(tmp_path: Path) -> None:
    schemas_root = tmp_path / "contracts" / "schemas"
    write_text(schemas_root / "backend-manifest" / "backend-manifest-v2.json", "{}\n")
    write_text(schemas_root / "backend-manifest" / "backend-manifest-v1.json", "{}\n")

    assert _extra_published_schema_paths(
        schemas_root,
        expected_relative_paths={"backend-manifest/backend-manifest-v2.json"},
    ) == ["backend-manifest/backend-manifest-v1.json"]


def test_check_generated_schemas_main_rejects_stale_extra_schema_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path
    schemas_root = repo_root / "contracts" / "schemas"
    write_text(schemas_root / "backend-manifest" / "backend-manifest-v2.json", "{}\n")
    write_text(schemas_root / "backend-manifest" / "backend-manifest-v1.json", "{}\n")

    fake_generator = types.ModuleType("tools.generate_contract_schemas")
    fake_generator.main = lambda: None
    fake_generator._schema_output_path = lambda root, name: root / "backend-manifest" / f"{name}.json"
    fake_contracts = types.ModuleType("aces_contracts.contracts")
    fake_contracts.schema_bundle = lambda: {"backend-manifest-v2": {}}
    fake_package = types.ModuleType("aces_contracts")
    fake_package.contracts = fake_contracts

    monkeypatch.setattr(check_generated_schemas, "REPO_ROOT", repo_root)
    monkeypatch.setattr(check_generated_schemas, "SCHEMAS_ROOT", schemas_root)
    monkeypatch.setattr(check_generated_schemas, "PYTHON_ROOT", repo_root / "implementations" / "python")
    monkeypatch.setattr(sys, "argv", ["check_generated_schemas.py"])
    monkeypatch.setitem(sys.modules, "tools.generate_contract_schemas", fake_generator)
    monkeypatch.setitem(sys.modules, "aces_contracts", fake_package)
    monkeypatch.setitem(sys.modules, "aces_contracts.contracts", fake_contracts)

    assert check_generated_schemas.main() == 1
