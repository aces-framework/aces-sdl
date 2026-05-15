# Controlled Vocabularies And Enumerations

## Scope

This specification defines the controlled-vocabulary authority surface for
portable declared terms whose values must compare consistently across ACES
artifacts.

It distinguishes two cases:

- closed enumerations, where the portable term set is fixed
- governed-extension vocabularies, where the portable base terms are fixed but
  controlled extension space remains available for ACES-native, experimental,
  or still-evolving declarations

Controlled vocabularies do not replace concept families, reference models, or
semantic profiles. They govern the stable term sets used inside those other
surfaces where cross-artifact comparison depends on shared portable values.

## Decision Record

[ADR-012](../../docs/decisions/adrs/adr-012-shared-concept-authority-and-aces-extension-discipline.md)
governs this specification.

## Controlled Vocabulary Catalog

Each controlled-vocabulary catalog declares:

- a stable `schema_version`
- a keyed `vocabularies` map

Each vocabulary declares:

- a human-readable `title`
- a `description`
- a `kind`, either `enumeration` or `vocabulary`
- optional `governed_scopes` identifying the published contract fields that
  use the vocabulary
- an `extension_policy`, either `closed` or `governed-extension`
- an `extension_pattern` when governed extensions are allowed
- a keyed `terms` map whose property names are the portable term identifiers

Controlled vocabulary identifiers are authoritative at the map key. They are
not duplicated inside each vocabulary object.

### Enumeration Rules

Closed enumerations are for stable portable values where cross-artifact
comparison must remain exact.

Enumerations:

- must use `extension_policy: closed`
- must not declare `extension_pattern`
- may declare governed scopes when they are bound to a published field surface

### Governed-Extension Rules

Governed-extension vocabularies are for portable terms that need stable shared
comparison today while still permitting disciplined local extension space.

Governed-extension vocabularies:

- must declare at least one governed scope
- must declare an `extension_pattern`
- must use only governed scopes owned by the published contract surfaces

Extension values are valid only when they match the declared extension
pattern. Values that are neither declared portable terms nor valid governed
extensions are invalid.

## Initial Catalog

The initial GOV-922 catalog is:

`contracts/concept-authority/controlled-vocabularies-v1.json`

It defines:

- closed enumerations for processor features, workflow features, workflow
  state-predicate features, realization support modes, and concept provenance
  categories
- governed-extension vocabularies for backend capability surfaces where stable
  portable terms exist but controlled local extension space is still needed:
  provisioner node types, operating-system families, content types, account
  features, orchestrator supported sections, and evaluator supported sections

## Machine-Readable Artifacts

The JSON Schema for the catalog format is published at:

`contracts/schemas/concept-authority/controlled-vocabularies-v1.json`

The valid and invalid fixture corpus for controlled vocabularies is published
under:

`contracts/fixtures/concept-authority/controlled-vocabularies-v1/`

## Validation Expectations

Contract and runtime validation must treat the catalog as the authority for
the governed surfaces it declares.

For governed apparatus-manifest capability fields:

- declared base terms must validate against the catalog
- extension values must match the governed extension pattern
- closed enumerations must reject extension values

## Relationship To Other Requirements

- GOV-917: canonical concept authority
- GOV-918: cross-artifact concept binding
- GOV-919: disciplined ACES-native extensions
- GOV-920: shared semantic profiles
- GOV-921: shared reference models
- GOV-922: controlled vocabularies and enumerations
