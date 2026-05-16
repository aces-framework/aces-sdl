# Agentic Cyber Environment System

Agentic Cyber Environment System (ACES) is a backend-agnostic scenario
description language and reference runtime for cyber range scenarios and
experiments.

The repository separates authored scenario meaning from processors, backends,
participant implementations, runtime state, and archived evidence. That lets
the same scenario be validated and compiled without binding it to one cloud,
range implementation, or execution harness.

This is an academic and engineering project. The repository is intended to be
read, tested, and used as a working reference implementation, not treated as a
product surface.

## Contents

- [What ACES SDL Describes](#what-aces-sdl-describes)
- [Getting Started](#getting-started)
- [Using the Python Reference Implementation](#using-the-python-reference-implementation)
- [Repository Layout](#repository-layout)
- [Lineage](#lineage)
- [Documentation](#documentation)
- [Verification](#verification)
- [Contributing](#contributing)
- [Versioning](#versioning)
- [Citation](#citation)
- [License](#license)
- [Maintainer](#maintainer)

## What ACES SDL Describes

An SDL file is a declarative scenario document. It can describe topology,
hosts, services, identities, content, relationships, agents, objectives,
workflows, variables, and evaluation material without directly describing a
specific backend's infrastructure primitives.

```yaml
name: hospital-ransomware-surgery-day
description: Surgery-day ransomware exercise for a regional hospital.

variables:
  surgery_day_speed:
    type: number
    default: 1.0

nodes:
  internet-edge:
    type: Switch
    description: Public ingress for email, VPN, and external access

  mail-gateway:
    type: VM
    os: linux
    source: secure-mail-gateway
    resources: {ram: 2 gib, cpu: 1}
    services:
      - {port: 25, name: smtp-inbound}
    roles: {mail-admin: postfix}
```

Complete examples live in [`examples/scenarios/`](examples/scenarios/).

## Getting Started

Prerequisites:

- Python 3.11 or newer
- [uv](https://github.com/astral-sh/uv)
- [nox](https://nox.thea.codes/) for the repository verification graph, or
  `uvx nox` without a separate install

Set up the Python reference implementation:

```shell
git clone https://github.com/autarchy-ai/aces.git
cd aces/implementations/python
uv sync --all-extras
uv run aces --help
```

## Using the Python Reference Implementation

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

Run the CLI from `implementations/python`:

```shell
uv run aces sdl resolve ../../examples/scenarios/hospital-ransomware-surgery-day.sdl.yaml
uv run aces sdl verify-imports ../../examples/scenarios/hospital-ransomware-surgery-day.sdl.yaml
uv run aces sdl publish ../../examples/scenarios/hospital-ransomware-surgery-day.sdl.yaml
uv run aces processor --help
uv run aces conformance --help
uv run aces-mcp
```

## Repository Layout

- `specs/` - normative prose and formal specification material
- `contracts/` - published schemas, fixtures, manifests, and profiles
- `implementations/` - reference implementations and their local tooling
- `examples/` - worked SDL scenario examples
- `docs/` - explanatory documentation, API docs, and architecture decisions
- `research/` - supporting literature and reference ecosystem material
- `tools/` - repository maintenance, policy, and publication tooling
- `changelog.d/` - towncrier release note fragments

## Lineage

- [Open Cyber Range SDL](https://documentation.opencyberrange.ee/docs/sdl/reference/)
- [Open Cybersecurity Schema Framework](https://schema.ocsf.io/)
- [CACAO Security Playbooks v2.0](https://docs.oasis-open.org/cacao/security-playbooks/v2.0/security-playbooks-v2.0.html)
- [STIX 2.1](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html)
- [CybORG](https://github.com/cage-challenge/CybORG)
- [TENA](https://www.trmc.osd.mil/tena-about.html)
- [IEEE High Level Architecture](https://standards.ieee.org/standard/1516-2025.html)
- [SISO Cyber DEM](https://cdn.ymaws.com/www.sisostandards.org/resource/resmgr/standards_products/siso-std-025-2023_cyberdem.pdf)
- [SISO Cyber FOM](https://www.sisostandards.org/news/690125/Publication-of-Cyber-FOM-and-SIRL-Users-Guide.htm)
- [MITRE CALDERA](https://github.com/mitre/caldera)
- [Atomic Red Team](https://github.com/redcanaryco/atomic-red-team)

## Documentation

The documentation source is under [`docs/`](docs/). Important entry points:

- [`docs/index.md`](docs/index.md) - documentation index
- [`docs/explain/sdl/index.md`](docs/explain/sdl/index.md) - SDL guide
- [`docs/explain/sdl/runtime-architecture.md`](docs/explain/sdl/runtime-architecture.md) - runtime architecture
- [`docs/explain/reference/backend-conformance.md`](docs/explain/reference/backend-conformance.md) - backend conformance model
- [`docs/decisions/adrs/README.md`](docs/decisions/adrs/README.md) - architecture decisions
- [`contracts/README.md`](contracts/README.md) - contract publication surface

## Verification

`nox` is the canonical verification graph. From the repository root:

```shell
uvx nox -s verify
uvx nox -s tests
uvx nox -l
```

The full `verify` session runs the project checks expected for pull requests,
including repository policy, generated artifact checks, tests, and docs.

## Contributing

Contributions are welcome where they improve the language, reference
implementation, contracts, tests, examples, or documentation. Start with
[CONTRIBUTING.md](CONTRIBUTING.md).

Language and contract changes should be discussed before implementation because
small SDL changes can affect validation, generated schemas, backend
conformance, and existing scenario examples.

## Versioning

The Python package currently declares its version in
[`implementations/python/pyproject.toml`](implementations/python/pyproject.toml).
Release notes are collated from towncrier fragments in
[`changelog.d/`](changelog.d/). Do not hand-edit `CHANGELOG.md`.

## Maintainers

- Brad Edwards — [Personal GitHub](https://github.com/Brad-Edwards), [PANW GitHub](https://github.com/Brad-Edwards-SecOps), [LinkedIn](https://www.linkedin.com/in/bradley-edwards-dev/)

## Citation

If you use ACES SDL in academic work, cite the repository:

```bibtex
@software{aces_sdl,
  author       = {Edwards, Brad},
  title        = {ACES SDL: Backend-Agnostic Scenario Description Language for Cyber Range Experiments},
  year         = {2026},
  organization = {Autarchy},
  license      = {MIT},
  url          = {https://github.com/autarchy-ai/aces}
}
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
