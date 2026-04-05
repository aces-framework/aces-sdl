"""Challenge lifecycle manager — launch/stop Docker containers for CTF challenges."""

import io
import logging
import os
import re
import socket
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from .registry import ChallengeRegistry

logger = logging.getLogger(__name__)


class ChallengeManager:
    """Manage Docker container lifecycle for benchmark challenges.

    Follows BoxPwnr's CybenchPlatform pattern:
    1. Look up challenge in registry
    2. Run init_script.sh if present
    3. docker compose up -d
    4. Health check
    5. Return target URL

    Usage::

        registry = ChallengeRegistry("configs/challenges/cybench.yaml")
        manager = ChallengeManager(registry, bench_dir="/path/to/cybench")
        url = manager.setup("eval-me")  # -> "http://localhost:32805"
        manager.teardown("eval-me")
    """

    def __init__(
        self,
        registry: ChallengeRegistry,
        bench_dir: str,
        host: str = "localhost",
        network: str = "shared_net",
    ):
        self.registry = registry
        self.bench_dir = Path(bench_dir)
        self.host = host
        self.network = network
        self._running: dict[str, str] = {}  # challenge_id -> target_url
        self._startup_mode: dict[str, str] = (
            {}
        )  # challenge_id -> compose|start_docker.sh
        self._candidate_dirs_cache: list[Path] | None = None
        self._benchmark_root_cache: Path | None = None
        self._docker_preflight_ok = False

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize text for challenge path matching."""
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        """Tokenize text for loose path matching across benchmark variants."""
        stop_tokens = {
            "the",
            "a",
            "an",
            "and",
            "very",
            "easy",
            "medium",
            "hard",
            "challenge",
            "ctf",
            "benchmark",
        }
        return {
            tok
            for tok in re.split(r"[^a-z0-9]+", value.lower())
            if tok and tok not in stop_tokens and not tok.isdigit()
        }

    @staticmethod
    def _looks_like_challenge_dir(path: Path) -> bool:
        """Heuristic: return True when a directory resembles a challenge root."""
        markers = (
            "metadata",
            "challenge",
            "dist",
            "release",
            "env",
            "docker-compose.yml",
            "docker-compose.yaml",
            "start_docker.sh",
        )
        return any((path / marker).exists() for marker in markers)

    def _challenge_root_score(self, root: Path) -> int:
        """Score how likely a directory is a benchmark challenge root."""
        if not root.is_dir():
            return 0
        try:
            direct_dirs = [item for item in root.iterdir() if item.is_dir()]
        except OSError:
            return 0
        if not direct_dirs:
            return 0

        score = 0
        for child in direct_dirs:
            if self._looks_like_challenge_dir(child):
                score += 5
                continue
            # Common benchmark layout: category/challenge.
            try:
                grandchildren = [item for item in child.iterdir() if item.is_dir()]
            except OSError:
                continue
            if any(
                self._looks_like_challenge_dir(grandchild)
                for grandchild in grandchildren
            ):
                score += 3

        # Prefer roots with enough immediate subdirs to represent categories/tasks.
        score += min(10, len(direct_dirs))
        return score

    def _benchmark_root(self) -> Path:
        """Return the benchmark root directory."""
        if self._benchmark_root_cache is not None:
            return self._benchmark_root_cache

        has_path_hints = any(info.path_hint for info in self.registry.list_all())

        # Prefer explicit benchmark layout if present.
        explicit = self.bench_dir / "benchmark"
        if (
            explicit.exists()
            and self._challenge_root_score(explicit) > 0
            and not has_path_hints
        ):
            self._benchmark_root_cache = explicit
            return explicit

        # Generic benchmark repos often keep challenges under one of these roots.
        roots: list[Path] = [
            self.bench_dir / name
            for name in ("benchmarks", "challenges", "tasks", "ctf", "data")
            if (self.bench_dir / name).is_dir()
        ]

        # Some repos keep benchmark under nested platform folders
        # like src/.../cybench-repo/benchmark.
        skip_parts = {".git", ".venv", "__pycache__", "node_modules"}
        search_bases = {self.bench_dir}
        if has_path_hints and self.bench_dir.parent != self.bench_dir:
            search_bases.add(self.bench_dir.parent)
        if has_path_hints and self.bench_dir.parent.parent != self.bench_dir.parent:
            search_bases.add(self.bench_dir.parent.parent)

        for base in search_bases:
            for candidate in base.rglob("benchmark"):
                if not candidate.is_dir():
                    continue
                if any(part in skip_parts for part in candidate.parts):
                    continue
                roots.append(candidate)

        # If registry path hints exist, prioritize roots with the highest
        # path-hint coverage so mixed benchmark layouts resolve deterministically.
        def _hint_coverage(root: Path) -> int:
            covered = 0
            for info in self.registry.list_all():
                if not info.path_hint:
                    continue
                hint = Path(info.path_hint)
                hint_path = hint if hint.is_absolute() else root.parent / hint
                if hint_path.exists():
                    covered += 1
            return covered

        scored = []
        for root in roots:
            structure_score = self._challenge_root_score(root)
            if structure_score <= 0:
                continue
            hint_score = _hint_coverage(root)
            score = hint_score * 1000 + structure_score
            if score > 0:
                scored.append((score, hint_score, -len(root.parts), str(root), root))

        if scored:
            _, hint_score, _, _, best_root = max(scored)
            if hint_score:
                logger.info(
                    "Selected benchmark root %s using path-hint coverage (%d matches)",
                    best_root,
                    hint_score,
                )
            self._benchmark_root_cache = best_root
            return best_root

        self._benchmark_root_cache = self.bench_dir
        return self.bench_dir

    @staticmethod
    def _truncate_stderr(stderr: str, limit: int = 240) -> str:
        text = (stderr or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    def _docker_preflight(self) -> None:
        """Validate Docker can run nested challenge workloads."""
        if self._docker_preflight_ok:
            return

        preflight_timeout = max(
            30,
            int(os.environ.get("TRAJGYM_DOCKER_PREFLIGHT_TIMEOUT", "120")),
        )

        try:
            info = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=20,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "docker command not found; install Docker on the host first."
            ) from exc

        if info.returncode != 0:
            raise RuntimeError(
                f"Docker daemon is unavailable: {self._truncate_stderr(info.stderr or info.stdout)}"
            )

        # Probe layer import/unpack capability without registry/network dependency.
        with tempfile.TemporaryDirectory(prefix="trajgym-preflight-") as tmpdir:
            image_ref = f"trajgym-preflight-{abs(hash(tmpdir)) & 0xFFFFFFFF:x}:latest"
            tar_path = Path(tmpdir) / "rootfs.tar"
            payload = b"trajgym preflight\n"
            with tarfile.open(tar_path, "w") as tf:
                info = tarfile.TarInfo(name="trajgym_preflight.txt")
                info.size = len(payload)
                tf.addfile(info, io.BytesIO(payload))

            import_result = subprocess.run(
                ["docker", "import", str(tar_path), image_ref],
                capture_output=True,
                text=True,
                timeout=preflight_timeout,
            )
            if import_result.returncode != 0:
                stderr = self._truncate_stderr(
                    import_result.stderr or import_result.stdout
                )
                lowered = stderr.lower()
                if any(
                    x in lowered
                    for x in ("operation not permitted", "unshare", "mount")
                ):
                    raise RuntimeError(
                        "Docker cannot unpack image layers in this environment "
                        f"({stderr}). Run the pod in privileged mode with nested container "
                        "support enabled."
                    )
                raise RuntimeError(f"Docker image import preflight failed: {stderr}")

            subprocess.run(
                ["docker", "rmi", "-f", image_ref],
                capture_output=True,
                text=True,
                timeout=preflight_timeout,
            )

        self._docker_preflight_ok = True

    def _list_candidate_dirs(self) -> list[Path]:
        """Index challenge-like directories in benchmark tree."""
        if self._candidate_dirs_cache is not None:
            return self._candidate_dirs_cache

        root = self._benchmark_root()
        if not root.exists():
            self._candidate_dirs_cache = []
            return self._candidate_dirs_cache

        candidates: list[Path] = []
        for path in root.rglob("*"):
            if not path.is_dir():
                continue
            if any(
                (path / marker).exists()
                for marker in ("metadata", "challenge", "dist", "release", "env")
            ):
                candidates.append(path)
                continue
            if any(
                (path / marker).exists()
                for marker in (
                    "docker-compose.yml",
                    "docker-compose.yaml",
                    "start_docker.sh",
                )
            ):
                candidates.append(path)

        # Include flat challenge directories for legacy layout.
        for path in root.iterdir():
            if path.is_dir():
                candidates.append(path)

        self._candidate_dirs_cache = sorted(
            set(candidates), key=lambda p: (len(p.parts), str(p))
        )
        return self._candidate_dirs_cache

    def _score_candidate(self, query: str, candidate: Path) -> int:
        """Score how well a candidate directory matches a challenge query."""
        if not query:
            return 0

        query_norm = self._normalize(query)
        query_tokens = self._tokenize(query)
        base = self._normalize(candidate.name)
        rel_text = str(candidate.relative_to(self._benchmark_root()))
        rel = self._normalize(rel_text)
        base_tokens = self._tokenize(candidate.name)
        rel_tokens = self._tokenize(rel_text)
        candidate_tokens = base_tokens | rel_tokens
        if not base:
            return 0

        score = 0
        if query_norm == base:
            score = max(score, 100)
        elif query_norm in base:
            score = max(score, 88)
        elif base in query_norm:
            score = max(score, 83)
        elif query_norm in rel:
            score = max(score, 80)

        if query_tokens and base_tokens:
            overlap = len(query_tokens & base_tokens)
            if overlap:
                precision = overlap / len(base_tokens)
                recall = overlap / len(query_tokens)
                score = max(score, int(63 + 30 * max(precision, recall)))
                if base_tokens.issubset(query_tokens):
                    score = max(score, 84 + min(6, len(base_tokens)))
                if query_tokens.issubset(base_tokens):
                    score = max(score, 82 + min(6, len(query_tokens)))

        if query_tokens and candidate_tokens:
            overlap = len(query_tokens & candidate_tokens)
            if overlap:
                precision = overlap / len(candidate_tokens)
                recall = overlap / len(query_tokens)
                score = max(score, int(58 + 25 * max(precision, recall)))

        # Prefer paths that already contain launch artifacts.
        if score > 0 and self._find_first(
            candidate, ["docker-compose.yaml", "docker-compose.yml", "start_docker.sh"]
        ):
            score += 5
        return score

    def _challenge_dir(self, challenge_id: str) -> Path:
        """Resolve challenge directory in benchmark tree (flat or nested)."""
        info = self.registry.get(challenge_id)
        benchmark_root = self._benchmark_root()

        # 1) path_hint override from registry config.
        if info.path_hint:
            hint = Path(info.path_hint)
            hint_path = hint if hint.is_absolute() else benchmark_root / hint
            if hint_path.exists():
                return hint_path

        # 2) Legacy flat layout path.
        legacy_path = benchmark_root / info.id
        if legacy_path.exists():
            return legacy_path

        # 3) Nested-path discovery using id/name/aliases.
        queries = [info.id, info.name, *info.aliases]
        queries = [q for q in queries if q]

        best_path: Path | None = None
        best_score = 0
        second_score = 0
        for candidate in self._list_candidate_dirs():
            for query in queries:
                score = self._score_candidate(query, candidate)
                if score > best_score:
                    second_score = best_score
                    best_score = score
                    best_path = candidate
                elif score > second_score and candidate != best_path:
                    second_score = score

        if best_path is None or best_score < 80:
            raise RuntimeError(
                f"Could not resolve benchmark path for challenge '{challenge_id}' "
                f"(name='{info.name}') under {benchmark_root}. "
                "Set path_hint/aliases in configs/challenges/cybench.yaml."
            )

        if second_score >= best_score - 2 and best_score < 95:
            raise RuntimeError(
                f"Ambiguous benchmark path resolution for challenge '{challenge_id}' "
                f"(best_score={best_score}, second_score={second_score}) under {benchmark_root}. "
                "Set path_hint in challenge registry to make the mapping deterministic."
            )

        logger.info(
            "Resolved challenge %s -> %s (score=%d)",
            challenge_id,
            best_path,
            best_score,
        )
        return best_path

    def _find_first(self, challenge_dir: Path, names: list[str]) -> Path | None:
        """Find launch artifact in challenge dir (first direct, then recursive)."""
        for name in names:
            direct = challenge_dir / name
            if direct.exists():
                return direct

        matches: list[Path] = []
        for name in names:
            matches.extend(challenge_dir.rglob(name))
        if not matches:
            return None

        return sorted(set(matches), key=lambda p: (len(p.parts), str(p)))[0]

    def _ensure_shared_network_exists(self) -> None:
        """Ensure the configured Docker network exists for challenge compose files."""
        if not self.network:
            return
        try:
            result = subprocess.run(
                ["docker", "network", "ls", "--format", "{{.Name}}"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "docker command not found; install Docker on the host first."
            ) from exc

        if result.returncode != 0:
            raise RuntimeError(f"docker network ls failed: {result.stderr}")

        networks = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        if self.network in networks:
            return

        create = subprocess.run(
            ["docker", "network", "create", self.network],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if create.returncode != 0:
            err = self._truncate_stderr(create.stderr or create.stdout)
            if "operation not permitted" in err.lower():
                raise RuntimeError(
                    f"Failed to create docker network '{self.network}': {err}. "
                    "This host does not allow nested Docker networking (NET_ADMIN/bridge). "
                    "Use a privileged runtime for CyBench docker challenges."
                )
            raise RuntimeError(
                f"Failed to create docker network '{self.network}': {err}"
            )

    def setup(self, challenge_id: str) -> str:
        """Launch a challenge's Docker container and return the target URL.

        Args:
            challenge_id: Challenge identifier from the registry.

        Returns:
            Target URL (e.g. "http://localhost:32805").

        Raises:
            KeyError: If challenge not in registry.
            ValueError: If challenge is static (no Docker needed).
            RuntimeError: If container fails to start.
        """
        info = self.registry.get(challenge_id)

        if info.infra_type != "docker":
            raise ValueError(
                f"Challenge {challenge_id} is {info.infra_type}, not docker — no container to launch"
            )

        self._docker_preflight()
        challenge_dir = self._challenge_dir(challenge_id)

        # Run init_script.sh if present (builds images, etc.)
        init_script = self._find_first(challenge_dir, ["init_script.sh"])
        if init_script:
            logger.info("Running init script for %s", challenge_id)
            # Match BoxPwnr's CyBench calling convention: pass a writable temp dir
            # as arg1 so init scripts that copy artifacts can run successfully.
            tmp_dir = (
                Path("/tmp/trajgym")
                / "challenge-init"
                / re.sub(r"[^a-zA-Z0-9_.-]+", "_", info.id)
            )
            tmp_dir.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["bash", str(init_script), str(tmp_dir)],
                cwd=str(init_script.parent),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.warning(
                    "init_script.sh failed for %s: %s", challenge_id, result.stderr
                )

        self._ensure_shared_network_exists()
        startup_mode = "compose"

        # Start with docker compose
        compose_file = self._find_first(
            challenge_dir, ["docker-compose.yaml", "docker-compose.yml"]
        )
        if compose_file:
            logger.info("Starting docker compose for %s", challenge_id)
            try:
                result = subprocess.run(
                    ["docker", "compose", "-f", str(compose_file), "up", "-d"],
                    cwd=str(compose_file.parent),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except FileNotFoundError as exc:
                raise RuntimeError(
                    "docker command not found; install Docker on the host first."
                ) from exc
            if result.returncode != 0:
                raise RuntimeError(
                    f"docker compose up failed for {challenge_id}: {result.stderr}"
                )
        else:
            # Try start_docker.sh fallback
            start_script = self._find_first(challenge_dir, ["start_docker.sh"])
            if start_script:
                startup_mode = "start_docker.sh"
                logger.info("Running start_docker.sh for %s", challenge_id)
                result = subprocess.run(
                    ["bash", str(start_script)],
                    cwd=str(start_script.parent),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"start_docker.sh failed for {challenge_id}: {result.stderr}"
                    )
            else:
                raise RuntimeError(
                    f"No docker-compose.yaml or start_docker.sh found in {challenge_dir}"
                )

        target_url = self.registry.get_target_url(info.id, host=self.host)
        if target_url:
            self._running[info.id] = target_url
            self._startup_mode[info.id] = startup_mode
            return target_url

        if info.port is None:
            raise RuntimeError(
                f"Challenge {info.id} started but no port is configured. "
                "Set port in the registry entry or provide a benchmark-specific target resolver."
            )
        fallback_url = f"http://{self.host}:{info.port}"
        self._running[info.id] = fallback_url
        self._startup_mode[info.id] = startup_mode
        return fallback_url

    def teardown(self, challenge_id: str) -> None:
        """Stop a challenge's Docker container.

        Args:
            challenge_id: Challenge identifier.
        """
        info = self.registry.get(challenge_id)
        if info.infra_type != "docker":
            return

        challenge_dir = self._challenge_dir(challenge_id)
        startup_mode = self._startup_mode.get(info.id, "")
        stopped = False

        compose_file = self._find_first(
            challenge_dir, ["docker-compose.yaml", "docker-compose.yml"]
        )
        if compose_file:
            logger.info("Stopping docker compose for %s", challenge_id)
            try:
                subprocess.run(
                    ["docker", "compose", "-f", str(compose_file), "down"],
                    cwd=str(compose_file.parent),
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                stopped = True
            except FileNotFoundError:
                logger.warning(
                    "docker command not found while tearing down %s", challenge_id
                )

        if not stopped and startup_mode == "start_docker.sh":
            stop_script = self._find_first(challenge_dir, ["stop_docker.sh"])
            if stop_script:
                logger.info("Running stop_docker.sh for %s", challenge_id)
                result = subprocess.run(
                    ["bash", str(stop_script)],
                    cwd=str(stop_script.parent),
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    logger.warning(
                        "stop_docker.sh failed for %s: %s",
                        challenge_id,
                        self._truncate_stderr(result.stderr),
                    )
                else:
                    stopped = True
            else:
                logger.warning(
                    "Challenge %s started via start_docker.sh but no stop_docker.sh found. "
                    "Skipping explicit teardown.",
                    challenge_id,
                )

        self._running.pop(info.id, None)
        self._startup_mode.pop(info.id, None)

    def setup_all(self, ids: list[str] | None = None) -> dict[str, str]:
        """Launch multiple challenges. Returns {challenge_id: target_url}.

        Args:
            ids: Specific challenge IDs. If None, launches all docker challenges.
        """
        if ids is None:
            ids = [c.id for c in self.registry.list_docker_challenges()]

        if ids:
            self._docker_preflight()

        results = {}
        for cid in ids:
            try:
                url = self.setup(cid)
                results[cid] = url
            except Exception as exc:
                logger.error("Failed to setup %s: %s", cid, exc)
        return results

    def teardown_all(self) -> None:
        """Stop all running challenge containers."""
        for cid in list(self._running.keys()):
            try:
                self.teardown(cid)
            except Exception as exc:
                logger.error("Failed to teardown %s: %s", cid, exc)

    def health_check(self, challenge_id: str, timeout: int = 5) -> bool:
        """Check if a challenge's service is responding.

        Args:
            challenge_id: Challenge identifier.
            timeout: HTTP timeout in seconds.

        Returns:
            True if service responds, False otherwise.
        """
        info = self.registry.get(challenge_id)
        url = self.registry.get_target_url(info.id, host=self.host)
        if not url:
            return False

        # Avoid false positives from unrelated host services: require at least
        # one running docker container to expose this challenge port.
        if info.infra_type == "docker" and info.port:
            try:
                ps = subprocess.run(
                    ["docker", "ps", "--format", "{{.Ports}}"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if ps.returncode != 0:
                    return False
                expected = f":{info.port}->"
                if expected not in ps.stdout:
                    return False
            except Exception:
                return False

        parsed = urlparse(url)
        scheme = parsed.scheme.lower() if parsed.scheme else "http"
        host = parsed.hostname or self.host
        port = parsed.port or info.port

        if scheme == "file":
            path = parsed.path or ""
            return bool(path and Path(path).exists())

        try:
            if scheme in {"http", "https"}:
                result = subprocess.run(
                    [
                        "curl",
                        "-sf",
                        "--max-time",
                        str(timeout),
                        "-o",
                        "/dev/null",
                        "-w",
                        "%{http_code}",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=timeout + 5,
                )
                status = result.stdout.strip()
                if status.startswith(("2", "3", "4")):
                    return True
        except (subprocess.TimeoutExpired, Exception):
            pass

        if not host or not port:
            return False
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except (OSError, ValueError):
            return False

    def get_running(self) -> list[str]:
        """Return list of currently running challenge IDs."""
        return list(self._running.keys())
