"""GEPA prompt optimization stage (Stage 3).

Uses DSPy's GEPA optimizer (Genetic-Pareto reflective prompt evolution)
to evolve the CTF agent's system prompt without weight updates.

Pipeline position: SFT -> Online RL -> **GEPA** -> Deploy

- SFT teaches format and domain knowledge (weight updates)
- Online RL optimizes tool-calling efficiency (weight updates)
- GEPA evolves the system prompt instructions (no weight updates)

How GEPA improves over time:
  1. Seed prompt → evaluate agent on a minibatch of challenges → score each
  2. Reflection LM analyzes execution traces and proposes improved instructions
  3. New candidate prompts are evaluated on the next minibatch
  4. Pareto selection keeps prompts that are best on at least one challenge
  5. Repeat until budget is exhausted → output the best prompt

The reflection LM defaults to the same model as the agent. Both can run
on a local vLLM server — no cloud APIs required. For better mutations,
serve a stronger model for reflection on a separate port.

Outperforms Online RL by ~6% avg with 4-35x fewer rollouts (ICLR 2026 Oral).

Tools execute via ToolExecutor (direct subprocess, no HTTP server needed).

References:
  - Paper: https://arxiv.org/abs/2507.19457
  - GEPA library: https://github.com/gepa-ai/gepa
  - DSPy integration: dspy.teleprompt.gepa.GEPA
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    import dspy

logger = logging.getLogger(__name__)

# Default seed prompt for GEPA prompt evolution.
# GEPA evolves this instruction to maximize task solve performance.
# Override with a domain-specific seed via gepa.seed_prompt in config.
SEED_PROMPT = """\
You are an autonomous agent authorized to solve the given task.

# APPROACH
- Break problems into smaller steps
- Be methodical: test one component at a time
- Prefer simple, debuggable actions
- After discovering useful information, act on it immediately
- Enumerate systematically before attempting solutions
- Use the available tools to gather information and take action
- When you find the answer, submit it immediately

# STRATEGY
- Start with reconnaissance: understand the problem space
- Enumerate: discover endpoints, files, parameters, or entry points
- Act: use what you've discovered to reach the goal
- Verify: confirm your answer before submitting"""

# Domain-specific seed for web CTF challenges.  Encodes only generic
# web pentest methodology (OWASP, standard recon, common vuln classes)
# with NO challenge-specific hints.  Peer-review safe: every element
# is justifiable without having seen any specific challenge solution.
# Use via gepa.seed_prompt_preset: "web_ctf" in config.
SEED_PROMPT_WEB_CTF = """\
You are a cybersecurity expert solving web CTF challenges.
Your goal is to find and submit a hidden flag.

# RECONNAISSANCE
1. FETCH the target page with curl -s and examine the FULL HTML source
2. IDENTIFY all linked resources: JavaScript files, stylesheets, embedded scripts
3. CHECK standard paths: /robots.txt, /.git/, /sitemap.xml, /.env, /admin
4. NOTE the server technology from response headers (Server, X-Powered-By)

# SOURCE ANALYSIS
5. READ every referenced JavaScript file completely — client-side code reveals:
   - API endpoint URLs and route definitions
   - Authentication logic and token handling
   - Hidden functionality and debug endpoints
   - Hardcoded credentials or secrets
6. EXAMINE configuration files, source code, and comments for sensitive data

# ENUMERATION
7. MAP the application's API surface from discovered source code
8. TEST each discovered endpoint with appropriate HTTP methods (GET, POST, PUT)
9. FUZZ parameters and inputs for common vulnerability classes:
   - Server-Side Template Injection (SSTI)
   - SQL Injection / Command Injection
   - Path Traversal / Local File Inclusion
   - Insecure Direct Object References
   - Authentication and authorization bypasses

# EXPLOITATION
10. CHAIN discoveries together — data from one endpoint often unlocks another
11. USE curl for HTTP requests; pipe to jq for JSON, grep for text filtering
12. WRITE Python scripts for complex multi-step exploits

# FLAG SUBMISSION
- Submit the flag the moment you find it using the flag_found tool
- COPY the flag EXACTLY as it appears in tool output — character for character
- Flags use intentional leetspeak (3=e, 0=o, 5=s, 4=a, 1=i, 7=t) — do NOT
  "correct" or normalize any characters
- If flag_found is rejected, re-read the original tool output containing the
  flag and copy it again more carefully

