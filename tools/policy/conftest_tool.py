from __future__ import annotations

import json
import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from ..tool_versions import CONTFEST_VERSION
from .common import REPO_ROOT, PolicyFailure

POLICY_DIR = REPO_ROOT / "tools" / "policy" / "conftest"
CACHE_ROOT = REPO_ROOT / ".cache" / "aces-sdl" / "tooling" / "conftest"


def _release_base_url(version: str = CONTFEST_VERSION) -> str:
    return f"https://github.com/open-policy-agent/conftest/releases/download/v{version}"


def _release_asset_name(version: str = CONTFEST_VERSION) -> str:
    system = platform.system()
    machine = platform.machine().lower()
    arch_map = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    arch = arch_map.get(machine)
    if arch is None:
        raise RuntimeError(f"unsupported conftest architecture: {machine}")
    if system not in {"Linux", "Darwin"}:
        raise RuntimeError(f"unsupported conftest platform: {system}")
    return f"conftest_{version}_{system}_{arch}.tar.gz"


def conftest_binary_path(repo_root: Path = REPO_ROOT, *, version: str = CONTFEST_VERSION) -> Path:
    return repo_root / ".cache" / "aces-sdl" / "tooling" / "conftest" / version / "conftest"


def ensure_conftest(repo_root: Path = REPO_ROOT, *, version: str = CONTFEST_VERSION) -> Path:
    binary_path = conftest_binary_path(repo_root, version=version)
    if binary_path.exists():
        return binary_path

    cache_dir = binary_path.parent
    cache_dir.mkdir(parents=True, exist_ok=True)
    asset_name = _release_asset_name(version)
    base_url = _release_base_url(version)
    asset_url = f"{base_url}/{asset_name}"
    checksums_url = f"{base_url}/checksums.txt"

    try:
        with urlopen(checksums_url) as response:  # noqa: S310 - pinned HTTPS release asset
            checksums_text = response.read().decode("utf-8")
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"failed to download conftest checksums from {checksums_url}: {exc}") from exc

    expected_checksum = None
    for line in checksums_text.splitlines():
        checksum, _, name = line.partition("  ")
        if name == asset_name:
            expected_checksum = checksum.strip()
            break
    if not expected_checksum:
        raise RuntimeError(f"missing checksum for conftest asset {asset_name}")

    try:
        with urlopen(asset_url) as response:  # noqa: S310 - pinned HTTPS release asset
            archive_bytes = response.read()
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"failed to download conftest from {asset_url}: {exc}") from exc

    actual_checksum = sha256(archive_bytes).hexdigest()
    if actual_checksum != expected_checksum:
        raise RuntimeError(
            f"conftest checksum mismatch for {asset_name}: expected {expected_checksum}, got {actual_checksum}"
        )

    with tempfile.TemporaryDirectory(prefix="aces-conftest-") as tmpdir:
        archive_path = Path(tmpdir) / asset_name
        archive_path.write_bytes(archive_bytes)
        with tarfile.open(archive_path, "r:gz") as archive:
            member = archive.getmember("conftest")
            archive.extract(member, path=tmpdir, filter="data")
        extracted = Path(tmpdir) / "conftest"
        extracted.chmod(extracted.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        shutil.move(extracted, binary_path)

    return binary_path


def run_conftest_policy(
    input_document: dict,
    *,
    repo_root: Path = REPO_ROOT,
    policy_dir: Path = POLICY_DIR,
) -> list[PolicyFailure]:
    binary = ensure_conftest(repo_root)

    with tempfile.TemporaryDirectory(prefix="aces-conftest-input-") as tmpdir:
        input_path = Path(tmpdir) / "repo-policy-input.json"
        input_path.write_text(json.dumps(input_document, indent=2, sort_keys=True), encoding="utf-8")
        proc = subprocess.run(
            [
                str(binary),
                "test",
                str(input_path),
                "--policy",
                str(policy_dir),
                "--output",
                "json",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    if proc.returncode not in {0, 1}:
        details = proc.stderr.strip() or proc.stdout.strip() or "unknown conftest failure"
        raise RuntimeError(f"conftest repo policy evaluation failed: {details}")

    if not proc.stdout.strip():
        return []

    raw_results = json.loads(proc.stdout)
    failures: list[PolicyFailure] = []
    for result in raw_results:
        for failure in result.get("failures", []):
            metadata = failure.get("metadata", {})
            failures.append(
                PolicyFailure(
                    metadata.get("rule_id", "conftest-policy-failure"),
                    failure["msg"],
                    metadata.get("path"),
                )
            )
    failures.sort(key=lambda item: (item.path or "", item.rule_id, item.message))
    return failures


def verify_conftest_policy(*, repo_root: Path = REPO_ROOT, policy_dir: Path = POLICY_DIR) -> None:
    binary = ensure_conftest(repo_root)
    proc = subprocess.run(
        [
            str(binary),
            "verify",
            "--policy",
            str(policy_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        details = proc.stderr.strip() or proc.stdout.strip() or "unknown conftest verify failure"
        raise RuntimeError(f"conftest policy verification failed: {details}")
