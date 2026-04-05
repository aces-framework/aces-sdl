#!/usr/bin/env python3
"""
Analyze malformed traces from RL training checkpoint evaluations.

These are eval rollouts from two RL checkpoint variants:
  - "noth" (no-think): checkpoint step 110, ~22% parse error rate
  - "fixt" (fix-think): checkpoint step 45, ~13% parse error rate

Each dataset has episode-N episodes. We analyze the MALFORMED assistant
outputs to understand what types of formatting failures occur.
"""

import json
import os
import random
import re
import statistics
from collections import Counter, defaultdict

from datasets import load_dataset


DATASETS = [
    ("DCAgent2/dev_set_v2_rl_rl_conf_24GP_base_noth_yaml_mode_path_r2eg_nl2b_stac_bugs_trai_daadf65c04", "noth_v2_step110", 297),
    ("DCAgent2/dev_set_v2_rl_rl_conf_24GP_base_yaml_mode_path_r2eg_nl2b_stac_bugs_fixt_trai_daddc63529", "fixt_v2_step45", 297),
    ("DCAgent2/dev_set_71_tasks_rl_rl_conf_24GP_base_noth_yaml_mode_path_r2eg_nl2b_stac_bugs_t3c184dcc", "noth_71tasks_step110", 210),
    ("DCAgent2/dev_set_71_tasks_rl_rl_conf_24GP_base_yaml_mode_path_r2eg_nl2b_stac_bugs_fixt_tebb946f3", "fixt_71tasks_step45", 210),
]


def has_parsing_error(conversations):
    for msg in conversations:
        content = msg.get("content", "") or ""
        if "Previous response had parsing errors" in content:
            return True
    return False


def count_parsing_errors(conversations):
    count = 0
    for msg in conversations:
        content = msg.get("content", "") or ""
        if "Previous response had parsing errors" in content:
            count += 1
    return count


def get_last_assistant_message(conversations):
    for msg in reversed(conversations):
        if msg.get("role") == "assistant":
            return msg.get("content", "") or ""
    return ""


def get_first_assistant_message(conversations):
    for msg in conversations:
        if msg.get("role") == "assistant":
            return msg.get("content", "") or ""
    return ""


def get_malformed_assistant_messages(conversations):
    """
    Find each assistant message that came BEFORE a 'Previous response had parsing errors' message.
    Returns list of dicts with content, position info.
    """
    results = []
    for i, msg in enumerate(conversations):
        content = msg.get("content", "") or ""
        if "Previous response had parsing errors" in content:
            for j in range(i - 1, -1, -1):
                if conversations[j].get("role") == "assistant":
                    results.append({
                        "content": conversations[j].get("content", "") or "",
                        "assistant_idx": j,
                        "error_idx": i,
                        "error_content": content,
                    })
                    break
    return results


def get_parsing_error_messages(conversations):
    """Get the actual parsing error feedback messages."""
    results = []
    for msg in conversations:
        content = msg.get("content", "") or ""
        if "Previous response had parsing errors" in content:
            results.append(content)
    return results


