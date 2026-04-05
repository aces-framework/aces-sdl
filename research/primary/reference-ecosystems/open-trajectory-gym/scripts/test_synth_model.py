#!/usr/bin/env python3
"""Test synthetic generation with one or more models across all manifests.

Usage:
  OPENROUTER_API_KEY=... python scripts/test_synth_model.py --model openrouter/stepfun/step-3.5-flash:free
  OPENROUTER_API_KEY=... python scripts/test_synth_model.py --model openrouter/stepfun/step-3.5-flash:free --manifests all
"""

import argparse
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trajgym.synthetic_data_generation.executor import SimulatedEnvironmentExecutor
from trajgym.synthetic_data_generation.generator import LiteLLMAgentAdapter
from trajgym.synthetic_data_generation.manifest import WorldManifest

MANIFEST_DIR = "configs/synthetic_data_generation"
DEFAULT_MANIFEST = os.path.join(MANIFEST_DIR, "default.yaml")
MAX_TURNS = 30


def grade_manifest_adherence(trace: dict, manifest: WorldManifest) -> dict:
    """Grade how well a trajectory adheres to the manifest scenario.

    Returns a dict of scores (0.0-1.0) and notes.
    """
    messages = trace["messages"]
    scores = {}
    notes = []

    # 1. Host Discovery: Did the agent reference manifest hosts?
    host_refs = 0
    total_hosts = len(set(h.hostname for h in manifest.hosts.values()))
    for m in messages:
        content = str(m.get("content", ""))
        for h in manifest.hosts.values():
            if h.ip in content or h.hostname in content:
                host_refs += 1
                break
    scores["host_discovery"] = min(1.0, host_refs / max(1, total_hosts * 2))

    # 2. Service Interaction: Did the agent interact with manifest services?
    service_names = set()
    for h in manifest.hosts.values():
        for s in h.services:
            service_names.add(s.name)
            service_names.add(str(s.port))
    svc_refs = sum(
        1
        for m in messages
        if any(sn in str(m.get("content", "")) for sn in service_names)
    )
    scores["service_interaction"] = min(1.0, svc_refs / max(1, len(service_names) * 2))

    # 3. File Discovery: Did the agent access manifest files?
    files_found = set()
    for m in messages:
        content = str(m.get("content", ""))
        for fpath in manifest.files:
            if fpath in content or os.path.basename(fpath) in content:
                files_found.add(fpath)
    scores["file_discovery"] = len(files_found) / max(1, len(manifest.files))
    if files_found:
        notes.append(f"Files found: {sorted(files_found)}")

    # 4. Credential Usage: Did the agent find and use credentials from files?
    creds_in_files = set()
    for fnode in manifest.files.values():
        for match in re.findall(r"['\"]([^'\"]{4,})['\"]", fnode.content):
            creds_in_files.add(match)
        for match in re.findall(
            r"(?:pass|password|secret|key)\s*[=:]\s*['\"]?(\S{4,})['\"]?",
            fnode.content,
            re.IGNORECASE,
        ):
            creds_in_files.add(match.rstrip("';"))
    creds_used = set()
    for m in messages:
        if m.get("role") in ("assistant",):
            for tc in m.get("tool_calls", []):
                args_str = tc.get("function", {}).get("arguments", "")
                for cred in creds_in_files:
                    if cred in args_str:
                        creds_used.add(cred)
    scores["credential_usage"] = (
        len(creds_used) / max(1, len(creds_in_files)) if creds_in_files else 0.5
    )
    if creds_used:
        notes.append(f"Credentials used: {len(creds_used)}/{len(creds_in_files)}")

    # 5. Flag Capture
    scores["flag_capture"] = 1.0 if trace["metadata"]["success"] else 0.0

    # 6. Reasoning Quality: % of assistant messages with <think> blocks
    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
    think_count = sum(
        1 for m in assistant_msgs if "<think>" in str(m.get("content", ""))
    )
    scores["reasoning"] = think_count / max(1, len(assistant_msgs))

    # 7. Tool Diversity: How many unique tools were used?
    tool_names = set()
    for m in messages:
        if m.get("role") == "assistant":
            for tc in m.get("tool_calls", []):
                tool_names.add(tc["function"]["name"])
    scores["tool_diversity"] = min(1.0, len(tool_names) / 4)  # 4+ tools = perfect

    # 8. Trajectory Length: Prefer 8-30 messages (typical SFT averages)
    n = len(messages)
    if n < 6:
        scores["trajectory_length"] = 0.3
        notes.append(f"Too short ({n} msgs)")
    elif n <= 40:
        scores["trajectory_length"] = 1.0
    else:
        scores["trajectory_length"] = 0.7
        notes.append(f"Long trajectory ({n} msgs)")

    # Overall weighted score
    weights = {
        "flag_capture": 0.30,
        "credential_usage": 0.15,
        "host_discovery": 0.10,
        "service_interaction": 0.10,
        "file_discovery": 0.10,
        "reasoning": 0.10,
        "tool_diversity": 0.08,
        "trajectory_length": 0.07,
    }
    overall = sum(scores[k] * weights[k] for k in weights)
    scores["overall"] = round(overall, 3)

    return {"scores": {k: round(v, 2) for k, v in scores.items()}, "notes": notes}


