# SDL Sections Reference

A scenario is a YAML document with a required top-level `name`, optional
top-level composition fields (`version`, `module`, `imports`), and up to 21 named SDL
sections. Aside from `name`, all sections are optional.

Top-level composition fields are:

- `version` — scenario or module version
- `module` — optional publishable module descriptor (`id`, `version`, `parameters`, `exports`, `description`)
- `imports` — optional module imports using backward-compatible `path:` or canonical `source:`

Canonical `imports.source` classes are:

- `local:...` for repo-local files
- `oci:...` for remote OCI-packaged modules
- `locked:...` for lockfile-resolved concrete imports

## Section Overview

### From Open Cyber Range SDL (14 sections)

| Section | Type | Purpose |
|---------|------|---------|
| `nodes` | `dict[str, Node]` | VMs and network switches — the compute/network topology |
| `infrastructure` | `dict[str, InfraNode]` | Deployment topology: counts, links, dependencies, IP/CIDR, ACLs |
| `features` | `dict[str, Feature]` | Software (Service/Configuration/Artifact) deployed to VMs |
| `conditions` | `dict[str, Condition]` | Health checks (command+interval or library source) |
| `vulnerabilities` | `dict[str, Vulnerability]` | CWE-classified vulnerabilities assigned to nodes/features |
| `metrics` | `dict[str, Metric]` | Scoring: Manual (human-graded) or Conditional (automated) |
| `evaluations` | `dict[str, Evaluation]` | Metric groups with pass/fail thresholds |
| `tlos` | `dict[str, TLO]` | Training Learning Objectives linked to evaluations |
| `goals` | `dict[str, Goal]` | High-level goals composed of TLOs |
| `entities` | `dict[str, Entity]` | Teams, organizations, people (recursive, with exercise roles) |
| `injects` | `dict[str, Inject]` | Actions between entities during exercises |
| `events` | `dict[str, Event]` | Triggered actions combining conditions + injects |
| `scripts` | `dict[str, Script]` | Timed event sequences with human-readable durations |
| `stories` | `dict[str, Story]` | Top-level exercise orchestration grouping scripts |

### Extended Sections (7 sections)

| Section | Type | Purpose | Adapted From |
|---------|------|---------|--------------|
| `content` | `dict[str, Content]` | Data placed into systems (files, datasets, emails) | CyRIS `copy_content` |
| `accounts` | `dict[str, Account]` | User accounts on nodes (AD users, SSH, DB users) | CyRIS `add_account` |
| `relationships` | `dict[str, Relationship]` | Typed edges between elements (auth, trust, federation) | STIX Relationship SRO |
| `agents` | `dict[str, Agent]` | Autonomous participants (actions, knowledge, scope) | CybORG Agents |
| `objectives` | `dict[str, Objective]` | Declarative experiment tasks binding actors, targets, windows, and success | OCR scoring + CACAO action/target/agent |
| `workflows` | `dict[str, Workflow]` | Branching and parallel control graphs over declared objectives | CACAO workflow graph patterns; semantics tightened using Step Functions / Argo / SCXML style control-flow rules |
| `variables` | `dict[str, Variable]` | Parameterization (types, defaults, substitution) | CACAO playbook_variables |

---

## Nodes

Nodes are the compute and network elements of the scenario.