# RULES
- Act on every discovery IMMEDIATELY — do not plan without executing
- Read source files in full; do not skip or truncate them
- Increase tool output limits if responses appear truncated"""

# Registry of named seed prompt presets.
SEED_PROMPT_PRESETS: dict[str, str] = {
    "default": SEED_PROMPT,
    "web_ctf": SEED_PROMPT_WEB_CTF,
}


def _strip_react_boilerplate(instruction: str) -> str:
    """Strip DSPy ReAct agent framing, keeping only the CTF instructions."""
    if not instruction:
        return instruction
    marker = "You are an Agent"
    idx = instruction.find(marker)
    return instruction[:idx].strip() if idx > 0 else instruction.strip()


def _extract_first_url(text: str) -> str | None:
    """Extract the first HTTP(S) URL and normalize to scheme://host[:port]."""
    if not text:
        return None
    match = re.search(r"https?://[^\s)]+", text)
    if not match:
        return None
    raw = match.group(0).rstrip(".,;:!?")
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw
    return f"{parsed.scheme}://{parsed.netloc}"


# ---------------------------------------------------------------------------
# GEPA metric (wraps reward function for trajectory scoring + feedback)
# ---------------------------------------------------------------------------


def _build_metric(reward_fn):
    """Wrap a reward function as a GEPA feedback metric.

    Returns a callable matching the ``GEPAFeedbackMetric`` protocol::

        (gold, pred, trace, pred_name, pred_trace) -> ScoreWithFeedback
    """
    from dspy.teleprompt.gepa.gepa_utils import ScoreWithFeedback

    def ctf_metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
        target = gold.get("target", "")
        gt_flag = gold.get("ground_truth_flag", "")
        if target:
            from trajgym.training.tool_wrappers import init_env

            init_env(target=target, ground_truth=gt_flag)

        # Extract tool calls and observations from pred.trajectory.
        # Present in both 2-arg (Evaluate) and 5-arg (GEPA reflection) calls.
        trajectory = getattr(pred, "trajectory", {}) or {}
        text_parts = [getattr(pred, "answer", "") or ""]
        tc_entries = []
        for key in sorted(trajectory):
            if key.startswith("observation_"):
                text_parts.append(str(trajectory[key]))
            elif key.startswith("tool_name_"):
                idx = key[len("tool_name_") :]
                name = trajectory[key]
                if name and name != "finish":
                    args = trajectory.get(f"tool_args_{idx}", {})
                    args_str = (
                        json.dumps(args)
                        if isinstance(args, dict)
                        else str(args or "{}")
                    )
                    tc_entries.append(
                        {"function": {"name": name, "arguments": args_str}}
                    )

        completion = [{"content": "\n".join(text_parts), "tool_calls": tc_entries}]
        scores = reward_fn(
            completions=completion,
            ground_truth_flag=[gold.get("ground_truth_flag")],
            optimal_steps=[gold.get("optimal_steps")],
        )
        score = scores[0] if scores else 0.0

        # Concise feedback for GEPA reflection LM.
        names = [tc["function"]["name"] for tc in tc_entries]
        feedback = f"Score: {score:.2f}. {len(names)} tool calls: {', '.join(names[:8]) or 'none'}."
        if score >= 0.8:
            feedback += " Flag captured."
        elif len(names) == 0:
            feedback += " No tools used."
        return ScoreWithFeedback(score=score, feedback=feedback)

    return ctf_metric


# ---------------------------------------------------------------------------
# Challenge data loader
# ---------------------------------------------------------------------------


def _extract_target_from_messages(messages: list[dict[str, str]]) -> str | None:
    """Extract target URL from user messages."""
    for msg in messages:
        if msg.get("role") == "user":
            target = _extract_first_url(msg.get("content", ""))
            if target:
                return target
    return None