def classify_malformation(text):
    """Classify what kind of malformation this is."""
    if not text or not text.strip():
        return "EMPTY_RESPONSE"

    stripped = text.strip()

    # Check for thinking tokens
    has_think = "<think>" in stripped or "</think>" in stripped
    has_reasoning = "<reasoning>" in stripped or "</reasoning>" in stripped

    if has_think or has_reasoning:
        # Remove thinking block and check what remains
        cleaned = re.sub(r'<think>.*?</think>', '', stripped, flags=re.DOTALL).strip()
        cleaned = re.sub(r'<reasoning>.*?</reasoning>', '', cleaned, flags=re.DOTALL).strip()
        if not cleaned:
            return "THINKING_TOKENS_ONLY"
        # Check if remaining is valid JSON/YAML
        try:
            json.loads(cleaned)
            return "THINKING_TOKENS_WRAPPING_VALID_JSON"
        except:
            pass
        if cleaned.startswith("```"):
            return "THINKING_THEN_CODE_FENCE"
        if cleaned.startswith("{") or cleaned.startswith("["):
            return "THINKING_THEN_BROKEN_JSON"
        return "THINKING_THEN_TEXT"

    # Check for markdown code fences
    if stripped.startswith("```"):
        # Extract content inside fences
        fence_match = re.match(r'```\w*\n?(.*?)```', stripped, re.DOTALL)
        if fence_match:
            inner = fence_match.group(1).strip()
            try:
                json.loads(inner)
                return "CODE_FENCE_AROUND_VALID_JSON"
            except:
                return "CODE_FENCE_AROUND_INVALID_CONTENT"
        return "UNCLOSED_CODE_FENCE"

    # Check if it starts with JSON
    starts_json = stripped.startswith("{") or stripped.startswith("[")

    # Try parsing as JSON
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            keys = set(parsed.keys())
            if "action" in keys and "command" in keys:
                return "VALID_JSON_ACTION_COMMAND"
            elif "action" in keys:
                return "VALID_JSON_WITH_ACTION"
            return f"VALID_JSON_KEYS({','.join(sorted(keys)[:5])})"
        return "VALID_JSON_NON_DICT"
    except json.JSONDecodeError as e:
        json_err = str(e)

    # Try parsing as YAML
    if "action:" in stripped or "command:" in stripped:
        return "YAML_FORMAT_NOT_JSON"

    if starts_json:
        open_braces = stripped.count("{") - stripped.count("}")
        open_brackets = stripped.count("[") - stripped.count("]")

        if open_braces > 0 or open_brackets > 0:
            return f"TRUNCATED_JSON(unclosed_braces={open_braces},brackets={open_brackets})"

        if stripped.endswith("}") or stripped.endswith("]"):
            # Try to identify the specific JSON error
            if "Expecting ',' delimiter" in json_err:
                return "JSON_MISSING_COMMA"
            elif "Expecting property name" in json_err:
                return "JSON_BAD_PROPERTY"
            elif "Expecting value" in json_err:
                return "JSON_EXPECTING_VALUE"
            elif "Unterminated string" in json_err:
                return "JSON_UNTERMINATED_STRING"
            elif "Invalid control character" in json_err:
                return "JSON_INVALID_CONTROL_CHAR"
            elif "Invalid \\escape" in json_err:
                return "JSON_INVALID_ESCAPE"
            return f"JSON_SYNTAX_ERROR({json_err[:60]})"
        else:
            last_brace = max(stripped.rfind("}"), stripped.rfind("]"))
            if last_brace > 0:
                trailing = stripped[last_brace+1:].strip()[:80]
                return f"JSON_WITH_TRAILING({repr(trailing[:40])})"
            return "JSON_WITH_TRAILING_TEXT"

    # Plain text
    if "{" in stripped:
        return "TEXT_THEN_JSON"
    if "action" in stripped.lower():
        return "PLAIN_TEXT_MENTIONS_ACTION"
    return "PLAIN_TEXT"


def truncate(text, max_len=2000):
    if not text:
        return "<empty>"
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n... [TRUNCATED, total length={len(text)}]"


def print_indented(text, prefix="    | ", max_len=2000):
    for line in truncate(text, max_len).split('\n'):
        print(f"{prefix}{line}")


