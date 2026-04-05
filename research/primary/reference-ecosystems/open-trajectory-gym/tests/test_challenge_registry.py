"""Tests for ChallengeRegistry."""

import json
from pathlib import Path

import pytest
import yaml
from trajgym.challenges.registry import ChallengeInfo, ChallengeRegistry


@pytest.fixture
def registry_yaml(tmp_path):
    """Create a test registry YAML."""
    data = {
        "challenges": [
            {
                "id": "eval-me",
                "name": "[Very Easy] eval-me",
                "category": "misc",
                "difficulty": "very_easy",
                "infra_type": "docker",
                "port": 32805,
                "aliases": ["EvalMe", "Eval_Me"],
            },
            {
                "id": "Dynastic",
                "name": "[Very Easy] Dynastic",
                "category": "crypto",
                "difficulty": "very_easy",
                "infra_type": "static",
            },
            {
                "id": "TimeKORP",
                "name": "[Easy] TimeKORP",
                "category": "web",
                "difficulty": "easy",
                "infra_type": "docker",
                "port": 32810,
            },
        ]
    }
    path = tmp_path / "test_challenges.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return str(path)


class TestChallengeRegistry:
    def test_load_challenges(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        assert len(reg) == 3

    def test_get_existing(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        info = reg.get("eval-me")
        assert info.id == "eval-me"
        assert info.category == "misc"
        assert info.infra_type == "docker"
        assert info.port == 32805

    def test_get_unknown_raises(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        with pytest.raises(KeyError, match="nonexistent"):
            reg.get("nonexistent")

    def test_list_docker_challenges(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        docker = reg.list_docker_challenges()
        assert len(docker) == 2
        ids = {c.id for c in docker}
        assert ids == {"eval-me", "TimeKORP"}

    def test_list_static_challenges(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        static = reg.list_static_challenges()
        assert len(static) == 1
        assert static[0].id == "Dynastic"

    def test_get_target_url_docker(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        url = reg.get_target_url("eval-me")
        assert url == "http://localhost:32805"

    def test_get_target_url_custom_host(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        url = reg.get_target_url("eval-me", host="192.168.1.100")
        assert url == "http://192.168.1.100:32805"

    def test_get_target_url_static_returns_none(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        url = reg.get_target_url("Dynastic")
        assert url is None

    def test_target_overrides_file_takes_precedence(self, registry_yaml, tmp_path):
        overrides_path = tmp_path / "targets.json"
        overrides_path.write_text(
            json.dumps({"challenge_targets": {"eval-me": "http://localhost:43012"}})
        )
        reg = ChallengeRegistry(
            registry_yaml,
            target_overrides_path=str(overrides_path),
        )
        assert reg.get_target_url("eval-me") == "http://localhost:43012"
        # Localhost overrides still honor explicit host rewrites for callers.
        assert (
            reg.get_target_url("eval-me", host="127.0.0.2") == "http://127.0.0.2:43012"
        )

    def test_target_overrides_support_port_only_entries(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        loaded = reg.set_target_overrides({"eval-me": 43055})
        assert loaded == 1
        assert reg.get_target_url("EvalMe") == "http://localhost:43055"

    def test_target_overrides_strict_mode_raises_unknown_id(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        with pytest.raises(KeyError, match="unknown-id"):
            reg.set_target_overrides(
                {"unknown-id": "http://localhost:43001"}, strict=True
            )

    def test_contains(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        assert "eval-me" in reg
        assert "Eval_Me" in reg
        assert "nonexistent" not in reg

    def test_get_by_display_name(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        info = reg.get("[Very Easy] eval-me")
        assert info.id == "eval-me"

    def test_get_by_alias(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        info = reg.get("EvalMe")
        assert info.id == "eval-me"

    def test_list_all(self, registry_yaml):
        reg = ChallengeRegistry(registry_yaml)
        all_challenges = reg.list_all()
        assert len(all_challenges) == 3

    def test_token_overlap_resolution(self, tmp_path):
        data = {
            "challenges": [
                {
                    "id": "the-three-eyed-oracle",
                    "name": "[Medium] the-three-eyed-oracle",
                    "category": "crypto",
                    "difficulty": "medium",
                    "infra_type": "docker",
                    "port": 32801,
                }
            ]
        }
        path = tmp_path / "token_match.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f)
        reg = ChallengeRegistry(str(path))
        assert reg.get("oracle").id == "the-three-eyed-oracle"

    def test_ambiguous_resolution_returns_not_found(self, tmp_path):
        data = {
            "challenges": [
                {
                    "id": "first-oracle",
                    "name": "[Hard] Oracle One",
                    "category": "crypto",
                    "difficulty": "hard",
                    "infra_type": "docker",
                    "port": 32801,
                },
                {
                    "id": "second-oracle",
                    "name": "[Hard] Oracle Two",
                    "category": "crypto",
                    "difficulty": "hard",
                    "infra_type": "docker",
                    "port": 32802,
                },
            ]
        }
        path = tmp_path / "ambiguous.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f)
        reg = ChallengeRegistry(str(path))
        with pytest.raises(KeyError, match="oracle"):
            reg.get("oracle")

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            ChallengeRegistry("/nonexistent/path.yaml")

    def test_cybench_registry_covers_online_rl_dataset(self):
        """Guardrail: keep cybench registry IDs aligned with online RL dataset challenge names."""
        repo_root = Path(__file__).resolve().parents[1]
        registry = ChallengeRegistry(str(repo_root / "configs/challenges/cybench.yaml"))
        dataset_path = repo_root / "data/online_rl.jsonl"

        missing = set()
        with dataset_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                metadata = row.get("metadata", {})
                challenge_id = metadata.get("challenge_id") or metadata.get("challenge")
                if challenge_id and registry.resolve_id(str(challenge_id)) is None:
                    missing.add(str(challenge_id))

        assert (
            not missing
        ), f"Registry missing challenge IDs referenced by data: {sorted(missing)}"


class TestChallengeInfo:
    def test_dataclass_defaults(self):
        info = ChallengeInfo(
            id="test", category="web", difficulty="easy", infra_type="docker"
        )
        assert info.name == ""
        assert info.port is None
        assert info.ground_truth_flag is None
        assert info.aliases == []
        assert info.path_hint is None
        assert info.target_url is None

    def test_full_construction(self):
        info = ChallengeInfo(
            id="test",
            category="web",
            difficulty="easy",
            infra_type="docker",
            name="Test Challenge",
            port=8080,
            ground_truth_flag="FLAG{test}",
            aliases=["alias-one"],
            path_hint="benchmark/test",
            target_url="http://localhost:43001",
        )
        assert info.port == 8080
        assert info.ground_truth_flag == "FLAG{test}"
        assert info.aliases == ["alias-one"]
        assert info.path_hint == "benchmark/test"
        assert info.target_url == "http://localhost:43001"
