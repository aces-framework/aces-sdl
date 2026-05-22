# ACES Examples

This directory contains non-normative worked examples. They are useful for
reading and testing current SDL behavior. They are not conformance fixtures,
schemas, deployment recipes, or backend guarantees.

## Current Corpus

| File | Best use | Current coverage | Limits |
|------|----------|------------------|--------|
| [`scenarios/hospital-ransomware-surgery-day.sdl.yaml`](scenarios/hospital-ransomware-surgery-day.sdl.yaml) | Large enterprise and clinical operations scenario | Disk-backed example test; complex example checks for objectives, agents, relationships, content, stories, metrics, direct refs | Does not deploy a hospital range or prove clinical exercise adequacy |
| [`scenarios/satcom-release-poisoning.sdl.yaml`](scenarios/satcom-release-poisoning.sdl.yaml) | Supply-chain, release, tenant, and rollback scenario | Disk-backed example test; complex example checks for objectives, agents, relationships, content, stories, metrics, workflows, enum-backed variables | Does not implement a CI/CD backend or production release system |
| [`scenarios/port-authority-surge-response.sdl.yaml`](scenarios/port-authority-surge-response.sdl.yaml) | IT/OT, customs, yard operations, and recovery scenario | Disk-backed example test; complex example checks for objectives, agents, relationships, content, stories, metrics, workflows, direct refs | Does not implement OT control, safety validation, or port operations |
| [`scenarios/techvault.sdl.yaml`](scenarios/techvault.sdl.yaml) | Runtime inventory and image provenance parity example | Disk-backed example test | Does not provide a deployable TechVault application or image build pipeline |

The tests are in
[`../implementations/python/tests/test_scenarios.py`](../implementations/python/tests/test_scenarios.py).

## Validate The Examples

From the Python implementation directory:

```shell
cd implementations/python
uv run --extra dev pytest tests/test_scenarios.py -q
```

For one file, use the parser boundary directly:

```python
from pathlib import Path

from aces_sdl import parse_sdl_file

scenario = parse_sdl_file(
    Path("../../examples/scenarios/port-authority-surge-response.sdl.yaml")
)
assert scenario.advisories == []
```

## How To Use These Files

Use the examples as references for current SDL shape:

- section structure
- stable identifiers and references
- variables
- workflows
- objectives
- entities and agents
- content and evidence-like scenario material
- runtime inventory fields where present

Check the section reference and limitations before adapting a file:

- [`../docs/explain/sdl/sections.md`](../docs/explain/sdl/sections.md)
- [`../docs/explain/sdl/validation.md`](../docs/explain/sdl/validation.md)
- [`../docs/explain/sdl/limitations.md`](../docs/explain/sdl/limitations.md)
- [`../docs/explain/sdl/testing.md`](../docs/explain/sdl/testing.md)

## Template Boundary

There are no placeholder templates in this directory. Files under
`examples/scenarios/` are positive SDL examples and must load successfully from
disk.

Do not add invalid or incomplete SDL files under `examples/scenarios/`.
Negative-path examples belong in focused parser, model, validator, contract, or
conformance tests.

Current gaps:

- no reusable participant-behavior template catalog
- no task template catalog
- no run template catalog
- no study template catalog
- no versioned pattern-library metadata

Those surfaces need current syntax, contracts, or validation rules before a
repository artifact can make a factual claim about them.
