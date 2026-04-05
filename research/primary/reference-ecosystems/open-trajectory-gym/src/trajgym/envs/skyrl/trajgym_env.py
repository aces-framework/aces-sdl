"""SkyRL-Gym BaseTextEnv subclass bridging SkyRL to execution environments.

Each SkyRL agent loop gets its own env instance with a pluggable StepAgent
for tool parsing + execution. The default agent (DefaultStepAgent) includes
resilient retry/feedback semantics via ``resilient_mode=True``.

Architecture:
    SkyRL SkyRLGymGenerator -> agent_loop()
        -> env.init(prompt) -> agent.reset()
        -> env.step(action) -> agent.step(), compute reward via Reward
        -> env.close() -> agent.close()

The env receives raw LLM text output, delegates tool parsing + execution
to the StepAgent, and computes rewards from agent state.
"""

import importlib
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any

from trajgym.agent.rollout_status import RolloutStatus, normalize_rollout_status
from trajgym.parsing.tool_calls import (
    parse_tool_calls,  # noqa: F401 — re-exported for backward compat
)

logger = logging.getLogger(__name__)

# Type aliases matching SkyRL's ConversationType
ConversationType = list[dict[str, Any]]

# Pattern for stripping <think>...</think> reasoning blocks from LLM output.
# Qwen3.5 and similar models emit these during chain-of-thought; they must be
# removed before tool-call parsing to avoid confusing the parser with tool
# references inside the reasoning block.
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


# ---------------------------------------------------------------------------
# Agent class resolution
# ---------------------------------------------------------------------------


def _resolve_class(dotpath: str | None):
    """Resolve a dotted path string to a class.

    Example: "my_module.MyAgent" -> <class my_module.MyAgent>

    Returns None if dotpath is None or empty.
    Raises ImportError/AttributeError if the path is invalid.
    """
    if not dotpath:
        return None
    parts = dotpath.rsplit(".", 1)
    if len(parts) == 2:
        module = importlib.import_module(parts[0])
        return getattr(module, parts[1])
    # Single name — try importing as module (unlikely for a class)
    return importlib.import_module(dotpath)


# ---------------------------------------------------------------------------
# Lazy import of BaseTextEnv — avoids hard dependency on skyrl_gym at
# module load time (allows running validate / other CLIs without skyrl).
# ---------------------------------------------------------------------------


def _get_base_class():
    """Import BaseTextEnv lazily to avoid hard dep on skyrl_gym."""
    try:
        from skyrl_gym.envs.base_text_env import BaseTextEnv

        return BaseTextEnv
    except ImportError:
        # Fallback: return object so the class can still be defined
        # (won't pass SkyRL isinstance checks but allows unit testing)
        logger.warning(
            "skyrl_gym not installed — TrajGymTextEnv will not register with SkyRL"
        )
        return object


# Build the class dynamically to handle missing skyrl_gym gracefully
_Base = _get_base_class()


