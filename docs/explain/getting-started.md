# Getting Started With ACES

ACES currently provides a Scenario Description Language (SDL), a Python
reference implementation, contracts, examples, tests, and explanatory
documentation. It is not a managed cyber range and does not include a
production backend.

Use this page to choose the smallest useful entrypoint for your task.

## Current Boundary

ACES can currently support:

- reading and authoring SDL scenario documents
- parsing and validating SDL through the Python implementation
- instantiating variables and compiling runtime models in the reference stack
- checking backend contract fixtures and conformance profiles
- reviewing the specifications, ADRs, and examples that define current claims

ACES does not currently provide:

- production range deployment
- hosted backend operation
- a general template catalog
- participant-behavior templates
- task, run, or study templates
- a reusable pattern library with versioned catalog metadata

Treat the examples as worked examples, not as conformance fixtures or schema
authority.

## Choose A Path

| Goal | Start with | Current check | Supported statement |
|------|------------|---------------|---------------------|
| Understand the repository | `README.md`, [`docs/index.md`](../index.md), [`docs/explain/reference/canonical-reference-map.md`](reference/canonical-reference-map.md) | Read the referenced docs | The repository layout and current boundaries are understood. |
| Read a complete scenario | `examples/README.md`, `examples/scenarios/*.sdl.yaml` | `pytest tests/test_scenarios.py` | The checked examples load through the current parser boundary. |
| Author a small SDL file | [`docs/explain/sdl/index.md`](sdl/index.md), [`docs/explain/sdl/sections.md`](sdl/sections.md), [`docs/explain/sdl/validation.md`](sdl/validation.md) | `parse_sdl_file()` or `load_scenario()` | The file is accepted by the current SDL model and semantic validator. |
| Use variables or imports | [`docs/explain/sdl/parser.md`](sdl/parser.md), [`docs/explain/sdl/sections.md`](sdl/sections.md) | `aces sdl resolve`, `aces sdl verify-imports` | Imports and variable placeholders follow the current parser rules. |
| Inspect current limits | [`docs/explain/sdl/limitations.md`](sdl/limitations.md), [`docs/explain/sdl/testing.md`](sdl/testing.md) | Compare the use case to the listed materialized surfaces | Unsupported or partial surfaces are identified before authoring. |
| Work on backend conformance | [`docs/explain/sdl/runtime-architecture.md`](sdl/runtime-architecture.md), `contracts/README.md`, [`docs/explain/reference/backend-conformance.md`](reference/backend-conformance.md) | `aces conformance --help` and the conformance tests | The backend work is aligned with published contracts and fixtures. |
| Review semantics or authority | [`docs/specs/formal.md`](../specs/formal.md), [`docs/decisions/adrs/`](../decisions/adrs/README.md), [`docs/explain/reference/normative-artifact-authority.md`](reference/normative-artifact-authority.md) | Read the relevant spec, ADR, and tests together | The claim is grounded in the current authority surface. |

## Rigor Levels

Use the lowest level that answers the question.

| Level | Use when | Current artifact | What it can show | What it cannot show |
|-------|----------|------------------|------------------|---------------------|
| Orientation | You need to know what ACES is and is not. | README, docs index, reference map | Current repository scope and entrypoints | SDL validity, backend behavior, or experiment adequacy |
| SDL parse and validation | You have an SDL file and need current parser feedback. | `parse_sdl_file()`, `load_scenario()`, SDL parser/model/validator tests | Structural and semantic acceptance by the reference implementation | Deployment viability or general domain completeness |
| Example-backed authoring | You need a worked scenario to study or adapt. | `examples/scenarios/*.sdl.yaml`, `test_scenarios.py` | The example loads from disk without advisories under current tests | Suitability for another range, backend, exercise, or research design |
| Runtime and contracts | You need processor or backend integration context. | Runtime compiler/planner, contract schemas, backend profiles, conformance fixtures | Current reference-stack and contract behavior | Production backend correctness or operational reliability |
| Specification review | You need to evaluate a semantic or authority claim. | `specs/`, ADRs, formal notes, tests | The current reasoning and normative boundary for a claim | Completed implementation when the materialized code/contracts are absent |

## Basic Setup

From the repository root:

```shell
cd implementations/python
uv sync --all-extras
uv run aces --help
```

Parse and validate a scenario from Python:

```python
from pathlib import Path

from aces_sdl import parse_sdl_file

scenario = parse_sdl_file(
    Path("../../examples/scenarios/hospital-ransomware-surgery-day.sdl.yaml")
)

for advisory in scenario.advisories:
    print(advisory)
```

Run the current disk-backed example tests:

```shell
cd implementations/python
uv run --extra dev pytest tests/test_scenarios.py -q
```

Work with SDL module imports:

```shell
cd implementations/python
uv run aces sdl resolve ../../examples/scenarios/hospital-ransomware-surgery-day.sdl.yaml
uv run aces sdl verify-imports ../../examples/scenarios/hospital-ransomware-surgery-day.sdl.yaml
```

The CLI does not expose a separate general-purpose `validate` command today.
Use the Python parser boundary or the test suite for direct validation.

## Current Example Use

The current positive example corpus is under `examples/scenarios/`. Each file
is real SDL and is loaded by `implementations/python/tests/test_scenarios.py`.

Use examples to:

- inspect large SDL structure
- see current workflow, objective, relationship, content, and runtime surfaces
- exercise parser and semantic validation with real files
- identify authoring friction against current limits

Do not use examples to claim:

- production backend support
- complete cyber-range domain coverage
- participant-behavior adequacy
- task, run, or study provenance support
- conformance to any backend beyond published fixtures and tests

## Unsupported Template And Pattern Surfaces

Some useful artifacts are not present because the current system lacks the
syntax, contracts, or validation boundary needed to make them useful now.

Current status:

- Scenario examples exist as valid SDL files.
- Workflow examples exist inside scenario files and workflow specs.
- Participant behavior has architecture and partial contract work, but no
  reusable authoring template catalog.
- Tasks, runs, and studies are recognized ecosystem concepts, but no current
  template or pattern catalog exists for them.
- Evidence and provenance concerns are documented at architecture and
  limitation surfaces, but not fully materialized as published template
  artifacts.

When adding an artifact, put it where its current role matches the repository
authority boundary:

- valid worked SDL examples: `examples/scenarios/*.sdl.yaml`
- explanatory snippets: `docs/`
- normative rules: `specs/`
- published schemas and fixtures: `contracts/`
- implementation tests: `implementations/python/tests/`

Invalid SDL specimens belong in focused tests or contract fixtures, not in the
positive example corpus.
