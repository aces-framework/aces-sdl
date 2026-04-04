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
from aces.core.sdl import parse_sdl, parse_sdl_file

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
- **Runtime compilation**, planning, and control-plane contracts
- **Schemas** and backend conformance fixtures
- **CLI commands**, docs, examples, and tests

```{toctree}
:maxdepth: 2
:caption: SDL Guide

sdl/index
sdl/sections
sdl/parser
sdl/validation
sdl/precedents
sdl/complex-scenarios
sdl/limitations
sdl/testing
```

```{toctree}
:maxdepth: 2
:caption: Runtime

sdl/runtime-architecture
```

```{toctree}
:maxdepth: 2
:caption: Architecture Decisions

adrs/README
adrs/adr-000-use-adrs
adrs/adr-001-scenario-description-language
adrs/adr-002-declarative-sdl-objectives
adrs/adr-003-workflows-targetable-subobjects-and-enum-variables
adrs/adr-004-sdl-runtime-layer
adrs/adr-005-control-flow-primitives
adrs/adr-006-workflow-control-language-redesign
adrs/adr-007-lightweight-formal-methods-policy
```

```{toctree}
:maxdepth: 2
:caption: Reference

reference/coding-standards
```

```{toctree}
:maxdepth: 2
:caption: Formal Specifications

specs/formal
```

```{toctree}
:maxdepth: 2
:caption: API Reference

api/core-sdl
api/core-runtime
api/core-semantics
api/cli
```
