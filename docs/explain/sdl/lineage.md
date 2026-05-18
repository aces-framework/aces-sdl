# Lineage and Prior Work

ACES is not designed as a clean-room language. It is a consolidation layer over
cyber range SDLs, adversary emulation formats, agent-evaluation environments,
runtime architectures, and security event schemas that solve adjacent parts of
the same problem.

This page is a short map of the main influences. It is not a compatibility
claim, and it is not an exhaustive bibliography. For element-level provenance,
see [Design Precedents](precedents.md).

## Specification Surface

- [Open Cyber Range SDL](https://documentation.opencyberrange.ee/docs/sdl/reference/)
  is the closest direct SDL precedent. ACES starts from its author-facing
  section surface, including logical nodes, infrastructure, features,
  conditions, scoring concepts, entities, injects, events, scripts, and
  stories. ACES keeps the logical scenario surface separate from backend
  realization instead of treating the SDL as a deployment format.
- [Open Cybersecurity Schema Framework](https://ocsf.io/) influences the event
  and schema side of the architecture. Its schema, profile, extension, and
  attribute-dictionary model is the main precedent for portable telemetry and
  disciplined schema evolution.
- Domain-specific language work, especially the classic DSL literature and
  formal cyber-range DSLs such as VSDL and CRACK, informs the separation
  between concrete YAML syntax, semantic models, validation, compilation, and
  runtime contracts.

## Scenario Concepts

- [CACAO Security Playbooks v2.0](https://docs.oasis-open.org/cacao/security-playbooks/v2.0/security-playbooks-v2.0.pdf)
  informs variables, objective composition, workflow graph structure, and the
  distinction between authored playbook intent and concrete execution.
- [STIX 2.1](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html)
  informs typed directed relationships and cross-object references. ACES adapts
  that pattern for scenario elements rather than threat-intelligence objects.
- CyRIS, KYPO, OCR, VSDL, and CRACK are prior scenario-definition systems.
  Their strongest shared lesson is that scenario meaning must be more than a
  deployment script.

## Participant Semantics

- [OpenAI Gym](https://arxiv.org/abs/1606.01540),
  [Gymnasium](https://arxiv.org/abs/2407.17032),
  [PettingZoo](https://papers.nips.cc/paper/2021/hash/7ed2d3454c5eea71148b11d0c25104ff-Abstract.html),
  and [OpenSpiel](https://arxiv.org/abs/1908.09453) inform the agent-facing
  interface vocabulary: actions, observations, rewards, resets, local histories,
  imperfect information, and multi-agent interaction.
- POMDP, Dec-POMDP, POSG, and Markov-game literature is the theoretical lineage
  behind ACES's insistence that participant-visible observations are not world
  truth, and that multi-participant behavior cannot be reduced to a single
  centralized state stream.
- [CybORG](https://arxiv.org/abs/2108.09118),
  [CyberBattleSim](https://www.microsoft.com/en-us/research/project/cyberbattlesim/),
  and [CyGIL](https://arxiv.org/abs/2304.01244) are the cyber-agent environment
  precedents. They show the value of explicit
  action/observation/reward/episode interfaces, and also expose the
  sim-to-emulation gap that ACES must record through realization disclosure and
  evidence provenance.
- CALDERA adversary-emulation research informs the action semantics: cyber
  actions can change foothold, knowledge, observations, detection surface, and
  downstream outcomes under uncertainty.

## Benchmark And Experiment Lineage

- [Cybench](https://arxiv.org/abs/2408.08926) and
  [AutoPenBench](https://arxiv.org/abs/2410.03225) inform ACES's treatment of
  task descriptions, starter files, evaluators, subtasks, gold steps,
  milestones, human assistance, and repeated runs as experiment artifacts.
  ACES does not adopt flag capture or milestone completion as the complete
  outcome model; those are inputs to explicit interpretation rules.
- [CAIBench](https://arxiv.org/abs/2510.24317) motivates integrated offensive,
  defensive, privacy, and cyber-physical evaluation surfaces. ACES adapts this
  as role-neutral multi-participant semantics and privacy/redaction disclosure,
  not as a bundled meta-benchmark score.
- General agent-evaluation critiques such as
  [AI Agents That Matter](https://arxiv.org/abs/2407.01502) and
  [Benchmarking Practices in LLM-driven Offensive Security](https://arxiv.org/abs/2504.10112)
  motivate holdout discipline, anti-contamination controls, scaffold
  disclosure, baseline disclosure, cost/resource traces, and standardized run
  records. ACES records these as provenance and information-boundary concerns
  so downstream studies can audit what a participant actually could observe.

## DSL Evaluation Lineage

- [Do Software Languages Engineers Evaluate their Languages?](https://arxiv.org/abs/1109.6794),
  Mernik, Heering, and Sloane's
  ["When and How to Develop Domain-Specific Languages"](https://doi.org/10.1145/1118890.1118892),
  and Kosar, Bohra, and Mernik's
  ["Domain-Specific Languages: A Systematic Mapping Study"](https://doi.org/10.1016/j.infsof.2015.11.001)
  inform ACES's treatment of language adequacy as an evidence claim. A language
  can be domain-aware and formally specified while still failing on ambiguity,
  usability, effectiveness, maintainability, or domain-expert reviewability.
- Issue #346 tracks this as a dedicated evidence gate. It is related to
  authoring accessibility, formal validation, and participant semantics, but it
  is not discharged by any of those alone.

## Runtime, Time, And Causality

- [TENA](https://www.trmc.osd.mil/tena-about.html) and the
  [IEEE High Level Architecture](https://standards.ieee.org/ieee/1516/3744/)
  are the main runtime/federation precedents for distributed exercise services,
  time management, and object publication.
- [SISO Cyber DEM](https://cdn.ymaws.com/www.sisostandards.org/resource/resmgr/standards_products/siso-std-025-2023_cyberdem.pdf)
  and Cyber FOM are cyber-specific simulation-interoperability precedents.
- Lamport logical clocks, HLA time management, Time Warp, DEVS, SimPy, ROS 2
  time, ns-3 realtime mode, and FMI inform ACES's separation of timestamp,
  ordering, clock authority, pacing, synchronization, and causality.
- Halpern-Pearl structural causality informs ACES's treatment of attribution:
  a participant action followed by an alert is not automatically a causal
  explanation without an evidence basis.

## Adversary Emulation And Security Knowledge

- [MITRE ATT&CK](https://www.mitre.org/news-insights/publication/mitre-attck-design-and-philosophy),
  MITRE CALDERA, Atomic Red Team, and OpenC2 are adversary-emulation and
  command/response precedents. ACES treats them as behavior and execution
  sources that scenarios may bind to, not as replacements for the SDL.
- OCSF is the preferred lineage for normalized security event and finding
  structure. ACES uses that style for observations and evidence without making
  raw telemetry equal to participant-visible state.

## What ACES Adds

ACES separates authored scenario meaning, processor/runtime contracts, backend
realization, participant implementations, live state, and archival
evidence/provenance. The participant-semantics design extends that separation:
actions, observations, visibility, causality, temporal behavior, and outcomes
must be portable across human, AI-agent, scripted, simulated, and hybrid
participants without collapsing into any one backend or learning API.
