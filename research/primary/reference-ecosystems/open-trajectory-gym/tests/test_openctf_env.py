"""Smoke tests for TrajGymTextEnv tool call parsing.

Validates parse_tool_calls() across all supported formats:
- Hermes/Qwen3/Nanbeige: <tool_call>{"name": ..., "arguments": ...}</tool_call>
- GLM-4 XML: <tool_call>func<arg_key>k</arg_key><arg_value>v</arg_value></tool_call>
- Bare JSON: {"name": "...", "arguments": {...}}
- Python-style fallback: shell_command(command="...")
- Plain text: returns empty list (no tool calls detected)
"""

from trajgym.parsing import parse_tool_calls

# ---------------------------------------------------------------------------
# Hermes / Qwen3 / Nanbeige format
# ---------------------------------------------------------------------------


class TestHermesFormat:
    def test_single_tool_call(self):
        text = """Let me scan the target.
<tool_call>
{"name": "shell_command", "arguments": {"command": "nmap -sV 10.0.0.1"}}
</tool_call>"""
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
        assert calls[0]["arguments"]["command"] == "nmap -sV 10.0.0.1"

    def test_multiple_tool_calls(self):
        text = """
<tool_call>
{"name": "shell_command", "arguments": {"command": "nmap target"}}
</tool_call>
Some reasoning text here.
<tool_call>
{"name": "read_file", "arguments": {"path": "/etc/passwd"}}
</tool_call>"""
        calls = parse_tool_calls(text)
        assert len(calls) == 2
        assert calls[0]["name"] == "shell_command"
        assert calls[1]["name"] == "read_file"

    def test_arguments_as_string(self):
        """Arguments provided as JSON string should be parsed."""
        text = '<tool_call>\n{"name": "flag_found", "arguments": "{\\"content\\": \\"FLAG{test}\\"}"}\n</tool_call>'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "flag_found"
        assert isinstance(calls[0]["arguments"], dict)

    def test_invalid_json_skipped(self):
        text = "<tool_call>\n{not valid json}\n</tool_call>"
        calls = parse_tool_calls(text)
        assert calls == []

    def test_name_required(self):
        """Tool call without name should be skipped."""
        text = '<tool_call>\n{"arguments": {"command": "ls"}}\n</tool_call>'
        calls = parse_tool_calls(text)
        assert calls == []


# ---------------------------------------------------------------------------
# GLM-4 XML format
# ---------------------------------------------------------------------------


class TestGLM4Format:
    def test_single_tool_call(self):
        text = """<tool_call>shell_command<arg_key>command</arg_key><arg_value>nmap target</arg_value></tool_call>"""
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
        assert calls[0]["arguments"]["command"] == "nmap target"

    def test_multiple_args(self):
        text = """<tool_call>exec_command<arg_key>cmd</arg_key><arg_value>python3</arg_value><arg_key>workdir</arg_key><arg_value>/tmp</arg_value></tool_call>"""
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "exec_command"
        assert calls[0]["arguments"]["cmd"] == "python3"
        assert calls[0]["arguments"]["workdir"] == "/tmp"

    def test_json_arg_value_parsed(self):
        """Integer values in arg_value should be parsed as JSON."""
        text = """<tool_call>shell_command<arg_key>timeout</arg_key><arg_value>30</arg_value></tool_call>"""
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["arguments"]["timeout"] == 30


# ---------------------------------------------------------------------------
# Bare JSON format
# ---------------------------------------------------------------------------


class TestBareJSONFormat:
    def test_single_bare_json(self):
        text = 'I will run a scan: {"name": "shell_command", "arguments": {"command": "nmap target"}}'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"

    def test_invalid_args_json_still_creates_entry(self):
        text = '{"name": "flag_found", "arguments": {}}'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "flag_found"

    def test_nested_braces_in_arguments(self):
        """Arguments containing one level of nested braces should parse correctly."""
        text = '{"name": "shell_command", "arguments": {"command": "echo {hello}"}}'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
        assert calls[0]["arguments"]["command"] == "echo {hello}"

    def test_nested_json_in_arguments(self):
        """Arguments containing a nested JSON object should parse correctly."""
        text = (
            '{"name": "python_code", "arguments": {"code": "data = {"key": "value"}"}}'
        )
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "python_code"

    def test_unknown_tool_filtered(self):
        text = '{"name": "type", "arguments": {"command": "ls"}}'
        calls = parse_tool_calls(text)
        assert calls == []


