# ADR-022: Participant Behavior and Interaction Semantics

## Status

proposed

## Date

2026-05-18

## Context

Issue #71 is the joint design surface for `SEM-208`, `SEM-209`, `SEM-210`,
`SEM-211`, `SEM-212`, `SEM-213`, and `SEM-215`. These requirements define a
single theory of participant behavior: actions, observations, state
transitions, visibility, failures, causality, time, interaction, and outcome
interpretation cannot be designed independently without semantic drift.

The current repository has two important adjacent pieces:

- `ACT-601` and ADR-020 define declarative participant framing in the SDL:
  identity, role, starting conditions, authority anchors, and operating scope.
- `RUN-311` and ADR-013 define participant episode lifecycle contracts:
  initialize, reset, restart, terminate, terminal reason, durable episode
  history, and stable participant address.

Those pieces are necessary but insufficient. The current `agents` model still
has only a list of action names, starting access/knowledge, and scope anchors.
The runtime participant-episode contract records lifecycle state, not the
semantic meaning of an action, observation, participant-visible state, conflict,
disclosure, causal attribution, timing, or participant-local outcome. The live
SEM-200 coverage table therefore correctly marks these participant families as
planned before this ADR.

The primary literature and standards point toward a disciplined middle ground:

- Formal cyber-range SDLs and construction systems such as VSDL, CRACK, and
  CyRIS show that scenario automation is not academically defensible without
  checkable meaning and deployed-behavior correspondence. They also show the
  boundary of construction-focused languages: repeatable deployment and
  topology feasibility do not define participant observations, causality,
  interaction, or outcomes.
- Gym, Gymnasium, PettingZoo, CybORG, CyberBattleSim, and CyGIL show the value
  of observation/action/reward/episode interfaces for learning agents, but also
  show why ACES cannot reduce participant semantics to one Gym-style API:
  cyber ranges have hidden truth state, human/script/agent participants,
  emulation/simulation gaps, real tools, backend-specific timing, and evidence
  requirements.
- Cybench, AutoPenBench, CAIBench, and broader agent-benchmark critiques show
  that benchmark instrumentation must distinguish public task statements,
  starter files, hidden answer keys, subtask guidance, human assistance,
  scaffolds, progress milestones, privacy handling, and run-to-run
  reproducibility. A final flag, reward, or score is not enough evidence for
  participant behavior claims.
- POMDP, Dec-POMDP, Markov-game, and game-environment literature provides the
  right conceptual vocabulary for partial observability, local histories,
  shared state, and multi-agent interaction, but ACES is not itself a policy
  optimizer. It needs portable experiment semantics, not an algorithmic
  commitment to any one solver or RL library.
- Automated adversary-emulation work, especially CALDERA planning-and-acting
  research, emphasizes that cyber actions often expand both foothold and
  knowledge under open-ended uncertainty; therefore action applicability,
  observations, failure, and discovery must be modeled explicitly.
- Lamport ordering, HLA time management, Time Warp, DEVS, SimPy, ROS 2 time,
  ns-3 realtime mode, FMI, and Cyber DEM all show that timestamps alone do not
  define ordering, causality, pacing, or synchronization in distributed and
  hybrid simulation/emulation systems.
- Halpern-Pearl structural causality is the right warning sign for attribution:
  "action X caused alert Y" is a causal claim requiring a model and evidence,
  not a consequence of temporal adjacency.
- OCSF, ATT&CK, CACAO, STIX, Cyber DEM, OpenC2, CVE, exploit modules, and
  benchmark milestones provide useful vocabularies for events, behavior,
  agents/targets, relationships, command/response boundaries, and procedures,
  but none is the ACES participant semantics by itself.
- DSL evaluation literature warns that a domain-specific language is not
  validated merely because it uses domain concepts. Future concrete syntax must
  be evaluated for expressiveness, usability, maintainability, ambiguity, and
  domain-expert reviewability.

## Decision

Adopt a participant-semantics model with six separations as the design baseline
for issue #71 and its child implementation issues.

### 1. Separate hidden world state from participant-visible state

ACES SHALL distinguish:

- **world state**: the backend/processor/evaluator truth model needed to run
  and assess the experiment
- **participant-visible state**: the projection visible to a participant at a
  specific episode step and time domain
- **participant belief/history**: what a participant has observed or been told,
  including stale, uncertain, deceptive, or later-refuted observations
