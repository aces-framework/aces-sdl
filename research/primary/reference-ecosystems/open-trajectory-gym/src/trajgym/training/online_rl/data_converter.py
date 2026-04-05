"""Online RL dataset conversion for SkyRL.

Converts trajgym Online RL JSONL to SkyRL's expected format, handling
challenge registry resolution, target URL rewriting, difficulty filtering,
and system prompt normalization.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

from trajgym.training.online_rl._utils import _DIFFICULTY_ORDER, _DIFFICULTY_RANK

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Prompt helpers
# ------------------------------------------------------------------


def _canonical_system_prompt() -> str:
    """Return the canonical system prompt with tool docs."""
    try:
        from trajgym.prompts import get_canonical_system_prompt

        return str(get_canonical_system_prompt())
    except Exception:
        # Keep a minimal fallback if converter import fails in stripped envs.
        return (
            "You are an expert penetration tester participating in a CTF challenge.\n"
            "Your goal is to find and capture the flag by systematically exploring and exploiting the target.\n\n"
            "Flags are often hidden or obfuscated. Check for encoding (base64, hex), "
            "reversed strings, split fragments across locations, and embedded data. "
            "Always verify your flag matches the expected format before submitting.\n\n"
            "Available tools:\n"
            "- shell_command: Run a shell command and get output\n"
            "- exec_command: Start an interactive process in a PTY session\n"
            "- write_stdin: Send input to a running PTY session\n"
            "- python_code: Execute Python code\n"
            "- read_file: Read file contents\n"
            "- grep: Search for patterns in files\n"
            "- file_search: Find files by name\n"
            "- flag_found: Submit a discovered flag\n"
            "- web_search: Search the web for information\n"
            "- apply_patch: Apply patches to files"
        )


def _normalize_prompt_system_tools(
    prompt: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Ensure the prompt has a system message with required tool docs.

    Some upstream traces occasionally include truncated system prompts
    (for example only two short sentences). This normalizes them so online
    Online RL always trains against the same tool-aware policy prompt.
    """
    required_markers = ("Available tools:", "- shell_command:", "- python_code:")

    for msg in prompt:
        if msg.get("role") != "system":
            continue
        content = msg.get("content", "")
        text = content if isinstance(content, str) else str(content)
        if all(marker in text for marker in required_markers):
            return prompt

        canonical = _canonical_system_prompt()
        if "Available tools:" in text:
            # Keep existing content, append only missing canonical lines.
            canonical_lines = [ln for ln in canonical.splitlines() if ln.strip()]
            merged = text.rstrip()
            for line in canonical_lines:
                if line not in merged:
                    merged += f"\n{line}"
            msg["content"] = merged
        elif text.strip():
            # Preserve custom lead-in, append canonical tools section.
            tools_block = canonical.split("Available tools:", 1)
            if len(tools_block) == 2:
                msg["content"] = (
                    f"{text.rstrip()}\n\nAvailable tools:\n{tools_block[1].lstrip()}"
                )
            else:
                msg["content"] = canonical
        else:
            msg["content"] = canonical

        logger.warning(
            "Normalized system prompt to canonical version (%d chars). "
            "Runtime _inject_tool_schemas() will add tool definitions before tokenization.",
            len(msg.get("content", "")),
        )
        return prompt

    prompt.insert(0, {"role": "system", "content": _canonical_system_prompt()})
    logger.warning("Injected missing system prompt with canonical tool docs.")
    return prompt


# ------------------------------------------------------------------
# Target URL rewriting
# ------------------------------------------------------------------


