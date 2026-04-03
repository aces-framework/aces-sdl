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

- shared result constraints: `src/aces/core/semantics/workflow.py`
- typed result models: `src/aces/core/runtime/models.py`
- manager contract validation: `src/aces/core/runtime/manager.py`
- backend example: `src/aces/backends/stubs.py`

## Tests

- `tests/test_runtime_manager.py`
- `tests/test_runtime_models.py`
- `tests/test_runtime_contracts.py`
