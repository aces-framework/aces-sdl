#!/usr/bin/env python3
"""Sample and characterize malformed traces from RL training, sorted by date."""

from __future__ import annotations
import re
import sys
from collections import defaultdict
from datetime import datetime
from datasets import load_dataset

REPO = "penfever/rl_rl-conf_24GP_base-yaml_mode-path_r2eg-nl2b-stac-bugs-fixt_trai-data_exp_rpt_pyme-larg"
PARSING_ERROR_MARKER = "Previous response had parsing errors"


def parse_date(date_str) -> datetime | None:
    if not isinstance(date_str, str):
        return None
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def has_parsing_error(conversations) -> bool:
    if not isinstance(conversations, list):
        return False
    for msg in conversations:
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str) and PARSING_ERROR_MARKER in content:
                return True
    return False


def count_parsing_errors(conversations) -> int:
    count = 0
    if not isinstance(conversations, list):
        return 0
    for msg in conversations:
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str) and PARSING_ERROR_MARKER in content:
                count += 1
    return count


def get_assistant_messages(conversations):
    results = []
    if not isinstance(conversations, list):
        return results
    for i, msg in enumerate(conversations):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str):
                results.append((i, content))
    return results


def find_first_malformed_message(conversations):
    """Find the assistant message just before the first parsing error."""
    if not isinstance(conversations, list):
        return None, None
    for i, msg in enumerate(conversations):
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str) and PARSING_ERROR_MARKER in content:
                for j in range(i - 1, -1, -1):
                    prev = conversations[j]
                    if isinstance(prev, dict) and prev.get("role") == "assistant":
                        return j, prev.get("content", "")
                return i, content
    return None, None


def classify_failure(content: str) -> str:
    if not content or not content.strip():
        return "EMPTY_RESPONSE"

    stripped = content.strip()
    has_think_open = "<think>" in stripped
    has_think_close = "</think>" in stripped
    has_json_brace = "{" in stripped

    after_think = stripped
    if "</think>" in stripped:
        after_think = stripped.split("</think>", 1)[-1].strip()

    json_after_think = after_think.startswith("{") if after_think else False
    open_braces = stripped.count("{")
    close_braces = stripped.count("}")

    if not has_json_brace:
        if has_think_open and not has_think_close:
            return "THINKING_NOT_CLOSED"
        return "NO_JSON_STRUCTURE"

    if has_think_close and json_after_think:
        if after_think.rstrip().endswith("}"):
            if open_braces == close_braces:
                return "VALID_FORMAT"
            return "BRACE_MISMATCH"
        return "TRUNCATED_JSON_AFTER_THINK"

    if not stripped.startswith("<") and not stripped.startswith("{"):
        return "TEXT_BEFORE_JSON"

    if has_think_open and not has_think_close:
        return "THINKING_NOT_CLOSED"

    if open_braces > close_braces + 1:
        return "TRUNCATED_JSON"

    if stripped.startswith("{") and stripped.rstrip().endswith("}"):
        return "JSON_ONLY_NO_THINK"

    return "OTHER"


def main():
    print(f"Loading dataset: {REPO}")
    ds = load_dataset(REPO, split="train")
    print(f"Total rows: {len(ds)}")

    # Parse dates and sort
    rows_with_dates = []
    for i in range(len(ds)):
        row = ds[i]
        dt = parse_date(row.get("date", ""))
        if dt:
            rows_with_dates.append((dt, i))

    rows_with_dates.sort(key=lambda x: x[0])
    print(f"Rows with valid dates: {len(rows_with_dates)}")
    print(f"Date range: {rows_with_dates[0][0]} -> {rows_with_dates[-1][0]}")
    print()

    # Divide into temporal bins: first 64, next 64, next 64, next 64
    # (each group of 64 traces ~= 1 training step worth of data)
    bins = [
        ("Bin A: traces 1-64 (pre-step-0)", rows_with_dates[:64]),
        ("Bin B: traces 65-128", rows_with_dates[64:128]),
        ("Bin C: traces 129-256", rows_with_dates[128:256]),
        ("Bin D: traces 257-512", rows_with_dates[256:512]),
        ("Bin E: traces 513-1024", rows_with_dates[512:1024]),
        ("Bin F: traces 1025-2048", rows_with_dates[1024:2048]),
        ("Bin G: traces 5000-5064 (mid-training)", rows_with_dates[5000:5064]),
    ]

    for bin_name, bin_rows in bins:
        if not bin_rows:
            print(f"=== {bin_name}: NO DATA ===\n")
            continue

        total = len(bin_rows)
        error_indices = []
        ok_indices = []
        classification_counts = defaultdict(int)

        for dt, idx in bin_rows:
            row = ds[idx]
            convos = row.get("conversations", [])
            if has_parsing_error(convos):
                error_indices.append((dt, idx))
                _, mal_content = find_first_malformed_message(convos)
                cls = classify_failure(mal_content) if mal_content else "UNKNOWN"
                classification_counts[cls] += 1
            else:
                ok_indices.append((dt, idx))

        n_err = len(error_indices)
        err_rate = n_err / total * 100 if total else 0
        date_start = bin_rows[0][0].strftime("%H:%M:%S")
        date_end = bin_rows[-1][0].strftime("%H:%M:%S")

        print(f"{'=' * 80}")
        print(f"{bin_name}")
        print(f"  Time range: {date_start} - {date_end}")
        print(f"  Traces: {total}, Parse errors: {n_err} ({err_rate:.1f}%), OK: {len(ok_indices)}")
        if classification_counts:
            print(f"  Failure types:")
            for cls, count in sorted(classification_counts.items(), key=lambda x: -x[1]):
                print(f"    {cls}: {count}")
        print(f"{'=' * 80}")

        # Show up to 3 error traces
        for dt, idx in error_indices[:3]:
            row = ds[idx]
            convos = row.get("conversations", [])
            n_parse_errs = count_parsing_errors(convos)
            mal_idx, mal_content = find_first_malformed_message(convos)
            assistant_msgs = get_assistant_messages(convos)
            cls = classify_failure(mal_content) if mal_content else "UNKNOWN"

            print(f"\n  [ERROR] date={dt} task={row.get('task','?')} result={row.get('result','?')}")
            print(f"    msgs={len(convos)} asst_msgs={len(assistant_msgs)} parse_errors={n_parse_errs}")
            print(f"    Failure type: {cls}")
            if mal_content:
                print(f"    Malformed msg (idx {mal_idx}, {len(mal_content)} chars):")
                print(f"      FIRST 800: {repr(mal_content[:800])}")
                if len(mal_content) > 800:
                    print(f"      LAST  400: {repr(mal_content[-400:])}")

        # Show up to 2 OK traces
        for dt, idx in ok_indices[:2]:
            row = ds[idx]
            convos = row.get("conversations", [])
            assistant_msgs = get_assistant_messages(convos)
            first_asst = assistant_msgs[0][1] if assistant_msgs else ""
            cls = classify_failure(first_asst)

            print(f"\n  [OK] date={dt} task={row.get('task','?')} result={row.get('result','?')}")
            print(f"    msgs={len(convos)} asst_msgs={len(assistant_msgs)}")
            print(f"    First assistant format: {cls}")
            print(f"      FIRST 800: {repr(first_asst[:800])}")

        print("\n")


if __name__ == "__main__":
    main()
