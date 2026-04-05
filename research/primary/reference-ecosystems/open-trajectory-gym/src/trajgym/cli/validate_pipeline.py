#!/usr/bin/env python3
"""Pipeline validation for Open Trajectory Gym.

Validates data format, reward functions, training scripts, tool registry,
model formatters, and reference projects WITHOUT requiring GPU or model weights.

Usage:
    trajgym-validate
    trajgym-validate --mode online-rl-preflight
"""

import argparse
import contextlib
import hashlib
import http.client
import json
import py_compile
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _ok(msg):
    print(f"  {GREEN}+{RESET} {msg}")


def _fail(msg, errors):
    print(f"  {RED}x{RESET} {msg}")
    errors.append(msg)


def _warn(msg, warnings):
    print(f"  {YELLOW}?{RESET} {msg}")
    warnings.append(msg)


def _section(msg):
    print(f"\n{BOLD}{'_'*60}\n  {msg}\n{'_'*60}{RESET}")


def _probe_target_url(target: str, timeout: float = 1.5) -> tuple[bool, str]:
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
        conn = conn_cls(host=host, port=port, timeout=timeout)
        try:
            conn.request("GET", path, headers={"User-Agent": "trajgym-preflight/1.0"})
            resp = conn.getresponse()
            return True, f"http_status_{resp.status}"
        except Exception as exc:
            return False, str(exc)
        finally:
            with contextlib.suppress(Exception):
                conn.close()

    host = text
    port = 80
    if "/" in host:
        host = host.split("/", 1)[0]
    if ":" in host:
        h, p = host.rsplit(":", 1)
        host = h
        try:
            port = int(p)
        except ValueError:
            port = 80
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True, ""
    except Exception as exc:
        return False, str(exc)
    finally:
        sock.close()


def _compile_python_file(label: str, path: Path, errors: list[str]) -> None:
    if not path.exists():
        _fail(f"{label}: Not found", errors)
        return
    try:
        py_compile.compile(str(path), doraise=True)
        _ok(f"{label}: Syntax OK ({path.stat().st_size} bytes)")
    except py_compile.PyCompileError as exc:
        _fail(f"{label}: Syntax error -> {exc}", errors)
    except PermissionError:
        # __pycache__ may be owned by root from Docker runs.
        _ok(f"{label}: Exists ({path.stat().st_size} bytes, pyc write skipped)")


def _compile_first_existing(
    label: str,
    paths: list[Path],
    errors: list[str],
) -> None:
    """Compile the first existing path from candidates.

    Supports repos that still use legacy module layout.
    """
    for path in paths:
        if path.exists():
            _compile_python_file(label, path, errors)
            return
    _fail(f"{label}: Not found", errors)


def _safe_load_yaml(path: Path, warnings: list[str], label: str) -> dict | None:
    try:
        import yaml
    except ImportError:
        _warn(f"PyYAML not installed; skipping {label} checks", warnings)
        return None
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _first_existing_path(*candidates: Path) -> Path:
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_challenge_id(sample: dict) -> str | None:
    metadata = sample.get("metadata") if isinstance(sample, dict) else None
    if isinstance(metadata, dict):
        cid = metadata.get("challenge_id") or metadata.get("challenge")
        if cid:
            return str(cid)
    for key in ("challenge_id", "challenge"):
        if isinstance(sample, dict) and sample.get(key):
            return str(sample[key])
    return None


