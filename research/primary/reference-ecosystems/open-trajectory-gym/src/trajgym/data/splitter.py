"""Split converted BoxPwnr traces into SFT and online RL datasets.

SFT gets only successful traces (clean demonstrations).
Online RL gets ALL traces (success + failure) for contrastive learning,
with ground_truth_flag cross-referenced from successful traces
and optimal_steps computed as min successful turns per challenge.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# Shared regex patterns (single source of truth in converter)
from trajgym.data.converter import (
    _COMMAND_RE as _COMMAND_TAG_RE,
)
from trajgym.data.converter import (
    _OUTPUT_RE as _OUTPUT_TAG_RE,
)
from trajgym.data.converter import (
    _STDOUT_RE as _STDOUT_TAG_RE,
)

logger = logging.getLogger(__name__)


def _challenge_key(meta: dict[str, Any]) -> str:
    """Stable key for grouping traces by challenge."""
    platform = meta.get("platform", "unknown")
    challenge = meta.get("challenge", "unknown")
    return f"{platform}:{challenge}"


class DatasetSplitter:
    """Splits converted JSONL traces into SFT and online RL training sets."""

    def __init__(
        self,
        max_online_rl_tokens: int = 32768,
    ):
        self.max_online_rl_tokens = int(max_online_rl_tokens)

    def split(
        self,
        input_path: str,
        sft_output: str,
        online_rl_output: str,
    ) -> dict[str, Any]:
        """Split input JSONL into SFT and online RL sets.

        Args:
            input_path: Path to JSONL file from the converter.
            sft_output: Path for SFT output JSONL.
            online_rl_output: Path for online RL output JSONL.

        Returns:
            Summary statistics dict.
        """
        traces = self._load_traces(input_path)
        total_input = len(traces)

        # Normalize chat-command tags in all traces
        for trace in traces:
            trace["messages"] = self._normalize_chat_commands(trace["messages"])

        # Cross-reference flags from successful traces
        flag_lookup = self._crossref_flags(traces)

        # Compute optimal steps per challenge
        optimal_lookup = self._compute_optimal_steps(traces)

        # Apply cross-referenced data to all traces
        for trace in traces:
            key = _challenge_key(trace.get("metadata", {}))

            # Fill missing ground_truth_flag from successful siblings
            if not trace.get("ground_truth_flag") and key in flag_lookup:
                trace["ground_truth_flag"] = flag_lookup[key]

            # Set optimal_steps from cross-challenge minimum
            if key in optimal_lookup:
                trace["optimal_steps"] = optimal_lookup[key]

        # Split
        sft_traces = [t for t in traces if t.get("metadata", {}).get("success", False)]
        online_rl_traces = list(traces)  # all traces

        # Token filtering for online RL
        online_rl_filtered_count = 0
        online_rl_kept: list[dict] = []
        for trace in online_rl_traces:
            est = self._estimate_tokens(trace["messages"])
            if est > self.max_online_rl_tokens:
                online_rl_filtered_count += 1
                logger.debug(
                    "Filtered online RL trace (%d est tokens): %s",
                    est,
                    _challenge_key(trace.get("metadata", {})),
                )
            else:
                online_rl_kept.append(trace)

        # Count online RL traces still missing ground_truth_flag
        online_rl_missing_flag = sum(
            1 for t in online_rl_kept if not t.get("ground_truth_flag")
        )

        # Collect stats
        tool_counter: Counter[str] = Counter()
        platform_counter: Counter[str] = Counter()
        sft_turn_sum = 0
        online_rl_turn_sum = 0

        for trace in traces:
            meta = trace.get("metadata", {})
            platform_counter[meta.get("platform", "unknown")] += 1
            for msg in trace.get("messages", []):
                if msg.get("role") == "assistant" and msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        name = tc.get("function", {}).get("name", "unknown")
                        tool_counter[name] += 1

        for t in sft_traces:
            sft_turn_sum += self._count_turns(t["messages"])
        for t in online_rl_kept:
            online_rl_turn_sum += self._count_turns(t["messages"])

        # Write outputs
        Path(sft_output).parent.mkdir(parents=True, exist_ok=True)
        Path(online_rl_output).parent.mkdir(parents=True, exist_ok=True)

        self._write_jsonl(sft_output, sft_traces)
        self._write_jsonl(online_rl_output, online_rl_kept)

        stats = {
            "total_input": total_input,
            "sft_count": len(sft_traces),
            "online_rl_count": len(online_rl_kept),
            "online_rl_filtered": online_rl_filtered_count,
            "online_rl_missing_flag": online_rl_missing_flag,
            "tool_distribution": dict(tool_counter.most_common()),
            "platform_distribution": dict(platform_counter.most_common()),
            "avg_turns_sft": (
                round(sft_turn_sum / len(sft_traces), 1) if sft_traces else 0
            ),
            "avg_turns_online_rl": (
                round(online_rl_turn_sum / len(online_rl_kept), 1)
                if online_rl_kept
                else 0
            ),
        }

        return stats

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_traces(path: str) -> list[dict[str, Any]]:
        """Load JSONL file into a list of dicts."""
        traces: list[dict[str, Any]] = []
        with open(path) as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    traces.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Skipping malformed JSON at line %d: %s", lineno, exc
                    )
        return traces

    @staticmethod
    def _write_jsonl(path: str, records: list[dict[str, Any]]) -> None:
        """Write records as JSONL."""
        with open(path, "w") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _estimate_tokens(messages: list[dict]) -> int:
        """Rough token estimate: total chars / 4."""
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            reasoning = msg.get("reasoning_content", "")
            if isinstance(reasoning, str):
                total_chars += len(reasoning)
            # Count tool call arguments
            for tc in msg.get("tool_calls", []):
                args = tc.get("function", {}).get("arguments", "")
                if isinstance(args, str):
                    total_chars += len(args)
        return total_chars // 4

    @staticmethod
    def _compute_optimal_steps(traces: list[dict]) -> dict[str, int]:
        """Compute minimum assistant turns across successful traces per challenge."""
        challenge_turns: dict[str, list[int]] = defaultdict(list)

        for trace in traces:
            meta = trace.get("metadata", {})
            if not meta.get("success", False):
                continue
            key = _challenge_key(meta)
            turns = sum(
                1 for m in trace.get("messages", []) if m.get("role") == "assistant"
            )
            challenge_turns[key].append(turns)

        return {key: min(counts) for key, counts in challenge_turns.items()}

    @staticmethod
    def _crossref_flags(traces: list[dict]) -> dict[str, str]:
        """Build challenge -> ground_truth_flag lookup from successful traces."""
        lookup: dict[str, str] = {}
        for trace in traces:
            meta = trace.get("metadata", {})
            if not meta.get("success", False):
                continue
            flag = trace.get("ground_truth_flag")
            if flag:
                key = _challenge_key(meta)
                # Keep the first flag found (they should all be the same)
                if key not in lookup:
                    lookup[key] = flag
                elif lookup[key] != flag:
                    logger.warning(
                        "Flag conflict for challenge %s: existing=%r, new=%r",
                        key,
                        lookup[key],
                        flag,
                    )
        return lookup

    @staticmethod
    def _normalize_chat_commands(messages: list[dict]) -> list[dict]:
        """Parse <COMMAND>/<OUTPUT> tags in assistant/user content into tool_calls.

        If a message already has proper tool_calls, leave it alone.
        Only normalizes assistant messages that contain <COMMAND> tags
        paired with the following user message containing <OUTPUT>.
        """
        normalized: list[dict] = []
        i = 0
        while i < len(messages):
            msg = messages[i]

            # Only process assistant messages without existing tool_calls
            if (
                msg.get("role") == "assistant"
                and not msg.get("tool_calls")
                and isinstance(msg.get("content", ""), str)
                and _COMMAND_TAG_RE.search(msg["content"])
            ):
                content = msg["content"]
                cmd_match = _COMMAND_TAG_RE.search(content)
                command = cmd_match.group(2).strip()
                timeout = cmd_match.group(1)
                reasoning = content[: cmd_match.start()].strip()
                # Text after the command tag
                after = content[cmd_match.end() :].strip()
                if after:
                    reasoning = (
                        (reasoning + "\n\n" + after).strip() if reasoning else after
                    )

                call_id = f"call_{uuid.uuid4().hex[:12]}"
                args: dict[str, Any] = {"command": command}
                if timeout:
                    args["timeout"] = int(timeout)

                new_msg: dict[str, Any] = {"role": "assistant", "content": ""}
                if reasoning:
                    new_msg["reasoning_content"] = reasoning
                # Preserve existing reasoning_content if present
                if msg.get("reasoning_content"):
                    existing = msg["reasoning_content"]
                    if reasoning:
                        new_msg["reasoning_content"] = existing + "\n\n" + reasoning
                    else:
                        new_msg["reasoning_content"] = existing

                new_msg["tool_calls"] = [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": "shell_command",
                            "arguments": json.dumps(args),
                        },
                    }
                ]
                normalized.append(new_msg)

                # Check if next message is a user message with <OUTPUT>
                if i + 1 < len(messages):
                    next_msg = messages[i + 1]
                    next_content = next_msg.get("content", "")
                    if (
                        next_msg.get("role") == "user"
                        and isinstance(next_content, str)
                        and _OUTPUT_TAG_RE.search(next_content)
                    ):
                        output_match = _OUTPUT_TAG_RE.search(next_content)
                        output_block = output_match.group(1)
                        stdout_match = _STDOUT_TAG_RE.search(output_block)
                        stdout = (
                            stdout_match.group(1).strip()
                            if stdout_match
                            else output_block.strip()
                        )
                        normalized.append(
                            {
                                "role": "tool",
                                "tool_call_id": call_id,
                                "name": "shell_command",
                                "content": stdout,
                            }
                        )
                        i += 2
                        continue

                i += 1
            else:
                normalized.append(msg)
                i += 1

        return normalized

    @staticmethod
    def _count_turns(messages: list[dict]) -> int:
        """Count total non-system messages (a rough proxy for conversation turns)."""
        return sum(1 for m in messages if m.get("role") != "system")
