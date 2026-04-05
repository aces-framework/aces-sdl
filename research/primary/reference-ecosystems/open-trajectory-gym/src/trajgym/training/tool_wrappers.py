"""Tool wrappers for CTF environment interaction via ToolExecutor.

These functions provide a typed Python interface to the ToolExecutor
for direct subprocess execution.  JSON tool schemas are auto-generated
from the Google-style docstrings and type annotations, making them
compatible with SkyRL and other trainers that accept callable tools.

Full BoxPwnr tool set (13 tools, organized by tier):

  Tier 1 -- Execution:  shell_command, exec_command, write_stdin,
                        python_code, execute_command
  Tier 2 -- File ops:   read_file, grep, file_search, apply_patch
  Tier 3 -- Meta:       flag_found, submit_flag, web_search,
                        list_sessions, close_session

Episode management
------------------
When multiple generations run against the same environment,
cross-contamination must be prevented:

1. ``mark_step_begin()`` -- called by the trainer at the start of each
   batch.  Resets the environment and clears episode-done state.
2. ``_episode_done`` flag -- once ``flag_found()`` returns success for
   *any* generation, subsequent tool calls return an early-exit string
   instead of executing.

Usage::

    from trajgym.training.tool_wrappers import get_all_tools, init_env

    init_env()
    tools = get_all_tools()  # returns list of callables
"""

import logging
import threading

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level ToolExecutor
# ---------------------------------------------------------------------------

_executor = None  # type: ignore
_episode_id: str | None = None

# Episode lifecycle tracking (managed by the Online RL trainer).
_thread_local = threading.local()
_batch_gen: int = 0
_batch_gen_lock = threading.Lock()


def _sync_thread_state() -> None:
    """Reset thread-local episode state if the batch generation has advanced."""
    local_gen = getattr(_thread_local, "batch_gen", -1)
    if local_gen != _batch_gen:
        _thread_local.batch_gen = _batch_gen
        _thread_local.episode_done = False
        _thread_local.step_count = 0


def _get_episode_done() -> bool:
    _sync_thread_state()
    return getattr(_thread_local, "episode_done", False)


def _set_episode_done(value: bool) -> None:
    _sync_thread_state()
    _thread_local.episode_done = value


def _get_step_count() -> int:
    _sync_thread_state()
    return getattr(_thread_local, "step_count", 0)


def _set_step_count(value: int) -> None:
    _sync_thread_state()
    _thread_local.step_count = value


def init_env(
    target: str = "",
    ground_truth: str = "",
    max_steps: int = 30,
    stdout_limit: int = 4096,
) -> None:
    """Initialize the ToolExecutor.

    Must be called before any tool function is used.

    Args:
        target: Target URL or description.
        ground_truth: Expected flag for verification.
        max_steps: Maximum steps per episode.
        stdout_limit: Max characters kept from tool stdout.
            Default 4096.  Increase for challenges where critical
            information appears deep in large files (e.g. JS source).
    """
    global _executor
    from trajgym.envs.tool_executor import SubprocessExecutor

    _executor = SubprocessExecutor(
        target=target,
        ground_truth=ground_truth,
        max_steps=max_steps,
        stdout_limit=stdout_limit,
    )
    logger.info("ToolExecutor initialized (target=%s)", target or "(default)")


def reset_env(challenge_id: str | None = None, ground_truth: str | None = None) -> str:
    """Reset the environment for a new episode.

    Args:
        challenge_id: Optional challenge identifier (unused, kept for API compat).
        ground_truth: Optional ground-truth flag for this episode.

    Returns:
        The initial observation text from the environment.
    """
    _ensure_initialized()
    if ground_truth is not None:
        _executor.ground_truth = ground_truth
    resp = _executor.reset()
    return resp.get("stdout", "Environment reset.")


def close_env() -> None:
    """Close the ToolExecutor and release resources."""
    global _executor
    if _executor is not None:
        _executor.close()
    _executor = None
    logger.info("ToolExecutor closed")


def mark_step_begin(
    challenge_id: str | None = None, ground_truth: str | None = None
) -> None:
    """Reset environment and clear episode state for a new training step.

    Called by the Online RL trainer before each batch's tool-call loop.

    Args:
        challenge_id: Optional challenge to load on reset (unused, kept for API compat).
        ground_truth: Optional ground-truth flag for this episode.
    """
    global _batch_gen
    with _batch_gen_lock:
        _batch_gen += 1
    _set_episode_done(False)
    _set_step_count(0)
    reset_env(challenge_id, ground_truth=ground_truth)
    logger.debug(
        "Episode reset — step_begin (challenge=%s, has_flag=%s, batch_gen=%d)",
        challenge_id,
        ground_truth is not None,
        _batch_gen,
    )


