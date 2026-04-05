"""Teacher Hint PRM — calls a teacher LLM to inject hints into the student's conversation."""

from __future__ import annotations

import logging
from typing import Any, Callable

from prm.base import ProcessRewardModel, register_prm

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful teaching assistant. A student is working on a software engineering "
    "task inside a sandboxed terminal environment. The student appears to be struggling. "
    "Your job is to provide a single, concise hint that helps the student make progress "
    "without giving away the full solution. Focus on the most impactful next step."
)

_DEFAULT_USER_PROMPT_TEMPLATE = (
    "## Task Instruction\n"
    "{task_instruction}\n\n"
    "## Recent Activity (last {k} exchanges)\n"
    "{recent_turns}\n\n"
    "Based on the student's recent activity, provide ONE concise hint (1-3 sentences) "
    "to help them make progress. Do NOT give the full solution."
)


@register_prm
class TeacherHint(ProcessRewardModel):
    """PRM that calls a teacher LLM to provide hints to a struggling student agent.

    Instead of terminating the agent (like ThrashingDetector), this PRM
    inspects the last ``k`` message pairs every ``check_interval`` turns and
    asks a teacher model for a concise hint.  The hint is injected into the
    student's next observation via the ``str`` return path of the turn
    callback.

    Constructor kwargs (all from YAML config):
        engine_type: Engine backend — ``"openai"``, ``"anthropic"``,
            ``"vllm_local"``, ``"google_gemini"``, ``"none"``.
        engine_kwargs: Dict passed to ``create_inference_engine()``.
        check_interval: Run the teacher every *N* turns.
        min_turns: Don't hint before this turn number.
        k: Number of recent message pairs to show the teacher.
        teacher_system_prompt: Custom system prompt (has sensible default).
        teacher_user_prompt_template: Custom user prompt template with
            ``{task_instruction}``, ``{recent_turns}``, ``{k}`` placeholders.
        max_hint_tokens: ``max_tokens`` passed to the teacher engine.
        hint_prefix / hint_suffix: Wrapping around the raw hint text.
    """

    def __init__(
        self,
        engine_type: str = "openai",
        engine_kwargs: dict[str, Any] | None = None,
        check_interval: int = 5,
        min_turns: int = 3,
        k: int = 6,
        teacher_system_prompt: str | None = None,
        teacher_user_prompt_template: str | None = None,
        max_hint_tokens: int = 2048,
        hint_prefix: str = "\n\n[HINT FROM TEACHER]: ",
        hint_suffix: str = "\n\n",
        **kwargs: Any,
    ):
        self.engine_type = engine_type
        self.engine_kwargs = dict(engine_kwargs or {})
        self.check_interval = check_interval
        self.min_turns = min_turns
        self.k = k
        self.teacher_system_prompt = teacher_system_prompt or _DEFAULT_SYSTEM_PROMPT
        self.teacher_user_prompt_template = (
            teacher_user_prompt_template or _DEFAULT_USER_PROMPT_TEMPLATE
        )
        self.max_hint_tokens = max_hint_tokens
        self.hint_prefix = hint_prefix
        self.hint_suffix = hint_suffix

        # Lazy-initialised on first call to get_hint().
        self._engine = None

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------

    @classmethod
    def name(cls) -> str:
        return "teacher_hint"

    # ------------------------------------------------------------------
    # Core PRM interface
    # ------------------------------------------------------------------

    def should_terminate(
        self,
        turn: int,
        trajectory_steps: list,
        messages: list,
    ) -> bool:
        """Teacher never kills the agent — always returns False."""
        return False

    # ------------------------------------------------------------------
    # Hint generation
    # ------------------------------------------------------------------

    def get_hint(
        self,
        turn: int,
        trajectory_steps: list,
        messages: list,
    ) -> str | None:
        """Generate a hint if timing gates pass, else return None."""
        if turn < self.min_turns:
            return None
        if turn % self.check_interval != 0:
            return None

        # Lazy engine init
        if self._engine is None:
            self._engine = self._create_engine()
            if self._engine is None:
                return None

        # Build the teacher prompt
        task_instruction = self._extract_task_instruction(messages)
        recent_turns = self._format_recent_turns(messages)
        user_prompt = self.teacher_user_prompt_template.format(
            task_instruction=task_instruction,
            recent_turns=recent_turns,
            k=self.k,
        )
        full_prompt = (
            f"### System\n{self.teacher_system_prompt}\n\n"
            f"### User\n{user_prompt}"
        )

        try:
            raw_hint = self._engine.generate(
                full_prompt,
                max_tokens=self.max_hint_tokens,
            )
        except Exception:
            logger.warning(
                "Teacher hint engine failed at turn %d; skipping hint.",
                turn,
                exc_info=True,
            )
            return None

        if not raw_hint or not raw_hint.strip():
            return None

        return f"{self.hint_prefix}{raw_hint.strip()}{self.hint_suffix}"

    # ------------------------------------------------------------------
    # Callback override
    # ------------------------------------------------------------------

    def as_turn_callback(self) -> Callable:
        """Return a closure that returns ``str`` (hint) or ``False`` (no hint)."""

        def _callback(
            turn: int,
            trajectory_steps: list,
            messages: list,
        ) -> str | bool:
            hint = self.get_hint(turn, trajectory_steps, messages)
            if hint:
                return hint
            return False

        return _callback

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_engine(self):
        """Lazy-create the inference engine via data.generation.engines."""
        try:
            from data.generation.engines import create_inference_engine

            return create_inference_engine(self.engine_type, **self.engine_kwargs)
        except Exception:
            logger.warning(
                "Failed to create teacher hint engine (type=%s); "
                "hints will be disabled for this run.",
                self.engine_type,
                exc_info=True,
            )
            return None

    @staticmethod
    def _extract_task_instruction(messages: list) -> str:
        """Extract the task instruction from the first message, truncated."""
        if not messages:
            return "(no instruction available)"
        content = messages[0].get("content", "")
        if len(content) > 4000:
            content = content[:4000] + "..."
        return content

    def _format_recent_turns(self, messages: list) -> str:
        """Format the last 2*k messages as [ROLE]\\ncontent blocks."""
        tail = messages[-(2 * self.k) :] if len(messages) > 2 * self.k else messages
        parts = []
        for msg in tail:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            if len(content) > 2000:
                content = content[:2000] + "..."
            parts.append(f"[{role}]\n{content}")
        return "\n\n".join(parts)
