from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv


def test_tokenizer_drift_schema_injection():
    """
    Test that the tool schema injection in TrajGymTextEnv matches the exact
    expected string format used during SFT (e.g. by TRL or formatters).
    This ensures no token drift occurs between offline SFT and online RL.
    """
    env = TrajGymTextEnv(
        target="http://localhost:8000",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "shell_command",
                    "description": "Run a shell command.",
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string"}},
                        "required": ["command"],
                    },
                },
            }
        ],
    )

    initial_prompt = [{"role": "system", "content": "You are a helpful CTF agent."}]

    # Inject tool schemas (simulating Online RL start)
    injected_prompt = env._inject_tool_schemas(initial_prompt)

    # Extract the system prompt
    sys_content = injected_prompt[0]["content"]

    # Assert exact literal structure to prevent formatting drift.
    # Default tool_call_format is "hermes".
    expected_header = "\n\n# Available Tools\n\n"
    expected_hermes_instruction = 'Call tools using: <tool_call>{"name": "tool_name", "arguments": {...}}</tool_call>'
    expected_tool_def = "- shell_command: Runs a shell script (string) and returns its output when finished."

    assert expected_header in sys_content, "Tool schema injection header drifted."
    assert (
        expected_hermes_instruction in sys_content
    ), "Hermes format instruction drifted."
    assert expected_tool_def in sys_content, "Tool schema parameter formatting drifted."
    assert sys_content.startswith(
        "You are a helpful CTF agent."
    ), "System message prefix was lost."

    # Test without system message
    no_sys_prompt = [{"role": "user", "content": "Hello"}]
    injected_no_sys = env._inject_tool_schemas(no_sys_prompt)
    assert len(injected_no_sys) == 2
    assert injected_no_sys[0]["role"] == "system"
    assert (
        "You are a CTF agent with access to the following tools."
        in injected_no_sys[0]["content"]
    )
    assert expected_header in injected_no_sys[0]["content"]

    print("Token drift test passed: Schema injection is deterministic.")


def test_glm4_tool_call_format():
    """Test that GLM4 format instruction is injected when tool_call_format='glm4'."""
    env = TrajGymTextEnv(target="http://localhost:8000", tool_call_format="glm4")

    prompt = [{"role": "system", "content": "You are a CTF agent."}]
    injected = env._inject_tool_schemas(prompt)
    sys_content = injected[0]["content"]

    assert "<arg_key>" in sys_content, "GLM4 format instruction not injected."
    assert (
        '"name": "tool_name"' not in sys_content
    ), "Hermes instruction leaked into GLM4 format."


def test_existing_tool_list_still_gets_format_instruction():
    """If prompt already has an Available tools list, inject format guidance only."""
    env = TrajGymTextEnv(target="http://localhost:8000", tool_call_format="qwen3_coder")
    prompt = [
        {
            "role": "system",
            "content": (
                "You are a CTF agent.\n\n"
                "Available tools:\n"
                "- shell_command: Run commands\n"
                "- read_file: Read files\n"
            ),
        }
    ]
    injected = env._inject_tool_schemas(prompt)
    sys_content = injected[0]["content"]
    assert "# Tool Call Format" in sys_content
    assert "<function=tool_name>" in sys_content
    # Should not duplicate full schema block when tools are already present.
    assert sys_content.count("# Available Tools") == 0
