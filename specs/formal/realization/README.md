# Realization Semantics

This directory holds the normative semantic boundary for binding author
declarations versus concerns left open to backend realization (`SEM-218`).
In ACES the processor layer does not realize underspecified author
concerns: it compiles the typed runtime requirement and plans against
backend support. Realization happens at the backend layer, and only
backend manifests carry `realization_support`.

## Scope

- the three-class taxonomy of author intent: exact declaration, constrained
  declaration, open realization
- the rules that decide when realization is permitted, when an explicit
  declaration must be honored, and when an unsupported exact requirement
  must be rejected rather than silently approximated
- the cross-stage gate that the SDL, processor, and backend layers must
  pass for those rules to hold across authoring, validation, instantiation,
  compilation, planning, execution, and observation
- the capability-disclosure surface on **backend** manifests that
  declares which exact-requirement-kinds and constraint-kinds the
  backend supports, and the per-domain support mode that governs how
  those kinds may be realized — processor manifests carry no
  `realization_support` because the processor layer does not realize
  underspecified concerns

## Out Of Scope

- new SDL syntax for declaring exact, constrained, or open authoring
  intent — the existing closed Pydantic SDL models, controlled
  vocabularies, semantic profiles, and apparatus manifests carry the
  necessary surfaces
- enumerating every future exact-requirement-kind or constraint-kind;
  governed extension happens through the controlled-vocabulary,
  reference-model, and semantic-profile authorities
- wave-3 participant semantics (`SEM-208`–`SEM-229`) that build on this
  boundary — those have their own owning requirements

## Realization Status

The spec's semantic boundary is normative immediately. End-to-end
realization across the seven `SEM-200` lifecycle phases is staged: today
the boundary is enforced at the authoring and validation phases through
the apparatus contract layer (the shape gates on backend
`RealizationSupportDeclaration` and the JSON-schema conditional gate,
plus the asymmetric rejection of `realization_support` on processor
manifests). Instantiation, compilation, planning, execution, and
observation responsibilities in the spec are normative but not yet
realized end-to-end. The coverage row in
`docs/explain/reference/shared-semantic-integrity.md` carries the
current `partial` status; promoting it to `active` is the implementation
work the SEM-218 row tracks.

## Implementation Mapping

- realization support modes: `implementations/python/packages/aces_contracts/vocabulary.py`
  (`RealizationSupportMode`)
- apparatus declarations:
  `implementations/python/packages/aces_contracts/apparatus.py`
  (`RealizationSupportDeclaration`, `ConceptBinding`, `ApparatusIdentity`)
- contract-model gates and JSON schema (backend manifest):
  `implementations/python/packages/aces_contracts/contracts.py`
  (`RealizationSupportDeclarationModel`)
- processor-vs-backend asymmetry:
  `implementations/python/packages/aces_contracts/contracts.py`
  (`ProcessorManifestV2Model` rejects `realization_support`)
- backend-manifest payload encoding:
  `implementations/python/packages/aces_backend_protocols/manifest.py`
- native concept family for realization semantics:
  `contracts/concept-authority/concept-families-v1.json`
  (`realization-and-disclosure`)
- invalid fixtures evidencing fail-closed rejection:
  `contracts/fixtures/backend-manifest/backend-manifest-v2/invalid/hollow-realization-support.json`,
  `contracts/fixtures/backend-manifest/backend-manifest-v2/invalid/malformed-realization-support.json`,
  `contracts/fixtures/processor-manifest/processor-manifest-v2/invalid/hollow-realization-support.json`,
  `contracts/fixtures/processor-manifest/processor-manifest-v2/invalid/malformed-realization-support.json`

## Tests

- `implementations/python/tests/test_backend_manifest.py` — shape-gate
  rejection of hollow / malformed backend `realization_support`
- `implementations/python/tests/test_processor_manifest.py` — processor
  manifest rejection of any `realization_support` section
  (`test_processor_manifest_v2_rejects_realization_support_section`)
- `implementations/python/tests/test_runtime_contracts.py` — JSON-schema
  conditional gate for backend manifests and the assertion that the
  generated processor schema carries no `realization_support` property

## Notes

- `explicitness-and-realization.md` is the normative semantic boundary for
  `SEM-218`. It is the citable source for "is this declaration binding?",
  "when may a realizer pick a value?", and "must this unsupported exact
  requirement be rejected?".
- The non-normative companion at
  `docs/explain/reference/explicitness-realization-semantics.md` records
  the architecture guardrails for the implementation that realizes the
  spec; it is implementer-facing reference and not itself authoritative.
- `SEM-218`'s coverage row in
  `docs/explain/reference/shared-semantic-integrity.md` tracks realization
  status across the seven `SEM-200` lifecycle phases.