- **archival evidence**: the run record used for replay, adjudication, and
  research review

Participant observations are projections or disclosures, not direct access to
world truth. A participant MAY discover, infer, conceal, or disclose
information only through explicit semantic rules and observed effects.

### 2. Treat action semantics as contracts, not names

A participant action is a semantic contract over:

- actor identity and episode
- action kind or capability
- target references
- parameters and non-secret argument shape
- preconditions
- intended effects
- side effects
- visibility/disclosure effects
- temporal contract
- failure classes
- observation and evidence expectations

The existing `agents.*.actions` list is therefore only an authoring affordance.
It cannot be the normative behavior model for `SEM-208` or `SEM-211`.

### 3. Model interaction through joint actions and shared-state effects

Multi-participant behavior is defined over a joint action set for an ordering
interval. The semantics must make these interaction classes explicit:

- **coordination**: actions require or synchronize with other participant
  actions
- **contention**: actions compete for an exclusive resource, lock, budget,
  target, account, channel, or authority
- **interference**: one action changes the preconditions, observations, or
  outcomes of another action
- **shared-state change**: multiple actions read or write the same semantic
  object or evidence stream

Backends must not hide interaction semantics behind "last writer wins" or
backend-native scheduler order. If a backend cannot provide simultaneous or
serializable joint-action semantics, it must disclose the realized order and
weakened guarantee in provenance.

### 4. Make information-boundary semantics first-class

Visibility is not just network reachability. The design treats each
participant's view as a time-indexed information boundary over:

- observable resources and telemetry
- known accounts, credentials, tools, files, and services
- disclosed instructions, policies, directives, hints, and task statements
- hidden truth assets, gold answers, private reference data, and adjudication
  material
- concealment, deception, delayed disclosure, and information revocation

This is an `FM2` graph/constraint surface and often an `FM3` stateful surface:
view membership changes over time and as a result of actions.

### 5. Require evidence-labeled causality and attribution

ACES SHALL distinguish weaker and stronger attribution:

- **declared association**: an author or adapter labels an action and outcome as
  related
- **temporal support**: the alleged cause precedes the alleged effect under an
  explicit ordering relation
- **contract support**: the action contract declares an effect compatible with
  the observed change
- **observation support**: evidence artifacts or event streams support the
  link
- **counterfactual or intervention support**: replay, ablation, holdout, or
  structural-causal evidence supports an actual-cause claim

Only the last class is a strong causal claim. Other classes are provenance or
correlation evidence and must be labeled as such.

### 6. Interpret participant-local outcomes separately from objectives

Participant-local action success, participant episode status, objective
success, workflow state, evaluation result, and reward are separate semantic
layers.

An action can succeed locally while an objective fails. An action can fail
locally but still produce a detection, alert, disclosure, or learning-relevant
trajectory. A participant can complete an episode while the scenario or
evaluation remains inconclusive. Outcome interpretation must therefore be an
explicit mapping from participant-local observations and action results into
scenario, objective, workflow, evaluation, evidence, and reward surfaces.

### Cross-cutting conformance obligations

ACES SHALL also require future child implementations to preserve the
participant-semantics critique in executable artifacts:

- action contracts carry semantic version, behavioral granularity, procedure
  basis, realization profile, fidelity claims, lifecycle state, and
  loss-labeled external mappings;
- observation and evidence contracts disclose capture basis, capture
  granularity, loss or sampling, redaction policy, latency, and known observer
  effects;
- run and study provenance records scenario/content/action-contract versions,
  participant implementation, backend realization, reset strategy, scaffold or
  instruction exposure, randomization/seed basis where applicable, and hidden
  asset policy;
- public starter material, private answer keys, canaries, holdout variants,
  adjudication references, and subtask guidance are information-boundary
  objects, not informal benchmark setup;
- conformance cannot rest on prose or schema acceptance alone. It requires
  typed contracts, state-machine or other machine-checkable semantic coverage,
  negative fixtures, and cross-stage agreement tests.

## Consequences

### Positive

- Issue #71 has one joint semantic model instead of seven drifting local
  designs.
- The design is role-neutral: humans, LLM agents, RL agents, scripts,
  playbooks, simulated actors, and human-control proxies can all occupy the
  same participant semantic role through different apparatus bindings.
- Observation and hidden truth are kept separate, reducing benchmark leakage
  and invalid evaluation claims.