def main():
    token = os.environ.get("HF_TOKEN", None)
    random.seed(42)

    for ds_name, label, expected_rows in DATASETS:
        print("\n" + "=" * 120)
        print(f"DATASET: {label}")
        print(f"  {ds_name}")
        print("=" * 120)

        ds = load_dataset(ds_name, split="train", token=token)
        print(f"Rows: {len(ds)}, Columns: {ds.column_names}")

        # Separate error vs ok traces
        error_traces = []
        ok_traces = []
        for i in range(len(ds)):
            row = ds[i]
            convos = row["conversations"]
            if has_parsing_error(convos):
                error_traces.append(row)
            else:
                ok_traces.append(row)

        print(f"Parse error traces: {len(error_traces)}/{len(ds)} ({100*len(error_traces)/len(ds):.1f}%)")
        print(f"Clean traces: {len(ok_traces)}/{len(ds)} ({100*len(ok_traces)/len(ds):.1f}%)")

        # Result distribution for error vs ok
        error_results = Counter(r["result"] for r in error_traces)
        ok_results = Counter(r["result"] for r in ok_traces)
        print(f"\nResult distribution (error traces): {dict(error_results.most_common(5))}")
        print(f"Result distribution (clean traces): {dict(ok_results.most_common(5))}")

        # Count parse errors per trace
        error_counts = Counter()
        for r in error_traces:
            n = count_parsing_errors(r["conversations"])
            error_counts[n] += 1
        print(f"\nParse errors per trace distribution: {dict(sorted(error_counts.items()))}")

        # Message count distribution
        error_msg_counts = [len(r["conversations"]) for r in error_traces]
        ok_msg_counts = [len(r["conversations"]) for r in ok_traces]
        if error_msg_counts:
            print(f"Msg count (error traces): min={min(error_msg_counts)}, max={max(error_msg_counts)}, median={statistics.median(error_msg_counts):.0f}")
        if ok_msg_counts:
            print(f"Msg count (clean traces): min={min(ok_msg_counts)}, max={max(ok_msg_counts)}, median={statistics.median(ok_msg_counts):.0f}")

        # =====================================================
        # CLASSIFY ALL MALFORMED MESSAGES
        # =====================================================
        print(f"\n{'=' * 80}")
        print(f"MALFORMATION CLASSIFICATION (all error traces)")
        print(f"{'=' * 80}")

        all_classifications = []
        all_malformed = []
        for r in error_traces:
            malformed_list = get_malformed_assistant_messages(r["conversations"])
            for minfo in malformed_list:
                cls = classify_malformation(minfo["content"])
                all_classifications.append(cls)
                all_malformed.append({
                    "classification": cls,
                    "content": minfo["content"],
                    "error_content": minfo["error_content"],
                    "task": r.get("task", ""),
                    "episode": r.get("episode", ""),
                    "result": r.get("result", ""),
                    "assistant_idx": minfo["assistant_idx"],
                    "num_messages": len(r["conversations"]),
                })

        cls_counts = Counter(all_classifications)
        total = len(all_classifications)
        print(f"Total malformed assistant messages: {total}")
        for cls, count in cls_counts.most_common():
            print(f"  {cls}: {count} ({100*count/total:.1f}%)")

        # Length stats
        lengths = [len(m["content"]) for m in all_malformed]
        if lengths:
            print(f"\nMalformed message length stats:")
            print(f"  min={min(lengths)}, max={max(lengths)}, median={statistics.median(lengths):.0f}, mean={statistics.mean(lengths):.0f}")

        # Position stats: where in the conversation does the first parse error occur?
        first_error_positions = []
        for r in error_traces:
            for mi, msg in enumerate(r["conversations"]):
                if "Previous response had parsing errors" in (msg.get("content", "") or ""):
                    first_error_positions.append(mi)
                    break
        if first_error_positions:
            print(f"\nFirst parse error position in conversation:")
            print(f"  min={min(first_error_positions)}, max={max(first_error_positions)}, median={statistics.median(first_error_positions):.0f}")

        # =====================================================
        # DETAILED EXAMPLES: 5 error traces + 3 clean traces
        # =====================================================
        print(f"\n{'=' * 80}")
        print(f"SAMPLED ERROR TRACES (up to 5)")
        print(f"{'=' * 80}")

        sampled_errors = random.sample(error_traces, min(5, len(error_traces)))
        for idx, r in enumerate(sampled_errors):
            convos = r["conversations"]
            n_parse = count_parsing_errors(convos)
            malformed_list = get_malformed_assistant_messages(convos)

            print(f"\n{'~' * 100}")
            print(f"ERROR TRACE {idx + 1}")
            print(f"  Task:          {r.get('task', '')}")
            print(f"  Episode:       {r.get('episode', '')}")
            print(f"  Date:          {r.get('date', '')}")
            print(f"  Result:        {r.get('result', '')}")
            print(f"  Num messages:  {len(convos)}")
            print(f"  Parse errors:  {n_parse}")

            roles = [m.get("role", "?") for m in convos]
            print(f"  Roles: {' -> '.join(roles[:20])}{'...' if len(roles) > 20 else ''}")

            for mi, minfo in enumerate(malformed_list[:3]):  # Show up to 3 malformed per trace
                cls = classify_malformation(minfo["content"])
                print(f"\n  --- MALFORMED MSG #{mi+1} (at msg idx {minfo['assistant_idx']}, class: {cls}, len: {len(minfo['content'])}) ---")
                print_indented(minfo["content"], max_len=2000)

                # Also show the error feedback
                print(f"\n  --- ERROR FEEDBACK (at msg idx {minfo['error_idx']}) ---")
                print_indented(minfo["error_content"], max_len=800)

            # Show last assistant message
            last = get_last_assistant_message(convos)
            print(f"\n  --- LAST ASSISTANT MSG (len: {len(last)}) ---")
            print_indented(last, max_len=1500)

        # =====================================================
        # SAMPLED CLEAN TRACES
        # =====================================================
        print(f"\n{'=' * 80}")
        print(f"SAMPLED CLEAN TRACES (up to 3)")
        print(f"{'=' * 80}")

        sampled_ok = random.sample(ok_traces, min(3, len(ok_traces)))
        for idx, r in enumerate(sampled_ok):
            convos = r["conversations"]
            first_asst = get_first_assistant_message(convos)
            last_asst = get_last_assistant_message(convos)

            print(f"\n{'~' * 100}")
            print(f"CLEAN TRACE {idx + 1}")
            print(f"  Task:          {r.get('task', '')}")
            print(f"  Episode:       {r.get('episode', '')}")
            print(f"  Result:        {r.get('result', '')}")
            print(f"  Num messages:  {len(convos)}")

            print(f"\n  --- FIRST ASSISTANT MSG (len: {len(first_asst)}) ---")
            print_indented(first_asst, max_len=1000)

            print(f"\n  --- LAST ASSISTANT MSG (len: {len(last_asst)}) ---")
            print_indented(last_asst, max_len=1000)

        # =====================================================
        # ONE EXAMPLE PER CLASSIFICATION TYPE
        # =====================================================
        print(f"\n{'=' * 80}")
        print(f"ONE EXAMPLE PER CLASSIFICATION TYPE")
        print(f"{'=' * 80}")

        seen_types = set()
        for m in all_malformed:
            cls = m["classification"]
            if cls not in seen_types:
                seen_types.add(cls)
                print(f"\n  --- TYPE: {cls} ---")
                print(f"  Task: {m['task']}, Episode: {m['episode']}, Result: {m['result']}")
                print(f"  Msg position: assistant_idx={m['assistant_idx']}, total_msgs={m['num_messages']}")
                print(f"  Length: {len(m['content'])} chars")
                print(f"  Content:")
                print_indented(m["content"], max_len=1500)
                print(f"  Error feedback:")
                print_indented(m["error_content"], max_len=600)

        # =====================================================
        # SPECIAL: FIRST ASSISTANT MESSAGE ANALYSIS
        # =====================================================
        print(f"\n{'=' * 80}")
        print(f"FIRST ASSISTANT MESSAGE ANALYSIS")
        print(f"{'=' * 80}")

        # Is the FIRST assistant message ever the malformed one?
        first_msg_malformed = 0
        for m in all_malformed:
            if m["assistant_idx"] <= 2:  # First or second message is assistant
                first_msg_malformed += 1
        print(f"Malformed messages at conversation start (idx<=2): {first_msg_malformed}/{total}")

        # Check if first assistant message of error traces is different from clean traces
        error_first_msgs = [get_first_assistant_message(r["conversations"]) for r in error_traces]
        ok_first_msgs = [get_first_assistant_message(r["conversations"]) for r in ok_traces]

        error_first_valid_json = sum(1 for m in error_first_msgs if m.strip().startswith("{") and _try_json(m.strip()))
        ok_first_valid_json = sum(1 for m in ok_first_msgs if m.strip().startswith("{") and _try_json(m.strip()))

        print(f"First assistant msg is valid JSON (error traces): {error_first_valid_json}/{len(error_first_msgs)}")
        print(f"First assistant msg is valid JSON (clean traces): {ok_first_valid_json}/{len(ok_first_msgs)}")


def _try_json(text):
    try:
        json.loads(text)
        return True
    except:
        return False


if __name__ == "__main__":
    main()
