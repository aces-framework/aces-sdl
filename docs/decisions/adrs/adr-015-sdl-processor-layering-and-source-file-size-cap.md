# ADR-015: SDL-Processor Layering and Source-File Size Cap

## Status

accepted

## Date

2026-05-10

## Context

Two structural problems in the `aces-sdl` Python tree, surfaced by the
modularity audit ([issue #3](https://github.com/aces-framework/aces-sdl/issues/3)):

1. **Circular dependency.** `aces_sdl/validator.py` imported
   `analyze_objective_window` and workflow helpers from
   `aces_processor.semantics.{objectives,workflow}`, while
   `aces_processor/{compiler,manager,planner,models}.py` imported runtime
   types and helpers from `aces_sdl.{instantiate,scenario,nodes,_base,
   infrastructure,entities,orchestration}`. Conceptually the SDL defines
   the language; the processor compiles and runs it. The dependency must
   be one-way (processor → SDL), but imports ran both directions.

2. **Oversized modules.** Fourteen non-test, non-generated source files
   under `implementations/python/packages/` exceeded 600 lines, four of
   them by 50–270%. These files attract further growth and mix multiple
   subdomains. Splitting them is tracked by the 14 child issues of #3,
   but the splits need an enforced cap to keep working: a file dropped
   below 600 lines that can silently grow back has not been split, just
   shuffled.

Neither is enforceable by reviewer attention alone. Both need structural
CI gates.

## Decision

### 1. SDL-processor layering

`aces_sdl` shall not import `aces_processor` — directly or via the
`aces_processor.semantics.*` re-export path.

The cycle is broken by relocating the two SDL-language modules
`objectives.py` and `workflow.py` from `aces_processor/semantics/` to
`aces_sdl/semantics/`. Their contents — objective-window analysis, the
workflow step-type contract and `branch_closure`, and a pure workflow
step-result validator — are SDL-language semantics; they import only the
standard library and have no import-time coupling to `aces_processor`;
`aces_sdl/validator.py` is their primary consumer. Each module moves as a
unit. In particular `validate_workflow_step_result` (which checks a
backend's *reported* execution state against the step-type contract) moves
with the rest of `workflow.py`: it is pure, so moving it does not violate
the layering rule, and keeping the module intact avoids fragmenting the
`aces.core.semantics.workflow` compatibility surface for what would be a
marginal conceptual gain. (A reasonable alternative — pulling that
validator into a processor-owned module — was considered and rejected on
that basis.)

`semantics/planner.py` stays at `aces_processor/semantics/planner.py`.
Although it also has stdlib-only imports, its content — resource-action
reconciliation between compiled resources and runtime snapshots,
dependency-graph construction over compiled-resource addresses,
topological ordering of processor-domain resources — operates on
*compiled resources*, a processor artifact, so it is processor-runtime
logic rather than SDL-language semantics. Moving it would put processor
logic into the SDL package solely to satisfy a "stdlib-only imports"
heuristic, which would not improve the layering.

The owning-package import paths `aces_processor.semantics.{objectives,
workflow}` are removed, not preserved with re-export shims. Per ADR-009
and ADR-010 the *stable* public surface is the `aces.*` namespace, not
the owning packages; the compatibility model is exactly one shim layer
(`aces.*`), and the `aces.core.semantics.{objectives,workflow}` wrappers
retarget to `aces_sdl.semantics.*` so that surface is unchanged.
`aces.core.semantics.planner` continues to target
`aces_processor.semantics.planner` (which did not move). Adding a second
shim layer at the owning-package level would introduce a pattern the
repository does not otherwise use and blur which location is canonical.

Enforcement: a `layering_rules` block in `tools/policy/adr_policy.yaml`
and a `_check_layering` checker in `tools/policy/repo_policy.py`. The
checker walks the AST of every changed `.py` file under each rule's
`scope_root` and emits `layering-rule-violation` for any `import` or
`from … import` of the forbidden top-level package or its submodules.

### 2. 600-line cap on non-test source files

No non-test, non-generated `.py` file under `implementations/python/packages/`
shall exceed 600 lines, except for paths listed in
`tools/policy/oversized_allowlist.yaml`.

The allowlist is the inverse of the goal: each entry is technical debt to
be drained. Each child PR of #3 splits its file and removes the entry.
The tracker closes when the allowlist is empty.

The fixed reference set — the 14 paths over the cap when this ADR landed —
is a *code constant*, `_ADR015_INITIAL_OVERSIZED_FILES` in
`tools/policy/repo_policy.py`, **not** config in `adr_policy.yaml`. Keeping
the locked set in PR-editable config would let one PR satisfy "the allowlist
only shrinks" by editing the allowlist and the locked set together; pinning
it in the policy module means adding a 15th entry requires a diff to the
checker code, which PR review scrutinises as policy rather than as data
noise. The allowlist must be a subset of that constant — no new entry may be
added; a file over the cap that wasn't one of the initial set must be split,
not allow-listed. Enforcement:

- `_check_oversized` — emits `oversized-source-file` for an over-cap,
  non-allowlisted changed file.
- `_check_drain` — emits `oversized-allowlist-locked` for an allowlist
  entry not in `_ADR015_INITIAL_OVERSIZED_FILES` (the allowlist may only
  shrink).
- `_check_allowlist_entries_still_oversized` — emits
  `oversized-allowlist-stale-entry` for an allowlist entry (one of the
  initial set) that no longer resolves to a regular file over the cap. A
  split PR deletes the original file, so `git diff` never lists it as
  "changed"; without this config-wide check a forgotten drain would leave
  the path permanently exempt and free to grow back. This is the
  structural gate that makes the drain step non-optional.

The `layering_rules` and `oversized_source_files` blocks are *required*
policy: an absent block surfaces as `policy-config-malformed`, not as a
silent opt-out, so neither gate can be disabled by deleting config.
Malformed config surfaces the same way rather than as a traceback — this
covers `adr_policy.yaml` itself failing to parse or not having a mapping
root (`evaluate_repo_policy` loads it through a guard before any checker
runs), wrong types or empty required lists inside the ADR-015 blocks, and
an unparseable or non-mapping allowlist YAML. Path
safety is enforced at a single chokepoint: `evaluate_repo_policy` runs
every path in the PR's changed-file list through an in-repo-resolution
check and drops any that escape the root *before any checker reads a
file*, so the layering scan, the size cap, and the pre-existing
import-direction and compat-wrapper checks all receive an
already-validated list. The allowlist file path
(`oversized_source_files.allowlist_path`) and each allowlist entry
inspected by the drain check are validated the same way. An absolute
path, a `..` segment, or a symlink resolving outside the tree surfaces as
`policy-path-unsafe` and the target is never opened. (This is
defense-in-depth for the in-repo trust model below, not a claim to
withstand an adversarial author who edits the policy itself.)

Test files under `implementations/python/tests/` and generated files
under `contracts/schemas/` are excluded from the cap — tests grow as a
function of the surface they cover, and generated files are not authored.

### Trust model

These gates catch unintentional regressions in normal source-code
contributions: a developer who accidentally types `import aces_processor`
in `aces_sdl/`, or one who pushes a 700-line file, or a split PR that
forgets to drain its allowlist entry. The policy code and its YAML config
are in the repository and are PR-mutable; PR review is responsible for
catching deliberate weakening of the policy itself. Defending against an
adversarial commit author who rewrites `repo_policy.py` is out of scope —
if that level of enforcement is ever required, the right answer is to move
the policy into immutable CI workflow code, not to harden in-repo code
defensively. That would be a separate ADR.

### Out of scope

- Splitting any of the 14 oversized files. Each has its own child issue
  under #3.
- Behavioral changes. The cycle break and policy gates are pure
  refactoring + tooling; semantics, public dataclass shapes, and runtime
  algorithms are unchanged.

## Consequences

### Positive

- The dependency between `aces_sdl` and `aces_processor` is a DAG,
  enforced by CI.
- Each subsequent file split inherits the layering invariant for free.
- The cap creates a forcing function: a file that wants to grow past 600
  lines must justify the split or the allowlist entry.
- The allowlist is self-documenting debt; its size measures remaining
  modularity work.

### Negative

- Fourteen subsequent PRs are needed to drain the allowlist.
- `docs/api/processor-semantics.rst` is rescoped to planner only; a new
  `docs/api/sdl-semantics.rst` documents the moved modules. Bookmarks to
  the processor-semantics page still resolve, to a smaller page.

### Risks

- A new top-level package introduced later (e.g. `aces_runtime`) could
  re-introduce a layering bug the current rule doesn't capture. Mitigation:
  each new package introduction should consider whether it needs its own
  `layering_rules` entry.
- The 600-line cap is conservative; some cohesive modules may hit it. The
  allowlist gives an explicit, visible escape hatch. The cap can be tuned
  later if it proves too aggressive.
