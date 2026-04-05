# Contracts

`contracts/` contains the machine-readable contract side of the repository.

The goal of this bucket is organizational clarity:

- `schemas/` contains published contract schemas
- `fixtures/` contains valid and invalid payload corpora for those contracts
- `profiles/` contains capability profile declarations

These assets are intentionally language-neutral. Any conformance runners or
implementation-specific validation helpers belong under `implementations/`,
not here.

This split follows the repository-structure decision captured in
[ADR-009](../docs/decisions/adrs/adr-009-normative-artifact-authority-and-repository-structure.md).
