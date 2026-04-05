"""Tests for SubprocessExecutor -- direct subprocess tool execution.

Validates:
- reset() returns expected dict shape
- step() with shell_command (subprocess execution)
- step() with python_code
- Flag submission: correct flag -> "Correct! Flag verified: ..."
- Flag submission: wrong flag -> "Incorrect submission: ..."
- max_steps -> done=True
- Unknown tool -> error response
- Per-generation state isolation
"""

from trajgym.envs.tool_executor import SubprocessExecutor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_executor(**kwargs) -> SubprocessExecutor:
    """Create a SubprocessExecutor with sensible test defaults."""
    defaults = {
        "target": "http://test-target:8080",
        "ground_truth": "FLAG{test123}",
        "max_steps": 10,
        "command_timeout": 5,
    }
    defaults.update(kwargs)
    return SubprocessExecutor(**defaults)


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------


class TestReset:
    def test_returns_expected_keys(self):
        exe = _make_executor()
        result = exe.reset()
        assert set(result.keys()) == {"stdout", "stderr", "exit_code", "done", "reward"}

    def test_initial_state(self):
        exe = _make_executor()
        result = exe.reset()
        assert result["done"] is False
        assert result["exit_code"] == 0
        assert result["reward"] == 0.0
        assert "test-target" in result["stdout"]

    def test_reset_clears_step_count(self):
        exe = _make_executor(max_steps=5)
        exe.reset()
        # Take a few steps
        exe.step("shell_command", {"command": "echo a"})
        exe.step("shell_command", {"command": "echo b"})
        # Reset should allow full steps again
        exe.reset()
        for _ in range(4):
            r = exe.step("shell_command", {"command": "echo x"})
            assert r["done"] is False
        r = exe.step("shell_command", {"command": "echo last"})
        assert r["done"] is True


# ---------------------------------------------------------------------------
# step() — shell_command
# ---------------------------------------------------------------------------


class TestShellCommand:
    def test_echo(self):
        exe = _make_executor()
        exe.reset()
        result = exe.step("shell_command", {"command": "echo hello"})
        assert result["stdout"].strip() == "hello"
        assert result["exit_code"] == 0
        assert result["done"] is False

    def test_returns_expected_keys(self):
        exe = _make_executor()
        exe.reset()
        result = exe.step("shell_command", {"command": "echo test"})
        assert set(result.keys()) == {"stdout", "stderr", "exit_code", "done", "reward"}

    def test_failed_command(self):
        exe = _make_executor()
        exe.reset()
        result = exe.step("shell_command", {"command": "false"})
        assert result["exit_code"] != 0
        assert result["reward"] < 0

    def test_execute_command_alias(self):
        """execute_command is an alias for shell_command."""
        exe = _make_executor()
        exe.reset()
        result = exe.step("execute_command", {"command": "echo aliased"})
        assert result["stdout"].strip() == "aliased"
        assert result["exit_code"] == 0

    def test_default_workdir_when_not_provided(self, tmp_path):
        exe = _make_executor(default_workdir=str(tmp_path))
        exe.reset()
        result = exe.step("shell_command", {"command": "pwd"})
        assert result["stdout"].strip() == str(tmp_path)

    def test_noninteractive_env_sets_unzipopt(self):
        exe = _make_executor()
        exe.reset()
        result = exe.step("shell_command", {"command": "echo ${UNZIPOPT}"})
        assert result["stdout"].strip() == "-o"


# ---------------------------------------------------------------------------
# step() — python_code
# ---------------------------------------------------------------------------


class TestPythonCode:
    def test_simple_code(self):
        exe = _make_executor()
        exe.reset()
        result = exe.step("python_code", {"code": "print(2 + 2)"})
        assert result["stdout"].strip() == "4"
        assert result["exit_code"] == 0

    def test_syntax_error(self):
        exe = _make_executor()
        exe.reset()
        result = exe.step("python_code", {"code": "def :"})
        assert result["exit_code"] != 0


