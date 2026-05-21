"""Observed runtime configuration models for SDL nodes."""

import re
from enum import Enum

from pydantic import Field, ValidationInfo, field_validator, model_validator

from ._base import (
    SDLModel,
    is_variable_ref,
    parse_bool_or_var,
    parse_float_or_var,
    parse_int_or_var,
)
from .runtime_application import (
    RuntimeApplicationDisclosure,
    RuntimeApplicationExposedField,
    RuntimeApplicationParameter,
    RuntimeApplicationParameterLocation,
    RuntimeApplicationProtocol,
    RuntimeApplicationRedirect,
    RuntimeApplicationResponse,
    RuntimeApplicationRoute,
    RuntimeApplicationSurface,
)
from .runtime_container import (
    RuntimeContainerConfiguration,
    RuntimeDeviceMapping,
    RuntimeExtraHost,
    RuntimeHealthcheckLog,
    RuntimeHealthObservation,
    RuntimeHealthStatus,
    RuntimeNamespaceConfiguration,
)
from .runtime_filesystem import (
    RuntimeFilesystemEntry,
    RuntimeFilesystemEntryType,
    RuntimeFilesystemStability,
    RuntimeMountPropagation,
    RuntimeSensitivityClassification,
)
from .runtime_identity import (
    RuntimeIdentityProvenance,
    RuntimeLocalGroup,
    RuntimeLocalIdentityInventory,
    RuntimeLocalUser,
    RuntimeSudoPrincipalKind,
    RuntimeSudoRule,
)
from .runtime_network import (
    RuntimeNetworkBackendDetail,
    RuntimeNetworkDriver,
    RuntimeNetworkEndpoint,
    RuntimeNetworkIdStability,
    RuntimeNetworkRealization,
    RuntimePublishedPort,
)
from .runtime_values import (
    absolute_path_or_var as _absolute_path_or_var,
)
from .runtime_values import (
    coerce_string_list as _coerce_string_list,
)
from .runtime_values import (
    control_interface_path_or_var as _control_interface_path_or_var,
)
from .runtime_values import (
    is_windows_named_pipe as _is_windows_named_pipe,
)
from .runtime_values import (
    parse_optional_bool_or_var as _parse_optional_bool_or_var,
)
from .runtime_values import (
    parse_ram,
)
from .runtime_values import (
    parse_runtime_enum_or_var as _parse_runtime_enum_or_var,
)

__all__ = [
    "RuntimeApplicationDisclosure",
    "RuntimeApplicationExposedField",
    "RuntimeApplicationParameter",
    "RuntimeApplicationParameterLocation",
    "RuntimeApplicationProtocol",
    "RuntimeApplicationRedirect",
    "RuntimeApplicationResponse",
    "RuntimeApplicationRoute",
    "RuntimeApplicationSurface",
    "RuntimeCapabilityPolicy",
    "RuntimeConfiguration",
    "RuntimeContainerConfiguration",
    "RuntimeControlInterface",
    "RuntimeControlInterfaceAccess",
    "RuntimeControlInterfaceKind",
    "RuntimeDependencyManifest",
    "RuntimeDeviceMapping",
    "RuntimeEnvironmentValueClassification",
    "RuntimeEnvironmentVariable",
    "RuntimeEnvironmentVariableProvenance",
    "RuntimeExtraHost",
    "RuntimeFilesystemEntry",
    "RuntimeFilesystemEntryType",
    "RuntimeFilesystemStability",
    "RuntimeHealthObservation",
    "RuntimeHealthStatus",
    "RuntimeHealthcheckLog",
    "RuntimeIdentityProvenance",
    "RuntimeLocalGroup",
    "RuntimeLocalIdentityInventory",
    "RuntimeLocalUser",
    "RuntimeMount",
    "RuntimeMountPropagation",
    "RuntimeMountSourceKind",
    "RuntimeNamespaceConfiguration",
    "RuntimeNetworkBackendDetail",
    "RuntimeNetworkDriver",
    "RuntimeNetworkEndpoint",
    "RuntimeNetworkIdStability",
    "RuntimeNetworkRealization",
    "RuntimeOperationalPolicy",
    "RuntimePackage",
    "RuntimePackageVulnerabilityFinding",
    "RuntimePackageVulnerabilitySeverity",
    "RuntimeProcessIdentity",
    "RuntimeProcessRole",
    "RuntimePublishedPort",
    "RuntimeResourceLimits",
    "RuntimeRestartPolicy",
    "RuntimeSensitivityClassification",
    "RuntimeSudoPrincipalKind",
    "RuntimeSudoRule",
    "parse_ram",
]


