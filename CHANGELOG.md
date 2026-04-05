# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-04

### Added

- Processor manifest declaration surface (`ProcessorFeature` enum,
  `ProcessorManifest` frozen dataclass, `ProcessorManifestModel` Pydantic
  contract) for declaring processor identity, supported language and contract
  versions, processing features, backend compatibility, and constraints
  (API-412).
- JSON Schema `processor-manifest-v1` published to
  `contracts/schemas/processor-manifest/`.
- Valid and invalid processor manifest fixtures in
  `contracts/fixtures/processor-manifest/`.
- Schema generation routing for processor manifest in
  `tools/generate_contract_schemas.py`.

## [0.1.0] - 2026-04-03

### Added

- Initial ACES SDL ecosystem extraction from APTL with SDL authoring layer,
  processor layer, backend protocols, conformance infrastructure, and CLI.

[0.2.0]: https://github.com/aces-framework/aces-sdl/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/aces-framework/aces-sdl/releases/tag/v0.1.0
