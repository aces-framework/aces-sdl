# Shared Concept Model

This note is the implementation-facing design guidance for `GOV-917` and the
closely related concept-model requirements around extension discipline,
cross-artifact concept binding, reference models, and controlled vocabularies.

It is intentionally not an implementation plan. Its purpose is to keep the
next implementation pass aligned with the right architectural model.

## Goal

Make shared meaning real across ACES artifacts without turning the ontology
into the SDL, the manifests, or the contract schema layout.

The core problem is semantic drift:

- SDL says one thing
- processor manifests say something similar
- backend manifests say something similar
- provenance and reports reuse the same words

but none of those surfaces are actually bound to the same authoritative
concept.

## Layer Model

The shared-concept model has three layers.

### 1. Concept authority layer

This layer defines what relevant cyber-domain concepts mean.

For the current direction, UCO is the leading candidate semantic spine for
concept families such as:

- assets
- identities
- relationships
- observables
- actions or events
- tools or artifacts

This layer is about semantic authority, not authoring syntax.

### 2. ACES concept layer

This layer defines the concepts ACES needs that are not naturally covered by
the cyber-domain authority, including:

- scenarios
- tasks, runs, and studies
- processor, backend, and participant declaration surfaces
- realization and disclosure
- provenance and evidence requirements
- time, clocks, and apparatus concerns

These are ACES-native concepts, even when they relate to cyber-domain
concepts.

### 3. Artifact binding layer

This layer is where SDL, manifests, contracts, provenance, and reports bind
their declared meaning to canonical concepts.

The binding layer is what prevents artifact-local strings from becoming de
facto semantics.

## Guardrails

The following constraints should shape any `GOV-917` implementation.

### UCO is not the SDL

Authors should not be required to write UCO directly.

ACES remains the authoring and ecosystem layer. Shared concept authority exists
behind the authoring surface, not in place of it.

### Ontology structure is not contract structure

Contracts, manifests, and reports do not need to mirror ontology layout
mechanically.

Concept authority answers "what does this declared thing mean?" It does not
require every artifact to serialize in the same shape as the ontology.

### ACES-native concepts must be explicit

If ACES needs concepts outside the chosen cyber-domain authority, those
concepts must be declared explicitly as ACES-native extensions.

Do not create silent local forks of imported concepts and do not introduce new
portable labels without saying whether they are:

- adopted from the shared authority
- adapted from the shared authority
- native to ACES

### Bind concepts, not just labels

The implementation target is shared concept binding, not merely consistent
wording.

If two artifacts use the same word but point at different meaning, the system
is still drifting.

### Start with a narrow representative slice

The first concept-model slice should cover the cyber-domain concept families
most likely to appear across more than one artifact family:

- assets
- identities
- relationships
- observables
- actions or events
- tools or artifacts

That is enough to validate whether the method works across SDL, manifests,
provenance, and reporting without forcing the whole ecosystem into one big
ontology exercise.

## What The First GOV-917 Slice Should Make Possible

The first slice should enable the repo to say something stronger than
"different artifacts happen to use similar words."

It should make it possible for ACES artifacts to state:

- this SDL construct refers to a canonical concept
- this manifest capability or declaration refers to the same concept
- this provenance or reporting surface refers to that same concept

The authoritative concept-family catalog is keyed by canonical family
identifier. That keeps the concept identifier authoritative at one boundary
instead of repeating it as an artifact-local field that can drift.

while still allowing each artifact family to keep its own fit-for-purpose
shape.

## Cross-Artifact Concept Binding (GOV-918)

`GOV-918` implements the artifact binding layer for apparatus manifests.

Both `v2` backend manifests and `v2` processor manifests now require a
`concept_bindings` section. Each entry maps a dot-delimited field path (scope)
to a concept family identifier from the authoritative catalog.

For example, a backend manifest binds its provisioner vocabulary:

```json
"concept_bindings": [
  {"scope": "capabilities.provisioner.supported_node_types", "family": "assets"},
  {"scope": "capabilities.provisioner.supported_os_families", "family": "assets"},
  {"scope": "capabilities.provisioner.supported_content_types", "family": "tools-and-artifacts"},
  {"scope": "capabilities.provisioner.supported_account_features", "family": "identities"},
  {"scope": "capabilities.orchestrator.supported_sections", "family": "actions-and-events"},
  {"scope": "capabilities.evaluator.supported_sections", "family": "observables"}
]
```

This makes it possible for downstream tooling to answer: "which concept family
does this manifest field belong to?" without relying on field-name conventions
or documentation.

The binding is required (not optional) to prevent specification gaps where
concept bindings could be silently omitted. Family identifiers are validated
against the authoritative catalog at model time, and scope paths must resolve
to governed manifest vocabulary surfaces that are actually declared in the
artifact.

## Relationship To Other Requirements

`GOV-917` is the concept-authority decision surface.

The related requirements split the rest of the problem:

- `GOV-918`
  Cross-artifact concept binding (implemented)
- `GOV-919`
  ACES extension discipline over the shared authority
- `GOV-920`
  shared semantic profiles
- `GOV-921`
  shared reference models
- `GOV-922`
  controlled vocabularies and enumerations

The point is to avoid solving all of those implicitly and inconsistently inside
one implementation pass.

## Non-Goals For The First Pass

The first pass should not attempt to:

- replace SDL with ontology syntax
- make every contract structurally identical to the ontology
- model all ACES concepts at once
- solve all participant, provenance, evidence, and time/apparatus semantics in
  one step
- standardize every local implementation detail as a portable vocabulary term

If a proposed change would do one of those things, it is probably trying to
solve too much at once.
