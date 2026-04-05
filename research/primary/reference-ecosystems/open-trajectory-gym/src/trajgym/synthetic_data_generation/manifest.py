import os
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class Service:
    port: int
    name: str
    version: str = ""
    banner: str = ""


@dataclass
class HostNode:
    ip: str
    hostname: str
    os_type: str = "linux"
    services: list[Service] = field(default_factory=list)


@dataclass
class FileNode:
    path: str
    content: str
    owner: str = "root"
    permissions: str = "rw-r--r--"


@dataclass
class WorldManifest:
    """Defines the deterministic state of a simulated environment for agentic generation."""

    name: str = "default_synth_env"
    description: str = "A mock environment for synthetic generation."

    # Graph structure
    hosts: dict[str, HostNode] = field(default_factory=dict)
    files: dict[str, FileNode] = field(default_factory=dict)
    users: dict[str, str] = field(default_factory=dict)

    # Mocking behaviors
    tool_responses: dict[str, dict[str, str]] = field(default_factory=dict)
    ground_truth_flag: str = "FLAG{synth_generated_flag}"

    # Advanced 2026 World State Dynamics (Spatial/Topology/Faults)
    enforce_topology: bool = False
    namespaces: list[dict[str, Any]] = field(default_factory=list)
    synthetic_faults: dict[str, Any] = field(default_factory=dict)

    # Environment state
    context_depth: str = "high"
    env_vars: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> "WorldManifest":
        with open(path) as f:
            data = yaml.safe_load(f)

        manifest = cls(
            name=data.get("name", "Unnamed"),
            description=data.get("description", ""),
            ground_truth_flag=data.get("ground_truth_flag", ""),
            enforce_topology=data.get("world_state_dynamics", {}).get(
                "enforce_topology", False
            ),
            namespaces=data.get("world_state_dynamics", {}).get("namespaces", []),
            synthetic_faults=data.get("world_state_dynamics", {}).get(
                "synthetic_faults", {}
            ),
        )

        # Hydrate hosts
        for h_data in data.get("hosts", []):
            services = [Service(**s) for s in h_data.get("services", [])]
            host = HostNode(
                ip=h_data.get("ip", ""),
                hostname=h_data.get("hostname", ""),
                os_type=h_data.get("os_type", "linux"),
                services=services,
            )
            manifest.hosts[host.hostname] = host
            manifest.hosts[host.ip] = host

        # Hydrate files
        for f_data in data.get("files", []):
            fnode = FileNode(**f_data)
            # Normalize path
            manifest.files[os.path.normpath(fnode.path)] = fnode

        # Hydrate tool responses (fuzzy regex or exact match mapped to string output)
        manifest.tool_responses = data.get("tool_responses", {})

        return manifest

    def clone(self) -> "WorldManifest":
        """Returns a deep copy of the manifest for safe isolated execution with scalable randomness."""
        import uuid

        cloned = deepcopy(self)

        # Ensure all data is incredibly unique to avoid identical trace memorization in LLMs
        old_flag = cloned.ground_truth_flag
        # Retain the same format FLAG{...} but randomize the interior
        if "FLAG{" in old_flag:
            new_inner = str(uuid.uuid4()).replace("-", "")[:16]
            cloned.ground_truth_flag = f"FLAG{{{new_inner}}}"

            # Sub into files
            for _file_path, file_node in cloned.files.items():
                if file_node.content and old_flag in file_node.content:
                    file_node.content = file_node.content.replace(
                        old_flag, cloned.ground_truth_flag
                    )

            # Sub into tool responses
            for tool_name, responses in cloned.tool_responses.items():
                for cmd, output in responses.items():
                    if output and old_flag in output:
                        cloned.tool_responses[tool_name][cmd] = output.replace(
                            old_flag, cloned.ground_truth_flag
                        )

        return cloned
