# Workflow Semantics

This directory holds the repo-native formal artifacts for SDL workflow control semantics.

## Scope

- workflow step kinds and their observable state contracts
- legal transitions for `objective`, `retry`, `parallel`, `decision`, `join`, and `end`
- join ownership and legal join entry
- step-state visibility before predicate evaluation
- portable workflow result envelopes
- explicit compensation / rollback registration and observation semantics

## Invariants

- every `join` has exactly one owning `parallel`
- only the owning parallel's branch closure may enter its `join`
- every explicit branch path converges on the declared `join`
- only observable step kinds may be referenced in step-state predicates
- step-state predicates may only ask for outcomes legal for the referenced step kind
- post-join visibility contains only step state guaranteed on every path to the join
- compensation executes only for successfully completed compensable steps
- compensation order is reverse completion order
- compensation workflows remain acyclic relative to normal `call` edges

## Implementation Mapping

- shared rules: `implementations/python/packages/aces_processor/semantics/workflow.py`
- validator enforcement: `implementations/python/packages/aces_sdl/validator.py`
- compiled contracts: `implementations/python/packages/aces_processor/compiler.py`
- typed runtime results and contract checks:
  - `implementations/python/packages/aces_processor/models.py`
  - `implementations/python/packages/aces_processor/manager.py`
- smoke/regression coverage:
  - `implementations/python/tests/test_sdl_validator.py`
  - `implementations/python/tests/test_runtime_models.py`
  - `implementations/python/tests/test_runtime_manager.py`
  - `implementations/python/tests/test_runtime_control_plane_api.py`

## Notes

This first wave uses Markdown as the abstract model format. TLA+ or Alloy can be added later for especially risky changes without changing the code-facing contract described here.
