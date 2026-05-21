# ADR-024: Local Identity Inventory Surface

## Status

accepted

## Date

2026-05-21

## Context

Issue #365 requires SDL parity for local identity facts observed inside a Linux
asset: `/etc/passwd`, `/etc/group`, sudo/sudoers command scope, and provenance
or stability distinctions such as image-defined versus runtime-created
accounts.

The repository already has two adjacent surfaces:

- top-level `accounts`, which are scenario/provisioning account resources and
  participant-reference targets
- `Node.runtime`, which carries observed runtime facts such as filesystem
  inventory, process identity, environment, Linux capabilities, container
  settings, packages, and health

Putting every observed system account into top-level `accounts` would make
service accounts such as `www-data`, `messagebus`, or `Debian-exim` look like
desired provisioned scenario accounts and backend account-placement work. Hiding
the same facts in untyped runtime dictionaries would lose schema, validation,
and generated contract coverage.

## Decision

### 1. Model full local identity inventory under node runtime

Complete local identity database observations belong in a typed nested runtime
inventory on `Node.runtime`, not in new top-level SDL sections.

The runtime identity surface should cover:

- local user records: username, UID, primary GID, primary group name,
  GECOS/comment, home, shell, disabled/locked/no-login facts, supplemental
  groups, provenance, and stability
- local group records: group name, GID, and members
- sudo/sudoers entries: principal kind, principal name, run-as scope,
  command scope, and no-password/authentication flags where observed

The field should be node-scoped because `/etc/passwd`, `/etc/group`, and
sudoers are local asset facts. Record-level uniqueness should be validated by
the natural local keys: username for users, GID/name for groups, and principal
plus command scope for sudo entries.

### 2. Preserve top-level `accounts` semantics

Top-level `accounts` remain the curated scenario account/provisioning surface.
They should be extended only for account facts that intentionally participate in
that surface. The full runtime inventory must not implicitly compile each local
runtime user into an `AccountPlacement`.

If the implementation adds UID/GID/login-state fields to `Account`, planner
feature detection must extend the existing `_account_features()` path and the
`provisioner-account-features` controlled vocabulary. Runtime-only inventory
facts should not be added to provisioning capability terms unless a backend is
expected to provision them.

### 3. Reuse existing SDL gates

The implementation must reuse:

- `SDLModel` closed-world Pydantic validation
- shared parse helpers such as `parse_int_or_var()`, `parse_bool_or_var()`,
  `parse_runtime_enum_or_var()`, `absolute_path_or_var()`, and
  `coerce_string_list()`
- parser key normalization, hashmap-key preservation, `source` shorthand
  rules, and variable-placeholder key rejection
- `SemanticValidator` and `SDLValidationError` for cross-node and OS-family
  checks
- `instantiate_scenario()` and `SDLInstantiationError` for substitution and
  concrete revalidation
- `schema_bundle()`, `tools/generate_contract_schemas.py`, and
  `tools/check_generated_schemas.py`; generated schemas under
  `contracts/schemas/` must not be edited directly

No new parser, schema registry, exception hierarchy, logging stack, or
persistence mechanism is justified for this issue.

### 4. Keep identity states explicit

Disabled, locked, and no-login are different facts. Do not infer all of them
from `shell`, and do not collapse them into a single overloaded boolean. The
existing `disabled` field may remain as backward-compatible scenario-account
state, but observed local inventory must preserve explicit locked/no-login
status when known.

### 5. Treat sudo scope as structured policy, not raw file text

Sudo/sudoers support should model the portable command scope and principal
scope directly. Raw sudoers lines may be retained only as optional descriptive
evidence with redaction controls; they must not be the primary portable model.

Command scopes can contain sensitive arguments. The surface must provide a
redacted representation path and must not write secrets, credentials, bearer
tokens, raw shadow hashes, or full backend-native parser output into SDL
examples, diagnostics, generated fixtures, logs, snapshots, or operation
metadata.

### 6. Keep the extensibility seam node-scoped

The extension seam is the node-scoped runtime local identity inventory. Future
variants such as POSIX ACLs, Linux capabilities attached to files, PAM policy,
shadow metadata, Windows SAM/local groups, or directory-service projections
should add typed submodels under the appropriate runtime or account boundary
instead of creating another identity database section.

## Guardrails

- Do not add `local_groups`, `sudoers`, or similar as new top-level SDL
  sections for this issue.
- Do not duplicate local group schema in both account fields and runtime
  inventory. Account supplemental groups are memberships; local group records
  are node-local database rows.
- Do not make `Account.groups` carry GIDs, member lists, or `/etc/group` row
  metadata.
- Do not equate a no-login shell with a locked password or disabled account.
- Do not require every observed service account to be targetable by agents.
  Promote only intentionally referenced accounts into top-level `accounts`.
- Do not place raw `/etc/shadow` hashes, sudo credentials, or secret command
  arguments into examples, contract fixtures, diagnostics, or runtime
  snapshots.
- Avoid nested field names called `source` unless parser shorthand skip rules
  are updated for that scope.
- If runtime identity records use mapping keys, update the parser's nested
  hashmap preservation list; if they use lists, validate duplicates in the
  runtime model.
- Keep the inventory inside the governed concept taxonomy. The runtime local
  identity inventory is node-scoped runtime state, so it is covered by the
  existing `scenario-node` reference model (concept family `assets`); the
  shared reference-model catalog binds only top-level scenario sections, so no
  new catalog entry is added. The guardrail is to avoid an orphan identity
  surface outside the taxonomy, not to force a catalog row the binding
  validator cannot resolve.

## Non-Goals

- Implementing issue #365.
- Updating `examples/scenarios/techvault.sdl.yaml`.
- Building an OS user/group discovery tool.
- Parsing host `/etc/passwd`, `/etc/group`, `/etc/shadow`, or sudoers files.
- Defining backend provisioning behavior for every observed runtime account.
- Adding Windows domain, LDAP, Active Directory, PAM, or NSS semantics beyond
  the local identity database expressivity required here.

## Consequences

### Positive

- Observed local identity facts stay distinguishable from desired account
  provisioning resources.
- Existing SDL parsing, validation, instantiation, schema generation, concept
  authority, and planner capability gates remain authoritative.
- TechVault parity can represent container-visible service accounts and group
  rows without pretending every row is participant-facing.

### Negative

- Some scenarios may intentionally carry both a top-level account and a runtime
  local user record for the same username. That duplication is acceptable only
  because the meanings differ.
- Backends that provision accounts and tools that inspect runtime inventory may
  need separate support paths.

### Risks

- Extending only top-level `accounts` would conflate observed inventory with
  desired provisioning.
- Adding a free-form runtime identity dictionary would bypass generated schema
  and validation guarantees.
- Treating sudoers as raw text could leak command secrets and leave downstream
  consumers without a portable command-scope model.