```yaml
nodes:
  corp-switch:
    type: Switch
    description: Corporate LAN

  web-server:
    type: VM
    os: linux                           # windows, linux, macos, freebsd, other
    os_version: "Ubuntu 22.04"
    source: ubuntu-22.04                # provider-neutral image reference
    resources:
      ram: 4 GiB                        # human-readable: GiB, MiB, GB, MB
      cpu: 2
    features:                           # dict form: {feature: role} or list form: [feature]
      nginx: web-admin
    conditions:
      web-health: web-admin
    vulnerabilities: [sqli, xss]
    roles:
      web-admin: www-data               # shorthand: role: username
      operator:                         # longhand
        username: ops
        entities: [blue-team.alice]     # binds to entity
    services:                           # exposed network services
      - port: 80
        protocol: tcp
        name: http
      - port: 443
        name: https
    runtime:                            # observed runtime configuration facts
      mounts:
        - target: /shuffle-database
          source: aptl_shuffle_data
          source_kind: volume
          filesystem_type: ext4
          read_only: false
          options: [rw, nosuid]
          propagation: rprivate
          stability: volume_backed
          backend_generated: true
      filesystem_inventory:
        - path: /app/app.py
          entry_type: file
          owner_user: root
          owner_group: root
          uid: 0
          gid: 0
          mode: "0644"                 # quote to preserve leading zeroes
          size: 4096
          content_digest: 4f8c2d
          digest_algorithm: sha256
          source_path: src/webapp/app.py
          provenance: python-package
          stability: stable
          sensitivity: plain
        - path: /var/log/gunicorn/access.log
          entry_type: file
          mode: "0600"
          stability: log
          sensitivity: operator_secret
      local_control_interfaces:
        - path: /run/docker.sock
          kind: unix_socket
          protocol: docker
          bind_source: /var/run/docker.sock
          access: read_write
      process:
        pid: 1
        command: ./shufflebackend
        user: root
        working_directory: /app
      processes:
        - name: supervisord
          pid: 1
          command: supervisord -n
          role: supervisor
        - name: gunicorn
          parent_pid: 1
          command: [gunicorn, app:app]
          role: worker
      environment:
        - name: TECHVAULT_ADMIN_PASSWORD
          value_classification: redacted
          provenance: operator
        - name: SCENARIO_FIXTURE_TOKEN
          value: fixture-token
          value_classification: secret_fixture
          provenance: compose
      linux_capabilities:
        required: [CAP_NET_ADMIN]
        effective: CAP_NET_ADMIN
      operational_policy:
        restart: unless_stopped
        resource_limits:
          memory: 512 MiB
          cpu: 0.5
          pids: 128
      container:
        entrypoint: [/entrypoint.sh]
        command: [gunicorn, app:app]
        log_driver: json-file
        log_options:
          max-size: 10m
          max-file: "3"
        namespaces:
          cgroup: private
          ipc: private
          pid: private
          userns: host
          uts: private
        privileged: false
        read_only_rootfs: false
        publish_all_ports: false
        autoremove: false
        shm_size: 64 MiB
        masked_paths: [/proc/acpi, /proc/kcore]
        read_only_paths: [/proc/sys]
        cgroup_parent: /docker
        runtime_name: runc
        devices:
          - host_path: /dev/null
            container_path: /dev/null
            permissions: rwm
        device_cgroup_rules: [c 1:3 rwm]
        extra_hosts:
          - hostname: wazuh-manager
            address: 172.20.0.10
        dns: [8.8.8.8]
        dns_options: [ndots:0]
        dns_search: [techvault.local]
        group_add: [adm, "101"]
      health:
        status: healthy
        failing_streak: 0
        log:
          - start: "2026-05-20T12:00:00Z"
            end: "2026-05-20T12:00:01Z"
            exit_code: 0
            output: ok
      packages:
        - manager: apk
          name: musl
          version: 1.2.4-r2
      dependency_manifests:
        - ecosystem: go
          path: /app/go.mod
          format: go-module
      package_vulnerabilities:
        - id: CVE-2026-12345
          package_name: musl
          installed_version: 1.2.4-r2
          fixed_version: 1.2.5-r0
          severity: high
          scanner: trivy
          image_digest: sha256:abc123
          scan_time: "2026-05-20T12:00:00Z"
    asset_value:                        # CIA triad (from CybORG)
      confidentiality: high
      integrity: medium
      availability: critical
```

**Switch** nodes are pure connectivity objects. They may define `type` and an optional `description`, but `source`, `resources`, `os`, `os_version`, `features`, `conditions`, `injects`, `vulnerabilities`, `roles`, `services`, `asset_value`, and `runtime` are rejected.

For **VM** nodes, `resources` remain optional at the SDL layer to preserve abstract specifications, but a VM without `resources` emits a non-fatal advisory because many deployment backends will need explicit sizing or well-defined defaults.

