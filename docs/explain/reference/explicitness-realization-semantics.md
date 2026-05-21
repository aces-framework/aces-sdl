# Explicitness And Realization Semantics

This note is the implementer-facing architecture companion to `SEM-218`. It
records the architecture guardrails for the implementation that realizes
the spec; it is implementation guidance, **not normative**. The normative
semantic boundary — including the invariants, the phase responsibilities,
the binding gates, and the realization-status framing — lives in
{download}`specs/formal/realization/explicitness-and-realization.md <../../../specs/formal/realization/explicitness-and-realization.md>`.
Where this note's prose differs from the spec, the spec governs; where
the spec is silent and this note records detail, treat that detail as
implementer reference rather than a binding rule. Realization status is
tracked in the `SEM-200` coverage table in
[`shared-semantic-integrity.md`](shared-semantic-integrity.md); the
realization-and-disclosure concept family in
`contracts/concept-authority/concept-families-v1.json` is the native
authority for what may be realized at all.

`SEM-218` defines the difference between an author declaration that is
binding and a concern left open for backend realization (the normative
statement of those rules lives in the spec linked above). The core
engineering risk is concept conflation: treating "not specified yet",
"backend may choose", "processor must preserve exactly", and
"unsupported exact request" as the same state.

## Architecture Decisions

- Reuse the existing semantic authority stack. Explicitness semantics belong
  beside SDL validation, semantic profiles, apparatus manifests, controlled
  vocabularies, and runtime diagnostics; they must not introduce a second
  semantic registry or a second manifest family.
- Keep authoring intent, processor compilation/planning, and backend
  realization as distinct concerns. SDL authoring declares scenario
  meaning. The processor instantiates, compiles, and plans, but does not
  pick values for underspecified concerns — processor manifests carry no
  `realization_support`. The backend realizes only what the plan leaves
  to it and what its manifest declares.
- Treat exact author declarations as binding. If an author declares an exact
  requirement, downstream stages either honor it or reject the artifact with a
  structured error. Silent approximation is forbidden.
- Treat open concerns as explicit permission, not absence of validation. A
  missing exact declaration may allow realization only when the owning schema or
  semantic rule defines that field as realizable and the selected backend's
  manifest declares compatible support.
- Keep rejection semantics fail-closed and diagnostic-driven. Unsupported exact
  requirements should surface through existing `SDLValidationError`,
  `SDLInstantiationError`, or `aces_processor.models.Diagnostic` paths,
  depending on the phase where support is known.

## Canonical Incumbents

Build on these existing surfaces before adding anything new:

- SDL parsing and closed models: `aces_sdl.parser`, `aces_sdl.SDLModel`, and
  Pydantic `extra="forbid"` model boundaries
- static semantics: `SemanticValidator` and `SDLValidationError`
- instantiation: `instantiate_scenario()` and `SDLInstantiationError`
- shared semantic helpers: `aces_sdl.semantics.*` and
  `aces_processor.semantics.*`
- processor/backend declarations: `aces_processor.manifest`,
  `aces_processor.capabilities`, `aces_backend_protocols.capabilities`, and
  `aces_backend_protocols.manifest.backend_manifest_payload()`
- apparatus contract primitives: `aces_contracts.apparatus`,
  `RealizationSupportDeclaration`, `ConceptBinding`, and
  `RealizationSupportMode`
- contract validation: `aces_contracts.contracts.ContractModel`,
  `BackendManifestV2Model`, `ProcessorManifestV2Model`, `schema_bundle()`,
  generated `contracts/schemas/`, and fixture validation
- authority helpers: `manifest_authority`, `controlled_vocabularies`,
  `semantic_profiles`, `reference_models`, and the concept-authority catalogs
- runtime diagnostics and envelopes: `aces_processor.models.Diagnostic`,
  runtime plan/result/snapshot models, and published control-plane contracts
- workflow gates: `.ground-control.yaml`, `.gc/plan-rules.md`,
  `tools/check_repo_policy.py`, `tools/check_requirement_governance.py`,
  `tools/check_json_artifacts.py`, `tools/check_generated_schemas.py`, and
  `tools/verify_all.py`