- Multi-participant concurrency and interference become reviewable instead of
  backend-local side effects.
- Causal and attribution claims become auditable evidence claims rather than
  timestamp guesses.
- External mappings to ATT&CK, OCSF, CACAO, STIX, OpenC2, Cyber DEM, CVEs,
  exploit modules, and benchmark milestones become reviewable translations with
  declared loss instead of silent semantic substitutions.
- Run/study provenance, hidden-asset discipline, and scaffold disclosure become
  part of the participant semantics instead of benchmark-harness folklore.
- Temporal participant behavior can build on the broader ACES time-model work
  without prematurely collapsing all time domains into wall-clock timestamps.

### Negative

- Future implementation work must add more than SDL field validation. It needs
  typed semantic contracts, abstract state-machine coverage, evidence/provenance
  surfaces, and cross-stage agreement tests.
- Action and observation surfaces become versioned governed content; child
  issues must manage lifecycle, deprecation, and mapping-loss evidence instead
  of treating external vocabularies as stable semantics.
- The existing `agents` section remains intentionally incomplete until the
  child implementation issues publish concrete action/observation/visibility
  contracts.
- Backends that can currently expose only lifecycle state will need stronger
  capability and disclosure declarations before claiming participant-semantics
  conformance.

### Risks

- If action names are treated as behavior semantics, experiments will appear
  portable while hiding backend-specific action meaning.
- If observation equals truth, agent evaluations can leak hidden assets or make
  invalid claims about what a participant could know.
- If timestamps are treated as causality, multi-backend comparisons will be
  invalid when scheduling, latency, or clock authority differ.
- If reward is treated as the outcome, participant-local behavior will be
  optimized or interpreted against a training artifact rather than the scenario
  and evidence model.
- If causal claims are not evidence-labeled, downstream AI and AI-security
  papers may overstate what the instrumentation actually proves.
- If ATT&CK, CVE, exploit-module, command, or benchmark milestone labels are
  treated as action contracts, ACES will reproduce the procedure-fidelity gap
  seen in prior cyber-agent environments.
- If hidden answer keys, canaries, starter files, or subtask guidance are not
  modeled as information-boundary objects, agent evaluations can overfit,
  leak, or become impossible to audit.
- If the language is expressive but not evaluated for authoring ambiguity and
  domain-expert reviewability, it can still fail as experimental
  instrumentation.

## Required Formal Artifact

The formal design for this ADR lives in
`specs/formal/participant-semantics/README.md`.
It is the issue #71 design artifact and contains section-per-UID coverage for
`SEM-208`, `SEM-209`, `SEM-210`, `SEM-211`, `SEM-212`, `SEM-213`, and
`SEM-215`.

The intended future classification is `FM3` for the complete participant
surface: it includes state machines, multi-agent interaction, lifecycle
semantics, temporal ordering, result contracts, and evidence-linked
interpretation. Some child slices may land as `FM1` or `FM2`, but the complete
surface is not defensible without an abstract state-machine model and typed
contract coverage.

The ADR and formal README are not, by themselves, sufficient implementation
evidence. Future child issues must make the semantics executable through
contracts, invariants, model/state-machine coverage, negative fixtures,
backend-conformance fixtures, mapping-loss tests, leakage tests, and run/study
provenance checks.

## Cross-Issue Dependencies And Deferred Evidence

The critical review for issue #71 identified several concerns that are broader
than participant semantics. This ADR records them as dependencies or deferrals
instead of claiming that SEM-208 through SEM-215 solve them alone.

| Concern | Owning issue(s) | ADR-022 obligation |
| ------- | --------------- | ------------------ |
| Scenario/run/study provenance and comparability | #87, #89, #105, #106 | Require participant-semantics artifacts to name the provenance fields they consume or emit; do not define the whole study model here |
| Observability and evidence-capture adequacy | #88, #127, #128, #170, #273 | Require observation/evidence contracts to disclose capture basis, loss, latency, redaction, and observer effects |
| Benchmark hidden truth, gold standards, canaries, holdouts, and adjudication assets | #125, #328, #333, #166 | Treat these as information-boundary objects in participant views; defer asset lifecycle, corpus governance, and assurance protocols |
| Trajectories, demonstrations, replay, and participant datasets | #124 and its spawned trajectory issues | Require participant histories and outcomes to be compatible with replay/evidence needs; defer corpus/dataset semantics |
| Fidelity, backend realization, and sim/emulation transfer disclosure | #100, #165, #177, #239, #335 | Require action/observation contracts to state realization profiles and weakened guarantees |
| Machine-checkable semantic validation and evidence gates | #162, #168 | Require participant-specific invariants and negative fixtures; broader validation evidence remains under the falsification gates |
| DSL language adequacy and author/reviewer evaluation | #346 | Treat expressiveness, ambiguity, usability, maintainability, and domain-expert reviewability as evidence claims outside #71 |