def is_episode_done() -> bool:
    """Return whether the current episode's flag has been found."""
    return _get_episode_done()


def get_last_step_info() -> dict:
    """Return metadata from the last environment step."""
    return {}


# ---------------------------------------------------------------------------
# Tool collections
# ---------------------------------------------------------------------------


def get_all_tools() -> list:
    """Return the curated tool set for Online RL training.

    Returns the 8 core tools for online RL.

    Included (8 tools): shell_command, python_code, read_file, grep,
    file_search, apply_patch, web_search, flag_found.
    """
    return [
        # Tier 1: Execution
        shell_command,
        python_code,
        # Tier 2: File operations
        read_file,
        grep,
        file_search,
        apply_patch,
        # Tier 3: Meta
        flag_found,
        web_search,
    ]


def get_core_tools() -> list:
    """Return only the core 3 tools (backward compatible)."""
    return [shell_command, python_code, flag_found]


# ---------------------------------------------------------------------------
# Tier 1: Execution tools
# ---------------------------------------------------------------------------


def shell_command(command: str, timeout: int = 30) -> str:
    """Run a shell command in the CTF attacker container and return output.

    Use this to execute reconnaissance, enumeration, and exploitation
    commands against the target challenge. Supports pipes, redirects,
    and multi-line scripts.

    Args:
        command: The shell command to execute (e.g. ``nmap -sV target``).
        timeout: Maximum execution time in seconds. Defaults to 30.

    Returns:
        The combined stdout and stderr output from the command.
    """
    return _step("shell_command", {"command": command, "timeout": timeout})


def exec_command(cmd: str, workdir: str = "", yield_time: int = 5) -> str:
    """Start an interactive process in a PTY session and return its output.

    Returns a session ID for ongoing interaction via write_stdin. Use this
    for interactive programs like bash, python3, ssh, gdb, or netcat.
    For non-interactive commands, prefer shell_command instead.

    Args:
        cmd: Shell command to execute (e.g. ``python3``, ``ssh user@host``).
        workdir: Optional working directory to run the command in.
        yield_time: Seconds to wait for initial output before returning.
            Defaults to 5.

    Returns:
        Session ID and initial output from the process.
    """
    args = {"cmd": cmd, "yield_time": yield_time}
    if workdir:
        args["workdir"] = workdir
    return _step("exec_command", args)


def write_stdin(session_id: str, chars: str = "", yield_time: int = 2) -> str:
    """Send input to a running PTY session and return new output.

    Use this to interact with processes started via exec_command.
    Pass empty chars to poll for new output without sending input.

    Args:
        session_id: Numeric ID of the session (e.g. ``1``, ``2``).
        chars: Text to write to stdin. May be empty to just poll output.
        yield_time: Seconds to wait for output after writing. Defaults to 2.

    Returns:
        Process status and any new output from the session.
    """
    return _step(
        "write_stdin",
        {
            "session_id": session_id,
            "chars": chars,
            "yield_time": yield_time,
        },
    )


def python_code(code: str, timeout: int = 120) -> str:
    """Execute Python code in the CTF attacker container.

    Use this for complex exploits, payload generation, encoding/decoding,
    crypto operations, or data processing. Use print() to see output.

    Args:
        code: Python source code to execute.
        timeout: Maximum execution time in seconds. Defaults to 120.

    Returns:
        The output from executing the Python code.
    """
    return _step("python_code", {"code": code, "timeout": timeout})


def execute_command(command: str, timeout: int = 30) -> str:
    """Execute a non-interactive command and return complete output.

    Similar to shell_command. Use this for commands that produce output
    and exit. For interactive programs, use exec_command instead.

    Args:
        command: Shell command to execute.
        timeout: Maximum execution time in seconds. Defaults to 30.

    Returns:
        The combined stdout and stderr output from the command.
    """
    return _step("execute_command", {"command": command, "timeout": timeout})


# ---------------------------------------------------------------------------
# Tier 2: File operation tools
# ---------------------------------------------------------------------------


