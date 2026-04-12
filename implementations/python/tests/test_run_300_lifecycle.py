"""RUN-300: end-to-end processing-model lifecycle integrity tests.

RUN-300 ("Processing Model and Lifecycle") requires that the ecosystem
carry a valid scenario through instantiation, compilation, planning,
execution, and live observation while preserving scenario meaning across
those stages.

The existing per-stage tests (``test_fm2_semantics``, ``test_runtime_*``)
each verify a single stage or a single stage pair. The tests in this
module thread one parameterized scenario through all five stages end to
end, and assert that the canonical identity chosen at instantiation time
survives unchanged into the compiled model, the planner provenance tuple,
the applied snapshot, and the live-observation envelope — and that any
drift of that provenance is rejected rather than silently reconciled.
"""

from __future__ import annotations

import json
import textwrap

import pytest

from aces.backends.stubs import create_stub_target
from aces.core.runtime.compiler import compile_runtime_model
from aces.core.runtime.manager import RuntimeManager
from aces.core.runtime.models import (
    ChangeAction,
    ExecutionPlan,
    RuntimeDomain,
    RuntimeSnapshot,
)
from aces.core.runtime.planner import plan as plan_execution
from aces.core.sdl import (
    InstantiatedScenario,
    SDLInstantiationError,
    instantiate_scenario,
    parse_sdl,
)

NODE_NAME = "vm1"
EXPECTED_NODE_ADDRESS = f"provision.node.{NODE_NAME}"
DRIFT_DIAGNOSTIC_CODE = "runtime.plan-snapshot-mismatch"
PARAM_OS_KIND = "linux"
PARAM_CPU_COUNT = 2


def _raw_scenario():
    """Return a parsed, still-parameterized scenario.

    Canonical mapping keys (``nodes.vm1``) are fixed at parse time —
    the parser explicitly rejects ``${var}`` in user-defined mapping
    keys (see ``_reject_variable_mapping_keys`` in the SDL parser).
    The meaning-preservation probe therefore lives in value positions:
    the ``os_kind`` and ``cpu_count`` variables must flow through
    instantiation and land, fully substituted, inside the compiled
    model, the planner's operation payload, and the applied snapshot
    entry for ``provision.node.vm1``.

    The scenario exercises all three runtime domains (provisioning,
    orchestration, evaluation) so each downstream plan has non-empty
    operations and the live-observation surface is populated.
    """

    return parse_sdl(
        textwrap.dedent(
            f"""
            name: run-300-lifecycle
            variables:
              os_kind:
                type: string
                default: linux
              cpu_count:
                type: integer
                default: 1
            nodes:
              {NODE_NAME}:
                type: vm
                os: ${{os_kind}}
                resources:
                  ram: 1 gib
                  cpu: ${{cpu_count}}
                conditions: {{health: ops}}
                roles: {{ops: operator}}
            conditions:
              health: {{command: /bin/true, interval: 15}}
            metrics:
              uptime: {{type: conditional, max-score: 100, condition: health}}
            entities:
              blue: {{role: blue}}
            objectives:
              validate:
                entity: blue
                success: {{conditions: [health]}}
            workflows:
              response:
                start: run
                steps:
                  run:
                    type: objective
                    objective: validate
                    on-success: finish
                  finish: {{type: end}}
            """
        )
    )


def _no_variable_tokens(obj: object) -> bool:
    """Return ``True`` if ``obj`` contains no ``${...}`` placeholder tokens."""

    serialized = json.dumps(obj, default=str)
    return "${" not in serialized