This division keeps issue #71 focused on participant action, observation, state,
interaction, information-boundary, attribution, temporal, and outcome semantics.
It also prevents the design from using broader benchmark or language-evaluation
concerns as unverified claims.

## Non-Goals

- This ADR does not add SDL syntax or runtime code.
- This ADR does not claim `SEM-208` through `SEM-215` are implemented.
- This ADR does not make Gymnasium, PettingZoo, CybORG, CACAO, OCSF, ATT&CK,
  Cyber DEM, HLA, Cybench, AutoPenBench, CAIBench, or any other external system
  the normative ACES semantics.
- This ADR does not solve participant tool/affordance semantics, trajectories,
  budgets, quota/exhaustion, evidence-capture semantics, external knowledge
  bindings, or full clock-authority semantics beyond the portions needed for
  `SEM-208` through `SEM-215`.

## References

- Issue #71: Participant behavior and interaction semantics
- ADR-007: Lightweight Formal Methods Policy for Semantic Systems
- ADR-013: Participant Episode Lifecycle Boundaries
- ADR-016: Semantic Layer Scope and Coverage Model
- ADR-020: Declarative Participant Framing Boundaries
- [OpenAI Gym](https://arxiv.org/abs/1606.01540)
- [Gymnasium](https://arxiv.org/abs/2407.17032)
- [PettingZoo](https://papers.nips.cc/paper/2021/hash/7ed2d3454c5eea71148b11d0c25104ff-Abstract.html)
- [CybORG](https://arxiv.org/abs/2108.09118)
- [CyGIL unified emulation-simulation training](https://arxiv.org/abs/2304.01244)
- [CyberBattleSim](https://www.microsoft.com/en-us/research/project/cyberbattlesim/)
- [VSDL](https://arxiv.org/abs/2001.06681)
- [CyRIS](https://www.jaist.ac.jp/~razvan/publications/cyris_facilitating_training.pdf)
- [CRACK: Building next generation Cyber Ranges](https://iris.imtlucca.it/handle/20.500.11771/15672)
- [Automated Cyber Range Design](https://arxiv.org/abs/2307.04416)
- [Open Cyber Range SDL](https://documentation.opencyberrange.ee/docs/sdl/)
- [Cybench](https://arxiv.org/abs/2408.08926)
- [AutoPenBench](https://arxiv.org/abs/2410.03225)
- [CAIBench](https://arxiv.org/abs/2510.24317)
- [AI Agents That Matter](https://arxiv.org/abs/2407.01502)
- [Benchmarking Practices in LLM-driven Offensive Security](https://arxiv.org/abs/2504.10112)
- [CACAO Security Playbooks v2.0](https://docs.oasis-open.org/cacao/security-playbooks/v2.0/security-playbooks-v2.0.pdf)
- [OCSF](https://ocsf.io/)
- [MITRE ATT&CK Design and Philosophy](https://www.mitre.org/news-insights/publication/mitre-attck-design-and-philosophy)
- [CALDERA planning and acting with unknowns](https://www.mitre.org/sites/default/files/2021-11/prs-18-0944-1-automated-adversary-emulation-planning-acting.pdf)
- [Halpern and Pearl, structural-model causality](https://arxiv.org/abs/cs/0011012)
- [Lamport, Time, Clocks, and the Ordering of Events](https://systems.cs.columbia.edu/ds2-class/papers/lamport-time.pdf)
- [IEEE HLA 1516 family](https://standards.ieee.org/ieee/1516/3744/)
- [Do Software Languages Engineers Evaluate their Languages?](https://arxiv.org/abs/1109.6794)
- [SISO Cyber DEM](https://cdn.ymaws.com/www.sisostandards.org/resource/resmgr/standards_products/siso-std-025-2023_cyberdem.pdf)