class RuntimeMountSourceKind(str, Enum):
    """Portable source kind for a runtime filesystem mount."""

    VOLUME = "volume"
    BIND = "bind"
    TMPFS = "tmpfs"
    IMAGE = "image"
    OTHER = "other"


class RuntimeControlInterfaceKind(str, Enum):
    """Path-local control interface shape observed at runtime."""

    UNIX_SOCKET = "unix_socket"
    NAMED_PIPE = "named_pipe"
    FILE = "file"
    OTHER = "other"


class RuntimeControlInterfaceAccess(str, Enum):
    """Observed local-control access mode."""

    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    UNKNOWN = "unknown"


class RuntimePackageVulnerabilitySeverity(str, Enum):
    """Scanner-derived package finding severity."""

    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuntimeProcessRole(str, Enum):
    """Observed role of a process in a runtime process set."""

    PRIMARY = "primary"
    SUPERVISOR = "supervisor"
    WORKER = "worker"
    SIDECAR = "sidecar"
    AGENT = "agent"
    OTHER = "other"


class RuntimeEnvironmentValueClassification(str, Enum):
    """Sensitivity classification for an observed runtime environment value."""

    PLAIN = "plain"
    REDACTED = "redacted"
    SECRET_FIXTURE = "secret_fixture"  # noqa: S105
    UNKNOWN = "unknown"


class RuntimeEnvironmentVariableProvenance(str, Enum):
    """Origin class for an observed runtime environment variable."""

    COMPOSE = "compose"
    IMAGE = "image"
    OPERATOR = "operator"
    CONTAINER = "container"
    RUNTIME = "runtime"
    OTHER = "other"
    UNKNOWN = "unknown"


class RuntimeRestartPolicy(str, Enum):
    """Portable restart policy classification observed at runtime."""

    NO = "no"
    ALWAYS = "always"
    ON_FAILURE = "on_failure"
    UNLESS_STOPPED = "unless_stopped"
    UNKNOWN = "unknown"
    OTHER = "other"


def _normalize_capability_name(value: str) -> str:
    if is_variable_ref(value):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError("capability names must be non-empty strings")
    normalized = value.strip().upper().replace("-", "_")
    if not re.fullmatch(r"CAP_[A-Z0-9_]+", normalized):
        raise ValueError("capability names must use Linux CAP_* form")
    return normalized


class RuntimeMount(SDLModel):
    """A filesystem mount observed on a runtime node."""

    target: str
    source: str = ""
    source_kind: RuntimeMountSourceKind | str = RuntimeMountSourceKind.OTHER
    filesystem_type: str = ""
    read_only: bool | str = False
    options: list[str] = Field(default_factory=list)
    propagation: RuntimeMountPropagation | str = RuntimeMountPropagation.UNKNOWN
    stability: RuntimeFilesystemStability | str = RuntimeFilesystemStability.UNKNOWN
    backend_generated: bool | str | None = None
    description: str = ""

    @field_validator("target")
    @classmethod
    def validate_target(cls, v: str) -> str:
        return _absolute_path_or_var(v, field_name="target")

    @field_validator("source_kind", mode="before")
    @classmethod
    def normalize_source_kind(cls, v: RuntimeMountSourceKind | str) -> RuntimeMountSourceKind | str:
        return _parse_runtime_enum_or_var(v, RuntimeMountSourceKind, field_name="source_kind")

    @field_validator("read_only", mode="before")
    @classmethod
    def parse_read_only(cls, v: bool | str) -> bool | str:
        return parse_bool_or_var(v, field_name="read_only")

    @field_validator("propagation", mode="before")
    @classmethod
    def normalize_propagation(cls, v: RuntimeMountPropagation | str) -> RuntimeMountPropagation | str:
        return _parse_runtime_enum_or_var(v, RuntimeMountPropagation, field_name="propagation")

    @field_validator("stability", mode="before")
    @classmethod
    def normalize_stability(cls, v: RuntimeFilesystemStability | str) -> RuntimeFilesystemStability | str:
        return _parse_runtime_enum_or_var(v, RuntimeFilesystemStability, field_name="stability")

    @field_validator("backend_generated", mode="before")
    @classmethod
    def parse_backend_generated(cls, v: bool | str | None) -> bool | str | None:
        return _parse_optional_bool_or_var(v, field_name="backend_generated")


