# aces-sdl

A monorepo for ACES normative artifacts, portable contracts, conformance
assets, research, and reference implementations for the SDL ecosystem.

This repository is being reorganized so the language-agnostic,
backend-agnostic, and processor-agnostic work sits at the top level, while
reference implementations live under `implementations/`.

Breakage during the reorganization is expected. The goal of this pass is to put
the repo in the right shape, not to keep every existing import path, build
entrypoint, or helper script working during the transition.

## Top-Level Layout

- `specs/`: normative prose and formal specification material
- `contracts/`: machine-readable schemas, fixtures, and capability profiles
- `implementations/`: reference implementations and their local tests/tooling
- `examples/`: worked scenarios and other example artifacts
- `docs/`: explanatory material, architecture decisions, and migration notes
- `research/`: supporting literature and reference ecosystem material
- `tools/`: repository maintenance and migration helpers

## Current State

- The current Python reference implementation now lives under
  `implementations/python/`.
- Published contract assets now live under `contracts/`.
- Architecture decisions now live under `docs/decisions/adrs/`.
- Explanatory SDL/process documentation now lives under `docs/explain/`.

This repository is not a standards document. It is a working ecosystem repo
that is being structured so normative artifacts and implementation artifacts
are clearly separated while still standing on their own as a real, executable
system.

The working order for aligning the current implementation to that structure is
captured in [docs/decisions/adrs/adr-010-repository-realignment-order-and-compatibility-policy.md](docs/decisions/adrs/adr-010-repository-realignment-order-and-compatibility-policy.md).

The repository now treats several surfaces as distinct:

- the SDL and its authored scenario/experiment meaning
- processor behavior and manifests
- backend behavior and manifests
- participant implementations such as agents, policies, scripts, or
  human-control proxies
- live runtime/control-plane state
- archival run, evidence, and provenance artifacts

That separation is deliberate. It lets the same authored scenario be realized
through different backends, processed by different processors, and driven by
different participant implementations without silently changing what the SDL
itself means.
