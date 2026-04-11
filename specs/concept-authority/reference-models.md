# Shared Reference Models

## Scope

This specification defines shared reference models for recurrent
federation-relevant structures carried in ACES artifact surfaces.

Shared reference models do not redefine concept authority and do not replace
artifact-local schemas. They declare which published structure definitions are
the shared reusable models for recurrent objects such as assets, identities,
relationships, observables, actions or events, and tools or artifacts.

## Decision Record

[ADR-012](../../docs/decisions/adrs/adr-012-shared-concept-authority-and-aces-extension-discipline.md)
governs this specification.

## Reference Model Catalog

Each reference-model catalog declares:

- a stable `schema_version`
- a keyed `models` map

Each model declares:

- a human-readable `title`
- a `description`
- the authoritative `concept_family` it belongs to
- an `authoritative_schema` binding that identifies the published contract
  schema definition and the governed instance path where that structure is
  used
- optional `reused_schemas` bindings for equivalent reused structures in other
  published contracts
- `key_fields` that must exist on the referenced schema definition

Reference-model bindings must resolve to real published contract schemas, real
schema definitions, and real governed instance collections. Reference models
are intentionally anchored to existing schema authority instead of restating
object structure inline.

## Initial Catalog

The initial GOV-921 catalog is:

`contracts/concept-authority/reference-models-v1.json`

It declares the shared reference models for the current recurrent SDL object
slice:

- scenario nodes as asset-bearing structures
- scenario accounts as identity-bearing structures
- scenario relationships as directed relationship structures
- scenario conditions as observable structures
- scenario events as action or event structures
- scenario content as tool or artifact structures

## Machine-Readable Artifacts

The JSON Schema for the catalog format is published at:

`contracts/schemas/concept-authority/reference-models-v1.json`

The valid and invalid fixture corpus for reference models is published under:

`contracts/fixtures/concept-authority/reference-models-v1/`

## Relationship To Other Requirements

- GOV-917: canonical concept authority
- GOV-918: cross-artifact concept binding
- GOV-919: disciplined ACES-native extensions
- GOV-920: shared semantic profiles
- GOV-921: shared reference models
- GOV-922: controlled vocabularies and enumerations
