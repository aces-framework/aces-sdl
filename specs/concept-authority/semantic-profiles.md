# Shared Semantic Profiles

## Scope

This specification defines shared semantic profiles for ACES authoring,
exchange, processing, and execution surfaces.

Shared semantic profiles declare the compatible concept, contract, and
behavior assumptions required for interoperable artifact production,
publication, processing, and runtime operation.

## Decision Record

[ADR-012](../../docs/decisions/adrs/adr-012-shared-concept-authority-and-aces-extension-discipline.md)
governs this specification.

## Profile Model

Each semantic profile declares:

- a stable `profile_id`
- the `concept_catalog_version` it assumes
- phase-specific assumptions for `authoring`, `exchange`, `processing`, and
  `execution`

Each phase declares:

- `required_contracts`: the published contract identifiers required for that
  interoperability phase
- `required_concept_families`: the concept families whose meaning must be
  shared for that phase
- `required_bindings`: the required scope-to-family bindings where a governed
  artifact surface must bind its vocabulary explicitly
- `behavior_assumptions`: stable behavior-assumption identifiers and
  statements that describe the non-structural semantic expectations for that
  phase

`required_bindings` are only valid when they resolve to governed artifact
surfaces for that phase. In the initial profile, that means processor
manifest `v2` binding scopes for `processing` and backend manifest `v2`
binding scopes for `execution`. `authoring` and `exchange` do not currently
define governed binding surfaces and therefore do not declare
`required_bindings`.

## Initial Profile

The initial GOV-920 profile is:

`contracts/profiles/semantic/reference-stack-v1.json`

It declares the shared assumptions for the current reference stack:

- SDL authoring and instantiation
- processor planning and coordination
- backend realization and execution
- typed runtime exchange envelopes

The reference stack profile is intentionally concrete. It is the first
repo-owned semantic profile, not a promise that the ecosystem will forever use
only one profile.

## Machine-Readable Artifacts

The JSON Schema for semantic profiles is published at:

`contracts/schemas/profiles/semantic-profile-v1.json`

The valid and invalid fixture corpus for semantic profiles is published under:

`contracts/fixtures/semantic-profile/semantic-profile-v1/`

## Relationship To Other Requirements

- GOV-917: canonical concept authority
- GOV-918: cross-artifact concept binding
- GOV-919: disciplined ACES-native extensions
- GOV-920: shared semantic profiles
- GOV-921: shared reference models
- GOV-922: controlled vocabularies and enumerations