class RuntimeControlInterface(SDLModel):
    """A non-network local control API exposed inside a runtime node."""

    path: str
    kind: RuntimeControlInterfaceKind | str = RuntimeControlInterfaceKind.UNIX_SOCKET
    protocol: str = ""
    bind_source: str = ""
    access: RuntimeControlInterfaceAccess | str = RuntimeControlInterfaceAccess.UNKNOWN
    description: str = ""

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        return _control_interface_path_or_var(v, field_name="path")

    @field_validator("bind_source")
    @classmethod
    def validate_bind_source(cls, v: str) -> str:
        return _control_interface_path_or_var(v, field_name="bind_source") if v else v

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, v: RuntimeControlInterfaceKind | str) -> RuntimeControlInterfaceKind | str:
        return _parse_runtime_enum_or_var(v, RuntimeControlInterfaceKind, field_name="kind")

    @field_validator("access", mode="before")
    @classmethod
    def normalize_access(cls, v: RuntimeControlInterfaceAccess | str) -> RuntimeControlInterfaceAccess | str:
        return _parse_runtime_enum_or_var(v, RuntimeControlInterfaceAccess, field_name="access")

    @model_validator(mode="after")
    def validate_named_pipe_kind(self) -> "RuntimeControlInterface":
        if is_variable_ref(self.kind):
            return self
        has_windows_named_pipe_endpoint = _is_windows_named_pipe(self.path) or _is_windows_named_pipe(self.bind_source)
        if has_windows_named_pipe_endpoint and self.kind != RuntimeControlInterfaceKind.NAMED_PIPE:
            raise ValueError("Windows named pipe paths require kind 'named_pipe'")
        return self


class RuntimeProcessIdentity(SDLModel):
    """Observed process identity for a runtime node."""

    name: str = ""
    pid: int | str | None = None
    parent_pid: int | str | None = None
    command: list[str] = Field(default_factory=list)
    command_redacted: bool | str = False
    role: RuntimeProcessRole | str = RuntimeProcessRole.OTHER
    user: str = ""
    group: str = ""
    working_directory: str = ""
    description: str = ""

    @field_validator("pid", mode="before")
    @classmethod
    def parse_pid(cls, v: int | str | None) -> int | str | None:
        return parse_int_or_var(v, minimum=1, field_name="pid") if v is not None else v

    @field_validator("parent_pid", mode="before")
    @classmethod
    def parse_parent_pid(cls, v: int | str | None) -> int | str | None:
        return parse_int_or_var(v, minimum=1, field_name="parent_pid") if v is not None else v

    @field_validator("command", mode="before")
    @classmethod
    def normalize_command(cls, v: str | list[str] | None) -> list[str]:
        return _coerce_string_list(v)

    @field_validator("command_redacted", mode="before")
    @classmethod
    def parse_command_redacted(cls, v: bool | str) -> bool | str:
        return parse_bool_or_var(v, field_name="command_redacted")

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: RuntimeProcessRole | str) -> RuntimeProcessRole | str:
        return _parse_runtime_enum_or_var(v, RuntimeProcessRole, field_name="role")

    @field_validator("working_directory")
    @classmethod
    def validate_working_directory(cls, v: str) -> str:
        return _absolute_path_or_var(v, field_name="working_directory") if v else v