**Feature list shorthand:** `features: [nginx, php]` expands to `{nginx: "", php: ""}` (no role binding required).

When `features`, `conditions`, or `injects` use the `{name: role}` form, the role must be declared in the node's `roles` map.

Concrete service bindings on a VM must be unique by `protocol` + `port`. Reusing `53/tcp` and `53/udp` is valid; declaring `443/tcp` twice on the same node is rejected. If a service binding also has a `name`, that `name` must be unique within the node and can be targeted directly as `nodes.<node>.services.<service_name>`.

`runtime` captures observed VM/runtime facts that are not authored deployable
features or exposed network services. Mounts describe realized filesystem
attachments, including filesystem type, propagation, stability, and whether a
backend generated the source. `filesystem_inventory` records runtime-observed
filesystem entries with absolute path, entry type, ownership, UID/GID, mode,
size, digest algorithm/value pairs, source-package path, provenance, stability,
and sensitivity classification. `local_control_interfaces` describe path-local
control APIs such as Unix sockets; `process` records primary execution
identity; `processes` records a supervised or load-bearing process set;
`environment` records observed runtime environment variables with provenance
and redaction classification; `linux_capabilities` records container/Linux
capability policy; `operational_policy` records restart policy and observed
resource limits; `container` records observed host/container configuration and
namespace/security facts; `health` records observed health status and bounded
healthcheck log facts; `packages` and `dependency_manifests` record runtime
inventory; and `package_vulnerabilities` records scanner-derived CVE/advisory
findings tied to an image digest and scan time. These findings are separate
from the top-level `vulnerabilities` section, which remains the CWE-classified
scenario vulnerability surface.

---

## Infrastructure

Maps node names to deployment parameters.

```yaml
infrastructure:
  corp-switch:
    count: 1
    properties:
      cidr: 10.0.0.0/24
      gateway: 10.0.0.1
      internal: true                    # blocks internet egress
    acls:                               # network access controls (from CybORG NACLs)
      - name: allow-dmz-https
        direction: in
        from_net: dmz-switch
        protocol: tcp
        ports: [443]
        action: allow
      - name: deny-dmz-default
        direction: in
        from_net: dmz-switch
        action: deny

  web-server:
    count: 1                            # shorthand: web-server: 1
    links: [corp-switch]
    dependencies: [db-server]
    properties:                         # per-link IP assignments
      - corp-switch: 10.0.0.10
```

**Shorthand:** `web-server: 3` expands to `{count: 3}`.

`links` are switch/network connectivity references, not arbitrary infrastructure edges. If a node has attached `conditions`, its `count` must stay at `1` so the condition-to-node binding remains unambiguous. Per-link IP assignments must be valid IP addresses within the linked switch's CIDR.

ACL rule `name` is optional, but when present it must be unique within that infrastructure entry and can be targeted directly as `infrastructure.<infra>.acls.<acl_name>`.

---

## Features

Software deployed onto VMs. Three types: Service, Configuration, Artifact.

```yaml
features:
  nginx:
    type: Service
    source: nginx-1.24
  php-config:
    type: Configuration
    source: php-8.2-config
    dependencies: [nginx]               # deployed after nginx; cycles rejected
  log-agent:
    type: Artifact
    source: filebeat-8
    destination: /opt/filebeat
    environment: ["ELASTICSEARCH_HOST=10.0.0.5"]
```

Feature dependencies are hard same-node prerequisites at runtime. If a node
binds a feature whose declared dependency is not also bound on that same node,
runtime compilation emits a diagnostic and the plan is invalid rather than
silently ignoring the missing prerequisite.

---

## Conditions

Health checks with optional timeout/retries/start_period.

```yaml
conditions:
  web-alive:
    command: "curl -sf http://localhost/ || exit 1"
    interval: 15
    timeout: 5
    retries: 3
    start_period: 30
  scanner:
    source: vuln-scanner-pkg            # alternative: library-based check
```

Must have either `command` + `interval` or `source`, not both.

---

## Vulnerabilities

CWE-classified weaknesses. The `class` field is validated against `CWE-\d+`.

