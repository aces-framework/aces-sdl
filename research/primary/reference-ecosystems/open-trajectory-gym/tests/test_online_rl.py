"""Smoke tests for SkyRL Online RL orchestrator.

Validates:
- _convert_online_rl_data correctly converts Online RL JSONL to SkyRL format
- _build_skyrl_config produces valid SkyRL config dict
- Config has correct nesting (data.train_data, trainer.policy.model.path, etc.)
"""

import json
import os
from pathlib import Path

import pytest
import yaml
from trajgym.challenges.registry import ChallengeRegistry
from trajgym.training.online_rl.runtime import (
    _DIFFICULTY_ORDER,
    _DIFFICULTY_RANK,
    _build_skyrl_config,
    _convert_online_rl_data,
    _has_step_wise_resp_index_guard,
    _is_qwen3_5_config,
    _resolve_reward_config,
    _resolve_vllm_ready_model_path,
    _should_force_legacy_inference,
    _validate_qwen3_5_runtime_dependencies,
    _validate_step_wise_resp_index_guard,
)

# ---------------------------------------------------------------------------
# Sample Online RL data
# ---------------------------------------------------------------------------


def _write_online_rl_jsonl(path, samples=None):
    """Write sample Online RL JSONL data."""
    if samples is None:
        samples = [
            {
                "messages": [
                    {"role": "system", "content": "You are a CTF agent."},
                    {"role": "user", "content": "Scan 10.0.0.1 for vulnerabilities."},
                    {"role": "assistant", "content": "Running nmap..."},
                    {
                        "role": "tool",
                        "name": "shell_command",
                        "content": "80/tcp open http",
                    },
                ],
                "ground_truth_flag": "FLAG{test123}",
                "metadata": {
                    "optimal_steps": 5,
                    "challenge_id": "XBEN-001",
                    "task_type": "ctf",
                },
            },
            {
                "messages": [
                    {"role": "system", "content": "You are a CTF agent."},
                    {"role": "user", "content": "Find the flag on the web server."},
                    {"role": "assistant", "content": "Let me check."},
                ],
                "ground_truth_flag": "FLAG{web_flag}",
                "metadata": {
                    "optimal_steps": 3,
                    "challenge_id": "XBEN-002",
                    "task_type": "ctf",
                },
            },
        ]
    import jsonlines

    with jsonlines.open(str(path), "w") as w:
        for s in samples:
            w.write(s)


# ---------------------------------------------------------------------------
# _convert_online_rl_data
# ---------------------------------------------------------------------------


