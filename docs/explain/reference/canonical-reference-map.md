# Canonical Reference Map

This page identifies the current repository locations for ACES SDL reference
material. It is an index, not a replacement for the linked artifacts.

## Repository Authority

| Surface | Current reference |
|---------|-------------------|
| Authority boundary | [`specs/authority/authority-boundary.yaml`](../../../specs/authority/authority-boundary.yaml), [ADR-009](../../decisions/adrs/adr-009-normative-artifact-authority-and-repository-structure.md), [ADR-019](../../decisions/adrs/adr-019-normative-authority-boundary-manifest.md) |
| Normative prose | `specs/` |
| Architecture decisions | [`docs/decisions/adrs/`](../../decisions/adrs/README.md) |
| Reference notes | [`docs/explain/reference/`](README.md) |
| Coding policy | [`coding-standards.md`](coding-standards.md) |
| Documentation policy | [`documentation-style-guide.md`](documentation-style-guide.md) |

## SDL And Experiments

| Surface | Current reference |
|---------|-------------------|
| SDL guide | [`docs/explain/sdl/index.md`](../sdl/index.md) |
| SDL sections | [`docs/explain/sdl/sections.md`](../sdl/sections.md) |
| Parser behavior | [`docs/explain/sdl/parser.md`](../sdl/parser.md) |
| Semantic validation | [`docs/explain/sdl/validation.md`](../sdl/validation.md) |
| Current SDL limits | [`docs/explain/sdl/limitations.md`](../sdl/limitations.md) |
| Testing notes | [`docs/explain/sdl/testing.md`](../sdl/testing.md) |
| Design precedents | [`docs/explain/sdl/precedents.md`](../sdl/precedents.md) |
| Academic lineage | [`docs/explain/sdl/lineage.md`](../sdl/lineage.md) |

## Contracts And Processing

| Surface | Current reference |
|---------|-------------------|
| Contract root | `contracts/README.md` |
| Published schemas | `contracts/schemas/README.md` |
| Schema inventory | [`contracts/schema-publication-manifest.json`](../../../contracts/schema-publication-manifest.json) |
| Processor API | [`docs/api/processor.rst`](../../api/processor.rst) |
| Processor semantics API | [`docs/api/processor-semantics.rst`](../../api/processor-semantics.rst) |
| Runtime architecture | [`docs/explain/sdl/runtime-architecture.md`](../sdl/runtime-architecture.md) |
| Backend conformance | [`backend-conformance.md`](backend-conformance.md) |

## Formal And Semantic Material

| Surface | Current reference |
|---------|-------------------|
| Formal specs index | [`docs/specs/formal.md`](../../specs/formal.md), `specs/formal/README.md` |
| Objective semantics | `specs/formal/objectives/`, [`objective-semantics.md`](objective-semantics.md) |
| Workflow semantics | `specs/formal/workflows/` |
| Runtime contracts | `specs/formal/runtime-contracts/` |
| Assessment semantics | `specs/formal/assessment/`, [`assessment-semantics.md`](assessment-semantics.md) |
| Participant semantics | `specs/formal/participant-semantics/README.md` |
| Realization semantics | `specs/formal/realization/`, [`explicitness-realization-semantics.md`](explicitness-realization-semantics.md) |
| Planner semantics | `specs/formal/planner/` |

## Current Materialization Notes

- SDL authoring, parsing, validation, instantiation, compilation, planning,
  control-plane APIs, and published JSON schemas are present in the repository.
- Participant-implementation manifests, evidence-capture contracts, and
  provenance contract surfaces are described at the architecture level and are
  not fully materialized as published schemas.
- Legacy `v1` backend and processor manifest schemas remain checked in as
  deprecated reference artifacts; current conformance material uses the shared
  `v2` apparatus manifest envelope.
