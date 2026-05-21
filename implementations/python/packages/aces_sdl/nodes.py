"""Node models — VMs and network switches.

Ports the OCR SDL Node/VM/Switch/Resources/Role structs with
backend-agnostic Source references.
"""

from enum import Enum

from pydantic import Field, field_validator, model_validator

from ._base import (
    SDLModel,
    is_variable_ref,
    normalize_enum_value,
    parse_enum_or_var,
    parse_int_or_var,
)
from ._source import Source
from .runtime_configuration import (
    RuntimeCapabilityPolicy,
    RuntimeConfiguration,
    RuntimeContainerConfiguration,
    RuntimeControlInterface,
    RuntimeControlInterfaceAccess,
    RuntimeControlInterfaceKind,
    RuntimeDeviceMapping,
    RuntimeEnvironmentValueClassification,
    RuntimeEnvironmentVariable,
    RuntimeEnvironmentVariableProvenance,
    RuntimeExtraHost,
    RuntimeFilesystemEntry,
    RuntimeFilesystemEntryType,
    RuntimeFilesystemStability,
    RuntimeHealthcheckLog,
    RuntimeHealthObservation,
    RuntimeHealthStatus,
    RuntimeMount,
    RuntimeMountPropagation,
    RuntimeMountSourceKind,
    RuntimeNamespaceConfiguration,
    RuntimeOperationalPolicy,
    RuntimePackage,
    RuntimePackageVulnerabilityFinding,
    RuntimePackageVulnerabilitySeverity,
    RuntimeProcessIdentity,
    RuntimeProcessRole,
    RuntimeResourceLimits,
    RuntimeRestartPolicy,
    RuntimeSensitivityClassification,
    parse_ram,
)

__all__ = [
    "AssetValue",
    "AssetValueLevel",
    "MAX_NODE_NAME_LENGTH",
    "Node",
    "NodeType",
    "OSFamily",
    "Resources",
    "Role",
    "RuntimeCapabilityPolicy",
    "RuntimeContainerConfiguration",
    "RuntimeConfiguration",
    "RuntimeControlInterface",
    "RuntimeControlInterfaceAccess",
    "RuntimeControlInterfaceKind",
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
    "RuntimeMount",
    "RuntimeMountPropagation",
    "RuntimeMountSourceKind",
    "RuntimeNamespaceConfiguration",
    "RuntimeOperationalPolicy",
    "RuntimePackage",
    "RuntimePackageVulnerabilityFinding",
    "RuntimePackageVulnerabilitySeverity",
    "RuntimeProcessIdentity",
    "RuntimeProcessRole",
    "RuntimeResourceLimits",
    "RuntimeRestartPolicy",
    "RuntimeSensitivityClassification",
    "ServicePort",
    "parse_ram",
]

MAX_NODE_NAME_LENGTH = 35


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