class TestConvertOnlineRLData:
    @staticmethod
    def _write_registry(path: Path, challenges: list[dict]) -> None:
        path.write_text(yaml.safe_dump({"challenges": challenges}))

    def test_output_file_created(self, tmp_path):
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src)
        output_dir = str(tmp_path / "out")

        result = _convert_online_rl_data(str(src), output_dir)
        assert os.path.exists(result)
        assert result.endswith("skyrl_online_rl_data.jsonl")

    def test_correct_number_of_samples(self, tmp_path):
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src)
        output_dir = str(tmp_path / "out")

        result = _convert_online_rl_data(str(src), output_dir)
        import jsonlines

        with jsonlines.open(result) as reader:
            rows = list(reader)
        assert len(rows) == 2

    def test_prompt_extracted(self, tmp_path):
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src)
        output_dir = str(tmp_path / "out")

        result = _convert_online_rl_data(str(src), output_dir)
        import jsonlines

        with jsonlines.open(result) as reader:
            row = next(iter(reader))

        # Prompt should contain system + user messages before first assistant
        assert isinstance(row["prompt"], list)
        roles = [m["role"] for m in row["prompt"]]
        assert "system" in roles
        assert "user" in roles
        assert "assistant" not in roles

    def test_prompt_ends_with_user(self, tmp_path):
        """SkyRL requires prompt to end with a user message."""
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src)
        output_dir = str(tmp_path / "out")

        result = _convert_online_rl_data(str(src), output_dir)
        import jsonlines

        with jsonlines.open(result) as reader:
            for row in reader:
                assert row["prompt"][-1]["role"] == "user"

    def test_env_class_set(self, tmp_path):
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src)
        output_dir = str(tmp_path / "out")

        result = _convert_online_rl_data(str(src), output_dir)
        import jsonlines

        with jsonlines.open(result) as reader:
            for row in reader:
                assert row["env_class"] == "trajgym"

    def test_ground_truth_flag_preserved(self, tmp_path):
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src)
        output_dir = str(tmp_path / "out")

        result = _convert_online_rl_data(str(src), output_dir)
        import jsonlines

        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["ground_truth_flag"] == "FLAG{test123}"

    def test_metadata_flattened(self, tmp_path):
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src)
        output_dir = str(tmp_path / "out")

        result = _convert_online_rl_data(str(src), output_dir)
        import jsonlines

        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["optimal_steps"] == 5
        assert row["challenge_id"] == "XBEN-001"
        assert row["task_type"] == "ctf"

    def test_missing_user_message_gets_default(self, tmp_path):
        """If messages only have system + assistant, a default user msg is added."""
        src = tmp_path / "online_rl.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {"role": "assistant", "content": "Doing stuff."},
                    ],
                    "ground_truth_flag": "FLAG{x}",
                    "metadata": {},
                }
            )
        output_dir = str(tmp_path / "out")

        result = _convert_online_rl_data(str(src), output_dir)
        import jsonlines as jl2

        with jl2.open(result) as reader:
            row = next(iter(reader))
        # Prompt should end with user
        assert row["prompt"][-1]["role"] == "user"
        assert "flag" in row["prompt"][-1]["content"].lower()

    def test_registry_filter_drops_unresolved_samples(self, tmp_path):
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(
            src,
            samples=[
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {"role": "user", "content": "Challenge A"},
                    ],
                    "ground_truth_flag": "FLAG{a}",
                    "metadata": {"challenge_id": "known-id"},
                },
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {"role": "user", "content": "Challenge B"},
                    ],
                    "ground_truth_flag": "FLAG{b}",
                    "metadata": {"challenge_id": "missing-id"},
                },
            ],
        )
        registry_path = tmp_path / "registry.yaml"
        self._write_registry(
            registry_path,
            challenges=[
                {
                    "id": "known-id",
                    "name": "Known Challenge",
                    "category": "misc",
                    "difficulty": "easy",
                    "infra_type": "static",
                }
            ],
        )
        registry = ChallengeRegistry(str(registry_path))
        output_dir = str(tmp_path / "out")

        result = _convert_online_rl_data(
            str(src),
            output_dir,
            registry=registry,
            drop_unresolved_registry_samples=True,
        )
        import jsonlines

        with jsonlines.open(result) as reader:
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["challenge_id"] == "known-id"

    def test_drop_static_challenges_filters_static_infra(self, tmp_path):
        """Samples with infra_type='static' should be dropped when flag is set."""
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(
            src,
            samples=[
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {"role": "user", "content": "Docker challenge"},
                    ],
                    "ground_truth_flag": "FLAG{docker}",
                    "metadata": {"challenge_id": "docker-chall"},
                },
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {"role": "user", "content": "Static challenge"},
                    ],
                    "ground_truth_flag": "FLAG{static}",
                    "metadata": {"challenge_id": "static-chall"},
                },
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {"role": "user", "content": "Another docker challenge"},
                    ],
                    "ground_truth_flag": "FLAG{docker2}",
                    "metadata": {"challenge_id": "docker-chall-2"},
                },
            ],
        )
        registry_path = tmp_path / "registry.yaml"
        self._write_registry(
            registry_path,
            challenges=[
                {
                    "id": "docker-chall",
                    "name": "Docker Challenge",
                    "category": "web",
                    "difficulty": "easy",
                    "infra_type": "docker",
                    "port": 8080,
                },
                {
                    "id": "static-chall",
                    "name": "Static Challenge",
                    "category": "crypto",
                    "difficulty": "easy",
                    "infra_type": "static",
                },
                {
                    "id": "docker-chall-2",
                    "name": "Docker Challenge 2",
                    "category": "pwn",
                    "difficulty": "medium",
                    "infra_type": "docker",
                    "port": 1337,
                },
            ],
        )
        registry = ChallengeRegistry(str(registry_path))
        output_dir = str(tmp_path / "out")

        result = _convert_online_rl_data(
            str(src),
            output_dir,
            registry=registry,
            drop_static_challenges=True,
        )
        import jsonlines

        with jsonlines.open(result) as reader:
            rows = list(reader)

        assert len(rows) == 2
        ids = {row["challenge_id"] for row in rows}
        assert "docker-chall" in ids
        assert "docker-chall-2" in ids
        assert "static-chall" not in ids

    def test_drop_static_challenges_disabled_keeps_all(self, tmp_path):
        """When drop_static_challenges=False, static samples should be kept."""
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(
            src,
            samples=[
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {"role": "user", "content": "Static challenge"},
                    ],
                    "ground_truth_flag": "FLAG{static}",
                    "metadata": {"challenge_id": "static-chall"},
                },
            ],
        )
        registry_path = tmp_path / "registry.yaml"
        self._write_registry(
            registry_path,
            challenges=[
                {
                    "id": "static-chall",
                    "name": "Static Challenge",
                    "category": "crypto",
                    "difficulty": "easy",
                    "infra_type": "static",
                },
            ],
        )
        registry = ChallengeRegistry(str(registry_path))
        output_dir = str(tmp_path / "out")

        result = _convert_online_rl_data(
            str(src),
            output_dir,
            registry=registry,
            drop_static_challenges=False,
        )
        import jsonlines

        with jsonlines.open(result) as reader:
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["challenge_id"] == "static-chall"

    def test_registry_resolves_alias_to_canonical_id(self, tmp_path):
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(
            src,
            samples=[
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {"role": "user", "content": "Alias challenge"},
                    ],
                    "ground_truth_flag": "FLAG{x}",
                    "metadata": {"challenge_id": "[Very Easy] eval-me"},
                }
            ],
        )
        registry_path = tmp_path / "registry.yaml"
        self._write_registry(
            registry_path,
            challenges=[
                {
                    "id": "eval-me",
                    "name": "[Very Easy] eval-me",
                    "aliases": ["EvalMe"],
                    "category": "misc",
                    "difficulty": "very_easy",
                    "infra_type": "docker",
                    "port": 32805,
                }
            ],
        )
        registry = ChallengeRegistry(str(registry_path))
        output_dir = str(tmp_path / "out")

        result = _convert_online_rl_data(
            str(src),
            output_dir,
            registry=registry,
            drop_unresolved_registry_samples=True,
        )
        import jsonlines

        with jsonlines.open(result) as reader:
            row = next(iter(reader))

        assert row["challenge_id"] == "eval-me"
        assert row["target"] == "http://localhost:32805"

    def test_registry_flag_mismatch_raises_when_enabled(self, tmp_path):
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(
            src,
            samples=[
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {"role": "user", "content": "Challenge A"},
                    ],
                    "ground_truth_flag": "FLAG{dataset}",
                    "metadata": {"challenge_id": "known-id"},
                }
            ],
        )
        registry_path = tmp_path / "registry.yaml"
        self._write_registry(
            registry_path,
            challenges=[
                {
                    "id": "known-id",
                    "name": "Known Challenge",
                    "category": "misc",
                    "difficulty": "easy",
                    "infra_type": "docker",
                    "port": 32801,
                    "ground_truth_flag": "FLAG{registry}",
                }
            ],
        )
        registry = ChallengeRegistry(str(registry_path))

        with pytest.raises(ValueError, match="mismatches registry"):
            _convert_online_rl_data(
                str(src),
                str(tmp_path / "out"),
                registry=registry,
                fail_on_flag_mismatch=True,
            )

    def test_registry_flag_mismatch_uses_registry_when_not_failing(self, tmp_path):
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(
            src,
            samples=[
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {"role": "user", "content": "Challenge A"},
                    ],
                    "ground_truth_flag": "FLAG{dataset}",
                    "metadata": {"challenge_id": "known-id"},
                }
            ],
        )
        registry_path = tmp_path / "registry.yaml"
        self._write_registry(
            registry_path,
            challenges=[
                {
                    "id": "known-id",
                    "name": "Known Challenge",
                    "category": "misc",
                    "difficulty": "easy",
                    "infra_type": "docker",
                    "port": 32801,
                    "ground_truth_flag": "FLAG{registry}",
                }
            ],
        )
        registry = ChallengeRegistry(str(registry_path))

        result = _convert_online_rl_data(
            str(src),
            str(tmp_path / "out"),
            registry=registry,
            fail_on_flag_mismatch=False,
        )
        import jsonlines

        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["ground_truth_flag"] == "FLAG{registry}"

    def test_missing_registry_flag_raises_when_enabled(self, tmp_path):
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(
            src,
            samples=[
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {"role": "user", "content": "Challenge A"},
                    ],
                    "ground_truth_flag": "FLAG{dataset}",
                    "metadata": {"challenge_id": "known-id"},
                }
            ],
        )
        registry_path = tmp_path / "registry.yaml"
        self._write_registry(
            registry_path,
            challenges=[
                {
                    "id": "known-id",
                    "name": "Known Challenge",
                    "category": "misc",
                    "difficulty": "easy",
                    "infra_type": "docker",
                    "port": 32801,
                }
            ],
        )
        registry = ChallengeRegistry(str(registry_path))

        with pytest.raises(ValueError, match="missing ground_truth_flag"):
            _convert_online_rl_data(
                str(src),
                str(tmp_path / "out"),
                registry=registry,
                fail_on_missing_registry_flag=True,
            )

    def test_require_all_registry_challenges_raises_when_missing(self, tmp_path):
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(
            src,
            samples=[
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {"role": "user", "content": "Challenge A"},
                    ],
                    "ground_truth_flag": "FLAG{a}",
                    "metadata": {"challenge_id": "chall-a"},
                }
            ],
        )
        registry_path = tmp_path / "registry.yaml"
        self._write_registry(
            registry_path,
            challenges=[
                {
                    "id": "chall-a",
                    "name": "Challenge A",
                    "category": "misc",
                    "difficulty": "easy",
                    "infra_type": "docker",
                    "port": 32801,
                    "ground_truth_flag": "FLAG{a}",
                },
                {
                    "id": "chall-b",
                    "name": "Challenge B",
                    "category": "misc",
                    "difficulty": "easy",
                    "infra_type": "docker",
                    "port": 32802,
                    "ground_truth_flag": "FLAG{b}",
                },
            ],
        )
        registry = ChallengeRegistry(str(registry_path))

        with pytest.raises(ValueError, match="missing registry challenges"):
            _convert_online_rl_data(
                str(src),
                str(tmp_path / "out"),
                registry=registry,
                require_all_registry_challenges=True,
            )