def read_file(file_path: str, line_numbers: bool = True) -> str:
    """Read the contents of a file in the CTF environment.

    Returns file content with optional line numbers for reference.

    Args:
        file_path: Path to the file to read.
        line_numbers: Whether to include line numbers. Defaults to True.

    Returns:
        The file contents, optionally with line numbers.
    """
    return _step("read_file", {"file_path": file_path, "line_numbers": line_numbers})


def grep(pattern: str, path: str = ".", include: str = "") -> str:
    """Search for a regex pattern in files.

    Returns matching lines with file paths and line numbers.

    Args:
        pattern: Regex pattern to search for.
        path: Directory to search in. Defaults to current directory.
        include: File pattern to include (e.g. ``*.py``). Optional.

    Returns:
        Grep results with line numbers and context.
    """
    args = {"pattern": pattern, "path": path}
    if include:
        args["include"] = include
    return _step("grep", args)


def file_search(pattern: str, path: str = ".") -> str:
    """Find files by name pattern using the find command.

    Args:
        pattern: Glob pattern to match file names (e.g. ``*.py``, ``flag*``).
        path: Directory to search in. Defaults to current directory.

    Returns:
        List of matching file paths.
    """
    return _step("file_search", {"pattern": pattern, "path": path})


def apply_patch(patch: str) -> str:
    """Apply a patch to modify files in the CTF environment.

    Supports BoxPwnr patch format (*** Begin Patch) and standard diff.

    Args:
        patch: The patch content to apply.

    Returns:
        Result of applying the patch.
    """
    return _step("apply_patch", {"patch": patch})


# ---------------------------------------------------------------------------
# Tier 3: Meta tools
# ---------------------------------------------------------------------------


def flag_found(content: str) -> str:
    """Submit a discovered flag for verification. ONLY call this when you
    have found the EXACT flag string in tool output or a file. Flags
    typically match ``FLAG{...}`` or ``flag{...}`` format. Do NOT guess,
    fabricate, or submit partial flags -- incorrect submissions are
    penalized. The environment verifies the flag and ends the episode
    if correct.

    Args:
        content: The exact flag string copied from tool output
            (e.g. ``FLAG{s3cr3t_v4lu3}``). Must be the complete flag
            including the wrapper (FLAG{...}).

    Returns:
        Verification result indicating whether the flag is correct.
    """
    return _step("flag_found", {"content": content})


def web_search(query: str) -> str:
    """Search the web for information using DuckDuckGo.

    Use this to find documentation, CVE details, exploit code, or other
    public information relevant to the challenge.

    Args:
        query: The search query string.

    Returns:
        Search results with titles, snippets, and URLs.
    """
    return _step("web_search", {"query": query})


def list_sessions() -> str:
    """List all active interactive shell sessions.

    Shows session IDs, commands, and current status. Use this to check
    which PTY sessions are still running.

    Returns:
        List of active sessions with their status.
    """
    return _step("list_sessions", {})


def close_session(session_id: str) -> str:
    """Close an interactive shell session and free resources.

    Use this when done with a session started via exec_command.

    Args:
        session_id: Numeric ID of the session to close (e.g. ``1``).

    Returns:
        Confirmation that the session was closed.
    """
    return _step("close_session", {"session_id": session_id})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _step(tool_name: str, arguments: dict) -> str:
    """Execute a tool call via ToolExecutor and return the output string.

    Episode-aware: once ``flag_found`` succeeds in *any* generation, all
    further tool calls short-circuit with a done message.
    """
    if _get_episode_done():
        return (
            "[EPISODE COMPLETE] The flag has already been submitted and "
            "verified. No further actions are needed."
        )

    _ensure_initialized()
    _set_step_count(_get_step_count() + 1)

    resp = _executor.step(tool_name, arguments)
    stdout = resp.get("stdout", "")
    stderr = resp.get("stderr", "")
    done = resp.get("done", False)

    # Detect successful episode completion from executor signal only.
    if done:
        _set_episode_done(True)
        logger.info(
            "Episode done after %d steps (flag submitted via %s)",
            _get_step_count(),
            tool_name,
        )

    if stderr:
        return f"{stdout}\n[stderr] {stderr}"
    return stdout


# Keep submit_flag as an alias for backward compatibility
def submit_flag(flag: str) -> str:
    """Submit a captured flag for verification. Alias for flag_found.

    Args:
        flag: The flag string to submit.

    Returns:
        Verification result.
    """
    return flag_found(flag)


def _ensure_initialized() -> None:
    """Raise if init_env() has not been called."""
    if _executor is None:
        raise RuntimeError("ToolExecutor not initialized. Call init_env() first.")
