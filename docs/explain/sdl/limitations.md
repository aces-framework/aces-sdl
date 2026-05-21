# SDL Limitations

## Known Expressiveness Gaps

These are known current gaps identified through repository tests, examples,
and stress testing against 19 scenarios from 8 platforms. The list is evidence
from the current corpus, not a completeness proof.

### Deployment Authoring Boundaries (by design)

The SDL distinguishes authored deployment intent from observed runtime facts.
Backends own deployment-specific mechanics such as Docker Compose
profiles, host port publication decisions, image build execution, and engine
realization. The node `runtime` surface can record observed runtime facts
for analysis and parity, including mounts, Linux capabilities, namespace modes,
entrypoints, image commands, extra hosts, DNS options, security flags, resource
limits, health status/logs, filesystem inventory, and the local identity
database (`/etc/passwd` users, `/etc/group` groups, and sudo/sudoers grants).
Container image build
provenance is a separate source-artifact expressivity surface tracked by issue
#364 and [ADR-023](../../decisions/adrs/adr-023-container-image-build-provenance-surface.md);
recording either surface in SDL does not make Docker, Compose, or any specific
container engine the normative deployment model.

### Specification-Layer Gaps

These are current SDL expressiveness gaps:

| Gap | Description | Candidate Precedent |
|-----|-------------|-------------------|
| **Hosted registry operations / ecosystem distribution** | OCI-backed module resolution, lockfiles, trust policy, and publishable image-layout packaging exist, but this repository does not operate a shared registry service, signer distribution, or ecosystem-wide discovery policy | Terraform registry, OCI artifact delivery |
| **Manual compensation APIs / advanced rollback patterns** | SDL workflows support explicit automatic compensation targets, reverse-completion rollback ordering, and cancel/timeout/failure compensation observation, but not manual rollback triggers, nested compensation-of-compensation, or richer exception-style recovery surfaces | CACAO v2.0 workflow types, saga compensation patterns |
| **Temporal operators** | STIX-style FOLLOWEDBY/WITHIN for time-ordered event assertions | STIX Patterning Language |
| **Full time and clock model** | The SDL currently exposes timelines, timeouts, and budget-like controls, but it does not provide a full authoring surface for time domains, clock authority, pacing/dilation policy, synchronization mode, or explicit ordering/deadline semantics across different realizations | Time-and-simulation primary references under `research/`, ROS 2 Clock and Time, FMI, ns-3 realtime, DEVS/time-management literature |
| **Full solver-backed verification** | Global proof-style verification that attack paths are reachable and defenses are consistent is not implemented; the repository uses lightweight semantic modeling, invariants, typed contracts, and selective property/state-machine methods | VSDL SMT solver, CRACK Datalog |
| **Full participant behavior surface** | The current `agents` section under-expresses richer role-neutral behavior concerns such as tool/affordance declarations, control-context assets, decision-surface exposure policies, episode structure, and benchmark-oriented participant assets | CybORG, OpenRange, Open Trajectory Gym |
| **Scenario-native observability and authored evidence requirements** | The ecosystem treats in-world observability systems and authored “capture these data from these sources” requirements as first-class concerns, but the current SDL syntax does not surface the full required authoring model | OpenRange, OCSF-informed telemetry models |
| **User behavior profiles** | Normal user activity patterns (browsing, email, file access schedules) | CybORG Green agents |
| **Multi-tenancy** | Multiple independent exercises sharing infrastructure | Locked Shields team-per-subnet model |

### Ecosystem-Layer Gaps (outside pure SDL syntax)

Some current requirement work is intentionally broader than SDL syntax alone.
These concerns are first-class ecosystem requirements, but they are
not fully materialized as published contracts and implementations:

- participant-implementation manifests for agents, policies, scripts, and
  human-control proxies
- participant-implementation provenance and exposure disclosure in run records
- fully materialized evidence-capture, augmentation-disclosure, and
  participant-exposure contract surfaces

These are not examples of backend leakage into the SDL. They are ecosystem
surfaces that sit alongside the SDL and must remain distinct from authored
scenario meaning.

### Variable Resolution

Variables (`${var_name}`) are stored as literal strings in the model. They are **not** resolved at parse time. This means:

- The validator can confirm that a full-value `${var}` reference has a matching variable definition
- Cross-reference rules that depend on a placeholder's final concrete value are deferred to the repo-owned instantiation phase
- Selected leaf enum-backed property fields are parameterizable, but discriminant/schema-shaping enums and user-defined mapping keys remain concrete
- Type checking of substituted runtime values happens during repo-owned instantiation, before compilation/runtime planning

This is a deliberate design choice (matching CACAO's model), but substitution
semantics are owned by the repo rather than left to backend-specific
interpretation.

## What Has Been Validated

The SDL has been tested against 19 scenarios from 8 platforms. This establishes
coverage over the listed examples; it does not establish general domain
completeness or usability for all cyber-range designs.

| # | Scenario | Source | Nodes | Services | Vulns |
|---|----------|--------|-------|----------|-------|
| 1 | OCR Full Exercise | OCR test suite | 3 | - | 1 |
| 2 | CybORG CAGE-1 | CAGE Challenge 1 | 7 | - | 2 |
| 3 | CybORG CAGE-2 (13-host) | CAGE Challenge 2 | 16 | - | 5 |
| 4 | CALDERA Ransack | CALDERA adversary | 0 | - | 0 |
| 5 | Atomic Red Team T1003 | Atomic tests | 0 | - | 0 |
| 6 | CyRIS DMZ | CyRIS | 7 | 3 | 2 |
| 7 | KYPO CTF | KYPO | 3 | - | 3 |
| 8 | HTB Machine | Hack The Box | 2 | 3 | 2 |
| 9 | Enterprise AD | Multi-domain lab | 10 | - | 6 |
| 10 | Cloud Hybrid | AWS VPC + on-prem | 9 | - | 3 |
| 11 | Exchange + data | SDL extended | 5 | 3 | 1 |
| 12 | CybORG with agents | CAGE-2 + agents | 9 | - | 1 |
| 13 | AD trust + federation | Multi-domain + vars | 6 | - | 2 |
| 14 | Incalmo Equifax | MHBench | 6 | 7 | 2 |
| 15 | NICE Challenge 17 | NICE/NIST | 6 | 9 | 3 |
| 16 | CCDC 2007 | Competition packet | 5 | 11 | 0 |
| 17 | HTB Offshore-style | ProLab | 6 | 11 | 6 |
| 18 | Metasploitable 2 | Classic lab | 2 | 23 | 11 |
| 19 | Locked Shields IT/OT | NATO exercise | 7 | 13 | 0 |

Additionally, a 28-node enterprise lab topology (4 networks, 17 health checks, 17 vulnerabilities) has been described in SDL and validated.

Property-based fuzz testing (Hypothesis) has run 1,050+ random inputs through the parser with zero unhandled crashes.
