# Integration Lessons

This directory records integration findings from co-evolving ACES with
sibling research projects that consume the ACES contract surface as
backends. The first consumer is APTL (`Brad-Edwards/aptl`, sibling repo at
`../aptl`).

It is not a decision log. ADRs continue to record decisions; this directory
records the **post-decision evidence** that emerges when ACES's published
contracts, profiles, fixtures, and runtime model meet a real-world backend.
Findings here can produce follow-up issues, amendments to existing ADRs, or
new ADRs. The finding entry stays as the historical record.

## When To Write An Entry

Write a new entry when:

- A published contract surface (`backend-manifest-v2`, runtime envelopes,
  plan contracts, snapshot models) is ambiguous, incomplete, or implies
  something the conformance suite does not enforce.
- The published profile (`provisioning-only`,
  `orchestration-capable`, `orchestration-evaluation`,
  `full-remote-control-plane`) under-specifies or over-specifies what a
  real backend has to provide.
- The fixture corpus passes for a backend that's not actually production-
  conformant, or fails for a backend that is.
- The reference Python implementation (`aces_processor`,
  `aces_backend_stubs`, `aces_conformance`) makes an assumption the real
  backend can't honor.
- The `RuntimeTarget` / `RuntimeManager` API needs a shape change to
  accommodate a backend's actual lifecycle, capabilities, or failure
  modes.
- A piece of cross-repo coordination cost surprised you — naming, schema
  version handling, dependency pinning, release cadence.

Routine implementation work does not need an entry. Do not dilute the
signal.

## Convention

One Markdown file per finding, named `YYYY-MM-DD-<short-slug>.md`. Slug is
kebab-case; pick the noun the finding is about, not a verb.

Each entry's frontmatter:

```markdown
---
date: 2026-05-19
side: ACES | APTL | both
sibling_entry: <link to the matching entry in the sibling repo, if any>
follow_ups:
  - <repo>#<issue> — one-line description
adr_impact:
  - ADR-NNN — amendment / supersede / new ADR
contract_impact:
  - backend-manifest-v2 / runtime-snapshot-v1 / etc. — what changed or
    needs to change
profile_impact:
  - provisioning-only / orchestration-capable / etc. — capability profile
    affected, if any
---
```

Body sections (use the ones that apply, omit the rest):

- **Context** — what the backend was trying to do.
- **What we expected** — the contract surface's apparent promise, the ADR's
  claim, or the conformance suite's assumption going in.
- **What we found** — the actual behavior or shape from the integrating
  backend.
- **Decision** — what landed in the current PR. Use one of: `fix-in-aces`,
  `fix-in-backend`, `cross-repo-coordination`, `accept`, `escalate`. Do
  not use `defer` — record a `follow_ups` issue instead.
- **Why this side** — when fix could have landed on either repo, why we
  chose the one we did. ACES's bias should be toward fixing the contract
  surface (not papering over it in the backend), but evidence from the
  first backend integration is exactly the moment to question that bias.
- **Follow-ups** — issues opened on each side, with cross-references.

## Cross-Repo Symmetry

The sibling repository maintains the same convention at the same path
(`docs/lessons/`). Entries that describe the same finding from each side's
viewpoint should link to each other via the `sibling_entry` frontmatter
field. Do not assume a 1:1 mapping — many findings only need an entry on
one side.

## Why Not An ADR

ADRs answer "what did we decide and why." Lessons answer "what did we
discover when the decision met reality." Mixing the two pollutes the
decision record's signal: later readers cannot tell where the
authoritative position ends and the war stories begin.

## Why Not Issue Threads

Issue threads scroll, close, and rot. They live on a single repo with
unstable URLs, are gated by GitHub auth for some readers, and are not part
of the source-tree narrative. Lessons are durable next to the code that
embodies them.

## Relationship To The Reference Backend

`aces_backend_stubs` is the reference Python backend. When the same finding
applies to both the reference stub and a real backend, prefer recording it
on the ACES side with `contract_impact` / `profile_impact` populated, and
cross-link the backend repo's entry only when the backend-specific
adaptation cost is itself the lesson.
