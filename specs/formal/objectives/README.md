# Objective Window Semantics

This directory holds the formal artifacts for objective window and reachability
semantics.

## Scope

- normalized story/script/event/workflow/workflow-step reference resolution
- consistency between `window.stories`, `window.scripts`, `window.events`,
  `window.workflows`, and `window.steps`
- reachability derivation from story -> script -> event chains
- refresh dependency derivation from workflow and workflow-step refs
- fail-closed behavior for invalid, dangling, or out-of-window references
- composition-ready invariants for later namespace/module expansion

## Implementation Mapping

- shared helpers: `implementations/python/packages/aces_processor/semantics/objectives.py`
- semantic validation: `implementations/python/packages/aces_sdl/validator.py`
- compiled runtime diagnostics and dependency derivation:
  - `implementations/python/packages/aces_processor/compiler.py`
  - `implementations/python/packages/aces_processor/models.py`

## Tests

- `implementations/python/tests/test_semantics_objectives.py`
- `implementations/python/tests/test_fm2_semantics.py`
- `implementations/python/tests/test_sdl_validator.py`
- `implementations/python/tests/test_runtime_models.py`
