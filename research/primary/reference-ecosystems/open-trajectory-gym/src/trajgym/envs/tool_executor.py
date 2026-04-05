"""Direct tool execution engine for CTF training environments.

Subprocess-based tool executor with per-generation state isolation.
SkyRL gives each env instance its own process, so no HTTP layer is needed.

Architecture:
    SkyRL -> TrajGymTextEnv -> ToolExecutor -> subprocess (direct)

Supports 13 tools across 3 tiers (shell, file ops, meta), flag submission
with verification strings, and interactive PTY sessions.  The public API
is reset/step/close with plain-dict returns for Ray serialization.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import shlex
import shutil
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# Canonical parameter name for flag submission is "content" (tool_registry.py),
# but models commonly use "flag", "value", or "submission".  Accept all of them
# and fall back to the first string value in the arguments dict.
_FLAG_PARAM_NAMES = ("content", "flag", "value", "submission")


def _extract_flag_value(arguments: dict[str, Any]) -> str:
    """Extract the submitted flag string from tool arguments.

    Tries canonical name first, then common aliases, then first string value.
    """
    for key in _FLAG_PARAM_NAMES:
        val = arguments.get(key)
        if val and isinstance(val, str):
            return val
    # Last resort: take the first string value from the dict
    for val in arguments.values():
        if isinstance(val, str) and val.strip():
            return val
    return ""


def _noninteractive_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return a process env tuned for unattended tool execution."""
    env = os.environ.copy()
    env.setdefault("UNZIPOPT", "-o")
    env.setdefault("DEBIAN_FRONTEND", "noninteractive")
    if extra:
        env.update(extra)
    return env


# ---------------------------------------------------------------------------
# PTY Session Manager
# ---------------------------------------------------------------------------


class _Session:
    """A running interactive process with non-blocking stdout/stderr capture."""

    def __init__(self, session_id: str, cmd: str, workdir: str | None = None):
        self.session_id = session_id
        self.cmd = cmd
        self.start_time = time.time()
        self._buf = io.StringIO()
        self._lock = threading.Lock()

        kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
            "env": _noninteractive_env(),
        }
        if workdir:
            kwargs["cwd"] = workdir

        self._proc = subprocess.Popen(["bash", "-c", cmd], **kwargs)

        # Background reader thread
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        try:
            for line in self._proc.stdout:
                with self._lock:
                    self._buf.write(line)
        except (ValueError, OSError):
            pass  # Pipe closed

    @property
    def running(self) -> bool:
        return self._proc.poll() is None

    @property
    def exit_code(self) -> int | None:
        return self._proc.poll()

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.start_time

    def write(self, chars: str) -> None:
        if self._proc.stdin and self.running:
            try:
                self._proc.stdin.write(chars)
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError):
                pass

    def read(self) -> str:
        with self._lock:
            output = self._buf.getvalue()
            self._buf = io.StringIO()
        return output

    def close(self) -> None:
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            self._proc.kill()


class SessionManager:
    """Manages interactive PTY sessions for exec_command/write_stdin."""

    def __init__(self):
        self._sessions: dict[str, _Session] = {}
        self._next_id = 1

    def start(
        self, cmd: str, workdir: str | None = None, yield_time: int = 5
    ) -> tuple[str, str]:
        """Start a new session. Returns (session_id, initial_output)."""
        sid = str(self._next_id)
        self._next_id += 1
        session = _Session(sid, cmd, workdir)
        self._sessions[sid] = session
        time.sleep(min(yield_time, 30))
        output = session.read()
        status = "running" if session.running else f"exited ({session.exit_code})"
        header = f"Process {status} with session ID {sid} (command: {cmd})"
        return sid, f"{header}\n\nOutput:\n{output}" if output else header

    def write(self, session_id: str, chars: str, yield_time: int = 2) -> str:
        """Write to a session and read output after waiting."""
        session = self._sessions.get(session_id)
        if not session:
            return f"Error: No session with ID {session_id}"

        if chars:
            if chars.isprintable() and not chars.endswith("\n"):
                chars += "\n"
            session.write(chars)

        time.sleep(min(yield_time, 30))
        output = session.read()
        status = "running" if session.running else f"exited ({session.exit_code})"
        header = f"Process {status} with session ID {session_id}"
        return f"{header}\n\nOutput:\n{output}" if output else header

    def list(self) -> str:
        """List all active sessions."""
        if not self._sessions:
            return "No active sessions."
        lines = ["Active sessions:"]
        for sid, s in self._sessions.items():
            status = "running" if s.running else f"exited ({s.exit_code})"
            idle = int(s.idle_seconds)
            lines.append(f"  ID: {sid}: {s.cmd} ({status}, idle: {idle}s)")
        return "\n".join(lines)

    def close(self, session_id: str) -> str:
        """Close a session."""
        session = self._sessions.pop(session_id, None)
        if not session:
            return f"Error: No session with ID {session_id}"
        session.close()
        return f"Session {session_id} closed successfully"

    def close_all(self) -> None:
        """Close all sessions (called on episode reset)."""
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()
        self._next_id = 1