def _load_target_map_rows(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        if isinstance(payload.get("challenges"), list):
            return [r for r in payload["challenges"] if isinstance(r, dict)]
        if isinstance(payload.get("challenge_targets"), dict):
            return [
                {"id": k, "target_url": v}
                for k, v in payload["challenge_targets"].items()
            ]
        rows = []
        for k, v in payload.items():
            if isinstance(v, dict):
                row = dict(v)
                row.setdefault("id", k)
                rows.append(row)
            elif isinstance(v, str):
                rows.append({"id": k, "target_url": v})
        return rows
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    return []


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Open Trajectory Gym pipeline health."
    )
    parser.add_argument(
        "--mode",
        choices=["basic", "online-rl-preflight"],
        default="basic",
        help="Validation mode. online-rl-preflight adds dependency + target reachability checks.",
    )
    parser.add_argument(
        "--online-rl-data",
        default=None,
        help=(
            "Path to online RL JSONL for preflight "
            "(default: data/online_rl.jsonl)"
        ),
    )
    parser.add_argument(
        "--challenge-registry",
        default=None,
        help="Path to challenge registry YAML (default: configs/challenges/cybench.yaml)",
    )
    parser.add_argument(
        "--target-map",
        default=None,
        help="Optional challenge target map JSON for connectivity checks.",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host override used for challenge registry target resolution checks.",
    )
    parser.add_argument(
        "--data-manifest",
        default=None,
        help=(
            "Optional path to dataset manifest JSON "
            "(default: <online-rl-data>.manifest.json)"
        ),
    )
    parser.add_argument(
        "--require-manifest",
        action="store_true",
        help="Fail preflight if dataset manifest is missing.",
    )
    parser.add_argument(
        "--require-target-map-coverage",
        action="store_true",
        help=(
            "Fail preflight if challenge IDs in --target-map are not all present in dataset."
        ),
    )
    args = parser.parse_args()

    errors = []
    warnings = []

    # Resolve paths: cli/ -> trajgym/ -> src/ -> project root
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
    SRC_DIR = PROJECT_ROOT / "src"
    DATA_DIR = PROJECT_ROOT / "data"

    # -------------------------------------------------------------------
    # 1. Data files
    # -------------------------------------------------------------------
    _section("1. DATA FILES")

    data_checks = [
        (
            "SFT",
            _first_existing_path(
                DATA_DIR / "sft_quality.jsonl", DATA_DIR / "sft.jsonl"
            ),
        ),
        (
            "ONLINE RL",
            DATA_DIR / "online_rl.jsonl",
        ),
    ]

    for label, fpath in data_checks:
        if not fpath.exists():
            _warn(
                f"{label}: Not found at {fpath.name} (run trajgym-convert + trajgym-split)",
                warnings,
            )
            continue

        with open(fpath) as f:
            lines = f.readlines()
        count = len(lines)

        if count == 0:
            _fail(f"{label}: Empty file", errors)
            continue

        _ok(f"{label}: {count} samples at {fpath.name}")

        # Validate format of first 5 lines
        format_errors = 0
        for i, line in enumerate(lines[:5]):
            try:
                obj = json.loads(line)
                msgs = obj.get("messages")
                if not msgs or not isinstance(msgs, list):
                    format_errors += 1
                    continue
                roles = {m.get("role") for m in msgs}
                if "assistant" not in roles:
                    _warn(f"{label} line {i}: Missing assistant role", warnings)
            except json.JSONDecodeError:
                format_errors += 1

        if format_errors > 0:
            _fail(f"{label}: {format_errors}/5 lines have invalid JSON", errors)
        else:
            _ok(f"{label}: Format validated (first 5 lines)")

        # Check for ground_truth_flag in Online RL data
        if "online rl" in label.lower():
            try:
                first = json.loads(lines[0])
                if "ground_truth_flag" in first:
                    _ok(f"{label}: ground_truth_flag field present")
                else:
                    _warn(f"{label}: Missing ground_truth_flag field", warnings)
            except json.JSONDecodeError:
                pass

    # -------------------------------------------------------------------
    # 2. Reward function
    # -------------------------------------------------------------------
    _section("2. REWARD FUNCTION")

    try:
        from trajgym.rewards.reward import Reward

        _ok("Reward imported successfully")

        reward = Reward()
        _ok(
            f"Reward instantiated (weights: flag={reward.flag_weight}, "
            f"uniqueness={reward.uniqueness_weight}, efficiency={reward.efficiency_weight}, "
            f"format={reward.format_weight})"
        )

        mock_completions = [
            [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "shell_command",
                                "arguments": '{"command": "nmap 10.10.10.1"}',
                            }
                        }
                    ],
                },
                {"role": "tool", "content": "80/tcp open"},
                {
                    "role": "assistant",
                    "content": "FLAG{test_flag_12345}",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "flag_found",
                                "arguments": '{"content": "FLAG{test_flag_12345}"}',
                            }
                        }
                    ],
                },
            ],
            "I cannot help with that request.",
        ]

        rewards = reward(
            completions=mock_completions,
            ground_truth_flag=["FLAG{test_flag_12345}", None],
            optimal_steps=[3, None],
            metadata=[{"success": True}, {"success": False}],
        )

        if len(rewards) == 2:
            _ok(f"Reward batch scoring works: [{rewards[0]:.3f}, {rewards[1]:.3f}]")
        else:
            _fail(f"Expected 2 rewards, got {len(rewards)}", errors)

        if rewards[0] > rewards[1]:
            _ok(
                f"Success reward ({rewards[0]:.3f}) > failure reward ({rewards[1]:.3f})"
            )
        else:
            _fail("Success reward should exceed failure reward", errors)

    except ImportError as e:
        _fail(f"Reward import failed: {e}", errors)
    except Exception as e:
        _fail(f"Reward test failed: {e}", errors)

    # -------------------------------------------------------------------
    # 3. Training scripts
    # -------------------------------------------------------------------
    _section("3. TRAINING SCRIPTS")

    _compile_first_existing(
        "src/trajgym/cli/train.py",
        [SRC_DIR / "trajgym" / "cli" / "train.py"],
        errors,
    )
    _compile_first_existing(
        "src/trajgym/training/sft/trl.py",
        [
            SRC_DIR / "trajgym" / "training" / "sft" / "trl.py",
            SRC_DIR / "trajgym" / "training" / "sft_trl.py",
        ],
        errors,
    )
    _compile_first_existing(
        "src/trajgym/training/online_rl/runtime.py",
        [
            SRC_DIR / "trajgym" / "training" / "online_rl" / "runtime.py",
        ],
        errors,
    )

    config_file = PROJECT_ROOT / "examples" / "qwen35-27b" / "training.yaml"
    if config_file.exists():
        cfg = _safe_load_yaml(config_file, warnings, "training.yaml")
        if cfg is not None:
            required_sections = ["model", "lora", "sft", "output"]
            for s in required_sections:
                if s in cfg:
                    _ok(f"training.yaml: '{s}' section present")
                else:
                    _fail(f"training.yaml: Missing '{s}' section", errors)

            online_rl = cfg.get("online_rl")
            if isinstance(online_rl, dict):
                _ok("training.yaml: 'online_rl' section present")
            else:
                _fail("training.yaml: Missing 'online_rl' section", errors)
                online_rl = {}

            if online_rl.get("beta", 1.0) <= 0.01:
                _ok(f"Online RL beta={online_rl['beta']} (correctly low)")
            else:
                _warn(
                    f"Online RL beta={online_rl.get('beta', 'missing')} (should be <= 0.01)",
                    warnings,
                )

            policy_loss_type = str(online_rl.get("policy_loss_type", "") or "").strip()
            legacy_loss_type = str(online_rl.get("loss_type", "") or "").strip()
            if policy_loss_type:
                _ok(f"Online RL policy_loss_type={policy_loss_type}")
            elif legacy_loss_type:
                _ok(
                    "Online RL legacy loss_type is set "
                    f"({legacy_loss_type}); runtime alias mapping will apply"
                )
            else:
                _warn(
                    "Online RL loss config missing (set online_rl.policy_loss_type, "
                    "or legacy online_rl.loss_type)",
                    warnings,
                )
    else:
        _fail("training.yaml: Not found", errors)

    # -------------------------------------------------------------------
    # 4. Tool registry
    # -------------------------------------------------------------------
    _section("4. TOOL REGISTRY")

    try:
        from trajgym.formatters.tool_registry import AGENT_TOOLS

        _ok(f"AGENT_TOOLS imported: {len(AGENT_TOOLS)} tools")

        tool_names = {t["function"]["name"] for t in AGENT_TOOLS}
        required_tools = ["shell_command", "exec_command", "write_stdin", "flag_found"]
        for tool in required_tools:
            if tool in tool_names:
                _ok(f"  Tool '{tool}' present")
            else:
                _fail(f"  Tool '{tool}' missing from registry", errors)
    except ImportError as e:
        _fail(f"Tool registry import failed: {e}", errors)
    except Exception as e:
        _fail(f"Tool registry validation failed: {e}", errors)

    # -------------------------------------------------------------------
    # 5. Model formatters
    # -------------------------------------------------------------------
    _section("5. MODEL FORMATTERS")

    formatters_dir = SRC_DIR / "trajgym" / "formatters"
    if formatters_dir.exists():
        formatter_files = list(formatters_dir.glob("*.py"))
        _ok(f"Formatters directory: {len(formatter_files)} files")

        try:
            from trajgym.formatters import get_formatter

            test_models = [
                ("Qwen/Qwen3-8B", "Qwen3Formatter"),
                ("THUDM/glm-4-9b", "GLM4Formatter"),
                ("mistralai/Devstral-Small-2", "DevstralFormatter"),
            ]
            for model_id, expected_cls in test_models:
                f = get_formatter(model_id)
                cls_name = type(f).__name__
                if cls_name == expected_cls:
                    _ok(f"  {model_id} -> {cls_name}")
                else:
                    _fail(
                        f"  {model_id} -> {cls_name} (expected {expected_cls})", errors
                    )
        except ImportError as e:
            _warn(f"Formatters import failed: {e}", warnings)
        except Exception as e:
            _warn(f"Formatters validation failed: {e}", warnings)
    else:
        _warn("Formatters directory not found", warnings)

    # -------------------------------------------------------------------
    # 6. BoxPwnr reference
    # -------------------------------------------------------------------
    _section("6. BOXPWNR REFERENCE")

    try:
        from trajgym.integrations.boxpwnr_runner import (
            _default_boxpwnr_source_candidates,
        )

        candidates = _default_boxpwnr_source_candidates()
        existing = [p for p in candidates if p.exists()]
        if existing:
            for src in existing:
                git_dir = src.parent / ".git"
                if git_dir.exists():
                    _ok(f"BoxPwnr source candidate: {src} (git repo)")
                else:
                    _ok(f"BoxPwnr source candidate: {src}")

                tools_file = src / "boxpwnr" / "tools" / "tools.py"
                if tools_file.exists():
                    _ok(f"BoxPwnr tools.py: Found ({tools_file.stat().st_size} bytes)")
                else:
                    _warn(f"BoxPwnr tools.py not found under {src}", warnings)
        else:
            _warn(
                "No local BoxPwnr source candidates found. "
                "Install `boxpwnr` in env or set TRAJGYM_BOXPWNR_SRC.",
                warnings,
            )
    except Exception as e:
        _warn(f"BoxPwnr source candidate validation failed: {e}", warnings)

    # -------------------------------------------------------------------
    # 7. Evaluation harness
    # -------------------------------------------------------------------
    _section("7. EVALUATION HARNESS")

    eval_files = {
        "src/trajgym/eval/evaluator.py": SRC_DIR / "trajgym" / "eval" / "evaluator.py",
        "src/trajgym/cli/evaluate.py": SRC_DIR / "trajgym" / "cli" / "evaluate.py",
    }

    for label, fpath in eval_files.items():
        _compile_python_file(label, fpath, errors)

    challenges_file = PROJECT_ROOT / "configs" / "challenges" / "eval_default.yaml"
    if challenges_file.exists():
        data = _safe_load_yaml(challenges_file, warnings, "challenges.yaml")
        if data is not None:
            challenges = data.get("challenges", [])
            if challenges:
                _ok(f"challenges.yaml: {len(challenges)} challenges defined")
            else:
                _warn("challenges.yaml: No challenges defined", warnings)
    else:
        _warn("challenges.yaml: Not found", warnings)

    # -------------------------------------------------------------------
    # 8. Agent runner
    # -------------------------------------------------------------------
    _section("8. AGENT RUNNER")

    runner_file = SRC_DIR / "trajgym" / "integrations" / "boxpwnr_runner.py"
    if runner_file.exists():
        _compile_python_file("integrations/boxpwnr_runner.py", runner_file, errors)

        try:
            from trajgym.integrations.boxpwnr_runner import AgentRunner  # noqa: F401

            _ok("AgentRunner imported successfully")
        except ImportError as e:
            _warn(f"AgentRunner import failed (may need BoxPwnr): {e}", warnings)
    else:
        _warn("integrations/boxpwnr_runner.py: Not found", warnings)

    # -------------------------------------------------------------------
    # 9. ONLINE RL preflight (optional)
    # -------------------------------------------------------------------
    if args.mode == "online-rl-preflight":
        _section("9. ONLINE RL PREFLIGHT")

        # Fast runtime dependency checks for Qwen3.5 linear attention path.
        try:
            import importlib.util

            for dep in ("fla", "causal_conv1d"):
                if importlib.util.find_spec(dep):
                    _ok(f"Dependency '{dep}': importable")
                else:
                    _fail(f"Dependency '{dep}': missing", errors)
        except Exception as exc:
            _warn(f"Dependency probe failed: {exc}", warnings)

        # Guard against known SkyRL step-wise crash:
        # per_token_reward[resp_end_idx] out-of-range writes.
        try:
            import importlib.util

            skyrl_spec = importlib.util.find_spec(
                "skyrl_train.generators.skyrl_gym_generator"
            )
            skyrl_origin = getattr(skyrl_spec, "origin", None) if skyrl_spec else None
            if skyrl_origin:
                from trajgym.training.online_rl.runtime import (
                    _has_step_wise_resp_index_guard,
                )

                source = Path(skyrl_origin).read_text()
                if _has_step_wise_resp_index_guard(source):
                    _ok("SkyRL step-wise index guard: present")
                else:
                    _fail(
                        "SkyRL step-wise index guard missing (run docker/patches/apply_all_patches.sh)",
                        errors,
                    )
            else:
                _warn(
                    "SkyRL generator module not found; skipping step-wise index-guard check",
                    warnings,
                )
        except Exception as exc:
            _warn(f"SkyRL step-wise index-guard probe failed: {exc}", warnings)

        online_rl_data = (
            Path(args.online_rl_data)
            if args.online_rl_data
            else DATA_DIR / "online_rl.jsonl"
        )
        if online_rl_data.exists():
            try:
                with open(online_rl_data) as f:
                    sample_count = sum(1 for line in f if line.strip())
                if sample_count > 0:
                    _ok(f"Online RL data: {sample_count} samples ({online_rl_data})")
                else:
                    _fail(f"Online RL data is empty: {online_rl_data}", errors)
            except Exception as exc:
                _fail(f"Failed to read online RL data {online_rl_data}: {exc}", errors)
        else:
            _fail(f"Online RL data not found: {online_rl_data}", errors)

        if args.challenge_registry:
            registry_path = Path(args.challenge_registry)
        else:
            candidates = [
                PROJECT_ROOT / "configs" / "challenges" / "cybench.yaml",
                PROJECT_ROOT / "configs" / "challenges" / "eval_default.yaml",
            ]
            registry_path = next((p for p in candidates if p.exists()), candidates[0])
        if registry_path.exists():
            _ok(f"Challenge registry found: {registry_path}")
        else:
            _fail(f"Challenge registry missing: {registry_path}", errors)

        registry_ids: set[str] = set()
        registry_flags: dict[str, str] = {}
        if registry_path.exists():
            registry_doc = _safe_load_yaml(
                registry_path, warnings, "challenge registry"
            )
            if isinstance(registry_doc, dict):
                challenge_rows = registry_doc.get("challenges", [])
                if isinstance(challenge_rows, list):
                    for row in challenge_rows:
                        if not isinstance(row, dict):
                            continue
                        cid = row.get("id")
                        if not cid:
                            continue
                        key = str(cid)
                        registry_ids.add(key)
                        registry_flags[key] = str(
                            row.get("ground_truth_flag") or ""
                        ).strip()
                else:
                    _warn(
                        "Challenge registry has no 'challenges' list; skipping sync checks",
                        warnings,
                    )

        dataset_ids: set[str] = set()
        dataset_missing_challenge_id = 0
        dataset_flag_mismatch = 0
        dataset_missing_registry_flag = 0
        dataset_provenance_registry_hashes: set[str] = set()
        dataset_provenance_target_map_hashes: set[str] = set()
        if online_rl_data.exists():
            try:
                with open(online_rl_data) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            sample = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        cid = _extract_challenge_id(sample)
                        if not cid:
                            dataset_missing_challenge_id += 1
                            continue
                        dataset_ids.add(cid)
                        sample_flag = str(sample.get("ground_truth_flag") or "").strip()
                        registry_flag = registry_flags.get(cid, "").strip()
                        if cid in registry_flags:
                            if not registry_flag:
                                dataset_missing_registry_flag += 1
                            elif sample_flag and sample_flag != registry_flag:
                                dataset_flag_mismatch += 1
                        metadata = sample.get("metadata")
                        if isinstance(metadata, dict):
                            src_reg = metadata.get("source_registry_sha256")
                            src_tmap = metadata.get("source_target_map_sha256")
                            if isinstance(src_reg, str) and src_reg.strip():
                                dataset_provenance_registry_hashes.add(src_reg.strip())
                            if isinstance(src_tmap, str) and src_tmap.strip():
                                dataset_provenance_target_map_hashes.add(
                                    src_tmap.strip()
                                )
            except Exception as exc:
                _warn(
                    f"Could not parse online RL dataset for registry sync checks: {exc}",
                    warnings,
                )

        if registry_ids:
            unknown_ids = sorted(dataset_ids - registry_ids)
            if unknown_ids:
                _fail(
                    f"Dataset has {len(unknown_ids)} challenge IDs not in registry "
                    f"(sample: {unknown_ids[:10]})",
                    errors,
                )
            else:
                _ok("Dataset challenge IDs all resolve to registry entries")

        if dataset_missing_challenge_id:
            _warn(
                f"Dataset rows missing challenge_id/challenge: {dataset_missing_challenge_id}",
                warnings,
            )

        if dataset_missing_registry_flag:
            _fail(
                f"Registry missing ground_truth_flag for {dataset_missing_registry_flag} dataset rows",
                errors,
            )

        if dataset_flag_mismatch:
            _fail(
                f"Dataset ground_truth_flag mismatched registry on {dataset_flag_mismatch} rows",
                errors,
            )
        elif dataset_ids and registry_ids:
            _ok("Dataset ground_truth_flag values match registry")

        manifest_path = (
            Path(args.data_manifest)
            if args.data_manifest
            else Path(f"{online_rl_data}.manifest.json")
        )
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
                source = (
                    manifest.get("source", {}) if isinstance(manifest, dict) else {}
                )
                manifest_registry_hash = source.get("registry_sha256")
                current_registry_hash = _sha256_path(registry_path)
                if (
                    isinstance(manifest_registry_hash, str)
                    and current_registry_hash
                    and manifest_registry_hash != current_registry_hash
                ):
                    _fail(
                        "Manifest registry SHA256 does not match current registry file "
                        f"({manifest_path})",
                        errors,
                    )
                elif current_registry_hash:
                    _ok("Manifest registry SHA256 matches current registry")

                if dataset_provenance_registry_hashes:
                    if current_registry_hash in dataset_provenance_registry_hashes:
                        _ok(
                            "Dataset row provenance registry SHA256 matches current registry"
                        )
                    else:
                        _fail(
                            "Dataset row provenance registry SHA256 does not match current registry",
                            errors,
                        )

                declared_ids = manifest.get("challenge_ids")
                if isinstance(declared_ids, list):
                    declared_set = {str(cid) for cid in declared_ids}
                    if declared_set != dataset_ids:
                        _fail(
                            "Manifest challenge_ids do not match dataset challenge IDs "
                            f"(manifest={len(declared_set)} dataset={len(dataset_ids)})",
                            errors,
                        )
                    else:
                        _ok("Manifest challenge_ids match dataset challenge IDs")
            except Exception as exc:
                _fail(f"Failed to parse data manifest {manifest_path}: {exc}", errors)
        elif args.require_manifest:
            _fail(f"Required data manifest not found: {manifest_path}", errors)
        else:
            _warn(f"Data manifest not found: {manifest_path}", warnings)

        target_map_path = Path(args.target_map) if args.target_map else None
        if target_map_path and target_map_path.exists():
            try:
                payload = json.loads(target_map_path.read_text())
                rows = _load_target_map_rows(payload)
                ok_count = 0
                bad_count = 0
                map_ids: set[str] = {
                    str(
                        row.get("id") or row.get("challenge_id") or row.get("challenge")
                    )
                    for row in rows
                    if (
                        row.get("id") or row.get("challenge_id") or row.get("challenge")
                    )
                }
                for row in rows[:40]:
                    target = (
                        row.get("target_url") or row.get("target") or row.get("url")
                    )
                    if not target:
                        bad_count += 1
                        continue
                    ok, _ = _probe_target_url(str(target))
                    if ok:
                        ok_count += 1
                    else:
                        bad_count += 1
                if bad_count == 0:
                    _ok(f"Target map probe: {ok_count}/{len(rows[:40])} reachable")
                else:
                    _warn(
                        f"Target map probe: {ok_count} reachable, {bad_count} unreachable (sampled {len(rows[:40])})",
                        warnings,
                    )

                if args.require_target_map_coverage and map_ids:
                    missing = sorted(map_ids - dataset_ids)
                    if missing:
                        _fail(
                            f"Dataset missing {len(missing)} challenge IDs present in target map "
                            f"(sample: {missing[:10]})",
                            errors,
                        )
                    else:
                        _ok("Dataset covers all challenge IDs from target map")

                if dataset_provenance_target_map_hashes:
                    current_target_map_hash = _sha256_path(target_map_path)
                    if (
                        current_target_map_hash
                        and current_target_map_hash
                        in dataset_provenance_target_map_hashes
                    ):
                        _ok(
                            "Dataset row provenance target-map SHA256 matches current target map"
                        )
                    else:
                        _fail(
                            "Dataset row provenance target-map SHA256 does not match current target map",
                            errors,
                        )

                if manifest_path.exists():
                    try:
                        manifest = json.loads(manifest_path.read_text())
                        source = (
                            manifest.get("source", {})
                            if isinstance(manifest, dict)
                            else {}
                        )
                        manifest_target_map_hash = source.get("target_map_sha256")
                        current_target_map_hash = _sha256_path(target_map_path)
                        if (
                            isinstance(manifest_target_map_hash, str)
                            and current_target_map_hash
                            and manifest_target_map_hash != current_target_map_hash
                        ):
                            _fail(
                                "Manifest target-map SHA256 does not match current target map "
                                f"({manifest_path})",
                                errors,
                            )
                        elif current_target_map_hash:
                            _ok("Manifest target-map SHA256 matches current target map")
                    except Exception as exc:
                        _warn(f"Manifest target-map SHA check skipped: {exc}", warnings)
            except Exception as exc:
                _warn(f"Target map probe failed for {target_map_path}: {exc}", warnings)
        elif target_map_path:
            _warn(f"Target map not found: {target_map_path}", warnings)

        # Universal runtime preflight gate:
        # fail fast on registry/target/port/container/reachability mismatches.
        if registry_path.exists():
            try:
                from trajgym.challenges.preflight import validate_runtime_preflight
                from trajgym.challenges.registry import ChallengeRegistry

                registry = ChallengeRegistry(str(registry_path))
                if target_map_path and target_map_path.exists():
                    registry.load_target_overrides(str(target_map_path), strict=False)

                preflight_ids: list[str] | None = None
                if dataset_ids:
                    preflight_ids = sorted(dataset_ids)
                validate_runtime_preflight(
                    registry,
                    host=args.host,
                    challenge_ids=preflight_ids,
                    timeout_seconds=2.0,
                    require_reachable=True,
                    strict_container_check=True,
                )
                _ok(
                    "Runtime preflight gate passed "
                    "(registry/target/port/container/connectivity)"
                )
            except Exception as exc:
                _fail(f"Runtime preflight gate failed: {exc}", errors)

    # -------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------
    _section("SUMMARY")

    if not errors:
        print(f"\n  {GREEN}{BOLD}ALL CHECKS PASSED{RESET}")
        print("  Pipeline is ready for training.\n")
    else:
        print(f"\n  {RED}{BOLD}{len(errors)} ERROR(S) FOUND:{RESET}")
        for e in errors:
            print(f"    {RED}-{RESET} {e}")
        print()

    if warnings:
        print(f"  {YELLOW}{len(warnings)} warning(s){RESET}\n")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
