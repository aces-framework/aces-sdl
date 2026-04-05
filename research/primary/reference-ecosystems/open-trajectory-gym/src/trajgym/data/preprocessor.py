#!/usr/bin/env python3
"""Preprocess SFT JSONL data for training quality.

Handles 6 known data quality issues found in sft_curated.jsonl:
  1. HTML-escaped content (&lt; → <, etc.)
  2. Orphan </think> tags (missing opening <think>)
  3. Trajectories missing terminal flag_found call
  4. Non-canonical tool calls (Edit, Task, Write, etc.)
  5. Hallucinated flag submissions (inject "Incorrect" verification)
  6. Echo assistant responses ("Flag found: ..." with no reasoning)

Usage:
  python scripts/preprocess_sft_data.py \
      --input data/sft_curated.jsonl \
      --output data/sft_curated_clean.jsonl

  # Dry run (report issues without writing):
  python scripts/preprocess_sft_data.py \
      --input data/sft_curated.jsonl --dry-run
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

# --- Canonical tools (from trajgym.envs.tool_executor) ---
_CANONICAL_TOOLS = frozenset(
    {
        "shell_command",
        "exec_command",
        "write_stdin",
        "python_code",
        "read_file",
        "grep",
        "file_search",
        "apply_patch",
        "flag_found",
        "web_search",
        "list_sessions",
        "close_session",
        "execute_command",
        # Allow submit_flag as alias
        "submit_flag",
    }
)


def _fix_html_escapes(text: str) -> str:
    """Unescape HTML entities (&lt; &gt; &amp; &quot; &#39;).

    Applies twice to handle double-encoded entities (e.g. &amp;lt; → &lt; → <).
    """
    result = html.unescape(text)
    # Second pass for double-encoded entities
    result2 = html.unescape(result)
    return result2


def _fix_orphan_think(text: str) -> str:
    """Fix orphan </think> tags by prepending <think>."""
    # If content has </think> but no <think> before it, prepend <think>
    if "</think>" in text and "<think>" not in text.split("</think>")[0]:
        text = "<think>" + text
    return text


def _extract_submitted_flag(tool_call: dict) -> str | None:
    """Extract the submitted flag string from a flag_found tool call."""
    args_raw = tool_call.get("function", {}).get("arguments", "{}")
    if isinstance(args_raw, str):
        try:
            args = json.loads(args_raw)
        except json.JSONDecodeError:
            return args_raw.strip() or None
    elif isinstance(args_raw, dict):
        args = args_raw
    else:
        return None
    return args.get("content") or args.get("flag") or args.get("answer") or None


def _is_non_canonical(tool_call: dict) -> bool:
    """Check if a tool call uses a non-canonical tool."""
    name = tool_call.get("function", {}).get("name", "")
    return name not in _CANONICAL_TOOLS


def _make_flag_found_call(flag: str, call_id: str = "auto_flag") -> dict:
    """Build a flag_found tool call message."""
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": "flag_found",
                    "arguments": json.dumps({"content": flag}),
                },
            }
        ],
    }


def _make_verification(call_id: str, submitted: str, ground_truth: str | None) -> dict:
    """Build a verification tool response."""
    if submitted and ground_truth and submitted.strip() == ground_truth.strip():
        content = f"Correct! Flag verified: {submitted}"
    elif submitted and ground_truth:
        content = f"Incorrect submission: {submitted}. The flag was not correct."
    elif submitted:
        content = f"Flag submitted: {submitted}"
    else:
        content = "No flag content provided."
    msg: dict = {"role": "tool", "content": content, "name": "flag_found"}
    if call_id:
        msg["tool_call_id"] = call_id
    return msg


def _is_proper_verification(content: str) -> bool:
    """Check if tool response content is a proper verification (not an echo)."""
    if not content:
        return False
    # Our injected verification format
    if "Correct!" in content or "Incorrect submission:" in content:
        return True
    # Some environments return explicit pass/fail
    return bool(
        "Flag submitted:" in content
        and ("correct" in content.lower() or "incorrect" in content.lower())
    )


def _find_flag_response_idx(messages: list[dict], start: int, tc: dict) -> int | None:
    """Find the index of the tool response for a flag_found call.

    Returns the message index or None if not found.
    """
    tc_id = tc.get("id", "")
    for j in range(start, min(start + 5, len(messages))):
        m = messages[j]
        if m.get("role") != "tool":
            continue
        if m.get("tool_call_id") == tc_id and tc_id:
            return j
        if m.get("name") in ("flag_found", "submit_flag"):
            return j
    return None


def preprocess_sample(sample: dict) -> tuple[dict | None, dict]:
    """Preprocess a single SFT sample. Returns (fixed_sample_or_None, stats).

    Returns None if the sample should be dropped entirely.
    """
    stats = {
        "html_fixed": 0,
        "think_fixed": 0,
        "echo_stripped": 0,
        "noncanonical_stripped": 0,
        "verification_injected": 0,
        "verification_replaced": 0,
        "terminal_flag_added": 0,
        "dropped": False,
    }

    messages = list(sample.get("messages", []))
    ground_truth = sample.get("ground_truth_flag", "")

    # --- Pass 1: Fix HTML escapes and orphan think tags in all messages ---
    for m in messages:
        content = m.get("content") or ""
        if not content:
            continue

        # HTML unescape
        fixed = _fix_html_escapes(content)
        if fixed != content:
            stats["html_fixed"] += 1
            content = fixed

        # Orphan think tags
        fixed = _fix_orphan_think(content)
        if fixed != content:
            stats["think_fixed"] += 1
            content = fixed

        m["content"] = content

    # --- Pass 2: Strip non-canonical tool calls and echo responses ---
    cleaned: list[dict] = []
    skip_next_tools = set()  # tool_call_ids to skip their responses

    for _i, m in enumerate(messages):
        role = m.get("role", "")
        content = m.get("content", "") or ""

        # Skip echo assistant responses (e.g. "Flag found: {flag}")
        if role == "assistant" and content.strip().startswith("Flag found:"):
            tool_calls = m.get("tool_calls", [])
            if not tool_calls:
                stats["echo_stripped"] += 1
                continue

        # Handle tool responses for skipped non-canonical calls
        if role == "tool" and m.get("tool_call_id") in skip_next_tools:
            skip_next_tools.discard(m.get("tool_call_id"))
            continue

        # Filter non-canonical tool calls from assistant messages
        tool_calls = m.get("tool_calls", [])
        if tool_calls:
            canonical_tcs = []
            for tc in tool_calls:
                if _is_non_canonical(tc):
                    stats["noncanonical_stripped"] += 1
                    tc_id = tc.get("id")
                    if tc_id:
                        skip_next_tools.add(tc_id)
                else:
                    canonical_tcs.append(tc)

            if not canonical_tcs and not content.strip():
                # Assistant message had ONLY non-canonical tool calls and no content
                continue
            elif not canonical_tcs:
                # Had content but no canonical tools — keep as text-only
                m = dict(m)
                m.pop("tool_calls", None)
            else:
                m = dict(m)
                m["tool_calls"] = canonical_tcs

        cleaned.append(m)

    messages = cleaned

    # --- Pass 3: Ensure every flag_found call has a proper verification response ---
    # Two cases:
    #   a) Existing response is an echo ("Flag found: X") — replace with verification
    #   b) No response at all — inject verification
    #   c) Existing response is proper ("Correct!", "Incorrect") — keep as-is
    final: list[dict] = []
    replace_indices: set[int] = set()  # message indices to replace

    # First pass: identify which flag_found responses need replacing
    for i, m in enumerate(messages):
        tool_calls = m.get("tool_calls") or []
        flag_calls = [
            tc
            for tc in tool_calls
            if tc.get("function", {}).get("name") in ("flag_found", "submit_flag")
        ]
        for tc in flag_calls:
            resp_idx = _find_flag_response_idx(messages, i + 1, tc)
            if resp_idx is not None:
                resp_content = messages[resp_idx].get("content", "") or ""
                if not _is_proper_verification(resp_content):
                    replace_indices.add(resp_idx)

    # Second pass: build final message list
    for i, m in enumerate(messages):
        if i in replace_indices:
            # Replace echo/bad response with proper verification
            tc_id = m.get("tool_call_id", "")
            # Find the corresponding flag_found call to get submitted flag
            submitted = None
            for j in range(max(0, i - 5), i):
                for tc in messages[j].get("tool_calls", []):
                    fn = tc.get("function", {}).get("name", "")
                    if fn in ("flag_found", "submit_flag") and (
                        tc.get("id") == tc_id or not tc_id
                    ):
                        submitted = _extract_submitted_flag(tc)
            verification = _make_verification(
                call_id=tc_id,
                submitted=submitted or "",
                ground_truth=ground_truth,
            )
            final.append(verification)
            stats["verification_replaced"] += 1
            continue

        final.append(m)

        # Also inject verification for flag_found calls with NO response at all
        tool_calls = m.get("tool_calls") or []
        flag_calls = [
            tc
            for tc in tool_calls
            if tc.get("function", {}).get("name") in ("flag_found", "submit_flag")
        ]
        for tc in flag_calls:
            resp_idx = _find_flag_response_idx(messages, i + 1, tc)
            if resp_idx is None:
                submitted = _extract_submitted_flag(tc)
                verification = _make_verification(
                    call_id=tc.get("id", ""),
                    submitted=submitted or "",
                    ground_truth=ground_truth,
                )
                final.append(verification)
                stats["verification_injected"] += 1

    messages = final

    # --- Pass 4: Add terminal flag_found if missing ---
    has_flag_call = any(
        tc.get("function", {}).get("name") in ("flag_found", "submit_flag")
        for m in messages
        for tc in m.get("tool_calls", [])
    )

    if not has_flag_call and ground_truth:
        # Add a terminal flag_found + correct verification
        messages.append(_make_flag_found_call(ground_truth, call_id="terminal_flag"))
        messages.append(
            _make_verification(
                call_id="terminal_flag",
                submitted=ground_truth,
                ground_truth=ground_truth,
            )
        )
        stats["terminal_flag_added"] += 1

    # --- Build result ---
    # Drop samples with fewer than 4 messages (system + user + at least 1 turn)
    if len(messages) < 4:
        stats["dropped"] = True
        return None, stats

    result = dict(sample)
    result["messages"] = messages
    return result, stats


def process_file(input_path: Path, output_path: Path | None) -> dict:
    """Process an entire JSONL file. If output_path is None, dry-run only."""
    totals = {
        "samples_in": 0,
        "samples_out": 0,
        "samples_dropped": 0,
        "html_fixed": 0,
        "think_fixed": 0,
        "echo_stripped": 0,
        "noncanonical_stripped": 0,
        "verification_injected": 0,
        "verification_replaced": 0,
        "terminal_flag_added": 0,
    }

    fout = open(output_path, "w") if output_path else None  # noqa: SIM115

    try:
        with open(input_path) as fin:
            for line in fin:
                line = line.strip()
                if not line:
                    continue

                sample = json.loads(line)
                totals["samples_in"] += 1

                fixed, stats = preprocess_sample(sample)

                if stats["dropped"] or fixed is None:
                    totals["samples_dropped"] += 1
                    continue

                totals["samples_out"] += 1
                for key in (
                    "html_fixed",
                    "think_fixed",
                    "echo_stripped",
                    "noncanonical_stripped",
                    "verification_injected",
                    "verification_replaced",
                    "terminal_flag_added",
                ):
                    totals[key] += stats[key]

                if fout:
                    fout.write(json.dumps(fixed, ensure_ascii=False) + "\n")
    finally:
        if fout:
            fout.close()

    return totals


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preprocess SFT JSONL data: fix HTML escapes, think tags, "
        "non-canonical tools, hallucinated flags, missing verifications."
    )
    parser.add_argument("--input", required=True, help="Input SFT JSONL file")
    parser.add_argument("--output", help="Output JSONL file (omit for dry run)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report issues without writing output"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = None if args.dry_run else Path(args.output) if args.output else None
    if not args.dry_run and not output_path:
        print("Error: --output required (or use --dry-run)", file=sys.stderr)
        sys.exit(1)

    totals = process_file(input_path, output_path)

    print(f"Input:  {totals['samples_in']} samples from {input_path}")
    if output_path:
        print(f"Output: {totals['samples_out']} samples to {output_path}")
    else:
        print(f"Output: {totals['samples_out']} samples (dry run, no file written)")
    print(f"  Dropped:                 {totals['samples_dropped']}")
    print(f"  HTML escapes fixed:      {totals['html_fixed']}")
    print(f"  Orphan think tags fixed: {totals['think_fixed']}")
    print(f"  Echo responses stripped:  {totals['echo_stripped']}")
    print(f"  Non-canonical tools stripped: {totals['noncanonical_stripped']}")
    print(f"  Verifications injected:  {totals['verification_injected']}")
    print(f"  Verifications replaced:  {totals['verification_replaced']}")
    print(f"  Terminal flag_found added: {totals['terminal_flag_added']}")


if __name__ == "__main__":
    main()
