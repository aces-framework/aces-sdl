#!/usr/bin/env python3
"""Generate a readiness report for online RL data + target mapping."""

from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml


def _load_registry(path: Path) -> dict[str, dict]:
    doc = yaml.safe_load(path.read_text())
    challenges = doc.get("challenges", []) if isinstance(doc, dict) else []
    return {c.get("id"): c for c in challenges if isinstance(c, dict) and c.get("id")}


def _load_target_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []

    payload = json.loads(path.read_text())
    if isinstance(payload, dict):
        if isinstance(payload.get("challenges"), list):
            return [r for r in payload["challenges"] if isinstance(r, dict)]
        if isinstance(payload.get("challenge_targets"), dict):
            return [
                {"id": k, "target_url": v}
                for k, v in payload["challenge_targets"].items()
            ]
        return [
            {"id": k, "target_url": v if isinstance(v, str) else v.get("target_url")}
            for k, v in payload.items()
            if isinstance(v, (str, dict))
        ]
    if isinstance(payload, list):
        rows = []
        for row in payload:
            if isinstance(row, dict):
                rows.append(row)
            elif isinstance(row, str):
                rows.append({"id": row, "target_url": row})
        return rows
    return []


def _probe_target(target: str, timeout_secs: float = 1.5) -> tuple[bool, str]:
    text = str(target or "").strip()
    if not text:
        return False, "empty target"
    if text.startswith("file://"):
        return True, "file_target"
    if text.startswith(("http://", "https://")):
        parsed = urlparse(text)
        host = parsed.hostname
        if not host:
            return False, f"invalid target: {text}"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        conn_cls = (
            http.client.HTTPSConnection
            if parsed.scheme == "https"
            else http.client.HTTPConnection
        )
        conn = conn_cls(host=host, port=port, timeout=timeout_secs)
        try:
            conn.request("GET", path, headers={"User-Agent": "trajgym-readiness/1.0"})
            resp = conn.getresponse()
            return True, f"http_status_{resp.status}"
        except Exception as e:  # pragma: no cover - diagnostics path
            return False, str(e)
        finally:
            with contextlib.suppress(Exception):
                conn.close()

    host = text
    port = 80
    if "/" in host:
        host = host.split("/", 1)[0]
    if ":" in host:
        host, ps = host.rsplit(":", 1)
        try:
            port = int(ps)
        except Exception:
            port = 80

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout_secs)
    try:
        s.connect((host, port))
        return True, ""
    except Exception as e:  # pragma: no cover - diagnostics path
        return False, str(e)
    finally:
        s.close()


def _extract_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for p in content:
            if isinstance(p, dict):
                if isinstance(p.get("text"), str):
                    parts.append(p["text"])
                elif isinstance(p.get("content"), str):
                    parts.append(p["content"])
        return "\n".join(parts)
    if isinstance(content, dict):
        if isinstance(content.get("content"), str):
            return content["content"]
        if isinstance(content.get("text"), str):
            return content["text"]
    return ""


def _audit_dataset(path: Path, registry: dict[str, dict]) -> dict:
    stats = {
        "path": str(path),
        "samples": 0,
        "unique_challenges": 0,
        "dataset_challenges_not_in_registry": 0,
        "registry_challenges_missing_from_dataset": 0,
        "missing_ground_truth_flag": 0,
        "bad_system_prompt": 0,
        "system_urls_found": 0,
        "samples_with_challenge_id": 0,
        "compared_registry_flag_count": 0,
        "registry_flag_match": 0,
        "registry_flag_mismatch": 0,
    }
    if not path.exists():
        return stats

    registry_ids = set(registry)
    ids: list[str] = []

    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            stats["samples"] += 1
            md = obj.get("metadata") or {}
            cid = (
                md.get("challenge_id")
                or md.get("challenge")
                or obj.get("challenge_id")
                or obj.get("challenge")
            )
            if cid:
                ids.append(cid)
                stats["samples_with_challenge_id"] += 1

            gtf = obj.get("ground_truth_flag")
            if not gtf:
                stats["missing_ground_truth_flag"] += 1

            msgs = obj.get("messages") or []
            sys_txt = ""
            if isinstance(msgs, list):
                for m in msgs:
                    if isinstance(m, dict) and m.get("role") == "system":
                        sys_txt += "\n" + _extract_text(m.get("content", ""))

            if sys_txt:
                if not (
                    ("expert penetration tester" in sys_txt.lower())
                    or ("ctf challenge" in sys_txt.lower())
                    or ("available tools" in sys_txt.lower())
                ):
                    stats["bad_system_prompt"] += 1
                stats["system_urls_found"] += len(
                    re.findall(r"https?://[^\s\)\]]+", sys_txt)
                )

            if cid in registry and registry[cid].get("ground_truth_flag") and gtf:
                stats["compared_registry_flag_count"] += 1
                if str(gtf).strip() == str(registry[cid]["ground_truth_flag"]).strip():
                    stats["registry_flag_match"] += 1
                else:
                    stats["registry_flag_mismatch"] += 1

    idset = set(ids)
    stats["unique_challenges"] = len(idset)
    stats["dataset_challenges_not_in_registry"] = len(idset - registry_ids)
    stats["registry_challenges_missing_from_dataset"] = len(registry_ids - idset)
    stats["missing_registry_challenge_ids"] = sorted(list(registry_ids - idset))[:20]
    stats["extra_dataset_challenge_ids"] = sorted(list(idset - registry_ids))[:20]
    return stats


def _pick_existing(*candidates: Path) -> Path:
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write online RL readiness report JSON."
    )
    parser.add_argument("--run-root", required=True)
    parser.add_argument(
        "--registry",
        default="configs/challenges/cybench.yaml",
    )
    parser.add_argument(
        "--target-map",
        default="configs/challenges/cybench_target_map_runpod.json",
    )
    parser.add_argument(
        "--online-rl-data",
        default="data/online_rl.jsonl",
        help="Path to online RL JSONL dataset",
    )
    args = parser.parse_args()

    run_root = Path(args.run_root)
    registry = _load_registry(Path(args.registry))
    rows = _load_target_rows(Path(args.target_map))

    reach_ok: list[tuple[str, str]] = []
    reach_bad: list[tuple[str, str, str]] = []
    for row in rows:
        cid = row.get("id") or row.get("challenge") or row.get("challenge_id") or ""
        target = row.get("target_url") or row.get("target") or row.get("url") or ""
        if not target:
            reach_bad.append((str(cid), "", "missing target_url"))
            continue
        ok, reason = _probe_target(target)
        if ok:
            reach_ok.append((str(cid), str(target)))
        else:
            reach_bad.append((str(cid), str(target), reason))

    online_rl = Path(args.online_rl_data)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline_run_root": str(run_root),
        "registry_challenge_count": len(registry),
        "registry_with_ground_truth_flag": sum(
            1 for c in registry.values() if c.get("ground_truth_flag")
        ),
        "target_map_file": str(args.target_map),
        "target_map_entries": len(rows),
        "target_map_reachable": len(reach_ok),
        "target_map_unreachable": len(reach_bad),
        "datasets": {
            "online_rl": _audit_dataset(online_rl, registry),
        },
        "unreachable_targets_sample": reach_bad[:10],
    }

    out = run_root / "online_rl_readiness_report_v2.json"
    out.write_text(json.dumps(report, indent=2))
    print(out)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
