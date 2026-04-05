# Concept Authority

## Scope

This specification defines the canonical concept authority for cyber-domain
concepts used across ACES SDL, manifests, contracts, provenance, reporting,
and related ecosystem artifacts.

It establishes what concept families exist, where their meaning comes from,
and how the ecosystem distinguishes imported meaning from native extensions.

## Decision Record

[ADR-012](../../docs/decisions/adrs/adr-012-shared-concept-authority-and-aces-extension-discipline.md)
is the architectural decision that governs this specification.

## Layer Model

The shared concept model has three layers.

### 1. Concept Authority Layer

Defines what relevant cyber-domain concepts mean.

UCO (Unified Cyber Ontology) is the semantic authority for cyber-domain
concept families. This is a concept-authority relationship, not an
authoring-syntax or schema-structure requirement.

### 2. ACES Concept Layer

Defines concepts that ACES needs beyond the cyber-domain authority. These
are ACES-native extensions for experiment, runtime, apparatus, provenance,
and governance concerns.

### 3. Artifact Binding Layer

Where SDL, manifests, contracts, provenance, and reports bind their declared
meaning to canonical concepts. This layer prevents artifact-local strings
from becoming de facto semantics.

## Provenance Categories

Every concept family declares its provenance:

| Category | Meaning |
|----------|---------|
| `adopted` | Imported from the external authority with equivalent meaning. |
| `adapted` | Derived from the external authority with ACES-specific modifications. |
| `native` | Defined by ACES with no external authority source. |

## Concept Families

### Cyber-Domain Families

These families use UCO as the concept authority.

| Family | Provenance | Scope |
|--------|-----------|-------|
| `assets` | adopted | Nodes, infrastructure, networks, and deployable resources. |
| `identities` | adopted | Accounts, entities, roles, and identity-bearing participants. |
| `relationships` | adapted | Typed associations between scenario elements. |
| `observables` | adopted | Conditions, metrics, telemetry, and observable properties. |
| `actions-and-events` | adopted | Events, injects, workflow steps, and executable actions. |
| `tools-and-artifacts` | adopted | Features, content, software, and deployable artifacts. |

The `relationships` family uses `adapted` provenance because existing
relationship types draw from STIX 2.1 Relationship SROs and OCR dependency
patterns, not from UCO alone.

### ACES-Native Families

These families have no external authority. They are defined by ACES for
ecosystem-specific concerns.

| Family | Scope |
|--------|-------|
| `scenarios` | SDL scenarios, compositions, modules, and authoring constructs. |
| `tasks-runs-studies` | Execution lifecycle, run records, and study organization. |
| `apparatus-declarations` | Processor, backend, and participant-implementation manifests. |
| `realization-and-disclosure` | Instantiation, planning, compilation, and realization artifacts. |
| `provenance-and-evidence` | Run provenance records, evidence expectations, and audit artifacts. |
| `time-and-apparatus` | Clocks, timing constraints, and apparatus-level concerns. |

## Machine-Readable Catalog

The authoritative concept family catalog is published at:

`contracts/concept-authority/concept-families-v1.json`

The catalog is a keyed map. `families` is an object whose property names are
the canonical family identifiers, and each property value is the family
definition. The family identifier is authoritative at the map key and is not
duplicated inside each family object.

The catalog must not be empty. Each family entry must declare a non-empty
`title` and `description`.

The machine-readable catalog also makes the provenance rules normative:

- `adopted` and `adapted` families must declare both `authority` and
  `authority_reference`
- `native` families must not declare either authority field

The JSON Schema for the catalog format is published at:

`contracts/schemas/concept-authority/concept-families-v1.json`

## Relationship to Implementation

Implementation code may define enums and models that correspond to concept
families, but the normative catalog is the authority for what families exist
and where their meaning comes from.

## Relationship to Other Requirements

- GOV-917: This specification (concept authority definition).
- GOV-918: Cross-artifact concept binding (how artifacts reference concepts).
- GOV-919: Extension discipline (rules for adding new concepts).
- GOV-920: Shared semantic profiles.
- GOV-921: Shared reference models.
- GOV-922: Controlled vocabularies and enumerations.
