# ADR-023: Container Image Build Provenance Surface

## Status

proposed

## Date

2026-05-21

## Context

Issue #364 requires SDL parity for observable custom container-image facts:
base images and digests, layer chains, Dockerfile instructions, build args,
copied source paths, generated image config, source package checksums,
source-to-runtime mappings, and attestation or verification status.

The current `Source` model identifies an artifact by `name` and `version`.
`Node.runtime` already records observed runtime facts such as filesystem
inventory, effective process identity, environment variables, Linux
capabilities, runtime container host/security configuration, health, packages,
dependency manifests, and scanner findings. The design risk is to bolt image
build facts onto whichever model is nearby and thereby conflate:

- artifact identity
- artifact build provenance
- image default configuration
- runtime-effective container state
- backend deployment mechanics
- archival run provenance

This would also conflict with existing cross-cutting gates: the SDL parser has
special `source` shorthand behavior, all SDL models are closed Pydantic models,
generated schemas come from model sources, secrets are not allowed to leak into
diagnostics or fixtures, and ADR-009/ADR-010 keep implementation ownership and
normative artifact boundaries separate.

## Decision

### 1. Put build provenance on the source artifact boundary

Container/image build provenance belongs on the artifact reference boundary,
not in a new top-level SDL section and not in `Node.runtime` by default.

The implementation should extend the existing `Source` shape with an optional
typed, image-specific provenance block. `Source.name` and `Source.version`
remain the provider-neutral artifact identity. The provenance block carries
facts about how that artifact was built or inspected when those facts are
available.

### 2. Keep image defaults separate from runtime-effective state

Image config facts such as default entrypoint, command, working directory,
labels, exposed ports, and default environment are image-artifact facts.
Runtime-effective facts remain under `Node.runtime`.

If a runtime launches with the same entrypoint or command as the image default,
that equality may be represented in both places, but the meanings are still
different: one is an image default, the other is the realized runtime state.
The implementation must not silently move runtime host/security facts such as
mounts, devices, namespace modes, cgroup settings, DNS, extra hosts, restart
policy, or health observations into the image provenance block.

### 3. Reuse existing SDL and contract gates

The new surface must reuse the repository's existing gates:

- `SDLModel` closed-world validation and Pydantic field/model validators
- parser key normalization, hashmap-key preservation, `source` shorthand
  rules, and variable-placeholder rules
- `SemanticValidator` and `SDLValidationError` for cross-field or
  cross-reference authoring errors
- `instantiate_scenario()` and `SDLInstantiationError` for concrete
  substitution and revalidation
- `schema_bundle()`, `tools/generate_contract_schemas.py`, and
  `tools/check_generated_schemas.py`; do not edit `contracts/schemas/`
  directly
- `tools/check_json_artifacts.py`, example scenario loading tests, and the
  nox verification graph

No new parser, schema registry, validation framework, exception hierarchy, or
logging stack is justified for this issue.

### 4. Treat provenance values as observable facts, not file reads

Source paths, Dockerfile paths, copied paths, and source-package checksums are
declarative facts unless a later tool explicitly resolves them. Any resolver
that reads local files must validate paths against its declared context root
and reject absolute paths, `..` traversal, and symlink escapes before opening
files.

Layer digests, base-image digests, file checksums, and source input checksums
should use one shared validation helper if strict digest validation is added;
the same digest regex must not be duplicated across models.

### 5. Preserve redaction and attestation semantics explicitly

Build args may carry resolved values only when they are non-secret. Redacted,
secret-fixture, operator-secret, and unknown values must be represented through
classification fields and must omit raw secret values, matching the existing
runtime redaction discipline.

Attestation availability and verification result are separate facts. A mutable
local image tag with no registry-visible OCI, in-toto, or SLSA attestation is
not the same state as a failed verification. The SDL surface must preserve that
distinction so downstream provenance work can make a falsifiable claim instead
of inferring one from absence.

### 6. Keep the extensibility seam artifact-scoped

The seam is a typed artifact-provenance block under `Source`. Future variants
such as non-Docker OCI builders, BuildKit metadata, source archives, VM image
recipes, or SBOM/provenance attachments should extend artifact-scoped
submodels or discriminated sub-blocks rather than creating new top-level SDL
sections or overloading `runtime`.

## Guardrails

- Do not add raw Dockerfile text as the primary portable model. Dockerfile or
  shell syntax can contain `${...}` strings that collide with ACES variable
  substitution. Prefer structured instruction records, and define an explicit
  escaping or redaction rule before preserving raw instruction text.
- Do not name nested plain-string fields `source` inside the new provenance
  block unless the parser's source-shorthand skip rules are updated. Otherwise
  the parser can expand them into `Source` objects by accident.
- Preserve hashmap keys for Docker labels, build-arg names, and other
  case-sensitive/native keys by extending the parser's nested hashmap rules
  where needed.
- Keep `RuntimeFilesystemEntry.source_path` and image source-to-runtime mapping
  aligned by stable source path or input identifiers; do not create two
  unrelated source mapping dialects.
- Keep attestation evidence references as references or statuses, not embedded
  registry credentials, bearer tokens, certificates, or raw backend responses.

## Non-Goals

- Implementing issue #364.
- Updating `examples/scenarios/techvault.sdl.yaml`.
- Building or inspecting images.
- Defining a backend build executor, Docker Compose authoring format, registry
  distribution service, or OCI module packaging policy.
- Adding archival run-provenance contracts beyond the SDL expressivity needed
  for the source artifact facts.

## Consequences

### Positive

- The source artifact, image build recipe, image default configuration, and
  runtime-effective state stay distinguishable.
- Existing SDL parsing, validation, instantiation, schema generation, and
  verification gates remain authoritative.
- TechVault parity can be added without making Docker or Compose the normative
  deployment model.

### Negative

- `Source` becomes more than a simple name/version pair when the optional
  provenance block is present.
- Some facts may intentionally appear twice with different meanings, such as
  image-default command and runtime-effective command.

### Risks

- Parser shorthand behavior can corrupt nested provenance fields if new
  case-sensitive maps or plain `source` keys are added casually.
- Secret build args or raw instruction text can leak through validation errors,
  examples, generated schemas, or logs if redaction is not enforced before
  values enter diagnostics.
- Overfitting to Dockerfile syntax could make future OCI/SBOM/provenance
  inputs look like incompatible second-class artifacts.
