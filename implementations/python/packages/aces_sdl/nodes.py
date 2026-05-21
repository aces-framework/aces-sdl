"""Node models — VMs and network switches.

Ports the OCR SDL Node/VM/Switch/Resources/Role structs with
backend-agnostic Source references.
"""

import re
from enum import Enum

from pydantic import Field, field_validator, model_validator

from ._base import (
    SDLModel,
    is_variable_ref,
    normalize_enum_value,
    parse_bool_or_var,
    parse_enum_or_var,
    parse_int_or_var,
)
from ._source import Source

MAX_NODE_NAME_LENGTH = 35

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


class NodeType(str, Enum):
    """Whether a node is a virtual machine or network switch."""

    VM = "vm"
    SWITCH = "switch"


class Resources(SDLModel):
    """Compute resources for a VM node."""

    ram: int | str = Field(description="RAM in bytes (parsed from human-readable)")
    cpu: int | str = Field(description="Number of CPU cores")

    @field_validator("ram", mode="before")
    @classmethod
    def parse_ram_value(cls, v: str | int) -> int | str:
        return parse_ram(v)

    @field_validator("cpu", mode="before")
    @classmethod
    def parse_cpu_value(cls, v: int | str) -> int | str:
        return parse_int_or_var(v, minimum=1, field_name="cpu")


class Role(SDLModel):
    """A named role on a VM with optional entity assignments.

    Shorthand: ``admin: "username"`` (just the username string).
    Longhand: ``admin: {username: "admin", entities: ["blue-team.bob"]}``.
    """

    username: str
    entities: list[str] = Field(default_factory=list)


class OSFamily(str, Enum):
    """Operating system family. Vocabulary from OCSF Device.os."""

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    FREEBSD = "freebsd"
    OTHER = "other"


class AssetValueLevel(str, Enum):
    """CIA triad value level. Adapted from CybORG ConfidentialityValue."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AssetValue(SDLModel):
    """CIA triad asset valuation for scoring and risk assessment."""

    confidentiality: AssetValueLevel | str = AssetValueLevel.MEDIUM
    integrity: AssetValueLevel | str = AssetValueLevel.MEDIUM
    availability: AssetValueLevel | str = AssetValueLevel.MEDIUM

    @field_validator(
        "confidentiality",
        "integrity",
        "availability",
        mode="before",
    )
    @classmethod
    def normalize_asset_value(
        cls,
        v: AssetValueLevel | str,
    ) -> AssetValueLevel | str:
        return parse_enum_or_var(
            v,
            AssetValueLevel,
            field_name="asset_value",
        )


class ServicePort(SDLModel):
    """A network service exposed by a node. From OCSF NetworkEndpoint."""

    port: int | str
    protocol: str = "tcp"
    name: str = ""
    description: str = ""

    @field_validator("port", mode="before")
    @classmethod
    def parse_port_value(cls, v: int | str) -> int | str:
        return parse_int_or_var(v, minimum=1, maximum=65535, field_name="port")


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

    pid: int | str | None = None
    command: list[str] = Field(default_factory=list)
    user: str = ""
    group: str = ""
    working_directory: str = ""

    @field_validator("pid", mode="before")
    @classmethod
    def parse_pid(cls, v: int | str | None) -> int | str | None:
        return parse_int_or_var(v, minimum=1, field_name="pid") if v is not None else v

    @field_validator("command", mode="before")
    @classmethod
    def normalize_command(cls, v: str | list[str] | None) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v

    @field_validator("working_directory")
    @classmethod
    def validate_working_directory(cls, v: str) -> str:
        return _absolute_path_or_var(v, field_name="working_directory") if v else v


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
    packages: list[RuntimePackage] = Field(default_factory=list)
    dependency_manifests: list[RuntimeDependencyManifest] = Field(default_factory=list)
    package_vulnerabilities: list[RuntimePackageVulnerabilityFinding] = Field(default_factory=list)


class Node(SDLModel):
    """A scenario node — either a VM or a Switch.

    The ``type`` field determines which variant is active. VM fields
    are only valid when type is VM; Switch nodes carry no extra data.
    """

    type: NodeType = Field(alias="type")
    description: str = ""
    source: Source | None = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        return normalize_enum_value(v)

    resources: Resources | None = None
    os: OSFamily | str | None = None
    os_version: str = ""
    features: dict[str, str] = Field(default_factory=dict)
    conditions: dict[str, str] = Field(default_factory=dict)
    injects: dict[str, str] = Field(default_factory=dict)
    vulnerabilities: list[str] = Field(default_factory=list)
    roles: dict[str, Role] = Field(default_factory=dict)
    services: list[ServicePort] = Field(default_factory=list)
    asset_value: AssetValue | None = None
    runtime: RuntimeConfiguration | None = None

    @field_validator("os", mode="before")
    @classmethod
    def normalize_os(cls, v):
        return parse_enum_or_var(v, OSFamily, field_name="os") if v is not None else v

    @model_validator(mode="after")
    def validate_type_constraints(self) -> "Node":
        """Switch nodes cannot carry VM-only fields."""
        if self.type != NodeType.SWITCH:
            return self

        disallowed_fields = self._populated_vm_only_fields()
        if disallowed_fields:
            raise ValueError("Switch nodes cannot have VM-only fields: " + ", ".join(disallowed_fields))
        return self

    def _populated_vm_only_fields(self) -> list[str]:
        fields = {
            "source": self.source is not None,
            "resources": self.resources is not None,
            "os": self.os is not None,
            "os_version": bool(self.os_version),
            "features": bool(self.features),
            "conditions": bool(self.conditions),
            "injects": bool(self.injects),
            "vulnerabilities": bool(self.vulnerabilities),
            "roles": bool(self.roles),
            "services": bool(self.services),
            "asset_value": self.asset_value is not None,
            "runtime": self.runtime is not None,
        }
        return [field_name for field_name, is_populated in fields.items() if is_populated]

    @model_validator(mode="after")
    def validate_unique_service_ports(self) -> "Node":
        """Concrete VM service bindings must stay uniquely addressable."""
        if self.type != NodeType.VM:
            return self

        seen: set[tuple[str, int]] = set()
        seen_names: set[str] = set()
        for service in self.services:
            if not isinstance(service.port, int):
                pass
            elif not is_variable_ref(service.protocol):
                key = (service.protocol.lower(), service.port)
                if key in seen:
                    raise ValueError(f"Duplicate service binding '{service.protocol}/{service.port}' on node")
                seen.add(key)
            if service.name:
                if service.name in seen_names:
                    raise ValueError(f"Duplicate named service '{service.name}' on node")
                seen_names.add(service.name)
        return self