class TestRun300Lifecycle:
    """Five-stage pipeline integrity tests for RUN-300."""

    def test_valid_scenario_flows_through_all_five_stages_preserving_identity(self):
        """One parameterized scenario → instantiate → compile → plan → apply → observe.

        Asserts that the ``${node_name}`` chosen at instantiation becomes
        the canonical address ``provision.node.vm1`` and survives into
        every downstream stage's typed contract (compiled model, plan
        operation, applied snapshot entry, orchestration-history event).
        """

        # ----- Stage 1: Instantiation --------------------------------
        raw = _raw_scenario()
        instantiated = instantiate_scenario(
            raw,
            parameters={"os_kind": PARAM_OS_KIND, "cpu_count": PARAM_CPU_COUNT},
        )

        assert isinstance(instantiated, InstantiatedScenario), (
            "instantiate_scenario must return a typed InstantiatedScenario, "
            "not a loose dict — typed contracts are how RUN-300 preserves "
            "meaning across stages."
        )
        assert instantiated.instantiation_parameters == {
            "os_kind": PARAM_OS_KIND,
            "cpu_count": PARAM_CPU_COUNT,
        }, (
            "Instantiation parameters must be captured on the concrete "
            "scenario so downstream stages can trace provenance back to "
            "the authoring inputs."
        )
        instantiated_payload = instantiated.model_dump(mode="python", by_alias=True)
        assert _no_variable_tokens(instantiated_payload), (
            "All ${...} tokens must be resolved during instantiation; any "
            "token surviving into compilation would mean a stage is "
            "consuming raw SDL rather than the canonical compiled form."
        )
        assert NODE_NAME in instantiated_payload.get("nodes", {}), (
            "The canonical node identity must appear under its literal key after instantiation."
        )

        # ----- Stage 2: Compilation ----------------------------------
        model = compile_runtime_model(instantiated)
        compile_errors = [diag for diag in model.diagnostics if diag.is_error]
        assert not compile_errors, (
            f"Compilation produced error diagnostics: {compile_errors!r}. A valid scenario must compile cleanly."
        )
        assert EXPECTED_NODE_ADDRESS in model.node_deployments, (
            f"Compiled RuntimeModel must key its node_deployments on the "
            f"canonical address {EXPECTED_NODE_ADDRESS!r}. Any other key "
            f"shape would mean planning has to reparse raw SDL to know "
            f"what a node is called."
        )
        compiled_node = model.node_deployments[EXPECTED_NODE_ADDRESS]
        assert compiled_node.node_name == NODE_NAME
        assert compiled_node.os_family == PARAM_OS_KIND, (
            f"os_kind parameter ({PARAM_OS_KIND!r}) must survive "
            f"substitution through into the compiled node's os_family; "
            f"got {compiled_node.os_family!r}."
        )

        # ----- Stage 3: Planning -------------------------------------
        target = create_stub_target()
        empty_snapshot = RuntimeSnapshot()
        execution_plan = plan_execution(
            model,
            target.manifest,
            empty_snapshot,
            target_name=target.name,
        )

        assert isinstance(execution_plan, ExecutionPlan)
        assert execution_plan.target_name == target.name, (
            "ExecutionPlan provenance must bind to the target name the manager will apply against."
        )
        assert execution_plan.manifest is target.manifest, (
            "ExecutionPlan provenance must carry the manifest used at planning time so apply can detect manifest drift."
        )
        assert execution_plan.base_snapshot is empty_snapshot, (
            "ExecutionPlan provenance must carry the snapshot used at planning time so apply can detect snapshot drift."
        )
        assert execution_plan.scenario_name == instantiated.name, (
            "The planner must propagate the scenario identity through the "
            "plan so archival layers can correlate plans back to their "
            "originating compiled model."
        )
        assert execution_plan.is_valid, f"Plan must be valid; got diagnostics: {execution_plan.diagnostics!r}"

        provision_addresses = {op.address for op in execution_plan.provisioning.operations}
        assert EXPECTED_NODE_ADDRESS in provision_addresses, (
            f"Planner must emit a provisioning operation addressed "
            f"{EXPECTED_NODE_ADDRESS!r}; got {sorted(provision_addresses)!r}."
        )
        create_ops = [op for op in execution_plan.provisioning.operations if op.address == EXPECTED_NODE_ADDRESS]
        assert create_ops and create_ops[0].action == ChangeAction.CREATE, (
            "Against an empty snapshot the node must reconcile as CREATE; "
            "any other action means planning is conflating base state with "
            "the compiled model."
        )

        # ----- Stage 4: Execution (apply) ----------------------------
        manager = RuntimeManager(target)
        apply_result = manager.apply(execution_plan)

        error_diagnostics = [diag for diag in apply_result.diagnostics if diag.is_error]
        assert apply_result.success, (
            f"Apply must succeed on a clean scenario against an empty snapshot; diagnostics: {error_diagnostics!r}"
        )
        assert not error_diagnostics, (
            f"Apply must not surface error diagnostics on the happy path; got: {error_diagnostics!r}"
        )

        applied_snapshot = manager.snapshot
        provisioning_state = applied_snapshot.for_domain(RuntimeDomain.PROVISIONING)
        assert EXPECTED_NODE_ADDRESS in provisioning_state, (
            f"Applied provisioning snapshot must contain the canonical "
            f"address {EXPECTED_NODE_ADDRESS!r}. Loss of this address "
            f"would mean execution rewrote the identity between planning "
            f"and apply."
        )
        applied_entry = provisioning_state[EXPECTED_NODE_ADDRESS]
        assert applied_entry.resource_type == "node", (
            "The snapshot entry must carry the canonical resource type from the compiled model."
        )
        assert applied_entry.domain is RuntimeDomain.PROVISIONING
        assert EXPECTED_NODE_ADDRESS in apply_result.changed_addresses, (
            "ApplyResult must report the canonical address as changed so "
            "live-observation consumers can subscribe by canonical identity."
        )
        assert _no_variable_tokens(applied_entry.payload), (
            "Applied snapshot payload must not contain any ${...} tokens — "
            "meaning has been lost if unsubstituted placeholders reached "
            "the runtime state surface."
        )

        # ----- Stage 5: Live observation -----------------------------
        # The published live-observation surface is the manager snapshot's
        # orchestration_results / orchestration_history (portable envelope
        # defined in specs/formal/runtime-contracts/workflow-results.md).
        # The stub orchestrator produces a running workflow state keyed by
        # the compiled workflow address; that address — like the node
        # address — must derive from the compiled identity, not from raw SDL.
        orchestration_state = applied_snapshot.for_domain(RuntimeDomain.ORCHESTRATION)
        assert orchestration_state, (
            "Orchestration domain must contain at least one runtime entry "
            "after apply for a scenario that declares a workflow."
        )
        workflow_addresses = list(orchestration_state)
        for workflow_address in workflow_addresses:
            assert workflow_address.startswith("orchestration."), (
                f"Orchestration entry {workflow_address!r} must use the "
                f"canonical address namespace; raw SDL names must not leak "
                f"through the live-observation surface."
            )

        orchestration_results = applied_snapshot.orchestration_results
        if orchestration_results:
            # Portable workflow-execution-state envelope invariants.
            for address, state in orchestration_results.items():
                assert address in orchestration_state, (
                    f"Orchestration result {address!r} must correspond to a snapshot entry in the orchestration domain."
                )
                assert "state_schema_version" in state, (
                    "Workflow execution state must declare a "
                    "state_schema_version per RUN-300's meaning-preservation "
                    "contract (see workflow-results.md)."
                )
                assert "workflow_status" in state, (
                    "Workflow execution state must publish a "
                    "workflow_status; consumers key on it to interpret "
                    "the live envelope."
                )

    def test_reapplying_stale_plan_is_rejected_by_provenance_drift_check(self):
        """Drift rejection test.

        After a successful apply the manager's snapshot advances. Re-applying
        the original plan — whose ``base_snapshot`` is now stale — must
        surface a ``runtime.plan-snapshot-mismatch`` diagnostic and leave
        the manager state untouched. This exercises the provenance check
        at ``aces_processor/manager.py`` (the base_snapshot comparison in
        ``_provenance_diagnostics``) and is the concrete guarantee that
        RUN-300's "preserving scenario meaning across those stages" clause
        is enforced even against out-of-order or replayed plans.
        """

        raw = _raw_scenario()
        instantiated = instantiate_scenario(
            raw,
            parameters={"os_kind": PARAM_OS_KIND, "cpu_count": PARAM_CPU_COUNT},
        )
        model = compile_runtime_model(instantiated)
        target = create_stub_target()
        empty_snapshot = RuntimeSnapshot()
        stale_plan = plan_execution(
            model,
            target.manifest,
            empty_snapshot,
            target_name=target.name,
        )

        manager = RuntimeManager(target)
        first_apply = manager.apply(stale_plan)
        assert first_apply.success, "First apply must succeed to advance the snapshot."
        assert manager.snapshot != empty_snapshot, (
            "Manager snapshot must advance after a successful apply; otherwise the drift check below is a tautology."
        )

        # Attempt to apply the original plan a second time. Its base_snapshot
        # is still the empty snapshot, which no longer matches the manager.
        second_apply = manager.apply(stale_plan)

        assert not second_apply.success, (
            "Re-applying a plan whose base_snapshot no longer matches the "
            "manager's current snapshot must fail rather than silently "
            "reconcile against a different base."
        )
        drift_codes = {diag.code for diag in second_apply.diagnostics if diag.is_error}
        assert DRIFT_DIAGNOSTIC_CODE in drift_codes, (
            f"Expected provenance drift diagnostic {DRIFT_DIAGNOSTIC_CODE!r}; got error codes: {sorted(drift_codes)!r}"
        )
        assert second_apply.snapshot is manager.snapshot, (
            "On drift rejection the manager snapshot must be returned unchanged — no partial apply is permitted."
        )

    def test_unresolved_instantiation_parameter_is_rejected_before_compilation(self):
        """Invalid scenarios must not reach compilation.

        RUN-300 requires the processing model to carry *valid* scenarios
        through the pipeline. An unresolved variable reference is an
        instantiation-time error and must be raised before the compiler
        ever sees the scenario, so that no downstream stage can mistake
        an unsubstituted ``${...}`` token for a canonical identity.
        """

        raw = parse_sdl(
            textwrap.dedent(
                """
                name: run-300-unresolved
                variables:
                  os_kind:
                    type: string
                nodes:
                  vm1:
                    type: vm
                    os: ${os_kind}
                    resources: {ram: 1 gib, cpu: 1}
                """
            )
        )
        with pytest.raises(SDLInstantiationError):
            instantiate_scenario(raw, parameters={})
