"""Individual reward signal scoring functions.

Each function computes one of the 8 reward signals used in CTF trajectory
scoring. These are pure functions (no class state) — parameters that were
previously accessed via ``self`` are now explicit arguments.
"""

import json
import math
import re
from typing import Any

from trajgym.rewards.constants import (
    _ENUM_BINARIES,
    _EXPLOIT_BINARIES,
    _FLAG_PLACEHOLDERS,
    _KNOWN_TOOL_NAMES,
    _RECON_BINARIES,
    _SHELL_WRAPPERS,
    _TOOL_NAME_PHASES,
)


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------


def is_real_flag(flag: str) -> bool:
    """Return True if the flag is a real value, not a placeholder or template."""
    if not flag:
        return False
    if flag in _FLAG_PLACEHOLDERS:
        return False
    flag_lower = flag.lower()
    for poison in (
        "content_of_flag_here",
        "dummy_flag",
        "fake_flag",
        "this_is_fake",
        "placeholder",
    ):
        if poison in flag_lower:
            return False
    return True


def is_known_tool(name: str) -> bool:
    """Check if a tool name is a recognized CTF instrument."""
    return name in _KNOWN_TOOL_NAMES


def extract_command(tc: dict[str, str]) -> str:
    """Extract the command string from a tool call's arguments.

    Handles common BoxPwnr argument schemas:
      - {"command": "..."} (shell_command, exec_command)
      - {"code": "..."} (python_code)
      - {"content": "..."} (flag_found)
      - {"query": "..."} (web_search, grep)
      - {"path": "..."} (read_file)
      - Plain string arguments
    """
    args_str = tc.get("arguments", "")
    if not args_str:
        return ""

    # Try JSON first
    try:
        args = json.loads(args_str) if isinstance(args_str, str) else args_str
        if isinstance(args, dict):
            # Try common argument keys in priority order
            for key in (
                "command",
                "code",
                "content",
                "query",
                "path",
                "pattern",
                "search_query",
                "stdin",
            ):
                val = args.get(key)
                if val and isinstance(val, str):
                    return val.strip()
            # Fallback: use first non-empty string value
            for val in args.values():
                if isinstance(val, str) and val.strip():
                    return val.strip()
        elif isinstance(args, str):
            return args.strip()
    except (json.JSONDecodeError, TypeError):
        # Not JSON -- use raw string
        if isinstance(args_str, str):
            return args_str.strip()

    return ""


def action_fingerprint(tc: dict[str, str]) -> str:
    """Create a fingerprint for a tool call action.

    For shell wrappers, includes the binary name so that
    shell_command("nmap") and shell_command("curl") are distinct.
    For other tools, uses the tool name directly.
    No regex -- uses split + rsplit for binary extraction.
    """
    name = tc.get("name", "")
    if name in _SHELL_WRAPPERS:
        cmd = extract_command(tc)
        if cmd:
            binary = cmd.split()[0].rsplit("/", 1)[-1].lower()
            return f"{name}:{binary}"
    return name


def classify_phase(tc: dict[str, str]) -> str | None:
    """Classify a tool call into a CTF phase. Set-based, no regex."""
    name = tc.get("name", "")

    # Direct tool name classification
    if name in _TOOL_NAME_PHASES:
        return _TOOL_NAME_PHASES[name]

    # For shell wrappers, classify by first token (binary name)
    if name in _SHELL_WRAPPERS:
        cmd = extract_command(tc)
        if not cmd:
            return None
        first_token = cmd.split()[0].rsplit("/", 1)[-1].lower()
        if first_token in _RECON_BINARIES:
            return "recon"
        if first_token in _ENUM_BINARIES:
            return "enum"
        if first_token in _EXPLOIT_BINARIES:
            return "exploit"

    return None


# ------------------------------------------------------------------
# Signal scoring functions
# ------------------------------------------------------------------


