# Reconstructed Work Order After GOV-917

Date reconstructed: 2026-04-05

This note captures the most likely intended requirement order immediately after
the `GOV-917` canonical concept authority work, based on repository state,
ADR text, Ground Control requirement records, and recoverable Cursor workspace
metadata.

## Likely intended side sequence

The strongest evidence indicates that work was meant to continue briefly in the
`GOV-917` follow-on cluster before returning to the broader repository
realignment order:

1. `GOV-917` Canonical Concept Authority For Cyber-Domain Meaning
2. `GOV-918` Cross-Artifact Concept Binding
3. `GOV-919` ACES Extension Discipline Over Shared Concept Authorities
4. `GOV-920` Shared Semantic Profiles
5. `GOV-921` Shared Reference Models
6. `GOV-922` Controlled Vocabularies And Enumerations

There is also evidence that the concept-authority line expanded further the
same day into:

7. `GOV-923` Gateway And Bridge Contracts
8. `GOV-924` Translation-Path Provenance And Validation
9. `GOV-925` Standards Profiles And Compatible Stack Recommendation
10. `GOV-926` Federation-Level VV&A And Accreditation Basis

## Return to ADR-010 order

After the concept-authority side sequence, the intended return path appears to
be the explicit ordering from ADR-010:

1. `API-412` and `API-413`
2. `RUN-300` and related runtime/control-plane requirements
3. `RUN-313`, `RUN-314`, and `RUN-315`
4. Remaining unfinished `SEM-*` work
5. Deferred broader `API-400` expansion surfaces

## Why this reconstruction is likely correct

- `GOV-917` was implemented in commit `8ccd1b1` on 2026-04-05.
- The branch name for that work is `486-canonical-concept-authority-for-cyber-domain-meaning`.
- The concept-authority spec and design note both explicitly split the related
  follow-on problem into `GOV-918` through `GOV-922`.
- In Ground Control, `GOV-918` through `GOV-926` were created immediately after
  `GOV-917` on 2026-04-05, suggesting they were intentionally queued as a
  coherent cluster.
- ADR-010 still provides the standing post-realignment requirement order:
  `API-412`/`API-413`, then `RUN-300`, then `RUN-313`/`RUN-314`/`RUN-315`,
  then remaining `SEM-*`, then deferred `API-400` children.

## Caveat

The newest Cursor conversation body was not recoverable as a full transcript.
Cursor preserved workspace/session metadata for `aces-sdl`, but the relevant
agent transcript append path was failing, so this note is a reconstruction from
repo artifacts and Ground Control rather than a verbatim chat record.