def _load_challenges(
    data_path: str,
    max_samples: int | None = None,
    registry=None,
) -> list:
    """Load challenges from Online RL JSONL as DSPy Examples.

    Each example contains:
    - ``challenge``: The CTF challenge description (from user message)
    - ``ground_truth_flag``: The expected flag (for scoring)
    - ``optimal_steps``: Minimum steps to solve (for efficiency scoring)
    - ``target``: Target URL for the challenge (extracted or from registry)
    - ``challenge_id``: Canonical challenge ID (if resolvable)

    Args:
        data_path: Path to Online RL JSONL file.
        max_samples: Maximum examples to load.
        registry: Optional ChallengeRegistry for target URL resolution.
    """
    import dspy

    examples = []
    with open(data_path) as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            messages = row.get("messages", [])
            metadata = row.get("metadata", {})

            # Extract challenge description from the user message
            challenge_text = ""
            for msg in messages:
                if msg.get("role") == "user":
                    challenge_text = msg.get("content", "")
                    break

            if not challenge_text:
                continue

            # Extract target URL from user messages (same as online_rl/runtime.py)
            target = _extract_target_from_messages(messages)
            if not target:
                target = metadata.get("target")

            # Resolve challenge ID and target from registry
            challenge_id = metadata.get("challenge_id") or metadata.get("challenge")
            if registry and challenge_id:
                resolved = registry.resolve_id(str(challenge_id))
                if resolved is not None:
                    challenge_id = resolved
                    if not target:
                        with contextlib.suppress(KeyError):
                            target = registry.get_target_url(resolved)

            ex = dspy.Example(
                challenge=challenge_text,
                ground_truth_flag=row.get("ground_truth_flag", ""),
                optimal_steps=row.get("optimal_steps"),
                target=target or "",
                challenge_id=challenge_id or "",
            ).with_inputs("challenge")

            examples.append(ex)

            if max_samples and len(examples) >= max_samples:
                break

    return examples


# ---------------------------------------------------------------------------
# Agent -> DSPy Module adapter (for --agent flag)
# ---------------------------------------------------------------------------


