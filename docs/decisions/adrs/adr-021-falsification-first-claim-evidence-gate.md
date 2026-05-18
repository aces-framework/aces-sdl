# ADR-021: Falsification-First Claim Evidence Gate

## Status

proposed

## Date

2026-05-18

## Context

ACES is being developed with substantial agent assistance. That changes the
failure mode: code, contracts, documentation, and tests can become internally
consistent while still overstating what the ecosystem has actually proven.

The existing assurance policy classifies changes by formal-methods depth and
required verification artifacts. That is necessary, but it is not enough for
maturity claims such as:

- the SDL is backend-agnostic
- independent backends can implement ACES from published contracts
- backend conformance detects dishonest or incomplete capability claims
- authored, compiled, planned, realized, observed, and derived facts remain
  distinguishable
- processor artifacts are consumable without Python implementation internals

Those are claims about external credibility. They need falsification protocols
and evidence records, not just positive-path implementation tests.

## Decision

Adopt a falsification-first evidence gate for major architecture and maturity
claims.

A major claim is **untested** until it has:

1. a precise claim statement
2. explicit threats to validity
3. a falsification protocol
4. objective pass/fail criteria
5. allowed and disallowed evidence sources
6. named evidence artifacts
7. an evidence status

Evidence status values are:

- `untested` - no protocol has produced evidence yet
- `partial` - evidence exists but does not cover the full claim
- `demonstrated` - the protocol passed against named evidence artifacts
- `refuted` - the protocol failed or exposed a contradiction in the claim

The default status is `untested`. A claim never becomes `demonstrated` because
the architecture is coherent, because reference code passes its own happy-path
tests, or because docs describe the intended boundary.

When a claim is `untested`, `partial`, or `refuted`, maturity summaries, release
notes, and planning material must use that status rather than promote the claim
as demonstrated.

The first claim protocols are tracked as GitHub issues:

- independent backend implementability from published contracts
- backend conformance falsification of dishonest or incomplete claims
- backend substitution without SDL lock-in
- authored-vs-realized disclosure and provenance audit
- processor artifact consumability from published contracts without Python
  internals

## Consequences

### Positive

- ACES can no longer promote backend-agnostic or contract-first maturity claims
  solely from internal consistency.
- Failed protocols become actionable contract, fixture, diagnostic,
  documentation, or conformance gaps.
- Backend lock-in and hidden processor assumptions become testable failure modes.
- Maturity language becomes more honest: untested claims stay untested.

### Negative

- Some claims will remain visibly unproven for longer.
- Evidence collection becomes a first-class activity, not a side effect of
  implementation.
- Planning must distinguish building a feature from proving the claim that the
  feature supports.

### Risks

- If protocol issues become vague implementation trackers, the gate will lose
  force. Protocols must keep pass/fail criteria explicit and avoid designing the
  implementation under test.
- If evidence artifacts are not named and preserved, the same claim may be
  re-litigated without a durable record.
- If maturity summaries ignore claim status, the repository can drift back into
  confidence-based reporting.
