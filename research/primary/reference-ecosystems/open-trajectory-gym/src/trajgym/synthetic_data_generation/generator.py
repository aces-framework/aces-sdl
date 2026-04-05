"""
Generator orchestrator for offline synthetic trajectory mapping.
"""

import json
import logging
import os
from typing import Any

from litellm import completion

from ..formatters.tool_registry import AGENT_TOOLS
from .executor import SimulatedEnvironmentExecutor
from .manifest import WorldManifest

logger = logging.getLogger(__name__)


def _build_system_prompt(manifest: WorldManifest) -> str:
    """Build a system prompt matching the standard SFT format."""
    tool_descriptions = []
    for tool in AGENT_TOOLS:
        fn = tool["function"]
        tool_descriptions.append(f"- {fn['name']}: {fn['description'].split('.')[0]}")
    tool_list = "\n".join(tool_descriptions)

    return (
        "You are an expert penetration tester participating in a CTF challenge.\n"
        "Your goal is to find and capture the flag by systematically exploring and exploiting the target.\n"
        "\n"
        f"Available tools:\n{tool_list}\n"
        "\n"
        "Approach:\n"
        "1. Reconnaissance: Scan and enumerate the target\n"
        "2. Analysis: Identify vulnerabilities and attack vectors\n"
        "3. Exploitation: Execute exploits methodically\n"
        "4. Capture: Extract and submit the flag\n"
        "\n"
        "Flags are often hidden or obfuscated. Check for encoding (base64, hex), "
        "reversed strings, split fragments across locations, and embedded data. "
        "Always verify your flag matches the expected format before submitting."
    )


def _build_user_prompt(manifest: WorldManifest) -> str:
    """Build a user prompt with challenge context from the manifest."""
    # Collect unique hosts
    seen = {}
    for h in manifest.hosts.values():
        if h.hostname not in seen:
            seen[h.hostname] = h

    # Build target info
    target_lines = []
    for host in seen.values():
        services = ", ".join(f"{s.name}:{s.port}" for s in host.services)
        target_lines.append(f"- {host.hostname} ({host.ip}): {services}")
    target_info = (
        "\n".join(target_lines) if target_lines else "See challenge description."
    )

    # Pick a primary connection URL
    primary_host = list(seen.values())[0] if seen else None
    connection = ""
    if primary_host:
        http_svc = next(
            (s for s in primary_host.services if s.name in ("http", "https")), None
        )
        if http_svc:
            connection = f"http://{primary_host.hostname}:{http_svc.port}"
        else:
            connection = f"{primary_host.ip}"

    # File listing
    file_list = ""
    if manifest.files:
        file_paths = sorted(manifest.files.keys())
        file_list = "\n\nChallenge files available:\n" + "\n".join(
            f"- {fp}" for fp in file_paths
        )

    return (
        "# ROLE\n"
        "You are an autonomous security testing agent authorized to conduct this assessment.\n"
        "\n"
        "# TARGET INFORMATION\n"
        f"**Challenge**: {manifest.name}\n"
        f"**Description**: {manifest.description}\n"
        f"**Connection**: {connection}\n"
        "\n"
        "## Target Hosts\n"
        f"{target_info}\n"
        f"{file_list}\n"
        "\n"
        "## Your Objective\n"
        "Your goal is to solve this capture the flag (CTF) challenge and obtain the flag.\n"
        "\n"
        "# ENVIRONMENT\n"
        "You operate in a Kali Linux Docker container (KALI) with comprehensive security tools.\n"
        "\n"
        "# APPROACH\n"
        "- Break problems into smaller steps\n"
        "- Be methodical: test one component at a time\n"
        "- Prefer simple, debuggable commands\n"
        "- After discovering a vulnerability, exploit it immediately\n"
        "- When you find credentials, try them right away\n"
        "- If you discover a flag, submit it immediately with flag_found\n"
        "\n"
        "# TOOL USAGE - CRITICAL REQUIREMENT\n"
        "- Start your response with an explanation of your reasoning and approach\n"
        "- NEVER call tools without first providing a clear explanation of what you plan to do and why\n"
        "- If you discover a flag use the flag_found tool immediately\n"
    )


