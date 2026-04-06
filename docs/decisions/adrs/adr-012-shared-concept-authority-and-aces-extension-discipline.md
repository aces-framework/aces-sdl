# ADR-012: Shared Concept Authority and ACES Extension Discipline

## Status

accepted

## Date

2026-04-05

## Context

The repository is now far enough along that several externally visible
surfaces are beginning to carry overlapping semantic claims:

- SDL authoring constructs
- processor manifests
- backend manifests
- provenance and reporting surfaces
- external knowledge bindings and translation paths

Without an explicit concept-authority decision, those surfaces can drift into a
weak form of agreement where they reuse similar strings without sharing
authoritative meaning.

At the same time, ACES should not respond by inventing an isolated ontology
from scratch when mature cyber-domain concept authorities already exist.

Primary-source review suggests a cleaner layered model:

- use an external semantic authority where it fits
- keep ACES as the authoring and ecosystem layer
- define ACES-native extensions where experiment, runtime, apparatus,
  provenance, and governance concerns exceed classic cyber ontology

The repo therefore needs one clear architectural decision about how shared
meaning is sourced and extended before more manifests, contracts, and reports
are added.

## Decision

Adopt a layered shared-concept model in which external concept authority is
used for relevant cyber-domain meaning and ACES defines disciplined native
extensions for ecosystem-specific concerns.

### 1. Use external concept authority where it fits

ACES should prefer a shared external semantic authority for cyber-domain
concepts when that authority is mature, portable, and semantically appropriate.

For the current GOV-917 direction, UCO is the leading candidate semantic spine
for cyber-domain concepts such as:

- assets
- identities
- relationships
- observables
- actions or events
- tools or artifacts

This is a concept-authority decision, not an authoring-syntax decision.

### 2. ACES remains the language and ecosystem

ACES SDL, manifests, contracts, provenance, evidence, and runtime artifacts
remain ACES ecosystem surfaces.

Authors must not be required to write UCO directly, and externally visible
ACES artifacts must not be forced to mirror ontology structure mechanically.

### 3. Define ACES-native extensions where the ecosystem goes beyond cyber ontology

ACES shall define native extension concepts when the ecosystem needs concepts
that do not naturally belong to the shared cyber-domain authority, including
areas such as:

- scenarios
- tasks, runs, and studies
- processor, backend, and participant declaration surfaces
- realization and disclosure concepts
- provenance and evidence expectations
- time, clock, and apparatus concerns

These extensions must be explicit rather than implicit shadow vocabularies.

### 4. Bind artifacts to concepts instead of reusing labels loosely

SDL, manifests, contracts, provenance, and reports should bind to canonical
concepts rather than merely repeating the same text labels.

The goal is shared meaning across artifacts, not merely consistent spelling.

### 5. Keep concept authority separate from structure authority

Shared concept authority does not imply that every artifact must expose the
same structural shape as the ontology.

Normative prose, schemas, manifests, and reports remain responsible for their
own artifact-level structure, while concept authority governs what declared
terms mean.

### 6. Start narrow and representative

The initial concept-model slice should be narrow enough to validate the method
without ontology-izing the entire ecosystem prematurely.

The first slice should focus on the cyber-domain concept families listed above
and the artifact-binding rules needed to carry those concepts across SDL,
manifests, provenance, and reporting.

### 7. Tighten v2 semantics instead of preserving v1 looseness

The first apparatus-manifest implementation should tighten the `v2` semantics
instead of preserving any looser `v1` behavior for compatibility.

In practice, that means:

- `concept_bindings` are required on `v2` apparatus manifests
- each bound family identifier must resolve against the authoritative
  `concept-families-v1` catalog
- each bound scope must resolve to a governed manifest vocabulary surface that
  is actually declared in the artifact being validated

This tightening is intentional. The legacy `v1` shapes are deprecated and are
not a constraint on how precisely the `v2` concept-binding layer is enforced.

## Consequences

### Positive

- The repo gets a clear semantic-authority story instead of continuing to grow
  independent local vocabularies.
- ACES can reuse mature cyber-domain meaning without surrendering its own
  ecosystem identity.
- Future manifest, reporting, and interoperability work has a cleaner basis
  for shared meaning.

### Negative

- Contributors will need to distinguish concept authority from authoring
  syntax, artifact shape, and implementation model.
- Some concept and extension boundaries will remain provisional while the first
  narrow slice is validated.

### Risks

- If UCO is adopted too mechanically, ACES could accidentally force ontology
  structure into author-facing or contract-facing surfaces.
- If ACES-native extensions are added casually, the project could recreate the
  same drift problem under a new namespace.
- If the first slice grows too broad, the concept-model effort could turn into
  an ontology migration instead of a controlled architectural alignment.
