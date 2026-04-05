# Bring Your Own (BYO) Benchmark

Open CTF Environment is designed to be domain-agnostic. While it ships with CyBench natively, you can plug in any benchmark that involves an agent interacting with a target environment (e.g., Cyber Gym, xbow, SWE-bench, custom internal CTFs).

The platform interfaces with benchmarks via **Challenge Registries** (YAML files) and the `ChallengeManager`, which handles the lifecycle of target environments.

## The Challenge Registry

A benchmark is defined entirely by a single YAML file in `configs/challenges/`. You do not need to write Python code to integrate a new benchmark, provided the benchmark repository follows standard Docker Compose conventions.

### Copy the Template

```bash
cp examples/bring-your-own/benchmark/challenge_template.yaml configs/challenges/my_benchmark.yaml
```

### Registry Structure

```yaml
challenges:
  - id: my-web-1                    # Unique ID across the platform
    name: "Web Exploitation 1"      # Display name
    category: web                   # Category grouping
    difficulty: easy                # Difficulty grouping
    infra_type: docker              # "docker" (network service) or "static" (file-only)
    port: 8080                      # The HOST port the container will bind to
    path_hint: web/my-web-1         # Relative path to challenge files from benchmark root
    ground_truth_flag: "FLAG{...}"  # The exact string the agent must submit
```

## Infrastructure Requirements (The "Gotchas")

The `ChallengeManager` looks for specific markers to launch `docker` infra_type challenges. Your benchmark repository **must** conform to one of the following for each challenge directory:

### 1. The `docker-compose.yaml` Standard (Recommended)
If a challenge directory contains a `docker-compose.yaml` (or `.yml`), the platform will automatically run `docker compose up -d` in that directory. 

**Port Collision Warning:** The platform does not dynamically allocate ports. If your registry YAML says `port: 8080`, your `docker-compose.yaml` **must** map the host port to 8080 (e.g., `ports: ["8080:80"]`). If multiple challenges bind to the same host port, the launch will crash. Ensure unique port mappings across your entire benchmark suite.

### 2. The `start_docker.sh` Fallback
If there is no compose file, the platform will look for an executable bash script named `start_docker.sh`. It will run this script to launch the challenge. If this method is used, the platform will subsequently look for a `stop_docker.sh` during teardown.

> **Important**: If your target directory has neither a compose file nor a `start_docker.sh`, the ChallengeManager will throw a `RuntimeError`.

## Path Resolution Magic & Dangers

When you run a challenge, the platform tries to find its directory inside your benchmark root (e.g., `--benchmark-root /workspace/my_benchmark`). 

The `ChallengeManager` uses a fuzzy-matching heuristic to find the directory based on the challenge `id`, `name`, and directory names. 

**Best Practice:** To avoid the platform accidentally launching the wrong challenge in massive benchmark repositories with duplicate folder names, **always** provide an explicit `path_hint` in your registry YAML.

```yaml
# Good: Deterministic
path_hint: path/to/the/exact/challenge/folder

# Bad: Relies on fuzzy matching the 'id' against the filesystem
path_hint: "" 
```

## Integrating Global Orchestrators (xbow, Cyber Gym)

Some modern benchmarks (like xbow) use a global Python orchestrator rather than individual `docker-compose` files (e.g., `python launch.py --env challenge-1`). 

Because our `ChallengeManager` strictly requires a `docker-compose.yaml` or `start_docker.sh` *inside* the specific challenge directory, you must create a bridge.

### The `start_docker.sh` Bridge Pattern

To integrate frameworks like xbow, you can automatically generate a flat directory structure where each challenge folder contains a simple `start_docker.sh` wrapper script that calls the overarching orchestrator.

**Example `my_benchmark/challenge-1/start_docker.sh`:**
```bash
#!/bin/bash
# Bridge to the xbow orchestrator
cd /workspace/xbow-benchmark
python3 -m xbow start challenge-1 --port 8080
```

**Example `my_benchmark/challenge-1/stop_docker.sh`:**
```bash
#!/bin/bash
cd /workspace/xbow-benchmark
python3 -m xbow stop challenge-1
```

Point your `path_hint` to these bridge folders, and the Open CTF platform will transparently orchestrate the external framework.

## Lifecycle Commands

Once your registry YAML is ready, you can manage the external benchmark entirely through the `open-ctf` CLI:

```bash
# Launch all challenges in the registry
open-ctf-challenges setup --registry configs/challenges/my_benchmark.yaml --benchmark-root /workspace/my_benchmark

# Check health status
open-ctf-challenges status --registry configs/challenges/my_benchmark.yaml

# Run an evaluation utilizing the running challenges
open-ctf-eval --model Qwen/Qwen3.5-27B --challenges configs/challenges/my_benchmark.yaml

# Tear down all containers
open-ctf-challenges teardown --registry configs/challenges/my_benchmark.yaml
```
