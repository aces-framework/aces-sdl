# ADR-025: Container Network Realization Surface

## Status

accepted

## Date

2026-05-21

## Context

Issue #366 requires SDL parity for container network facts observed from inside
the realized range or by a harness: per-network aliases and DNS names,
hostname/domain identity, endpoint MAC addresses, endpoint prefix and gateway,
backend network and endpoint identifiers, host-published port bindings, backend
driver/IPAM details, and stable versus ephemeral classification for generated
identifiers.

The repository already has adjacent surfaces, but none owns this complete
meaning:

- `infrastructure` declares topology, dependencies, switch/network CIDR and
  gateway properties, links, ACLs, and static per-link IP assignment.
- `Node.services` declares services on a node by container-side port/protocol.
- `Source.build.config.exposed_ports` records image-default exposed ports.
- `Node.runtime.container` records observed host/security/container runtime
  configuration, DNS server settings, extra host-file mappings, namespace
  modes, devices, and health.

The design risk is to express Docker endpoint facts by overloading one of those
surfaces and thereby conflate declared topology, image defaults, container
runtime state, host exposure, backend identifiers, and participant-visible
network identity.

## Decision

### 1. Put realized endpoint facts under node runtime

Container network realization facts belong under the node-scoped runtime
surface, as typed observed facts attached to `Node.runtime`, not as a new
top-level SDL section and not as new fields on `infrastructure`.

`infrastructure` remains the authoring/provisioning topology declaration. A
runtime endpoint record may reference an infrastructure network by name, but it
must not turn backend-generated network IDs, endpoint IDs, aliases, MAC
addresses, or harness-only observations into topology declarations.

### 2. Keep endpoint identity facts distinct

The implementation must preserve the distinction among:

- per-network aliases
- DNS names observed for the endpoint
- node/container hostname
- node/container domain name
- backend-generated names or generated container-ID prefixes

Do not collapse these into one `name`, `alias`, or `dns` string. Generated DNS
names may be useful evidence, but they are not stable scenario identity unless
the model records them as stable.

### 3. Model host publication separately from services and image exposed ports

Host-published bindings are runtime/host exposure facts. They may reference a
declared node service or repeat the container-side port/protocol, but they must
not be represented by mutating `Node.services` or by using image
`exposed_ports`.

The model must keep host IP, host port, container port, and protocol distinct.
`publish_all_ports` remains the observed runtime flag; concrete bindings belong
in a typed binding list when they are known.

### 4. Use typed backend details, not raw inspect payloads

Backend network driver and IPAM details should be represented through a typed
runtime network detail surface with a bounded extension seam for backend-native
key/value facts. Do not embed raw Docker, Podman, Compose, or harness inspect
payloads into SDL.

Backend identifiers such as network ID and endpoint ID must carry an explicit
stability classification. Do not reuse `RuntimeFilesystemStability`; filesystem
stability and backend identifier stability are different concepts. Use a small
network-realization identifier classifier such as stable, ephemeral, unknown,
or other, with `backend_generated` where the backend produced the value.

### 5. Reuse existing SDL and contract gates

The implementation must reuse the repository's existing cross-cutting gates:

- `SDLModel` closed-world validation and Pydantic field/model validators
- shared parsing helpers such as `parse_int_or_var()`,
  `parse_bool_or_var()`, `parse_runtime_enum_or_var()`, and
  `coerce_string_list()`
- `ipaddress`-based validation patterns from `infrastructure.py` for IP,
  prefix, gateway, and CIDR consistency
- parser key normalization, hashmap-key preservation, `source` shorthand
  rules, and variable-placeholder key rejection
- `SemanticValidator` and `SDLValidationError` for cross-reference and
  cross-field authoring errors
- `instantiate_scenario()` and `SDLInstantiationError` for substitution and
  concrete revalidation
- `schema_bundle()`, `tools/generate_contract_schemas.py`, and
  `tools/check_generated_schemas.py`; generated schemas under
  `contracts/schemas/` must not be edited directly
- `aces_processor.models.Diagnostic` and published runtime/control-plane
  envelopes if realized network facts later flow through runtime snapshots or
  backend reports