# ---------------------------------------------------------------------------
# _build_skyrl_config
# ---------------------------------------------------------------------------


class TestBuildSkyrlConfig:
    @pytest.fixture
    def config(self):
        return {
            "model": {"max_seq_length": 8192},
            "lora": {
                "r": 64,
                "alpha": 128,
                "dropout": 0.0,
                "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
            },
            "online_rl": {
                "learning_rate": 5e-6,
                "num_generations": 4,
                "max_completion_length": 4096,
                "max_tool_calling_iterations": 15,
                "batch_size": 1,
                "epochs": 1,
                "beta": 0.001,
            },
            "output": {"save_steps": 50, "report_to": "none"},
        }

    def test_returns_dict(self, config):
        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        assert isinstance(result, dict)

    def test_data_train_data_nesting(self, config):
        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        assert "data" in result
        assert "train_data" in result["data"]
        assert result["data"]["train_data"] == ["/data.jsonl"]

    def test_trainer_policy_model_path(self, config):
        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        assert result["trainer"]["policy"]["model"]["path"] == "/path/to/model"

    def test_trainer_policy_optimizer_lr(self, config):
        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        assert result["trainer"]["policy"]["optimizer_config"]["lr"] == 5e-6

    def test_trainer_algorithm_default(self, config):
        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        algo = result["trainer"]["algorithm"]
        assert algo["advantage_estimator"] == "rloo"

    def test_generator_sampling_params(self, config):
        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        sp = result["generator"]["sampling_params"]
        assert sp["max_generate_length"] == 4096  # From fixture's max_completion_length
        assert sp["temperature"] == 1.0
        assert sp["top_p"] == 0.95
        assert "additional_kwargs" not in sp

    def test_generator_n_samples(self, config):
        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        # n_samples_per_prompt comes from config's num_generations (4 in fixture)
        assert result["generator"]["n_samples_per_prompt"] == 4

    def test_generator_weight_sync_backend_local_defaults_nccl(self, config):
        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        assert result["generator"]["run_engines_locally"] is True
        assert result["generator"]["weight_sync_backend"] == "nccl"

    def test_generator_max_turns(self, config):
        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        assert result["generator"]["max_turns"] == 15

    def test_policy_loss_type_prefers_explicit_over_legacy_alias(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"]["policy_loss_type"] = "starpo"
        cfg["online_rl"]["loss_type"] = "dapo"
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        assert result["trainer"]["algorithm"]["policy_loss_type"] == "starpo"

    def test_policy_loss_type_maps_legacy_dapo_alias(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"].pop("policy_loss_type", None)
        cfg["online_rl"]["loss_type"] = "dapo"
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        assert result["trainer"]["algorithm"]["policy_loss_type"] == "regular"

    def test_generator_tool_call_format_propagates_from_config(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"]["tool_call_format"] = "qwen3_coder"
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        assert result["generator"]["tool_call_format"] == "qwen3_coder"

    def test_generator_max_turns_invalid_falls_back(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"]["max_tool_calling_iterations"] = 0
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        assert result["generator"]["max_turns"] == 15

    def test_vllm_model_len_respects_prompt_plus_completion(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["model"]["max_seq_length"] = 131072
        cfg["online_rl"]["max_prompt_length"] = 6000
        cfg["online_rl"]["max_completion_length"] = 3000
        # Intentionally too small; builder should bump to prompt+completion.
        cfg["online_rl"]["vllm_max_model_len"] = 7000
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        assert result["generator"]["engine_init_kwargs"]["max_model_len"] == 9000

    def test_inference_parallel_sizes_propagate(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"]["inference_engine_tensor_parallel_size"] = 2
        cfg["online_rl"]["inference_engine_pipeline_parallel_size"] = 1
        cfg["online_rl"]["inference_engine_data_parallel_size"] = 3
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        gen = result["generator"]
        assert gen["inference_engine_tensor_parallel_size"] == 2
        assert gen["inference_engine_pipeline_parallel_size"] == 1
        assert gen["inference_engine_data_parallel_size"] == 3

    def test_max_env_workers_is_configurable(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"]["max_env_workers"] = 40
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        assert result["environment"]["skyrl_gym"]["max_env_workers"] == 40

    def test_generator_server_mode_without_url_uses_local_non_colocate(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"]["vllm_mode"] = "server"
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        assert result["trainer"]["placement"]["colocate_all"] is False
        assert result["generator"]["run_engines_locally"] is True
        assert result["generator"]["weight_sync_backend"] == "nccl"

    def test_generator_remote_vllm_with_lora_falls_back_to_local(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"]["vllm_server_url"] = "http://127.0.0.1:9000"
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        assert result["trainer"]["placement"]["colocate_all"] is False
        assert result["generator"]["run_engines_locally"] is True
        assert result["generator"]["weight_sync_backend"] == "nccl"
        assert result["generator"]["remote_inference_engine_urls"] == ["127.0.0.1:8001"]
        assert result["generator"]["sampling_params"]["logprobs"] == 0

    def test_custom_chat_template_forces_logprobs_none(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"]["chat_template"] = "qwen3_without_thinking"
        cfg["online_rl"]["logprobs"] = 0
        cfg["online_rl"]["eval_logprobs"] = 0
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        assert result["generator"]["sampling_params"]["logprobs"] is None
        assert result["generator"]["eval_sampling_params"]["logprobs"] is None

    def test_native_tool_schemas_injected_by_default(self, config):
        """Without custom chat_template, tools should be in chat_template_kwargs."""
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"].pop("chat_template", None)
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        kwargs = result["generator"]["chat_template_kwargs"]
        assert "tools" in kwargs, "Native tools should be in chat_template_kwargs"
        assert isinstance(kwargs["tools"], list)
        assert len(kwargs["tools"]) > 0
        # First tool should be shell_command
        assert kwargs["tools"][0]["function"]["name"] == "shell_command"
        # native_tool_schemas flag should be in generator for env propagation
        assert result["generator"]["native_tool_schemas"] is True

    def test_native_tool_schemas_auto_downgraded_with_custom_template(self, config):
        """With custom chat_template, native_tool_schemas auto-downgrades to False.

        SkyRL's custom templates (qwen3_without_thinking, qwen3_with_thinking)
        do NOT have a {% if tools %} block.  Passing tools via
        chat_template_kwargs would silently drop them.  The guard in runtime.py
        auto-downgrades to native_tool_schemas=False so the env uses text
        injection via _inject_tool_schemas() instead.  See Issue #38.
        """
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"]["chat_template"] = "qwen3_without_thinking"
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        kwargs = result["generator"]["chat_template_kwargs"]
        assert "tools" not in kwargs, (
            "Custom chat_template should auto-downgrade native_tool_schemas "
            "— tools must NOT be in chat_template_kwargs (template ignores them)"
        )
        assert result["generator"]["native_tool_schemas"] is False

    def test_native_tool_schemas_explicit_override(self, config):
        """Explicit native_tool_schemas=false should skip injection."""
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"]["native_tool_schemas"] = False
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        kwargs = result["generator"]["chat_template_kwargs"]
        assert "tools" not in kwargs
        assert result["generator"]["native_tool_schemas"] is False

    def test_generator_remote_vllm_without_lora_uses_broadcast_sync(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["lora"]["r"] = 0
        cfg["online_rl"]["vllm_server_url"] = "https://127.0.0.1:9000/"
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        assert result["trainer"]["placement"]["colocate_all"] is False
        assert result["generator"]["run_engines_locally"] is False
        assert result["generator"]["weight_sync_backend"] == "broadcast"
        assert result["generator"]["remote_inference_engine_urls"] == ["127.0.0.1:9000"]
        assert result["generator"]["sampling_params"]["logprobs"] is None

    def test_environment_env_class(self, config):
        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        assert result["environment"]["env_class"] == "trajgym"

    def test_lora_config_nested(self, config):
        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        lora = result["trainer"]["policy"]["model"]["lora"]
        assert lora["rank"] == 64
        assert lora["alpha"] == 128
        assert lora["dropout"] == 0.0
        assert lora["target_modules"] == ["q_proj", "k_proj", "v_proj", "o_proj"]

    def test_lora_target_modules_string_passthrough(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["lora"]["target_modules"] = "q_proj,k_proj"
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        lora = result["trainer"]["policy"]["model"]["lora"]
        assert lora["target_modules"] == ["q_proj", "k_proj"]

    def test_lora_target_modules_default_all_linear(self):
        cfg = {
            "model": {"max_seq_length": 4096},
            "lora": {"r": 32, "alpha": 64, "dropout": 0.0},
            "online_rl": {"batch_size": 1, "epochs": 1, "num_generations": 2},
            "output": {"save_steps": 50},
        }
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        lora = result["trainer"]["policy"]["model"]["lora"]
        assert lora["target_modules"] == "all-linear"

    def test_kl_loss_enabled_when_beta_positive(self, config):
        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        algo = result["trainer"]["algorithm"]
        assert algo["use_kl_loss"] is True
        assert algo["kl_loss_coef"] == 0.001

    def test_algorithm_clip_range_uses_grpo_config(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"]["epsilon_low"] = 0.15
        cfg["online_rl"]["epsilon_high"] = 0.28
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        algo = result["trainer"]["algorithm"]
        assert algo["eps_clip_low"] == 0.15
        assert algo["eps_clip_high"] == 0.28

    def test_algorithm_clip_high_defaults_to_low_when_unspecified(self, config):
        cfg = json.loads(json.dumps(config))
        cfg["online_rl"]["epsilon_low"] = 0.12
        cfg["online_rl"].pop("epsilon_high", None)
        result = _build_skyrl_config("/path/to/model", "/out", cfg, "/data.jsonl")
        algo = result["trainer"]["algorithm"]
        assert algo["eps_clip_low"] == 0.12
        assert algo["eps_clip_high"] == 0.12

    def test_missing_grpo_section_uses_defaults(self):
        """Config without online RL section should still produce valid output."""
        config = {
            "model": {"max_seq_length": 4096},
            "lora": {
                "r": 32,
                "alpha": 64,
                "dropout": 0.0,
                "target_modules": ["q_proj"],
            },
            "output": {"save_steps": 100},
        }
        result = _build_skyrl_config("/model", "/out", config, "/data.jsonl")
        assert isinstance(result, dict)
        assert "trainer" in result
        assert "generator" in result
        # Should have sensible defaults for Online RL params
        assert result["generator"]["n_samples_per_prompt"] >= 1

    def test_environment_env_class_always_trajgym(self):
        """env_class should always be 'trajgym' regardless of config."""
        config = {
            "model": {"max_seq_length": 4096},
            "lora": {
                "r": 32,
                "alpha": 64,
                "dropout": 0.0,
                "target_modules": ["q_proj"],
            },
            "online_rl": {"batch_size": 1, "epochs": 1, "num_generations": 2},
            "output": {"save_steps": 50},
        }
        result = _build_skyrl_config("/model", "/out", config, "/data.jsonl")
        assert result["environment"]["env_class"] == "trajgym"

    def test_ref_fsdp_wrap_policy_uses_transformer_layer_class(
        self, monkeypatch, config
    ):
        import transformers

        class DummyCfg:
            architectures = ["LlamaForCausalLM"]

        class DummyAutoConfig:
            @staticmethod
            def from_pretrained(*args, **kwargs):
                return DummyCfg()

        monkeypatch.setattr(transformers, "AutoConfig", DummyAutoConfig)

        result = _build_skyrl_config("/path/to/model", "/out", config, "/data.jsonl")
        ref_wrap = result["trainer"]["ref"]["fsdp_config"]["wrap_policy"]
        assert ref_wrap["transformer_layer_cls_to_wrap"] == ["LlamaDecoderLayer"]


class TestInferenceBackendSelection:
    def test_force_legacy_for_text_config(self, monkeypatch):
        import transformers

        class Qwen3_5TextConfig:
            pass

        class DummyAutoConfig:
            @staticmethod
            def from_pretrained(*args, **kwargs):
                return Qwen3_5TextConfig()

        monkeypatch.setattr(transformers, "AutoConfig", DummyAutoConfig)
        assert _should_force_legacy_inference("/model") is True

    def test_keep_new_inference_for_standard_config(self, monkeypatch):
        import transformers

        class LlamaConfig:
            pass

        class DummyAutoConfig:
            @staticmethod
            def from_pretrained(*args, **kwargs):
                return LlamaConfig()

        monkeypatch.setattr(transformers, "AutoConfig", DummyAutoConfig)
        assert _should_force_legacy_inference("/model") is False

    def test_config_probe_failure_does_not_force_legacy(self, monkeypatch):
        import transformers

        class DummyAutoConfig:
            @staticmethod
            def from_pretrained(*args, **kwargs):
                raise RuntimeError("boom")

        monkeypatch.setattr(transformers, "AutoConfig", DummyAutoConfig)
        assert _should_force_legacy_inference("/model") is False


class TestModelPathResolution:
    def test_text_wrapper_switches_to_sibling_vllm_path(self, monkeypatch, tmp_path):
        import transformers

        base_path = tmp_path / "model"
        vllm_path = tmp_path / "model_vllm"
        base_path.mkdir()
        vllm_path.mkdir()

        class Qwen3_5TextConfig:
            model_type = "qwen3_5_text"

        class Qwen3_5Config:
            model_type = "qwen3_5"

        class DummyAutoConfig:
            @staticmethod
            def from_pretrained(path, **kwargs):
                if str(path).endswith("_vllm"):
                    return Qwen3_5Config()
                return Qwen3_5TextConfig()

        monkeypatch.setattr(transformers, "AutoConfig", DummyAutoConfig)
        resolved = _resolve_vllm_ready_model_path(str(base_path))
        assert resolved == str(vllm_path)

    def test_non_text_wrapper_keeps_original_path(self, monkeypatch):
        import transformers

        class LlamaConfig:
            model_type = "llama"

        class DummyAutoConfig:
            @staticmethod
            def from_pretrained(*args, **kwargs):
                return LlamaConfig()

        monkeypatch.setattr(transformers, "AutoConfig", DummyAutoConfig)
        assert _resolve_vllm_ready_model_path("/model") == "/model"

    def test_text_wrapper_without_sibling_keeps_original_path(self, monkeypatch):
        import transformers

        class Qwen3_5TextConfig:
            model_type = "qwen3_5_text"

        class DummyAutoConfig:
            @staticmethod
            def from_pretrained(*args, **kwargs):
                return Qwen3_5TextConfig()

        monkeypatch.setattr(transformers, "AutoConfig", DummyAutoConfig)
        assert _resolve_vllm_ready_model_path("/model") == "/model"


class TestTargetExtraction:
    def test_target_from_user_message(self, tmp_path):
        """Target URL should be extracted from user message content."""
        src = tmp_path / "with_target.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {
                            "role": "user",
                            "content": "Solve the challenge at http://localhost:32801",
                        },
                        {"role": "assistant", "content": "Scanning..."},
                    ],
                    "ground_truth_flag": "FLAG{target_test}",
                    "metadata": {"challenge_id": "eval-me", "task_type": "ctf"},
                }
            )
        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(str(src), output_dir)
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["target"] == "http://localhost:32801"

    def test_no_target_produces_none(self, tmp_path):
        """File-based challenges without URLs should have target=None."""
        src = tmp_path / "no_target.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "You are a CTF agent."},
                        {"role": "user", "content": "Decrypt the ciphertext."},
                    ],
                    "ground_truth_flag": "FLAG{crypto}",
                    "metadata": {"challenge_id": "Dynastic", "task_type": "ctf"},
                }
            )
        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(str(src), output_dir)
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["target"] is None

    def test_challenge_id_fallback_to_challenge(self, tmp_path):
        """challenge_id should fall back to metadata.challenge if challenge_id missing."""
        src = tmp_path / "fallback.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {"role": "user", "content": "Solve it."},
                    ],
                    "ground_truth_flag": "FLAG{fb}",
                    "metadata": {"challenge": "eval-me", "task_type": "ctf"},
                }
            )
        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(str(src), output_dir)
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["challenge_id"] == "eval-me"

    def test_target_from_metadata_fallback(self, tmp_path):
        """If no URL in user message, target should come from metadata."""
        src = tmp_path / "meta_target.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {"role": "user", "content": "Solve the challenge."},
                    ],
                    "ground_truth_flag": "FLAG{mt}",
                    "metadata": {"target": "http://localhost:9999", "task_type": "ctf"},
                }
            )
        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(str(src), output_dir)
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["target"] == "http://localhost:9999"