def _rewrite_target(
    raw_url: str,
    target_port_offset: int = 0,
    target_host_override: str | None = None,
) -> str:
    """Apply host/port overrides to a target URL."""
    # Raw TCP targets (common for crypto/pwn) are stored as host:port.
    # urlparse() treats these as scheme/path and cannot rewrite host/port,
    # so handle this form explicitly first.
    raw = str(raw_url or "").strip()
    raw_host_port = re.fullmatch(r"(?P<host>[^:/\s]+):(?P<port>\d+)", raw)
    if raw_host_port:
        host = target_host_override or raw_host_port.group("host")
        port = int(raw_host_port.group("port"))
        if target_port_offset:
            port += int(target_port_offset)
        return f"{host}:{port}"

    try:
        parsed = urlparse(raw)
    except Exception:
        return raw_url
    if not parsed.scheme or not parsed.netloc:
        return raw_url

    host = target_host_override or parsed.hostname or ""
    port = parsed.port
    if port is not None and target_port_offset:
        port = port + int(target_port_offset)

    netloc = host
    if parsed.username:
        auth = parsed.username
        if parsed.password:
            auth += f":{parsed.password}"
        netloc = f"{auth}@{netloc}"
    if port is not None:
        netloc = f"{netloc}:{port}"

    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def _first_user_url(prompt_messages: list[dict[str, str]]) -> str | None:
    """Return first URL in user prompt text, if present."""
    for msg in prompt_messages:
        if msg.get("role") != "user":
            continue
        match = re.search(r"(?:https?|file)://[^\s)]+", str(msg.get("content", "")))
        if match:
            return match.group(0)
    return None