```yaml
vulnerabilities:
  sqli:
    name: SQL Injection
    description: SQLi in login form allows auth bypass
    technical: true
    class: CWE-89
```

---

## Scoring Pipeline: Metrics, Evaluations, TLOs, Goals

```
Conditions → Metrics → Evaluations → TLOs → Goals
```

```yaml
metrics:
  service-uptime:
    type: CONDITIONAL
    max-score: 100
    condition: web-alive
  report-quality:
    type: MANUAL
    max-score: 50
    artifact: true

evaluations:
  overall:
    metrics: [service-uptime, report-quality]
    min-score: 75                       # shorthand = percentage
    # or: min-score: {absolute: 100}

tlos:
  web-defense:
    name: Web Application Defense
    evaluation: overall

goals:
  pass-exercise:
    tlos: [web-defense]
```

---

## Entities

Recursive team/organization hierarchy with exercise roles and OCR-style
fact maps.

```yaml
entities:
  blue-team:
    name: Blue Team
    role: Blue
    mission: Defend infrastructure
    tlos: [web-defense]
    facts:
      department: SOC
      primary-shift: nights
    entities:
      alice: {name: Alice}
      bob: {name: Bob}
  red-team:
    name: Red Team
    role: Red                           # White, Green, Red, Blue
```

Nested entities are referenced via dot-notation: `blue-team.alice`.

---

## Orchestration: Injects, Events, Scripts, Stories

```yaml
injects:
  phishing-email:
    source: phishing-pkg
    from-entity: red-team
    to-entities: [blue-team]

events:
  attack-wave:
    conditions: [scanner]
    injects: [phishing-email]

scripts:
  main-timeline:
    start-time: 5 min                  # OCR units: y, mon, w, d, h, m/min, s/sec, ms, us, ns
    end-time: 2 hour
    speed: 1.0
    events:
      attack-wave: 30 min

stories:
  exercise:
    speed: 1
    scripts: [main-timeline]
```

Sub-second durations are rounded up to the nearest second, so `1 ms`,
`1 us`, and `1 ns` all parse as `1`.

---

## Content

Data placed into scenario systems. Adapted from CyRIS `copy_content`.

```yaml
content:
  phishing-emails:
    type: dataset
    target: exchange-server
    destination: /var/mail/
    format: eml
    sensitive: true
    items:
      - name: "Q3 Budget.eml"
        tags: [phishing, macro]
  flag-file:
    type: file
    target: victim
    path: /var/www/html/flag.txt
    text: "FLAG{found_it}"
  seed-data:
    type: dataset
    target: database
    source: customer-pii-seed          # large dataset via package reference
    format: sql
```

`target` is required for every content entry and must reference a VM node, not a switch/network node. `file` content requires `path`; `dataset` content requires either `source` or non-empty `items`; `directory` content requires `destination`.

---

## Accounts

User accounts within scenario nodes. Adapted from CyRIS `add_account`.

```yaml
accounts:
  domain-admin:
    username: Administrator
    node: dc01
    groups: [Domain Admins]
    password_strength: strong           # weak, medium, strong, none
  svc-sql:
    username: svc_mssql
    node: dc01
    password_strength: weak
    spn: "MSSQL/db.corp.local"         # Kerberos SPN
    auth_method: password               # password, key, certificate
    mail: ""
```

`username` and `node` are required. `node` must reference a VM node, not a switch/network node.

---

## Relationships

Typed directed edges between any named scenario elements. Adapted from STIX Relationship SROs.

```yaml
relationships:
  exchange-auth:
    type: authenticates_with
    source: exchange-service
    target: ad-ds
  domain-trust:
    type: trusts
    source: child-domain
    target: parent-domain
    properties:
      trust_type: parent-child
      trust_direction: bidirectional
  sso:
    type: federates_with
    source: adfs
    target: azure-ad
    properties: {protocol: SAML}
  app-to-db:
    type: connects_to
    source: webapp
    target: postgres
    properties: {protocol: tcp, port: "5432"}
```

Types: `authenticates_with`, `trusts`, `federates_with`, `connects_to`, `depends_on`, `manages`, `replicates_to`.

