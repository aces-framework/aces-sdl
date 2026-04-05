# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-04-05

### Added

- Canonical concept authority for cyber-domain meaning with three-layer model
  (concept authority, ACES concept, artifact binding), provenance categories
  (adopted/adapted/native), and 12 concept families mapped to UCO or
  ACES-native origins (GOV-917).
- JSON Schema `concept-families-v1` published to
  `contracts/schemas/concept-authority/`.
- Authoritative concept family catalog at
  `contracts/concept-authority/concept-families-v1.json`.
- Normative concept authority specification at
  `specs/concept-authority/concept-authority.md`.

## [0.2.0] - 2026-04-04

### Added

- Processor manifest declaration surface (`ProcessorFeature` enum,
  `ProcessorManifest` frozen dataclass, `ProcessorManifestModel` Pydantic
  contract) for declaring processor identity, supported language and contract
  versions, processing features, backend compatibility, and constraints
  (API-412).
- Reference processor manifest helpers and `aces processor manifest` CLI output
  for emitting the repo-owned processor declaration.
- JSON Schema `processor-manifest-v1` published to
  `contracts/schemas/processor-manifest/`.
- Valid and invalid processor manifest fixtures in
  `contracts/fixtures/processor-manifest/`.
- Schema generation routing for processor manifest in
  `tools/generate_contract_schemas.py`.
- Pre-commit hooks with ruff (lint + format), gitleaks (secrets), trailing
  whitespace, YAML/JSON checks, and pytest gate.
- GitHub Actions CI workflow with lint, test (coverage), fuzz, contract schema
  drift detection, and SonarCloud analysis.
- SonarCloud project configuration (`sonar-project.properties`).
- GitHub PR template and issue templates (bug report, feature request).
- Ruff linter and formatter configuration in `pyproject.toml`.

## [0.1.0] - 2026-04-03

### Added

- Initial ACES SDL ecosystem extraction from APTL with SDL authoring layer,
  processor layer, backend protocols, conformance infrastructure, and CLI.

[0.2.0]: https://github.com/aces-framework/aces-sdl/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/aces-framework/aces-sdl/releases/tag/v0.1.0
