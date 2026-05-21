"""Tests for SDL structural models (Pydantic validation)."""

import pytest
from pydantic import ValidationError

from aces.core.sdl._source import Source
from aces.core.sdl.conditions import Condition
from aces.core.sdl.entities import Entity, ExerciseRole, flatten_entities
from aces.core.sdl.features import Feature, FeatureType
from aces.core.sdl.infrastructure import ACLAction, ACLRule, InfraNode, SimpleProperties
from aces.core.sdl.nodes import (
    ContainerImageBuildProvenance,
    DockerfileInstruction,
    DockerfileInstructionKind,
    ImageAttestation,
    ImageAttestationStatus,
    ImageAttestationType,
    ImageBuildArg,
    ImageConfig,
    ImageCopiedSource,
    ImageEnvironmentDefault,
    ImageLayer,
    ImageSourceInput,
    ImageVerificationStatus,
    Node,
    NodeType,
    Resources,
    Role,
    RuntimeControlInterface,
    RuntimeControlInterfaceAccess,
    RuntimeControlInterfaceKind,
    RuntimeEnvironmentValueClassification,
    RuntimeEnvironmentVariableProvenance,
    RuntimeFilesystemEntryType,
    RuntimeFilesystemStability,
    RuntimeHealthStatus,
    RuntimeIdentityProvenance,
    RuntimeLocalGroup,
    RuntimeLocalIdentityInventory,
    RuntimeLocalUser,
    RuntimeMountPropagation,
    RuntimeMountSourceKind,
    RuntimeNetworkBackendDetail,
    RuntimeNetworkDriver,
    RuntimeNetworkEndpoint,
    RuntimeNetworkIdStability,
    RuntimeNetworkRealization,
    RuntimePackageVulnerabilitySeverity,
    RuntimeProcessRole,
    RuntimePublishedPort,
    RuntimeRestartPolicy,
    RuntimeSensitivityClassification,
    RuntimeSudoPrincipalKind,
    RuntimeSudoRule,
    parse_ram,
)
from aces.core.sdl.objectives import Objective, ObjectiveSuccess, ObjectiveWindow
from aces.core.sdl.orchestration import (
    Inject,
    Script,
    Story,
    Workflow,
    WorkflowPredicate,
    WorkflowStep,
    WorkflowStepOutcome,
    WorkflowStepType,
    parse_duration,
)
from aces.core.sdl.scoring import TLO, Evaluation, Goal, Metric, MetricType, MinScore
from aces.core.sdl.vulnerabilities import Vulnerability

# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------


class TestSource:
    def test_basic(self):
        s = Source(name="pkg", version="1.0")
        assert s.name == "pkg"
        assert s.version == "1.0"

    def test_default_version(self):
        s = Source(name="pkg")
        assert s.version == "*"

    def test_build_defaults_to_none(self):
        s = Source(name="pkg")
        assert s.build is None


