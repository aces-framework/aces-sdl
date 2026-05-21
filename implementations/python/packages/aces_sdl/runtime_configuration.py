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

_BYTE_UNITS = {
    "b": 1,
    "kb": 1_000,
    "kib": 1_024,
    "mb": 1_000_000,
    "mib": 1_048_576,
    "gb": 1_000_000_000,
    "gib": 1_073_741_824,
    "tb": 1_000_000_000_000,
    "tib": 1_099_511_627_776,
}

_RAM_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(" + "|".join(_BYTE_UNITS) + r")\s*$",
    re.IGNORECASE,
)
_WINDOWS_NAMED_PIPE_PREFIXES = ("\\\\.\\pipe\\", "\\\\?\\pipe\\")


def _absolute_path_or_var(value: str, *, field_name: str) -> str:
    if is_variable_ref(value):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if not value.startswith("/"):
        raise ValueError(f"{field_name} must be an absolute path")
    return value


def _is_windows_named_pipe(value: str) -> bool:
    return isinstance(value, str) and value.lower().startswith(_WINDOWS_NAMED_PIPE_PREFIXES)


def _control_interface_path_or_var(value: str, *, field_name: str) -> str:
    if is_variable_ref(value):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if value.startswith("/") or _is_windows_named_pipe(value):
        return value
    raise ValueError(f"{field_name} must be an absolute path or Windows named pipe")


def _parse_runtime_enum_or_var(value, enum_cls: type[Enum], *, field_name: str):
    if value is None or is_variable_ref(value):
        return value
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        normalized = value.lower().replace("-", "_")
        try:
            return enum_cls(normalized)
        except ValueError as e:
            allowed = ", ".join(member.value for member in enum_cls)
            raise ValueError(f"{field_name} must be one of: {allowed}") from e
    raise ValueError(f"{field_name} must be a string")


def parse_ram(value: str | int) -> int | str:
    """Parse a human-readable RAM string to bytes.

    Accepts bare integers (treated as bytes) or strings like
    ``"4 GiB"``, ``"2048 MiB"``, ``"512mb"``.
    """
    if is_variable_ref(value):
        return value
    if isinstance(value, bool):
        raise ValueError("RAM must be a positive integer or human-readable size")
    if isinstance(value, int):
        if value < 1:
            raise ValueError("RAM must be >= 1 byte")
        return value
    value_str = str(value).strip()
    if value_str.isdigit():
        parsed = int(value_str)
        if parsed < 1:
            raise ValueError("RAM must be >= 1 byte")
        return parsed
    match = _RAM_PATTERN.match(value_str)
    if not match:
        raise ValueError(f"Invalid RAM value: {value_str!r}. Use a number with a unit (e.g., '4 GiB', '2048 MiB').")
    amount = float(match.group(1))
    unit = match.group(2).lower()
    parsed = int(amount * _BYTE_UNITS[unit])
    if parsed < 1:
        raise ValueError("RAM must be >= 1 byte")
    return parsed


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
    SECRET_FIXTURE = "secret_fixture"  # noqa: S105 - classification label, not a credential value.
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


def _coerce_string_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return value


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
    read_only: bool | str = False
    options: list[str] = Field(default_factory=list)
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
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v

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
    local_control_interfaces: list[RuntimeControlInterface] = Field(default_factory=list)
    process: RuntimeProcessIdentity | None = None
    processes: list[RuntimeProcessIdentity] = Field(default_factory=list)
    environment: list[RuntimeEnvironmentVariable] = Field(default_factory=list)
    linux_capabilities: RuntimeCapabilityPolicy | None = None
    operational_policy: RuntimeOperationalPolicy | None = None
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
        return self