class TestConvertOnlineRLDataEdgeCases:
    def test_data_without_ground_truth_flag(self, tmp_path):
        """Samples without ground_truth_flag should still convert."""
        src = tmp_path / "no_flag.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {"role": "user", "content": "Scan the target."},
                    ],
                    "metadata": {"optimal_steps": 3},
                }
            )
        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(str(src), output_dir)
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        # Should have a prompt and env_class even without flag
        assert "prompt" in row
        assert row["env_class"] == "trajgym"

    def test_data_with_empty_metadata(self, tmp_path):
        """Samples with empty metadata dict should convert."""
        src = tmp_path / "empty_meta.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {"role": "user", "content": "Find the flag."},
                    ],
                    "ground_truth_flag": "FLAG{empty_meta}",
                    "metadata": {},
                }
            )
        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(str(src), output_dir)
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["ground_truth_flag"] == "FLAG{empty_meta}"


class TestRegistryIntegration:
    """Test _convert_online_rl_data with ChallengeRegistry integration."""

    def _make_registry(self, tmp_path):
        """Create a simple test registry."""
        import yaml

        registry_data = {
            "challenges": [
                {
                    "id": "eval-me",
                    "category": "misc",
                    "difficulty": "very_easy",
                    "infra_type": "docker",
                    "port": 32805,
                },
                {
                    "id": "Dynastic",
                    "category": "crypto",
                    "difficulty": "very_easy",
                    "infra_type": "static",
                },
            ]
        }
        path = tmp_path / "test_registry.yaml"
        with open(path, "w") as f:
            yaml.dump(registry_data, f)
        from trajgym.challenges.registry import ChallengeRegistry

        return ChallengeRegistry(str(path))

    @staticmethod
    def _write_registry(path: Path, challenges: list[dict]) -> ChallengeRegistry:
        path.write_text(yaml.safe_dump({"challenges": challenges}))
        return ChallengeRegistry(str(path))

    def test_registry_provides_target_when_missing(self, tmp_path):
        """Registry should provide target URL when not in user message."""
        registry = self._make_registry(tmp_path)

        src = tmp_path / "online_rl.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {"role": "user", "content": "Solve the eval-me challenge."},
                    ],
                    "ground_truth_flag": "FLAG{eval}",
                    "metadata": {"challenge_id": "eval-me"},
                }
            )

        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(str(src), output_dir, registry=registry)
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["target"] == "http://localhost:32805"

    def test_url_in_message_takes_precedence_over_registry(self, tmp_path):
        """If URL is in user message, it should override registry."""
        registry = self._make_registry(tmp_path)

        src = tmp_path / "online_rl.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {"role": "user", "content": "Solve at http://localhost:9999"},
                    ],
                    "ground_truth_flag": "FLAG{override}",
                    "metadata": {"challenge_id": "eval-me"},
                }
            )

        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(str(src), output_dir, registry=registry)
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["target"] == "http://localhost:9999"  # Message URL wins

    def test_prefer_registry_target_overrides_message_url(self, tmp_path):
        """When enabled, registry target should replace stale in-message URLs."""
        registry = self._make_registry(tmp_path)

        src = tmp_path / "online_rl.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {"role": "user", "content": "Solve at http://localhost:9999"},
                    ],
                    "ground_truth_flag": "FLAG{override}",
                    "metadata": {"challenge_id": "eval-me"},
                }
            )

        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(
            str(src),
            output_dir,
            registry=registry,
            prefer_registry_target=True,
        )
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["target"] == "http://localhost:32805"

    def test_converter_strips_legacy_non_neutral_prompt_sections(self, tmp_path):
        """Legacy quickstart/recon injected sections must be removed."""
        registry = self._make_registry(tmp_path)

        src = tmp_path / "online_rl.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {
                            "role": "user",
                            "content": (
                                "**Connection**: http://localhost:9999\n"
                                "# WEB RECON CHECKLIST\n"
                                "- Keep reasoning brief.\n"
                                "# WEB EXPLOIT PLAYBOOK\n"
                                "- Use /api/options then /api/monitor.\n"
                                "# CHALLENGE QUICKSTART (HIGH PRIORITY)\n"
                                "- Run exact one-liner exploit.\n"
                                "# TOOL USAGE\n"
                                "- Continue normal execution."
                            ),
                        },
                    ],
                    "ground_truth_flag": "FLAG{override}",
                    "metadata": {"challenge_id": "eval-me"},
                }
            )

        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(
            str(src),
            output_dir,
            registry=registry,
            prefer_registry_target=True,
        )
        with jsonlines.open(result) as reader:
            row = next(iter(reader))

        user_prompt = row["prompt"][1]["content"]
        assert row["target"] == "http://localhost:32805"
        assert "http://localhost:32805" in user_prompt
        assert "# WEB RECON CHECKLIST" not in user_prompt
        assert "# WEB EXPLOIT PLAYBOOK" not in user_prompt
        assert "# CHALLENGE QUICKSTART (HIGH PRIORITY)" not in user_prompt
        assert "/api/options" not in user_prompt
        assert "/api/monitor" not in user_prompt
        assert "# TOOL USAGE" in user_prompt

    def test_target_host_override_applies_to_raw_host_port_target(self, tmp_path):
        """Host override should rewrite raw host:port targets (crypto/pwn)."""
        src = tmp_path / "online_rl.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {
                            "role": "user",
                            "content": "Connect to localhost:32824 and solve.",
                        },
                    ],
                    "ground_truth_flag": "FLAG{crypto}",
                    "metadata": {
                        "challenge_id": "crypto-raw",
                        "category": "crypto",
                        "target": "localhost:32824",
                    },
                }
            )

        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(
            str(src),
            output_dir,
            target_host_override="172.17.0.1",
        )
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["target"] == "172.17.0.1:32824"

    def test_target_port_offset_applies_to_raw_host_port_target(self, tmp_path):
        """Port offset should rewrite raw host:port targets (crypto/pwn)."""
        src = tmp_path / "online_rl.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {
                            "role": "user",
                            "content": "Connect to localhost:32824 and solve.",
                        },
                    ],
                    "ground_truth_flag": "FLAG{crypto}",
                    "metadata": {
                        "challenge_id": "crypto-raw",
                        "category": "crypto",
                        "target": "localhost:32824",
                    },
                }
            )

        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(
            str(src),
            output_dir,
            target_host_override="172.17.0.1",
            target_port_offset=100,
        )
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["target"] == "172.17.0.1:32924"

    def test_static_challenge_gets_file_target_from_registry(self, tmp_path):
        """Static challenges should get file:///root/challenge/ target (not localhost)."""
        registry = self._make_registry(tmp_path)

        src = tmp_path / "online_rl.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {"role": "user", "content": "Solve the crypto puzzle."},
                    ],
                    "ground_truth_flag": "FLAG{dyn}",
                    "metadata": {"challenge_id": "Dynastic"},
                }
            )

        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(str(src), output_dir, registry=registry)
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert (
            row["target"] == "file:///root/challenge/"
        )  # Static = local workspace, not network

    def test_unknown_challenge_in_registry_returns_none(self, tmp_path):
        """Challenge not in registry should not crash, target stays None."""
        registry = self._make_registry(tmp_path)

        src = tmp_path / "online_rl.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {"role": "user", "content": "Solve it."},
                    ],
                    "ground_truth_flag": "FLAG{unk}",
                    "metadata": {"challenge_id": "unknown-challenge"},
                }
            )

        output_dir = str(tmp_path / "out")
        result = _convert_online_rl_data(str(src), output_dir, registry=registry)
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["target"] is None

    def test_registry_target_override_used_by_converter(self, tmp_path):
        registry = self._make_registry(tmp_path)
        registry.set_target_overrides({"eval-me": "http://localhost:43012"})

        src = tmp_path / "online_rl.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            w.write(
                {
                    "messages": [
                        {"role": "system", "content": "Agent."},
                        {"role": "user", "content": "Solve eval-me."},
                    ],
                    "ground_truth_flag": "FLAG{eval}",
                    "metadata": {"challenge_id": "eval-me"},
                }
            )

        result = _convert_online_rl_data(
            str(src), str(tmp_path / "out"), registry=registry
        )
        with jsonlines.open(result) as reader:
            row = next(iter(reader))
        assert row["target"] == "http://localhost:43012"

    def test_convert_raises_when_target_collisions_enabled(self, tmp_path):
        registry = self._write_registry(
            tmp_path / "registry.yaml",
            challenges=[
                {
                    "id": "a",
                    "name": "Alpha",
                    "category": "misc",
                    "difficulty": "easy",
                    "infra_type": "docker",
                    "port": 1337,
                },
                {
                    "id": "b",
                    "name": "Beta",
                    "category": "misc",
                    "difficulty": "easy",
                    "infra_type": "docker",
                    "port": 1337,
                },
            ],
        )
        src = tmp_path / "online_rl.jsonl"
        import jsonlines

        with jsonlines.open(str(src), "w") as w:
            for challenge_id in ("a", "b"):
                w.write(
                    {
                        "messages": [
                            {"role": "system", "content": "Agent."},
                            {"role": "user", "content": f"Solve {challenge_id}."},
                        ],
                        "ground_truth_flag": "FLAG{x}",
                        "metadata": {"challenge_id": challenge_id},
                    }
                )

        with pytest.raises(ValueError, match="Target URL collisions detected"):
            _convert_online_rl_data(
                str(src),
                str(tmp_path / "out"),
                registry=registry,
                fail_on_target_collisions=True,
            )


