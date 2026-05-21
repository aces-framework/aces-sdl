# ACES SDL Documentation

**A backend-agnostic cyber range scenario description language and runtime ecosystem.**

`aces-sdl` is a fully working SDL stack for describing cyber range scenarios
and experiments, validating their meaning, compiling runtime models, and
defining portable backend contracts.

It is designed to stand on its own as a coherent system. It also serves as a
working, contrastive ecosystem for RFC and standards work by the Red Queen
Working Group, so language, semantics, runtime, and assurance questions can be
tested in a live codebase rather than only in abstract design discussions.

## Quick Start

```python
from aces_sdl import parse_sdl, parse_sdl_file

# Parse from a string
scenario = parse_sdl(yaml_string)

# Parse from a file
scenario = parse_sdl_file(Path("scenarios/my-scenario.yaml"))

# Skip semantic validation (structural only)
scenario = parse_sdl(yaml_string, skip_semantic_validation=True)

# Non-fatal authoring advisories
for advisory in scenario.advisories:
    print(advisory)
```

## What's Included

- **Author-facing SDL** models and parsing for 21 scenario sections
- **Semantic validation** and formal semantic artifacts
- **Processor layer** with compiler, planner, and control-plane contracts
- **Schemas** and backend conformance fixtures
- **CLI commands**, docs, examples, and tests

```{toctree}
:maxdepth: 2
:caption: SDL Guide

explain/sdl/index
explain/sdl/sections
explain/sdl/parser
explain/sdl/validation
explain/sdl/precedents
explain/sdl/lineage
explain/sdl/complex-scenarios
explain/sdl/limitations
explain/sdl/testing
```

```{toctree}
:maxdepth: 2
:caption: Runtime

explain/sdl/runtime-architecture
```

```{toctree}
:maxdepth: 2
:caption: Architecture Decisions

decisions/adrs/README
decisions/adrs/adr-000-use-adrs
decisions/adrs/adr-001-scenario-description-language
decisions/adrs/adr-002-declarative-sdl-objectives
decisions/adrs/adr-003-workflows-targetable-subobjects-and-enum-variables
decisions/adrs/adr-004-sdl-runtime-layer
decisions/adrs/adr-005-control-flow-primitives
decisions/adrs/adr-006-workflow-control-language-redesign
decisions/adrs/adr-007-lightweight-formal-methods-policy
decisions/adrs/adr-008-processor-layer-and-execution-artifact-boundaries
decisions/adrs/adr-009-normative-artifact-authority-and-repository-structure
decisions/adrs/adr-010-repository-realignment-order-and-compatibility-policy
decisions/adrs/adr-011-narrow-end-to-end-mvp-validation
decisions/adrs/adr-012-shared-concept-authority-and-aces-extension-discipline
decisions/adrs/adr-013-participant-episode-lifecycle-boundaries
decisions/adrs/adr-014-nox-as-canonical-verification-graph
decisions/adrs/adr-015-sdl-processor-layering-and-source-file-size-cap
decisions/adrs/adr-016-semantic-layer-scope-and-coverage-model
decisions/adrs/adr-017-conversation-surface-hardening
decisions/adrs/adr-018-classification-based-assurance-policy
decisions/adrs/adr-019-normative-authority-boundary-manifest
decisions/adrs/adr-020-declarative-participant-framing-boundaries
decisions/adrs/adr-021-falsification-first-claim-evidence-gate
decisions/adrs/adr-022-participant-behavior-and-interaction-semantics
decisions/adrs/adr-023-container-image-build-provenance-surface
decisions/sem-213-temporal-participant-preflight
```

```{toctree}
:maxdepth: 2
:caption: Reference

explain/reference/README
explain/reference/coding-standards
explain/reference/canonical-reference-map
explain/reference/documentation-style-guide
explain/reference/glossary
explain/reference/shared-concept-model
explain/reference/shared-semantic-integrity
explain/reference/backend-conformance
explain/reference/normative-artifact-authority
explain/reference/assessment-semantics
explain/reference/objective-semantics
explain/reference/explicitness-realization-semantics
```

```{toctree}
:maxdepth: 2
:caption: Formal Specifications

specs/formal
```

```{toctree}
:maxdepth: 2
:caption: API Reference

api/sdl
api/sdl-semantics
api/processor
api/processor-semantics
api/cli
```