Relationship endpoints resolve against the scenario's named elements, including top-level section keys, nested entity dot-paths, variables, other relationships, content item `name` values, named service bindings (`nodes.<node>.services.<service_name>`), and named ACL rules (`infrastructure.<infra>.acls.<acl_name>`).

Bare refs like `webapp` are valid when they are unambiguous. Any top-level section key may also be referenced explicitly as `<section>.<name>`, for example `nodes.webapp`, `features.postgres`, `accounts.db-admin`, or `infrastructure.dmz-net`. Content items may be referenced as `content.<content_name>.items.<item_name>` when a bare item `name` would collide with some other named element.

---

## Agents

Autonomous scenario participants. Adapted from CybORG CAGE Challenge. This
section is also the SDL-authoring surface for declarative participant framing
(ACT-601, ADR-020) — it covers all five framing facets the language
guarantees: identity, role, starting conditions, authority anchors, and
operating scope.

```yaml
agents:
  red-agent:
    entity: red-team                    # identity + role (via entities.role)
    actions: [Scan, Exploit, Escalate]
    starting_accounts: [phished-user]   # references accounts section
    starting_conditions: [beacon-online]  # references conditions section
    initial_knowledge:
      hosts: [user0]                    # known at scenario start
      subnets: [user-net]
      services: [ssh]                   # references nodes.*.services[].name
      accounts: [helpdesk-user]         # references accounts section
    authority_anchors:                  # declared bases for what the participant
      - red-team                        # may or is expected to do in scenario
      - red-controls-vm                 # meaning (entities, relationships, ...)
    allowed_subnets: [user-net, corp-net]
    operating_scope:                    # broader targetable scope beyond subnets
      - corp-net
      - user-net
    reward_calculator: HybridImpactPwn
```

`entity` is required and must resolve to the `entities` section; the
participant's authored identity and role both come from this binding (per
ADR-020). `initial_knowledge.hosts` references VM node names, `subnets`
references switch-backed infrastructure names, `services` references service
names declared in `nodes.*.services`, and `accounts` references entries in the
`accounts` section. `allowed_subnets` follows the same switch-backed
infrastructure rule.

`starting_conditions` lists names from the `conditions` section, giving the
authoring surface a declarative hook for participant-relevant precondition
checks without embedding executable setup commands. `authority_anchors`
references any declared scenario element (entities, relationships, content,
nodes, …) that anchors what the participant is allowed or expected to do in
scenario meaning — these are SDL-level anchors, not control-plane
authentication or bearer-token identity. `operating_scope` references
targetable named scenario elements (subnets, hosts, services, content) that
define the boundary of where the participant may act or observe; it
generalises `allowed_subnets`, which remains restricted to switch-backed
infrastructure.

Each of `starting_conditions`, `authority_anchors`, and `operating_scope`
accepts `${var}` placeholders that resolve through the declared `variables`
section. Symbol-defining keys (agent names) remain stable identifiers and
must not be variables.

This section captures the authoring-layer guarantees of ACT-601. Broader
participant concerns — behavior semantics, visibility, trajectories,
budgets, verifier/reward — remain owned by separate ecosystem requirements
(ACT-602, SEM-208, …) that are still planned.

Broader participant concerns are now treated as first-class ecosystem surfaces,
even where the current SDL syntax does not yet expose their full shape. Those
concerns include:

- participant-visible tool and affordance surfaces
- participant control-context artifacts such as directives and policies
- decision-surface exposure policies describing what is visible or hidden to a
  participant
- trajectory, episode, benchmark, verifier, and reward assets
- concrete participant implementations, which remain distinct from authored
  participant intent and from backend realization

That distinction is important: the SDL describes participant intent and
scenario meaning, while processors, backends, and participant implementations
remain separate apparatus surfaces.

---

## Objectives

Declarative experiment semantics that bind actors, targets, timing, and success criteria in the same SDL. Inspired by OCR's in-spec assessment model and CACAO's separation of agent, target, and workflow context.