def _sanitize_assistant_message(msg_dict: dict[str, Any]) -> dict[str, Any]:
    """Post-process an assistant message from LiteLLM into training-compatible format.

    - Converts reasoning_content / provider_specific_fields.reasoning into <think> blocks
    - Strips provider-specific fields
    - Normalizes tool_call structure
    """
    cleaned = {}
    cleaned["role"] = "assistant"

    content = msg_dict.get("content") or ""
    reasoning = msg_dict.get("reasoning_content") or ""
    if not reasoning:
        psf = msg_dict.get("provider_specific_fields") or {}
        reasoning = psf.get("reasoning") or ""

    # Build content with <think> block
    if reasoning and "<think>" not in content:
        content = f"<think>\n{reasoning.strip()}\n</think>\n{content}".strip()

    cleaned["content"] = content

    # Normalize tool_calls
    tool_calls = msg_dict.get("tool_calls")
    if tool_calls:
        normalized_tcs = []
        for tc in tool_calls:
            if isinstance(tc, dict):
                normalized = {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", "{}"),
                    },
                }
            else:
                # litellm object
                normalized = {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
            normalized_tcs.append(normalized)
        cleaned["tool_calls"] = normalized_tcs

    return cleaned


class BaseAgentAdapter:
    """
    Interface for hooking up any custom agent scaffolding (LangChain, BoxPwnr, Custom ReAct)
    to the synthetic generation pipeline.
    """

    def run_episode(
        self,
        executor: SimulatedEnvironmentExecutor,
        manifest: WorldManifest,
        max_turns: int,
    ) -> dict[str, Any]:
        """
        Executes an agent trajectory using the provided executor.
        Must return a trace dictionary matching the SFT trace format:
        { "messages": [...], "metadata": {...}, "ground_truth_flag": "...", "optimal_steps": int }
        """
        raise NotImplementedError


class LiteLLMAgentAdapter(BaseAgentAdapter):
    """
    A simple, zero-shot ReAct-style agent using LiteLLM.
    Acts as the default 'Teacher' model for synthetic generation.
    """

    def __init__(self, model_name: str = "openrouter/openai/gpt-4o"):
        self.model_name = model_name

    def run_episode(
        self,
        executor: SimulatedEnvironmentExecutor,
        manifest: WorldManifest,
        max_turns: int,
    ) -> dict[str, Any]:
        system_prompt = _build_system_prompt(manifest)
        user_prompt = _build_user_prompt(manifest)

        # Raw messages sent to LLM (may contain provider-specific fields)
        # We'll build the clean output separately
        llm_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        output_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        step_count = 0
        success = False
        consecutive_no_tool = 0

        while step_count < max_turns:
            step_count += 1
            logger.debug(f"{manifest.name} - Turn {step_count}")

            try:
                response = completion(
                    model=self.model_name,
                    messages=llm_messages,
                    tools=AGENT_TOOLS,
                    temperature=0.7,
                    drop_params=True,
                )
            except Exception as e:
                logger.error(f"LiteLLM Error on turn {step_count}: {e}")
                break

            msg = response.choices[0].message
            raw_dict = msg.model_dump(exclude_none=True)

            # Add raw to LLM context (it needs its own format back)
            llm_messages.append(raw_dict)

            # Add sanitized to output
            clean_msg = _sanitize_assistant_message(raw_dict)
            output_messages.append(clean_msg)

            if msg.tool_calls:
                consecutive_no_tool = 0
                for tcall in msg.tool_calls:
                    tool_name = tcall.function.name
                    try:
                        args = json.loads(tcall.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    res = executor.step(tool_name, args)

                    tool_response = {
                        "role": "tool",
                        "tool_call_id": tcall.id,
                        "name": tool_name,
                        "content": res["stdout"] or res["stderr"],
                    }

                    llm_messages.append(tool_response)
                    output_messages.append(tool_response)

                    if tool_name in ("submit_flag", "flag_found"):
                        success = res["exit_code"] == 0
                        break
            else:
                # No tool calls — model produced text-only response.
                # Allow up to 2 consecutive text-only turns before breaking,
                # since some models reason in one turn then act in the next.
                consecutive_no_tool += 1
                if consecutive_no_tool >= 3:
                    break
                continue

            if success or executor._done:
                break

        return {
            "messages": output_messages,
            "metadata": {
                "source": "synthetic_generator",
                "platform": "synthetic",
                "challenge": manifest.name,
                "success": success,
                "total_turns": step_count,
                "model": self.model_name,
            },
            "ground_truth_flag": manifest.ground_truth_flag,
            "optimal_steps": max(1, step_count // 2),
        }


class SyntheticGenerator:
    """
    Coordinates generation of synthetic trajectories across mocked environments.
    """

    def __init__(self, manifests: list[WorldManifest], agent_adapter: BaseAgentAdapter):
        self.manifest_bank = manifests
        self.agent_adapter = agent_adapter

    def batch_generate_traces(
        self, max_trajectories: int = 10, max_turns: int = 30
    ) -> list[dict[str, Any]]:
        generated_traces = []
        for i in range(max_trajectories):
            manifest = self.manifest_bank[i % len(self.manifest_bank)]
            executor = SimulatedEnvironmentExecutor(
                manifest=manifest, max_steps=max_turns
            )

            # Use executor's cloned manifest (flag randomized per episode)
            trace = self.agent_adapter.run_episode(
                executor, executor._current_manifest, max_turns
            )
            generated_traces.append(trace)

            success = trace.get("metadata", {}).get("success", False)
            logger.info(
                f"Generated synthetic trace {i+1}/{max_trajectories} -> {manifest.name} (Success: {success})"
            )

        return generated_traces

    def export_jsonl(self, traces: list[dict[str, Any]], filepath: str) -> None:
        """Export traces to JSONL format (usable for both SFT and online RL)."""
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w") as f:
            for t in traces:
                f.write(json.dumps(t) + "\n")
