"""
Offline Simulated environment mimicking the ToolExecutor interface for fast, scalable generation.
"""

import logging
import os
import re
from typing import Any

from ..envs.tool_executor import ALL_TOOLS, BaseExecutor
from .manifest import WorldManifest

logger = logging.getLogger(__name__)


class SimulatedEnvironmentExecutor(BaseExecutor):
    """
    Offline executor that mocks all tool effects based on a WorldManifest.
    Removes realistic container execution to eliminate simulation drift.
    """

    def __init__(self, manifest: WorldManifest, **kwargs):
        super().__init__(**kwargs)
        self.manifest_template = manifest
        self.tools = kwargs.get("tools") or sorted(ALL_TOOLS)
        self.max_steps = kwargs.get("max_steps", 30)
        # State
        self._step_count = 0
        self._done = False
        self._current_manifest: WorldManifest = self.manifest_template.clone()
        # ground_truth must use the CLONED manifest (flag is randomized per episode)
        self.ground_truth = self._current_manifest.ground_truth_flag
        self._cwd = "/root"

    def reset(self, generation_id: str | None = None) -> dict:
        self._step_count = 0
        self._done = False
        self._current_manifest = self.manifest_template.clone()
        self.ground_truth = self._current_manifest.ground_truth_flag
        self._cwd = "/root"
        return {
            "stdout": f"Simulated environment loaded: {self._current_manifest.name}",
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

        # Handle mock flag submission
        if tool_name in ("submit_flag", "flag_found"):
            submitted = (
                arguments.get("content", "")
                or arguments.get("flag", "")
                or arguments.get("value", "")
            ).strip()
            correct = bool(self.ground_truth) and submitted == self.ground_truth
            self._done = True

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
                    "done": True,
                    "reward": -0.2,
                }

        # Dispatch to mock handling
        stdout, stderr, exit_code = self._handle_mock(tool_name, arguments)

        done = self._step_count >= self.max_steps
        reward = 0.05 if exit_code == 0 else -0.02

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "done": done,
            "reward": reward,
        }

    def close(self) -> None:
        pass

    # -- Path resolution --
    def _resolve_file(self, path: str) -> str | None:
        """Resolve a file path against the manifest, trying multiple strategies."""
        files = self._current_manifest.files

        # 1. Exact match
        norm = os.path.normpath(path)
        if norm in files:
            return norm

        # 2. Try as absolute
        if not path.startswith("/"):
            abs_path = os.path.normpath(os.path.join(self._cwd, path))
            if abs_path in files:
                return abs_path

        # 3. Basename match (fallback for relative paths like "config.php")
        basename = os.path.basename(path)
        matches = [fp for fp in files if os.path.basename(fp) == basename]
        if len(matches) == 1:
            return matches[0]

        return None

    # -- Manifest response matching --
    _SHELL_TOOL_NAMES = {"shell_command", "execute_command", "exec_command"}

    def _check_manifest_responses(self, query: str) -> str | None:
        """Check ALL shell-type manifest tool_responses against a command/code string.

        Returns the best matching scripted response.
        Priority: regex match > substring match > token-fragment match.
        Within each tier, prefers the longest-pattern match for specificity.
        """
        regex_matches = []
        substring_matches = []
        fragment_matches = []

        for manifest_key in self._SHELL_TOOL_NAMES:
            patterns = self._current_manifest.tool_responses.get(manifest_key, {})
            for pattern, response in patterns.items():
                # 1. Regex match
                try:
                    if re.search(pattern, query, re.IGNORECASE):
                        regex_matches.append((len(pattern), response))
                        continue
                except re.error:
                    pass
                # 2. Substring containment
                if pattern in query:
                    substring_matches.append((len(pattern), response))
                    continue
                # 3. Token fragment matching
                tokens = pattern.split()
                if len(tokens) >= 2 and all(t in query for t in tokens):
                    fragment_matches.append((len(pattern), response))

        # Return the longest (most specific) match from the highest-priority tier
        for tier in (regex_matches, substring_matches, fragment_matches):
            if tier:
                tier.sort(key=lambda x: x[0], reverse=True)
                return tier[0][1]
        return None

    # -- Mock Dispatchers --
    def _handle_mock(
        self, tool_name: str, args: dict[str, Any]
    ) -> tuple[str, str, int]:
        """Routes tool call dynamically based on manifest mappings or defined logic."""

        # 1. Check tool match overrides from manifest (non-shell tools only).
        #    Shell tools use _check_manifest_responses (which has priority matching)
        #    via _mock_shell, so skip them here to avoid first-match bugs.
        command_query = str(
            args.get(
                "command", args.get("code", args.get("path", args.get("file_path", "")))
            )
        )
        if (
            tool_name not in self._SHELL_TOOL_NAMES
            and tool_name in self._current_manifest.tool_responses
        ):
            # Use longest-match-wins, same as _check_manifest_responses
            regex_matches = []
            for pattern, response in self._current_manifest.tool_responses[
                tool_name
            ].items():
                try:
                    if re.search(pattern, command_query):
                        regex_matches.append((len(pattern), response))
                        continue
                except re.error:
                    pass
                if pattern in command_query:
                    regex_matches.append((len(pattern), response))
            if regex_matches:
                regex_matches.sort(key=lambda x: x[0], reverse=True)
                return regex_matches[0][1], "", 0

        # 2. File read tools
        if tool_name == "read_file":
            return self._mock_read_file(args)

        # 3. Shell/exec commands
        if tool_name in self._SHELL_TOOL_NAMES:
            return self._mock_shell(args)

        # 4. Python code
        if tool_name == "python_code":
            return self._mock_python(args)

        # 5. Grep
        if tool_name == "grep":
            return self._mock_grep(args)

        # 6. File search
        if tool_name == "file_search":
            return self._mock_file_search(args)

        # 7. Web search
        if tool_name == "web_search":
            query = args.get("query", "")
            return f"Web search results for: {query}\nNo relevant results found.", "", 0

        # 8. PTY session tools - stub
        if tool_name in ("list_sessions", "close_session", "write_stdin"):
            return "No active sessions.", "", 0

        return "Simulated execution success", "", 0

    def _mock_read_file(self, args: dict[str, Any]) -> tuple[str, str, int]:
        path = args.get("path", args.get("file_path", ""))
        resolved = self._resolve_file(path)
        if resolved:
            content = self._current_manifest.files[resolved].content
            lines = content.strip().split("\n")
            numbered = "\n".join(f"  {i+1}\t{line}" for i, line in enumerate(lines))
            return numbered, "", 0
        return "", f"cat: {path}: No such file or directory", 1

    def _mock_shell(self, args: dict[str, Any]) -> tuple[str, str, int]:
        cmd = args.get("command", args.get("cmd", ""))

        # --- Check manifest scripted responses first (cross-references all shell keys) ---
        scripted = self._check_manifest_responses(cmd)
        if scripted is not None:
            return scripted, "", 0

        # --- nmap ---
        if "nmap" in cmd:
            return self._mock_nmap(cmd)

        # --- whoami / id / hostname / uname ---
        if cmd.strip() == "whoami" or "whoami" in cmd.split("&&")[0]:
            return "root\n", "", 0
        if "uname" in cmd:
            return (
                "Linux target 5.15.0-88-generic #98-Ubuntu SMP x86_64 GNU/Linux\n",
                "",
                0,
            )
        if cmd.strip() == "id" or "id" in cmd.split("&&"):
            return "uid=0(root) gid=0(root) groups=0(root)\n", "", 0
        if cmd.strip() == "hostname":
            hosts = [h for h in self._current_manifest.hosts.values()]
            name = hosts[0].hostname if hosts else "target"
            return f"{name}\n", "", 0

        # --- pwd ---
        if cmd.strip() == "pwd":
            return f"{self._cwd}\n", "", 0

        # --- ls ---
        if re.match(r"^ls\b", cmd.strip()):
            return self._mock_ls(cmd)

        # --- cat (treat as read_file) ---
        # Skip flags like -A, -n, -v etc. and extract the file path
        cat_match = re.match(r"^cat\s+(?:-[a-zA-Z]+\s+)*([^\s|;&>]+)", cmd.strip())
        if cat_match:
            path = cat_match.group(1).strip().strip("'\"")
            resolved = self._resolve_file(path)
            if resolved:
                return self._current_manifest.files[resolved].content, "", 0
            return "", f"cat: {path}: No such file or directory", 1

        # --- strings / hexdump / xxd / wc / file (binary inspection) ---
        if re.match(r"^(strings|hexdump|xxd|wc|file)\b", cmd.strip()):
            return self._mock_binary_inspect(cmd)

        # --- find ---
        if cmd.strip().startswith("find"):
            return self._mock_find(cmd)

        # --- curl ---
        if "curl" in cmd:
            return self._mock_curl(cmd)

        # --- env / printenv ---
        if cmd.strip() in ("env", "printenv"):
            env_lines = []
            for k, v in self._current_manifest.env_vars.items():
                env_lines.append(f"{k}={v}")
            env_lines.extend(
                [
                    "HOME=/root",
                    "USER=root",
                    "SHELL=/bin/bash",
                    f"PWD={self._cwd}",
                    "LANG=en_US.UTF-8",
                ]
            )
            return "\n".join(env_lines) + "\n", "", 0

        # --- ps / netstat / ss ---
        if re.match(r"^(ps|netstat|ss)\b", cmd.strip()):
            return self._mock_process_info(cmd)

        # --- generic commands that should succeed silently ---
        if any(
            cmd.strip().startswith(c)
            for c in ("cd ", "mkdir ", "chmod ", "chown ", "touch ", "echo ")
        ):
            if cmd.strip().startswith("cd "):
                self._cwd = cmd.strip()[3:].strip().strip("'\"") or self._cwd
            if cmd.strip().startswith("echo "):
                text = cmd.strip()[5:]
                return text + "\n", "", 0
            return "", "", 0

        # --- grep in shell context ---
        if re.match(r"^(grep|egrep|fgrep)\b", cmd.strip()):
            return self._mock_shell_grep(cmd)

        # --- python3/python inline scripts (heredoc, -c, pipe) ---
        # Models often run `python3 -c '...'` or `python3 - <<'PY' ...` in shell.
        # Route these to _mock_python so they get proper manifest-aware responses.
        if re.match(r"^python[23]?\s+(-|(-c\s))", cmd.strip()):
            # Extract the code portion — use the full command as fallback
            code = cmd
            # -c 'code' — greedy match to last quote to handle nested quotes
            c_match = re.search(r"""-c\s+['"](.*)['"]\s*$""", cmd.strip(), re.DOTALL)
            if c_match:
                code = c_match.group(1)
            # heredoc pattern: python3 - <<'PY'\n...\nPY
            hd_match = re.search(r"<<['\"]?\w+['\"]?\s*\n(.+)", cmd, re.DOTALL)
            if hd_match:
                code = hd_match.group(1)
            return self._mock_python({"code": code})

        # --- Credential-aware fallback ---
        # If the command uses secrets/credentials found in manifest files,
        # return the most relevant scripted response (typically the flag-bearing one).
        # This handles mysql, psql, ssh, crackmapexec, wmic, etc. generically.
        cred_response = self._check_credential_command(cmd)
        if cred_response is not None:
            return cred_response, "", 0

        # --- Fallback: return plausible empty result ---
        return "", "bash: command output unavailable in simulated environment", 0

    def _check_credential_command(self, cmd: str) -> str | None:
        """Generic handler for commands that use credentials/secrets from manifest files.

        Works for mysql, psql, ssh, crackmapexec, wmic, kubectl, etc.
        If the command contains secrets found in manifest files, returns the
        flag-bearing scripted response from tool_responses.
        """
        # Extract potential secrets from all manifest files (passwords, keys, tokens)
        manifest_secrets = set()
        for fnode in self._current_manifest.files.values():
            # Match quoted strings, key-like values, password patterns
            for match in re.findall(r"['\"]([^'\"]{4,})['\"]", fnode.content):
                manifest_secrets.add(match)
            # Also match common credential patterns: key=value, pass=value
            for match in re.findall(
                r"(?:pass|password|secret|key|token)\s*[=:]\s*['\"]?(\S{4,})['\"]?",
                fnode.content,
                re.IGNORECASE,
            ):
                manifest_secrets.add(match.rstrip("';"))

        # Check if the command uses any known secrets
        if not any(secret in cmd for secret in manifest_secrets):
            return None

        # Command uses valid credentials — return the best scripted response.
        # Priority: 1) flag-bearing response, 2) any matching response
        flag = self._current_manifest.ground_truth_flag
        fallback = None
        for manifest_key in self._SHELL_TOOL_NAMES:
            patterns = self._current_manifest.tool_responses.get(manifest_key, {})
            for _pattern, response in patterns.items():
                if flag and flag in response:
                    return response
                if fallback is None:
                    fallback = response
        return fallback

    def _mock_nmap(self, cmd: str) -> tuple[str, str, int]:
        # Deduplicate hosts (manifest stores by hostname AND ip)
        seen_hosts = {}
        for host in self._current_manifest.hosts.values():
            if host.hostname not in seen_hosts:
                seen_hosts[host.hostname] = host

        lines = [
            "Starting Nmap 7.94SVN ( https://nmap.org ) at 2026-03-01 10:00 UTC",
        ]
        for host in seen_hosts.values():
            lines.append(f"Nmap scan report for {host.hostname} ({host.ip})")
            lines.append("Host is up (0.0012s latency).")
            if host.services:
                lines.append("")
                lines.append("PORT      STATE SERVICE       VERSION")
                for srv in host.services:
                    ver = f" {srv.version}" if srv.version else ""
                    lines.append(f"{srv.port}/tcp  open  {srv.name:<14}{ver}")
                    if srv.banner:
                        lines.append(f"|_{srv.banner}")
            lines.append("")

        lines.append(f"Nmap done: {len(seen_hosts)} IP address(es) scanned")
        return "\n".join(lines) + "\n", "", 0

    def _mock_ls(self, cmd: str) -> tuple[str, str, int]:
        # Parse target directory from ls command
        parts = cmd.strip().split()
        target_dir = None
        for p in parts[1:]:
            if not p.startswith("-"):
                target_dir = p
                break
        if target_dir is None:
            target_dir = self._cwd

        target_dir = os.path.normpath(target_dir)
        detailed = "-l" in cmd or "-la" in cmd or "-al" in cmd

        # Collect files under this directory
        entries = []
        seen_dirs = set()
        for fpath in self._current_manifest.files:
            norm = os.path.normpath(fpath)
            parent = os.path.dirname(norm)
            if parent == target_dir or target_dir == "/":
                fname = os.path.basename(norm)
                fnode = self._current_manifest.files[fpath]
                size = len(fnode.content) if fnode.content else 0
                entries.append((fname, fnode.permissions, fnode.owner, size, False))
            # Track subdirectories
            if norm.startswith(target_dir + "/"):
                rel = norm[len(target_dir) + 1 :]
                subdir = rel.split("/")[0]
                if subdir and subdir not in seen_dirs:
                    seen_dirs.add(subdir)
                    entries.append((subdir, "rwxr-xr-x", "root", 4096, True))

        if not entries:
            # Fallback: show all top-level files
            for fpath in self._current_manifest.files:
                fname = os.path.basename(fpath)
                fnode = self._current_manifest.files[fpath]
                size = len(fnode.content) if fnode.content else 0
                entries.append((fname, fnode.permissions, fnode.owner, size, False))

        if detailed:
            lines = [f"total {len(entries) * 4}"]
            for name, perms, owner, size, is_dir in sorted(entries):
                prefix = "d" if is_dir else "-"
                lines.append(
                    f"{prefix}{perms} 1 {owner:<8} {owner:<8} {size:>6} Mar  1 10:00 {name}"
                )
            return "\n".join(lines) + "\n", "", 0
        else:
            names = [e[0] for e in sorted(entries)]
            return "  ".join(names) + "\n", "", 0

    def _mock_find(self, cmd: str) -> tuple[str, str, int]:
        lines = []
        name_match = re.search(r'-name\s+["\']?([^"\']+)["\']?', cmd)
        pattern = name_match.group(1) if name_match else None

        for fpath in sorted(self._current_manifest.files.keys()):
            if pattern:
                # Convert glob to regex
                pat_re = (
                    pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
                )
                if re.search(pat_re, os.path.basename(fpath)):
                    lines.append(fpath)
            else:
                lines.append(fpath)

        return (
            "\n".join(lines) + "\n" if lines else "",
            "" if lines else "find: no matches",
            0,
        )

    def _mock_curl(self, cmd: str) -> tuple[str, str, int]:
        # The full curl command is already checked against manifest tool_responses
        # by _check_manifest_responses in _mock_shell before we get here.
        # This handles cases where no scripted response matched.

        # Extract URL from curl command
        url = None
        tokens = re.findall(r'[^\s"\']+|"[^"]*"|\'[^\']*\'', cmd)
        for tok in tokens:
            tok_clean = tok.strip("'\"")
            if re.match(r"https?://", tok_clean):
                url = tok_clean
                break
            if re.match(r"\d+\.\d+\.\d+\.\d+:\d+", tok_clean) or re.match(
                r"[a-zA-Z][\w.-]+:\d+", tok_clean
            ):
                url = f"http://{tok_clean}"
                break
        if not url:
            for tok in tokens:
                tok_clean = tok.strip("'\"")
                for host in self._current_manifest.hosts.values():
                    if host.ip == tok_clean or host.hostname == tok_clean:
                        url = f"http://{tok_clean}"
                        break
                if url:
                    break
        if not url:
            return "", "curl: no URL specified", 1

        # Check if it matches any host in the manifest
        for host in self._current_manifest.hosts.values():
            if host.ip in url or host.hostname in url:
                services = ", ".join(f"{s.name}:{s.port}" for s in host.services)
                http_services = [
                    s
                    for s in host.services
                    if s.name in ("http", "https", "http-proxy")
                ]
                if http_services:
                    srv = http_services[0]
                    return (
                        (
                            f"<!DOCTYPE html>\n<html>\n<head><title>{host.hostname}</title></head>\n"
                            f"<body>\n<h1>Welcome to {host.hostname}</h1>\n"
                            f"<p>Server: {srv.version}</p>\n"
                            f"</body>\n</html>\n"
                        ),
                        "",
                        0,
                    )
                return (
                    f"Connection to {host.hostname} ({host.ip}) established.\nServices: {services}\n",
                    "",
                    0,
                )

        return "", f"curl: (7) Failed to connect to {url}", 1

    def _mock_grep(self, args: dict[str, Any]) -> tuple[str, str, int]:
        pattern_str = args.get("pattern", "")
        search_path = args.get("path", ".")

        results = []
        try:
            pat = re.compile(pattern_str, re.IGNORECASE)
        except re.error:
            pat = re.compile(re.escape(pattern_str), re.IGNORECASE)

        for fpath, fnode in self._current_manifest.files.items():
            if search_path != "." and not fpath.startswith(search_path):
                continue
            for i, line in enumerate(fnode.content.split("\n"), 1):
                if pat.search(line):
                    results.append(f"{fpath}:{i}:{line.strip()}")

        if results:
            return "\n".join(results) + "\n", "", 0
        return "", "grep: no matches found", 1

    def _mock_shell_grep(self, cmd: str) -> tuple[str, str, int]:
        # Parse grep pattern and file from shell command
        match = re.search(
            r"(?:grep|egrep|fgrep)\s+(?:-[a-zA-Z]*\s+)*['\"]?([^'\"]+?)['\"]?\s+(.+)$",
            cmd.strip(),
        )
        if not match:
            return "", "grep: missing pattern", 1

        pattern_str = match.group(1)
        target = match.group(2).strip()

        results = []
        try:
            pat = re.compile(pattern_str, re.IGNORECASE)
        except re.error:
            pat = re.compile(re.escape(pattern_str), re.IGNORECASE)

        for fpath, fnode in self._current_manifest.files.items():
            if (
                target != "."
                and target not in fpath
                and os.path.basename(fpath) != target
            ):
                continue
            for i, line in enumerate(fnode.content.split("\n"), 1):
                if pat.search(line):
                    results.append(f"{fpath}:{i}:{line.strip()}")

        if results:
            return "\n".join(results) + "\n", "", 0
        return "", f"grep: {pattern_str}: no matches", 1

    def _mock_python(self, args: dict[str, Any]) -> tuple[str, str, int]:
        code = args.get("code", "")

        # 1. Check manifest scripted responses (e.g. python code that runs mysql)
        scripted = self._check_manifest_responses(code)
        if scripted is not None:
            return scripted, "", 0

        # 2. If code uses credentials from manifest files (DB, SSH, HTTP, etc.),
        #    return the best scripted response via the generic credential handler
        cred_response = self._check_credential_command(code)
        if cred_response is not None:
            return cred_response, "", 0

        # 3. If code references files in manifest, return the file contents.
        #    This handles patterns like Path('file').read_text(), open('file'), etc.
        matched_files = []
        for fpath, fnode in self._current_manifest.files.items():
            if fpath in code or os.path.basename(fpath) in code:
                matched_files.append((fpath, fnode))
        if matched_files:
            parts = []
            for _fpath, fnode in matched_files:
                parts.append(fnode.content.strip())
            return "\n---\n".join(parts) + "\n", "", 0

        # 4. If code uses requests/urllib/socket to hit manifest hosts, check
        #    manifest tool_responses first (the full code as query), then fall back
        #    to generic HTML.
        if any(ind in code for ind in ("requests.", "urllib", "http.client", "socket")):
            for host in self._current_manifest.hosts.values():
                if host.ip in code or host.hostname in code:
                    http_svcs = [
                        s for s in host.services if s.name in ("http", "https")
                    ]
                    if http_svcs:
                        srv = http_svcs[0]
                        return (
                            (
                                f"<Response [200]>\n"
                                f"<!DOCTYPE html>\n<html><head><title>{host.hostname}</title></head>\n"
                                f"<body><h1>Welcome to {host.hostname}</h1>\n"
                                f"<p>Server: {srv.version}</p></body></html>\n"
                            ),
                            "",
                            0,
                        )

        return "Python code executed successfully.\n", "", 0

    def _mock_file_search(self, args: dict[str, Any]) -> tuple[str, str, int]:
        pattern = args.get("pattern", "*")
        args.get("path", ".")

        pat_re = pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
        results = []
        for fpath in sorted(self._current_manifest.files.keys()):
            if re.search(pat_re, os.path.basename(fpath)):
                results.append(fpath)

        if results:
            return "\n".join(results) + "\n", "", 0
        return "", f"No files matching '{pattern}' found", 1

    def _mock_binary_inspect(self, cmd: str) -> tuple[str, str, int]:
        """Handle strings, hexdump, xxd, wc, file commands on manifest files."""
        # Extract the file path (last non-flag argument)
        tokens = cmd.strip().split()
        path = None
        for tok in reversed(tokens[1:]):
            if not tok.startswith("-"):
                path = tok.strip("'\"")
                break
        if not path:
            return "", f"{tokens[0]}: missing file operand", 1

        resolved = self._resolve_file(path)
        if not resolved:
            return "", f"{tokens[0]}: {path}: No such file or directory", 1

        content = self._current_manifest.files[resolved].content
        tool = tokens[0]
        if tool == "strings":
            # Return printable strings from the file content
            return content, "", 0
        elif tool in ("hexdump", "xxd"):
            # Return a hex dump of first few bytes
            raw = content.encode()[:64]
            hex_lines = []
            for i in range(0, len(raw), 16):
                chunk = raw[i : i + 16]
                hex_part = " ".join(f"{b:02x}" for b in chunk)
                ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                hex_lines.append(f"{i:08x}  {hex_part:<48}  |{ascii_part}|")
            return "\n".join(hex_lines) + "\n", "", 0
        elif tool == "wc":
            lines = content.count("\n")
            words = len(content.split())
            chars = len(content)
            return f"  {lines}  {words} {chars} {path}\n", "", 0
        elif tool == "file":
            return f"{path}: ASCII text\n", "", 0
        return content, "", 0

    def _mock_process_info(self, cmd: str) -> tuple[str, str, int]:
        if cmd.strip().startswith("ps"):
            lines = [
                "USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND",
                "root           1  0.0  0.0   2416   512 ?        Ss   10:00   0:00 /sbin/init",
            ]
            for host in self._current_manifest.hosts.values():
                for srv in host.services:
                    lines.append(
                        f"root       {100+srv.port:>5}  0.1  0.2  45000  8192 ?        Sl   10:00   0:05 {srv.name} (port {srv.port})"
                    )
            return "\n".join(lines) + "\n", "", 0

        if cmd.strip().startswith(("netstat", "ss")):
            lines = [
                "Proto  Recv-Q Send-Q Local Address           Foreign Address         State"
            ]
            for host in self._current_manifest.hosts.values():
                for srv in host.services:
                    lines.append(
                        f"tcp    0      0 0.0.0.0:{srv.port}            0.0.0.0:*               LISTEN"
                    )
            return "\n".join(lines) + "\n", "", 0

        return "", "", 0
