# Bring Your Own Benchmark

Add any benchmark to the training pipeline by defining a challenge registry YAML file. The platform is domain-agnostic — CTF challenges, SWE tasks, sysadmin scenarios, data analysis problems, or anything where an agent interacts with tools over multiple turns.

## How the Registry Works

The challenge registry is a YAML file that tells the platform three things about each task:

1. **What to give the agent** — a description and (optionally) local files or a network service
2. **How to verify success** — a `ground_truth_flag` string the agent must submit via `flag_found`
3. **Metadata for filtering** — category, difficulty, infrastructure type

Every stage of the pipeline reads this file:

| Stage | What the registry provides |
|-------|---------------------------|
| `trajgym-generate-rl` | Generates `online_rl.jsonl` seed prompts from registry entries |
| `trajgym-train rl` | Looks up `ground_truth_flag` per challenge to compute reward |
| `trajgym-eval` | Runs agent against each challenge, scores against ground truth |
| `trajgym-challenges` | Manages Docker containers for challenges that need a live service |

## Quick Start

### 1. Create a registry

```bash
cp examples/bring-your-own/benchmark/challenge_template.yaml \
   configs/challenges/my_benchmark.yaml
```

Edit the file. Each entry needs these required fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (used in data files, logs, metrics) |
| `category` | string | Arbitrary label for grouping/filtering (e.g., `web`, `crypto`, `swe`, `sysadmin`) |
| `difficulty` | string | One of: `very_easy`, `easy`, `medium`, `hard`, `expert`, `master` |
| `infra_type` | string | `docker` (live networked service) or `static` (local files only) |
| `ground_truth_flag` | string | Exact string the agent must submit. Byte-exact match. |
| `description` | string | Task description given to the agent as the user prompt |

Optional fields: `port` (docker only), `path_hint` (path to challenge files), `name` (display name).

**On `category`**: This is a free-form label — not limited to CTF categories. Use whatever makes sense for your domain: `web`, `binary`, `api`, `k8s`, `database`, `networking`, etc. Categories are used for filtering and reporting only.

**On `ground_truth_flag`**: This is the success signal for reward computation. For CTF benchmarks it's a literal flag string. For other domains, it can be any verifiable answer — a hash, a specific output value, a secret token planted in the environment. The agent submits it via the `flag_found` tool and the reward function checks for exact match.

### 2. Set up infrastructure (if needed)

**Docker challenges** — the agent connects to a live service:

```bash
# Start containers for your challenges
trajgym-challenges setup --registry configs/challenges/my_benchmark.yaml

# Verify all services are reachable
trajgym-challenges status --registry configs/challenges/my_benchmark.yaml
```

**Static challenges** — the agent works with local files only. Place files at the `path_hint` paths relative to your benchmark root. No containers needed.

### 3. Generate training data

```bash
# Create online RL seed prompts from your registry
trajgym-generate-rl \
  --registry configs/challenges/my_benchmark.yaml \
  --output data/online_rl.jsonl

# (Optional) Validate data + registry consistency
trajgym-validate --mode online_rl-preflight \
  --online-rl-data data/online_rl.jsonl \
  --challenge-registry configs/challenges/my_benchmark.yaml
```

### 4. Train and evaluate

```bash
# Online RL against your benchmark
trajgym-train rl \
  --model outputs/sft-merged \
  --data data/online_rl.jsonl \
  --output outputs/online_rl_custom \
  --config examples/qwen35-27b/training.yaml \
  --challenge-registry configs/challenges/my_benchmark.yaml

# Evaluate
trajgym-eval \
  --model outputs/online_rl_custom/final \
  --challenge-registry configs/challenges/my_benchmark.yaml
```

## Registry Examples

### Security (CTF)

```yaml
- id: my-web-challenge
  category: web
  difficulty: easy
  infra_type: docker
  port: 8080
  ground_truth_flag: FLAG{sql_injection_success}
  description: >
    Analyze the web application at localhost:8080 and find the flag.
```

### SWE / Code Generation

```yaml
- id: fix-auth-bug
  category: swe
  difficulty: medium
  infra_type: static
  path_hint: benchmark/swe-tasks/auth-bug
  ground_truth_flag: PASS{all_tests_green_abc123}
  description: >
    Fix the authentication bug in the Flask app at $TMP_DIR/app.py.
    Run the test suite with pytest. The flag is printed when all tests pass.
```

### System Administration

```yaml
- id: k8s-misconfigured-rbac
  category: k8s
  difficulty: hard
  infra_type: docker
  port: 6443
  ground_truth_flag: ADMIN{cluster_role_escalation_complete}
  description: >
    A Kubernetes cluster at localhost:6443 has misconfigured RBAC.
    Escalate from a read-only service account to cluster-admin
    and read the flag from the kube-system namespace.
```

## Tips

- **Flags must be byte-exact.** Verify by solving the challenge manually before adding to the registry.
- **Docker challenges need port mappings.** The `port` field is the host-side port the container exposes.
- **Use `trajgym-challenges status`** to verify all containers are reachable before training.
- **Remote GPU setups**: Use `--target-map` to map registry ports to actual endpoints (e.g., SSH tunnel ports). See [docs/training.md](../../../docs/training.md) for details.
- **Mix benchmarks**: You can combine multiple registries or put challenges from different sources in one file.

## Reference

See [`configs/challenges/cybench.yaml`](../../../configs/challenges/cybench.yaml) for the full 40-challenge CyBench registry, or [`challenge_template.yaml`](challenge_template.yaml) for an annotated template.