class RuntimeEnvironmentVariable(SDLModel):
    """Observed runtime environment variable with provenance and sensitivity."""

    name: str
    value: str = ""
    value_classification: RuntimeEnvironmentValueClassification | str = RuntimeEnvironmentValueClassification.UNKNOWN
    provenance: RuntimeEnvironmentVariableProvenance | str = RuntimeEnvironmentVariableProvenance.UNKNOWN
    source: str = ""
    description: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("environment variable name must be a non-empty string")
        if "=" in v:
            raise ValueError("environment variable name must not contain '='")
        return v

    @field_validator("value_classification", mode="before")
    @classmethod
    def normalize_value_classification(
        cls,
        v: RuntimeEnvironmentValueClassification | str,
    ) -> RuntimeEnvironmentValueClassification | str:
        return _parse_runtime_enum_or_var(
            v,
            RuntimeEnvironmentValueClassification,
            field_name="value_classification",
        )

    @field_validator("provenance", mode="before")
    @classmethod
    def normalize_provenance(
        cls,
        v: RuntimeEnvironmentVariableProvenance | str,
    ) -> RuntimeEnvironmentVariableProvenance | str:
        return _parse_runtime_enum_or_var(v, RuntimeEnvironmentVariableProvenance, field_name="provenance")

    @model_validator(mode="after")
    def validate_redacted_value(self) -> "RuntimeEnvironmentVariable":
        if self.value_classification == RuntimeEnvironmentValueClassification.REDACTED and self.value:
            raise ValueError("redacted runtime environment variables must omit value")
        return self


