"""Tests for ChallengeManager — mocked Docker subprocess calls."""

import subprocess
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from trajgym.challenges.manager import ChallengeManager
from trajgym.challenges.registry import ChallengeRegistry


@pytest.fixture
def registry_yaml(tmp_path):
    """Create a test registry."""
    data = {
        "challenges": [
            {
                "id": "eval-me",
                "name": "[Very Easy] eval-me",
                "category": "misc",
                "difficulty": "very_easy",
                "infra_type": "docker",
                "port": 32805,
            },
            {
                "id": "Dynastic",
                "name": "[Very Easy] Dynastic",
                "category": "crypto",
                "difficulty": "very_easy",
                "infra_type": "static",
            },
        ]
    }
    path = tmp_path / "test_challenges.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return str(path)


@pytest.fixture
def bench_dir(tmp_path):
    """Create a mock benchmark directory structure."""
    # Docker challenge with docker-compose.yaml
    eval_dir = tmp_path / "benchmark" / "eval-me"
    eval_dir.mkdir(parents=True)
    (eval_dir / "docker-compose.yaml").write_text(
        "version: '3'\nservices:\n  app:\n    image: test"
    )

    # Static challenge (no docker files)
    crypto_dir = tmp_path / "benchmark" / "Dynastic"
    crypto_dir.mkdir(parents=True)
    (crypto_dir / "challenge.py").write_text("# crypto challenge")

    return str(tmp_path)


@pytest.fixture
def manager(registry_yaml, bench_dir):
    """Create a ChallengeManager instance."""
    registry = ChallengeRegistry(registry_yaml)
    return ChallengeManager(registry=registry, bench_dir=bench_dir)