# ---------------------------------------------------------------------------
# Python-style fallback format
# ---------------------------------------------------------------------------


class TestPythonStyleFormat:
    def test_keyword_arguments(self):
        text = 'shell_command(command="ls -la /root/challenge", timeout=15)'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
        assert calls[0]["arguments"]["command"] == "ls -la /root/challenge"
        assert calls[0]["arguments"]["timeout"] == 15

    def test_positional_argument(self):
        text = 'read_file("/root/challenge/index.php")'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "read_file"
        assert calls[0]["arguments"]["file_path"] == "/root/challenge/index.php"

    def test_unquoted_path_argument(self):
        text = "read_file(/root/challenge/index.php)"
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "read_file"
        assert calls[0]["arguments"]["file_path"] == "/root/challenge/index.php"

    def test_inline_call_inside_prose(self):
        text = (
            "First I will probe the target. Use this next: "
            'shell_command(command="curl -s http://localhost:43010").'
        )
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_command"
        assert calls[0]["arguments"]["command"] == "curl -s http://localhost:43010"

    def test_placeholder_call_is_ignored(self):
        text = 'For web challenges start with shell_command(command="curl -s <target_url>").'
        calls = parse_tool_calls(text)
        assert calls == []


# ---------------------------------------------------------------------------
# Plain text (no tool calls)
# ---------------------------------------------------------------------------


class TestPlainText:
    def test_empty_string(self):
        assert parse_tool_calls("") == []

    def test_plain_text_no_tools(self):
        text = "I'm thinking about how to approach this challenge. Let me consider the options."
        assert parse_tool_calls(text) == []

    def test_text_with_curly_braces_but_no_tool(self):
        text = "The JSON format is {key: value} but this isn't a tool call."
        assert parse_tool_calls(text) == []

    def test_partial_tag_not_matched(self):
        text = "<tool_call>incomplete"
        assert parse_tool_calls(text) == []


# ---------------------------------------------------------------------------
# Priority: Hermes > GLM4 > Bare JSON
# ---------------------------------------------------------------------------


class TestFormatPriority:
    def test_hermes_takes_priority_over_bare_json(self):
        """If Hermes tags are found, bare JSON is not parsed."""
        text = """<tool_call>
{"name": "shell_command", "arguments": {"command": "from_hermes"}}
</tool_call>
Also has bare JSON: {"name": "read_file", "arguments": {"path": "/tmp"}}"""
        calls = parse_tool_calls(text)
        # Hermes should be returned, bare JSON should be ignored
        assert len(calls) == 1
        assert calls[0]["arguments"]["command"] == "from_hermes"


# ---------------------------------------------------------------------------
# Native tool schema integration
# ---------------------------------------------------------------------------


class TestNativeToolSchemas:
    """Verify native_tool_schemas flag skips _inject_tool_schemas()."""

    def test_native_flag_skips_text_injection(self):
        """When native_tool_schemas=True, _inject_tool_schemas is skipped."""
        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        env = TrajGymTextEnv(target="http://localhost:8000", native_tool_schemas=True)
        prompt = [{"role": "system", "content": "You are a CTF agent."}]
        result = env.init(prompt)
        injected = result[0] if isinstance(result, tuple) else result
        # System message should NOT have "# Available Tools" injected
        sys_content = injected[0]["content"]
        assert (
            "# Available Tools" not in sys_content
        ), "native_tool_schemas=True should skip _inject_tool_schemas()"

    def test_default_flag_injects_text(self):
        """Default (native_tool_schemas=False) still injects tool schemas."""
        from trajgym.envs.skyrl.trajgym_env import TrajGymTextEnv

        env = TrajGymTextEnv(target="http://localhost:8000")
        prompt = [{"role": "system", "content": "You are a CTF agent."}]
        result = env.init(prompt)
        injected = result[0] if isinstance(result, tuple) else result
        sys_content = injected[0]["content"]
        assert (
            "# Available Tools" in sys_content
        ), "Default should inject tool schemas via _inject_tool_schemas()"