```yaml
objectives:
  red-initial-access:
    agent: red-agent                   # or: entity: red-team
    actions: [Scan, Exploit]           # should be declared on the agent
    targets:                           # any named scenario elements except variables/objectives/workflows
      - web-server
      - app-to-db
      - nodes.web-server.services.https
      - infrastructure.dmz-switch.acls.allow-dmz-https
    success:
      mode: all_of                     # all_of, any_of
      goals: [pass-exercise]
      metrics: [service-uptime]
    window:
      stories: [exercise]
      scripts: [main-timeline]
      events: [attack-wave]
      workflows: [release-response]
      steps: [release-response.validate-release]

  blue-reporting:
    entity: blue-team
    success:
      metrics: [report-quality]
    depends_on: [red-initial-access]
```

Every objective must declare exactly one actor: either `agent` or `entity`. `success` is required and must reference at least one declared `condition`, `metric`, `evaluation`, `tlo`, or `goal`. `targets` are optional, but when present they must resolve to named scenario elements. Bare target refs work when unambiguous; otherwise use a qualified ref such as `nodes.web-server`, `features.app-to-db`, or `content.mailbox.items.invoice.eml`. `window` is optional; when supplied, referenced stories/scripts/events/workflows must exist and remain internally consistent. Workflow steps use qualified refs of the form `<workflow>.<step>`.

`depends_on` is an ordering relation, not just commentary. It defines a partial order over objectives: downstream objectives are not considered ready until their predecessors have been satisfied. Objective dependency cycles are rejected.

This section is intentionally declarative. It says who is trying to do what, against what, during which window, and how success is interpreted. It does **not** embed backend-specific probes such as Wazuh queries or command-output checks.

---

## Workflows

Declarative control programs over SDL-defined objectives and portable workflow state. Workflows remain backend-agnostic: they express experiment control intent, retries, failure handling, and concurrency without embedding backend-native commands.

```yaml
workflows:
  release-response:
    start: validate-release
    steps:
      validate-release:
        type: objective
        objective: blue-validate-release
        on-success: branch-on-promotion
      branch-on-promotion:
        type: decision
        when:
          conditions: [rogue-release-promoted]
        then: rollback-fanout
        else: finish
      rollback-fanout:
        type: parallel
        branches: [revoke-artifact, rollback-edge]
        join: rollback-joined
      revoke-artifact:
        type: objective
        objective: blue-revoke-artifact
        on-success: rollback-joined
      rollback-edge:
        type: objective
        objective: blue-preserve-service
        on-success: rollback-joined
      rollback-joined:
        type: join
        next: verify-rollback
      verify-rollback:
        type: decision
        when:
          steps:
            - step: revoke-artifact
              outcomes: [succeeded]
        then: finish
        else: revalidate-release
      revalidate-release:
        type: objective
        objective: blue-validate-release
        on-success: finish
      finish:
        type: end
```

Workflow step types are:

- `objective` — execute a declared objective; `on-success` is required and `on-failure` is optional. If `on-failure` is omitted, workflow execution fails terminally on objective failure.
- `decision` — branch on a declarative predicate using `then` / `else`
- `switch` — evaluate ordered `cases`, take the first matching case target, and fall back to `default` when no case predicate matches
- `retry` — re-run a declared objective until it succeeds or `max-attempts` is exhausted; `on-success` is required and `on-exhausted` is optional
- `call` — invoke another declared workflow as a reusable subflow; `workflow` and `on-success` are required, and `on-failure` is optional
- `parallel` — launch two or more branch entry steps concurrently and require all explicit branch paths to converge on a named `join` step; `on-failure` is optional
- `join` — an explicit barrier step, not a normal direct successor edge, that resumes linear control via `next` only after the owning `parallel` step has observed all branches converge
- `end` — terminal node

Compensation is step-attached and workflow-governed:

- compensable steps are `objective` and `call`
- those step kinds may declare `compensate-with: <workflow>`
- workflows may declare a `compensation:` policy with:
  - `mode: automatic | disabled`
  - `on: [failed, cancelled, timed_out]`
  - `failure_policy: fail_workflow | record_and_continue`
  - `order: reverse_completion` (the only supported ordering in v1)