# ---------------------------------------------------------------------------
# Shell / Python helpers
# ---------------------------------------------------------------------------


def _default_shell(
    command: str, timeout: int, workdir: str | None = None
) -> tuple[str, str, int]:
    """Execute a shell command via ``bash -c`` (non-login shell).

    Using a non-login shell avoids issues where container ``.bashrc``
    contains ``exit 0`` (e.g. NGC PyTorch images), which kills the login
    shell before the command executes.  PATH is inherited from the parent
    process, so tools remain available.
    """
    try:
        script = command
        if workdir:
            script = f"cd {shlex.quote(workdir)} && {script}"
        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_noninteractive_env(),
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Command timed out after {timeout}s", 124
    except Exception as e:
        return "", str(e), 1


def _default_python(code: str, timeout: int) -> tuple[str, str, int]:
    """Execute Python code via a temp file.

    Writing to a temp file avoids shell-quoting issues with complex
    multi-line code containing quotes and special characters (matching
    BoxPwnr's approach).
    """
    import base64

    try:
        # Base64-encode to avoid any shell escaping issues
        encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")

        # Create temp file, decode into it, run, clean up
        script = (
            "TMPF=$(mktemp /tmp/pycode_XXXXXX.py) && "
            f"echo '{encoded}' | base64 -d > \"$TMPF\" && "
            'python3 "$TMPF"; EXIT_CODE=$?; rm -f "$TMPF"; exit $EXIT_CODE'
        )
        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_noninteractive_env(),
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Code timed out after {timeout}s", 124
    except Exception as e:
        return "", str(e), 1


# ---------------------------------------------------------------------------
# Per-generation state
# ---------------------------------------------------------------------------


@dataclass
class ToolState:
    """Tracks episode progress for one generation."""

    episode_id: str = ""
    step_count: int = 0
    target: str = ""
    tools_used: int = 0
    tools_available: list[str] = field(default_factory=list)
    flag_submitted: bool = False
    flag_correct: bool = False
    ground_truth: str = ""
    max_steps: int = 30


# ---------------------------------------------------------------------------
# Tool handler type
# ---------------------------------------------------------------------------

ToolHandler = Callable[[dict[str, Any], int], tuple[str, str, int]]

# Full tool set organized by tier
TIER1_TOOLS = {
    "shell_command",
    "exec_command",
    "write_stdin",
    "python_code",
    "execute_command",
}
TIER2_TOOLS = {"read_file", "grep", "file_search", "apply_patch"}
TIER3_TOOLS = {
    "submit_flag",
    "flag_found",
    "web_search",
    "list_sessions",
    "close_session",
}
ALL_TOOLS = TIER1_TOOLS | TIER2_TOOLS | TIER3_TOOLS


# ---------------------------------------------------------------------------
# ToolExecutor
# ---------------------------------------------------------------------------