class RuntimeCapabilityPolicy(SDLModel):
    """Linux/container capability policy observed for a runtime node."""

    required: list[str] = Field(default_factory=list)
    effective: list[str] = Field(default_factory=list)
    add: list[str] = Field(default_factory=list)
    drop: list[str] = Field(default_factory=list)
    description: str = ""

    @field_validator("required", "effective", "add", "drop", mode="before")
    @classmethod
    def coerce_capability_lists(cls, v):
        return _coerce_string_list(v)

    @field_validator("required", "effective", "add", "drop")
    @classmethod
    def validate_capability_names(cls, v: list[str]) -> list[str]:
        return [_normalize_capability_name(item) for item in v]

    @model_validator(mode="after")
    def validate_unique_capabilities(self) -> "RuntimeCapabilityPolicy":
        for field_name in ("required", "effective", "add", "drop"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate runtime capability in {field_name}")
        return self


class RuntimeResourceLimits(SDLModel):
    """Observed runtime/cgroup resource limits for a node."""

    memory: int | str | None = None
    memory_swap: int | str | None = None
    cpu: float | str | None = None
    pids: int | str | None = None
    open_files: int | str | None = None
    description: str = ""

    @field_validator("memory", "memory_swap", mode="before")
    @classmethod
    def parse_memory_limit(cls, v: int | str | None) -> int | str | None:
        return parse_ram(v) if v is not None else v

    @field_validator("cpu", mode="before")
    @classmethod
    def parse_cpu_limit(cls, v: float | str | None) -> float | str | None:
        return parse_float_or_var(v, minimum=0, field_name="cpu") if v is not None else v

    @field_validator("pids", "open_files", mode="before")
    @classmethod
    def parse_count_limit(cls, v: int | str | None, info: ValidationInfo) -> int | str | None:
        return parse_int_or_var(v, minimum=1, field_name=info.field_name) if v is not None else v


class RuntimeOperationalPolicy(SDLModel):
    """Observed restart and resource-limit policy for a runtime node."""

    restart: RuntimeRestartPolicy | str = RuntimeRestartPolicy.UNKNOWN
    resource_limits: RuntimeResourceLimits | None = None
    description: str = ""

    @field_validator("restart", mode="before")
    @classmethod
    def normalize_restart(cls, v: RuntimeRestartPolicy | str | bool) -> RuntimeRestartPolicy | str:
        if v is False:
            return RuntimeRestartPolicy.NO
        return _parse_runtime_enum_or_var(v, RuntimeRestartPolicy, field_name="restart")


class RuntimePackage(SDLModel):
    """A package observed in a runtime image or node."""

    manager: str
    name: str
    version: str
    architecture: str = ""
    source: str = ""
    purl: str = ""


class RuntimeDependencyManifest(SDLModel):
    """A dependency manifest visible in the realized runtime artifact."""

    ecosystem: str
    path: str
    format: str = ""
    name: str = ""
    version: str = ""

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        return _absolute_path_or_var(v, field_name="path")


class RuntimePackageVulnerabilityFinding(SDLModel):
    """A scanner-derived CVE/advisory finding for an observed package."""

    id: str
    package_name: str
    installed_version: str
    severity: RuntimePackageVulnerabilitySeverity | str = RuntimePackageVulnerabilitySeverity.UNKNOWN
    scanner: str
    image_digest: str
    scan_time: str
    fixed_version: str = ""
    advisory_url: str = ""
    scanner_version: str = ""
    scanner_database: str = ""

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(
        cls,
        v: RuntimePackageVulnerabilitySeverity | str,
    ) -> RuntimePackageVulnerabilitySeverity | str:
        return _parse_runtime_enum_or_var(v, RuntimePackageVulnerabilitySeverity, field_name="severity")


class RuntimeConfiguration(SDLModel):
    """Observed runtime configuration facts attached to a VM node."""

    mounts: list[RuntimeMount] = Field(default_factory=list)
    filesystem_inventory: list[RuntimeFilesystemEntry] = Field(default_factory=list)
    local_control_interfaces: list[RuntimeControlInterface] = Field(default_factory=list)
    process: RuntimeProcessIdentity | None = None
    processes: list[RuntimeProcessIdentity] = Field(default_factory=list)
    environment: list[RuntimeEnvironmentVariable] = Field(default_factory=list)
    linux_capabilities: RuntimeCapabilityPolicy | None = None
    operational_policy: RuntimeOperationalPolicy | None = None
    container: RuntimeContainerConfiguration | None = None
    health: RuntimeHealthObservation | None = None
    local_identity: RuntimeLocalIdentityInventory | None = None
    network: RuntimeNetworkRealization | None = None
    applications: list[RuntimeApplicationSurface] = Field(default_factory=list)
    packages: list[RuntimePackage] = Field(default_factory=list)
    dependency_manifests: list[RuntimeDependencyManifest] = Field(default_factory=list)
    package_vulnerabilities: list[RuntimePackageVulnerabilityFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_runtime_entries(self) -> "RuntimeConfiguration":
        seen_env_names: set[str] = set()
        for variable in self.environment:
            if variable.name in seen_env_names:
                raise ValueError(f"Duplicate runtime environment variable '{variable.name}'")
            seen_env_names.add(variable.name)

        seen_mount_targets: set[str] = set()
        for mount in self.mounts:
            if mount.target in seen_mount_targets:
                raise ValueError(f"Duplicate runtime mount target '{mount.target}'")
            seen_mount_targets.add(mount.target)

        seen_filesystem_paths: set[str] = set()
        for entry in self.filesystem_inventory:
            if entry.path in seen_filesystem_paths:
                raise ValueError(f"Duplicate runtime filesystem path '{entry.path}'")
            seen_filesystem_paths.add(entry.path)

        seen_process_names: set[str] = set()
        seen_process_pids: set[int | str] = set()
        for process in self.processes:
            if process.name:
                if process.name in seen_process_names:
                    raise ValueError(f"Duplicate runtime process name '{process.name}'")
                seen_process_names.add(process.name)
            if process.pid is not None:
                if process.pid in seen_process_pids:
                    raise ValueError(f"Duplicate runtime process pid '{process.pid}'")
                seen_process_pids.add(process.pid)

        seen_application_ids: set[str] = set()
        for application in self.applications:
            if application.application_id in seen_application_ids:
                raise ValueError(f"Duplicate runtime application_id '{application.application_id}'")
            seen_application_ids.add(application.application_id)
        return self
