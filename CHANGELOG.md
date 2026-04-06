# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-04-05

### Added

- Cross-artifact concept binding for v2 apparatus manifests (GOV-918).
  Backend and processor manifests now require a `concept_bindings` section
  that binds vocabulary fields to canonical concept families from the
  concept-authority catalog.
- `ConceptBindingEntryModel` Pydantic contract with pattern-validated
  `scope` and `family` fields.
- `ConceptFamilyId` pattern-constrained type for concept family identifiers.
- `ConceptBinding` frozen dataclass for runtime concept binding declarations.
- Invalid fixtures for missing, duplicate, and malformed concept bindings.
- Cross-catalog validation test confirming fixture bindings resolve to
  the authoritative concept-families-v1 catalog.

### Changed

- `BackendManifestV2Model` and `ProcessorManifestV2Model` now require
  `concept_bindings` with at least one entry.
- `BackendManifest` and `ProcessorManifest` frozen dataclasses now require
  `concept_bindings` tuple.
- Backend and processor manifest emission functions emit concept bindings.
- Updated all v2 manifest fixtures with concept binding declarations.
- Updated all v2 invalid fixtures to include concept bindings for single-concern testing.
- Regenerated backend-manifest-v2 and processor-manifest-v2 JSON Schemas.

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

[0.3.0]: https://github.com/aces-framework/aces-sdl/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/aces-framework/aces-sdl/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/aces-framework/aces-sdl/releases/tag/v0.1.0