No new parser, schema registry, exception hierarchy, logging stack, persistence
mechanism, or backend-specific top-level SDL dialect is justified for this
issue.

### 6. Keep the extensibility seam node-scoped and backend-neutral

The seam is a typed node-scoped runtime network realization block. Future
variants such as Podman, Kubernetes pod networks, bridge/overlay/macvlan
drivers, IPv6, multi-address endpoints, service meshes, or additional IPAM
attributes should extend that block or its backend-detail submodels instead of
creating a second network schema elsewhere.

## Security and Validation Gates

- Parser gate: if backend detail maps preserve native keys, add only the needed
  nested hashmap preservation entry. Avoid nested fields named `source` unless
  the parser's source-shorthand skip behavior is intentionally updated.
- SDL model gate: validate host and container ports with the existing integer
  helpers, validate IP addresses and gateways with `ipaddress`, and reject
  duplicate endpoint records, aliases, DNS names, endpoint IDs, and published
  bindings where they would become ambiguous.
- Semantic validation gate: endpoint network references must resolve to
  switch-backed infrastructure entries; concrete endpoint IPs and gateways
  should be checked against the referenced network CIDR when available.
- Instantiation gate: variable placeholders may stand in value fields, but not
  symbol-defining keys; concrete instantiated scenarios must revalidate.
- Contract/schema gate: schema changes come from Python model sources and
  regeneration, never direct edits under `contracts/schemas/`.
- Runtime/control-plane gate: if these facts are surfaced through snapshots or
  operation payloads, use the published `RuntimeSnapshotEnvelopeModel`,
  `OperationReceiptModel`, and `OperationStatusModel` shapes plus existing
  request-size, authentication, authorization, audit, idempotency, and redacted
  error handling in `aces_processor.control_plane_api`.
- Host/OS exposure gate: host-published bindings are externally reachable
  attack surface. Do not log, fixture, diagnose, or persist raw backend payloads
  that include bearer tokens, registry credentials, private addresses that were
  intentionally withheld, or unredacted harness output.

## Guardrails

- Do not put aliases, DNS names, MAC addresses, endpoint IDs, or host bindings
  into `infrastructure.properties`; that surface currently expresses network
  CIDR/gateway properties and static per-link IP assignment.
- Do not use `RuntimeExtraHost` for network aliases or DNS names; it models
  host-file mappings.
- Do not treat backend-generated IDs or generated container-ID DNS prefixes as
  stable scenario identifiers by default.
- Do not add Docker-specific top-level SDL fields. Docker is a backend source
  of observed facts, not the SDL authority boundary.
- Do not make realized endpoint IDs targetable participant/objective refs.
- Do not add implementation logic under `implementations/python/src/aces/`;
  that tree is compatibility-only.

## Non-Goals

- Implementing issue #366.
- Updating `examples/scenarios/techvault.sdl.yaml`.
- Building a Docker, Compose, Podman, Kubernetes, or harness inspector.
- Defining backend provisioning behavior for all network drivers or IPAM
  systems.
- Changing `infrastructure` topology semantics beyond allowing runtime endpoint
  records to reference existing switch-backed networks.
- Defining a new backend manifest/profile capability vocabulary unless a later
  implementation needs machine-checkable backend support claims for these
  specific runtime facts.

## Consequences

### Positive

- Declared topology, runtime endpoint observation, image defaults, services,
  and host-published exposure stay distinguishable.
- Existing SDL parsing, validation, instantiation, schema generation, concept
  authority, runtime diagnostics, and control-plane envelopes remain
  authoritative.
- TechVault parity can represent Docker-observed endpoint facts without making
  Docker inspect JSON part of the SDL.

### Negative

- Some network facts may appear in adjacent places with different meanings, for
  example a declared static IP assignment and the realized endpoint IP observed
  at runtime.
- Backend adapters and harnesses need to classify identifier stability instead
  of dumping whatever identifier the backend returned.

### Risks

- Overloading `infrastructure` would turn observation into authoring intent and
  confuse planner behavior.
- Overloading `services` or image `exposed_ports` would hide host OS exposure
  and make security review unreliable.
- A free-form backend payload would bypass closed-world schema validation and
  make redaction, stability classification, and cross-backend comparison
  brittle.