def _rewrite_prompt_targets(
    prompt_messages: list[dict[str, str]],
    canonical_target: str,
) -> list[dict[str, str]]:
    """Rewrite stale connection URLs in user prompt text to canonical target.

    This helper is intentionally benchmark-neutral. It normalizes connection
    endpoints only, and strips known legacy prompt sections that leak
    challenge-specific shortcuts.
    """

    def _strip_legacy_non_neutral_sections(text: str) -> str:
        blocked_headers = {
            "# WEB RECON CHECKLIST",
            "# WEB EXPLOIT PLAYBOOK",
            "# CHALLENGE QUICKSTART (HIGH PRIORITY)",
        }
        lines = text.splitlines()
        cleaned: list[str] = []
        skipping = False
        for line in lines:
            stripped = line.strip()
            if stripped in blocked_headers:
                skipping = True
                continue
            if (
                skipping
                and stripped.startswith("# ")
                and stripped not in blocked_headers
            ):
                skipping = False
            if not skipping:
                cleaned.append(line)
        return "\n".join(cleaned)

    def _rewrite_http_url_preserve_path(url: str) -> str:
        """Rewrite only scheme/host/port to canonical target, preserving path/query."""
        try:
            canonical = urlparse(canonical_target)
            parsed = urlparse(url)
            if not canonical.scheme or not canonical.netloc:
                return canonical_target
            return urlunparse(
                (
                    canonical.scheme,
                    canonical.netloc,
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )
        except Exception:
            return canonical_target

    rewritten: list[dict[str, str]] = []
    for msg in prompt_messages:
        role = msg.get("role")
        content = str(msg.get("content", ""))
        if role != "user":
            rewritten.append({"role": role or "", "content": content})
            continue

        updated = content
        updated = _strip_legacy_non_neutral_sections(updated)
        # Keep structured connection lines consistent with the effective target.
        updated = re.sub(
            r"(\*\*Connection\*\*:\s*)([^\n]+)",
            lambda m: f"{m.group(1)}{canonical_target}",
            updated,
        )
        updated = re.sub(
            r"(You can interact with the challenge service at:\s*)([^\n]+)",
            lambda m: f"{m.group(1)}{canonical_target}",
            updated,
            flags=re.IGNORECASE,
        )
        # Replace stale localhost URLs (for example 328xx / 8901) with canonical target.
        if canonical_target.startswith(("http://", "https://")):
            updated = re.sub(
                r"https?://(?:localhost|127\.0\.0\.1):\d+(?:/[^\s)\"']*)?",
                lambda m: _rewrite_http_url_preserve_path(m.group(0)),
                updated,
            )
            # Also rewrite docker-compose service name URLs (e.g. http://web:8080)
            # that are unreachable from the training host.
            updated = re.sub(
                r"https?://(?!localhost|127\.0\.0\.1)[a-z][a-z0-9_-]*:\d+(?:/[^\s)\"']*)?",
                lambda m: _rewrite_http_url_preserve_path(m.group(0)),
                updated,
            )
        elif canonical_target.startswith("file://"):
            updated = re.sub(r"file://[^\s)\"']+", canonical_target, updated)
        elif re.fullmatch(r"[^:/\s]+:\d+", canonical_target):
            updated = re.sub(
                r"https?://(?:localhost|127\.0\.0\.1):\d+(?:/[^\s)\"']*)?",
                lambda m: _rewrite_http_url_preserve_path(m.group(0)),
                updated,
            )

        rewritten.append({"role": "user", "content": updated})
    return rewritten


# ------------------------------------------------------------------
# Main converter
# ------------------------------------------------------------------


def _convert_online_rl_data(
    data_path: str,
    output_dir: str,
    registry=None,
    drop_unresolved_registry_samples: bool = False,
    drop_static_challenges: bool = False,
    max_samples: int | None = None,
    max_samples_per_challenge: int | None = None,
    target_port_offset: int = 0,
    target_host_override: str | None = None,
    fail_on_target_collisions: bool = False,
    fail_on_flag_mismatch: bool = False,
    fail_on_missing_registry_flag: bool = False,
    require_all_registry_challenges: bool = False,
    prefer_registry_target: bool = False,
    difficulty_min: str | None = None,
    difficulty_max: str | None = None,
    exclude_challenge_ids: list[str] | None = None,
) -> str:
    """Convert our Online RL JSONL to SkyRL dataset format.

    SkyRL expects each sample to have:
      - prompt: list of message dicts (system + user)
      - Per-sample extras as flat top-level keys (ground_truth_flag, etc.)

    Our Online RL JSONL has:
      - messages: full trajectory (system, user, assistant, tool, ...)
      - ground_truth_flag: str
      - metadata: dict with optimal_steps, task_type, etc.

    We extract the prompt (system + user messages before first assistant)
    and flatten metadata as top-level keys for SkyRL extras.

    Args:
        data_path: Source Online RL JSONL path.
        output_dir: Output directory for converted JSONL.
        registry: Optional ChallengeRegistry for challenge ID normalization.
        drop_unresolved_registry_samples: If True and registry is provided,
            samples whose challenge ID cannot be resolved are dropped.
        drop_static_challenges: If True and registry is provided, samples
            whose resolved challenge has infra_type="static" are dropped.
            Static challenges have no running Docker service, so they waste
            compute during online RL training.
        max_samples: Optional cap on converted samples (after filtering).
        max_samples_per_challenge: Optional per-challenge cap for balancing.
        target_port_offset: Optional port offset applied to parsed target URLs.
            Useful for SSH-forwarded challenge ranges (e.g., 328xx -> 430xx).
        target_host_override: Optional host override for parsed target URLs.
        fail_on_target_collisions: If True, raise when multiple challenge IDs
            resolve to the same target URL.
        fail_on_flag_mismatch: If True, raise when dataset ground_truth_flag
            mismatches canonical registry ground_truth_flag.
        fail_on_missing_registry_flag: If True, raise when a resolved registry
            challenge has an empty ground_truth_flag.
        require_all_registry_challenges: If True, require converted data to
            include all registry challenge IDs after static/difficulty filtering.
        prefer_registry_target: If True, use registry-resolved target URL when
            available, even when a user message already contains a URL.
        difficulty_min: Optional minimum difficulty (inclusive). Requires registry.
            Samples below this difficulty are skipped. One of:
            very_easy, easy, medium, hard, expert, master.
        difficulty_max: Optional maximum difficulty (inclusive). Requires registry.
            Samples above this difficulty are skipped.

    Returns:
        Path to the converted JSONL file.
    """
    import jsonlines

    output_path = os.path.join(output_dir, "skyrl_online_rl_data.jsonl")
    os.makedirs(output_dir, exist_ok=True)

    # Validate difficulty bounds.
    min_rank: int | None = None
    max_rank: int | None = None
    if difficulty_min is not None:
        if difficulty_min not in _DIFFICULTY_RANK:
            raise ValueError(
                f"Invalid difficulty_min={difficulty_min!r}. Must be one of: {_DIFFICULTY_ORDER}"
            )
        min_rank = _DIFFICULTY_RANK[difficulty_min]
    if difficulty_max is not None:
        if difficulty_max not in _DIFFICULTY_RANK:
            raise ValueError(
                f"Invalid difficulty_max={difficulty_max!r}. Must be one of: {_DIFFICULTY_ORDER}"
            )
        max_rank = _DIFFICULTY_RANK[difficulty_max]
    if min_rank is not None and max_rank is not None and min_rank > max_rank:
        raise ValueError(
            f"difficulty_min={difficulty_min!r} is harder than difficulty_max={difficulty_max!r}."
        )

    converted = 0
    skipped = 0
    skipped_static = 0
    skipped_difficulty = 0
    unresolved_counts: dict[str, int] = {}
    missing_challenge_id = 0
    per_challenge_counts: dict[str, int] = {}
    target_to_challenges: dict[str, set[str]] = {}
    target_to_infra_types: dict[str, set[str]] = {}
    flag_mismatch_counts: dict[str, int] = {}
    missing_registry_flag_ids: set[str] = set()
    converted_registry_ids: set[str] = set()
    prompt_target_mismatch_samples = 0
    prompt_target_rewrite_samples = 0

    with (
        jsonlines.open(data_path) as reader,
        jsonlines.open(output_path, "w") as writer,
    ):
        for sample in reader:
            if max_samples and converted >= int(max_samples):
                break
            messages = sample.get("messages", [])

            # Extract prompt: system + user messages before first assistant/tool
            prompt = []
            for msg in messages:
                role = msg.get("role", "")
                if role in ("system", "user"):
                    prompt.append({"role": role, "content": msg.get("content", "")})
                else:
                    break

            # Normalize system prompt so tool docs are always present.
            prompt = _normalize_prompt_system_tools(prompt)

            # Ensure prompt ends with user message (SkyRL requirement)
            if not prompt or prompt[-1]["role"] != "user":
                challenge = sample.get("metadata", {}).get("challenge", "")
                prompt.append(
                    {
                        "role": "user",
                        "content": (
                            f"Solve the CTF challenge{f': {challenge}' if challenge else ''}. "
                            "Find and capture the flag."
                        ),
                    }
                )

            # Flatten extras as top-level keys (SkyRL reads them as extras).
            # env_class is required — SkyRL dataset pops it to find the registered env.
            metadata = sample.get("metadata", {})

            # Extract target URL from user messages (http(s) or file://).
            target = None
            for msg in messages:
                if msg.get("role") == "user":
                    urls = re.findall(
                        r"(?:https?|file)://[^\s)]+", msg.get("content", "")
                    )
                    if urls:
                        target = urls[0]
                        break
            if not target:
                target = metadata.get("target")

            # Resolve challenge ID against registry when available.
            challenge_id = metadata.get("challenge_id") or metadata.get("challenge")
            resolved_challenge_id = challenge_id
            if registry:
                if challenge_id:
                    resolved = registry.resolve_id(str(challenge_id))
                    if resolved is not None:
                        resolved_challenge_id = resolved
                    elif drop_unresolved_registry_samples:
                        skipped += 1
                        key = str(challenge_id)
                        unresolved_counts[key] = unresolved_counts.get(key, 0) + 1
                        continue
                elif drop_unresolved_registry_samples:
                    skipped += 1
                    missing_challenge_id += 1
                    continue

            # Drop static challenges (no Docker service to attack during online RL).
            if drop_static_challenges and registry and resolved_challenge_id:
                try:
                    _static_info = registry.get(str(resolved_challenge_id))
                    if _static_info.infra_type == "static":
                        skipped += 1
                        skipped_static += 1
                        continue
                except KeyError:
                    pass

            # Exclude specific challenge IDs (e.g. TCP-only challenges the model can't solve).
            if (
                exclude_challenge_ids
                and resolved_challenge_id
                and str(resolved_challenge_id) in exclude_challenge_ids
            ):
                skipped += 1
                logger.debug("Skipping excluded challenge: %s", resolved_challenge_id)
                continue

            # Difficulty curriculum filter: skip challenges outside the allowed range.
            if (
                (min_rank is not None or max_rank is not None)
                and registry
                and resolved_challenge_id
            ):
                try:
                    _diff_info = registry.get(str(resolved_challenge_id))
                    diff_rank = _DIFFICULTY_RANK.get(_diff_info.difficulty)
                    if diff_rank is not None:
                        if min_rank is not None and diff_rank < min_rank:
                            skipped += 1
                            skipped_difficulty += 1
                            continue
                        if max_rank is not None and diff_rank > max_rank:
                            skipped += 1
                            skipped_difficulty += 1
                            continue
                except KeyError:
                    pass

            registry_target = None
            registry_category = None
            registry_infra_type = None
            registry_path_hint = None
            registry_flag = None
            sample_flag = str(sample.get("ground_truth_flag") or "").strip() or None
            if registry and resolved_challenge_id:
                try:
                    info = registry.get(resolved_challenge_id)
                    registry_target = registry.get_target_url(resolved_challenge_id)
                    registry_category = info.category or None
                    registry_infra_type = info.infra_type or None
                    registry_path_hint = info.path_hint or None
                    registry_flag = info.ground_truth_flag or None
                    if not registry_flag:
                        missing_registry_flag_ids.add(str(resolved_challenge_id))
                    if (
                        registry_flag
                        and sample_flag
                        and sample_flag.strip() != str(registry_flag).strip()
                    ):
                        key = str(resolved_challenge_id)
                        flag_mismatch_counts[key] = flag_mismatch_counts.get(key, 0) + 1
                except KeyError:
                    registry_target = None

            # Prefer canonical registry target when configured (useful for
            # remote/tunneled runs where prompts may contain stale localhost URLs).
            if (
                prefer_registry_target
                and registry_target
                or not target
                and registry_target
            ):
                target = registry_target
            # Static challenges do not expose network targets in the registry.
            # Use a stable file:// target so envs avoid falling back to localhost.
            if not target and registry_infra_type == "static":
                target = "file:///root/challenge/"
            if target:
                target = _rewrite_target(
                    str(target),
                    target_port_offset=target_port_offset,
                    target_host_override=target_host_override,
                )

            # Category from registry (e.g. "crypto", "rev", "forensics", "web")
            # falls back to metadata.category if no registry match.
            category = registry_category or metadata.get("category")
            prompt_first_url_before = _first_user_url(prompt)
            if target:
                prompt = _rewrite_prompt_targets(
                    prompt,
                    str(target),
                )
                prompt_first_url_after = _first_user_url(prompt)
                if prompt_first_url_before and prompt_first_url_before != str(target):
                    prompt_target_mismatch_samples += 1
                if (
                    prompt_first_url_before
                    and prompt_first_url_after == str(target)
                    and prompt_first_url_before != prompt_first_url_after
                ):
                    prompt_target_rewrite_samples += 1

            if max_samples_per_challenge and resolved_challenge_id:
                key = str(resolved_challenge_id)
                current = per_challenge_counts.get(key, 0)
                if current >= int(max_samples_per_challenge):
                    skipped += 1
                    continue

            row = {
                "prompt": prompt,
                "env_class": "trajgym",
                # Registry is canonical whenever it provides a flag.
                "ground_truth_flag": registry_flag or sample_flag,
                "optimal_steps": sample.get("optimal_steps")
                or metadata.get("optimal_steps"),
                "challenge_id": resolved_challenge_id,
                "task_type": metadata.get("task_type", "challenge"),
                "target": target,
                "category": category,
                "infra_type": registry_infra_type or metadata.get("infra_type"),
                "path_hint": registry_path_hint or metadata.get("path_hint"),
            }

            writer.write(row)
            converted += 1
            if resolved_challenge_id:
                key = str(resolved_challenge_id)
                per_challenge_counts[key] = per_challenge_counts.get(key, 0) + 1
                converted_registry_ids.add(key)
                if target:
                    target_to_challenges.setdefault(str(target), set()).add(key)
                    infra_key = str(
                        registry_infra_type or metadata.get("infra_type") or ""
                    ).strip()
                    if infra_key:
                        target_to_infra_types.setdefault(str(target), set()).add(
                            infra_key
                        )

    if skipped:
        logger.warning(
            "Skipped %d/%d ONLINE_RL samples during conversion (registry filtering enabled=%s)",
            skipped,
            skipped + converted,
            bool(registry and drop_unresolved_registry_samples),
        )
    if unresolved_counts:
        top = sorted(unresolved_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        logger.warning("Top unresolved challenge IDs (sample count): %s", top)
    if missing_challenge_id:
        logger.warning(
            "Skipped %d samples with missing challenge_id/challenge metadata.",
            missing_challenge_id,
        )
    if skipped_static:
        logger.info(
            "Dropped %d static challenge samples (infra_type='static', no Docker service).",
            skipped_static,
        )
    if skipped_difficulty:
        logger.info(
            "Dropped %d samples by difficulty filter (min=%s, max=%s).",
            skipped_difficulty,
            difficulty_min,
            difficulty_max,
        )
    if prompt_target_mismatch_samples:
        logger.info(
            "Detected %d prompt/target URL mismatches; rewrote %d prompts to canonical target URLs.",
            prompt_target_mismatch_samples,
            prompt_target_rewrite_samples,
        )
    if missing_registry_flag_ids:
        sorted_missing = sorted(missing_registry_flag_ids)
        msg = (
            "Resolved registry challenges with missing ground_truth_flag: "
            f"{sorted_missing[:20]} (total={len(sorted_missing)})."
        )
        if fail_on_missing_registry_flag:
            raise ValueError(msg)
        logger.warning("%s", msg)
    if flag_mismatch_counts:
        top = sorted(flag_mismatch_counts.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]
        msg = (
            "Dataset ground_truth_flag mismatches registry for "
            f"{len(flag_mismatch_counts)} challenges. Top: {top}"
        )
        if fail_on_flag_mismatch:
            raise ValueError(msg)
        logger.warning("%s", msg)
    if converted == 0:
        raise ValueError(
            "No ONLINE_RL samples remained after conversion. "
            "Check challenge registry mappings or disable drop_unresolved_registry_samples."
        )
    if require_all_registry_challenges and registry:
        expected_ids: set[str] = set()
        for info in registry.list_all():
            if drop_static_challenges and info.infra_type == "static":
                continue
            diff_rank = _DIFFICULTY_RANK.get(info.difficulty)
            if diff_rank is not None:
                if min_rank is not None and diff_rank < min_rank:
                    continue
                if max_rank is not None and diff_rank > max_rank:
                    continue
            expected_ids.add(info.id)
        missing_expected = sorted(expected_ids - converted_registry_ids)
        if missing_expected:
            raise ValueError(
                "Converted online RL data is missing registry challenges after filtering: "
                f"{missing_expected[:20]} (missing={len(missing_expected)} total={len(expected_ids)})."
            )

    if max_samples_per_challenge:
        logger.info(
            "Per-challenge cap active: max_samples_per_challenge=%s (kept %d challenges)",
            max_samples_per_challenge,
            len(per_challenge_counts),
        )
    collisions = {}
    for tgt, ids in target_to_challenges.items():
        if len(ids) <= 1:
            continue
        # Static/file-based challenges intentionally share a local workspace
        # target (for example file:///root/challenge/) and should not fail
        # the docker tunnel collision gate.
        infra_types = target_to_infra_types.get(tgt, set())
        if tgt.startswith("file://") or infra_types == {"static"}:
            continue
        collisions[tgt] = sorted(ids)
    if collisions:
        top = sorted(collisions.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        logger.warning(
            "Detected %d target URL collisions (multiple challenge IDs share one target). "
            "This often indicates stale tunnel/port mapping. Top collisions: %s",
            len(collisions),
            top,
        )
        if fail_on_target_collisions:
            raise ValueError(
                "Target URL collisions detected during ONLINE_RL data conversion; "
                "provide a challenge target map (TRAJGYM_TARGET_MAP_PATH / "
                "online_rl.target_map_path) or disable fail_on_target_collisions."
            )

    logger.info("Converted %d online RL samples → %s", converted, output_path)
    return output_path