class BaseExecutor:
    """Base interface for CTF tool execution environments."""

    def __init__(self, **kwargs):
        self.ground_truth = kwargs.get("ground_truth", "")
        self.max_steps = kwargs.get("max_steps", 30)

    def reset(self, generation_id: str | None = None) -> dict:
        raise NotImplementedError

    def step(
        self, tool_name: str, arguments: dict, generation_id: str | None = None
    ) -> dict:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class SubprocessExecutor(BaseExecutor):
    """Direct tool execution engine (no HTTP, no FastAPI).

    Executes tools via subprocess calls.  Supports per-generation
    state isolation via ``generation_id``.

    Args:
        target: Description or URL of the target.
        ground_truth: Expected flag for reward computation.
        max_steps: Maximum steps per episode.
        command_timeout: Per-command timeout in seconds.
        tools: List of tool names to enable.  Defaults to ALL_TOOLS.
        tool_handlers: Optional custom handlers keyed by tool name.
        stdout_limit: Max characters kept from stdout.
        stderr_limit: Max characters kept from stderr.
    """

    _DEFAULT_GEN = "__default__"

    def __init__(
        self,
        target: str | None = None,
        ground_truth: str = "",
        max_steps: int = 30,
        command_timeout: int = 30,
        tools: list[str] | None = None,
        tool_handlers: dict[str, ToolHandler] | None = None,
        stdout_limit: int = 4096,
        stderr_limit: int = 1024,
        default_workdir: str | None = None,
    ):
        self.target = target or os.getenv("CHALLENGE_TARGET", "http://localhost:8080")
        self.ground_truth = ground_truth or os.getenv("GROUND_TRUTH", "")
        self.max_steps = max_steps
        self.command_timeout = command_timeout
        self.tools = tools or sorted(ALL_TOOLS)
        self.stdout_limit = stdout_limit
        self.stderr_limit = stderr_limit
        self.default_workdir = (
            default_workdir or os.getenv("CHALLENGE_WORKDIR") or "/root/challenge"
        )

        self._states: dict[str, ToolState] = {}
        self._states_lock = threading.Lock()
        self._sessions = SessionManager()

        # Register built-in handlers
        self._handlers: dict[str, ToolHandler] = {
            # Tier 1
            "shell_command": self._handle_shell,
            "execute_command": self._handle_shell,  # alias
            "python_code": self._handle_python,
            "exec_command": self._handle_exec_command,
            "write_stdin": self._handle_write_stdin,
            # Tier 2
            "read_file": self._handle_read_file,
            "grep": self._handle_grep,
            "file_search": self._handle_file_search,
            "apply_patch": self._handle_apply_patch,
            # Tier 3
            "web_search": self._handle_web_search,
            "list_sessions": self._handle_list_sessions,
            "close_session": self._handle_close_session,
        }
        # submit_flag / flag_found handled inline (special logic)

        if tool_handlers:
            self._handlers.update(tool_handlers)

        self._validate_handlers()

    # -- Handler validation -------------------------------------------------

    # Tools that are handled inline (special flag submission logic) and
    # therefore do not need a registered handler.
    _FLAG_TOOLS = frozenset({"submit_flag", "flag_found"})

    def _validate_handlers(self) -> None:
        """Check that every enabled tool has a handler or is a flag tool."""
        missing = []
        for tool in self.tools:
            if tool not in self._handlers and tool not in self._FLAG_TOOLS:
                missing.append(tool)
        if missing:
            logger.warning(
                "Tools without handlers: %s — calls to these will return errors",
                sorted(missing),
            )

    def _resolve_default_workdir(self) -> str | None:
        """Return a safe default working directory if it exists."""
        workdir = str(self.default_workdir or "").strip()
        if workdir and os.path.isdir(workdir):
            return workdir
        return None

    def _resolve_workdir(self, requested: Any) -> str | None:
        """Prefer explicit workdir, then fall back to challenge workspace."""
        if isinstance(requested, str) and requested.strip():
            val = requested.strip()
            # Models sometimes generate the literal string "None" as a default.
            if val.lower() == "none":
                return self._resolve_default_workdir()
            return val
        return self._resolve_default_workdir()

    # -- Per-generation state -----------------------------------------------

    def _get_state(self, generation_id: str | None = None) -> ToolState:
        gid = generation_id or self._DEFAULT_GEN
        with self._states_lock:
            if gid not in self._states:
                self._states[gid] = ToolState(
                    episode_id=str(uuid.uuid4()),
                    step_count=0,
                    target=self.target,
                    tools_used=0,
                    tools_available=list(self.tools),
                    flag_submitted=False,
                    flag_correct=False,
                    ground_truth=self.ground_truth,
                    max_steps=self.max_steps,
                )
            return self._states[gid]

    # -- Public API ---------------------------------------------------------

    def reset(self, generation_id: str | None = None) -> dict:
        """Reset the environment for a new episode.

        Returns:
            Dict with stdout, stderr, exit_code, done, reward fields.
        """
        self._sessions.close_all()

        gid = generation_id or self._DEFAULT_GEN
        new_state = ToolState(
            episode_id=str(uuid.uuid4()),
            step_count=0,
            target=self.target,
            tools_used=0,
            tools_available=list(self.tools),
            flag_submitted=False,
            flag_correct=False,
            ground_truth=self.ground_truth,
            max_steps=self.max_steps,
        )
        with self._states_lock:
            self._states.clear()
            self._states[gid] = new_state

        return {
            "stdout": f"Environment ready. Target: {self.target}",
            "stderr": "",
            "exit_code": 0,
            "done": False,
            "reward": 0.0,
        }

    def step(
        self, tool_name: str, arguments: dict, generation_id: str | None = None
    ) -> dict:
        """Execute a tool call.

        Args:
            tool_name: Name of the tool to invoke.
            arguments: Tool arguments dict.
            generation_id: Optional generation ID for state isolation.

        Returns:
            Dict with stdout, stderr, exit_code, done, reward fields.
        """
        state = self._get_state(generation_id)
        state.step_count += 1
        state.tools_used += 1

        # Validate tool
        if tool_name not in self.tools:
            return {
                "stdout": "",
                "stderr": f"Tool '{tool_name}' is not available. Available: {self.tools}",
                "exit_code": 1,
                "done": state.step_count >= self.max_steps,
                "reward": -0.02,
            }

        # Flag submission (both names).
        # Models may use any of: content, flag, value, submission — accept all.
        if tool_name in ("submit_flag", "flag_found"):
            submitted = _extract_flag_value(arguments)
            return self._handle_flag_submission(submitted, state)

        # Dispatch to handler
        handler = self._handlers.get(tool_name)
        if handler is None:
            return {
                "stdout": "",
                "stderr": f"No handler registered for tool '{tool_name}'",
                "exit_code": 1,
                "done": state.step_count >= self.max_steps,
                "reward": -0.02,
            }

        stdout, stderr, exit_code = handler(arguments, self.command_timeout)
        done = state.step_count >= self.max_steps
        reward = 0.05 if exit_code == 0 else -0.02

        return {
            "stdout": stdout[: self.stdout_limit],
            "stderr": stderr[: self.stderr_limit],
            "exit_code": exit_code,
            "done": done,
            "reward": reward,
        }

    def close(self) -> None:
        """Release all resources (PTY sessions)."""
        self._sessions.close_all()
        logger.debug("ToolExecutor closed")

    # -- Flag submission ----------------------------------------------------

    def _handle_flag_submission(self, submitted: str, state: ToolState) -> dict:
        submitted = submitted.strip()
        correct = bool(self.ground_truth) and submitted == self.ground_truth

        state.flag_submitted = True
        state.flag_correct = correct

        if correct:
            stdout = f"Correct! Flag verified: {submitted}"
            reward = 1.0
        else:
            stdout = f"Incorrect submission: {submitted}"
            reward = -0.2

        return {
            "stdout": stdout,
            "stderr": "",
            "exit_code": 0 if correct else 1,
            # Keep episode running after incorrect submissions so the agent
            # can continue exploring and retry a corrected flag.
            "done": bool(correct or state.step_count >= self.max_steps),
            "reward": reward,
        }

    # -- Tier 1: Execution handlers -----------------------------------------

    def _handle_shell(self, args: dict[str, Any], timeout: int) -> tuple[str, str, int]:
        cmd = args.get("command", "echo 'no command'")
        t = args.get("timeout", timeout)
        # Model may pass timeout as string with suffix (e.g. "5s", "10s")
        if isinstance(t, str):
            t = t.rstrip("smSM").strip()
            try:
                t = int(t)
            except (ValueError, TypeError):
                t = timeout
        workdir = self._resolve_workdir(args.get("workdir"))
        return _default_shell(cmd, t, workdir=workdir)

    def _handle_python(
        self, args: dict[str, Any], timeout: int
    ) -> tuple[str, str, int]:
        code = args.get("code", "print('no code')")
        t = args.get("timeout", timeout)
        if isinstance(t, str):
            t = t.rstrip("smSM").strip()
            try:
                t = int(t)
            except (ValueError, TypeError):
                t = timeout
        return _default_python(code, t)

    def _handle_exec_command(
        self, args: dict[str, Any], timeout: int
    ) -> tuple[str, str, int]:
        cmd = args.get("cmd", args.get("command", "bash"))
        workdir = self._resolve_workdir(args.get("workdir"))
        yield_time = args.get("yield_time", 5)
        sid, output = self._sessions.start(cmd, workdir, yield_time=yield_time)
        return output, "", 0

    def _handle_write_stdin(
        self, args: dict[str, Any], timeout: int
    ) -> tuple[str, str, int]:
        session_id = args.get("session_id", "1")
        chars = args.get("chars", "")
        yield_time = args.get("yield_time", 2)
        output = self._sessions.write(str(session_id), chars, yield_time)
        if output.startswith("Error:"):
            return "", output, 1
        return output, "", 0

    # -- Tier 2: File operation handlers ------------------------------------

    def _handle_read_file(
        self, args: dict[str, Any], timeout: int
    ) -> tuple[str, str, int]:
        file_path = args.get(
            "file_path", args.get("path", args.get("file", args.get("filename", "")))
        )
        line_numbers = args.get("line_numbers", True)
        if not file_path:
            return "", "No file_path provided", 1
        quoted = shlex.quote(file_path)
        cmd = f"cat -n {quoted}" if line_numbers else f"cat {quoted}"
        return _default_shell(cmd, timeout)

    def _handle_grep(self, args: dict[str, Any], timeout: int) -> tuple[str, str, int]:
        pattern = args.get("pattern", "")
        path = args.get("path", self._resolve_default_workdir() or ".")
        include = args.get("include", "")
        if not pattern:
            return "", "No pattern provided", 1
        cmd = f"grep -rn {shlex.quote(pattern)} {shlex.quote(path)}"
        if include:
            cmd += f" --include={shlex.quote(include)}"
        return _default_shell(cmd, timeout)

    def _handle_file_search(
        self, args: dict[str, Any], timeout: int
    ) -> tuple[str, str, int]:
        pattern = args.get("pattern", "*")
        path = args.get("path", self._resolve_default_workdir() or ".")
        cmd = f"find {shlex.quote(path)} -name {shlex.quote(pattern)} 2>/dev/null"
        return _default_shell(cmd, timeout)

    def _handle_apply_patch(
        self, args: dict[str, Any], timeout: int
    ) -> tuple[str, str, int]:
        patch = args.get("patch", "")
        if not patch:
            return "", "No patch provided", 1
        patch_file = f"/tmp/patch_{uuid.uuid4().hex[:8]}.patch"
        try:
            with open(patch_file, "w") as f:
                f.write(patch)
            if "*** Begin Patch" in patch:
                return self._apply_boxpwnr_patch(patch, timeout)
            else:
                return _default_shell(f"patch -p0 < {patch_file}", timeout)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(patch_file)

    def _resolve_patch_path(self, path: str) -> str:
        """Resolve patch path under the challenge workspace."""
        raw = str(path or "").strip()
        if not raw:
            raise ValueError("Patch path is empty")
        base = os.path.abspath(self._resolve_default_workdir() or os.getcwd())
        candidate = (
            os.path.abspath(raw)
            if os.path.isabs(raw)
            else os.path.abspath(os.path.join(base, raw))
        )
        if candidate != base and not candidate.startswith(base + os.sep):
            raise ValueError(f"Patch path escapes workspace: {raw}")
        return candidate

    @staticmethod
    def _apply_boxpwnr_update_block(original_text: str, block_lines: list[str]) -> str:
        """Apply BoxPwnr update-hunk lines to file content."""
        hunks: list[list[tuple[str, str]]] = [[]]
        for raw in block_lines:
            if raw.startswith("@@"):
                if hunks[-1]:
                    hunks.append([])
                continue
            if raw == "*** End of File":
                continue
            if not raw:
                raise ValueError("Malformed update hunk: empty line without prefix")
            op = raw[0]
            if op not in {" ", "+", "-"}:
                raise ValueError(f"Malformed update hunk line: {raw}")
            hunks[-1].append((op, raw[1:]))
        if not hunks[-1]:
            hunks = [h for h in hunks if h]

        src_lines = original_text.splitlines()
        out_lines: list[str] = []
        cursor = 0

        def _find_line(value: str, start: int) -> int:
            for idx in range(start, len(src_lines)):
                if src_lines[idx] == value:
                    return idx
            return -1

        for ops in hunks:
            anchor = next((text for op, text in ops if op in {" ", "-"}), None)
            if anchor is not None:
                anchor_pos = _find_line(anchor, cursor)
                if anchor_pos < 0:
                    raise ValueError(f"Failed to find hunk anchor line: {anchor!r}")
                out_lines.extend(src_lines[cursor:anchor_pos])
                cursor = anchor_pos

            for op, text in ops:
                if op == " ":
                    if cursor >= len(src_lines) or src_lines[cursor] != text:
                        got = src_lines[cursor] if cursor < len(src_lines) else "<eof>"
                        raise ValueError(
                            f"Context mismatch while applying patch: expected {text!r}, got {got!r}"
                        )
                    out_lines.append(src_lines[cursor])
                    cursor += 1
                elif op == "-":
                    if cursor >= len(src_lines) or src_lines[cursor] != text:
                        got = src_lines[cursor] if cursor < len(src_lines) else "<eof>"
                        raise ValueError(
                            f"Delete mismatch while applying patch: expected {text!r}, got {got!r}"
                        )
                    cursor += 1
                else:  # "+"
                    out_lines.append(text)

        out_lines.extend(src_lines[cursor:])
        new_text = "\n".join(out_lines)
        if original_text.endswith("\n") or new_text:
            new_text += "\n"
        return new_text

    def _apply_boxpwnr_patch(self, patch: str, timeout: int) -> tuple[str, str, int]:
        del timeout  # Not used; apply is local filesystem mutation.
        lines = patch.splitlines()
        if not lines or lines[0].strip() != "*** Begin Patch":
            return "", "Invalid patch: missing '*** Begin Patch' header", 1

        i = 1
        results: list[str] = []
        try:
            while i < len(lines):
                line = lines[i]
                if line.startswith("*** End Patch"):
                    break

                if line.startswith("*** Add File: "):
                    rel = line.split(":", 1)[1].strip()
                    dst = self._resolve_patch_path(rel)
                    i += 1
                    added: list[str] = []
                    while i < len(lines) and not lines[i].startswith("*** "):
                        if not lines[i].startswith("+"):
                            raise ValueError(
                                f"Invalid add-file line (missing '+'): {lines[i]}"
                            )
                        added.append(lines[i][1:])
                        i += 1
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    with open(dst, "w", encoding="utf-8") as f:
                        f.write("\n".join(added))
                        if added:
                            f.write("\n")
                    results.append(f"Added file: {rel}")
                    continue

                if line.startswith("*** Delete File: "):
                    rel = line.split(":", 1)[1].strip()
                    dst = self._resolve_patch_path(rel)
                    if os.path.isdir(dst) and not os.path.islink(dst):
                        shutil.rmtree(dst)
                    elif os.path.exists(dst):
                        os.remove(dst)
                    results.append(f"Deleted file: {rel}")
                    i += 1
                    continue

                if line.startswith("*** Update File: "):
                    rel = line.split(":", 1)[1].strip()
                    src = self._resolve_patch_path(rel)
                    if not os.path.exists(src):
                        raise ValueError(f"Update target does not exist: {rel}")
                    i += 1

                    move_to: str | None = None
                    if i < len(lines) and lines[i].startswith("*** Move to: "):
                        move_to = lines[i].split(":", 1)[1].strip()
                        i += 1

                    block: list[str] = []
                    while i < len(lines):
                        nxt = lines[i]
                        if nxt.startswith("*** End Patch"):
                            break
                        if (
                            nxt.startswith("*** Add File: ")
                            or nxt.startswith("*** Delete File: ")
                            or nxt.startswith("*** Update File: ")
                        ):
                            break
                        block.append(nxt)
                        i += 1

                    with open(src, encoding="utf-8") as f:
                        old = f.read()
                    new = self._apply_boxpwnr_update_block(old, block)

                    dst = src
                    if move_to:
                        dst = self._resolve_patch_path(move_to)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                    with open(dst, "w", encoding="utf-8") as f:
                        f.write(new)
                    if move_to and os.path.abspath(dst) != os.path.abspath(src):
                        if os.path.exists(src):
                            os.remove(src)
                        results.append(f"Updated file: {rel} -> {move_to}")
                    else:
                        results.append(f"Updated file: {rel}")
                    continue

                raise ValueError(f"Unsupported patch directive: {line}")
        except Exception as exc:
            return "", f"Failed to apply patch: {exc}", 1

        if i >= len(lines) or not any(
            line.startswith("*** End Patch") for line in lines[i:]
        ):
            return "", "Invalid patch: missing '*** End Patch' footer", 1
        return "\n".join(results) if results else "Patch applied", "", 0

    # -- Tier 3: Meta handlers ----------------------------------------------

    def _handle_web_search(
        self, args: dict[str, Any], timeout: int
    ) -> tuple[str, str, int]:
        query = args.get("query", "")
        if not query:
            return "", "No query provided", 1
        cmd = (
            f"command -v ddgr >/dev/null 2>&1 && "
            f"ddgr -n 5 --json '{query}' 2>/dev/null || "
            f"curl -sL 'https://lite.duckduckgo.com/lite/?q={query.replace(' ', '+')}' "
            f'2>/dev/null | grep -oP \'(?<=<a rel="nofollow" href=")[^"]+\' | head -5'
        )
        return _default_shell(cmd, timeout)

    def _handle_list_sessions(
        self, args: dict[str, Any], timeout: int
    ) -> tuple[str, str, int]:
        output = self._sessions.list()
        return output, "", 0

    def _handle_close_session(
        self, args: dict[str, Any], timeout: int
    ) -> tuple[str, str, int]:
        session_id = args.get("session_id", "")
        if not session_id:
            return "", "No session_id provided", 1
        output = self._sessions.close(str(session_id))
        if output.startswith("Error:"):
            return "", output, 1
        return output, "", 0