def run_test(model_id: str, manifest_path: str) -> dict:
    manifest = WorldManifest.from_yaml(manifest_path)
    adapter = LiteLLMAgentAdapter(model_name=model_id)
    executor = SimulatedEnvironmentExecutor(manifest=manifest, max_steps=MAX_TURNS)

    start = time.time()
    trace = adapter.run_episode(executor, executor._current_manifest, MAX_TURNS)
    elapsed = time.time() - start

    messages = trace["messages"]
    meta = trace["metadata"]

    # Analyze
    tool_calls = []
    has_think = False
    for m in messages:
        if m.get("role") == "assistant":
            content = m.get("content", "") or ""
            if "<think>" in content:
                has_think = True
            for tc in m.get("tool_calls", []):
                tool_calls.append(tc["function"]["name"])

    # Check format compliance
    issues = []
    for i, m in enumerate(messages):
        if m.get("role") == "assistant":
            for bad_key in ("reasoning_content", "provider_specific_fields", "index"):
                if bad_key in m:
                    issues.append(f"msg[{i}] has unsanitized field: {bad_key}")
            for tc in m.get("tool_calls", []):
                if "index" in tc:
                    issues.append(f"msg[{i}] tool_call has 'index' field")
                if not tc.get("id"):
                    issues.append(f"msg[{i}] tool_call missing 'id'")
                if tc.get("type") != "function":
                    issues.append(f"msg[{i}] tool_call type={tc.get('type')}")

    # Grade manifest adherence
    adherence = grade_manifest_adherence(trace, manifest)

    result = {
        "model": model_id,
        "manifest": os.path.basename(manifest_path),
        "challenge": manifest.name,
        "success": meta["success"],
        "total_turns": meta["total_turns"],
        "elapsed_sec": round(elapsed, 1),
        "message_count": len(messages),
        "tool_call_count": len(tool_calls),
        "unique_tools": sorted(set(tool_calls)),
        "has_think_blocks": has_think,
        "has_flag_found": "flag_found" in tool_calls or "submit_flag" in tool_calls,
        "format_issues": issues,
        "adherence": adherence,
        "ground_truth_flag": trace["ground_truth_flag"],
    }

    # Save full trace
    safe_model = model_id.replace("/", "_").replace(":", "_")
    safe_manifest = os.path.splitext(os.path.basename(manifest_path))[0]
    out_path = f"data/synth_test_{safe_model}_{safe_manifest}.jsonl"
    os.makedirs("data", exist_ok=True)
    with open(out_path, "w") as f:
        f.write(json.dumps(trace, default=str) + "\n")
    result["trace_path"] = out_path

    return result


def print_report(result: dict):
    print("=" * 70)
    print(f"MODEL: {result['model']}  |  CHALLENGE: {result['challenge']}")
    print("=" * 70)
    print(f"  Success:          {result['success']}")
    print(f"  Turns:            {result['total_turns']}")
    print(f"  Time:             {result['elapsed_sec']}s")
    print(f"  Messages:         {result['message_count']}")
    print(f"  Tool calls:       {result['tool_call_count']}")
    print(f"  Unique tools:     {result['unique_tools']}")
    print(f"  <think> blocks:   {result['has_think_blocks']}")
    print(f"  flag_found:       {result['has_flag_found']}")
    print(f"  Format issues:    {len(result['format_issues'])}")
    for issue in result["format_issues"][:5]:
        print(f"    - {issue}")

    adh = result["adherence"]
    print(f"\n  --- Manifest Adherence (overall: {adh['scores']['overall']}) ---")
    for k, v in sorted(adh["scores"].items()):
        if k != "overall":
            bar = "#" * int(v * 20) + "." * (20 - int(v * 20))
            print(f"    {k:<22} [{bar}] {v:.2f}")
    for note in adh["notes"]:
        print(f"    * {note}")

    print(f"\n  Trace saved:      {result['trace_path']}")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--manifests",
        default="default",
        help="'default', 'all', or comma-separated YAML filenames",
    )
    args = parser.parse_args()

    # Resolve manifest paths
    if args.manifests == "all":
        manifest_paths = sorted(glob.glob(os.path.join(MANIFEST_DIR, "*.yaml")))
    elif args.manifests == "default":
        manifest_paths = [DEFAULT_MANIFEST]
    else:
        manifest_paths = [
            os.path.join(MANIFEST_DIR, m.strip()) for m in args.manifests.split(",")
        ]

    results = []
    for mp in manifest_paths:
        if not os.path.exists(mp):
            print(f"SKIP: {mp} not found")
            continue
        print(f"\n>>> Running {args.model} on {os.path.basename(mp)} ...")
        try:
            result = run_test(args.model, mp)
            results.append(result)
            print_report(result)
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback

            traceback.print_exc()

    if len(results) > 1:
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        total_success = sum(1 for r in results if r["success"])
        avg_adherence = sum(r["adherence"]["scores"]["overall"] for r in results) / len(
            results
        )
        avg_tools = sum(r["tool_call_count"] for r in results) / len(results)
        avg_turns = sum(r["total_turns"] for r in results) / len(results)
        print(f"  Model:            {args.model}")
        print(f"  Challenges:       {len(results)}")
        print(f"  Successes:        {total_success}/{len(results)}")
        print(f"  Avg adherence:    {avg_adherence:.3f}")
        print(f"  Avg tool calls:   {avg_tools:.1f}")
        print(f"  Avg turns:        {avg_turns:.1f}")
        for r in results:
            status = "OK" if r["success"] else "FAIL"
            print(
                f"    [{status}] {r['challenge']:<40} adherence={r['adherence']['scores']['overall']:.3f}  tools={r['tool_call_count']}  turns={r['total_turns']}"
            )

    # Dump JSON
    print("\n--- JSON ---")
    print(
        json.dumps(
            results if len(results) > 1 else results[0] if results else {},
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