def flag_score(
    text: str,
    ground_truth: str | None,
    *,
    flag_verified_marker: str = "Correct! Flag verified",
    flag_rejected_marker: str = "Incorrect submission",
    metadata_success: bool | None = None,
    tool_calls: list[dict[str, str]] | None = None,
) -> float:
    """Score flag capture (online mode).

    Priority order:
      1. Environment verification signal in tool response text
         ("Correct! Flag verified" -> 1.0, "Incorrect submission" -> 0.0)
      2. Exact match against ground_truth_flag -> 1.0
         (only if flag_found was called — prevents false rewards from
         flags appearing incidentally in tool output)
      3. Pattern match: FLAG{<alphanumeric>} -> 0.1
      4. No flag -> 0.0
    """
    if flag_verified_marker in text:
        return 1.0
    if flag_rejected_marker in text:
        return 0.0

    has_flag_submission = "flag_found" in text or any(
        tc.get("name") in ("flag_found", "submit_flag")
        for tc in (tool_calls or [])
    )
    if (
        ground_truth
        and is_real_flag(ground_truth)
        and ground_truth in text
        and has_flag_submission
    ):
        return 1.0

    if re.search(r"FLAG\{[a-zA-Z0-9_-]+\}", text):
        return 0.1

    return 0.0


def efficiency_score(
    actual_steps: int,
    optimal_steps: int | None,
    flag_found: bool = False,
    tool_calls: list[dict[str, str]] | None = None,
) -> float:
    """Principle of least action: step_ratio × action_novelty × temporal_decay.

    Three physics-inspired components:
      1. Step ratio (classical efficiency): min(optimal/actual, 1.0)
      2. Action novelty (information redundancy): unique_fingerprints / total
      3. Temporal decay (time cost): exp(-λ × excess_steps / optimal)

    Returns 0.0 for zero steps, 0.3 (weak prior) without metadata.
    Non-flag completions capped at 0.3. Fewer than 3 steps = 0.0.
    """
    if actual_steps == 0:
        return 0.0
    if actual_steps < 3:
        return 0.0
    opt = optimal_steps or 10

    step_ratio = min(opt / actual_steps, 1.0)

    if tool_calls and len(tool_calls) > 0:
        fingerprints = [action_fingerprint(tc) for tc in tool_calls]
        novelty = len(set(fingerprints)) / len(fingerprints)
    else:
        novelty = 1.0

    excess = max(0, actual_steps - opt) / max(opt, 1)
    time_decay = math.exp(-0.3 * excess)

    score = step_ratio * novelty * time_decay

    if not flag_found:
        return min(score, 0.3)
    return score


def format_score(tool_calls: list[dict[str, str]]) -> float:
    """Signal fidelity: valid instrument readings from known tools only.

    Scoring per known tool call:
      - Valid JSON args: 1.0
      - Invalid JSON args: 0.5 (partial signal, learning)
      - Unknown tool name: 0.0 (no signal)
    """
    if not tool_calls:
        return 0.0

    valid = 0
    known_count = 0
    for tc in tool_calls:
        name = tc.get("name", "")
        if not is_known_tool(name):
            continue

        known_count += 1
        if tc["arguments"]:
            args = tc["arguments"]
            if isinstance(args, dict):
                valid += 1
            else:
                try:
                    json.loads(args)
                    valid += 1
                except (json.JSONDecodeError, TypeError):
                    valid += 0.5

    if known_count == 0:
        return 0.0
    return min(valid / known_count, 1.0)


def progression_score(tool_calls: list[dict[str, str]]) -> float:
    """Phase space trajectory: RECON->ENUM->EXPLOIT ordering.

    Scoring: 0.6 for phase presence + 0.4 for correct ordering.
    """
    if not tool_calls:
        return 0.0

    phases: list[str] = []
    for tc in tool_calls:
        phase = classify_phase(tc)
        if phase and (not phases or phases[-1] != phase):
            phases.append(phase)

    if not phases:
        return 0.0

    has_recon = "recon" in phases
    has_enum = "enum" in phases
    has_exploit = "exploit" in phases

    presence = 0.2 * has_recon + 0.2 * has_enum + 0.2 * has_exploit

    order = 0.0
    if has_recon and has_enum and phases.index("recon") < phases.index("enum"):
        order += 0.2
    if has_enum and has_exploit and phases.index("enum") < phases.index("exploit"):
        order += 0.2

    return min(presence + order, 1.0)


