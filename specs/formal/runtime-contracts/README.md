# Runtime Contract Semantics

This directory holds the formal artifacts for portable runtime result contracts.

## Scope

- typed workflow execution envelopes
- typed workflow step execution state
- typed evaluator result envelopes
- typed evaluator history streams
- manager-side validation of backend workflow results
- manager-side validation of backend evaluator results

## Implementation Mapping

- shared result constraints: `implementations/python/packages/aces_processor/semantics/workflow.py`
- typed result models: `implementations/python/packages/aces_processor/models.py`
- manager contract validation: `implementations/python/packages/aces_processor/manager.py`
- backend example: `implementations/python/packages/aces_backend_stubs/stubs.py`

## Tests

- `implementations/python/tests/test_runtime_manager.py`
- `implementations/python/tests/test_runtime_models.py`
- `implementations/python/tests/test_runtime_contracts.py`