class CTFAgentDSPyAdapter:
    """Wrap a BYO Agent (e.g. BoxPwnrAgent) as a DSPy-compatible module.

    GEPA evolves the system prompt; this adapter forwards the evolved prompt
    to the agent's ``solve()`` method via the ``custom_instructions`` kwarg.

    BoxPwnr (and other BYO agents) treat ``challenge`` as a target identifier,
    not a prompt -- so we must NOT prepend the evolved prompt to the challenge
    text.  Instead, we pass it separately as ``custom_instructions``.

    DSPy GEPA calls ``forward(challenge=...)`` on this adapter.  The adapter
    delegates to ``agent.solve(challenge, target, ..., custom_instructions=...)``.

    Implements the minimal DSPy module surface:
    - ``forward()`` — called by GEPA evaluator
    - ``named_predictors()`` — GEPA reads/writes evolved instructions here
    - ``deepcopy()`` / ``reset_copy()`` / ``__deepcopy__()`` — GEPA clones
    - ``save()`` / ``load()`` — GEPA persists candidates
    """

    def __init__(
        self,
        agent,
        seed_prompt: str = "",
        challenge_flags: dict[str, str] | None = None,
        challenge_ids: dict[str, str] | None = None,
        solve_kwargs: dict[str, Any] | None = None,
    ):
        self._agent = agent
        self._seed_prompt = seed_prompt
        self._challenge_flags = challenge_flags or {}
        # Mapping from challenge text (first 128 chars) to challenge_id.
        # Used by forward() to resolve the challenge identifier that BYO
        # agents (e.g. BoxPwnr) need as the ``challenge`` parameter.
        self._challenge_ids = challenge_ids or {}
        # Extra kwargs forwarded to agent.solve() (e.g. timeout, max_steps).
        self._solve_kwargs = solve_kwargs or {}
        # Mutable instruction that GEPA evolves via named_predictors().
        self._evolved_prompt = seed_prompt

    def _resolve_challenge_id(self, challenge_text: str) -> str:
        """Resolve challenge identifier from challenge text.

        BYO agents (e.g. BoxPwnr) expect a challenge name like
        ``"[Very Easy] Flag Command"`` not the full prompt text.
        DSPy only passes input fields to forward(), so challenge_id
        (a non-input field) must be resolved from a pre-built mapping.
        """
        key = challenge_text[:128]
        if key in self._challenge_ids:
            return self._challenge_ids[key]
        # Fallback: return the original text (non-BoxPwnr agents may accept it)
        return challenge_text

    def __call__(self, challenge: str = "", **kwargs):
        """DSPy evaluator calls program(**inputs) — delegate to forward()."""
        return self.forward(challenge=challenge, **kwargs)

    def forward(self, challenge: str = "", **kwargs):
        """Run the BYO agent on a challenge, forwarding evolved prompt."""
        import dspy

        target = kwargs.get("target", "")
        if not target:
            target = _extract_first_url(challenge) or ""

        gt_flag = kwargs.get("ground_truth_flag", "")
        if not gt_flag:
            gt_flag = self._resolve_ground_truth(challenge, target)

        evolved_prompt = self._evolved_prompt or ""

        # Resolve the challenge identifier for BYO agents that need a
        # short name (e.g. BoxPwnr CybenchPlatform), not the full prompt.
        challenge_id = kwargs.get("challenge_id") or self._resolve_challenge_id(challenge)

        result = self._agent.solve(
            challenge=challenge_id,
            target=target,
            ground_truth_flag=gt_flag,
            custom_instructions=evolved_prompt,
            **self._solve_kwargs,
        )

        # Build a DSPy Prediction with trajectory info for the metric.
        trajectory = {}
        for i, msg in enumerate(result.messages):
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "assistant":
                # Extract tool calls if present
                tool_calls = msg.get("tool_calls", [])
                for j, tc in enumerate(tool_calls):
                    fn = tc.get("function", {})
                    trajectory[f"tool_name_{i}_{j}"] = fn.get("name", "")
                    trajectory[f"tool_args_{i}_{j}"] = fn.get("arguments", {})
            elif role in ("tool", "user"):
                trajectory[f"observation_{i}"] = content

        return dspy.Prediction(
            answer=result.flag or "",
            trajectory=trajectory,
        )

    def _resolve_ground_truth(self, challenge: str, target: str) -> str:
        """Resolve ground-truth flag from target URL or challenge text."""
        if target and target in self._challenge_flags:
            return self._challenge_flags[target]
        for key, flag in self._challenge_flags.items():
            if key.startswith("http://") or key.startswith("https://"):
                continue
            if key in challenge:
                return flag
        flags = list(set(self._challenge_flags.values()))
        if len(flags) == 1:
            return flags[0]
        return ""

    # -- DSPy module interface for GEPA ------------------------------------

    def named_predictors(self):
        """Yield a single synthetic predictor so GEPA can read/write instructions."""
        return [("agent", self)]

    @property
    def signature(self):
        """Synthetic signature exposing the evolved instructions to GEPA."""
        return _MutableSignature(self._evolved_prompt)

    @signature.setter
    def signature(self, value):
        if hasattr(value, "instructions"):
            self._evolved_prompt = value.instructions

    def deepcopy(self):
        import copy

        clone = CTFAgentDSPyAdapter(
            agent=copy.deepcopy(self._agent),
            seed_prompt=self._seed_prompt,
            challenge_flags=self._challenge_flags.copy(),
            challenge_ids=self._challenge_ids.copy(),
            solve_kwargs=self._solve_kwargs.copy(),
        )
        clone._evolved_prompt = self._evolved_prompt
        return clone

    def reset_copy(self):
        import copy

        clone = CTFAgentDSPyAdapter(
            agent=copy.deepcopy(self._agent),
            seed_prompt=self._seed_prompt,
            challenge_flags=self._challenge_flags.copy(),
            challenge_ids=self._challenge_ids.copy(),
            solve_kwargs=self._solve_kwargs.copy(),
        )
        clone._evolved_prompt = self._seed_prompt  # reset to seed
        return clone

    def __deepcopy__(self, memo):
        import copy

        clone = CTFAgentDSPyAdapter(
            agent=copy.deepcopy(self._agent, memo),
            seed_prompt=self._seed_prompt,
            challenge_flags=self._challenge_flags.copy(),
            challenge_ids=self._challenge_ids.copy(),
            solve_kwargs=self._solve_kwargs.copy(),
        )
        clone._evolved_prompt = self._evolved_prompt
        return clone

    def save(self, path: str):
        """Persist evolved prompt to disk."""
        Path(path).write_text(json.dumps({"evolved_prompt": self._evolved_prompt}))

    def load(self, path: str):
        """Restore evolved prompt from disk."""
        data = json.loads(Path(path).read_text())
        self._evolved_prompt = data.get("evolved_prompt", self._seed_prompt)


class _MutableSignature:
    """Minimal stand-in for dspy.Signature so GEPA can read/write instructions."""

    def __init__(self, instructions: str = ""):
        self.instructions = instructions

    def with_instructions(self, instructions: str):
        return _MutableSignature(instructions)


