# Synthetic Data Generation Manifests

YAML configuration files that define simulated CTF environments for offline trajectory generation.

## Manifest Schema

```yaml
# Required
name: "challenge_name"                    # Unique challenge identifier
description: "What the challenge is"      # Shown to the teacher LLM as context
ground_truth_flag: "FLAG{...}"            # Template flag (randomized per episode via UUID)

# Optional — environment context
context_depth: "high"                     # Currently unused, reserved for future
env_vars:                                 # Environment variables visible via `env`/`printenv`
  KEY: "value"

# Hosts — define the attack surface
hosts:
  - hostname: "target.example.com"        # DNS name (used for nmap, curl matching)
    ip: "10.0.0.1"                        # IP address (used for nmap, curl matching)
    os_type: "linux"                      # linux | windows (affects output formatting)
    services:                             # Open services (shown in nmap scans)
      - port: 80
        name: "http"                      # Service name (nmap output)
        version: "Apache 2.4.41"          # Version string (optional)
        banner: ""                        # Banner string (optional, shown as nmap |_ line)

# Files — discoverable artifacts in the simulated filesystem
files:
  - path: "/etc/passwd"                   # Absolute path (used for read_file, cat, find)
    content: |                            # File content (returned on read)
        root:x:0:0:root:/root:/bin/bash
    owner: "root"                         # Optional, default "root"
    permissions: "rw-r--r--"              # Optional, default "rw-r--r--"

# Tool Responses — scripted outputs keyed by tool name + regex pattern
tool_responses:
  "shell_command":                        # Tool name (shell_command, execute_command, etc.)
    "nmap.*10.0.0.1": |                   # Regex pattern matched against the command
      PORT    STATE SERVICE
      80/tcp  open  http
    "curl.*target.*8080": |               # Another pattern — longest match wins
      <html><body>Hello</body></html>

# World State Dynamics (optional, advanced)
world_state_dynamics:
  enforce_topology: true                  # Enable network topology constraints
  namespaces:                             # Network zones with egress rules
    - name: "dmz"
      allowed_egress: ["internal"]
    - name: "internal"
      allowed_egress: ["db-zone"]
  synthetic_faults:                       # Fault injection parameters
    pod_eviction_rate: 0.05               # Chance of pod eviction per step
    api_rate_limiting: true               # Enable rate limiting simulation
    latency_jitter_ms: 200                # Added latency jitter
```

## Tool Response Matching

Patterns under `tool_responses.shell_command` are matched against every shell command using a 3-tier priority system:

1. **Regex match** (`re.search(pattern, cmd)`) — highest priority
2. **Substring match** (`pattern in cmd`)
3. **Token fragment match** (all space-separated tokens found in cmd)

Within each tier, the **longest pattern wins**. This means more specific patterns automatically take precedence:

```yaml
# This pattern (53 chars) beats the generic one (32 chars) for script URLs
"curl.*-X POST.*(jenkins).*(script|scriptText)": "Result: jenkins"
"curl.*(jenkins).*8080": "<html>Dashboard</html>"
```

### Pattern Tips

- Use `.*` between command parts to handle arbitrary flags: `kubectl.*get pod` matches `kubectl --kubeconfig /root/.kube/config get pods -A`
- Use alternation for hostnames/IPs: `nmap.*(10.0.0.10|DC01)` matches either
- Use `\b` word boundaries to prevent partial matches: `kubectl.* get (ns|namespaces?)\b`
- Put the flag in the response for the "winning" command pattern

## Included Manifests

| File | Scenario | Key Tools | Difficulty |
|------|----------|-----------|------------|
| `default.yaml` | Internal wiki SQL injection + data exfiltration | nmap, curl, mysql, cat | Easy |
| `incident_response_k8s.yaml` | K8s cryptominer detection & remediation | kubectl, curl (k8s API), read_file | Medium |
| `pentest_lateral_movement.yaml` | Jenkins RCE → SSH lateral movement to DB | nmap, curl, ssh, read_file | Medium |
| `threat_emulation_apt.yaml` | APT lateral movement via SMB/WMI | crackmapexec, smbclient, wmic, impacket | Hard |

## Creating a New Manifest

1. **Define your scenario**: What hosts exist? What services? What's the attack path to the flag?

2. **Start with hosts and files**: These are what the agent discovers first via `ls`, `nmap`, `cat`

3. **Map the critical path**: What sequence of commands leads to the flag? Add `tool_responses` for each step:
   ```yaml
   tool_responses:
     "shell_command":
       "nmap.*target": "PORT 80/tcp open http"              # Step 1: recon
       "curl.*target.*login": "Login page with SQLi"         # Step 2: discover vuln
       "sqlmap.*target": "FLAG{your_flag}"                   # Step 3: exploit → flag
   ```

4. **Add breadcrumbs**: Include discoverable files (`.bash_history`, config files, credential stores) that hint at the intended attack path

5. **Add alternative paths**: Models don't always follow the intended path. Add response patterns for common variants (e.g., `impacket-wmiexec` as alternative to `wmic`)

6. **Test with `test_synth_model.py`**:
   ```bash
   python scripts/test_synth_model.py \
       --model "azure/gpt-5.2-codex" \
       --manifests "your_manifest.yaml"
   ```

## Flag Randomization

The `ground_truth_flag` in YAML is a **template**. At runtime, `WorldManifest.clone()` replaces the flag interior with a random UUID:

```
Template:  FLAG{wmic_process_call_create_detected}
Episode 1: FLAG{a1b2c3d4e5f67890}
Episode 2: FLAG{9876543210fedcba}
```

This replacement propagates to all `files` and `tool_responses` containing the template flag. This prevents the training model from memorizing specific flag strings.