# ---------------------------------------------------------------------------
# Flag submission
# ---------------------------------------------------------------------------


class TestFlagSubmission:
    def test_correct_flag(self):
        exe = _make_executor(ground_truth="FLAG{correct}")
        exe.reset()
        result = exe.step("flag_found", {"content": "FLAG{correct}"})
        assert "Correct! Flag verified: FLAG{correct}" in result["stdout"]
        assert result["reward"] == 1.0
        assert result["done"] is True

    def test_incorrect_flag(self):
        exe = _make_executor(ground_truth="FLAG{correct}")
        exe.reset()
        result = exe.step("flag_found", {"content": "FLAG{wrong}"})
        assert "Incorrect submission: FLAG{wrong}" in result["stdout"]
        assert result["reward"] < 0
        # Incorrect flag allows agent to retry (done only at max_steps)
        assert result["done"] is False

    def test_submit_flag_alias(self):
        """submit_flag should work the same as flag_found."""
        exe = _make_executor(ground_truth="FLAG{abc}")
        exe.reset()
        result = exe.step("submit_flag", {"content": "FLAG{abc}"})
        assert "Correct! Flag verified: FLAG{abc}" in result["stdout"]
        assert result["reward"] == 1.0

    def test_empty_ground_truth_always_incorrect(self):
        exe = _make_executor(ground_truth="")
        exe.reset()
        result = exe.step("flag_found", {"content": "FLAG{anything}"})
        assert "Incorrect" in result["stdout"]
        # No ground truth means never correct; done only at max_steps
        assert result["done"] is False


# ---------------------------------------------------------------------------
# max_steps -> done
# ---------------------------------------------------------------------------


class TestMaxSteps:
    def test_done_at_max_steps(self):
        exe = _make_executor(max_steps=3)
        exe.reset()
        r1 = exe.step("shell_command", {"command": "echo 1"})
        assert r1["done"] is False
        r2 = exe.step("shell_command", {"command": "echo 2"})
        assert r2["done"] is False
        r3 = exe.step("shell_command", {"command": "echo 3"})
        assert r3["done"] is True


# ---------------------------------------------------------------------------
# Unknown / unavailable tools
# ---------------------------------------------------------------------------


class TestUnknownTool:
    def test_unknown_tool_returns_error(self):
        exe = _make_executor()
        exe.reset()
        result = exe.step("nonexistent_tool", {})
        assert result["exit_code"] == 1
        assert "not available" in result["stderr"]
        assert result["reward"] < 0

    def test_restricted_tools(self):
        """When tools= is restricted, unlisted tools should fail."""
        exe = _make_executor(tools=["shell_command", "flag_found"])
        exe.reset()
        result = exe.step("python_code", {"code": "print(1)"})
        assert result["exit_code"] == 1
        assert "not available" in result["stderr"]


# ---------------------------------------------------------------------------
# Per-generation state isolation
# ---------------------------------------------------------------------------


class TestGenerationIsolation:
    def test_separate_step_counts(self):
        exe = _make_executor(max_steps=3)
        exe.reset(generation_id="gen_a")

        # gen_a takes 2 steps
        exe.step("shell_command", {"command": "echo a1"}, generation_id="gen_a")
        exe.step("shell_command", {"command": "echo a2"}, generation_id="gen_a")

        # gen_b starts fresh
        r = exe.step("shell_command", {"command": "echo b1"}, generation_id="gen_b")
        # gen_b should be at step 1 (not 3), so not done
        assert r["done"] is False

    def test_flag_independent(self):
        exe = _make_executor(ground_truth="FLAG{x}")
        exe.reset(generation_id="gen_a")

        # gen_a finds the flag
        r_a = exe.step("flag_found", {"content": "FLAG{x}"}, generation_id="gen_a")
        assert r_a["done"] is True

        # gen_b should still be able to operate (different state)
        r_b = exe.step(
            "shell_command", {"command": "echo still_going"}, generation_id="gen_b"
        )
        assert r_b["done"] is False
        assert r_b["stdout"].strip() == "still_going"


