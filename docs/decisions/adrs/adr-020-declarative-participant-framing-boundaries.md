# ADR-020: Declarative Participant Framing Boundaries

## Status

proposed

## Date

2026-05-18

## Context

`ACT-601` requires declarative participant framing in the language: identity,
role, starting conditions, authority anchors, and operating scope.

The repository already has several nearby concepts:

- `entities` model organizations, teams, people, and exercise roles.
- `accounts` model environment accounts on scenario nodes.
- `agents` model autonomous scenario participants with starting accounts,
  initial knowledge, allowed subnets, actions, and reward-calculator labels.
- `objectives` bind agents or entities to declarative experiment intent.
- participant episode contracts model runtime lifecycle state and history.
- control-plane identity models authenticated HTTP/control-plane callers.
- backend and processor manifests model apparatus identity and capability.

Those surfaces overlap in vocabulary but not in responsibility. Participant
framing must extend authored SDL meaning without collapsing environment
credentials, runtime episode state, control-plane authentication, or concrete
participant implementations into one overloaded participant concept.

## Decision

### 1. Participant framing is an SDL authoring concern

Declarative participant framing belongs in the SDL authoring layer. The
implementation should evolve the existing participant-authoring surface
(`agents`, and the declared elements it references) unless a separate language
surface is clearly necessary for a distinct authored concept.

It must not be implemented first as runtime snapshot metadata, control-plane
request shape, backend manifest metadata, or participant episode state.

### 2. Keep the five framing facets separate

The language-level model must keep these concerns distinct:

- **Identity**: the participant's authored scenario identity or alignment,
  anchored to declared `entities` and the shared `identities` concept family.
  This is not an OS account username, API caller identity, or apparatus name.
- **Role**: the participant's scenario role or exercise alignment. Reuse
  `entities.role` and related authored role structure where that is sufficient;
  do not confuse it with node-local login role mappings.
- **Starting conditions**: declared initial state, access, knowledge, or
  precondition references. Reuse `starting_accounts`, `initial_knowledge`,
  `conditions`, and named SDL references rather than embedding executable
  setup probes or runtime observations.
- **Authority anchors**: declared bases for what the participant is allowed or
  expected to do in scenario meaning. Anchor these to SDL declarations,
  relationships, concept-authority bindings, or future policy/directive
  surfaces; do not use control-plane authentication or bearer-token identity as
  authored authority.
- **Operating scope**: declared boundaries for where the participant may act or
  observe. Reuse `allowed_subnets`, targetable named references, and existing
  scope validation patterns. Do not treat backend process boundaries or OS
  sandbox configuration as SDL operating scope.

### 3. Reuse existing validation and contract boundaries

Participant framing must pass through the existing SDL and contract pipeline:

- parser normalization and shorthand expansion in `aces_sdl.parser`
- closed-world Pydantic SDL models via `SDLModel(extra="forbid")`
- semantic cross-reference validation in `SemanticValidator`
- variable-reference rules from `aces_sdl._base`
- generated SDL contract schemas through
  `aces_contracts.contracts.schema_bundle()`
- schema publication checks; `contracts/schemas/` remains generated output

If portable enumerations or governed terms become necessary, they belong in the
controlled-vocabulary authority surface rather than as artifact-local strings.

### 4. Preserve runtime and apparatus boundaries

Participant framing may compile into processor-owned runtime artifacts when
the processor needs it for planning or execution, but authored framing remains
separate from:

- participant episode lifecycle state/history from ADR-013
- `ControlPlaneIdentity` and control-plane roles
- backend `ParticipantRuntimeCapabilities`
- concrete participant-implementation manifests and provenance
- mutable `RuntimeSnapshot.metadata` blobs

Runtime episode identity should continue to use stable `participant_address`
plus per-episode `episode_id` and `sequence_number`; SDL participant framing
should not replace or weaken those lifecycle invariants.

### 5. Extensibility seam

The next likely participant-language changes are behavior semantics,
visibility, tool/affordance exposure, decision-surface policy, trajectories,
budgets, and verifier/reward assets. The framing model should leave room for
those by using explicit optional fields or nested SDL submodels with semantic
validation hooks, not by turning one free-form `metadata` or `authority` map
into a catch-all extension point.

New fields should be parameterizable only through the repository's existing
variable-reference rules. Symbol-defining keys must remain stable authoring
identifiers, not variables.

### 6. ACT-601 published field surface

The ACT-601 implementation pins the following authoring shape on `agents.*`:

- identity — `entity` (existing) anchored to the declared `entities`
  hierarchy.
- role — `entities.<entity>.role` (existing) reached through the
  participant's `entity` binding.
- starting conditions — `starting_conditions` (new), a list of bare or
  qualified references into the scenario's `conditions` section. Combined
  with the existing `starting_accounts` and `initial_knowledge`.
- authority anchors — `authority_anchors` (new), a list of references into
  the named-element index (entities, relationships, content, nodes, …).
- operating scope — `operating_scope` (new), a list of references into a
  spatially-bounded subset of targetable elements: VM `nodes`,
  switch-backed `infrastructure` entries, declared service refs, and
  `content` items. The legacy `allowed_subnets` field stays restricted to
  switch-backed infrastructure.

Each new field accepts `${var}` placeholders, defaults to an empty list,
and is rejected when undeclared by the parser's closed-world model. The
generated SDL JSON Schema and `docs/explain/sdl/sections.md` carry the
field names; the `agents` section heading remains the publishing surface.

## Consequences

### Positive

- ACT-601 has a clear language-layer home without disturbing ADR-013 runtime
  episode boundaries.
- Existing `entities`, `accounts`, `agents`, `objectives`, named-reference,
  concept-authority, and generated-schema patterns stay canonical.
- Later participant-behavior work can extend the model without re-editing a
  monolithic catch-all field.

### Negative

- Implementors must distinguish several similar names: identity, role,
  account, agent, participant address, control-plane identity, and apparatus
  identity.
- Some existing `agents` fields may need clearer semantics before additional
  participant fields are added.

### Risks

- Duplicating `Agent` under a new `participants` model without a clear semantic
  split would create two language surfaces for the same authored concept.
- Encoding authority anchors as transport authentication would leak deployment
  security into scenario meaning.
- Encoding starting conditions as commands or live observations would bypass
  the condition/evaluation pipeline and weaken reproducibility.
- Adding a free-form extension map would delay the hard modeling decisions and
  make semantic validation ineffective.

## Non-Goals

- Implement participant behavior semantics, visibility policy, trajectories,
  budgets, or verifier/reward assets (ACT-602, SEM-208, …).
- Redesign participant episode lifecycle contracts.
- Introduce new control-plane authentication, authorization, logging, or
  persistence machinery.
- Move schema authority away from the existing generated-contract pipeline.