def exploration_score(
    tool_calls: list[dict[str, str]],
    gamma: float = 0.95,
) -> float:
    """Exponentially-decayed novelty of known instruments."""
    if not tool_calls:
        return 0.0

    seen: set = set()
    score = 0.0
    max_possible = 0.0

    for t, tc in enumerate(tool_calls):
        name = tc.get("name", "")
        if not name:
            continue

        decay = gamma**t

        if is_known_tool(name):
            max_possible += decay
            if name not in seen:
                seen.add(name)
                score += decay

    return score / max_possible if max_possible > 0 else 0.0


def uniqueness_score(tool_calls: list[dict[str, str]]) -> float:
    """Score command diversity (0.0 - 1.0). No regex.

    Information entropy: ratio of unique commands to total commands.
    Returns 0.0 for no tool calls, 0.5 for non-extractable commands.
    """
    if not tool_calls:
        return 0.0

    commands: list[str] = []
    for tc in tool_calls:
        cmd = extract_command(tc)
        if cmd:
            commands.append(cmd)

    if not commands:
        return 0.5

    return len(set(commands)) / len(commands)


def recovery_score(tool_calls: list[dict[str, str]]) -> float:
    """Resilience: reward pivots after stuck runs.

    A "stuck run" is 2+ consecutive calls with the same action
    fingerprint (tool name + binary name for shell wrappers).
    A "pivot" is transitioning out of a stuck run.
    """
    if len(tool_calls) < 3:
        return 0.5

    actions: list[str] = []
    for tc in tool_calls:
        actions.append(action_fingerprint(tc))

    if not actions:
        return 0.5

    stuck_runs = 0
    pivots = 0
    run_length = 1

    for i in range(1, len(actions)):
        if actions[i] == actions[i - 1]:
            run_length += 1
        else:
            if run_length >= 2:
                stuck_runs += 1
                pivots += 1
            run_length = 1

    if run_length >= 2:
        stuck_runs += 1

    if stuck_runs == 0:
        return 0.5

    return pivots / stuck_runs


def cognitive_score(text: str, tool_calls: list[dict[str, str]]) -> float:
    """Words-per-action scoring. Optimal reasoning density at ~42 WPA.

    Applies a repetition penalty: when >50% of tool calls share the
    same command, the score is capped at 0.3.
    """
    if not tool_calls:
        return 0.0

    words = text.split() if text else []
    word_count = len(words)

    if word_count < 5:
        return 0.5

    wpa = word_count / len(tool_calls)

    _OPTIMAL = 42.0
    if wpa < 10:
        score = 0.1
    elif wpa <= _OPTIMAL:
        score = 0.1 + 0.9 * (wpa - 10) / (_OPTIMAL - 10)
    elif wpa <= 80:
        score = 1.0 - 0.5 * (wpa - _OPTIMAL) / (80 - _OPTIMAL)
    else:
        score = 0.3

    if len(tool_calls) >= 4:
        commands = []
        for tc in tool_calls:
            cmd = extract_command(tc)
            commands.append(cmd)
        if commands:
            from collections import Counter

            most_common_count = Counter(commands).most_common(1)[0][1]
            if most_common_count > len(tool_calls) * 0.5:
                score = min(score, 0.3)

    return score


def hallucination_score(
    tool_calls: list[dict[str, str]],
    flag_sc: float,
    ground_truth: str | None = None,
    penalty: float = 0.20,
) -> float:
    """Energy loss for false flag submissions. Structural, no regex.

    When ``flag_found`` tool was called but flag_score < 1.0, the
    trajectory has moved backward. Returns a negative penalty.
    """
    import difflib

    if flag_sc >= 1.0:
        return 0.0

    for tc in tool_calls:
        if tc.get("name") in ("flag_found", "submit_flag"):
            pen = -penalty

            premature_mult = 1.0 + max(0.0, 1.0 - len(tool_calls) / 5.0)
            pen *= premature_mult

            if ground_truth:
                submitted = extract_command(tc).strip()
                if submitted:
                    similarity = difflib.SequenceMatcher(
                        None, submitted, ground_truth
                    ).ratio()
                    if similarity >= 0.8:
                        pen *= 0.1

            return pen

    return 0.0