# ---------------------------------------------------------------------------
# File operation handlers
# ---------------------------------------------------------------------------


class TestFileOps:
    def test_read_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1\nline2\n")

        exe = _make_executor()
        exe.reset()
        result = exe.step("read_file", {"file_path": str(test_file)})
        assert "line1" in result["stdout"]
        assert "line2" in result["stdout"]
        assert result["exit_code"] == 0

    def test_read_file_accepts_file_alias(self, tmp_path):
        test_file = tmp_path / "alias.txt"
        test_file.write_text("alias_ok\n")

        exe = _make_executor()
        exe.reset()
        result = exe.step("read_file", {"file": str(test_file)})
        assert "alias_ok" in result["stdout"]
        assert result["exit_code"] == 0

    def test_read_file_accepts_filename_alias(self, tmp_path):
        """Models often use {"filename": "..."} — verify the alias works."""
        test_file = tmp_path / "fn_alias.txt"
        test_file.write_text("filename_ok\n")

        exe = _make_executor()
        exe.reset()
        result = exe.step("read_file", {"filename": str(test_file)})
        assert "filename_ok" in result["stdout"]
        assert result["exit_code"] == 0

    def test_grep(self, tmp_path):
        test_file = tmp_path / "search.txt"
        test_file.write_text("flag_here\nno_match\nflag_also\n")

        exe = _make_executor()
        exe.reset()
        result = exe.step("grep", {"pattern": "flag", "path": str(test_file)})
        assert "flag_here" in result["stdout"]
        assert result["exit_code"] == 0

    def test_file_search(self, tmp_path):
        (tmp_path / "target.py").write_text("pass")
        (tmp_path / "other.txt").write_text("")

        exe = _make_executor()
        exe.reset()
        result = exe.step("file_search", {"pattern": "*.py", "path": str(tmp_path)})
        assert "target.py" in result["stdout"]
        assert result["exit_code"] == 0


class TestApplyPatch:
    def test_apply_patch_updates_file_contents(self, tmp_path):
        target = tmp_path / "notes.txt"
        target.write_text("alpha\nbeta\n", encoding="utf-8")

        exe = _make_executor(default_workdir=str(tmp_path))
        exe.reset()
        patch = (
            "*** Begin Patch\n"
            "*** Update File: notes.txt\n"
            "@@\n"
            "-beta\n"
            "+gamma\n"
            "*** End Patch\n"
        )
        result = exe.step("apply_patch", {"patch": patch})
        assert result["exit_code"] == 0
        assert "Updated file: notes.txt" in result["stdout"]
        assert target.read_text(encoding="utf-8") == "alpha\ngamma\n"

    def test_apply_patch_rejects_workspace_escape(self, tmp_path):
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("x\n", encoding="utf-8")

        exe = _make_executor(default_workdir=str(tmp_path))
        exe.reset()
        patch = (
            "*** Begin Patch\n"
            "*** Update File: ../outside.txt\n"
            "@@\n"
            "-x\n"
            "+y\n"
            "*** End Patch\n"
        )
        result = exe.step("apply_patch", {"patch": patch})
        assert result["exit_code"] == 1
        assert "escapes workspace" in (result["stderr"] or "")
        assert outside.read_text(encoding="utf-8") == "x\n"


# ---------------------------------------------------------------------------
# stdout/stderr limits
# ---------------------------------------------------------------------------


class TestOutputLimits:
    def test_stdout_truncated(self):
        exe = _make_executor(stdout_limit=20)
        exe.reset()
        result = exe.step(
            "shell_command", {"command": "python3 -c \"print('A' * 100)\""}
        )
        assert len(result["stdout"]) <= 20


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


class TestClose:
    def test_close_is_safe(self):
        exe = _make_executor()
        exe.reset()
        exe.step("shell_command", {"command": "echo test"})
        exe.close()  # Should not raise

    def test_double_close_is_safe(self):
        exe = _make_executor()
        exe.reset()
        exe.close()
        exe.close()  # Should not raise