class TestRuntimeGuards:
    def test_is_qwen3_5_config_detects_model_type(self):
        class _Cfg:
            model_type = "qwen3_5"
            architectures = []

        assert _is_qwen3_5_config(_Cfg()) is True

    def test_is_qwen3_5_config_detects_architecture(self):
        class _Cfg:
            model_type = "custom"
            architectures = ["Qwen3_5ForConditionalGeneration"]

        assert _is_qwen3_5_config(_Cfg()) is True

    def test_validate_qwen3_5_runtime_dependencies_raises_when_missing(
        self, monkeypatch
    ):
        import trajgym.training.online_rl._utils as utils_mod

        class _Cfg:
            model_type = "qwen3_5"
            architectures = ["Qwen3_5ForConditionalGeneration"]

        monkeypatch.setattr(
            utils_mod,
            "_missing_qwen3_5_fast_path_deps",
            lambda: ["flash-linear-attention (module: fla)", "causal-conv1d"],
        )

        with pytest.raises(RuntimeError, match="flash-linear-attention"):
            _validate_qwen3_5_runtime_dependencies(
                _Cfg(),
                {"require_fast_linear_attention": True},
            )

    def test_validate_qwen3_5_runtime_dependencies_allows_override(self, monkeypatch):
        import trajgym.training.online_rl._utils as utils_mod

        class _Cfg:
            model_type = "qwen3_5"
            architectures = ["Qwen3_5ForConditionalGeneration"]

        monkeypatch.setattr(
            utils_mod,
            "_missing_qwen3_5_fast_path_deps",
            lambda: ["flash-linear-attention (module: fla)"],
        )

        _validate_qwen3_5_runtime_dependencies(
            _Cfg(),
            {"require_fast_linear_attention": False},
        )

    def test_resolve_reward_config_defaults_to_empty_dict(self):
        assert _resolve_reward_config({}) == {}

    def test_resolve_reward_config_rejects_non_dict(self):
        with pytest.raises(TypeError, match="config\\['reward'\\] must be a dict"):
            _resolve_reward_config({"reward": "bad"})