class RemoteBatchExecutor(BaseExecutor):
    """Execution engine that batches commands and proxies them to a remote target."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.target = kwargs.get("target") or os.getenv(
            "CHALLENGE_TARGET", "http://localhost:8080"
        )
        self.tools = kwargs.get("tools") or sorted(ALL_TOOLS)
        self.stdout_limit = kwargs.get("stdout_limit", 4096)
        self.stderr_limit = kwargs.get("stderr_limit", 1024)

        self._step_count = 0
        self._done = False

    def reset(self, generation_id: str | None = None) -> dict:
        self._step_count = 0
        self._done = False
        return {
            "stdout": f"Remote environment ready. Target: {self.target}",
            "stderr": "",
            "exit_code": 0,
            "done": False,
            "reward": 0.0,
        }

    def step(
        self, tool_name: str, arguments: dict, generation_id: str | None = None
    ) -> dict:
        self._step_count += 1

        if tool_name not in self.tools:
            return {
                "stdout": "",
                "stderr": f"Tool '{tool_name}' is not available.",
                "exit_code": 1,
                "done": self._step_count >= self.max_steps,
                "reward": -0.02,
            }

        # Handle flag submission locally for speed.
        # Models may use any of: content, flag, value, submission — accept all.
        if tool_name in ("submit_flag", "flag_found"):
            submitted = _extract_flag_value(arguments).strip()
            correct = bool(self.ground_truth) and submitted == self.ground_truth
            self._done = bool(correct or self._step_count >= self.max_steps)
            if correct:
                return {
                    "stdout": f"Correct! Flag verified: {submitted}",
                    "stderr": "",
                    "exit_code": 0,
                    "done": True,
                    "reward": 1.0,
                }
            else:
                return {
                    "stdout": f"Incorrect submission: {submitted}",
                    "stderr": "",
                    "exit_code": 1,
                    "done": self._done,
                    "reward": -0.2,
                }

        stdout = f"Executed {tool_name} on {self.target} (MOCK)"
        exit_code = 0
        reward = 0.05
        done = self._step_count >= self.max_steps

        return {
            "stdout": stdout,
            "stderr": "",
            "exit_code": exit_code,
            "done": done,
            "reward": reward,
        }

    def close(self) -> None:
        pass
