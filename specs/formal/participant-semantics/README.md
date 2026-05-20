# Participant Semantics Formal Design

This document is the issue #71 formal design artifact for:

- `SEM-208` - Participant Behavior Semantics
- `SEM-209` - Multi-Participant Interaction Semantics
- `SEM-210` - Visibility And Information-Boundary Semantics
- `SEM-211` - Participant Preconditions, Effects, And Failure Semantics
- `SEM-212` - Participant Causality And Attribution Semantics
- `SEM-213` - Temporal Participant Semantics
- `SEM-215` - Participant Outcome Interpretation Semantics

It is a design artifact, not an implementation artifact. It establishes the
semantic model that later child implementation issues must realize in SDL
models, semantic helpers, compiler/runtime contracts, evidence/provenance
contracts, and tests.

## Current Sufficiency Finding

The existing implementation is not sufficient for `SEM-208` through `SEM-215`.

What exists:

- `agents.*` declares participant framing inputs: `entity`, `actions`,
  `starting_accounts`, `initial_knowledge`, `allowed_subnets`,
  `starting_conditions`, `authority_anchors`, and `operating_scope`.
- ADR-020 defines identity, role, starting conditions, authority anchors, and
  operating scope as authored participant framing.
- ADR-013 and the participant-episode contracts define lifecycle state and
  history for initialization, reset, restart, termination, and terminal reason.
- Objective, workflow, assessment, planner, runtime-result, and semantic-profile
  surfaces already provide patterns for shared semantic helpers and contract
  boundaries.

What is missing:

- no normative participant action contract beyond action names
- no observation model that distinguishes world truth from participant-visible
  projection
- no visibility, discovery, concealment, disclosure, or inference semantics
- no precondition/effect/side-effect/failure taxonomy for participant actions
- no joint-action model for coordination, contention, interference, or
  shared-state change among participants
- no temporal participant behavior model for cadence, dwell, deadlines,
  latency, schedule, or time-windowed action interpretation
- no evidence-labeled causality and attribution model connecting participant
  actions to state changes, detections, alerts, or downstream outcomes
- no participant-local outcome interpretation layer relating action/episode
  outcomes to objectives, workflows, evaluations, rewards, and evidence

The repository is therefore correctly at `partial` design coverage after this
artifact, and not at implementation coverage.

## Primary-Source Review

### Agent Environment Interfaces