## Cross-Cutting Layers

The implementation must pass every layer it touches:

- SDL parser gate: variable substitution must not create hidden exact
  declarations, rename semantic identities, or smuggle realization directives
  through keys.
- SDL model gate: explicitness state must be represented in typed fields or
  existing structured extension surfaces, not in untyped `dict` side channels.
- semantic validation gate: exact declarations must be validated as exact, and
  open realizable concerns must still be checked for shape, scope, and
  ambiguity.
- instantiation gate: defaults and parameters may fill open concerns only when
  the owning semantic rule permits it; concrete scenarios must be revalidated.
- contract/schema gate: external payload shape belongs in `ContractModel`
  descendants and generated schemas. Do not hand-edit `contracts/schemas/`.
- manifest/profile gate: supported contract versions, concept bindings,
  binding scopes, realization support modes, exact requirement kinds, and
  controlled vocabulary terms must resolve through existing authority helpers.
- planner/backend boundary gate: backend support checks must compare the
  compiled requirement against backend manifest `realization_support` instead
  of local string conventions.
- error-envelope gate: unsupported exact requirements and forbidden
  approximations must be reported with stable validation errors or structured
  diagnostics; do not leak raw backend exceptions or private payloads.
- control-plane gate: any runtime-facing realization result must pass existing
  request-size, authentication, authorization, audit, idempotency, and published
  response-model validation.
- persistence and observation gate: realized choices may be recorded only in
  portable snapshot/result/provenance envelopes. Do not persist secrets,
  bearer tokens, credentials, backend-native objects, or unredacted tracebacks.
- host/OS exposure gate: exact requirement values, credentials, and backend
  tokens must not be passed through process argv, logs, audit details,
  diagnostics, JSON fixtures, or semantic-profile artifacts when they may carry
  sensitive material.

## Extensibility Seam

The seam is a typed realization requirement classifier plus the existing
manifest support declaration, not a backend-specific branch. Future variation
should be added by extending the governed requirement-kind vocabulary and the
`RealizationSupportDeclaration`/manifest contract inputs, then regenerating and
validating schemas.

Keep the classifier independent of any one backend. The next obvious change is
additional exact requirement kinds for other artifact families; that should
require adding governed terms and shared semantic checks, not rewriting planner
or conformance call sites.

## Gotchas And Anti-Patterns

Avoid:

- using `realization_support` as a substitute for authoring semantics
- treating `open-realization` as permission to ignore exact declarations
- treating missing data as equivalent to backend freedom
- silently downgrading an exact requirement into a constrained or best-effort
  realization
- adding a second exception hierarchy, schema registry, vocabulary table, or
  manifest contract for explicitness semantics
- duplicating support checks in compiler, planner, conformance, and backend
  adapters instead of sharing a pure helper
- stuffing explicitness flags into `constraints` strings without a governed
  schema, vocabulary, or profile rule
- treating semantic profiles as backend capability profiles, or backend
  capability profiles as semantic profiles
- putting normative semantics in `docs/` or implementation constants instead
  of `specs/` and `contracts/`

## Companion Scope

This note is implementation guidance for the SEM-218 normative spec at
{download}`specs/formal/realization/explicitness-and-realization.md <../../../specs/formal/realization/explicitness-and-realization.md>`.
It does not itself add SDL syntax, define exact-requirement-kinds, or
change manifest payloads — those are governed by the spec and by the
controlled-vocabulary / reference-model authorities. The PR that
introduced the spec also promoted the SEM-218 row in the SEM-200
coverage table to `partial` and transitioned the requirement from
`DRAFT` to `ACTIVE` in Ground Control; the staged work that lifts the
row from `partial` to `active` (the SEM-218 classifier in
`SemanticValidator`, the typed compiler emission, the planner gate, the
runtime non-approximation envelope, the SEM-218 provenance fields) is
tracked under the SEM-218 coverage row and is the subject of follow-on
`/implement` runs. Treat the prose above as architecture guidance for
that staged work; treat the spec as the binding contract.