class TrajGymTextEnv(_Base):
    """SkyRL-Gym BaseTextEnv for CTF challenges via pluggable StepAgent.

    Each instance manages one episode. Tool parsing + execution is delegated
    to a StepAgent (default: DefaultStepAgent). The env owns reward computation,
    tool schema injection, and SkyRL protocol compliance.

    SkyRL's ``make()`` merges registered kwargs (static config) with
    per-sample kwargs from the dataset:

    - **Static** (from ``register(kwargs=...)``)::

        reward_config: dict of Reward weight overrides
        agent_class: dotted path to StepAgent class (optional)
        agent_kwargs: dict of kwargs for StepAgent constructor (optional)

    - **Per-sample** (from dataset ``extras``)::

        ground_truth_flag: expected flag string
        optimal_steps: optimal step count for efficiency reward
        challenge_id: challenge identifier

    Both arrive as keyword args; per-sample data is nested under ``extras``.
    """

    def __init__(
        self,
        env_config: Any = None,
        extras: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        if _Base is not object:
            super().__init__()

        extras = extras or {}

        raw_max_turns = extras.get("max_turns") or kwargs.get("max_turns", 15)
        # Clamp max_turns to max_tool_calling_iterations if provided.
        # This ensures the env's done=True fires at or before SkyRL's
        # generator stops calling env.step(), so terminal Reward is
        # always computed within the agent_loop rather than only in close().
        max_tool_iters = extras.get("max_tool_calling_iterations") or kwargs.get(
            "max_tool_calling_iterations"
        )
        if max_tool_iters is not None:
            max_tool_iters = int(max_tool_iters)
            if int(raw_max_turns) > max_tool_iters:
                logger.warning(
                    "Clamping max_turns from %s to max_tool_calling_iterations=%d "
                    "(env max_turns must not exceed generator iteration limit)",
                    raw_max_turns,
                    max_tool_iters,
                )
            self.max_turns = min(int(raw_max_turns), max_tool_iters)
        else:
            self.max_turns = int(raw_max_turns)
        self._base_max_turns = int(self.max_turns)
        self.turns = 0

        logger.info(
            "TrajGymTextEnv max_turns=%d (raw=%s, max_tool_calling_iterations=%s)",
            self.max_turns,
            raw_max_turns,
            max_tool_iters,
        )

        # Optional progressive horizon schedule:
        #   {"rounds": [12, 24, 40, 60], "step_interval": 80}
        # If set, max_turns is reduced/expanded by global_step stage.
        self._horizon_schedule: dict[str, Any] | None = extras.get(
            "horizon_schedule"
        ) or kwargs.get("horizon_schedule")

        # Tool schemas — SkyRL uses these for prompt injection.
        from trajgym.formatters.tool_registry import AGENT_TOOLS

        self.tools = AGENT_TOOLS
        self.tool_groups = []

        # Context-budget safety net: if max_input_length is provided,
        # the env will proactively set done=True when estimated context
        # tokens reach 85% of the budget.  This ensures terminal Reward
        # fires BEFORE SkyRL's agent_loop breaks due to length overflow
        # (which calls close() instead of step(), losing the reward).
        self._max_input_length: int = int(
            extras.get("max_input_length") or kwargs.get("max_input_length", 0)
        )
        # Rough chars-per-token ratio for context estimation.
        self._chars_per_token: float = 3.5
        # Budget threshold: trigger done at this fraction of max_input_length.
        self._context_budget_threshold: float = 0.85

        # Step-wise trajectory rewards: when enabled, per-step rewards
        # include small format-compliance and phase-progression signals
        # instead of returning 0.0 for all non-terminal steps.
        self._step_wise: bool = bool(
            extras.get("step_wise_trajectories")
            or kwargs.get("step_wise_trajectories", False)
        )

        # Native tool schemas: when True, tool schemas are injected via
        # chat_template_kwargs["tools"] → apply_chat_template(tools=...)
        # so the tokenizer formats them per the model's native template.
        # Skip _inject_tool_schemas() text injection to avoid duplication.
        self._native_tool_schemas: bool = bool(
            extras.get("native_tool_schemas")
            or kwargs.get("native_tool_schemas", False)
        )

        # Track tool call count before each step for per-step reward.
        self._prev_tool_call_count: int = 0

        # Tool call format for prompt injection.
        # "hermes" (default): <tool_call>{"name": ..., "arguments": ...}</tool_call>
        # "qwen3_coder": <tool_call><function=name><parameter=k>v</parameter></function></tool_call>
        # "glm4":  <tool_call>func_name<arg_key>k</arg_key><arg_value>v</arg_value></tool_call>
        self._tool_call_format: str = extras.get("tool_call_format") or kwargs.get(
            "tool_call_format", "hermes"
        )

        # Strip <think>...</think> reasoning blocks from LLM output before
        # passing to the agent for tool-call parsing. Qwen3.5 emits these
        # blocks during chain-of-thought; leaving them in can confuse the
        # parser when the model mentions tool names inside its reasoning.
        # Default True — set strip_think: false in env_kwargs to disable.
        _raw_strip_think = (
            extras.get("strip_think")
            if extras.get("strip_think") is not None
            else kwargs.get("strip_think", True)
        )
        self._strip_think: bool = bool(_raw_strip_think)

        # Reconstruct reward function from serializable config dict.
        # If reward_config is missing/empty, use Reward defaults instead of
        # silently falling back to binary terminal reward.
        reward_config = kwargs.get("reward_config", extras.get("reward_config", {}))
        if reward_config is None:
            reward_config = {}
        if not isinstance(reward_config, dict):
            logger.warning(
                "Invalid reward_config type %s; using Reward defaults.",
                type(reward_config).__name__,
            )
            reward_config = {}
        weight_keys = [k for k in reward_config if k.endswith("_weight")]
        logger.info(
            "Reward config received (%d keys, %d weight keys): %s",
            len(reward_config),
            len(weight_keys),
            {k: v for k, v in reward_config.items() if k.endswith("_weight")},
        )
        try:
            from trajgym.training.online_rl.step_reward import create_reward_fn

            self._reward_fn = create_reward_fn({"reward": reward_config})
        except Exception as exc:
            logger.warning(
                "Failed to create reward function: %s — using binary fallback", exc
            )
            self._reward_fn = None

        # Per-episode data (set from dataset sample extras)
        self._ground_truth_flag: str | None = extras.get("ground_truth_flag")
        self._optimal_steps: int | None = extras.get("optimal_steps")
        self._challenge_id: str | None = extras.get("challenge_id")
        self._infra_type: str = str(
            extras.get("infra_type") or kwargs.get("infra_type") or "docker"
        )
        self._path_hint: str | None = extras.get("path_hint") or kwargs.get("path_hint")
        # Per-challenge init script name (default: init_script.sh).
        self._init_script: str = str(
            extras.get("init_script") or kwargs.get("init_script") or "init_script.sh"
        )
        # Subdirs considered safe for release artifacts (configurable per-benchmark).
        self._release_subdirs: list[str] = list(
            extras.get("release_subdirs")
            or kwargs.get("release_subdirs")
            or ["release", "challenge", "dist", "public"]
        )
        self._workspace_root: str = str(
            extras.get("workspace_root")
            or kwargs.get("workspace_root")
            or os.environ.get(
                "TRAJGYM_WORKSPACE_ROOT",
                os.environ.get("OPENCTF_WORKSPACE_ROOT", "/tmp/trajgym-workspaces"),
            )
        )
        raw_workdir = (
            extras.get("challenge_workdir")
            or kwargs.get("challenge_workdir")
            or os.getenv("CHALLENGE_WORKDIR")
            or "/root/challenge"
        )
        self._challenge_workdir: str = str(raw_workdir).strip() or "/root/challenge"
        self._ephemeral_workspace: bool = False

        # Target URL for the challenge
        raw_target = extras.get("target", kwargs.get("target", ""))
        self._target: str = str(raw_target).strip() if raw_target else ""

        # Trajectory logging (optional, for post-run analysis).
        # The output_dir is a plain string path, not a logger object, because
        # this must be serializable through Ray. Each env worker creates its
        # own TrajectoryLogger instance writing to the shared output dir.
        self._trajectory_output_dir: str | None = kwargs.get(
            "trajectory_output_dir"
        ) or extras.get("trajectory_output_dir")
        self._trajectory_logger = None
        self._episode_trajectory_logged = False
        if self._trajectory_output_dir:
            try:
                from trajgym.training.online_rl.trajectory_logger import (
                    TrajectoryLogger,
                )

                # Reuse the same TensorBoard logdir set by _resolve_skyrl_logger()
                # so environment scalars appear alongside SkyRL training metrics.
                tb_dir = os.environ.get("TENSORBOARD_LOGDIR")
                self._trajectory_logger = TrajectoryLogger(
                    self._trajectory_output_dir,
                    enabled=True,
                    tensorboard_dir=tb_dir,
                )
            except Exception as exc:
                logger.warning("Failed to create TrajectoryLogger: %s", exc)

        # Global step counter (set from env extras per sample).
        self._global_step: int = extras.get("global_step", 0)
        self._generation_idx: int = extras.get("generation_idx", 0)
        # Challenge metadata for logging
        self._category: str | None = extras.get("category")
        self._difficulty: str | None = extras.get("difficulty")
        # Prompt messages for logging (set in init())
        self._prompt_messages: list | None = None
        self._last_rollout_status: str = RolloutStatus.OK.value
        self._status_counts: dict[str, int] = {}
        self._timing_totals: dict[str, float] = {
            "parse_s": 0.0,
            "execute_s": 0.0,
            "total_s": 0.0,
        }
        # Rollout quality filter: statuses that should not contribute reward.
        # PARSER_ERROR removed from defaults — zeroing reward for episodes
        # where the *last* step had a parse failure kills learning signal
        # even when earlier steps made good tool calls.  Parser errors are
        # already penalized via format_weight in Reward.
        hard_mask_statuses = (
            extras.get("hard_mask_statuses")
            or kwargs.get("hard_mask_statuses")
            or [
                RolloutStatus.INFRA_UNREACHABLE.value,
                RolloutStatus.TARGET_MISMATCH.value,
                RolloutStatus.TOOL_TIMEOUT.value,
            ]
        )
        self._hard_mask_statuses = {
            str(s).strip() for s in hard_mask_statuses if str(s).strip()
        }
        # Optional warmup mode: clamp non-positive rollout rewards to 0 during
        # early steps, which avoids strong negative gradients before the policy
        # learns to issue stable tool calls.
        raw_positive_only_until_step = (
            extras.get("positive_only_until_step")
            if extras.get("positive_only_until_step") is not None
            else kwargs.get("positive_only_until_step", 0)
        )
        try:
            self._positive_only_until_step = int(raw_positive_only_until_step or 0)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid positive_only_until_step=%r; defaulting to 0.",
                raw_positive_only_until_step,
            )
            self._positive_only_until_step = 0

        raw_positive_only_reward_floor = (
            extras.get("positive_only_reward_floor")
            if extras.get("positive_only_reward_floor") is not None
            else kwargs.get("positive_only_reward_floor", 0.0)
        )
        try:
            self._positive_only_reward_floor = float(
                raw_positive_only_reward_floor or 0.0
            )
        except (TypeError, ValueError):
            logger.warning(
                "Invalid positive_only_reward_floor=%r; defaulting to 0.0.",
                raw_positive_only_reward_floor,
            )
            self._positive_only_reward_floor = 0.0

        # Resolve and create the pluggable StepAgent.
        # agent_class is a dotted path string (Ray-safe serialization).
        # Default runtime agent is DefaultStepAgent (resilient_mode=True).
        agent_class_path = kwargs.get("agent_class") or extras.get("agent_class")
        agent_cls = _resolve_class(agent_class_path)
        if agent_cls is None:
            from trajgym.agent.default_agent import DefaultStepAgent

            agent_cls = DefaultStepAgent

        agent_kwargs = dict(
            kwargs.get("agent_kwargs") or extras.get("agent_kwargs") or {}
        )
        # Pass executor config to agent if not already specified
        if "executor_type" not in agent_kwargs:
            agent_kwargs["executor_type"] = extras.get(
                "executor_type", kwargs.get("executor_type", "subprocess")
            )
        # Keep parser feedback and runtime prompt format aligned.
        agent_kwargs.setdefault("tool_call_format", self._tool_call_format)

        self._agent = agent_cls(**agent_kwargs)

        # Validate reward-critical attributes and warn early for BYO agents.
        from trajgym.agent.protocol import validate_step_agent

        agent_warnings = validate_step_agent(self._agent)
        for w in agent_warnings:
            logger.warning("StepAgent validation: %s", w)

        # Let agent override tool schemas if it provides them
        agent_tools = getattr(self._agent, "tools", None)
        if agent_tools is not None:
            self.tools = agent_tools

    @property
    def _all_text(self) -> str:
        """Proxy to agent's all_text for backward compatibility."""
        return getattr(self._agent, "all_text", "")

    @property
    def _tool_calls_history(self) -> list:
        """Proxy to agent's tool_calls_history for backward compatibility."""
        return getattr(self._agent, "tool_calls_history", [])

    @property
    def _tool_outputs(self) -> list:
        """Proxy to agent's tool_outputs for backward compatibility."""
        return getattr(self._agent, "tool_outputs", [])

    def init(self, prompt: ConversationType) -> tuple:
        """Initialize episode: reset agent, return prompt with tool schemas.

        Args:
            prompt: Initial conversation (system + user messages).

        Returns:
            (prompt, metadata) — prompt with tool schemas injected, metadata has episode_id.
        """
        # Progressive horizon: clamp max turns by stage if schedule is enabled.
        self.max_turns = self._resolve_max_turns_for_step(self._global_step)
        self._setup_workspace()
        # For static challenges, stage challenge assets into /root/challenge.
        # For docker challenges, clean the workspace to prevent cross-episode
        # contamination (stale files from prior episodes mislead the model).
        if self._infra_type == "static":
            self._prepare_static_workspace()
        else:
            self._clean_workspace()
            # Docker challenges may also have local release artifacts the agent
            # needs (e.g. skilift's top.v, randsubware's chall.py).  Stage them
            # into /root/challenge/ after cleanup so the model doesn't waste
            # turns searching the filesystem.  Re-uses the same resolution +
            # copy logic as _prepare_static_workspace().
            self._provision_docker_release_artifacts()
        # Avoid empty target fallback to localhost for static rows.
        if not self._target:
            if self._infra_type == "static":
                self._target = self._file_target_for_workdir(self._challenge_workdir)
            else:
                self._target = os.getenv("CHALLENGE_TARGET", "http://localhost:8080")
        prompt = self._rewrite_prompt_workspace(prompt)
        self._agent.reset(
            target=self._target,
            ground_truth_flag=self._ground_truth_flag or "",
            max_steps=self.max_turns,
            tool_call_format=self._tool_call_format,
            challenge_workdir=self._challenge_workdir,
            prompt_messages=prompt,
            challenge_id=self._challenge_id,
            category=self._category,
            difficulty=self._difficulty,
            infra_type=self._infra_type,
            objective=(
                str(prompt[-1].get("content", "")).strip()
                if prompt and isinstance(prompt[-1], dict)
                else ""
            ),
        )

        self.turns = 0
        self._prev_tool_call_count = 0
        self._last_rollout_status = RolloutStatus.OK.value
        self._status_counts = {}
        self._timing_totals = {"parse_s": 0.0, "execute_s": 0.0, "total_s": 0.0}
        self._episode_trajectory_logged = False

        # If the BYO agent controls its own prompts (RL proxy mode), fetch it here
        if hasattr(self._agent, "get_initial_prompt"):
            proxy_prompt = self._agent.get_initial_prompt()
            if proxy_prompt is not None:
                prompt = proxy_prompt

        # Inject tool schemas into the system message so the model knows
        # what tools are available during Online RL rollouts.
        #
        # When native_tool_schemas=True, tools are passed via
        # chat_template_kwargs["tools"] → apply_chat_template(tools=...)
        # and the tokenizer formats them per the model's pretrained format.
        # Skip text injection to avoid duplicate/conflicting schemas.
        if self._native_tool_schemas:
            logger.info(
                "Native tool schemas active — skipping _inject_tool_schemas() "
                "(tools= will be formatted by tokenizer chat template)."
            )
        else:
            prompt = self._inject_tool_schemas(prompt)

        # Capture prompt for trajectory logging (shallow copy to avoid mutation).
        self._prompt_messages = list(prompt)

        logger.debug(
            "TrajGymTextEnv initialized: challenge=%s",
            self._challenge_id,
        )
        return prompt, {}

    @staticmethod
    def _file_target_for_workdir(workdir: str) -> str:
        path = (workdir or "/root/challenge").rstrip("/")
        if not path:
            path = "/root/challenge"
        return f"file://{path}/"

    def _setup_workspace(self) -> None:
        """Select or create the per-episode workspace path."""
        if self._infra_type != "static":
            self._ephemeral_workspace = False
            self._challenge_workdir = (
                str(
                    os.getenv(
                        "CHALLENGE_WORKDIR",
                        self._challenge_workdir or "/root/challenge",
                    )
                ).strip()
                or "/root/challenge"
            )
            return

        self._cleanup_ephemeral_workspace()
        os.makedirs(self._workspace_root, exist_ok=True)
        challenge_slug = re.sub(
            r"[^A-Za-z0-9_.-]+", "_", str(self._challenge_id or "challenge")
        ).strip("_")
        if not challenge_slug:
            challenge_slug = "challenge"
        self._challenge_workdir = tempfile.mkdtemp(
            prefix=f"{challenge_slug}_",
            dir=self._workspace_root,
        )
        self._ephemeral_workspace = True
        self._target = self._file_target_for_workdir(self._challenge_workdir)

    def _cleanup_ephemeral_workspace(self) -> None:
        """Delete prior per-episode static workspace if it is ephemeral."""
        if not self._ephemeral_workspace:
            return
        target_dir = str(self._challenge_workdir or "").strip()
        if not target_dir:
            return
        try:
            root_abs = os.path.abspath(self._workspace_root)
            target_abs = os.path.abspath(target_dir)
            if target_abs.startswith(root_abs + os.sep) and os.path.isdir(target_abs):
                shutil.rmtree(target_abs, ignore_errors=True)
        except Exception as exc:
            logger.debug("Failed to cleanup workspace %s: %s", target_dir, exc)
        finally:
            self._ephemeral_workspace = False

    def _rewrite_prompt_workspace(self, prompt: ConversationType) -> ConversationType:
        """Rewrite hardcoded /root/challenge references to the active workspace."""
        workdir = str(self._challenge_workdir or "").strip()
        if not workdir:
            return prompt
        normalized = workdir.rstrip("/")
        if not normalized:
            return prompt
        file_target = self._file_target_for_workdir(normalized)
        rewrites = (
            ("file:///root/challenge/", file_target),
            ("/root/challenge/", f"{normalized}/"),
            ("/root/challenge", normalized),
        )
        out: ConversationType = []
        for msg in prompt:
            if not isinstance(msg, dict):
                out.append(msg)
                continue
            updated = dict(msg)
            content = updated.get("content")
            if isinstance(content, str):
                for old, new in rewrites:
                    content = content.replace(old, new)
                updated["content"] = content
            out.append(updated)
        return out

    def _resolve_max_turns_for_step(self, global_step: int) -> int:
        """Return effective max turns for current training step."""
        schedule = self._horizon_schedule
        if not isinstance(schedule, dict):
            return self._base_max_turns
        rounds_raw = schedule.get("rounds")
        if not isinstance(rounds_raw, list):
            return self._base_max_turns
        rounds = []
        for item in rounds_raw:
            try:
                v = int(item)
            except (TypeError, ValueError):
                continue
            if v > 0:
                rounds.append(v)
        if not rounds:
            return self._base_max_turns
        try:
            step_interval = int(schedule.get("step_interval", 1))
        except (TypeError, ValueError):
            step_interval = 1
        step_interval = max(1, step_interval)
        stage = max(0, int(global_step) // step_interval)
        if stage >= len(rounds):
            stage = len(rounds) - 1
        return max(1, min(self._base_max_turns, int(rounds[stage])))

    def _resolve_static_source_path(self) -> str | None:
        """Resolve static challenge source path from path_hint + known roots."""
        hint = (self._path_hint or "").strip()
        if not hint:
            return None
        if os.path.isabs(hint) and os.path.exists(hint):
            return hint

        roots: list[str] = []
        env_roots = os.environ.get(
            "TRAJGYM_BENCHMARK_ROOTS", os.environ.get("OPENCTF_BENCHMARK_ROOTS", "")
        )
        if env_roots:
            roots.extend([p.strip() for p in env_roots.split(":") if p.strip()])
        roots.extend(
            [
                "/workspace/benchmarks/cybench",
                "/workspace/cybench",
                "/workspace/cybench-patched",
                "/workspace/open-trajectory-gym",
            ]
        )

        candidates: list[str] = []
        for root in roots:
            candidates.append(os.path.join(root, hint))
            if hint.startswith("benchmark/"):
                candidates.append(os.path.join(root, hint[len("benchmark/") :]))

        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _clean_workspace(self) -> None:
        """Remove stale files from /root/challenge between docker episodes.

        Without cleanup, files written by previous episodes (hallucinated code,
        curl artifacts, fake flags) persist and mislead the model into exploring
        the filesystem instead of making HTTP requests to the challenge service.
        """
        target_dir = self._challenge_workdir
        if not os.path.exists(target_dir):
            return
        for name in os.listdir(target_dir):
            path = os.path.join(target_dir, name)
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.remove(path)
            except OSError:
                continue
        logger.debug(
            "Cleaned workspace %s for docker challenge=%s",
            target_dir,
            self._challenge_id,
        )

    def _provision_docker_release_artifacts(self) -> None:
        """Copy release artifacts into /root/challenge/ for docker challenges.

        CyBench docker challenges use ``init_script.sh`` to stage specific
        release files into the agent's working directory.  We run the script
        directly (it only does ``cp``/``unzip`` operations) so the agent sees
        exactly the same files as the benchmark intended — no writeups,
        metadata, docker sources, or solution files leak into the workspace.

        Fallback: if no ``init_script.sh`` exists, copy from the first found
        ``release/``, ``challenge/``, or ``dist/`` subdirectory (but never the
        top-level benchmark dir, which contains writeups and metadata).
        """
        src = self._resolve_static_source_path()
        if not src:
            return

        target_dir = self._challenge_workdir
        os.makedirs(target_dir, exist_ok=True)

        # Preferred: run the benchmark's init script which copies exactly the
        # right files.  Script name is configurable per-challenge/benchmark
        # (default: init_script.sh for CyBench).
        init_script = os.path.join(src, self._init_script)
        if os.path.isfile(init_script):
            try:
                result = subprocess.run(
                    ["bash", init_script, target_dir],
                    cwd=src,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                staged = os.listdir(target_dir)
                logger.info(
                    "Staged docker release artifacts via init_script: "
                    "challenge=%s source=%s target=%s files=%d rc=%d",
                    self._challenge_id,
                    src,
                    target_dir,
                    len(staged),
                    result.returncode,
                )
                if result.returncode != 0 and result.stderr:
                    logger.warning(
                        "init_script.sh stderr for %s: %s",
                        self._challenge_id,
                        result.stderr[:500],
                    )
                return
            except (subprocess.TimeoutExpired, OSError) as exc:
                logger.warning(
                    "init_script.sh failed for %s, falling back: %s",
                    self._challenge_id,
                    exc,
                )

        # Fallback: copy from known release subdirs only.
        # Never copy the top-level dir (contains writeups, metadata, etc.).
        # Subdirs list is configurable per-benchmark via release_subdirs.
        payload = None
        for subdir in self._release_subdirs:
            candidate = os.path.join(src, subdir)
            if os.path.isdir(candidate):
                payload = candidate
                break

        if payload is None:
            logger.debug(
                "No init_script.sh or release subdir for docker challenge %s",
                self._challenge_id,
            )
            return

        try:
            entries = os.listdir(payload)
        except OSError:
            return
        if not entries:
            return

        for name in entries:
            src_path = os.path.join(payload, name)
            dst_path = os.path.join(target_dir, name)
            try:
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(src_path, dst_path)
            except (OSError, shutil.Error) as exc:
                logger.warning(
                    "Failed to stage docker release artifact %s → %s: %s",
                    src_path,
                    dst_path,
                    exc,
                )

        logger.info(
            "Staged docker release artifacts (fallback): challenge=%s "
            "source=%s payload=%s target=%s files=%d",
            self._challenge_id,
            src,
            payload,
            target_dir,
            len(entries),
        )

    def _prepare_static_workspace(self) -> None:
        """Stage static challenge files into /root/challenge for tool access."""
        src = self._resolve_static_source_path()
        target_dir = self._challenge_workdir
        self._target = self._file_target_for_workdir(target_dir)
        if not src:
            logger.warning(
                "Static challenge path not found for challenge=%s path_hint=%r",
                self._challenge_id,
                self._path_hint,
            )
            return

        os.makedirs(target_dir, exist_ok=True)

        # Preferred: run the benchmark's init script which extracts/copies
        # exactly the right files (e.g. unzips .zip releases, places binaries).
        # Same pattern as _provision_docker_release_artifacts().
        init_script = os.path.join(src, self._init_script)
        if os.path.isfile(init_script):
            try:
                result = subprocess.run(
                    ["bash", init_script, target_dir],
                    cwd=src,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                staged = os.listdir(target_dir)
                logger.info(
                    "Prepared static workspace via init_script: "
                    "challenge=%s source=%s target=%s files=%d rc=%d",
                    self._challenge_id,
                    src,
                    target_dir,
                    len(staged),
                    result.returncode,
                )
                if result.returncode != 0 and result.stderr:
                    logger.warning(
                        "init_script.sh stderr for static %s: %s",
                        self._challenge_id,
                        result.stderr[:500],
                    )
                return
            except (subprocess.TimeoutExpired, OSError) as exc:
                logger.warning(
                    "init_script.sh failed for static %s, falling back: %s",
                    self._challenge_id,
                    exc,
                )

        # Fallback: direct copy from release/challenge/dist subdirs.
        payload = src
        for subdir in ("release", "challenge", "dist"):
            candidate = os.path.join(src, subdir)
            if os.path.isdir(candidate):
                payload = candidate
                break

        for name in os.listdir(target_dir):
            path = os.path.join(target_dir, name)
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except FileNotFoundError:
                continue

        for name in os.listdir(payload):
            src_path = os.path.join(payload, name)
            dst_path = os.path.join(target_dir, name)
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, dst_path)

        logger.info(
            "Prepared static workspace: challenge=%s source=%s payload=%s target=%s",
            self._challenge_id,
            src,
            payload,
            target_dir,
        )

    def _inject_tool_schemas(self, prompt: ConversationType) -> ConversationType:
        """Prepend tool schemas to the system message in the prompt.

        If no system message exists, one is created. If the system message
        already contains tool schema text, injection is skipped to avoid
        duplication.

        Returns a new list (does not mutate the input).
        """
        if not self.tools:
            return prompt

        # Format tool schemas as a concise block
        tool_lines = []
        for tool_def in self.tools:
            fn = tool_def.get("function", {})
            name = fn.get("name", "")
            desc = fn.get("description", "")
            params = fn.get("parameters", {})
            required = params.get("required", [])
            props = params.get("properties", {})

            param_parts = []
            for pname, pschema in props.items():
                ptype = pschema.get("type", "string")
                req_marker = " [required]" if pname in required else ""
                param_parts.append(f"  - {pname}: {ptype}{req_marker}")

            param_str = "\n".join(param_parts) if param_parts else "  (no parameters)"
            tool_lines.append(f"- {name}: {desc}\n{param_str}")

        # Model-aware format instruction
        _FORMAT_INSTRUCTIONS = {
            "hermes": (
                'Call tools using: <tool_call>{"name": "tool_name", "arguments": {...}}</tool_call>'
            ),
            "glm4": (
                "Call tools using: <tool_call>tool_name"
                "<arg_key>param</arg_key><arg_value>value</arg_value>"
                "</tool_call>"
            ),
            "qwen3_coder": (
                "Call tools using: <tool_call><function=tool_name>"
                "<parameter=param>value</parameter>"
                "</function></tool_call>"
            ),
            "command_xml": (
                "Use strict command XML and output EXACTLY one action tag per turn: "
                "either <COMMAND maxtime=30>command</COMMAND> or <FLAG>flag_value</FLAG>. "
                "Do not output <tool_call>, JSON, <think>, explanations, or multiple tags."
            ),
        }
        fmt_instruction = _FORMAT_INSTRUCTIONS.get(
            self._tool_call_format, _FORMAT_INSTRUCTIONS["hermes"]
        )

        tools_block = (
            "\n\n# Available Tools\n\n"
            + fmt_instruction
            + "\n\n"
            + "\n".join(tool_lines)
            + "\n"
        )

        # Make a shallow copy to avoid mutating the original
        prompt = list(prompt)

        # Find or create system message
        if prompt and prompt[0].get("role") == "system":
            sys_content = prompt[0].get("content", "")
            # Skip if tool schemas already present (check multiple variants:
            # "# Available Tools" from our injection, "Available tools:" from
            # Online RL training data system prompts, "<tools>" from Nanbeige/Qwen
            # native format).  Prevents double injection that wastes ~800
            # context tokens.
            has_tools = (
                "# Available Tools" in sys_content
                or "Available tools:" in sys_content
                or "Available tools\n" in sys_content
                or "<tools>" in sys_content
            )
            has_format_instruction = (
                "Call tools using:" in sys_content or "<tool_call>" in sys_content
            )
            if not has_tools:
                prompt[0] = {
                    **prompt[0],
                    "content": sys_content + tools_block,
                }
            elif not has_format_instruction:
                prompt[0] = {
                    **prompt[0],
                    "content": (
                        sys_content
                        + "\n\n# Tool Call Format\n\n"
                        + fmt_instruction
                        + "\n"
                    ),
                }
        else:
            # No system message — prepend one with tool schemas
            prompt.insert(
                0,
                {
                    "role": "system",
                    "content": "You are a CTF agent with access to the following tools."
                    + tools_block,
                },
            )

        return prompt

    def step(self, action: str) -> dict[str, Any]:
        """Process LLM output: delegate to agent, compute reward.

        Args:
            action: Raw LLM text output (may contain tool calls).

        Returns:
            BaseTextEnvStepOutput dict with observations, reward, done, metadata.
        """
        self.turns += 1

        # Strip <think>...</think> reasoning blocks before tool parsing.
        # Qwen3.5 and similar models emit chain-of-thought inside these
        # tags; passing them through can confuse the tool-call parser
        # (e.g. tool names mentioned in reasoning get mis-parsed).
        if self._strip_think:
            clean_action = _THINK_PATTERN.sub("", action).strip()
            if clean_action != action:
                logger.debug(
                    "Stripped <think> blocks from action "
                    "(original=%d chars, cleaned=%d chars)",
                    len(action),
                    len(clean_action),
                )
        else:
            clean_action = action

        # Snapshot tool call count before agent processes this step,
        # so we can compute how many new tool calls this step produced
        # (needed for step-wise trajectory rewards).
        self._prev_tool_call_count = len(getattr(self._agent, "tool_calls_history", []))

        result = self._agent.step(clean_action)
        info = dict(result.info or {})
        rollout_status = normalize_rollout_status(
            info.get("rollout_status", RolloutStatus.OK.value)
        )
        self._last_rollout_status = rollout_status
        self._status_counts[rollout_status] = (
            int(self._status_counts.get(rollout_status, 0)) + 1
        )
        timing = info.get("timing", {})
        if isinstance(timing, dict):
            for key in ("parse_s", "execute_s", "total_s"):
                try:
                    self._timing_totals[key] += float(timing.get(key, 0.0))
                except (TypeError, ValueError):
                    continue

        done = result.done or self.turns >= self.max_turns

        # Context-budget safety net: proactively trigger done=True when
        # the estimated context tokens approach max_input_length.  Without
        # this, SkyRL's agent_loop breaks via its own length check and
        # calls env.close() — which computes terminal Reward for
        # diagnostics only, never feeding it back into per_token_reward.
        if not done and self._max_input_length > 0:
            est_tokens = self._estimate_context_tokens()
            budget_limit = int(self._max_input_length * self._context_budget_threshold)
            if est_tokens >= budget_limit:
                logger.info(
                    "Context budget trigger: est_tokens=%d >= %d (%.0f%% of %d). "
                    "Setting done=True to fire terminal Reward before "
                    "SkyRL length-break.",
                    est_tokens,
                    budget_limit,
                    self._context_budget_threshold * 100,
                    self._max_input_length,
                )
                done = True

        reward = self._compute_reward(done)

        # Log every step's reward for reward-wiring debugging
        logger.info(
            "env.step() returning: challenge=%s turn=%d/%d done=%s "
            "reward=%.6f step_wise=%s rollout_status=%s",
            self._challenge_id,
            self.turns,
            self.max_turns,
            done,
            reward,
            self._step_wise,
            self._last_rollout_status,
        )

        if done:
            # Minimal episode-level logging for diagnostics (avoid huge payloads).
            tool_calls = getattr(self._agent, "tool_calls_history", [])
            tool_outputs = getattr(self._agent, "tool_outputs", [])
            last_calls = [
                tc.get("name", "") if isinstance(tc, dict) else str(tc)
                for tc in tool_calls[-5:]
            ]
            last_outputs = [out[:200] for out in tool_outputs[-3:]]
            logger.info(
                "Episode done: challenge=%s target=%s steps=%s tool_calls=%s unique_tools=%s flag_found=%s "
                "last_tools=%s last_outputs=%s",
                self._challenge_id,
                self._target,
                self.turns,
                len(tool_calls),
                len(
                    set(
                        tc.get("name", "") if isinstance(tc, dict) else str(tc)
                        for tc in tool_calls
                    )
                ),
                getattr(self._agent, "episode_done", False),
                last_calls,
                last_outputs,
            )
            return {
                "observations": [],
                "reward": reward,
                "done": True,
                "metadata": info,
            }

        return {
            "observations": result.observations,
            "reward": reward,
            "done": False,
            "metadata": info,
        }

    def _estimate_context_tokens(self) -> int:
        """Estimate current conversation context size in tokens.

        Uses accumulated tool outputs, assistant text, and per-turn
        formatting overhead to approximate the total token count.
        This is intentionally conservative (overestimates) so we
        trigger done=True before SkyRL's exact tokenizer-based check.
        """
        tool_outputs = getattr(self._agent, "tool_outputs", [])
        all_text = getattr(self._agent, "all_text", "")

        # Baseline: system prompt + tool schemas + user message.
        # With native_tool_schemas, the tokenizer re-injects ~3000 tokens
        # of tool schemas on every re-tokenization.
        initial_tokens = 3500

        # Tool output text (curl HTML responses can be 1000+ chars each).
        output_chars = sum(len(o) for o in tool_outputs)
        output_tokens = output_chars / self._chars_per_token

        # Assistant reasoning/action text.
        text_tokens = len(all_text) / self._chars_per_token

        # ChatML formatting overhead per turn (~15 tokens: role tags,
        # newlines, im_start/im_end tokens).
        formatting_tokens = self.turns * 15

        return int(initial_tokens + output_tokens + text_tokens + formatting_tokens)

    def _compute_reward(self, done: bool) -> float:
        """Compute reward for the current step.

        Reads tool_calls_history, tool_outputs, all_text from the agent
        for reward computation. Falls back gracefully if the agent doesn't
        expose these attributes (custom agents may not).
        """
        # Read agent state (BoxPwnr/Default step agents expose these; custom
        # agents may not).
        tool_calls_history = getattr(self._agent, "tool_calls_history", [])
        tool_outputs = getattr(self._agent, "tool_outputs", [])
        all_text = getattr(self._agent, "all_text", "")
        episode_done = getattr(self._agent, "episode_done", False)

        if not done:
            from trajgym.training.online_rl.step_reward import per_step_reward

            # Compute how many new tool calls were added by this step.
            step_tool_call_count = len(tool_calls_history) - self._prev_tool_call_count
            step_reward = per_step_reward(
                tool_calls_history,
                self.turns,
                step_tool_call_count=max(0, step_tool_call_count),
                step_wise=self._step_wise,
            )

            # In step-wise mode we may never reach terminal done=True in
            # some generator paths. Persist partial trajectories so smoke and
            # diagnostics can still validate tool use/reward flow.
            if self._step_wise:
                self._log_episode_trajectory(
                    reward_total=step_reward,
                    reward_breakdown={"step_reward": float(step_reward)},
                    tool_calls_history=tool_calls_history,
                    tool_outputs=tool_outputs,
                    all_text=all_text,
                    episode_done=episode_done,
                    rollout_status=self._last_rollout_status,
                    update_scoreboard=False,
                )
            return step_reward

        # Terminal: compute full reward
        reward = 0.0
        breakdown = None

        if self._reward_fn is not None:
            completion_msgs = self._build_terminal_completion_msgs(
                tool_calls_history,
                tool_outputs,
                all_text,
            )

            # Pass challenge metadata so reward function can adjust weights
            # (e.g. crypto/rev/forensics skip RECON->ENUM->EXPLOIT progression).
            reward_metadata = [
                {"task_category": self._category or "web", "success": episode_done}
            ]

            logger.info(
                "Terminal reward input: challenge=%s tool_calls=%d tool_outputs=%d "
                "completion_msgs=%d gt_flag=%r episode_done=%s all_text_len=%d",
                self._challenge_id,
                len(tool_calls_history),
                len(tool_outputs),
                len(completion_msgs),
                self._ground_truth_flag[:30] if self._ground_truth_flag else None,
                episode_done,
                len(all_text),
            )

            # Use compute_with_breakdown if available for trajectory logging.
            if self._trajectory_logger and hasattr(
                self._reward_fn, "compute_with_breakdown"
            ):
                results = self._reward_fn.compute_with_breakdown(
                    completions=[completion_msgs],
                    ground_truth_flag=[self._ground_truth_flag],
                    optimal_steps=[self._optimal_steps],
                    metadata=reward_metadata,
                )
                if results:
                    reward, breakdown = results[0]
            else:
                rewards = self._reward_fn(
                    completions=[completion_msgs],
                    ground_truth_flag=[self._ground_truth_flag],
                    optimal_steps=[self._optimal_steps],
                    metadata=reward_metadata,
                )
                reward = rewards[0] if rewards else 0.0

            logger.info(
                "Terminal reward computed: challenge=%s reward=%.4f "
                "breakdown_keys=%s",
                self._challenge_id,
                reward,
                sorted(breakdown.keys()) if breakdown else "none",
            )
        else:
            # Fallback: binary flag reward
            reward = 1.0 if episode_done else 0.0

        # Quality filter: hard-mask known infra/runtime-invalid rollouts so they
        # do not inject misleading gradients into policy updates.
        if self._last_rollout_status in self._hard_mask_statuses:
            logger.info(
                "Hard-masking reward due to rollout_status=%s (challenge=%s step=%s)",
                self._last_rollout_status,
                self._challenge_id,
                self._global_step,
            )
            reward = 0.0
        elif (
            self._positive_only_until_step > 0
            and int(self._global_step) < self._positive_only_until_step
            and float(reward) <= self._positive_only_reward_floor
        ):
            logger.info(
                "Positive-only warmup masking reward=%s at step=%s (challenge=%s)",
                reward,
                self._global_step,
                self._challenge_id,
            )
            reward = 0.0

        # Log trajectory data when episode ends.
        self._log_episode_trajectory(
            reward_total=reward,
            reward_breakdown=breakdown,
            tool_calls_history=tool_calls_history,
            tool_outputs=tool_outputs,
            all_text=all_text,
            episode_done=episode_done,
            rollout_status=self._last_rollout_status,
            update_scoreboard=True,
        )

        return reward

    @staticmethod
    def _build_terminal_completion_msgs(
        tool_calls_history: list,
        tool_outputs: list,
        all_text: str,
    ) -> list[dict[str, Any]]:
        """Build completion messages for terminal Reward scoring.

        Converts agent tool-call history + outputs into the ChatML format
        expected by Reward. Uses safe ``.get()`` accessors throughout
        and skips non-dict entries in the history.
        """
        completion_msgs: list[dict[str, Any]] = []
        for i, tc in enumerate(tool_calls_history):
            if not isinstance(tc, dict):
                continue
            tc_name = tc.get("name", "")
            completion_msgs.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": tc_name,
                                "arguments": tc.get("arguments", "{}"),
                            }
                        }
                    ],
                }
            )
            if i < len(tool_outputs):
                completion_msgs.append(
                    {
                        "role": "tool",
                        "content": tool_outputs[i],
                        "name": tc_name,
                    }
                )
        completion_msgs.append({"role": "assistant", "content": all_text})
        return completion_msgs

    def _log_episode_trajectory(
        self,
        reward_total: float,
        reward_breakdown: dict[str, float] | None,
        tool_calls_history: list,
        tool_outputs: list,
        all_text: str,
        episode_done: bool,
        rollout_status: str,
        update_scoreboard: bool = True,
    ) -> None:
        """Log episode trajectory and update challenge scoreboard."""
        if not self._trajectory_logger:
            return

        try:
            # Build structured tool call list for logging
            logged_tool_calls = []
            for i, tc in enumerate(tool_calls_history):
                if not isinstance(tc, dict):
                    continue
                entry = {
                    "name": tc.get("name", ""),
                    "args": tc.get("arguments", ""),
                }
                if i < len(tool_outputs):
                    # Truncate long outputs to avoid huge JSONL files
                    output = tool_outputs[i]
                    if len(output) > 2000:
                        output = output[:2000] + "... [truncated]"
                    entry["output"] = output
                logged_tool_calls.append(entry)

            # Detect flag_submitted from tool calls
            flag_submitted = None
            for tc in tool_calls_history:
                if not isinstance(tc, dict):
                    continue
                if tc.get("name") in ("flag_found", "submit_flag"):
                    try:
                        args = tc.get("arguments", "")
                        if isinstance(args, str):
                            import json as _json

                            args = _json.loads(args)
                        flag_submitted = (
                            args.get("content", "")
                            if isinstance(args, dict)
                            else str(args)
                        )
                    except Exception:
                        flag_submitted = str(tc.get("arguments", ""))

            self._trajectory_logger.log_generation(
                global_step=self._global_step,
                generation_idx=self._generation_idx,
                challenge_id=self._challenge_id,
                category=self._category,
                difficulty=self._difficulty,
                target=self._target,
                prompt_messages=self._prompt_messages,
                model_output=all_text,
                tool_calls=logged_tool_calls,
                reward_total=reward_total,
                reward_breakdown=reward_breakdown,
                flag_found=episode_done,
                flag_submitted=flag_submitted,
                ground_truth_flag=self._ground_truth_flag,
                response_length=len(all_text),
                num_tool_calls=len(tool_calls_history),
                rollout_status=rollout_status,
                timing=dict(self._timing_totals),
                status_counts=dict(self._status_counts),
                max_turns=self.max_turns,
            )
            self._episode_trajectory_logged = True

            # Update challenge scoreboard
            if update_scoreboard and self._challenge_id:
                self._trajectory_logger.log_challenge_result(
                    challenge_id=self._challenge_id,
                    category=self._category,
                    difficulty=self._difficulty,
                    reward=reward_total,
                    flag_found=episode_done,
                )
        except Exception as exc:
            logger.warning("Trajectory logging failed: %s", exc)

    def close(self):
        """Close the episode and release resources.

        Computes terminal Reward for trajectory logging only when step()
        did NOT already log a terminal trajectory. This prevents duplicate
        trajectory entries that inflate scoreboard counts and confuse
        reward-wiring diagnostics.

        When step() already fired done=True and logged the trajectory
        (``_episode_trajectory_logged=True``), close() skips redundant
        reward computation and logging entirely.
        """
        if (
            self._trajectory_logger
            and self.turns > 0
            and not self._episode_trajectory_logged
        ):
            # step() never reached done=True (e.g. SkyRL agent_loop exited
            # on sequence length). Compute terminal reward for diagnostics.
            tool_calls_history = getattr(self._agent, "tool_calls_history", [])
            tool_outputs = getattr(self._agent, "tool_outputs", [])
            all_text = getattr(self._agent, "all_text", "")
            episode_done = bool(getattr(self._agent, "episode_done", False))
            reward_total = 1.0 if episode_done else 0.0
            reward_breakdown: dict[str, float] | None = None
            if self._reward_fn is not None:
                completion_msgs = self._build_terminal_completion_msgs(
                    tool_calls_history,
                    tool_outputs,
                    all_text,
                )
                reward_metadata = [
                    {
                        "task_category": self._category or "web",
                        "success": episode_done,
                    }
                ]
                if hasattr(self._reward_fn, "compute_with_breakdown"):
                    results = self._reward_fn.compute_with_breakdown(
                        completions=[completion_msgs],
                        ground_truth_flag=[self._ground_truth_flag],
                        optimal_steps=[self._optimal_steps],
                        metadata=reward_metadata,
                    )
                    if results:
                        reward_total, reward_breakdown = results[0]
                else:
                    rewards = self._reward_fn(
                        completions=[completion_msgs],
                        ground_truth_flag=[self._ground_truth_flag],
                        optimal_steps=[self._optimal_steps],
                        metadata=reward_metadata,
                    )
                    reward_total = rewards[0] if rewards else reward_total

            if self._last_rollout_status in self._hard_mask_statuses or (
                self._positive_only_until_step > 0
                and int(self._global_step) < self._positive_only_until_step
                and float(reward_total) <= self._positive_only_reward_floor
            ):
                reward_total = 0.0

            if reward_breakdown is None:
                reward_breakdown = {
                    RolloutStatus.NON_TERMINAL_CLOSE.value: float(reward_total)
                }

            logger.info(
                "close() terminal reward: challenge=%s turns=%d/%d reward=%.4f "
                "episode_done=%s rollout_status=%s",
                self._challenge_id,
                self.turns,
                self.max_turns,
                reward_total,
                episode_done,
                RolloutStatus.NON_TERMINAL_CLOSE.value,
            )

            self._log_episode_trajectory(
                reward_total=float(reward_total),
                reward_breakdown=reward_breakdown,
                tool_calls_history=tool_calls_history,
                tool_outputs=tool_outputs,
                all_text=all_text,
                episode_done=episode_done,
                rollout_status=RolloutStatus.NON_TERMINAL_CLOSE.value,
                update_scoreboard=True,
            )
        if self._agent:
            self._agent.close()
        self._cleanup_ephemeral_workspace()
        logger.debug("TrajGymTextEnv closed (challenge=%s)", self._challenge_id)

    def get_metrics(self) -> dict[str, Any]:
        """Return episode-level metrics."""
        tool_calls_history = getattr(self._agent, "tool_calls_history", [])
        episode_done = getattr(self._agent, "episode_done", False)
        return {
            "total_steps": self.turns,
            "total_tool_calls": len(tool_calls_history),
            "flag_found": episode_done,
            "unique_tools": len(
                set(
                    tc.get("name", "") if isinstance(tc, dict) else str(tc)
                    for tc in tool_calls_history
                )
            ),
        }

    @staticmethod
    def aggregate_metrics(metrics: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate metrics across multiple episodes."""
        if not metrics:
            return {}
        n = len(metrics)
        return {
            "avg_steps": sum(m.get("total_steps", 0) for m in metrics) / n,
            "avg_tool_calls": sum(m.get("total_tool_calls", 0) for m in metrics) / n,
            "flag_found_rate": sum(1 for m in metrics if m.get("flag_found")) / n,
            "avg_unique_tools": sum(m.get("unique_tools", 0) for m in metrics) / n,
            "num_episodes": n,
        }
