# ADR-021: Falsification-First Claim Evidence Gate

## Status

proposed

## Date

2026-05-18

## Context

ACES is being developed with substantial agent assistance. Ordinary
architectural coherence is therefore insufficient evidence of maturity:
generated code, contracts, documentation, and tests can become internally
consistent while still failing the real claims the ecosystem depends on. The
current assurance policy maps change classes to verification artifacts, but it
does not require major maturity claims to be pre-registered as falsifiable
claims with objective evidence before those claims are asserted as demonstrated.

## Decision

Adopt a falsification-first evidence gate for major architecture and maturity
claims.

A claim is not demonstrated merely because the reference implementation, docs,
or positive-path tests are internally consistent. Each major claim must have a
claim statement, threat-to-validity notes, a falsification protocol, objective
pass/fail criteria, allowed and disallowed evidence sources, named evidence
artifacts, and an evidence status that distinguishes untested, partially
demonstrated, demonstrated, and refuted.

Claims that fail or remain untested must be described as such in maturity
summaries, release notes, and implementation planning.

## Consequences

This creates a stricter standard for saying ACES is backend-agnostic,
independently implementable, conformance-backed, provenance-honest, or
externally consumable.

It will produce more explicit failures and may slow claim promotion, but it
makes overclaiming harder and gives implementation work concrete evidence
targets instead of roadmap confidence.

## References

- ASR-530: Claim Falsification And Evidence Gate
- Issue #162: Claim falsification and evidence gate