class TestStepWiseIndexGuardValidation:
    def test_has_guard_detects_bounded_assignment(self):
        source = """
if 0 <= resp_end_idx < len(per_token_reward):
    per_token_reward[resp_end_idx] = float(reward)
"""
        assert _has_step_wise_resp_index_guard(source) is True

    def test_has_guard_rejects_bare_assignment(self):
        source = "per_token_reward[resp_end_idx] = float(reward)"
        assert _has_step_wise_resp_index_guard(source) is False

    def test_validate_guard_raises_when_missing(self, monkeypatch, tmp_path):
        source = tmp_path / "skyrl_gym_generator.py"
        source.write_text("per_token_reward[resp_end_idx] = float(reward)\n")

        class _Spec:
            origin = str(source)

        monkeypatch.setattr(
            "importlib.util.find_spec", lambda *_args, **_kwargs: _Spec()
        )

        with pytest.raises(RuntimeError, match="step-wise reward index guard"):
            _validate_step_wise_resp_index_guard(
                {"require_step_wise_index_guard": True},
                step_wise_trajectories=True,
            )

    def test_validate_guard_allows_override(self, monkeypatch, tmp_path):
        source = tmp_path / "skyrl_gym_generator.py"
        source.write_text("per_token_reward[resp_end_idx] = float(reward)\n")

        class _Spec:
            origin = str(source)

        monkeypatch.setattr(
            "importlib.util.find_spec", lambda *_args, **_kwargs: _Spec()
        )

        _validate_step_wise_resp_index_guard(
            {"require_step_wise_index_guard": False},
            step_wise_trajectories=True,
        )

    def test_validate_guard_skips_when_step_wise_disabled(self):
        _validate_step_wise_resp_index_guard({}, step_wise_trajectories=False)


