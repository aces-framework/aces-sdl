"""Runtime execution protocols."""

from typing import Any, Protocol

from aces_processor.models import (
    ApplyResult,
    Diagnostic,
    EvaluationPlan,
    OrchestrationPlan,
    ParticipantEpisodeInitializeRequest,
    ParticipantEpisodeResetRequest,
    ParticipantEpisodeRestartRequest,
    ParticipantEpisodeTerminateRequest,
    ProvisioningPlan,
    RuntimeSnapshot,
)


class Provisioner(Protocol):
    """Applies provisioning plans to the target environment."""

    def validate(self, plan: ProvisioningPlan) -> list[Diagnostic]:
        """Return planner/runtime diagnostics for an apply attempt."""
        ...

    def apply(
        self,
        plan: ProvisioningPlan,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        """Apply provisioning reconciliation operations."""
        ...


class Orchestrator(Protocol):
    """Loads and starts the orchestration graph."""

    def start(
        self,
        plan: OrchestrationPlan,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        """Start or refresh orchestration state."""
        ...

    def status(self) -> dict[str, Any]:
        """Return current orchestration status."""
        ...

    def results(self) -> dict[str, dict[str, Any]]:
        """Return most recent workflow execution state envelope."""
        ...

    def history(self) -> dict[str, list[dict[str, Any]]]:
        """Return workflow execution history events."""
        ...

    def stop(self, snapshot: RuntimeSnapshot) -> ApplyResult:
        """Stop orchestration and clear orchestration state."""
        ...


class Evaluator(Protocol):
    """Loads and starts the evaluation graph."""

    def start(
        self,
        plan: EvaluationPlan,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        """Start or refresh evaluation state."""
        ...

    def status(self) -> dict[str, Any]:
        """Return current evaluator status."""
        ...

    def results(self) -> dict[str, dict[str, Any]]:
        """Return most recent evaluation results."""
        ...

    def history(self) -> dict[str, list[dict[str, Any]]]:
        """Return evaluation history events."""
        ...

    def stop(self, snapshot: RuntimeSnapshot) -> ApplyResult:
        """Stop evaluation and clear evaluation state."""
        ...


class ParticipantRuntime(Protocol):
    """Drives participant episode lifecycle transitions (RUN-311).

    The four control methods map 1:1 to the ``ParticipantEpisodeControlAction``
    enum. Each method is idempotent from the caller's perspective — the
    control plane routes duplicate submissions through its idempotency
    record store before reaching the backend. The backend is responsible
    for mutating ``RuntimeSnapshot.participant_episode_results`` and
    ``RuntimeSnapshot.participant_episode_history`` in a way that stays
    consistent with the RUN-311 invariants enforced by
    ``iter_participant_episode_snapshot_violations``.
    """

    def initialize(
        self,
        request: ParticipantEpisodeInitializeRequest,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        """Create the first episode for a participant (sequence_number=0)."""
        ...

    def reset(
        self,
        request: ParticipantEpisodeResetRequest,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        """Start a new episode instance from a non-terminal predecessor.

        Must allocate a new ``episode_id`` and increment
        ``sequence_number``, preserving the stable participant identity and
        linking back to the prior ``episode_id`` via ``previous_episode_id``.
        """
        ...

    def restart(
        self,
        request: ParticipantEpisodeRestartRequest,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        """Start a new episode instance from a terminated predecessor.

        Must allocate a new ``episode_id`` and increment
        ``sequence_number``, preserving the stable participant identity and
        linking back to the prior ``episode_id`` via ``previous_episode_id``.
        """
        ...

    def terminate(
        self,
        request: ParticipantEpisodeTerminateRequest,
        snapshot: RuntimeSnapshot,
    ) -> ApplyResult:
        """Drive the current episode to ``TERMINATED`` with the given reason."""
        ...

    def status(self) -> dict[str, Any]:
        """Return current participant runtime status."""
        ...

    def results(self) -> dict[str, dict[str, Any]]:
        """Return the most recent participant episode result envelopes."""
        ...

    def history(self) -> dict[str, list[dict[str, Any]]]:
        """Return participant episode history events."""
        ...