[OpenAI Gym](https://arxiv.org/abs/1606.01540) and
[Gymnasium](https://arxiv.org/abs/2407.17032) provide the standard single-agent
environment abstraction: observation, action, reward, termination/truncation,
reset, and reproducibility-oriented wrappers. They justify making participant
action, observation, reward, and episode concepts explicit.

[PettingZoo](https://papers.nips.cc/paper/2021/hash/7ed2d3454c5eea71148b11d0c25104ff-Abstract.html)
extends this ecosystem to multi-agent environments through the Agent Environment
Cycle model. It is a useful precedent for explicit per-agent turns and
multi-agent API consistency, but ACES cannot adopt a turn-only worldview because
real cyber ranges also need concurrent, asynchronous, and backend-realized
action ordering.

[OpenSpiel](https://arxiv.org/abs/1908.09453) is relevant because it supports
multi-player, cooperative, zero-sum, general-sum, perfect-information, and
imperfect-information games. It reinforces that information structure and game
form are part of the experiment definition, not incidental implementation
details.

### Partial Observability And Multi-Agent Control

Kaelbling, Littman, and Cassandra's POMDP treatment frames sequential action
under incomplete observation; the core lesson for ACES is that a participant's
observation stream is not the environment state. Local history and belief matter
when interpreting behavior.

Littman's Markov games and the Dec-POMDP/POSG literature generalize this to
multi-agent interaction. Bernstein, Zilberstein, and Immerman show that
decentralized control under partial observability is fundamentally harder than
centralized MDP/POMDP control. ACES should not pretend that one global state and
one global observation stream are enough for multi-participant experiments.

### Cyber Agent Environments

[CybORG](https://arxiv.org/abs/2108.09118) is the closest cyber-agent precedent.
It defines scenarios with agents, action spaces, observations, rewards, and
reset; it also supports simulation and emulation. Its reported sim-to-emulation
transfer failures are directly relevant: an agent can overfit to an observation
artifact that does not exist in the emulator. ACES must therefore record
observation provenance and realized backend disclosure, not just action results.

[CyberBattleSim](https://www.microsoft.com/en-us/research/project/cyberbattlesim/)
shows the value and limits of abstract cyber-network simulation. It is useful
for studying automated agents, but its high-level abstraction reinforces the
need to disclose which action/effect/observation semantics are realized rather
than assuming simulation results transfer to operational environments.

[CyGIL's unified emulation/simulation training design](https://arxiv.org/abs/2304.01244)
is relevant because it derives simulation transitions from emulated traces,
preserving the same action space across the sim-to-real loop. It motivates
ACES's requirement that action and observation contracts survive across backend
fidelity modes.

CyGIL also exposes a negative design lesson: an abstract action such as
"network discovery" is too coarse to transfer honestly to a real or emulated
network when concrete tools, parameters, network configuration, and observation
effects differ. ACES action contracts therefore need declared behavioral
granularity, procedure basis, and realization profile, not only a tactic or
technique label.

### Cybersecurity Agent Benchmarks

[Cybench](https://arxiv.org/abs/2408.08926) specifies CTF-derived tasks with
task descriptions, starter files, evaluators, executable environments,
observations, and subtasks. It is useful precedent for executable task
specification and partial-progress evaluation, but it also shows why hidden
answer keys, starter-file exposure, scaffold differences, and subtask guidance
must be part of the semantic and provenance record.

[AutoPenBench](https://arxiv.org/abs/2410.03225) adds penetration-test tasks,
gold steps, generic and specific milestones, autonomous and human-assisted
agent variants, and repeated execution. It reinforces that result
interpretation cannot be reduced to final flag capture: progress milestones,
human assistance, task memory, and run-to-run stochasticity are part of the
instrumentation.

[CAIBench](https://arxiv.org/abs/2510.24317) argues that isolated offensive,
defensive, static-knowledge, and execution-only benchmarks miss integrated
cybersecurity performance. Its Attack-and-Defense and privacy categories
reinforce ACES's role-neutral multi-participant model and the need to record
privacy/redaction semantics in observation and evidence surfaces.

[AI Agents That Matter](https://arxiv.org/abs/2407.01502) and the
[LLM offensive-security benchmarking-practices study](https://arxiv.org/abs/2504.10112)
are broader benchmark-methodology critiques. They motivate explicit holdout
discipline, anti-contamination controls, scaffold and cost/resource
provenance, baseline disclosure, and standardized run records. ACES does not
turn these papers into benchmark policy here, but participant semantics must
not make those controls impossible.

### Cyber Range Scenario Semantics

[Open Cyber Range SDL](https://documentation.opencyberrange.ee/docs/sdl/) is
the authoring-surface lineage for scenarios, but it does not provide the
participant behavior semantics required here.

[VSDL](https://arxiv.org/abs/2001.06681) gives formal meaning to cyber range
infrastructure through satisfiability constraints and solver-backed scenario
realization. It is strong precedent for formal scenario meaning, but its scope
is infrastructure constraints, not participant observations, causal
attribution, or multi-agent behavior.

CRACK's Datalog verification is similar prior art for executable cyber range
feasibility. It supports ACES's policy of making semantic claims checkable, but
does not remove the need for participant-specific semantics.

[CyRIS](https://www.jaist.ac.jp/~razvan/publications/cyris_facilitating_training.pdf)
is important because it automatically and repeatably creates cyber ranges from
YAML descriptions with topology, content, and security-incident features.
It strengthens the lineage for reproducible range construction, while also
showing the boundary of construction systems: repeatable deployment is not the
same as portable participant behavior, observation, causality, or outcome
semantics.

Ear, Remy, and Xu's automated cyber-range design framework
([arXiv:2307.04416](https://arxiv.org/abs/2307.04416)) treats range
architecture selection as an explicit requirements-matching problem. For ACES,
the lesson is that architecture, teaming model, fidelity, observability,
concurrency, resetability, and updateability are experiment requirements that
must be surfaced instead of disappearing into backend choice.

### Adversary Emulation And Security Events

The CALDERA planning-and-acting work argues that automated adversary emulation
is not only planning: adversaries interleave acting and sensing under open-ended
uncertainty. This motivates ACES's explicit distinction between actions that
change foothold, actions that change knowledge, and actions that do both.

[MITRE ATT&CK](https://www.mitre.org/news-insights/publication/mitre-attck-design-and-philosophy)
is an empirically grounded behavior vocabulary. It can classify participant
actions, but ATT&CK technique labels are not ACES action contracts.

[OCSF](https://ocsf.io/) provides vendor-neutral security event structure and
normalization. It is appropriate for observations, detections, findings, and
evidence references, but it is not a participant-visible-state model by itself.

[CACAO v2.0](https://docs.oasis-open.org/cacao/security-playbooks/v2.0/security-playbooks-v2.0.pdf)
separates workflows, commands, agents, targets, variables, and authentication
information. It is useful lineage for agent/target and action-step boundaries,
but ACES participant semantics must also handle observation, discovery,
concealment, and evaluation across heterogeneous participant implementations.

### Time, Ordering, And Causality

Lamport's happened-before relation establishes the key warning: distributed
systems have partial ordering, and physical timestamps alone are not the same as
causal ordering.

HLA time-management literature, Time Warp, DEVS, SimPy scheduling, ROS 2 clock
design, ns-3 realtime mode, and FMI all reinforce that clock authority, time
domain, advancement, pacing, synchronization, and event ordering are separate
semantic concerns.

[SISO Cyber DEM](https://cdn.ymaws.com/www.sisostandards.org/resource/resmgr/standards_products/siso-std-025-2023_cyberdem.pdf)
provides cyber objects and events for simulation interoperability. It supports
the idea that cyber events and effects need exchangeable representations across
simulation and range systems, but ACES still needs its own scenario/participant
semantics around those events.

Halpern and Pearl's structural-model causality motivates the attribution rule
in this spec: an observed alert after an action is not automatically caused by
that action. Causal claims require an evidence basis and, for strong claims, a
counterfactual or intervention model.

### DSL Evaluation And Language Critique

The software-language engineering evaluation literature warns that domain
familiarity is not enough to validate a DSL. Gabriel, Goulão, and Amaral's
[DSL evaluation review](https://arxiv.org/abs/1109.6794) specifically calls out
expressiveness, usability, effectiveness, maintainability, and domain-expert
productivity as concerns that can be skipped or relaxed. ACES's participant
semantics are therefore not academically complete if they only define a rich
semantic model; future child issues must also include authoring profiles,
examples, negative fixtures, and evidence that the notation can be used without
creating ambiguous or unreviewable experiments.

## Critical Re-Examination Against Known Failure Modes

The design above is necessary but not by itself sufficient. A critical reading
of existing SDLs, cyber-agent environments, and agent benchmarks identifies the
following failure modes that ACES must explicitly avoid.

| Failure mode | Direct evidence | Design correction |
| ------------ | --------------- | ----------------- |
| Prose-only or schema-only semantics | VSDL translates scenarios to SMT constraints; CRACK verifies SDL properties and tests deployed behavior against specification | Child implementations must publish executable contracts or abstract-state models plus negative fixtures; ADR prose and JSON-schema validation are not conformance |
| Deployment topology mistaken for experiment semantics | CyRIS, VSDL, CRACK, and automated range-design work focus on repeatable construction and feasibility | Participant semantics remain separate from deployment topology; backend realization, observation, causality, and outcomes require their own contracts |
| Technique labels treated as behavior | ATT&CK is a behavior vocabulary; CyGIL shows abstract cyber actions can fail to transfer to realistic networks | Action contracts carry behavioral granularity, procedure basis, realization profile, fidelity claims, and mapping-loss labels |
| Simulation and emulation observations conflated | CybORG reports agents overfitting to simulation-observation artifacts that were absent in emulation | Observation contracts record capture source, visibility basis, latency, capture granularity, loss/redaction, and realization profile |
| Flag success treated as full outcome meaning | Cybench uses tasks/subtasks/evaluators; AutoPenBench adds gold steps and milestones; CAIBench adds integrated A&D and privacy tasks | Outcome interpretation separates local action status, progress milestones, objectives, evaluations, rewards, evidence claims, privacy handling, and participant assistance |
| Benchmark contamination and hidden answer leakage | Cybench uses starter files, task servers, flags, and answer keys; broader agent-evaluation critiques identify weak holdouts and overfitting | Hidden truth, answer keys, canaries, holdout variants, public/private task material, and scaffold guidance are view-boundary objects with run/study provenance |
| Apparatus effects hidden from results | Cyber range architecture work treats monitoring, teaming, fidelity, concurrency, reset, and architecture as requirements | Evidence and observations disclose capture plane, observer effect, reset strategy, backend version, participant implementation, and unsupported guarantees |
| Language richness mistaken for language adequacy | DSL evaluation literature warns that expressiveness/usability/effectiveness/maintainability are often not evaluated | Future verification includes authoring-profile examples, ambiguity tests, round-trip tests, and domain-review evidence |

## Cross-Issue Coverage And Deferrals

The participant-semantics design intentionally remains partial for holistic
concerns that belong to other ACES design or evidence gates.

| Concern from the critique | Coverage after #71 | Owning issue(s) | Participant-semantics duty |
| ------------------------- | ------------------ | --------------- | -------------------------- |
| Scenario/run/study provenance | Partial | #87, #89, #105, #106 | Emit and consume named participant, action-contract, scaffold, backend, reset, and content-version provenance fields |
| Observability and evidence apparatus | Partial | #88, #127, #128, #170, #273 | Define participant observation/evidence semantics and disclose capture basis; defer full observability-plane design |
| Hidden truth, canaries, holdouts, answer keys, and adjudication assets | Partial | #125, #328, #333, #166 | Model participant visibility and leakage boundaries; defer benchmark asset lifecycle and corpus assurance |
| Trajectory, demonstration, replay, and dataset semantics | Partial | #124 and spawned trajectory issues | Preserve participant histories and local outcomes in a replay-compatible form |
| Backend realization and fidelity disclosure | Partial | #100, #165, #177, #239, #335 | Require action/observation realization profiles and mapping-loss labels |
| Machine-checkable semantic validation | Needs cross-gate evidence | #162, #168 | Provide participant-specific invariants and negative fixtures; do not treat ADR prose as conformance |
| DSL language adequacy | Needs dedicated evidence | #346 | Provide ambiguity, usability, maintainability, reviewability, and authoring-profile evidence for concrete syntax |

## Semantic Core

Let:

- `P` be the set of participants.
- `E_p` be the ordered set of episodes for participant `p`.
- `W_t` be the world state at logical instant `t`.
- `V_p,t` be participant `p`'s visible projection at logical instant `t`.
- `H_p,t` be participant `p`'s local history up to `t`.
- `A_p` be participant `p`'s available action contracts.
- `O_p,t` be observations delivered to participant `p` at `t`.
- `J_t` be the joint action set submitted or realized over an ordering
  interval containing `t`.
- `R_t` be the realized ordering relation for events in that interval.
- `X_t` be the archival evidence/provenance state at `t`.

World truth, participant-visible state, participant history, and evidence are
different objects. No implementation may substitute one for another without an
explicit semantics-preserving mapping.

### Participant Observation

An observation is a typed projection:

```text
Observation =
  participant_address
  episode_id
  observation_id
  observed_at
  source
  capture_basis
  capture_granularity
  capture_loss_model
  redaction_policy
  observer_effect
  visibility_basis
  subject_ref
  payload
  certainty
  latency
  disclosure_class
  evidence_refs
```

Observation invariants:

- `payload` is what the participant can receive, not necessarily what is true.
- `source` identifies the apparatus or scenario surface that produced the
  observation.
- `capture_basis` identifies the capture point or producer: participant
  surface, tool output, host telemetry, network sensor, backend adapter,
  evaluator, human input, synthetic disclosure, or replay.
- `capture_granularity`, `capture_loss_model`, `redaction_policy`, and
  `observer_effect` disclose whether the observation is complete, sampled,
  normalized, redacted, delayed, synthesized, or affected by the act of
  instrumentation.
- `visibility_basis` explains why the participant can see it: starting
  knowledge, operating scope, tool output, disclosure, inference,
  side-channel, deception, or backend-adapter disclosure.
- `latency` is part of observation meaning and may differ from event time.
- `evidence_refs` connect observations to archival evidence without disclosing
  hidden truth to the participant.

### Participant Action Contract

An action contract is a typed semantic object:

```text
ActionContract =
  action_id
  semantic_version
  action_kind
  behavior_granularity
  procedure_basis
  actor_scope
  target_scope
  parameter_schema
  preconditions
  effects
  side_effects
  failure_classes
  temporal_contract
  visibility_effects
  evidence_expectations
  external_mappings
  fidelity_claims
  realization_profile
  backend_realization_requirements
```

Action execution is a transition attempt:

```text
Attempt(p, e, a, args, t_submit)
  -> Realization(accepted | rejected, t_start?, t_end?, ordering_token?)
  -> Outcome(local_status, failure_class?, effects_observed, observations, evidence)
```

The action name in the current SDL is not enough to define this contract. A
future implementation must either resolve action names to governed action
contracts or fail closed when a participant action is referenced by semantics
that require a contract.

`behavior_granularity` distinguishes intent, tactic, technique, procedure,
tool invocation, command, and realized system effect. `procedure_basis` names
the evidence for the procedure, such as an ATT&CK technique, CVE, exploit
module, CACAO command, OpenC2 command, human runbook step, emulated trace, or
experiment-specific procedure. `external_mappings` are typed references with a
declared loss label; a mapping to ATT&CK, OCSF, CACAO, STIX, OpenC2, Cyber DEM,
Metasploit, or a benchmark milestone is not itself the ACES action semantics.
`fidelity_claims` and `realization_profile` distinguish portable intent from
simulation, emulation, live, human-mediated, or stubbed realization.

### State Transition

A participant action may produce any combination of:

- world-state mutation
- participant-local state mutation
- observation production
- evidence production
- disclosure or concealment change
- objective/workflow/evaluation refresh input
- no-op
- failed attempt
- unsafe withheld attempt

An action transition must not be treated as deterministic unless its contract
states so and the backend declares a realization profile that supports that
guarantee.

### Joint Action And Interaction

For an ordering interval `I`, a joint action set is:

```text
J_I = {Attempt(p_i, e_i, a_i, args_i, t_i)}
```

The processor/backend must assign or preserve a realized ordering relation
`R_I` that supports at least:

- happens-before edges required by participant episodes, workflows, and
  backend event delivery
- conflict/interference annotations
- simultaneity or concurrency claims only when supported by the backend
- explicit weakening when the backend serializes or drops concurrent attempts

Interaction classes:

- `coordination`: an action contract requires or synchronizes with another
  participant's action or state.
- `contention`: actions compete for an exclusive semantic resource.
- `interference`: one action changes another action's preconditions,
  observations, effects, or outcome.
- `shared_state_change`: multiple actions read or write the same object,
  contract surface, or evidence stream.

## Invariants

### I1 - Role-Neutral Participant Semantics

The semantic model applies to human participants, AI agents, scripts, playbooks,
simulated actors, and human-control proxies. Participant implementation type is
apparatus metadata, not a different semantic universe.

### I2 - Hidden Truth Boundary

World state and hidden benchmark assets must not be exposed as participant
observations unless an explicit disclosure rule permits it. Runtime evidence may
record hidden truth for adjudication without making it participant-visible.

### I3 - Observation Projection

An observation is never assumed to be complete truth. It has a source,
capture basis, visibility basis, latency, certainty, loss/redaction disclosure,
and evidence relationship.

### I4 - Fail-Closed Action Applicability

If an action's preconditions cannot be resolved or are not satisfied, the action
must be rejected, withheld, or marked unknown according to a declared failure
class. It must not silently execute under backend-local convention.

### I5 - Explicit Side Effects

Any participant action that may alter detection surface, telemetry, visibility,
shared state, or downstream objective/evaluation interpretation must declare
that class of side effect.

### I6 - Explicit Interaction Semantics

Coordination, contention, interference, and shared-state change must be visible
in the semantic model or provenance. Backend scheduler order must not be the
only record of interaction.

### I7 - Temporal Domain Separation

Episode step, scenario time, simulation time, backend time, and wall-clock time
are distinct. A deadline, dwell, cadence, timeout, or latency claim must name
the time domain and clock authority it uses.

### I8 - Ordering Before Causality

Causal attribution requires at least an ordering basis. A timestamp alone is not
enough; a happened-before, workflow, episode, or backend event-order relation
must be available.

### I9 - Evidence-Labeled Attribution

Attribution edges must declare their evidence strength: declared association,
temporal support, contract support, observation support, or counterfactual/
intervention support.

### I10 - Outcome-Layer Separation

Participant-local action status, episode terminal reason, objective success,
workflow state, evaluation result, and reward must remain separate until an
explicit interpretation rule relates them.

### I11 - Realization Disclosure

If a backend cannot realize a declared participant semantic guarantee, it must
fail capability validation or disclose the weaker realization before results are
used for comparison.

### I12 - Fidelity Claim Separation

A scenario may claim semantic portability without claiming fidelity
equivalence. Backends must disclose which behavior, observation, timing,
failure, and evidence guarantees are preserved, weakened, simulated, or
unavailable.

### I13 - Observation Apparatus Disclosure

Evidence and observations must disclose their capture basis, capture
granularity, loss model, redaction policy, and known observer effects.
Participant-visible observations must not be inferred from archival evidence
unless an explicit view rule permits that disclosure.

### I14 - External Mapping Loss Labels

Mappings to ATT&CK, OCSF, CACAO, STIX, OpenC2, Cyber DEM, CVE, Metasploit,
benchmark milestone, or other external vocabularies must declare whether the
mapping is exact, narrower, broader, approximate, lossy, or advisory.

### I15 - Run And Study Provenance

Claims spanning repeated runs, benchmark comparisons, ablations, or studies
require run-level provenance: scenario version, action-contract versions,
participant implementation version, backend version, reset strategy, random
seeds where applicable, scaffold/instruction disclosure, and relevant
environment fingerprints.

### I16 - Content And Contract Lifecycle

Participant action contracts, observation contracts, hidden assets, CTI-backed
labels, benchmark tasks, and external mappings are versioned content. They must
carry source, semantic version, freshness or validity basis, and deprecation or
replacement state when used for academic comparisons.

### I17 - Benchmark Leakage And Holdout Discipline

Hidden truth, answer keys, canaries, private references, task variants,
subtask guidance, public starter files, and adjudication material are
information-boundary objects. Their exposure or non-exposure must be recorded
as part of the participant view and run/study provenance.

### I18 - Language Evaluation Obligation

The participant-semantics language is not adequate merely because it is
expressive. Future concrete syntax and authoring profiles must be evaluated for
ambiguity, maintainability, domain-expert reviewability, and consistency across
examples, negative fixtures, and compiled contracts. Issue #346 tracks this as
a dedicated DSL language-evaluation evidence gate; this document only records
the participant-semantics obligation.

## SEM-208 - Participant Behavior Semantics

`SEM-208` requires explicit semantics for participant actions, observations,
state transitions, and role-neutral behavior interpretation.

Design commitments:

- behavior is modeled as episode-indexed action attempts and observation
  histories;
- actions resolve to action contracts, not untyped names;
- action contracts declare semantic version, behavioral granularity, procedure
  basis, realization profile, fidelity claim, and external mapping losses;
- observations are participant-specific projections of world/evidence state;
- state transitions can affect world state, participant-local state,
  observations, visibility, evidence, and outcome surfaces;
- behavior interpretation is role-neutral across participant implementation
  types.

Minimum future implementation artifacts:

- typed action/observation semantic helpers;
- participant behavior contract schemas;
- governed action-contract registry or equivalent source-of-truth mechanism
  with versioning, lifecycle state, and external mapping loss labels;
- validator checks for action contract references and observation-boundary
  declarations;
- compiler/runtime mapping from authored participants to participant contract
  addresses;
- cross-stage tests from SDL action declarations to compiled runtime contracts
  and observed participant history.

Current implementation artifacts for the `SEM-208` slice:

- `implementations/python/packages/aces_sdl/participant_behavior.py` defines
  typed action contracts and observation boundaries;
- `implementations/python/packages/aces_sdl/semantics/participant_behavior.py`
  and `implementations/python/packages/aces_sdl/validator.py` fail closed on
  unbound action-contract and observation-boundary references;
- `implementations/python/packages/aces_processor/compiler.py` maps authored
  participants to compiled participant action, observation, and behavior
  addresses;
- `implementations/python/packages/aces_processor/models.py` defines
  participant behavior-history events and validates action/observation/state
  transition totality over compiled addresses;
- `implementations/python/tests/test_sem_208_participant_behavior.py` covers
  the cross-stage SDL-to-runtime behavior-history path.

## SEM-209 - Multi-Participant Interaction Semantics

`SEM-209` requires semantics for coordination, contention, interference, and
shared-state change among concurrent participants.

Design commitments:

- multi-participant execution is modeled over joint action sets, not isolated
  single-agent steps;
- coordination, contention, interference, and shared-state changes are explicit
  interaction classes;
- realized ordering must be preserved or disclosed;
- backend simultaneity, serialization, lock, conflict, and dropped-action
  behavior are semantic guarantees, not adapter details;
- participant-local histories can differ even when they refer to one shared
  event.

Minimum future implementation artifacts:

- joint-action/interference formal invariants;
- runtime provenance fields for realized order and conflict semantics;
- property or differential tests for serializable vs non-serializable backend
  behavior;
- explicit simultaneity and conflict-resolution claims for backends that do
  not serialize joint action attempts.

Current implementation artifacts for the `SEM-209` slice:

- `implementations/python/packages/aces_sdl/participant_behavior.py` defines
  interaction classes, target references, related actions, and shared-state
  references on action contracts;
- `implementations/python/packages/aces_sdl/semantics/participant_behavior.py`
  and `implementations/python/packages/aces_sdl/validator.py` fail closed on
  unbound related actions, interaction targets, and shared-state references;
- `implementations/python/packages/aces_processor/compiler.py` carries declared
  interaction classes and shared-state references into compiled participant
  action contracts;
- `implementations/python/packages/aces_processor/models.py` records
  `joint_action_set_id`, `realized_order`, interaction class, interaction
  reference, and shared-state references in participant behavior history, and
  rejects duplicate realized orders within one joint action set;
- `implementations/python/packages/aces_conformance/conformance.py` applies the
  joint-action ordering invariant across participant-local histories in runtime
  snapshots.

This implementation follows the lineage above without adopting a framework
API: PettingZoo and OpenSpiel motivate preserving participant-local histories
and joint behavior as first-class data, while Lamport ordering motivates
recording realized order as provenance rather than treating timestamp adjacency
as causality. Cyber-agent systems motivate explicit action targets and
shared-state effects, but technique/tool labels remain external mappings, not
the ACES interaction semantics themselves.

## SEM-210 - Visibility And Information-Boundary Semantics

`SEM-210` requires semantics for what participants can observe, infer, conceal,
discover, or disclose over time.

Design commitments:

- visibility is an explicit view relation `V_p,t`, not a side effect of topology
  alone;
- initial knowledge, starting accounts, operating scope, authority anchors,
  tool outputs, telemetry streams, instructions, and hidden truth assets are
  distinct visibility inputs;
- public task statements, starter files, scaffold instructions, subtask
  guidance, private answer keys, canaries, and holdout variants are distinct
  information-boundary objects;
- discovery and disclosure are state transitions that alter future visibility;
- concealment and deception are permitted only when modeled explicitly;
- participant-visible artifacts and adjudication/evidence artifacts are
  separated.

Implemented transition discipline:

- `view_rules` define the initial view relation `V_p,0`; a transition
  `from_disposition` must match that current relation and cannot redefine the
  initial state;
- every `view_transition` carries an explicit integer `effective_order`, an
  `effective_from` label, a behavior-history anchor
  (`history_event_type`, plus `action_instance_id` except for `episode_close`),
  non-empty `evidence_refs`, `certainty`, and `latency_profile`;
- compiled participant observation boundaries sort transitions by
  `effective_order` and publish `view_relation_timeline` snapshots; dynamic
  discovery, inference, disclosure, concealment, and deception are read from
  those snapshots rather than from lifetime aggregate fields;
- runtime participant observation details that declare visible, disclosed, or
  evidence refs are checked against the compiled `V_p,t` snapshot derived from
  behavior-history anchors at or before the observation event, so future
  disclosure cannot justify earlier visibility;
- conformance diagnostics reject transition anchors that do not resolve to the
  corresponding participant behavior-history event; `episode_close` transitions
  resolve against terminal participant-episode history and do not authorize
  in-episode observation payloads.

Current implementation artifacts for the `SEM-210` slice:

- `implementations/python/packages/aces_sdl/participant_behavior.py` defines
  participant information-boundary classes, view dispositions, explicit view
  rules, time-indexed view transitions, realized-view disclosure metadata, and
  observation-boundary hidden, observable, and evidence-only reference
  separation;
- `implementations/python/packages/aces_sdl/semantics/participant_behavior.py`
  and `implementations/python/packages/aces_sdl/validator.py` continue to
  fail closed on unbound participant observation-boundary references, view-rule
  references, and view-transition evidence references;
- `implementations/python/packages/aces_processor/compiler.py` carries hidden,
  observable, discovered, inferred, concealed, disclosed, deceptive,
  evidence-only, and realized-view disclosure metadata into compiled
  participant observation boundaries, including an ordered
  `view_relation_timeline` snapshot series for `V_p,t`;
- `implementations/python/packages/aces_processor/models.py` exposes the
  compiled visibility metadata for runtime planning, snapshots, and
  conformance consumers, and validates observation detail refs against the
  corresponding timeline snapshot;
- `implementations/python/tests/test_sem_208_participant_behavior.py` covers
  leakage fixtures proving hidden truth cannot enter participant observations
  without an explicit disclosure rule, cannot be used as evidence without an
  evidence-only rule, cannot be inferred or disclosed through static metadata,
  and cannot be justified by a transition whose temporal order or runtime
  anchor is invalid.

This implementation slice enforces the reference-level visibility relation for
observation detail refs. The complete observation payload apparatus (`payload`,
capture basis, loss, redaction, latency, observer effects, and evidence-capture
adequacy) remains owned by the downstream observation/evidence requirements
listed in ADR-022 rather than being silently claimed by `SEM-210`.

## SEM-211 - Preconditions, Effects, And Failure Semantics

`SEM-211` requires semantics for action applicability, effects, side effects,
and failure classes.

Precondition classes:

- `authority`: participant may attempt this action under scenario meaning;
- `capability`: participant has a tool, role, implementation, or apparatus
  binding capable of this action;
- `target`: target exists and is in action scope;
- `knowledge`: participant has enough information to form the attempt;
- `resource`: budget, quota, credential, session, account, or tool state is
  available;
- `temporal`: schedule, cadence, dwell, deadline, or cooldown condition holds;
- `interaction`: required lock, coordination partner, or shared-state guard
  holds;
- `realization`: backend and participant implementation can realize the action.

Effect classes:

- `intended_effect`;
- `side_effect`;
- `observation_effect`;
- `visibility_effect`;
- `detection_effect`;
- `evidence_effect`;
- `no_effect`;
- `unknown_effect`.

Failure classes:

- `precondition_unsatisfied`;
- `unsupported_action`;
- `target_unavailable`;
- `authority_denied`;
- `resource_exhausted`;
- `timeout`;
- `interrupted`;
- `contention_lost`;
- `partial_success`;
- `unsafe_withheld`;
- `backend_error`;
- `unknown`.

Current implementation artifacts for the `SEM-211` slice:

- `implementations/python/packages/aces_sdl/participant_action_semantics.py`
  defines controlled precondition, effect, and portable failure vocabularies
  plus typed action-contract declarations and backend failure mappings;
- `implementations/python/packages/aces_sdl/participant_behavior.py` embeds
  those typed declarations in governed participant action contracts;
- `implementations/python/packages/aces_processor/compiler.py` carries the
  typed precondition classes, effect classes, failure classes, and backend
  failure mappings into compiled participant action contracts;
- `implementations/python/packages/aces_processor/models.py` defines typed
  action precondition results, action effect results, action results,
  fail-closed validation for unsatisfied or unresolved preconditions, behavior
  history action-result embedding, compiled-contract validation for declared
  effects and failure classes, and backend diagnostic mapping to portable
  failure classes;
- `implementations/python/packages/aces_contracts/contracts.py` publishes the
  action-result payload shape in the participant behavior-history and runtime
  snapshot schemas;
- `implementations/python/tests/test_sem_211_participant_action_semantics.py`
  covers positive contract compilation, controlled vocabulary rejection,
  fail-closed unresolved preconditions, portable failure round-tripping,
  participant-scope mismatch rejection, undeclared effect/failure-class
  counterexamples, required terminal action results, and backend diagnostic
  mapping.

## SEM-212 - Causality And Attribution Semantics

`SEM-212` requires semantics linking participant actions to observed state
changes, detections, alerts, and downstream outcomes.

Design commitments:

- attribution is an evidence-labeled edge, not an implicit consequence of time
  adjacency;
- every attribution edge names cause candidate, effect candidate, ordering
  basis, evidence basis, and confidence/strength;
- evidence basis includes the capture apparatus, granularity, loss model,
  redaction policy, and observer-effect disclosure for the evidence stream;
- strong causal claims require counterfactual, intervention, replay, ablation,
  or structural-causal evidence;
- weaker claims are allowed but must remain labeled as association, temporal,
  contract, or observation support;
- downstream objective/evaluation interpretation can consume attribution edges
  only according to explicit interpretation rules.

Minimum future implementation artifacts:

- attribution-edge contract;
- evidence-reference integration with observation and evaluation surfaces;
- tests that temporal adjacency alone cannot produce a strong causal claim;
- replay/ablation hooks when the backend supports stronger causal evidence.

## SEM-213 - Temporal Participant Semantics

`SEM-213` requires semantics for schedules, cadence, deadlines, dwell, latency,
and time-windowed participant behavior.

Design commitments:

- temporal claims name their time domain and clock authority;
- repeated-run and study-level temporal claims name reset strategy, replay
  boundary, randomization/seed basis, and backend pacing or synchronization
  guarantees;
- schedules define action eligibility windows;
- cadence defines repeated action/observation constraints;
- deadlines define latest acceptable realization or outcome times;
- dwell defines a minimum sustained condition over a named window;
- latency defines delay between cause/event/observation/action realization
  points;
- ordering and causality are separate from raw timestamp comparison;
- backend pacing/dilation/synchronization limitations must be disclosed.

Minimum future implementation artifacts:

- temporal participant contract fields aligned with the broader ACES time-model
  work;
- abstract state-machine model for deadlines, dwell, and timeout interaction;
- tests for ordering, delayed observation, and deadline/cadence edge cases.

## SEM-215 - Participant Outcome Interpretation Semantics

`SEM-215` requires semantics for interpreting participant-local outcomes and
relating them to scenario, objective, workflow, and evaluation meaning.

Design commitments:

- participant-local action outcome, episode status, objective success, workflow
  result, evaluation result, evidence claim, and reward are distinct;
- mappings between those layers are explicit interpretation rules;
- a local action success does not imply objective success;
- a local action failure may still create evidence, detection, alert, or
  reward-relevant behavior;
- reward is a derived training/evaluation signal unless declared otherwise by a
  governed assessment rule;
- participant outcomes must preserve enough provenance for replay and academic
  critique;
- progress milestones, subtasks, gold steps, human assistance, scaffold
  variants, cost/resource telemetry, and privacy/redaction results are outcome
  inputs only when declared by an interpretation rule; none substitutes for the
  full outcome model.

Minimum future implementation artifacts:

- outcome interpretation helper/contract;
- integration with objective and assessment semantics;
- tests for local-success/objective-failure and local-failure/evidence-success
  cases;
- evidence records that preserve participant-local outcome basis.

## Required Future Verification

The complete participant surface is `FM3`.

Future implementation PRs should include:

- invariant lists for each child UID;
- typed IR or published contracts for actions, observations, visibility,
  attribution, temporal clauses, and outcomes;
- abstract state-machine coverage for episode/action/observation/outcome
  progression;
- machine-checkable action, observation, visibility, failure, temporal,
  attribution, and outcome semantics; prose-only definitions are insufficient
  for conformance;
- property-based or differential tests for visibility, interaction, ordering,
  failure, and outcome interpretation;
- mapping-loss fixtures for ATT&CK, OCSF, CACAO, STIX, OpenC2, Cyber DEM, CVE,
  exploit-module, and benchmark-milestone bindings;
- observation-apparatus fixtures covering capture basis, sampling/loss,
  redaction, delayed disclosure, and observer-effect disclosures;
- hidden-answer, canary, holdout-variant, and starter-file leakage tests;
- run/study provenance fixtures covering reset strategy, seeds, backend and
  participant versions, scaffold disclosure, and content/action-contract
  versions;
- authoring-profile examples and ambiguity/usability review artifacts for the
  concrete syntax chosen by child implementation issues, coordinated with the
  DSL language-evaluation evidence gate in issue #346;
- cross-stage agreement tests spanning authoring, validation, instantiation,
  compilation, planning, execution, and observation;
- backend conformance fixtures demonstrating both supported and explicitly
  unsupported participant-semantic guarantees.

## Deliberate Non-Adoptions

- Do not adopt Gym/PettingZoo as the ACES runtime protocol. Use their concepts,
  not their API shape, as lineage.
- Do not treat CybORG action YAML as the ACES action contract. It is precedent
  for action/observation discipline and sim-to-emulation disclosure.
- Do not treat ATT&CK technique IDs as action semantics. They are behavior
  labels, not precondition/effect/failure contracts.
- Do not treat OCSF events as participant observations without an explicit view
  relation.
- Do not treat CACAO agents/targets as participant semantics. They are useful
  workflow and command-lineage objects.
- Do not treat Cyber DEM as the ACES scenario model. It is an exchange model for
  cyber simulation objects/events.
- Do not treat timestamp order as causal attribution.
- Do not treat CTF flag capture, subtask completion, or benchmark milestone
  progress as complete participant outcome semantics.
- Do not treat Docker/container reproducibility as run or study reproducibility
  without reset, seed, version, backend, scaffold, and hidden-asset provenance.
- Do not treat external CTI, CVE, exploit-module, or command names as portable
  behavior without an ACES action contract and loss-labeled mappings.

## References

- ADR-022: Participant Behavior and Interaction Semantics
- ADR-007: Lightweight Formal Methods Policy for Semantic Systems
- ADR-013: Participant Episode Lifecycle Boundaries
- ADR-016: Semantic Layer Scope and Coverage Model
- ADR-020: Declarative Participant Framing Boundaries
- [OpenAI Gym](https://arxiv.org/abs/1606.01540)
- [Gymnasium](https://arxiv.org/abs/2407.17032)
- [PettingZoo](https://papers.nips.cc/paper/2021/hash/7ed2d3454c5eea71148b11d0c25104ff-Abstract.html)
- [OpenSpiel](https://arxiv.org/abs/1908.09453)
- [Planning and Acting in Partially Observable Stochastic Domains](https://people.smp.uq.edu.au/YoniNazarathy/Control4406_2014/resources/KaelblingLittmanCassandra1998.pdf)
- [The Complexity of Decentralized Control of Markov Decision Processes](https://arxiv.org/abs/1301.3836)
- [CybORG](https://arxiv.org/abs/2108.09118)
- [CyGIL unified emulation-simulation training](https://arxiv.org/abs/2304.01244)
- [CyberBattleSim](https://www.microsoft.com/en-us/research/project/cyberbattlesim/)
- [Cybench](https://arxiv.org/abs/2408.08926)
- [AutoPenBench](https://arxiv.org/abs/2410.03225)
- [CAIBench](https://arxiv.org/abs/2510.24317)
- [AI Agents That Matter](https://arxiv.org/abs/2407.01502)
- [Benchmarking Practices in LLM-driven Offensive Security](https://arxiv.org/abs/2504.10112)
- [VSDL](https://arxiv.org/abs/2001.06681)
- [CyRIS](https://www.jaist.ac.jp/~razvan/publications/cyris_facilitating_training.pdf)
- [Automated Cyber Range Design](https://arxiv.org/abs/2307.04416)
- [Open Cyber Range SDL](https://documentation.opencyberrange.ee/docs/sdl/)
- [CRACK: Building next generation Cyber Ranges](https://iris.imtlucca.it/handle/20.500.11771/15672)
- [CACAO Security Playbooks v2.0](https://docs.oasis-open.org/cacao/security-playbooks/v2.0/security-playbooks-v2.0.pdf)
- [OCSF](https://ocsf.io/)
- [MITRE ATT&CK Design and Philosophy](https://www.mitre.org/news-insights/publication/mitre-attck-design-and-philosophy)
- [CALDERA planning and acting with unknowns](https://www.mitre.org/sites/default/files/2021-11/prs-18-0944-1-automated-adversary-emulation-planning-acting.pdf)
- [Halpern and Pearl, structural-model causality](https://arxiv.org/abs/cs/0011012)
- [Lamport, Time, Clocks, and the Ordering of Events](https://systems.cs.columbia.edu/ds2-class/papers/lamport-time.pdf)
- [IEEE HLA 1516 family](https://standards.ieee.org/ieee/1516/3744/)
- [SISO Cyber DEM](https://cdn.ymaws.com/www.sisostandards.org/resource/resmgr/standards_products/siso-std-025-2023_cyberdem.pdf)
- [Do Software Languages Engineers Evaluate their Languages?](https://arxiv.org/abs/1109.6794)