Compensation targets are always declared workflows, never inline rollback step
graphs. Successful compensable steps register rollback intent, and automatic
compensation executes in reverse completion order when the primary workflow
terminates with a configured trigger.

Workflow predicates may observe:

- scoring/evaluation data via `conditions`, `metrics`, `evaluations`, `tlos`, `goals`, and `objectives`
- prior step state via `steps`, where each entry names a prior executable step plus one or more expected outcomes (`succeeded`, `failed`, `exhausted`) and an optional `min-attempts`

Example predicate over prior step state:

```yaml
when:
  steps:
    - step: validate-release
      outcomes: [failed]
      min-attempts: 2
```

Workflow-visible step state is an immutable execution history. In v1, predicates may only inspect step outcomes and attempt counts; they may not inspect backend-specific failure classes. Step-state predicates must reference steps whose state is guaranteed to be known before the predicate executes.

After a `join`, downstream predicates may inspect executable branch steps from that fanout, but only when those steps are guaranteed on every path within their own branch before the join. Branch-local step state does not leak across sibling branches before the join, and a `parallel.on-failure` bypass does not expose abandoned branch state.

Workflow graphs remain acyclic. Every referenced step must exist, every step
must be reachable from `start`, joins must be referenced by exactly one
`parallel` step, every explicit branch path from a `parallel` step must
converge on its declared join, and workflow call graphs must also remain
acyclic. Workflow names may use canonical namespace-style dots, but workflow
step names may not because objective window refs use `<workflow>.<step>`
syntax and split on the final `.`.

Migration from the exploratory workflow syntax:

- replace `if` with `decision`
- replace `while` with `retry` when the repeated work is a single objective
- replace `next` on objective steps with required `on-success`
- replace `on-error` with `on-failure` (for `objective` / `parallel`) or `on-exhausted` (for `retry`)
- replace `parallel.next` with an explicit `join` step
- replace `step-outcomes: [step-name]` with `steps: [{step: step-name, outcomes: [...]}]`

---

## Variables

Scenario parameterization. Adapted from CACAO playbook_variables.

```yaml
variables:
  domain_name:
    type: string
    default: "corp.local"
    description: Active Directory domain name
  num_workstations:
    type: integer
    default: 5
  admin_strength:
    type: string
    default: weak
    allowed_values: [weak, medium, strong]
    required: false
```

Variables are referenced as `${var_name}` in other sections. They are **not resolved at parse time** — resolution happens at instantiation.

Full-value placeholders are currently supported in ordinary string fields, common scalar fields (counts, booleans, scores, timings, RAM/CPU, ports), many reference values, and selected leaf enum-backed property fields such as `accounts.*.password_strength`, `entities.*.role`, `nodes.*.os`, `nodes.*.asset_value.*`, `infrastructure.*.acls[*].action`, and `objectives.*.success.mode`. The semantic validator checks that `${var_name}` refers to a declared variable, and the repo-owned instantiation phase later substitutes concrete values before compilation/runtime planning. User-defined mapping keys and discriminant/schema-shaping enum fields such as section `type` tags still need concrete values, and placeholder keys are rejected at parse time.

Think of variables as parameterizing **properties of declared objects**, not the object graph itself. For example, a node's hostname, a content file's text, or a subnet CIDR may be variable-backed, while top-level identifiers like `nodes.web`, `features.nginx`, or `accounts.domain-admin` must remain literal.

`default` and every entry in `allowed_values` must match the declared `type`. If `allowed_values` is provided, `default` must be one of those values.

---

## Scoring, Objectives, and Runtime Checks

The SDL now carries both:

- the OCR-style scoring pipeline (`conditions → metrics → evaluations → TLOs → goals`)
- declarative objectives that bind actors, targets, windows, and success criteria
- workflow graphs that branch or parallelize declared objectives without embedding runtime probe logic

Backend-specific auto-validation mechanics still live outside the SDL. The runtime may use Wazuh queries, command probes, file checks, or other adapters to determine whether an SDL-declared objective or scoring condition has been satisfied, but those probe details are not the language itself.