class TestContainerImageBuildProvenance:
    """Tests for the SDL container image build/provenance surface (issue #364)."""

    def _full_build(self) -> dict:
        return {
            "base_image": "python:3.12-slim",
            "base_image_digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
            "dockerfile_path": "containers/webapp/Dockerfile",
            "instructions": [
                {"instruction": "from", "arguments": ["python:3.12-slim"]},
                {"instruction": "arg", "arguments": ["APP_VERSION"]},
                {"instruction": "copy", "arguments": ["webapp/app.py", "/app/app.py"]},
                {"instruction": "entrypoint", "arguments": ["/entrypoint.sh"]},
            ],
            "layers": [
                {
                    "digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
                    "created_by": "FROM python:3.12-slim",
                    "size": "31000000",
                },
                {"created_by": "ENV APP_HOME=/app", "empty": "true"},
            ],
            "build_args": [
                {"name": "APP_VERSION", "value": "1.4.2", "value_classification": "plain"},
                {"name": "PIP_INDEX_TOKEN", "value_classification": "redacted"},
            ],
            "copied_sources": [
                {"source_path": "webapp/app.py", "destination_path": "/app/app.py"},
                {
                    "source_path": "containers/webapp/entrypoint.sh",
                    "destination_path": "/entrypoint.sh",
                    "from_stage": "builder",
                },
            ],
            "config": {
                "entrypoint": "/entrypoint.sh",
                "command": ["gunicorn", "app:app"],
                "working_directory": "/app",
                "exposed_ports": ["8080/tcp"],
                "labels": {"org.opencontainers.image.source": "https://example.test/techvault"},
                "default_environment": [
                    {"name": "APP_HOME", "value": "/app", "value_classification": "plain"},
                ],
            },
            "source_inputs": [
                {
                    "identifier": "webapp-app",
                    "source_path": "webapp/app.py",
                    "destination_path": "/app/app.py",
                    "checksum": "4f8c2d",
                    "checksum_algorithm": "sha256",
                },
            ],
            "attestation": {
                "status": "absent",
                "verification": "unverified",
                "attestation_type": "none",
            },
        }

    def test_source_carries_full_build_provenance(self):
        s = Source(name="techvault-webapp", version="local", build=self._full_build())

        assert s.build is not None
        build = s.build
        assert build.base_image == "python:3.12-slim"
        assert build.dockerfile_path == "containers/webapp/Dockerfile"
        assert build.instructions[0].instruction == DockerfileInstructionKind.FROM
        assert build.instructions[2].arguments == ["webapp/app.py", "/app/app.py"]
        assert build.layers[0].size == 31000000
        assert build.layers[1].empty is True
        assert build.layers[1].digest == ""
        assert build.build_args[0].value == "1.4.2"
        assert build.copied_sources[1].from_stage == "builder"
        assert build.config is not None
        assert build.config.entrypoint == ["/entrypoint.sh"]
        assert build.config.working_directory == "/app"
        assert build.config.labels["org.opencontainers.image.source"] == "https://example.test/techvault"
        assert build.source_inputs[0].checksum_algorithm == "sha256"
        assert build.attestation is not None
        assert build.attestation.status == ImageAttestationStatus.ABSENT
        assert build.attestation.verification == ImageVerificationStatus.UNVERIFIED
        assert build.attestation.attestation_type == ImageAttestationType.NONE

    def test_instruction_kind_normalizes_case_and_hyphen(self):
        instruction = DockerfileInstruction(instruction="HEALTHCHECK", arguments="curl localhost")
        assert instruction.instruction == DockerfileInstructionKind.HEALTHCHECK
        assert instruction.arguments == ["curl localhost"]

    def test_instruction_rejects_unknown_kind(self):
        with pytest.raises(ValidationError, match="instruction must be one of"):
            DockerfileInstruction(instruction="not-a-real-instruction")

    def test_build_arg_redacted_value_must_be_omitted(self):
        with pytest.raises(ValidationError, match="redacted build arguments must omit value"):
            ImageBuildArg(name="SECRET", value="leaked", value_classification="redacted")

    def test_build_arg_rejects_name_with_equals(self):
        with pytest.raises(ValidationError, match="must not contain '='"):
            ImageBuildArg(name="A=B")

    def test_image_environment_default_redacted_value_must_be_omitted(self):
        with pytest.raises(ValidationError, match="redacted image environment variables must omit value"):
            ImageEnvironmentDefault(name="TOKEN", value="leaked", value_classification="redacted")

    def test_copied_source_destination_must_be_absolute(self):
        with pytest.raises(ValidationError, match="destination_path must be an absolute path"):
            ImageCopiedSource(source_path="webapp/app.py", destination_path="app/app.py")

    def test_copied_source_rejects_empty_source_path(self):
        with pytest.raises(ValidationError, match="source_path must be a non-empty string"):
            ImageCopiedSource(source_path="  ", destination_path="/app/app.py")

    def test_image_config_working_directory_must_be_absolute(self):
        with pytest.raises(ValidationError, match="working_directory must be an absolute path"):
            ImageConfig(working_directory="app")

    def test_image_config_rejects_duplicate_default_environment(self):
        with pytest.raises(ValidationError, match="Duplicate image environment variable 'APP_HOME'"):
            ImageConfig(
                default_environment=[
                    {"name": "APP_HOME", "value": "/app"},
                    {"name": "APP_HOME", "value": "/srv"},
                ],
            )

    def test_source_input_checksum_requires_algorithm(self):
        with pytest.raises(ValidationError, match="checksum requires checksum_algorithm"):
            ImageSourceInput(identifier="webapp-app", checksum="4f8c2d")

    def test_source_input_algorithm_requires_checksum(self):
        with pytest.raises(ValidationError, match="checksum_algorithm requires checksum"):
            ImageSourceInput(identifier="webapp-app", checksum_algorithm="sha256")

    def test_source_input_destination_must_be_absolute(self):
        with pytest.raises(ValidationError, match="destination_path must be an absolute path"):
            ImageSourceInput(identifier="webapp-app", destination_path="app/app.py")

    def test_attestation_absent_cannot_be_verified(self):
        with pytest.raises(ValidationError, match="absent attestation cannot have a verified"):
            ImageAttestation(status="absent", verification="verified")

    def test_attestation_absent_unverified_is_distinct_from_failed(self):
        absent = ImageAttestation(status="absent", verification="unverified")
        failed = ImageAttestation(status="present", verification="failed")
        assert absent.status == ImageAttestationStatus.ABSENT
        assert absent.verification == ImageVerificationStatus.UNVERIFIED
        assert failed.verification == ImageVerificationStatus.FAILED

    def test_build_rejects_duplicate_build_arg(self):
        with pytest.raises(ValidationError, match="Duplicate build argument 'APP_VERSION'"):
            ContainerImageBuildProvenance(
                build_args=[{"name": "APP_VERSION"}, {"name": "APP_VERSION"}],
            )

    def test_build_rejects_duplicate_source_input_identifier(self):
        with pytest.raises(ValidationError, match="Duplicate source input identifier 'webapp-app'"):
            ContainerImageBuildProvenance(
                source_inputs=[{"identifier": "webapp-app"}, {"identifier": "webapp-app"}],
            )

    def test_build_rejects_unknown_field(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ContainerImageBuildProvenance(not_a_field="x")

    def test_layer_supports_variable_placeholders(self):
        layer = ImageLayer(digest="${layer_digest}", size="${layer_size}")
        assert layer.digest == "${layer_digest}"
        assert layer.size == "${layer_size}"


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


class TestParseRam:
    def test_integer(self):
        assert parse_ram(4096) == 4096

    def test_gib_string(self):
        assert parse_ram("4 GiB") == 4 * 1073741824

    def test_mib_string(self):
        assert parse_ram("512 MiB") == 512 * 1048576

    def test_bare_digits(self):
        assert parse_ram("1024") == 1024

    def test_invalid_string(self):
        with pytest.raises(ValueError, match="Invalid RAM"):
            parse_ram("four gigabytes")

    @pytest.mark.parametrize("value", [0, -1, True])
    def test_rejects_non_positive_or_bool_values(self, value):
        with pytest.raises(ValueError, match="RAM"):
            parse_ram(value)


class TestResources:
    def test_human_readable_ram(self):
        r = Resources(ram="2 gib", cpu=2)
        assert r.ram == 2 * 1073741824

    def test_integer_ram(self):
        r = Resources(ram=1024, cpu=1)
        assert r.ram == 1024

    def test_variable_placeholders(self):
        r = Resources(ram="${ram_bytes}", cpu="${cpu_cores}")
        assert r.ram == "${ram_bytes}"
        assert r.cpu == "${cpu_cores}"

    def test_rejects_non_positive_ram(self):
        with pytest.raises(ValidationError, match="RAM"):
            Resources(ram=0, cpu=1)


class TestNode:
    def test_vm_node(self):
        n = Node(
            type="vm",
            source={"name": "ubuntu", "version": "22.04"},
            resources={"ram": "4 gib", "cpu": 2},
        )
        assert n.type == NodeType.VM

    def test_switch_node(self):
        n = Node(type="switch")
        assert n.type == NodeType.SWITCH

    def test_switch_rejects_source(self):
        with pytest.raises(ValidationError, match="Switch.*source"):
            Node(type="switch", source={"name": "pkg"})

    def test_switch_rejects_resources(self):
        with pytest.raises(ValidationError, match="Switch.*resources"):
            Node(type="switch", resources={"ram": "1 gib", "cpu": 1})

    @pytest.mark.parametrize(
        ("field_name", "value"),
        [
            ("os", "linux"),
            ("os_version", "22.04"),
            ("features", {"nginx": ""}),
            ("conditions", {"health-check": ""}),
            ("injects", {"email": ""}),
            ("vulnerabilities", ["sqli"]),
            ("roles", {"admin": {"username": "root"}}),
            ("services", [{"port": 80, "name": "http"}]),
            ("asset_value", {"confidentiality": "high"}),
            ("runtime", {"process": {"pid": 1, "command": "./shufflebackend"}}),
        ],
    )
    def test_switch_rejects_other_vm_only_fields(self, field_name, value):
        with pytest.raises(ValidationError, match=field_name):
            Node(type="switch", **{field_name: value})

    def test_vm_runtime_configuration_surfaces(self):
        n = Node(
            type="vm",
            runtime={
                "mounts": [
                    {
                        "target": "/shuffle-database",
                        "source": "aptl_shuffle_data",
                        "source_kind": "volume",
                    }
                ],
                "local_control_interfaces": [
                    {
                        "path": "/run/docker.sock",
                        "kind": "unix_socket",
                        "protocol": "docker",
                        "bind_source": "/var/run/docker.sock:/var/run/docker.sock:rw",
                        "access": "read_write",
                    }
                ],
                "process": {
                    "pid": 1,
                    "command": "./shufflebackend",
                    "user": "root",
                    "working_directory": "/app",
                },
                "packages": [
                    {
                        "manager": "apk",
                        "name": "musl",
                        "version": "1.2.4-r2",
                    }
                ],
                "dependency_manifests": [
                    {
                        "ecosystem": "go",
                        "path": "/app/go.mod",
                        "format": "go-module",
                    }
                ],
                "package_vulnerabilities": [
                    {
                        "id": "CVE-2026-12345",
                        "package_name": "musl",
                        "installed_version": "1.2.4-r2",
                        "fixed_version": "1.2.5-r0",
                        "severity": "high",
                        "scanner": "trivy",
                        "image_digest": "sha256:abc123",
                        "scan_time": "2026-05-20T12:00:00Z",
                    }
                ],
            },
        )

        runtime = n.runtime
        assert runtime is not None
        assert runtime.mounts[0].target == "/shuffle-database"
        assert runtime.mounts[0].source_kind == RuntimeMountSourceKind.VOLUME
        assert runtime.local_control_interfaces[0].kind == RuntimeControlInterfaceKind.UNIX_SOCKET
        assert runtime.local_control_interfaces[0].bind_source == "/var/run/docker.sock:/var/run/docker.sock:rw"
        assert runtime.local_control_interfaces[0].access == RuntimeControlInterfaceAccess.READ_WRITE
        assert runtime.process is not None
        assert runtime.process.pid == 1
        assert runtime.process.command == ["./shufflebackend"]
        assert runtime.process.user == "root"
        assert runtime.process.working_directory == "/app"
        assert runtime.packages[0].manager == "apk"
        assert runtime.packages[0].name == "musl"
        assert runtime.packages[0].version == "1.2.4-r2"
        assert runtime.dependency_manifests[0].ecosystem == "go"
        assert runtime.dependency_manifests[0].path == "/app/go.mod"
        assert runtime.dependency_manifests[0].format == "go-module"
        assert runtime.package_vulnerabilities[0].id == "CVE-2026-12345"
        assert runtime.package_vulnerabilities[0].package_name == "musl"
        assert runtime.package_vulnerabilities[0].installed_version == "1.2.4-r2"
        assert runtime.package_vulnerabilities[0].fixed_version == "1.2.5-r0"
        assert runtime.package_vulnerabilities[0].severity == RuntimePackageVulnerabilitySeverity.HIGH
        assert runtime.package_vulnerabilities[0].scanner == "trivy"
        assert runtime.package_vulnerabilities[0].image_digest == "sha256:abc123"
        assert runtime.package_vulnerabilities[0].scan_time == "2026-05-20T12:00:00Z"

    def test_vm_runtime_operational_surfaces(self):
        n = Node(
            type="vm",
            runtime={
                "processes": [
                    {
                        "name": "supervisord",
                        "pid": 1,
                        "command": "supervisord -n",
                        "role": "supervisor",
                    },
                    {
                        "name": "gunicorn",
                        "pid": 42,
                        "parent_pid": 1,
                        "command": ["gunicorn", "app:app"],
                        "role": "worker",
                    },
                    {
                        "name": "wazuh-agentd",
                        "parent_pid": 1,
                        "command_redacted": True,
                        "role": "agent",
                    },
                ],
                "environment": [
                    {
                        "name": "DJANGO_SETTINGS_MODULE",
                        "value": "techvault.settings",
                        "value_classification": "plain",
                        "provenance": "compose",
                    },
                    {
                        "name": "TECHVAULT_ADMIN_PASSWORD",
                        "value_classification": "redacted",
                        "provenance": "operator",
                    },
                    {
                        "name": "SCENARIO_FIXTURE_TOKEN",
                        "value": "fixture-token",
                        "value_classification": "secret_fixture",
                        "provenance": "compose",
                    },
                ],
                "linux_capabilities": {
                    "required": ["CAP_NET_ADMIN"],
                    "effective": "CAP_NET_ADMIN",
                },
                "operational_policy": {
                    "restart": "unless-stopped",
                    "resource_limits": {
                        "memory": "512 MiB",
                        "cpu": "0.5",
                        "pids": "128",
                    },
                },
            },
        )

        runtime = n.runtime
        assert runtime is not None
        assert runtime.processes[0].role == RuntimeProcessRole.SUPERVISOR
        assert runtime.processes[1].parent_pid == 1
        assert runtime.processes[1].command == ["gunicorn", "app:app"]
        assert runtime.processes[2].command_redacted is True
        assert runtime.environment[1].value == ""
        assert runtime.environment[1].value_classification == RuntimeEnvironmentValueClassification.REDACTED
        assert runtime.environment[1].provenance == RuntimeEnvironmentVariableProvenance.OPERATOR
        assert runtime.environment[2].value_classification == RuntimeEnvironmentValueClassification.SECRET_FIXTURE
        assert runtime.linux_capabilities is not None
        assert runtime.linux_capabilities.required == ["CAP_NET_ADMIN"]
        assert runtime.linux_capabilities.effective == ["CAP_NET_ADMIN"]
        assert runtime.operational_policy is not None
        assert runtime.operational_policy.restart == RuntimeRestartPolicy.UNLESS_STOPPED
        assert runtime.operational_policy.resource_limits is not None
        assert runtime.operational_policy.resource_limits.memory == 512 * 1048576
        assert runtime.operational_policy.resource_limits.cpu == 0.5
        assert runtime.operational_policy.resource_limits.pids == 128

    def test_vm_runtime_filesystem_inventory_surfaces(self):
        n = Node(
            type="vm",
            runtime={
                "filesystem_inventory": [
                    {
                        "path": "/app/app.py",
                        "entry_type": "file",
                        "owner_user": "root",
                        "owner_group": "root",
                        "uid": "0",
                        "gid": 0,
                        "mode": 0o644,
                        "size": "4096",
                        "content_digest": "4f8c2d",
                        "digest_algorithm": "sha256",
                        "source_path": "src/webapp/app.py",
                        "provenance": "python-package",
                        "stability": "stable",
                        "sensitivity": "plain",
                    },
                    {
                        "path": "/var/log/gunicorn/access.log",
                        "entry_type": "file",
                        "mode": "0600",
                        "stability": "log",
                        "sensitivity": "operator-secret",
                    },
                    {
                        "path": "/run/secrets/fixture-token",
                        "entry_type": "file",
                        "stability": "runtime-created",
                        "sensitivity": "secret-fixture",
                    },
                ],
            },
        )

        runtime = n.runtime
        assert runtime is not None
        assert runtime.filesystem_inventory[0].path == "/app/app.py"
        assert runtime.filesystem_inventory[0].entry_type == RuntimeFilesystemEntryType.FILE
        assert runtime.filesystem_inventory[0].uid == 0
        assert runtime.filesystem_inventory[0].gid == 0
        assert runtime.filesystem_inventory[0].mode == "0644"
        assert runtime.filesystem_inventory[0].size == 4096
        assert runtime.filesystem_inventory[0].digest_algorithm == "sha256"
        assert runtime.filesystem_inventory[0].content_digest == "4f8c2d"
        assert runtime.filesystem_inventory[0].source_path == "src/webapp/app.py"
        assert runtime.filesystem_inventory[0].stability == RuntimeFilesystemStability.STABLE
        assert runtime.filesystem_inventory[0].sensitivity == RuntimeSensitivityClassification.PLAIN
        assert runtime.filesystem_inventory[1].stability == RuntimeFilesystemStability.LOG
        assert runtime.filesystem_inventory[1].sensitivity == RuntimeSensitivityClassification.OPERATOR_SECRET
        assert runtime.filesystem_inventory[2].stability == RuntimeFilesystemStability.RUNTIME_CREATED
        assert runtime.filesystem_inventory[2].sensitivity == RuntimeSensitivityClassification.SECRET_FIXTURE

    def test_vm_runtime_container_host_config_surfaces(self):
        n = Node(
            type="vm",
            runtime={
                "mounts": [
                    {
                        "target": "/var/log/gunicorn",
                        "source": "techvault_gunicorn_logs",
                        "source_kind": "volume",
                        "filesystem_type": "ext4",
                        "read_only": False,
                        "options": ["rw", "nosuid"],
                        "propagation": "rprivate",
                        "stability": "volume-backed",
                        "backend_generated": True,
                    }
                ],
                "container": {
                    "entrypoint": ["/entrypoint.sh"],
                    "command": ["gunicorn", "app:app"],
                    "log_driver": "json-file",
                    "log_options": {"max-size": "10m", "max-file": "3"},
                    "namespaces": {
                        "cgroup": "private",
                        "ipc": "private",
                        "pid": "private",
                        "userns": "host",
                        "uts": "private",
                    },
                    "privileged": False,
                    "read_only_rootfs": False,
                    "publish_all_ports": False,
                    "autoremove": False,
                    "shm_size": "64 MiB",
                    "masked_paths": ["/proc/acpi", "/proc/kcore"],
                    "read_only_paths": "/proc/sys",
                    "cgroup_parent": "/docker",
                    "runtime_name": "runc",
                    "devices": [
                        {
                            "host_path": "/dev/null",
                            "container_path": "/dev/null",
                            "permissions": "rwm",
                        }
                    ],
                    "device_cgroup_rules": "c 1:3 rwm",
                    "extra_hosts": [{"hostname": "wazuh-manager", "address": "172.20.0.10"}],
                    "dns": ["8.8.8.8"],
                    "dns_options": "ndots:0",
                    "dns_search": ["techvault.local"],
                    "group_add": ["adm", "101"],
                },
                "health": {
                    "status": "healthy",
                    "failing_streak": "0",
                    "log": [
                        {
                            "start": "2026-05-20T12:00:00Z",
                            "end": "2026-05-20T12:00:01Z",
                            "exit_code": "0",
                            "output": "ok",
                        },
                        {
                            "start": "2026-05-20T12:01:00Z",
                            "end": "2026-05-20T12:01:01Z",
                            "exit_code": 1,
                            "output_redacted": True,
                        },
                    ],
                },
            },
        )

        runtime = n.runtime
        assert runtime is not None
        assert runtime.mounts[0].filesystem_type == "ext4"
        assert runtime.mounts[0].propagation == RuntimeMountPropagation.RPRIVATE
        assert runtime.mounts[0].stability == RuntimeFilesystemStability.VOLUME_BACKED
        assert runtime.mounts[0].backend_generated is True
        assert runtime.container is not None
        assert runtime.container.entrypoint == ["/entrypoint.sh"]
        assert runtime.container.command == ["gunicorn", "app:app"]
        assert runtime.container.log_driver == "json-file"
        assert runtime.container.namespaces is not None
        assert runtime.container.namespaces.userns == "host"
        assert runtime.container.privileged is False
        assert runtime.container.shm_size == 64 * 1048576
        assert runtime.container.read_only_paths == ["/proc/sys"]
        assert runtime.container.devices[0].host_path == "/dev/null"
        assert runtime.container.device_cgroup_rules == ["c 1:3 rwm"]
        assert runtime.container.extra_hosts[0].hostname == "wazuh-manager"
        assert runtime.container.dns_options == ["ndots:0"]
        assert runtime.container.group_add == ["adm", "101"]
        assert runtime.health is not None
        assert runtime.health.status == RuntimeHealthStatus.HEALTHY
        assert runtime.health.failing_streak == 0
        assert runtime.health.log[0].exit_code == 0
        assert runtime.health.log[1].output_redacted is True

    @pytest.mark.parametrize(
        ("runtime", "message"),
        [
            ({"mounts": [{"target": "shuffle-database", "source": "data"}]}, "target"),
            ({"mounts": [{"target": "/data", "backend_generated": "sometimes"}]}, "backend_generated"),
            ({"mounts": [{"target": "/data"}, {"target": "/data"}]}, "Duplicate runtime mount target"),
            ({"filesystem_inventory": [{"path": "app/app.py"}]}, "path"),
            (
                {"filesystem_inventory": [{"path": "/app/app.py", "content_digest": "abc"}]},
                "content_digest requires digest_algorithm",
            ),
            (
                {"filesystem_inventory": [{"path": "/app/app.py", "digest_algorithm": "sha256"}]},
                "digest_algorithm requires content_digest",
            ),
            ({"filesystem_inventory": [{"path": "/app/app.py", "mode": "888"}]}, "mode"),
            (
                {"filesystem_inventory": [{"path": "/app/app.py"}, {"path": "/app/app.py"}]},
                "Duplicate runtime filesystem path",
            ),
            ({"local_control_interfaces": [{"path": "run/docker.sock"}]}, "path"),
            ({"process": {"pid": 0, "command": "./shufflebackend"}}, "pid"),
            ({"process": {"working_directory": "app"}}, "working_directory"),
            ({"dependency_manifests": [{"ecosystem": "go", "path": "go.mod"}]}, "path"),
            ({"container": {"masked_paths": ["proc/acpi"]}}, "masked_paths"),
            ({"container": {"devices": [{"host_path": "dev/null", "container_path": "/dev/null"}]}}, "host_path"),
            (
                {
                    "container": {
                        "devices": [
                            {"host_path": "/dev/null", "container_path": "/dev/null"},
                            {"host_path": "/dev/null", "container_path": "/dev/null"},
                        ]
                    }
                },
                "Duplicate runtime device mapping",
            ),
            (
                {
                    "container": {
                        "extra_hosts": [
                            {"hostname": "wazuh-manager", "address": "172.20.0.10"},
                            {"hostname": "wazuh-manager", "address": "172.20.0.11"},
                        ]
                    }
                },
                "Duplicate runtime extra host",
            ),
            ({"health": {"log": [{"output": "secret", "output_redacted": True}]}}, "redacted healthcheck output"),
            (
                {
                    "environment": [
                        {"name": "TECHVAULT_ADMIN_PASSWORD", "value_classification": "redacted"},
                        {"name": "TECHVAULT_ADMIN_PASSWORD", "value_classification": "redacted"},
                    ]
                },
                "Duplicate runtime environment variable",
            ),
            ({"environment": [{"name": "BAD=NAME"}]}, "environment variable name"),
            (
                {"processes": [{"name": "gunicorn"}, {"name": "gunicorn"}]},
                "Duplicate runtime process name",
            ),
            ({"linux_capabilities": {"required": [""]}}, "capability"),
            ({"operational_policy": {"resource_limits": {"pids": 0}}}, "pids"),
            (
                {"local_identity": {"users": [{"username": "root"}, {"username": "root"}]}},
                "Duplicate runtime local user",
            ),
            (
                {"local_identity": {"groups": [{"name": "wheel"}, {"name": "wheel"}]}},
                "Duplicate runtime local group",
            ),
            (
                {"local_identity": {"groups": [{"name": "a", "gid": 10}, {"name": "b", "gid": 10}]}},
                "Duplicate runtime local group gid",
            ),
            (
                {
                    "local_identity": {
                        "sudo_rules": [
                            {"principal": "ops", "commands": ["/usr/bin/systemctl"]},
                            {"principal": "ops", "commands": ["/usr/bin/systemctl"]},
                        ]
                    }
                },
                "Duplicate runtime sudo rule",
            ),
            ({"local_identity": {"users": [{"username": "  "}]}}, "username"),
            ({"local_identity": {"users": [{"username": "svc", "home": "var/svc"}]}}, "home"),
            ({"local_identity": {"users": [{"username": "svc", "uid": -1}]}}, "uid"),
            ({"local_identity": {"groups": [{"name": ""}]}}, "group name"),
            (
                {
                    "local_identity": {
                        "sudo_rules": [{"principal": "ops", "command_redacted": True, "commands": ["/bin/sh"]}]
                    }
                },
                "redacted sudo rules must omit commands",
            ),
        ],
    )
    def test_runtime_configuration_rejects_invalid_runtime_anchors(self, runtime, message):
        with pytest.raises(ValidationError, match=message):
            Node(type="vm", runtime=runtime)

    def test_runtime_control_interface_accepts_windows_named_pipe_path(self):
        interface = RuntimeControlInterface(
            path=r"\\.\pipe\docker_engine",
            kind="named-pipe",
            bind_source=r"\\.\pipe\docker_engine",
        )

        assert interface.path == r"\\.\pipe\docker_engine"
        assert interface.kind == RuntimeControlInterfaceKind.NAMED_PIPE
        assert interface.bind_source == r"\\.\pipe\docker_engine"

    def test_runtime_control_interface_named_pipe_path_requires_named_pipe_kind(self):
        with pytest.raises(ValidationError, match="named_pipe"):
            RuntimeControlInterface(path=r"\\.\pipe\docker_engine", kind="unix-socket")

    def test_vm_runtime_local_identity_inventory_surfaces(self):
        n = Node(
            type="vm",
            runtime={
                "local_identity": {
                    "description": "getent passwd/group capture",
                    "users": [
                        {
                            "username": "root",
                            "uid": 0,
                            "primary_gid": 0,
                            "primary_group": "root",
                            "gecos": "root",
                            "home": "/root",
                            "shell": "/bin/bash",
                            "provenance": "image",
                            "stability": "stable",
                        },
                        {
                            "username": "www-data",
                            "uid": "33",
                            "primary_gid": 33,
                            "primary_group": "www-data",
                            "home": "/var/www",
                            "shell": "/usr/sbin/nologin",
                            "supplemental_groups": ["wazuh"],
                            "no_login": True,
                            "provenance": "package",
                        },
                        {
                            "username": "operator",
                            "uid": 1000,
                            "home": "/home/operator",
                            "shell": "/bin/bash",
                            "disabled": True,
                            "locked": True,
                            "provenance": "runtime-created",
                            "stability": "runtime_created",
                        },
                    ],
                    "groups": [
                        {"name": "root", "gid": 0, "members": ["root"], "provenance": "image"},
                        {"name": "www-data", "gid": 33, "members": ["www-data"]},
                        {"name": "wazuh", "gid": "101", "members": ["www-data", "operator"]},
                    ],
                    "sudo_rules": [
                        {
                            "principal": "operator",
                            "principal_kind": "user",
                            "run_as_users": ["root"],
                            "commands": ["/usr/bin/systemctl restart gunicorn"],
                            "nopasswd": True,
                        },
                        {
                            "principal": "wheel",
                            "principal_kind": "group",
                            "host_scope": "ALL",
                            "commands": ["ALL"],
                        },
                    ],
                },
            },
        )

        identity = n.runtime.local_identity
        assert identity is not None
        assert identity.description == "getent passwd/group capture"
        assert identity.users[0].username == "root"
        assert identity.users[0].uid == 0
        assert identity.users[0].primary_gid == 0
        assert identity.users[0].primary_group == "root"
        assert identity.users[0].gecos == "root"
        assert identity.users[0].home == "/root"
        assert identity.users[0].shell == "/bin/bash"
        assert identity.users[0].provenance == RuntimeIdentityProvenance.IMAGE
        assert identity.users[0].stability == RuntimeFilesystemStability.STABLE
        assert identity.users[1].uid == 33
        assert identity.users[1].supplemental_groups == ["wazuh"]
        assert identity.users[1].no_login is True
        assert identity.users[1].disabled is False
        assert identity.users[1].locked is False
        assert identity.users[1].provenance == RuntimeIdentityProvenance.PACKAGE
        assert identity.users[2].disabled is True
        assert identity.users[2].locked is True
        assert identity.users[2].no_login is False
        assert identity.users[2].provenance == RuntimeIdentityProvenance.RUNTIME_CREATED
        assert identity.groups[0].name == "root"
        assert identity.groups[0].gid == 0
        assert identity.groups[0].members == ["root"]
        assert identity.groups[2].gid == 101
        assert identity.groups[2].members == ["www-data", "operator"]
        assert identity.sudo_rules[0].principal == "operator"
        assert identity.sudo_rules[0].principal_kind == RuntimeSudoPrincipalKind.USER
        assert identity.sudo_rules[0].run_as_users == ["root"]
        assert identity.sudo_rules[0].commands == ["/usr/bin/systemctl restart gunicorn"]
        assert identity.sudo_rules[0].nopasswd is True
        assert identity.sudo_rules[1].principal_kind == RuntimeSudoPrincipalKind.GROUP
        assert identity.sudo_rules[1].host_scope == "ALL"

    def test_runtime_local_user_status_flags_are_independent(self):
        user = RuntimeLocalUser.model_validate({"username": "svc", "shell": "/usr/sbin/nologin", "no_login": True})
        assert user.no_login is True
        assert user.locked is False
        assert user.disabled is False

    def test_runtime_local_group_defaults(self):
        group = RuntimeLocalGroup(name="messagebus")
        assert group.gid is None
        assert group.members == []
        assert group.provenance == RuntimeIdentityProvenance.UNKNOWN

    def test_runtime_local_identity_inventory_is_optional(self):
        assert RuntimeLocalIdentityInventory().users == []
        assert Node(type="vm", runtime={}).runtime.local_identity is None

    def test_runtime_sudo_rule_redacted_commands_must_be_omitted(self):
        with pytest.raises(ValidationError, match="redacted sudo rules must omit commands"):
            RuntimeSudoRule(principal="ops", command_redacted=True, commands=["/bin/sh -c secret"])

    def test_runtime_sudo_rule_redacted_without_commands_is_valid(self):
        rule = RuntimeSudoRule(principal="ops", command_redacted=True)
        assert rule.command_redacted is True
        assert rule.commands == []


# ---------------------------------------------------------------------------
# Runtime network realization (ADR-025)
# ---------------------------------------------------------------------------


class TestRuntimeNetworkRealization:
    def test_vm_runtime_network_surface(self):
        n = Node(
            type="vm",
            runtime={
                "network": {
                    "description": "Docker network realization observed by harness inspection.",
                    "hostname": "techvault-webapp",
                    "domainname": "techvault.local",
                    "endpoints": [
                        {
                            "network": "aptl-dmz",
                            "network_id": "net-a1b2c3d4e5f6",
                            "network_id_stability": "stable",
                            "endpoint_id": "ep-1a2b3c4d5e6f",
                            "endpoint_id_stability": "ephemeral",
                            "backend_generated": True,
                            "ip_address": "172.20.0.20",
                            "ip_prefix_length": 24,
                            "gateway": "172.20.0.1",
                            "mac_address": "02:42:ac:14:00:14",
                            "aliases": ["aptl-webapp", "webapp"],
                            "dns_names": ["aptl-webapp", "webapp"],
                            "generated_dns_names": ["a1b2c3d4e5f6"],
                            "backend": {
                                "driver": "bridge",
                                "ipam_driver": "default",
                                "driver_options": {"com.docker.network.bridge.name": "br-dmz"},
                                "ipam_options": {"foo": "bar"},
                            },
                        },
                        {
                            "network": "aptl-internal",
                            "ip_address": "172.21.0.20",
                        },
                    ],
                    "published_ports": [
                        {
                            "container_port": 8080,
                            "protocol": "tcp",
                            "host_ip": "127.0.0.1",
                            "host_port": 8080,
                        }
                    ],
                },
            },
        )

        net = n.runtime.network
        assert net is not None
        assert net.hostname == "techvault-webapp"
        assert net.domainname == "techvault.local"
        ep = net.endpoints[0]
        assert ep.network == "aptl-dmz"
        assert ep.network_id == "net-a1b2c3d4e5f6"
        assert ep.network_id_stability == RuntimeNetworkIdStability.STABLE
        assert ep.endpoint_id_stability == RuntimeNetworkIdStability.EPHEMERAL
        assert ep.backend_generated is True
        assert ep.ip_address == "172.20.0.20"
        assert ep.ip_prefix_length == 24
        assert ep.gateway == "172.20.0.1"
        assert ep.mac_address == "02:42:ac:14:00:14"
        assert ep.aliases == ["aptl-webapp", "webapp"]
        assert ep.dns_names == ["aptl-webapp", "webapp"]
        assert ep.generated_dns_names == ["a1b2c3d4e5f6"]
        assert ep.backend.driver == RuntimeNetworkDriver.BRIDGE
        assert ep.backend.ipam_driver == "default"
        assert ep.backend.driver_options == {"com.docker.network.bridge.name": "br-dmz"}
        assert ep.backend.ipam_options == {"foo": "bar"}
        # Defaults on a sparsely-observed endpoint.
        assert net.endpoints[1].network_id == ""
        assert net.endpoints[1].network_id_stability == RuntimeNetworkIdStability.UNKNOWN
        assert net.endpoints[1].backend is None
        binding = net.published_ports[0]
        assert binding.container_port == 8080
        assert binding.host_ip == "127.0.0.1"
        assert binding.host_port == 8080
        assert binding.protocol == "tcp"

    def test_runtime_network_is_optional(self):
        assert RuntimeNetworkRealization().endpoints == []
        assert Node(type="vm", runtime={}).runtime.network is None

    def test_endpoint_accepts_variable_placeholders(self):
        ep = RuntimeNetworkEndpoint(
            network="aptl-dmz",
            ip_address="${WEBAPP_IP}",
            gateway="${DMZ_GATEWAY}",
            mac_address="${WEBAPP_MAC}",
            ip_prefix_length="${PREFIX}",
        )
        assert ep.ip_address == "${WEBAPP_IP}"
        assert ep.mac_address == "${WEBAPP_MAC}"
        assert ep.ip_prefix_length == "${PREFIX}"

    def test_published_port_protocol_normalized_and_required(self):
        binding = RuntimePublishedPort(container_port="443", protocol="TCP")
        assert binding.container_port == 443
        assert binding.protocol == "tcp"
        assert binding.host_port is None

    def test_published_port_rejects_out_of_range_ports(self):
        with pytest.raises(ValidationError, match="container_port must be <= 65535"):
            RuntimePublishedPort(container_port=70000)
        with pytest.raises(ValidationError, match="host_port must be >= 1"):
            RuntimePublishedPort(container_port=8080, host_port=0)

    def test_published_port_rejects_empty_protocol(self):
        with pytest.raises(ValidationError, match="protocol must be a non-empty string"):
            RuntimePublishedPort(container_port=8080, protocol="  ")

    def test_published_port_rejects_invalid_host_ip(self):
        with pytest.raises(ValidationError, match="host_ip must be a valid IP address"):
            RuntimePublishedPort(container_port=8080, host_ip="not-an-ip")

    def test_endpoint_rejects_invalid_ip_and_gateway(self):
        with pytest.raises(ValidationError, match="ip_address must be a valid IP address"):
            RuntimeNetworkEndpoint(network="aptl-dmz", ip_address="999.0.0.1")
        with pytest.raises(ValidationError, match="gateway must be a valid IP address"):
            RuntimeNetworkEndpoint(network="aptl-dmz", gateway="bad-gateway")

    def test_endpoint_rejects_invalid_mac_address(self):
        with pytest.raises(ValidationError, match="mac_address must be a colon-separated MAC address"):
            RuntimeNetworkEndpoint(network="aptl-dmz", mac_address="02-42-ac-14-00-14")

    def test_endpoint_rejects_out_of_range_prefix_length(self):
        with pytest.raises(ValidationError, match="ip_prefix_length must be <= 128"):
            RuntimeNetworkEndpoint(network="aptl-dmz", ip_prefix_length=129)

    def test_endpoint_rejects_empty_network(self):
        with pytest.raises(ValidationError, match="network must be a non-empty string"):
            RuntimeNetworkEndpoint(network="  ")

    def test_endpoint_rejects_duplicate_aliases(self):
        with pytest.raises(ValidationError, match="Duplicate runtime network aliases"):
            RuntimeNetworkEndpoint(network="aptl-dmz", aliases=["webapp", "webapp"])

    def test_endpoint_rejects_duplicate_dns_names(self):
        with pytest.raises(ValidationError, match="Duplicate runtime network dns_names"):
            RuntimeNetworkEndpoint(network="aptl-dmz", dns_names=["webapp", "webapp"])

    def test_realization_rejects_duplicate_endpoint_networks(self):
        with pytest.raises(ValidationError, match="Duplicate runtime network endpoint for network 'aptl-dmz'"):
            RuntimeNetworkRealization(
                endpoints=[{"network": "aptl-dmz"}, {"network": "aptl-dmz"}],
            )

    def test_realization_rejects_conflicting_host_bindings(self):
        with pytest.raises(ValidationError, match="Duplicate host-published binding"):
            RuntimeNetworkRealization(
                published_ports=[
                    {"container_port": 8080, "host_ip": "127.0.0.1", "host_port": 8080, "protocol": "tcp"},
                    {"container_port": 9090, "host_ip": "127.0.0.1", "host_port": 8080, "protocol": "tcp"},
                ],
            )

    def test_realization_allows_same_host_port_on_distinct_protocols(self):
        realization = RuntimeNetworkRealization(
            published_ports=[
                {"container_port": 53, "host_ip": "127.0.0.1", "host_port": 53, "protocol": "tcp"},
                {"container_port": 53, "host_ip": "127.0.0.1", "host_port": 53, "protocol": "udp"},
            ],
        )
        assert len(realization.published_ports) == 2

    def test_backend_detail_normalizes_driver_enum(self):
        detail = RuntimeNetworkBackendDetail(driver="OVERLAY")
        assert detail.driver == RuntimeNetworkDriver.OVERLAY

    def test_backend_detail_rejects_unknown_driver(self):
        with pytest.raises(ValidationError, match="driver must be one of"):
            RuntimeNetworkBackendDetail(driver="quantum-mesh")


class TestRole:
    def test_basic_role(self):
        r = Role(username="admin")
        assert r.entities == []

    def test_role_with_entities(self):
        r = Role(username="user", entities=["blue-team.bob"])
        assert len(r.entities) == 1


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------


class TestInfraNode:
    def test_defaults(self):
        n = InfraNode()
        assert n.count == 1
        assert n.links == []

    def test_with_count(self):
        n = InfraNode(count=3)
        assert n.count == 3

    def test_rejects_zero_count(self):
        with pytest.raises(ValidationError, match="count must be >= 1"):
            InfraNode(count=0)

    def test_duplicate_links_rejected(self):
        with pytest.raises(ValidationError, match="unique"):
            InfraNode(links=["a", "a"])

    def test_count_placeholder(self):
        n = InfraNode(count="${replicas}")
        assert n.count == "${replicas}"

    def test_duplicate_acl_names_rejected(self):
        with pytest.raises(ValidationError, match="ACL names must be unique"):
            InfraNode(
                acls=[
                    {"name": "allow-admin", "direction": "in", "from_net": "wan"},
                    {"name": "allow-admin", "direction": "out", "to_net": "wan"},
                ]
            )


class TestSimpleProperties:
    def test_valid(self):
        p = SimpleProperties(cidr="10.0.0.0/24", gateway="10.0.0.1")
        assert p.cidr == "10.0.0.0/24"

    def test_gateway_outside_cidr(self):
        with pytest.raises(ValidationError, match="not within CIDR"):
            SimpleProperties(cidr="10.0.0.0/24", gateway="192.168.1.1")

    def test_invalid_cidr(self):
        # Pinned to the field-level ``validate_cidr`` validator (the ipaddress
        # stdlib message), not the model-level ``gateway_within_cidr`` check,
        # which would also reject this CIDR. Keeps the test honest about which
        # validator is under exercise.
        with pytest.raises(ValidationError, match="does not appear to be an IPv4 or IPv6"):
            SimpleProperties(cidr="not-a-cidr", gateway="10.0.0.1")

    def test_variable_placeholders_skip_network_validation(self):
        p = SimpleProperties(
            cidr="${network_cidr}",
            gateway="${network_gateway}",
            internal="${is_internal}",
        )
        assert p.cidr == "${network_cidr}"
        assert p.gateway == "${network_gateway}"
        assert p.internal == "${is_internal}"


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------


class TestFeature:
    def test_service(self):
        f = Feature(type="service", source={"name": "apache"})
        assert f.type == FeatureType.SERVICE

    def test_with_dependencies(self):
        f = Feature(type="configuration", dependencies=["svc-a"])
        assert f.dependencies == ["svc-a"]


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------


class TestCondition:
    def test_command_based(self):
        c = Condition(command="/usr/bin/check.sh", interval=30)
        assert c.command == "/usr/bin/check.sh"

    def test_source_based(self):
        c = Condition(source={"name": "checker-pkg"})
        assert c.source.name == "checker-pkg"

    def test_rejects_both(self):
        with pytest.raises(ValidationError, match="both"):
            Condition(command="/bin/check", interval=10, source={"name": "pkg"})

    def test_rejects_neither(self):
        with pytest.raises(ValidationError, match="must have"):
            Condition()

    def test_command_without_interval(self):
        with pytest.raises(ValidationError, match="interval"):
            Condition(command="/bin/check")

    def test_scalar_placeholders(self):
        c = Condition(
            command="/usr/bin/check.sh",
            interval="${check_interval}",
            timeout="${check_timeout}",
            retries="${check_retries}",
            start_period="${check_start_period}",
        )
        assert c.interval == "${check_interval}"
        assert c.timeout == "${check_timeout}"
        assert c.retries == "${check_retries}"
        assert c.start_period == "${check_start_period}"


# ---------------------------------------------------------------------------
# Vulnerabilities
# ---------------------------------------------------------------------------


class TestVulnerability:
    def test_valid(self):
        v = Vulnerability(name="SQLi", description="SQL injection", **{"class": "CWE-89"})
        assert v.vuln_class == "CWE-89"

    def test_invalid_cwe(self):
        with pytest.raises(ValidationError, match="CWE"):
            Vulnerability(name="Test", description="Desc", **{"class": "INVALID"})


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestMetric:
    def test_manual(self):
        m = Metric(type="manual", max_score=10, artifact=True)
        assert m.type == MetricType.MANUAL

    def test_conditional(self):
        m = Metric(type="conditional", max_score=10, condition="cond-1")
        assert m.condition == "cond-1"

    def test_manual_rejects_condition(self):
        with pytest.raises(ValidationError, match="Manual.*condition"):
            Metric(type="manual", max_score=10, condition="cond-1")

    def test_conditional_requires_condition(self):
        with pytest.raises(ValidationError, match="requires.*condition"):
            Metric(type="conditional", max_score=10)

    def test_variable_placeholders(self):
        m = Metric(type="manual", max_score="${max_score}", artifact="${needs_upload}")
        assert m.max_score == "${max_score}"
        assert m.artifact == "${needs_upload}"


class TestMinScore:
    def test_percentage(self):
        ms = MinScore(percentage=75)
        assert ms.percentage == 75

    def test_absolute(self):
        ms = MinScore(absolute=50)
        assert ms.absolute == 50

    def test_rejects_both(self):
        with pytest.raises(ValidationError, match="both"):
            MinScore(absolute=50, percentage=75)

    def test_rejects_neither(self):
        with pytest.raises(ValidationError, match="either"):
            MinScore()

    def test_placeholder_percentage(self):
        ms = MinScore(percentage="${pass_percentage}")
        assert ms.percentage == "${pass_percentage}"


class TestEvaluation:
    def test_valid(self):
        e = Evaluation(metrics=["m-1"], min_score=MinScore(percentage=50))
        assert len(e.metrics) == 1

    def test_empty_metrics_rejected(self):
        with pytest.raises(ValidationError, match="at least 1 item"):
            Evaluation(metrics=[], min_score=MinScore(percentage=50))


class TestTLO:
    def test_valid(self):
        t = TLO(evaluation="eval-1")
        assert t.evaluation == "eval-1"


class TestGoal:
    def test_valid(self):
        g = Goal(tlos=["tlo-1"])
        assert len(g.tlos) == 1


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


class TestEntity:
    def test_basic(self):
        e = Entity(name="Team", role="blue")
        assert e.role == ExerciseRole.BLUE

    def test_role_placeholder(self):
        e = Entity(name="Team", role="${exercise_role}")
        assert e.role == "${exercise_role}"

    def test_facts_supported(self):
        e = Entity(name="Team", facts={"department": "SOC"})
        assert e.facts == {"department": "SOC"}

    def test_nested_entities(self):
        e = Entity(
            name="Team",
            entities={"bob": Entity(name="Bob")},
        )
        assert "bob" in e.entities

    def test_flatten(self):
        entities = {
            "blue": Entity(
                name="Blue",
                entities={"bob": Entity(name="Bob")},
            ),
        }
        flat = flatten_entities(entities)
        assert "blue" in flat
        assert "blue.bob" in flat


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


class TestParseDuration:
    def test_integer(self):
        assert parse_duration(60) == 60

    def test_simple_string(self):
        assert parse_duration("10 min") == 600

    def test_compound(self):
        assert parse_duration("1h 30min") == 5400

    def test_supports_months_and_years(self):
        assert parse_duration("1 mon") == 2_592_000
        assert parse_duration("1 y") == 31_536_000

    def test_supports_micro_and_nanoseconds(self):
        assert parse_duration("1 us") == 1
        assert parse_duration("1 ns") == 1

    def test_subsecond_values_round_up(self):
        assert parse_duration("1 ms") == 1
        assert parse_duration("1001 ms") == 2

    def test_supports_plus_syntax(self):
        assert parse_duration("1m+30") == 90

    def test_zero(self):
        assert parse_duration("0") == 0

    @pytest.mark.parametrize("value", [-1, -0.5, True, ""])
    def test_negative_or_blank_values_rejected(self, value):
        with pytest.raises(ValueError, match="Invalid duration"):
            parse_duration(value)

    def test_invalid(self):
        with pytest.raises(ValueError, match="Invalid duration"):
            parse_duration("not a duration")

    def test_rejects_garbage_suffix(self):
        with pytest.raises(ValueError, match="Invalid duration"):
            parse_duration("1h-nope")


class TestInject:
    def test_valid_pairing(self):
        i = Inject(from_entity="red", to_entities=["blue"])
        assert i.from_entity == "red"

    def test_rejects_partial_pairing(self):
        with pytest.raises(ValidationError, match="both"):
            Inject(from_entity="red")


class TestScript:
    def test_valid(self):
        s = Script(
            start_time="10 min",
            end_time="2 hour",
            speed=1.0,
            events={"evt-1": "30 min"},
        )
        assert s.start_time == 600
        assert s.end_time == 7200

    def test_end_before_start_rejected(self):
        with pytest.raises(ValidationError, match="end_time"):
            Script(
                start_time="2 hour",
                end_time="10 min",
                speed=1.0,
                events={"evt-1": "30 min"},
            )

    def test_event_outside_bounds_rejected(self):
        with pytest.raises(ValidationError, match="outside"):
            Script(
                start_time="10 min",
                end_time="20 min",
                speed=1.0,
                events={"evt-1": "30 min"},
            )

    def test_variable_placeholders(self):
        s = Script(
            start_time="${script_start}",
            end_time="${script_end}",
            speed="${script_speed}",
            events={"evt-1": "${event_time}"},
        )
        assert s.start_time == "${script_start}"
        assert s.end_time == "${script_end}"
        assert s.speed == "${script_speed}"
        assert s.events["evt-1"] == "${event_time}"


class TestStory:
    def test_valid(self):
        s = Story(scripts=["script-1"])
        assert s.speed == 1.0

    def test_speed_below_1_rejected(self):
        with pytest.raises(ValidationError, match="speed must be >= 1.0"):
            Story(scripts=["script-1"], speed=0.5)


# ---------------------------------------------------------------------------
# Objectives (ACES extensions)
# ---------------------------------------------------------------------------


class TestObjectiveSuccess:
    def test_requires_at_least_one_reference(self):
        with pytest.raises(ValidationError, match="at least one condition"):
            ObjectiveSuccess()

    def test_accepts_goal_reference(self):
        success = ObjectiveSuccess(goals=["pass-exercise"])
        assert success.goals == ["pass-exercise"]

    def test_mode_placeholder(self):
        success = ObjectiveSuccess(
            mode="${objective_mode}",
            goals=["pass-exercise"],
        )
        assert success.mode == "${objective_mode}"


class TestObjective:
    def test_requires_exactly_one_actor_binding(self):
        with pytest.raises(ValidationError, match="exactly one"):
            Objective(
                success={"goals": ["g1"]},
            )

        with pytest.raises(ValidationError, match="exactly one"):
            Objective(
                agent="red-agent",
                entity="red-team",
                success={"goals": ["g1"]},
            )

    def test_valid_agent_objective(self):
        objective = Objective(
            agent="red-agent",
            actions=["Scan"],
            targets=["web-server"],
            success={"goals": ["initial-access"]},
            window={
                "scripts": ["main-timeline"],
                "events": ["attack-wave"],
                "workflows": ["response-flow"],
                "steps": ["response-flow.validate"],
            },
            depends_on=["recon"],
        )
        assert objective.agent == "red-agent"
        assert objective.success.goals == ["initial-access"]
        assert isinstance(objective.window, ObjectiveWindow)
        assert objective.window.steps == ["response-flow.validate"]

    def test_valid_entity_objective(self):
        objective = Objective(
            entity="blue-team",
            success={"metrics": ["report-quality"]},
        )
        assert objective.entity == "blue-team"


# ---------------------------------------------------------------------------
# Extension models (G1-G9, G12-G13)
# ---------------------------------------------------------------------------

from aces.core.sdl.accounts import Account, PasswordStrength
from aces.core.sdl.content import Content, ContentItem, ContentType
from aces.core.sdl.nodes import AssetValue, AssetValueLevel, OSFamily, ServicePort


class TestContent:
    def test_file_content(self):
        c = Content(type="file", target="victim", path="/tmp/flag.txt", text="FLAG{x}")
        assert c.type == ContentType.FILE
        assert c.text == "FLAG{x}"

    def test_dataset_content(self):
        c = Content(
            type="dataset",
            target="exchange",
            format="eml",
            items=[ContentItem(name="email.eml", tags=["phishing"])],
        )
        assert len(c.items) == 1
        assert c.items[0].tags == ["phishing"]

    def test_sensitive_flag(self):
        c = Content(type="file", target="fs", path="/keys/id_rsa", sensitive=True)
        assert c.sensitive is True

    def test_sensitive_placeholder(self):
        c = Content(
            type="file",
            target="fs",
            path="/tmp/flag.txt",
            sensitive="${contains_sensitive_data}",
        )
        assert c.sensitive == "${contains_sensitive_data}"

    def test_requires_target(self):
        with pytest.raises(ValidationError, match="Content requires 'target'"):
            Content(type="file", path="/tmp/flag.txt")

    def test_file_requires_path(self):
        with pytest.raises(ValidationError, match="File content requires 'path'"):
            Content(type="file", target="victim")

    def test_dataset_requires_source_or_items(self):
        with pytest.raises(
            ValidationError,
            match="Dataset content requires either 'source' or non-empty 'items'",
        ):
            Content(type="dataset", target="victim")

    def test_directory_requires_destination(self):
        with pytest.raises(
            ValidationError,
            match="Directory content requires 'destination'",
        ):
            Content(type="directory", target="victim")


class TestAccount:
    def test_basic_account(self):
        a = Account(username="admin", node="dc")
        assert a.password_strength == PasswordStrength.MEDIUM

    def test_weak_account(self):
        a = Account(username="svc", node="dc", password_strength="weak")
        assert a.password_strength == PasswordStrength.WEAK

    def test_account_with_ad_fields(self):
        a = Account(
            username="svc_sql",
            node="dc",
            groups=["Domain Users"],
            spn="MSSQL/db.corp.local",
            password_strength="weak",
        )
        assert a.spn == "MSSQL/db.corp.local"

    def test_key_auth(self):
        a = Account(username="labadmin", node="victim", auth_method="key", password_strength="none")
        assert a.auth_method == "key"

    def test_disabled_placeholder(self):
        a = Account(username="svc", node="dc", disabled="${is_disabled}")
        assert a.disabled == "${is_disabled}"

    def test_password_strength_placeholder(self):
        a = Account(
            username="svc",
            node="dc",
            password_strength="${password_strength}",
        )
        assert a.password_strength == "${password_strength}"

    def test_requires_node(self):
        with pytest.raises(ValidationError, match="Account requires 'node'"):
            Account(username="admin")


class TestACLRule:
    def test_allow_rule(self):
        r = ACLRule(direction="in", from_net="wan", protocol="tcp", ports=[80, 443], action="allow")
        assert r.action == ACLAction.ALLOW
        assert r.ports == [80, 443]

    def test_deny_rule(self):
        r = ACLRule(direction="out", to_net="wan", action="deny")
        assert r.action == ACLAction.DENY

    def test_named_rule(self):
        r = ACLRule(name="allow-admin", direction="out", to_net="wan")
        assert r.name == "allow-admin"

    def test_port_placeholder(self):
        r = ACLRule(direction="in", from_net="wan", ports=["${https_port}"])
        assert r.ports == ["${https_port}"]

    def test_action_placeholder(self):
        r = ACLRule(direction="in", from_net="wan", action="${acl_action}")
        assert r.action == "${acl_action}"


class TestOSFamily:
    def test_windows(self):
        n = Node(type="vm", os="windows", resources={"ram": "1 gib", "cpu": 1})
        assert n.os == OSFamily.WINDOWS

    def test_linux(self):
        n = Node(type="vm", os="linux", resources={"ram": "1 gib", "cpu": 1})
        assert n.os == OSFamily.LINUX

    def test_no_os(self):
        n = Node(type="vm", resources={"ram": "1 gib", "cpu": 1})
        assert n.os is None

    def test_os_placeholder(self):
        n = Node(
            type="vm",
            os="${node_os}",
            resources={"ram": "1 gib", "cpu": 1},
        )
        assert n.os == "${node_os}"


class TestAssetValue:
    def test_defaults(self):
        av = AssetValue()
        assert av.confidentiality == AssetValueLevel.MEDIUM

    def test_custom(self):
        av = AssetValue(confidentiality="critical", availability="high")
        assert av.confidentiality == AssetValueLevel.CRITICAL

    def test_on_node(self):
        n = Node(
            type="vm",
            resources={"ram": "1 gib", "cpu": 1},
            asset_value={"confidentiality": "high", "availability": "critical"},
        )
        assert n.asset_value.confidentiality == AssetValueLevel.HIGH

    def test_placeholder(self):
        av = AssetValue(confidentiality="${cia_value}")
        assert av.confidentiality == "${cia_value}"


class TestServicePort:
    def test_basic(self):
        sp = ServicePort(port=443, name="https")
        assert sp.protocol == "tcp"

    def test_on_node(self):
        n = Node(
            type="vm",
            resources={"ram": "1 gib", "cpu": 1},
            services=[{"port": 22, "name": "ssh"}, {"port": 80, "name": "http"}],
        )
        assert len(n.services) == 2

    def test_duplicate_port_protocol_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate service binding"):
            Node(
                type="vm",
                resources={"ram": "1 gib", "cpu": 1},
                services=[
                    {"port": 443, "protocol": "tcp", "name": "https"},
                    {"port": 443, "protocol": "tcp", "name": "alt-https"},
                ],
            )

    def test_duplicate_named_service_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate named service"):
            Node(
                type="vm",
                resources={"ram": "1 gib", "cpu": 1},
                services=[
                    {"port": 22, "name": "admin"},
                    {"port": 443, "name": "admin"},
                ],
            )

    def test_same_port_with_different_protocols_allowed(self):
        n = Node(
            type="vm",
            resources={"ram": "1 gib", "cpu": 1},
            services=[
                {"port": 53, "protocol": "tcp", "name": "dns-tcp"},
                {"port": 53, "protocol": "udp", "name": "dns-udp"},
            ],
        )
        assert len(n.services) == 2

    def test_placeholder(self):
        sp = ServicePort(port="${service_port}", name="https")
        assert sp.port == "${service_port}"


class TestConditionExtensions:
    def test_timeout_and_retries(self):
        from aces.core.sdl.conditions import Condition

        c = Condition(command="/check", interval=15, timeout=5, retries=3, start_period=10)
        assert c.timeout == 5
        assert c.retries == 3
        assert c.start_period == 10


class TestSimplePropertiesInternal:
    def test_internal_flag(self):
        from aces.core.sdl.infrastructure import SimpleProperties

        p = SimpleProperties(cidr="10.0.0.0/24", gateway="10.0.0.1", internal=True)
        assert p.internal is True

    def test_default_not_internal(self):
        from aces.core.sdl.infrastructure import SimpleProperties

        p = SimpleProperties(cidr="10.0.0.0/24", gateway="10.0.0.1")
        assert p.internal is False


class TestWorkflow:
    def test_objective_step(self):
        step = WorkflowStep(
            type="objective",
            objective="verify-release",
            **{"on-success": "done"},
        )
        assert step.type == WorkflowStepType.OBJECTIVE
        assert step.objective == "verify-release"

    def test_decision_step_requires_branches(self):
        with pytest.raises(
            ValidationError,
            match="requires 'when', 'then', and 'else'",
        ):
            WorkflowStep(type="decision", when={"goals": ["g1"]})

    def test_parallel_step_requires_unique_branches(self):
        with pytest.raises(ValidationError, match="branches must be unique"):
            WorkflowStep(type="parallel", branches=["a", "a"], join="done")

    def test_valid_workflow(self):
        workflow = Workflow(
            start="validate",
            steps={
                "validate": {
                    "type": "objective",
                    "objective": "verify-release",
                    "on-success": "done",
                },
                "done": {"type": "end"},
            },
        )
        assert workflow.start == "validate"
        assert set(workflow.steps) == {"validate", "done"}

    def test_retry_step(self):
        step = WorkflowStep(
            type="retry",
            objective="verify-release",
            **{"on-success": "done", "max-attempts": 5},
        )
        assert step.type == WorkflowStepType.RETRY
        assert step.objective == "verify-release"
        assert step.on_success == "done"
        assert step.max_attempts == 5

    def test_retry_step_requires_objective_attempts_and_success_target(self):
        with pytest.raises(
            ValidationError,
            match="requires 'objective', 'max-attempts', and 'on-success'",
        ):
            WorkflowStep(type="retry", objective="verify-release")

    def test_switch_step(self):
        step = WorkflowStep(
            type="switch",
            cases=[
                {
                    "when": {"goals": ["g1"]},
                    "next": "done",
                }
            ],
            default="fallback",
        )
        assert step.type == WorkflowStepType.SWITCH
        assert step.default_step == "fallback"
        assert step.cases[0].next_step == "done"

    def test_call_step(self):
        step = WorkflowStep(
            type="call",
            workflow="child",
            **{"on-success": "done"},
        )
        assert step.type == WorkflowStepType.CALL
        assert step.workflow == "child"

    def test_workflow_timeout_scalar_parses_to_policy(self):
        workflow = Workflow(
            start="validate",
            timeout="5 min",
            steps={
                "validate": {
                    "type": "objective",
                    "objective": "verify-release",
                    "on-success": "done",
                },
                "done": {"type": "end"},
            },
        )
        assert workflow.timeout is not None
        assert workflow.timeout.seconds == 300

    def test_retry_step_forbids_decision_fields(self):
        with pytest.raises(
            ValidationError,
            match="Retry workflow step only supports",
        ):
            WorkflowStep(
                type="retry",
                objective="verify-release",
                **{
                    "on-success": "done",
                    "max-attempts": 3,
                    "then": "a",
                    "else": "b",
                },
            )

    def test_retry_max_attempts_must_be_positive(self):
        with pytest.raises(ValidationError, match="must be >= 1"):
            WorkflowStep(
                type="retry",
                objective="verify-release",
                **{"on-success": "done", "max-attempts": 0},
            )

    def test_retry_max_attempts_accepts_variable(self):
        step = WorkflowStep(
            type="retry",
            objective="verify-release",
            **{"on-success": "done", "max-attempts": "${max_retries}"},
        )
        assert step.max_attempts == "${max_retries}"

    def test_on_failure_on_objective_step(self):
        step = WorkflowStep(
            type="objective",
            objective="verify-release",
            **{"on-success": "done", "on-failure": "recover"},
        )
        assert step.on_failure == "recover"

    def test_on_failure_on_parallel_step(self):
        step = WorkflowStep(
            type="parallel",
            branches=["a", "b"],
            join="done",
            **{"on-failure": "recover"},
        )
        assert step.on_failure == "recover"

    def test_on_exhausted_accepts_variable(self):
        step = WorkflowStep(
            type="retry",
            objective="verify-release",
            **{
                "on-success": "done",
                "max-attempts": 3,
                "on-exhausted": "${recovery_step}",
            },
        )
        assert step.on_exhausted == "${recovery_step}"

    def test_on_failure_forbidden_on_decision_step(self):
        with pytest.raises(
            ValidationError,
            match="Decision workflow step only supports",
        ):
            WorkflowStep(
                type="decision",
                when={"goals": ["g1"]},
                **{"then": "a", "else": "b", "on-failure": "recover"},
            )

    def test_join_step_requires_next(self):
        with pytest.raises(ValidationError, match="Join workflow step requires 'next'"):
            WorkflowStep(type="join")

    def test_step_state_predicate(self):
        pred = WorkflowPredicate(steps=[{"step": "step-a", "outcomes": ["failed"], "min-attempts": 2}])
        assert pred.steps[0].step == "step-a"
        assert pred.steps[0].outcomes == [WorkflowStepOutcome.FAILED]
        assert pred.steps[0].min_attempts == 2

    def test_predicate_with_only_step_state_is_valid(self):
        pred = WorkflowPredicate(
            steps=[
                {"step": "step-a", "outcomes": ["failed"]},
                {"step": "step-b", "outcomes": ["succeeded"]},
            ]
        )
        assert len(pred.steps) == 2

    def test_legacy_workflow_step_type_rejected(self):
        with pytest.raises(ValidationError, match="no longer supported"):
            WorkflowStep(type="if", when={"goals": ["g1"]}, **{"then": "a", "else": "b"})

    def test_predicate_empty_rejected(self):
        with pytest.raises(ValidationError, match="must reference at least one"):
            WorkflowPredicate()


# ---------------------------------------------------------------------------
# Relationships, Agents, Variables (G10, G11, Identity)
# ---------------------------------------------------------------------------

from aces.core.sdl.agents import Agent, InitialKnowledge
from aces.core.sdl.relationships import Relationship, RelationshipType
from aces.core.sdl.variables import Variable, VariableType


class TestRelationship:
    def test_authenticates_with(self):
        r = Relationship(type="authenticates_with", source="exchange", target="ad-ds")
        assert r.type == RelationshipType.AUTHENTICATES_WITH

    def test_trusts_with_properties(self):
        r = Relationship(
            type="trusts",
            source="child-domain",
            target="parent-domain",
            properties={"trust_type": "parent-child", "trust_direction": "bidirectional"},
        )
        assert r.properties["trust_type"] == "parent-child"

    def test_connects_to(self):
        r = Relationship(
            type="connects_to", source="webapp", target="db", properties={"protocol": "tcp", "port": "5432"}
        )
        assert r.source == "webapp"
        assert r.type == RelationshipType.CONNECTS_TO
        assert r.properties == {"protocol": "tcp", "port": "5432"}

    def test_federates_with(self):
        r = Relationship(type="federates_with", source="adfs", target="azure-ad", properties={"protocol": "SAML"})
        assert r.type == RelationshipType.FEDERATES_WITH


class TestAgent:
    def test_basic_agent(self):
        a = Agent(entity="red-team", actions=["Scan", "Exploit"])
        assert len(a.actions) == 2

    def test_agent_with_starting_accounts(self):
        a = Agent(
            entity="red-team",
            starting_accounts=["phished-user"],
            allowed_subnets=["user-net"],
        )
        assert a.starting_accounts == ["phished-user"]

    def test_agent_with_initial_knowledge(self):
        a = Agent(
            entity="blue-team",
            initial_knowledge=InitialKnowledge(
                hosts=["defender", "server1"],
                subnets=["enterprise-net"],
            ),
        )
        assert len(a.initial_knowledge.hosts) == 2

    def test_initial_knowledge_defaults(self):
        ik = InitialKnowledge()
        assert ik.hosts == []
        assert ik.subnets == []
        assert ik.services == []
        assert ik.accounts == []

    def test_requires_entity(self):
        with pytest.raises(ValidationError, match="Agent requires 'entity'"):
            Agent(actions=["Scan"])

    def test_default_framing_lists_are_empty(self):
        a = Agent(entity="red-team")
        assert a.starting_conditions == []
        assert a.authority_anchors == []
        assert a.operating_scope == []

    def test_starting_conditions_field(self):
        a = Agent(entity="red-team", starting_conditions=["beacon-online", "vpn-up"])
        assert a.starting_conditions == ["beacon-online", "vpn-up"]

    def test_authority_anchors_field(self):
        a = Agent(
            entity="red-team",
            authority_anchors=["red-team", "trusts-blue-domain"],
        )
        assert a.authority_anchors == ["red-team", "trusts-blue-domain"]

    def test_operating_scope_field(self):
        a = Agent(
            entity="red-team",
            operating_scope=["corp-net", "dmz-net"],
        )
        assert a.operating_scope == ["corp-net", "dmz-net"]

    def test_framing_fields_accept_variable_placeholders(self):
        a = Agent(
            entity="red-team",
            starting_conditions=["${beacon_condition}"],
            authority_anchors=["${authority_ref}"],
            operating_scope=["${scope_ref}"],
        )
        assert a.starting_conditions == ["${beacon_condition}"]
        assert a.authority_anchors == ["${authority_ref}"]
        assert a.operating_scope == ["${scope_ref}"]

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            Agent(entity="red-team", unknown_field=["x"])


class TestVariable:
    def test_string_variable(self):
        v = Variable(type="string", default="techvault.local", description="Domain name")
        assert v.type == VariableType.STRING

    def test_integer_variable(self):
        v = Variable(type="integer", default=5)
        assert v.default == 5

    def test_variable_with_allowed_values(self):
        v = Variable(type="string", default="weak", allowed_values=["weak", "medium", "strong"])
        assert len(v.allowed_values) == 3

    def test_required_variable(self):
        v = Variable(type="string", required=True)
        assert v.required is True
        assert v.default is None

    def test_boolean_variable(self):
        v = Variable(type="boolean", default=True)
        assert v.type == VariableType.BOOLEAN

    def test_rejects_default_with_wrong_type(self):
        with pytest.raises(ValidationError, match="default must match"):
            Variable(type="integer", default="five")

    def test_rejects_allowed_values_with_wrong_type(self):
        with pytest.raises(ValidationError, match="allowed_values must match"):
            Variable(type="boolean", allowed_values=[True, "false"])

    def test_rejects_default_outside_allowed_values(self):
        with pytest.raises(ValidationError, match="default must be one of allowed_values"):
            Variable(type="string", default="critical", allowed_values=["low", "medium", "high"])

    def test_number_variable_accepts_int_and_float_allowed_values(self):
        v = Variable(type="number", default=1.5, allowed_values=[1, 1.5, 2.0])
        assert v.default == 1.5


class TestBooleanPlaceholders:
    def test_vulnerability_technical_placeholder(self):
        v = Vulnerability(
            name="SQLi",
            description="SQL injection",
            technical="${is_technical}",
            **{"class": "CWE-89"},
        )
        assert v.technical == "${is_technical}"