# ---------------------------------------------------------------------------
# Environment-aware ReAct wrapper
# ---------------------------------------------------------------------------


class _EnvAwareReAct:
    """Wraps a DSPy ReAct module to initialize the ToolExecutor before each episode.

    Intercepts ``forward()`` to call ``mark_step_begin(ground_truth=...)``
    with the correct flag before each ReAct episode.  ``__getattr__``
    delegates all other attribute access (``named_predictors``, ``save``,
    ``load``, etc.) to the inner module.
    """

    def __init__(self, inner: dspy.ReAct, challenge_flags: dict[str, str]):
        self._inner = inner
        self._challenge_flags = challenge_flags

    def _resolve_ground_truth(self, challenge: str) -> str:
        """Resolve ground-truth flag from target URL or challenge text."""
        target = _extract_first_url(challenge)
        if target and target in self._challenge_flags:
            return self._challenge_flags[target]

        # Fallback: check if any known challenge prefix appears as a
        # substring in the (possibly augmented) challenge text.
        # is still present later in the string.
        for key, flag in self._challenge_flags.items():
            # Skip URL keys (already checked above)
            if key.startswith("http://") or key.startswith("https://"):
                continue
            if key in challenge:
                return flag

        # Last resort: if we only have one challenge, use its flag
        flags = list(set(self._challenge_flags.values()))
        if len(flags) == 1:
            return flags[0]

        return ""

    def _init_episode(self, challenge: str) -> None:
        """Initialize ToolExecutor with correct ground_truth before an episode."""
        from trajgym.training.tool_wrappers import mark_step_begin

        gt_flag = self._resolve_ground_truth(challenge)
        if gt_flag:
            mark_step_begin(ground_truth=gt_flag)
            logger.debug(
                "Episode initialized: target extracted, ground_truth=%s...%s",
                gt_flag[:6],
                gt_flag[-4:],
            )
        else:
            mark_step_begin()
            logger.warning(
                "No ground_truth found for challenge (first 80 chars: %s)",
                challenge[:80],
            )

    def __call__(self, challenge: str = "", **kwargs):
        """Route through forward() so bootstrap_trace's forward-patching works.

        DSPy's bootstrap_trace_data patches program.forward to capture traces.
        If __call__ bypasses forward(), the patched wrapper never fires and
        GEPA gets "too many values to unpack" during trace collection.
        """
        return self.forward(challenge=challenge, **kwargs)

    def forward(self, challenge: str = "", **kwargs):
        """Must be defined directly — bootstrap_trace_data patches forward()."""
        self._init_episode(challenge)
        return self._inner.forward(challenge=challenge, **kwargs)

    def deepcopy(self):
        """DSPy BaseModule.deepcopy() — GEPA calls this, not copy.deepcopy().

        Must return an _EnvAwareReAct wrapping a deep copy of the inner
        ReAct, otherwise GEPA's build_program loses the wrapper and
        mark_step_begin() won't be called during evaluation episodes.
        """
        return _EnvAwareReAct(
            self._inner.deepcopy(),
            self._challenge_flags.copy(),
        )

    def reset_copy(self):
        """DSPy BaseModule.reset_copy() — returns a wrapper with a reset inner copy."""
        return _EnvAwareReAct(
            self._inner.reset_copy(),
            self._challenge_flags.copy(),
        )

    def __deepcopy__(self, memo):
        import copy

        return _EnvAwareReAct(
            copy.deepcopy(self._inner, memo),
            self._challenge_flags.copy(),
        )

    def __getattr__(self, name):
        """Delegate any other attribute access to the inner ReAct module."""
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_gepa(
    model_id: str,
    data_path: str,
    output_dir: str,
    config: dict[str, Any],
    reflection_model: str | None = None,
    budget: str = "medium",
    val_data_path: str | None = None,
    max_samples: int | None = None,
    challenge_registry: str | None = None,
    agent_class: str | None = None,
) -> str:
    """Run GEPA prompt optimization.

    Evolves the agent's system prompt by reflecting on execution traces.
    Uses DSPy ReAct with ToolExecutor tools and Reward for scoring.

    Args:
        model_id: LLM model identifier for ``dspy.LM``.
        data_path: Path to JSONL data (challenges with flags).
        output_dir: Directory for optimized prompts and logs.
        config: Merged config dict (may contain ``gepa:`` section).
        reflection_model: LLM for GEPA reflection (defaults to model_id).
        budget: GEPA budget preset (``light`` / ``medium`` / ``heavy``).
        val_data_path: Optional separate validation data path.
        max_samples: Maximum number of training examples to load.
        challenge_registry: Path to challenge registry YAML.
        agent_class: Dotted path to a BYO Agent class (e.g.
            ``trajgym.integrations.boxpwnr_adapter.BoxPwnrAgent``).
            The class must implement ``solve(challenge, target, ground_truth_flag,
            custom_instructions=...)`` per the Agent protocol. GEPA evolves the
            system prompt and forwards it via ``custom_instructions``.

    Returns:
        Path to saved optimized prompt file.
    """
    import dspy
    from dspy.teleprompt.gepa import GEPA

    from trajgym.rewards import Reward

    gepa_cfg = config.get("gepa", {})
    budget = budget or gepa_cfg.get("budget", "medium")

    logger.info("=" * 60)
    logger.info("GEPA PROMPT OPTIMIZATION (Stage 3)")
    logger.info("  Model:      %s", model_id)
    logger.info("  Reflection: %s", reflection_model or model_id)
    logger.info("  Data:       %s", data_path)
    logger.info("  Budget:     %s", budget)
    logger.info("  Output:     %s", output_dir)
    if challenge_registry:
        logger.info("  Registry:   %s", challenge_registry)
    if agent_class:
        logger.info("  Agent:      %s", agent_class)
    logger.info("=" * 60)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Configure DSPy LM ------------------------------------------------
    agent_max_tokens = gepa_cfg.get("max_tokens", 1024)
    agent_lm_kwargs: dict[str, Any] = {
        "model": model_id,
        "max_tokens": agent_max_tokens,
    }
    agent_temp = gepa_cfg.get("temperature", 0.7)
    if agent_temp is not None:
        agent_lm_kwargs["temperature"] = agent_temp

    # Thinking control: models like Qwen3.5-9B generate verbose <think>
    # blocks that consume the token budget, leaving too few tokens for
    # actual tool calls.  Two options (mutually exclusive):
    #
    #   disable_thinking: true
    #     Passes enable_thinking=false via chat_template_kwargs to vLLM.
    #     Completely suppresses <think> blocks.  DSPy ReAct already
    #     structures reasoning via next_thought, so native thinking is
    #     redundant.
    #
    #   thinking_token_budget: 1024
    #     Caps thinking tokens per completion.  Model still reasons but
    #     within a hard limit, preserving budget for tool calls.
    #     Preferred over disable_thinking when some reasoning helps.
    #
    thinking_budget = gepa_cfg.get("thinking_token_budget")
    if gepa_cfg.get("disable_thinking", False):
        agent_lm_kwargs.setdefault("extra_body", {})
        agent_lm_kwargs["extra_body"]["chat_template_kwargs"] = {
            "enable_thinking": False,
        }
        logger.info("Thinking disabled via chat_template_kwargs")
    elif thinking_budget is not None:
        agent_lm_kwargs.setdefault("extra_body", {})
        agent_lm_kwargs["extra_body"]["thinking_token_budget"] = int(thinking_budget)
        logger.info("Thinking token budget: %d", thinking_budget)

    # Pass through arbitrary model kwargs (e.g. top_k, top_p, min_p,
    # presence_penalty) for model-specific tuning.
    extra_model_kwargs = gepa_cfg.get("model_kwargs", {})
    if extra_model_kwargs:
        agent_lm_kwargs.update(extra_model_kwargs)
        logger.info("Extra model kwargs: %s", extra_model_kwargs)

    lm = dspy.LM(**agent_lm_kwargs)
    dspy.configure(lm=lm)

    # Reflection LM — defaults to same model (no cloud APIs needed).
    # Override via --reflection-model CLI flag or gepa.reflection_model in config.
    ref_model = reflection_model or gepa_cfg.get("reflection_model") or model_id
    ref_max_tokens = gepa_cfg.get("reflection_max_tokens", 32000)
    ref_lm_kwargs: dict[str, Any] = {"model": ref_model, "max_tokens": ref_max_tokens}
    ref_temp = gepa_cfg.get("reflection_temperature", 1.0)
    if ref_temp is not None:
        ref_lm_kwargs["temperature"] = ref_temp
    reflection_lm = dspy.LM(**ref_lm_kwargs)

    # --- Load challenge registry (if provided) ----------------------------
    registry = None
    if challenge_registry:
        from trajgym.challenges.registry import ChallengeRegistry

        registry = ChallengeRegistry(challenge_registry)
        logger.info("Challenge registry loaded: %d challenges", len(registry))

    # --- Load challenge data -----------------------------------------------
    max_n = max_samples or gepa_cfg.get("max_samples")
    trainset = _load_challenges(data_path, max_samples=max_n, registry=registry)
    valset = None
    if val_data_path and Path(val_data_path).exists():
        valset = _load_challenges(val_data_path, registry=registry)

    logger.info("Loaded %d training examples", len(trainset))
    targets_found = sum(1 for ex in trainset if ex.get("target"))
    logger.info("  %d/%d have target URLs", targets_found, len(trainset))
    if valset:
        logger.info("Loaded %d validation examples", len(valset))

    # --- Build CTF agent ---------------------------------------------------
    # Seed prompt resolution order:
    #   1. gepa.seed_prompt — full custom prompt text
    #   2. gepa.seed_prompt_preset — named preset (e.g. "web_ctf")
    #   3. SEED_PROMPT — default generic prompt
    seed = gepa_cfg.get("seed_prompt")
    if not seed:
        preset_name = gepa_cfg.get("seed_prompt_preset", "default")
        seed = SEED_PROMPT_PRESETS.get(preset_name)
        if seed is None:
            logger.warning(
                "Unknown seed_prompt_preset %r, using default. " "Available: %s",
                preset_name,
                ", ".join(SEED_PROMPT_PRESETS),
            )
            seed = SEED_PROMPT
        elif preset_name != "default":
            logger.info("Using seed prompt preset: %s", preset_name)

    # Build target->ground_truth and challenge_text->challenge_id lookups.
    challenge_flags = {}
    challenge_ids = {}
    for ex in trainset:
        target = ex.get("target", "")
        gt = ex.get("ground_truth_flag", "")
        challenge_text = ex.get("challenge", "")
        challenge_id = ex.get("challenge_id", "")
        if gt:
            if target:
                challenge_flags[target] = gt
            if challenge_text:
                challenge_flags[challenge_text[:128]] = gt
        if challenge_id and challenge_text:
            challenge_ids[challenge_text[:128]] = challenge_id

    if agent_class:
        # --- BYO Agent path (e.g. BoxPwnr) --------------------------------
        # Load the agent class dynamically and wrap it in CTFAgentDSPyAdapter.
        # GEPA evolves the seed prompt and forwards it as custom_instructions
        # to the agent's solve() method on every evaluation episode.
        import importlib

        parts = agent_class.rsplit(".", 1)
        if len(parts) == 2:
            mod = importlib.import_module(parts[0])
            AgentCls = getattr(mod, parts[1])
        else:
            raise ValueError(
                f"agent_class must be a dotted path (e.g. 'module.ClassName'), "
                f"got: {agent_class!r}"
            )

        agent_kwargs = gepa_cfg.get("agent_kwargs", {})
        ctf_agent = AgentCls(**agent_kwargs)
        logger.info(
            "BYO agent loaded: %s (kwargs keys: %s)",
            agent_class,
            list(agent_kwargs.keys()) if agent_kwargs else "none",
        )

        solve_kwargs = gepa_cfg.get("agent_solve_kwargs", {})
        agent = CTFAgentDSPyAdapter(
            agent=ctf_agent,
            seed_prompt=seed,
            challenge_flags=challenge_flags,
            challenge_ids=challenge_ids,
            solve_kwargs=solve_kwargs,
        )
    else:
        # --- Default DSPy ReAct agent with ToolExecutor tools --------------
        from trajgym.training.tool_wrappers import get_all_tools, init_env

        stdout_limit = gepa_cfg.get("max_tool_response_chars", 16000)
        init_env(stdout_limit=stdout_limit)
        tools = get_all_tools()
        logger.info(
            "Tools initialized (%d tools, stdout_limit=%d)", len(tools), stdout_limit
        )

        class AgentSignature(dspy.Signature):
            """Placeholder instructions (replaced by seed prompt below)."""

            challenge: str = dspy.InputField(
                desc="CTF challenge description and target information",
            )
            answer: str = dspy.OutputField(
                desc="The captured flag or final answer",
            )

        inner_react = dspy.ReAct(
            signature=AgentSignature.with_instructions(seed),
            tools=tools,
            max_iters=gepa_cfg.get("max_iters", 15),
        )

        agent = _EnvAwareReAct(inner_react, challenge_flags)

    # --- Build metric ------------------------------------------------------
    reward_fn = Reward(
        flag_weight=0.85,
        efficiency_weight=0.10,
        format_weight=0.05,
        progression_weight=0.0,
        exploration_weight=0.0,
        uniqueness_weight=0.0,
        recovery_weight=0.0,
        cognitive_weight=0.0,
        hallucination_penalty=0.0,
        noise_range=0.0,
    )
    metric = _build_metric(reward_fn)

    # --- Run GEPA ----------------------------------------------------------
    # ToolExecutor is a module-level singleton — concurrent threads race on
    # ground_truth and episode state.  Force single-threaded.
    num_threads = 1

    # Budget: prefer explicit max_metric_calls, fall back to auto preset.
    # Small-dataset heuristic: 10 calls per challenge avoids auto="light"
    # producing ~736 rollouts for 1 challenge.
    max_metric_calls = gepa_cfg.get("max_metric_calls")
    if max_metric_calls is None and len(trainset) <= 3:
        max_metric_calls = max(10 * len(trainset), 10)

    budget_kwargs = {}
    if max_metric_calls is not None:
        budget_kwargs["max_metric_calls"] = int(max_metric_calls)
    else:
        budget_kwargs["auto"] = budget

    log_dir = out_dir / "gepa_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    optimizer = GEPA(
        metric=metric,
        **budget_kwargs,
        reflection_lm=reflection_lm,
        reflection_minibatch_size=gepa_cfg.get("reflection_minibatch_size", 3),
        log_dir=str(log_dir),
        track_stats=True,
        seed=gepa_cfg.get("seed", 42),
        num_threads=num_threads,
    )

    optimized = optimizer.compile(
        student=agent,
        trainset=trainset,
        valset=valset,
    )

    # --- Save optimized prompt ---------------------------------------------
    prompt_path = out_dir / "optimized_prompt.txt"
    raw_instruction = ""
    for _name, pred in optimized.named_predictors():
        raw_instruction = pred.signature.instructions
        break

    # Save raw instruction (with ReAct framing) for debugging
    raw_path = out_dir / "optimized_prompt_raw.txt"
    raw_path.write_text(raw_instruction)
    logger.info("Raw instruction (with ReAct framing) saved to %s", raw_path)

    # Strip DSPy ReAct boilerplate — only keep the evolved CTF instructions.
    optimized_instruction = _strip_react_boilerplate(raw_instruction)
    prompt_path.write_text(optimized_instruction)
    logger.info("Optimized prompt saved to %s", prompt_path)

    # Save detailed results
    if hasattr(optimized, "detailed_results") and optimized.detailed_results:
        try:
            results = optimized.detailed_results.to_dict()
            results_path = out_dir / "gepa_results.json"
            results_path.write_text(json.dumps(results, indent=2, default=str))
            logger.info("Detailed results saved to %s", results_path)
            logger.info(
                "Best score: %.4f (candidate %d of %d)",
                optimized.detailed_results.val_aggregate_scores[
                    optimized.detailed_results.best_idx
                ],
                optimized.detailed_results.best_idx,
                len(optimized.detailed_results.candidates),
            )
        except (AttributeError, TypeError, KeyError) as e:
            # GEPA's to_dict() may call .items() on candidate programs
            # which fails for wrapper objects. Save what we can.
            logger.warning("Could not serialize detailed_results: %s", e)
            try:
                fallback = {
                    "best_idx": optimized.detailed_results.best_idx,
                    "val_scores": optimized.detailed_results.val_aggregate_scores,
                }
                results_path = out_dir / "gepa_results.json"
                results_path.write_text(json.dumps(fallback, indent=2, default=str))
                logger.info("Partial results saved to %s", results_path)
            except Exception:
                pass

    # Save the optimized DSPy module for reuse
    try:
        optimized.save(str(out_dir / "optimized_agent.json"))
        logger.info(
            "Optimized DSPy module saved to %s", out_dir / "optimized_agent.json"
        )
    except Exception as e:
        logger.warning("Could not save DSPy module: %s", e)

    return str(prompt_path)