class TestChallengeManager:
    @patch("subprocess.run")
    def test_setup_returns_url(self, mock_run, manager):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        url = manager.setup("eval-me")
        assert url == "http://localhost:32805"

    @patch("subprocess.run")
    def test_setup_calls_docker_compose(self, mock_run, manager):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        manager.setup("eval-me")

        # Should have called docker compose up -d
        calls = mock_run.call_args_list
        compose_call = [c for c in calls if "compose" in str(c)]
        assert len(compose_call) >= 1

    def test_setup_static_raises(self, manager):
        with pytest.raises(ValueError, match="static"):
            manager.setup("Dynastic")

    @patch("subprocess.run")
    def test_teardown_calls_docker_compose_down(self, mock_run, manager):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        manager.teardown("eval-me")

        calls = mock_run.call_args_list
        down_call = [c for c in calls if "down" in str(c)]
        assert len(down_call) >= 1

    @patch("subprocess.run")
    def test_health_check_returns_true(self, mock_run, manager):
        mock_run.side_effect = [
            MagicMock(
                returncode=0, stdout="0.0.0.0:32805->1337/tcp\n", stderr=""
            ),  # docker ps
            MagicMock(returncode=0, stdout="200", stderr=""),  # curl
        ]
        assert manager.health_check("eval-me") is True

    @patch("subprocess.run")
    def test_health_check_returns_false_on_timeout(self, mock_run, manager):
        mock_run.side_effect = [
            MagicMock(
                returncode=0, stdout="0.0.0.0:32805->1337/tcp\n", stderr=""
            ),  # docker ps
            subprocess.TimeoutExpired(cmd="curl", timeout=5),
        ]
        assert manager.health_check("eval-me") is False

    @patch("socket.create_connection")
    @patch("subprocess.run")
    def test_health_check_tcp_fallback_returns_true(
        self, mock_run, mock_socket, manager
    ):
        mock_run.side_effect = [
            MagicMock(
                returncode=0, stdout="0.0.0.0:32805->1337/tcp\n", stderr=""
            ),  # docker ps
            MagicMock(returncode=1, stdout="", stderr="curl failed"),  # curl
        ]
        mock_socket.return_value = nullcontext(object())
        assert manager.health_check("eval-me") is True

    @patch("subprocess.run")
    def test_get_running(self, mock_run, manager):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        manager.setup("eval-me")
        assert "eval-me" in manager.get_running()

    @patch("subprocess.run")
    def test_get_running_uses_canonical_id_for_alias_input(self, mock_run, manager):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        manager.setup("[Very Easy] eval-me")
        assert "eval-me" in manager.get_running()

    @patch("subprocess.run")
    def test_setup_all(self, mock_run, manager):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        results = manager.setup_all()
        # Only docker challenges should be launched
        assert "eval-me" in results
        assert "Dynastic" not in results

    @patch("subprocess.run")
    def test_teardown_all(self, mock_run, manager):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        manager.setup("eval-me")
        assert len(manager.get_running()) == 1
        manager.teardown_all()
        assert len(manager.get_running()) == 0

    @patch("subprocess.run")
    def test_setup_with_init_script(self, mock_run, manager, bench_dir):
        """If init_script.sh exists, it should be executed before docker compose."""
        # Create init_script.sh
        init_path = Path(bench_dir) / "benchmark" / "eval-me" / "init_script.sh"
        init_path.write_text("#!/bin/bash\necho 'building'")

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        manager.setup("eval-me")

        # Should have at least 2 calls: init_script + docker compose
        assert mock_run.call_count >= 2

    @patch("subprocess.run")
    def test_setup_failure_raises(self, mock_run, manager):
        def _run(*args, **kwargs):
            cmd = args[0]
            if cmd[:3] == ["docker", "network", "ls"]:
                return MagicMock(returncode=0, stdout="shared_net\nbridge\n", stderr="")
            if "compose" in cmd:
                return MagicMock(returncode=1, stdout="", stderr="container error")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = _run
        with pytest.raises(RuntimeError, match="docker compose up failed"):
            manager.setup("eval-me")

    @patch("subprocess.run")
    def test_teardown_uses_stop_script_for_start_docker_mode(self, mock_run, tmp_path):
        registry_data = {
            "challenges": [
                {
                    "id": "startup-only",
                    "name": "startup-only",
                    "category": "misc",
                    "difficulty": "easy",
                    "infra_type": "docker",
                    "port": 39999,
                }
            ]
        }
        registry_path = tmp_path / "registry.yaml"
        with open(registry_path, "w") as f:
            yaml.dump(registry_data, f)

        challenge_dir = tmp_path / "benchmark" / "startup-only"
        challenge_dir.mkdir(parents=True)
        (challenge_dir / "start_docker.sh").write_text("#!/bin/bash\necho start\n")
        (challenge_dir / "stop_docker.sh").write_text("#!/bin/bash\necho stop\n")

        registry = ChallengeRegistry(str(registry_path))
        mgr = ChallengeManager(registry=registry, bench_dir=str(tmp_path))
        mgr._startup_mode["startup-only"] = "start_docker.sh"
        mgr._running["startup-only"] = "http://localhost:39999"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        mgr.teardown("startup-only")

        call_strings = [str(c) for c in mock_run.call_args_list]
        assert any("stop_docker.sh" in s for s in call_strings)
        assert "startup-only" not in mgr.get_running()

    @patch("subprocess.run")
    def test_setup_resolves_nested_path_with_token_matching(self, mock_run, tmp_path):
        """Manager should resolve nested benchmark dirs without hardcoded aliases."""
        registry_data = {
            "challenges": [
                {
                    "id": "the-three-eyed-oracle",
                    "name": "[Medium] the-three-eyed-oracle",
                    "category": "crypto",
                    "difficulty": "hard",
                    "infra_type": "docker",
                    "port": 32801,
                }
            ]
        }
        registry_path = tmp_path / "registry.yaml"
        with open(registry_path, "w") as f:
            yaml.dump(registry_data, f)

        nested = (
            tmp_path
            / "benchmark"
            / "hackthebox"
            / "cyber-apocalypse-2024"
            / "pwn"
            / "[Hard] Oracle"
        )
        nested.mkdir(parents=True)
        (nested / "docker-compose.yml").write_text(
            "version: '3'\nservices:\n  app:\n    image: test"
        )

        registry = ChallengeRegistry(str(registry_path))
        mgr = ChallengeManager(registry=registry, bench_dir=str(tmp_path))

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        url = mgr.setup("the-three-eyed-oracle")
        assert url == "http://localhost:32801"

        # Ensure compose was launched from nested location.
        compose_calls = [c for c in mock_run.call_args_list if "compose" in str(c)]
        assert compose_calls, "expected docker compose invocation"

    @patch("subprocess.run")
    def test_setup_detects_generic_challenges_root(self, mock_run, tmp_path):
        """Manager should work when benchmark content lives under ./challenges."""
        registry_data = {
            "challenges": [
                {
                    "id": "eval-me",
                    "name": "[Very Easy] eval-me",
                    "category": "misc",
                    "difficulty": "very_easy",
                    "infra_type": "docker",
                    "port": 32805,
                }
            ]
        }
        registry_path = tmp_path / "registry.yaml"
        with open(registry_path, "w") as f:
            yaml.dump(registry_data, f)

        eval_dir = tmp_path / "challenges" / "eval-me"
        eval_dir.mkdir(parents=True)
        (eval_dir / "docker-compose.yaml").write_text(
            "version: '3'\nservices:\n  app:\n    image: test"
        )

        registry = ChallengeRegistry(str(registry_path))
        mgr = ChallengeManager(registry=registry, bench_dir=str(tmp_path))

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        url = mgr.setup("eval-me")
        assert url == "http://localhost:32805"

    @patch("subprocess.run")
    def test_setup_detects_nested_benchmark_root(self, mock_run, tmp_path):
        """Manager should discover deeply nested benchmark roots (BoxPwnr-style layout)."""
        registry_data = {
            "challenges": [
                {
                    "id": "eval-me",
                    "name": "[Very Easy] eval-me",
                    "category": "misc",
                    "difficulty": "very_easy",
                    "infra_type": "docker",
                    "port": 32805,
                }
            ]
        }
        registry_path = tmp_path / "registry.yaml"
        with open(registry_path, "w") as f:
            yaml.dump(registry_data, f)

        benchmark_root = (
            tmp_path
            / "src"
            / "boxpwnr"
            / "platforms"
            / "cybench"
            / "cybench-repo"
            / "benchmark"
        )
        challenge_dir = benchmark_root / "hackthebox" / "misc" / "[Very Easy] eval-me"
        challenge_dir.mkdir(parents=True)
        (challenge_dir / "docker-compose.yaml").write_text(
            "version: '3'\nservices:\n  app:\n    image: test"
        )

        registry = ChallengeRegistry(str(registry_path))
        mgr = ChallengeManager(registry=registry, bench_dir=str(tmp_path))

        assert mgr._benchmark_root() == benchmark_root
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        url = mgr.setup("eval-me")
        assert url == "http://localhost:32805"

    @patch("subprocess.run")
    def test_setup_preflight_fails_fast_on_unshare_block(self, mock_run, manager):
        """Preflight should surface actionable nested-Docker error."""

        def _run(*args, **kwargs):
            cmd = args[0]
            if cmd[:2] == ["docker", "info"]:
                return MagicMock(returncode=0, stdout="OK", stderr="")
            if cmd[:2] == ["docker", "import"]:
                return MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="failed to register layer: unshare: operation not permitted",
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = _run
        with pytest.raises(RuntimeError, match="nested container support"):
            manager.setup("eval-me")

    def test_benchmark_root_prefers_high_hint_coverage(self, tmp_path):
        """When hints exist, manager should pick root with highest path-hint coverage."""
        workspace = tmp_path / "workspace"
        bench_dir = workspace / "benchmarks" / "cybench"
        bench_root_partial = bench_dir / "benchmark"
        bench_root_partial.mkdir(parents=True)
        (
            bench_root_partial
            / "project-sekai-ctf"
            / "sekaictf-2023"
            / "crypto"
            / "noisier-crc"
        ).mkdir(parents=True)
        (
            bench_root_partial
            / "project-sekai-ctf"
            / "sekaictf-2023"
            / "crypto"
            / "noisier-crc"
            / "docker-compose.yml"
        ).write_text("version: '3'\nservices:\n  app:\n    image: test")

        boxpwnr_root = (
            workspace
            / "BoxPwnr"
            / "src"
            / "boxpwnr"
            / "platforms"
            / "cybench"
            / "cybench-repo"
            / "benchmark"
        )
        full_a = (
            boxpwnr_root
            / "project-sekai-ctf"
            / "sekaictf-2023"
            / "crypto"
            / "noisier-crc"
        )
        full_b = (
            boxpwnr_root
            / "project-sekai-ctf"
            / "sekaictf-2023"
            / "misc"
            / "just-another-pickle-jail"
        )
        full_a.mkdir(parents=True)
        full_b.mkdir(parents=True)
        (full_a / "docker-compose.yml").write_text(
            "version: '3'\nservices:\n  app:\n    image: test"
        )
        (full_b / "docker-compose.yml").write_text(
            "version: '3'\nservices:\n  app:\n    image: test"
        )

        registry_data = {
            "challenges": [
                {
                    "id": "noisier-crc",
                    "name": "noisier-crc",
                    "category": "crypto",
                    "difficulty": "hard",
                    "infra_type": "docker",
                    "port": 9999,
                    "path_hint": "benchmark/project-sekai-ctf/sekaictf-2023/crypto/noisier-crc",
                },
                {
                    "id": "just-another-pickle-jail",
                    "name": "just-another-pickle-jail",
                    "category": "misc",
                    "difficulty": "hard",
                    "infra_type": "docker",
                    "port": 1337,
                    "path_hint": "benchmark/project-sekai-ctf/sekaictf-2023/misc/just-another-pickle-jail",
                },
            ]
        }
        registry_path = tmp_path / "registry_hints.yaml"
        with open(registry_path, "w") as f:
            yaml.dump(registry_data, f)

        registry = ChallengeRegistry(str(registry_path))
        mgr = ChallengeManager(registry=registry, bench_dir=str(bench_dir))
        assert mgr._benchmark_root() == boxpwnr_root
