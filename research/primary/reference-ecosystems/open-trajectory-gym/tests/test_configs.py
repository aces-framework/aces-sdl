"""Smoke tests for YAML configuration files.

Validates:
- All YAML configs load without error
- SkyRL Online RL configs have required fields
- Config values are reasonable (batch sizes, learning rates, etc.)
"""

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


class TestSkyRLGRPOConfigs:
    GRPO_DIR = PROJECT_ROOT / "src" / "trajgym" / "training" / "online_rl_templates"

    def test_online_rl_dir_exists(self):
        assert self.GRPO_DIR.exists(), f"ONLINE_RL config dir not found: {self.GRPO_DIR}"

    @pytest.fixture(
        params=[
            "qwen35_27b.yaml",
        ]
    )
    def grpo_config(self, request):
        path = self.GRPO_DIR / request.param
        if not path.exists():
            pytest.skip(f"{request.param} not found")
        return _load_yaml(path), request.param

    def test_loads_without_error(self, grpo_config):
        cfg, name = grpo_config
        assert isinstance(cfg, dict), f"{name} did not load as dict"

    def test_has_trainer_section(self, grpo_config):
        cfg, name = grpo_config
        assert "trainer" in cfg, f"{name} missing 'trainer' section"

    def test_has_generator_section(self, grpo_config):
        cfg, name = grpo_config
        assert "generator" in cfg, f"{name} missing 'generator' section"

    def test_has_environment_section(self, grpo_config):
        cfg, name = grpo_config
        assert "environment" in cfg, f"{name} missing 'environment' section"

    def test_environment_class_is_trajgym(self, grpo_config):
        cfg, name = grpo_config
        env = cfg.get("environment", {})
        assert (
            env.get("env_class") == "trajgym"
        ), f"{name} environment.env_class should be 'trajgym'"

    def test_trainer_has_policy(self, grpo_config):
        cfg, name = grpo_config
        trainer = cfg.get("trainer", {})
        assert "policy" in trainer, f"{name} trainer missing 'policy'"

    def test_generator_has_sampling_params(self, grpo_config):
        cfg, name = grpo_config
        gen = cfg.get("generator", {})
        assert "sampling_params" in gen, f"{name} generator missing 'sampling_params'"

    def test_n_samples_per_prompt(self, grpo_config):
        cfg, name = grpo_config
        gen = cfg.get("generator", {})
        n = gen.get("n_samples_per_prompt", 0)
        assert n >= 2, f"{name} n_samples_per_prompt={n} should be >= 2 for ONLINE_RL"

    def test_max_turns_set(self, grpo_config):
        cfg, name = grpo_config
        gen = cfg.get("generator", {})
        turns = gen.get("max_turns", 0)
        assert turns >= 5, f"{name} max_turns={turns} should be >= 5"

    def test_algorithm_advantage_estimator(self, grpo_config):
        cfg, name = grpo_config
        algo = cfg.get("trainer", {}).get("algorithm", {})
        assert algo.get("advantage_estimator") in (
            "online_rl",
            "rloo",
            "rloo_n",
        ), f"{name} should use ONLINE_RL, RLOO, or RLOO-N advantage estimator"


# ---------------------------------------------------------------------------
# All YAML files load
# ---------------------------------------------------------------------------


class TestAllConfigsLoad:
    def test_all_yaml_files_parse(self):
        """Every YAML file under configs/ should parse without error."""
        yaml_files = list(CONFIGS_DIR.rglob("*.yaml"))
        assert len(yaml_files) > 0, "No YAML files found under configs/"

        for path in yaml_files:
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)
                assert data is not None, f"{path.name} loaded as None"
            except yaml.YAMLError as e:
                pytest.fail(f"{path.name} failed to parse: {e}")