# ---------------------------------------------------------------------------
# Difficulty Curriculum Filtering
# ---------------------------------------------------------------------------


class TestDifficultyCurriculum:
    """Tests for difficulty-based sample filtering in _convert_online_rl_data."""

    @staticmethod
    def _write_registry(path: Path, challenges: list[dict]) -> ChallengeRegistry:
        path.write_text(yaml.safe_dump({"challenges": challenges}))
        return ChallengeRegistry(str(path))

    @staticmethod
    def _make_challenges():
        """Create challenges at each difficulty level."""
        return [
            {
                "id": "ch-very-easy",
                "name": "VE",
                "category": "misc",
                "difficulty": "very_easy",
                "infra_type": "static",
            },
            {
                "id": "ch-easy",
                "name": "Easy",
                "category": "misc",
                "difficulty": "easy",
                "infra_type": "static",
            },
            {
                "id": "ch-medium",
                "name": "Med",
                "category": "misc",
                "difficulty": "medium",
                "infra_type": "static",
            },
            {
                "id": "ch-hard",
                "name": "Hard",
                "category": "misc",
                "difficulty": "hard",
                "infra_type": "static",
            },
            {
                "id": "ch-expert",
                "name": "Exp",
                "category": "misc",
                "difficulty": "expert",
                "infra_type": "static",
            },
            {
                "id": "ch-master",
                "name": "Mst",
                "category": "misc",
                "difficulty": "master",
                "infra_type": "static",
            },
        ]

    @staticmethod
    def _make_samples(challenge_ids):
        """Create minimal Online RL samples for given challenge IDs."""
        return [
            {
                "messages": [
                    {"role": "system", "content": "Agent."},
                    {"role": "user", "content": f"Solve {cid}."},
                ],
                "ground_truth_flag": f"FLAG{{{cid}}}",
                "metadata": {"challenge_id": cid},
            }
            for cid in challenge_ids
        ]

    def test_no_filter_keeps_all(self, tmp_path):
        """When no difficulty filter is set, all samples pass through."""
        registry = self._write_registry(tmp_path / "reg.yaml", self._make_challenges())
        all_ids = [c["id"] for c in self._make_challenges()]
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src, self._make_samples(all_ids))

        result = _convert_online_rl_data(
            str(src), str(tmp_path / "out"), registry=registry
        )
        import jsonlines

        with jsonlines.open(result) as reader:
            rows = list(reader)
        assert len(rows) == 6

    def test_difficulty_max_filters_hard_challenges(self, tmp_path):
        """difficulty_max='medium' should drop hard, expert, master."""
        registry = self._write_registry(tmp_path / "reg.yaml", self._make_challenges())
        all_ids = [c["id"] for c in self._make_challenges()]
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src, self._make_samples(all_ids))

        result = _convert_online_rl_data(
            str(src),
            str(tmp_path / "out"),
            registry=registry,
            difficulty_max="medium",
        )
        import jsonlines

        with jsonlines.open(result) as reader:
            rows = list(reader)
        kept_ids = {r["challenge_id"] for r in rows}
        assert kept_ids == {"ch-very-easy", "ch-easy", "ch-medium"}
        assert len(rows) == 3

    def test_difficulty_min_filters_easy_challenges(self, tmp_path):
        """difficulty_min='hard' should drop very_easy, easy, medium."""
        registry = self._write_registry(tmp_path / "reg.yaml", self._make_challenges())
        all_ids = [c["id"] for c in self._make_challenges()]
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src, self._make_samples(all_ids))

        result = _convert_online_rl_data(
            str(src),
            str(tmp_path / "out"),
            registry=registry,
            difficulty_min="hard",
        )
        import jsonlines

        with jsonlines.open(result) as reader:
            rows = list(reader)
        kept_ids = {r["challenge_id"] for r in rows}
        assert kept_ids == {"ch-hard", "ch-expert", "ch-master"}
        assert len(rows) == 3

    def test_difficulty_range_filters_both_ends(self, tmp_path):
        """difficulty_min='easy', difficulty_max='hard' keeps easy/medium/hard."""
        registry = self._write_registry(tmp_path / "reg.yaml", self._make_challenges())
        all_ids = [c["id"] for c in self._make_challenges()]
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src, self._make_samples(all_ids))

        result = _convert_online_rl_data(
            str(src),
            str(tmp_path / "out"),
            registry=registry,
            difficulty_min="easy",
            difficulty_max="hard",
        )
        import jsonlines

        with jsonlines.open(result) as reader:
            rows = list(reader)
        kept_ids = {r["challenge_id"] for r in rows}
        assert kept_ids == {"ch-easy", "ch-medium", "ch-hard"}
        assert len(rows) == 3

    def test_invalid_difficulty_min_raises(self, tmp_path):
        """Invalid difficulty_min should raise ValueError."""
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src)
        with pytest.raises(ValueError, match="Invalid difficulty_min"):
            _convert_online_rl_data(
                str(src),
                str(tmp_path / "out"),
                difficulty_min="impossible",
            )

    def test_invalid_difficulty_max_raises(self, tmp_path):
        """Invalid difficulty_max should raise ValueError."""
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src)
        with pytest.raises(ValueError, match="Invalid difficulty_max"):
            _convert_online_rl_data(
                str(src),
                str(tmp_path / "out"),
                difficulty_max="impossible",
            )

    def test_inverted_range_raises(self, tmp_path):
        """difficulty_min harder than difficulty_max should raise."""
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src)
        with pytest.raises(ValueError, match="is harder than"):
            _convert_online_rl_data(
                str(src),
                str(tmp_path / "out"),
                difficulty_min="hard",
                difficulty_max="easy",
            )

    def test_without_registry_no_filtering(self, tmp_path):
        """Difficulty filter with no registry should keep all samples."""
        src = tmp_path / "online_rl.jsonl"
        _write_online_rl_jsonl(src)  # 2 default samples, no registry

        result = _convert_online_rl_data(
            str(src),
            str(tmp_path / "out"),
            difficulty_max="easy",
        )
        import jsonlines

        with jsonlines.open(result) as reader:
            rows = list(reader)
        assert len(rows) == 2  # All kept because no registry to look up difficulty

    def test_difficulty_order_constants(self):
        """Verify difficulty ordering is correct."""
        assert _DIFFICULTY_ORDER == [
            "very_easy",
            "easy",
            "medium",
            "hard",
            "expert",
            "master",
        ]
        assert _DIFFICULTY_RANK["very_easy"] < _DIFFICULTY_RANK["easy"]
        assert _DIFFICULTY_RANK["easy"] < _DIFFICULTY_RANK["medium"]
        assert _DIFFICULTY_RANK["medium"] < _DIFFICULTY_RANK["hard"]
        assert _DIFFICULTY_RANK["hard"] < _DIFFICULTY_RANK["expert"]
        assert _DIFFICULTY_RANK["expert"] < _DIFFICULTY_RANK["master"]


