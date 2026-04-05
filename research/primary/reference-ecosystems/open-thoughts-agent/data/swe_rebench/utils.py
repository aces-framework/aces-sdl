"""
Utility functions for SWE-rebench dataset generation.
"""

from __future__ import annotations

from typing import Any


def load_swe_rebench_instances(
    split: str = "filtered",
) -> list[dict[str, Any]]:
    """Load SWE-rebench instances from HuggingFace.

    Args:
        split: Dataset split to load.  ``"filtered"`` (6.5k higher-quality
            subset) or ``"test"`` (full 21k set).

    Returns:
        List of instance dicts.
    """
    from datasets import load_dataset

    print(f"Loading nebius/SWE-rebench split={split!r} ...")
    ds = load_dataset("nebius/SWE-rebench", split=split)
    print(f"Loaded {len(ds)} instances")
    return list(ds)


def filter_instances_with_docker(
    instances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep only instances that have a pre-built Docker image."""
    filtered = [
        inst for inst in instances
        if inst.get("docker_image")
    ]
    print(f"Filtered to {len(filtered)}/{len(instances)} instances with docker_image")
    return filtered


def get_test_cmd(instance: dict[str, Any]) -> str:
    """Extract the test command from an instance's install_config."""
    install_config = instance.get("install_config", {})
    if isinstance(install_config, str):
        import json
        try:
            install_config = json.loads(install_config)
        except (json.JSONDecodeError, TypeError):
            install_config = {}
    return install_config.get("test_cmd", "pytest")
