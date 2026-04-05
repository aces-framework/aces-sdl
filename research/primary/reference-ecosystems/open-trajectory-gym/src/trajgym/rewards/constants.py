"""Shared constants for the CTF reward system.

Phase classification data, known tool registries, and placeholder flag
values used across reward scoring signals.
"""

# Placeholder flag strings that should not be used for matching.
# "CHECK" is used by PortSwigger challenges (appears in system prompt).
_FLAG_PLACEHOLDERS = frozenset(
    {
        "content_of_flag_here",
        "FLAG{...}",
        "",
        "CHECK",
        # Dummy/fake flags found in Online RL data (poisoned ground truth)
        "gctf{DUMMY_FLAG}",
        "flag{this_is_fake_flag}",
    }
)

# ---------------------------------------------------------------------------
# Phase classification for skill progression (set-based, NO regex).
# Classify commands by first token (binary name) of shell commands.
# ---------------------------------------------------------------------------
_RECON_BINARIES = frozenset(
    {
        "nmap",
        "masscan",
        "ping",
        "traceroute",
        "whois",
        "dig",
        "nslookup",
        "host",
        "arp-scan",
        "netdiscover",
        "ftp",
        "smbclient",
        "smbmap",
        "rpcclient",
        "snmpwalk",
        "enum4linux",
    }
)
_ENUM_BINARIES = frozenset(
    {
        "curl",
        "wget",
        "gobuster",
        "ffuf",
        "dirb",
        "dirsearch",
        "nikto",
        "wpscan",
        "whatweb",
        "ls",
        "cat",
        "head",
        "tail",
        "find",
        "grep",
        "egrep",
        "fgrep",
        "strings",
        "file",
        "id",
        "whoami",
        "ps",
        "env",
        "uname",
        "hostname",
        "ip",
        "ifconfig",
        "netstat",
        "ss",
        "wc",
        "sort",
        "uniq",
        "less",
        "more",
        "xxd",
        "hexdump",
        "objdump",
        "readelf",
        "cd",
        "echo",
        "which",
        "sed",
        "awk",
        "apt",
        "apt-get",
        "pip",
        "pip3",
        "export",
        "mkdir",
        "cp",
        "mv",
        "rm",
        "printf",
        "crackmapexec",
        "fls",
        "tesseract",
        "unzip",
        "tar",
        "gunzip",
    }
)
_EXPLOIT_BINARIES = frozenset(
    {
        "sqlmap",
        "hydra",
        "john",
        "hashcat",
        "python",
        "python3",
        "python2",
        "ruby",
        "perl",
        "gcc",
        "g++",
        "make",
        "nc",
        "ncat",
        "netcat",
        "ssh",
        "scp",
        "msfconsole",
        "msfvenom",
        "chmod",
        "chown",
        "gdb",
        "ltrace",
        "strace",
        "pwntools",
        "sshpass",
        "bash",
        "node",
        "java",
        "docker",
        "php",
        "socat",
    }
)
# Tool names (not shell commands) that map directly to phases.
_TOOL_NAME_PHASES = {
    "web_search": "recon",
    "WebFetch": "recon",
    "read_file": "enum",
    "Read": "enum",
    "read": "enum",
    "grep": "enum",
    "file_search": "enum",
    "python_code": "exploit",
    "python3_code": "exploit",
    "apply_patch": "exploit",
    "Write": "exploit",
    "Edit": "exploit",
    "flag_found": "flag",
}

# ---------------------------------------------------------------------------
# Known instrument registry -- information specificity filter.
#
# Includes all phase-classified tools + shell/exec wrappers + session
# management + orchestration tools found in real BoxPwnr traces.
# ---------------------------------------------------------------------------
_KNOWN_TOOL_NAMES = frozenset(
    set(_TOOL_NAME_PHASES.keys())
    | {
        "shell_command",
        "exec_command",
        "execute_command",
        "shell",
        "bash",
        "Bash",
        "write_stdin",
        "tmux_send_keys",
        "tmux_create_session",
        "tmux_read_output",
        # Session/orchestration (no phase, but still known instruments)
        "close_session",
        "list_sessions",
        "update_plan",
        "Task",
        "TaskOutput",
        "TaskStop",
    }
)

# Shell wrapper tool names (used for action fingerprinting in recovery).
_SHELL_WRAPPERS = frozenset(
    {
        "shell_command",
        "exec_command",
        "execute_command",
        "shell",
        "bash",
        "Bash",
    }
)