def test_run_skyrl_training_env_kwargs_include_tool_call_format():
    """Guard runtime wiring: generator.tool_call_format must reach env kwargs."""
    import inspect

    import trajgym.training.online_rl.runtime as runtime_mod

    source = inspect.getsource(runtime_mod._run_skyrl_training)
    assert 'env_kwargs["tool_call_format"] = tool_call_format' in source


class TestNativeToolSchemaIntegration:
    """End-to-end tests for the native tool schema integration pathway.

    Validates every layer: config → runtime → env_kwargs → env init → skip/inject.
    """

    def test_env_kwargs_propagates_native_flag(self):
        """_build_trajgym_env_kwargs reads native_tool_schemas from generator config."""
        import inspect

        import trajgym.training.online_rl.runtime as runtime_mod

        source = inspect.getsource(runtime_mod._run_skyrl_training)
        assert (
            '"native_tool_schemas"' in source
        ), "_build_trajgym_env_kwargs must include native_tool_schemas"

    def test_env_reads_native_flag_from_kwargs(self):
        """TrajGymTextEnv reads native_tool_schemas from kwargs."""
        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        env_on = TrajGymTextEnv(target="http://localhost", native_tool_schemas=True)
        assert env_on._native_tool_schemas is True

        env_off = TrajGymTextEnv(target="http://localhost", native_tool_schemas=False)
        assert env_off._native_tool_schemas is False

        env_default = TrajGymTextEnv(target="http://localhost")
        assert env_default._native_tool_schemas is False

    def test_env_reads_native_flag_from_extras(self):
        """TrajGymTextEnv reads native_tool_schemas from extras dict."""
        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        env = TrajGymTextEnv(
            target="http://localhost",
            extras={"native_tool_schemas": True},
        )
        assert env._native_tool_schemas is True

    def test_native_skips_injection_in_init(self):
        """When native_tool_schemas=True, init() does NOT inject text tools."""
        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        env = TrajGymTextEnv(target="http://localhost", native_tool_schemas=True)
        prompt = [{"role": "system", "content": "You are a CTF agent."}]
        result = env.init(prompt)
        injected = result[0] if isinstance(result, tuple) else result
        sys_content = injected[0]["content"]
        assert "# Available Tools" not in sys_content
        assert "shell_command" not in sys_content

    def test_default_injects_text_tools_in_init(self):
        """Default (native=False) should inject text tool schemas."""
        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        env = TrajGymTextEnv(target="http://localhost")
        prompt = [{"role": "system", "content": "You are a CTF agent."}]
        result = env.init(prompt)
        injected = result[0] if isinstance(result, tuple) else result
        sys_content = injected[0]["content"]
        assert "# Available Tools" in sys_content
        assert "shell_command" in sys_content

    def test_config_builds_tools_in_chat_template_kwargs(self):
        """_build_skyrl_config adds tools to chat_template_kwargs by default."""
        config = {
            "model": {"max_seq_length": 4096},
            "lora": {
                "r": 32,
                "alpha": 64,
                "dropout": 0.0,
                "target_modules": ["q_proj"],
            },
            "online_rl": {"batch_size": 1, "epochs": 1, "num_generations": 2},
            "output": {"save_steps": 50},
        }
        result = _build_skyrl_config("/model", "/out", config, "/data.jsonl")
        kwargs = result["generator"]["chat_template_kwargs"]
        tools = kwargs.get("tools", [])
        assert len(tools) > 0, "Tools should be injected into chat_template_kwargs"
        tool_names = [t["function"]["name"] for t in tools]
        assert "shell_command" in tool_names
        assert "read_file" in tool_names
        assert "flag_found" in tool_names
        assert result["generator"]["native_tool_schemas"] is True

    def test_tool_schemas_match_registry(self):
        """Tools in chat_template_kwargs must match tool_registry source of truth."""
        from trajgym.formatters.tool_registry import get_runtime_tools

        config = {
            "model": {"max_seq_length": 4096},
            "lora": {
                "r": 32,
                "alpha": 64,
                "dropout": 0.0,
                "target_modules": ["q_proj"],
            },
            "online_rl": {"batch_size": 1, "epochs": 1, "num_generations": 2},
            "output": {"save_steps": 50},
        }
        result = _build_skyrl_config("/model", "/out", config, "/data.jsonl")
        injected_tools = result["generator"]["chat_template_kwargs"]["tools"]
        registry_tools = get_runtime_tools()
        assert len(injected_tools) == len(registry_tools)
        for injected, registry in zip(injected_tools, registry_tools, strict=False):
            assert injected["function"]["name"] == registry["function"]["name"]

    def test_filename_alias_in_tool_executor(self, tmp_path):
        """ToolExecutor read_file accepts 'filename' alias (common model output)."""
        from trajgym.envs.tool_executor import SubprocessExecutor

        test_file = tmp_path / "test_fn.txt"
        test_file.write_text("content_via_filename\n")

        exe = SubprocessExecutor(max_steps=10, default_workdir=str(tmp_path))
        exe.reset()
        result = exe.step("read_file", {"filename": str(test_file)})
        assert "content_via_filename" in result["stdout"]
        assert result["exit_code"] == 0

    def test_all_read_file_aliases_work(self, tmp_path):
        """Every alias (file_path, path, file, filename) resolves correctly."""
        from trajgym.envs.tool_executor import SubprocessExecutor

        for alias in ["file_path", "path", "file", "filename"]:
            test_file = tmp_path / f"test_{alias}.txt"
            test_file.write_text(f"ok_{alias}\n")

            exe = SubprocessExecutor(max_steps=10, default_workdir=str(tmp_path))
            exe.reset()
            result = exe.step("read_file", {alias: str(test_file)})
            assert f"ok_{alias}" in result["stdout"], f"Alias '{alias}' failed"
            assert result["exit_code"] == 0
