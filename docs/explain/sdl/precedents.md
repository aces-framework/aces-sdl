# SDL Design Precedents

Every SDL element is adapted from an existing system or standard. This document traces each element to its source.

The SDL does not borrow every concern from the same place. In practice:

- the **section layout and author-facing YAML surface** start from Open Cyber
  Range SDL
- **exercise intent, variables, and workflow graph shape** draw primarily from
  CACAO
- **cross-object reference style** draws from STIX
- **control-flow semantics** are tightened using mature workflow and
  state-machine systems such as AWS Step Functions, Argo Workflows, and W3C
  SCXML
- **portable runtime/result contracts** follow the language-neutral boundary
  style used by systems such as Kubernetes, Temporal, and OpenC2

So the source tables below explain both where a section's author-facing shape
comes from and, where needed, which systems inform its execution semantics.

## Core Structure (from Open Cyber Range SDL)

The 14 base sections start from the [OCR SDL](https://github.com/Open-Cyber-Range/SDL-parser) v0.21.2 surface and are adapted into Python/Pydantic. This repository aims for coverage parity across the adopted OCR concepts while remaining its own SDL; when behavior diverges or OCR's own sources disagree, this document states repository behavior explicitly instead of making clone-level compatibility claims. The OCR SDL was developed by the Norwegian Cyber Range (CR14/NTNU).


| SDL Element                | OCR Source                | Changes                                             |
| -------------------------- | ------------------------- | --------------------------------------------------- |
| Scenario                   | `Scenario` struct         | Added SDL extension fields                          |
| Node (VM/Switch)           | `Node`, `VM`, `Switch`    | Added `os`, `os_version`, `services`, `asset_value` |
| Resources                  | `Resources`               | Human-readable RAM parsing via Python               |
| Role                       | `Role`                    | Direct port                                         |
| InfraNode                  | `InfraNode`               | Added `acls`, `internal` flag                       |
| Feature                    | `Feature`                 | Direct port                                         |
| Condition                  | `Condition`               | Added `timeout`, `retries`, `start_period`          |
| Vulnerability              | `Vulnerability`           | Direct port                                         |
| Metric/Evaluation/TLO/Goal | OCR scoring pipeline      | Direct port                                         |
| Entity                     | `Entity` + OCR entity surface | Direct port, including OCR fact maps            |
| Inject/Event/Script/Story  | OCR orchestration         | Direct port                                         |
| Source                     | `Source` (name + version) | Made provider-neutral                               |


## Extensions by Source

### From CybORG CAGE Challenge


| SDL Element             | CybORG Source                               | What We Adapted                               |
| ----------------------- | ------------------------------------------- | --------------------------------------------- |
| `Agent`                 | `Agents:` section (Scenario YAML)           | Actions, starting sessions, reward calculator |
| `InitialKnowledge`      | `INT:` (Initial Network Topology)           | Known hosts and subnets at start              |
| `Agent.allowed_subnets` | `AllowedSubnets:`                           | Network scope constraints                     |
| `AssetValue`            | `ConfidentialityValue`, `AvailabilityValue` | Extended to CIA triad                         |
| `ACLRule`               | `Subnets.NACLs`                             | Simplified from nested dict to flat rule list |
| `Objective.agent/actions` | Agent identity + action space             | Objective actor binding and optional action subset validation |


### From Newer Participant And Benchmark Ecosystems

These sources inform the newer participant-, benchmark-, and exposure-related
ecosystem surfaces. In many cases they are precedents for concerns the
requirements now recognize even when the current SDL syntax does not yet expose
the full shape directly.

| Concern | Primary Sources | What We Adapted |
| ------- | --------------- | --------------- |
| Participant decision surfaces and role-scoped observations | OpenRange episode/runtime model | Participant-visible decision context is treated as a first-class concern distinct from hidden truth assets and internal apparatus state |
| Control-context assets (instructions, directives, policies) | OpenRange prompt modes, agent-oriented benchmark/task systems | Execution-guiding context is modeled as a participant concern without binding the ecosystem to one prompting or policy framework |
| Trajectories, replay assets, and demonstration corpora | OpenRange training data, Open Thoughts Agent, Open Trajectory Gym | Stepwise participant interaction records are first-class experiment artifacts rather than incidental logs |
| Benchmark protocols, judges, verifiers, and rewards | OpenBench, Open Trajectory Gym, agent benchmark systems | Tasks, protocols, and evaluation components are treated as distinct experiment objects rather than hidden harness details |
| Hidden truth assets and adjudication surfaces | OpenRange private references, benchmark hidden tests/gold standards | Public task statements are kept distinct from hidden benchmark assets and adjudication material |
| Swappable participant implementations | Agent benchmark stacks, provider/model-selectable eval systems | Concrete agent/policy/script/human-control implementations are treated as apparatus surfaces distinct from SDL roles, processors, and backends |


### Participant Semantics Theory

Issue #71 adds a formal participant-semantics design in
`specs/formal/participant-semantics/` and ADR-022. These precedents inform that
design without becoming the ACES runtime API or authoring syntax.

| Concern | Primary Sources | What We Adapted |
| ------- | --------------- | --------------- |
| Single-agent episode interface | [OpenAI Gym](https://arxiv.org/abs/1606.01540), [Gymnasium](https://arxiv.org/abs/2407.17032) | Actions, observations, rewards, reset, termination, and truncation are explicit semantic concepts rather than incidental adapter methods |
| Multi-agent environment ordering | [PettingZoo](https://arxiv.org/abs/2009.14471), [OpenSpiel](https://arxiv.org/abs/1908.09453), Markov-game literature | Per-participant histories and information structure are first-class; joint behavior is not collapsed into one global action stream |
| Partial observability and local history | POMDP, Dec-POMDP, POSG, and imperfect-information game literature | Participant-visible state is a projection with history, uncertainty, latency, and disclosure basis, not world truth |
| Cyber-specific action/observation discipline | [CybORG](https://arxiv.org/abs/2108.09118), [CyberBattleSim](https://www.microsoft.com/en-us/research/project/cyberbattlesim/), [CyGIL](https://arxiv.org/abs/2304.01244) | Action/effect/observation semantics must disclose simulation, emulation, and realization assumptions instead of assuming transfer across fidelity modes |
| Adversary behavior under uncertainty | [CALDERA planning and acting](https://www.mitre.org/sites/default/files/2021-11/prs-18-0944-1-automated-adversary-emulation-planning-acting.pdf), [MITRE ATT&CK design](https://www.mitre.org/news-insights/publication/mitre-attck-design-and-philosophy) | Cyber actions may change foothold, knowledge, detection surface, and downstream outcomes; technique labels do not replace action contracts |
| Causality and temporal ordering | [Lamport ordering](https://systems.cs.columbia.edu/ds2-class/papers/lamport-time.pdf), [Halpern-Pearl structural causality](https://arxiv.org/abs/cs/0011012), HLA time management | Attribution edges require explicit ordering and evidence support; timestamp adjacency is not a causal claim |
| Checkable scenario semantics | [VSDL](https://arxiv.org/abs/2001.06681), [CRACK](https://iris.imtlucca.it/handle/20.500.11771/15672), [CyRIS](https://www.jaist.ac.jp/~razvan/publications/cyris_facilitating_training.pdf) | Participant semantics inherit the requirement for executable contracts and conformance tests, while staying separate from topology/deployment generation |
| Agent benchmark task structure | [Cybench](https://arxiv.org/abs/2408.08926), [AutoPenBench](https://arxiv.org/abs/2410.03225) | Task descriptions, starter files, evaluators, subtasks, gold steps, and milestones are treated as participant-view and outcome-interpretation inputs rather than hidden harness details |
| Integrated adversarial evaluation | [CAIBench](https://arxiv.org/abs/2510.24317) | Offensive, defensive, privacy, and cyber-physical capabilities require role-neutral multi-participant semantics and outcome layers richer than final score |
| Benchmark validity and overfitting controls | [AI Agents That Matter](https://arxiv.org/abs/2407.01502), [Benchmarking Practices in LLM-driven Offensive Security](https://arxiv.org/abs/2504.10112) | Run/study provenance, holdout discipline, scaffold disclosure, hidden assets, baselines, and cost/resource traces are experimental-instrumentation concerns |
| DSL language adequacy and evaluation | [Do Software Languages Engineers Evaluate their Languages?](https://arxiv.org/abs/1109.6794), [When and How to Develop Domain-Specific Languages](https://doi.org/10.1145/1118890.1118892), [Domain-Specific Languages: A Systematic Mapping Study](https://doi.org/10.1016/j.infsof.2015.11.001) | Issue #346 treats expressiveness, usability, effectiveness, maintainability, ambiguity, and domain-expert reviewability as evidence-gated language claims |


### From CyRIS


| SDL Element | CyRIS Source                              | What We Adapted                                   |
| ----------- | ----------------------------------------- | ------------------------------------------------- |
| `Content`   | `copy_content`, `emulate_traffic_capture` | Generalized to file/dataset/directory types       |
| `Account`   | `add_account`, `modify_account`           | Added groups, password_strength, SPN, auth_method |


### From STIX 2.1


| SDL Element                | STIX Source                             | What We Adapted                            |
| -------------------------- | --------------------------------------- | ------------------------------------------ |
| `Relationship`             | Relationship SRO (typed directed edges) | Simplified to 7 relationship types         |
| Cross-reference validation | STIX object referencing model           | Source/target resolve to any named element |


### From CACAO v2.0


| SDL Element           | CACAO Source                       | What We Adapted                                                        |
| --------------------- | ---------------------------------- | ---------------------------------------------------------------------- |
| `Variable`            | `playbook_variables`               | Types, defaults, allowed_values                                        |
| `${var}` substitution | CACAO variable substitution syntax | Deferred to instantiation time                                         |
| `Objective`           | agent/target/workflow context      | Declarative actor-target-window-success binding without runtime probes |
| `Workflow`            | workflow-step graph patterns       | Branching/parallel objective composition with SDL-only step types      |


### Control-Flow Semantics from Mature Workflow Systems

These sources do not define the YAML keys directly, but they strongly inform
how the runtime interprets workflow behavior after parsing.

| Concern | Primary Sources | What We Adapted |
| ------- | --------------- | --------------- |
| Conditional branching over declared predicates | AWS Step Functions `Choice`, CACAO conditional steps | Explicit decision nodes with typed predicate dependencies instead of backend-local branching rules |
| Parallel branch execution and convergence | AWS Step Functions `Parallel`, W3C SCXML `parallel`, Argo DAG fan-out/fan-in patterns | Parallel branches are explicit, joins are explicit barriers, and foreign entry into a join is rejected |
| Retry and terminal outcome meaning | AWS Step Functions `Retry`/`Catch`, Argo retry strategy | Retry behavior is part of workflow semantics rather than a hidden adapter loop |
| Observable step state | Step Functions execution-visible state, SCXML completion semantics | Only selected step kinds expose portable lifecycle/outcome state for predicates and backend results |
| Workflow semantics as a first-class assurance surface | SCXML state-machine model, Kepler FM guidance for workflows/state machines | Workflow changes are treated as `FM3` state-machine work, not just parser changes |


### Runtime Boundary and Contract Precedents

These sources inform the runtime/result contract rather than the SDL YAML
surface.

| Concern | Primary Sources | What We Adapted |
| ------- | --------------- | --------------- |
| Language-neutral backend boundary | Kubernetes API objects, Temporal payload/history model, OpenC2 abstract model + JSON serialization | Backends exchange plain-data, versioned workflow result envelopes rather than Python object identity |
| Explicit compiled contract between definition and execution | Kubernetes versioned object schemas, Temporal workflow definition vs event-history separation | Compiler emits a dedicated `result_contract` instead of forcing the manager to infer semantics from incidental planner payloads |
| Internal typed adapters behind a plain-data boundary | Temporal SDK data conversion, Kubernetes typed models over portable representations | Python typed workflow result models are internal normalization helpers, not the backend protocol |
| Distinct apparatus declaration surfaces | OpenRange episode/runtime split, OpenBench model/provider configuration, benchmark registries | Processor, backend, and participant-implementation declaration surfaces remain distinct so the same scenario can be run under different apparatus honestly |


### From Time, Simulation, and Co-Simulation Systems

These sources inform the emerging time-model requirements. They are not a
claim that ACES adopts one simulator's worldview wholesale. They are precedents
for the recurring architectural concerns that show up once scenarios must run
honestly across simulation, emulation, and live infrastructure.

The primary research set for this area is curated in
`research/primary/literature/time-and-simulation/`.

| Concern | Primary Sources | What We Adapted |
| ------- | --------------- | --------------- |
| Distinct time domains and clock authority | [ROS 2 Clock and Time](https://design.ros2.org/articles/clock_and_time.html), [FMI 3.0.2](https://fmi-standard.org/docs/3.0.2/) | Authored temporal intent and realized clocks cannot be treated as the same thing; multiple clocks and explicit clock authority are first-class concerns |
| Event-driven, logical, and virtual time progression | [SimPy Time and Scheduling](https://simpy.readthedocs.io/en/4.0.2/topical_guides/time_and_scheduling.html), Misra virtual-time work, DEVS literature | Time advancement policy is part of system meaning, not just a backend optimization |
| Real-time pacing and synchronization | [ns-3 realtime execution](https://www.nsnam.org/docs/manual/html/realtime.html), adaptive time-dilation work for integrated simulation/emulation | Synchronization policy, pacing, and dilation are apparatus properties that affect experiment validity and comparability |
| Ordering and causality beyond raw timestamps | Time Warp, DEVS, distributed-simulation time-management literature | Event order, causality guarantees, and temporal windows/deadlines must be modeled separately from the existence of timestamps |
| Reset, replay, and episode-local temporal semantics | OpenRange episode model, benchmark/task systems, simulation literature | Episode boundaries, reset semantics, and replayability are temporal concerns, not just lifecycle bookkeeping |
| Realized-time disclosure and provenance | OpenRange run/training-data records, co-simulation timing literature | Runs need explicit disclosure of the realized time model when results are compared across backends or replayed later |


### From OCSF


| SDL Element     | OCSF Source         | What We Adapted                  |
| --------------- | ------------------- | -------------------------------- |
| `OSFamily` enum | `Device.os.type_id` | Vocabulary for OS classification |
| `ServicePort`   | `NetworkEndpoint`   | Simplified port/protocol/name; named bindings become first-class refs |


### From Docker / Deployment Patterns


| SDL Element                              | Source                          | What We Adapted              |
| ---------------------------------------- | ------------------------------- | ---------------------------- |
| `SimpleProperties.internal`              | Docker Compose `internal: true` | Network egress blocking flag |
| `Condition.timeout/retries/start_period` | Docker health check fields      | Direct mapping               |


## Deliberate Omissions

These were considered and explicitly excluded:


| Concept                                 | Why Excluded                       | Where It Belongs                       |
| --------------------------------------- | ---------------------------------- | -------------------------------------- |
| Port mappings (host:container)          | Backend-specific deployment detail | Backend implementation layer           |
| Volume mounts                           | Backend-specific deployment detail | Backend implementation layer           |
| Linux capabilities (NET_RAW, SYS_ADMIN) | Backend-specific security config   | Backend implementation layer           |
| Docker Compose profiles                 | Backend-specific grouping          | Backend implementation layer           |
| Dockerfile/build context                | Backend-specific build detail      | Backend implementation layer           |
| Container entrypoints                   | Backend-specific runtime config    | Backend implementation layer           |
| Framework-specific participant APIs | Framework coupling | Integration adapters outside the core SDL/runtime |
| Terraform module composition            | Import, version, namespace, parameter, locking, and packaging patterns | Implemented as deterministic SDL module/import expansion with OCI packaging, lockfiles, and trust policy |
| Full CACAO workflow surface             | Current SDL now covers decisions, switch/case routing, reusable workflow calls, retries, explicit joins, cancel/timeout lifecycle contracts, and explicit compensation targets/order | Future: richer exception control and compensation-of-compensation semantics |
| Full Step Functions / SCXML execution model | Current SDL adopts only the parts needed for objective-centric branching, retry, and explicit joins | Future: richer workflow/event semantics if the SDL grows beyond current scope |
| VSDL SMT verification                   | Too heavyweight for broad default use today | Selective future extension beyond the lightweight formal-methods policy |
