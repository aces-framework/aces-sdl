"""Reward wiring tests for TrajGymTextEnv."""

import json

from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv
from trajgym.rewards.reward import Reward


def _extras() -> dict:
    return {
        "ground_truth_flag": "FLAG{test}",
        "optimal_steps": 5,
        "max_turns": 3,
    }


def test_default_reward_is_created_when_config_missing():
    env = TrajGymTextEnv(extras=_extras())
    try:
        assert env._reward_fn is not None
    finally:
        env.close()


def test_default_reward_is_created_for_empty_reward_config():
    env = TrajGymTextEnv(extras=_extras(), reward_config={})
    try:
        assert env._reward_fn is not None
    finally:
        env.close()


def test_invalid_reward_config_type_uses_defaults(caplog):
    caplog.set_level("WARNING")
    env = TrajGymTextEnv(extras=_extras(), reward_config="invalid")
    try:
        assert env._reward_fn is not None
        assert any("Invalid reward_config type" in msg for msg in caplog.messages)
    finally:
        env.close()


# ---------------------------------------------------------------------------
# Metadata pipeline: category flows from extras -> env -> reward
# ---------------------------------------------------------------------------


def _tc(name: str, args: dict) -> dict:
    return {"name": name, "arguments": json.dumps(args)}


def _shell(cmd: str) -> dict:
    return _tc("shell_command", {"command": cmd})


def _completion_with_tools(tool_calls: list, text: str = "") -> list:
    msgs = []
    for i, t in enumerate(tool_calls):
        msgs.append(
            {
                "role": "assistant",
                "content": text if i == 0 else "",
                "tool_calls": [{"function": t}],
            }
        )
        msgs.append(
            {
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "content": f"output_{i}",
            }
        )
    return msgs


def test_category_extracted_from_extras():
    """Env reads category from extras (set by _convert_online_rl_data)."""
    extras = {**_extras(), "category": "crypto"}
    env = TrajGymTextEnv(extras=extras)
    try:
        assert env._category == "crypto"
    finally:
        env.close()


def test_category_defaults_to_none_when_absent():
    env = TrajGymTextEnv(extras=_extras())
    try:
        assert env._category is None
    finally:
        env.close()


def test_crypto_category_disables_progression_weight():
    """Crypto challenges should get zero progression weight and redistributed weights."""
    reward = Reward(seed=42, noise_range=0.0)

    # Build a completion that has RECON->ENUM->EXPLOIT progression
    # (would score high on progression for "web" but should be zero for "crypto")
    tool_calls = [
        _shell("nmap -sV target"),  # recon
        _shell("curl http://target/"),  # enum
        _shell("python3 exploit.py"),  # exploit
        _tc("flag_found", {"content": "FLAG{test}"}),
    ]
    text = " ".join(["word"] * 50)  # enough words for cognitive score
    completion = _completion_with_tools(tool_calls, text=text)

    # Score with web category (default) -- progression is active
    web_results = reward.compute_with_breakdown(
        completions=[completion],
        ground_truth_flag=["FLAG{test}"],
        optimal_steps=[4],
        metadata=[{"task_category": "web", "success": True}],
    )
    web_score, web_breakdown = web_results[0]

    # Score with crypto category -- progression should be zeroed
    crypto_results = reward.compute_with_breakdown(
        completions=[completion],
        ground_truth_flag=["FLAG{test}"],
        optimal_steps=[4],
        metadata=[{"task_category": "crypto", "success": True}],
    )
    crypto_score, crypto_breakdown = crypto_results[0]

    # Crypto progression_weighted should be 0 (weight redistributed)
    assert crypto_breakdown["progression_weighted"] == 0.0
    # Web progression_weighted should be > 0 for a RECON->ENUM->EXPLOIT trace
    assert web_breakdown["progression_weighted"] > 0.0

    # The scores should differ because of the weight redistribution
    assert web_score != crypto_score


def test_rev_and_forensics_also_disable_progression():
    """Rev and forensics categories should also disable progression."""
    reward = Reward(seed=42, noise_range=0.0)

    tool_calls = [
        _shell("nmap target"),
        _shell("curl http://target/"),
        _shell("python3 exploit.py"),
        _tc("flag_found", {"content": "FLAG{abc}"}),
    ]
    text = " ".join(["word"] * 50)
    completion = _completion_with_tools(tool_calls, text=text)

    for category in ("rev", "forensics"):
        results = reward.compute_with_breakdown(
            completions=[completion],
            ground_truth_flag=["FLAG{abc}"],
            optimal_steps=[4],
            metadata=[{"task_category": category, "success": True}],
        )
        _, breakdown = results[0]
        assert (
            breakdown["progression_weighted"] == 0.0
        ), f"Expected zero progression for {category}, got {breakdown['progression_weighted']}"
