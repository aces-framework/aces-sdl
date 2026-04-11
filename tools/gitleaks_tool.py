from __future__ import annotations

import platform
import shutil
import stat
import tarfile
import tempfile
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from tools.tool_versions import GITLEAKS_VERSION

REPO_ROOT = Path(__file__).resolve().parents[1]


def _release_base_url(version: str = GITLEAKS_VERSION) -> str:
    return f"https://github.com/gitleaks/gitleaks/releases/download/v{version}"


def _release_asset_name(version: str = GITLEAKS_VERSION) -> str:
    system = platform.system()
    machine = platform.machine().lower()
    arch_map = {
        "x86_64": "x64",
        "amd64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    platform_map = {
        "Linux": "linux",
        "Darwin": "darwin",
    }
    arch = arch_map.get(machine)
    platform_name = platform_map.get(system)
    if arch is None:
        raise RuntimeError(f"unsupported gitleaks architecture: {machine}")
    if platform_name is None:
        raise RuntimeError(f"unsupported gitleaks platform: {system}")
    return f"gitleaks_{version}_{platform_name}_{arch}.tar.gz"


def _checksums_asset_name(version: str = GITLEAKS_VERSION) -> str:
    return f"gitleaks_{version}_checksums.txt"


def gitleaks_binary_path(repo_root: Path = REPO_ROOT, *, version: str = GITLEAKS_VERSION) -> Path:
    return repo_root / ".cache" / "aces-sdl" / "tooling" / "gitleaks" / version / "gitleaks"


def ensure_gitleaks(repo_root: Path = REPO_ROOT, *, version: str = GITLEAKS_VERSION) -> Path:
    binary_path = gitleaks_binary_path(repo_root, version=version)
    if binary_path.exists():
        return binary_path

    cache_dir = binary_path.parent
    cache_dir.mkdir(parents=True, exist_ok=True)
    asset_name = _release_asset_name(version)
    base_url = _release_base_url(version)
    asset_url = f"{base_url}/{asset_name}"
    checksums_url = f"{base_url}/{_checksums_asset_name(version)}"

    try:
        with urlopen(checksums_url) as response:  # noqa: S310 - pinned HTTPS release asset
            checksums_text = response.read().decode("utf-8")
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"failed to download gitleaks checksums from {checksums_url}: {exc}") from exc

    expected_checksum = None
    for line in checksums_text.splitlines():
        checksum, _, name = line.partition("  ")
        if name == asset_name:
            expected_checksum = checksum.strip()
            break
    if not expected_checksum:
        raise RuntimeError(f"missing checksum for gitleaks asset {asset_name}")

    try:
        with urlopen(asset_url) as response:  # noqa: S310 - pinned HTTPS release asset
            archive_bytes = response.read()
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"failed to download gitleaks from {asset_url}: {exc}") from exc

    actual_checksum = sha256(archive_bytes).hexdigest()
    if actual_checksum != expected_checksum:
        raise RuntimeError(
            f"gitleaks checksum mismatch for {asset_name}: expected {expected_checksum}, got {actual_checksum}"
        )

    with tempfile.TemporaryDirectory(prefix="aces-gitleaks-") as tmpdir:
        archive_path = Path(tmpdir) / asset_name
        archive_path.write_bytes(archive_bytes)
        with tarfile.open(archive_path, "r:gz") as archive:
            member = archive.getmember("gitleaks")
            archive.extract(member, path=tmpdir, filter="data")
        extracted = Path(tmpdir) / "gitleaks"
        extracted.chmod(extracted.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        shutil.move(extracted, binary_path)

    return binary_path
