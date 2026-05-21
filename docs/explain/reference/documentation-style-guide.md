# Documentation Style Guide

This guide applies to prose documentation in this repository: root Markdown
files, `docs/`, `specs/`, `contracts/`, `implementations/`, and release-note
fragments.

The audience is technical and academic. Documentation describes the current
repository state. It is not a product page, roadmap, or funding document.

## Required Stance

- Be accurate before being persuasive.
- State limits, exclusions, and uncertainty directly.
- Prefer short declarative sentences.
- Use present tense for current behavior.
- Use normative language only for repository rules, specifications, contracts,
  and policies.
- Treat prior art as evidence or lineage, not as authority for ACES semantics.

## Prohibited Content

Do not add:

- marketing language
- sales claims
- vague praise
- unexplained superlatives
- roadmap claims
- timelines
- promises about planned behavior
- unsupported maturity claims

Avoid terms such as "powerful", "seamless", "world-class", "production-ready",
"comprehensive", "permanent", and "state of the art" unless the sentence
defines a measurable property and cites evidence.

## Current-State Claims

Every factual claim must be grounded in one of these sources:

- repository source code
- tests
- contracts or schemas
- normative specs under `specs/`
- ADRs under `docs/decisions/adrs/`
- primary external literature or standards

If a feature is absent, say so plainly. Do not imply planned support. Prefer
"not implemented" or "outside the current scope".

## Citations

Use citations for external technical claims, lineage claims, and terminology
borrowed from another system.

Prefer primary sources:

- standards and specifications from the maintaining body
- peer-reviewed papers or technical reports by the originating authors
- official project documentation or source repositories
- published schema catalogs from the maintaining project

Avoid secondary summaries when a primary source is available. If a secondary
source is the only available source, identify it as secondary.

Use inline Markdown links for short references. Use a `## References` section
when a document cites several sources.

## Primary Sources Already Used In This Repository

- [Open Cyber Range SDL](https://documentation.opencyberrange.ee/docs/sdl/)
- [CACAO Security Playbooks v2.0](https://docs.oasis-open.org/cacao/security-playbooks/v2.0/security-playbooks-v2.0.pdf)
- [STIX 2.1](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html)
- [OCSF](https://ocsf.io/)
- [CybORG](https://arxiv.org/abs/2108.09118)
- [CALDERA planning and acting with unknowns](https://www.mitre.org/sites/default/files/2021-11/prs-18-0944-1-automated-adversary-emulation-planning-acting.pdf)
- [IEEE HLA 1516 family](https://standards.ieee.org/ieee/1516/3744/)
- [SISO Cyber DEM](https://cdn.ymaws.com/www.sisostandards.org/resource/resmgr/standards_products/siso-std-025-2023_cyberdem.pdf)

## Terminology

- Define terms at first use when they are ACES-specific or overloaded in the
  literature.
- Use ACES terms consistently with the current specs, contracts, and code.
- Do not rename an external concept when citing a source.
- Do not import semantics from cited systems unless the ACES document states
  the adopted subset or difference.
- Distinguish authored scenario meaning, processor behavior, backend behavior,
  runtime state, and evidence artifacts.

## Structure

- Put the main claim first.
- Keep sections short.
- Use tables only when comparison is clearer than prose.
- Use examples only when they match current parser, schema, or contract
  behavior.
- Link to the closest authoritative repository artifact instead of restating
  long rules.

## Review Checklist

- Does the document describe current repository behavior?
- Are external claims cited to primary sources?
- Are limits and exclusions explicit?
- Are ACES terms used consistently with the specs, contracts, and code?
- Is all promotional or forward-looking language removed?
