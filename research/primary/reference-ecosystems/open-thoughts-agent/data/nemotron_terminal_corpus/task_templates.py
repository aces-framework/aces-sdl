"""
Shared template helpers for Nemotron-Terminal-Corpus task generation.
"""

from __future__ import annotations

from textwrap import dedent


def render_task_toml(difficulty: str = "medium", category: str = "terminal") -> str:
    return dedent(
        f"""\
        version = "1.0"

        [metadata]
        author_name = "Nemotron-Terminal-Corpus Generator"
        author_email = "generated@nemotron-tc.nvidia.com"
        difficulty = "{difficulty}"
        category = "{category}"
        tags = ["code", "terminal", "{category}"]

        [verifier]
        restart_environment = false
        timeout_sec = 600.0

        [agent]
        timeout_sec = 1500.0
        """
    )


PLAIN_DOCKERFILE = dedent(
    """\
    FROM ubuntu:24.04

    WORKDIR /app

    RUN apt-get update && apt-get install -y \\
        python3 python3-pip python3-venv \\
        git curl wget jq bc \\
        && rm -rf /var/lib/apt/lists/*

    RUN mkdir -p /logs
    """
)


def render_instruction_md(task_description: str) -> str:
    return task_description.strip()


__all__ = [
    "render_task_toml",
    "PLAIN_DOCKERFILE",
    "render_instruction_md",
]
