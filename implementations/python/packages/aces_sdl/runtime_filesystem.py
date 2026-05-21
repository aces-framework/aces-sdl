"""Observed runtime filesystem inventory models for SDL nodes."""

import re
from enum import Enum

from pydantic import ValidationInfo, field_validator, model_validator

from ._base import SDLModel, is_variable_ref, parse_int_or_var
from .runtime_values import absolute_path_or_var, parse_runtime_enum_or_var


class RuntimeMountPropagation(str, Enum):
    """Portable propagation mode for a runtime filesystem mount."""

    PRIVATE = "private"
    RPRIVATE = "rprivate"
    SHARED = "shared"
    RSHARED = "rshared"
    SLAVE = "slave"
    RSLAVE = "rslave"
    UNKNOWN = "unknown"
    OTHER = "other"


class RuntimeFilesystemEntryType(str, Enum):
    """Observed type of a runtime filesystem inventory entry."""

    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    DEVICE = "device"
    SOCKET = "socket"
    FIFO = "fifo"
    OTHER = "other"


class RuntimeFilesystemStability(str, Enum):
    """Stability class for an observed runtime filesystem or mount fact."""

    STABLE = "stable"
    GENERATED = "generated"
    LOG = "log"
    CACHE = "cache"
    RUNTIME_CREATED = "runtime_created"
    VOLUME_BACKED = "volume_backed"
    TRANSIENT = "transient"
    UNKNOWN = "unknown"
    OTHER = "other"


class RuntimeSensitivityClassification(str, Enum):
    """Sensitivity/redaction class for observed runtime facts."""

    PLAIN = "plain"
    REDACTED = "redacted"
    SECRET_FIXTURE = "secret_fixture"  # noqa: S105
    OPERATOR_SECRET = "operator_secret"  # noqa: S105
    UNKNOWN = "unknown"


class RuntimeFilesystemEntry(SDLModel):
    """A filesystem entry observed inside a runtime node or container asset."""

    path: str
    entry_type: RuntimeFilesystemEntryType | str = RuntimeFilesystemEntryType.OTHER
    owner_user: str = ""
    owner_group: str = ""
    uid: int | str | None = None
    gid: int | str | None = None
    mode: str = ""
    size: int | str | None = None
    content_digest: str = ""
    digest_algorithm: str = ""
    source_path: str = ""
    provenance: str = ""
    stability: RuntimeFilesystemStability | str = RuntimeFilesystemStability.UNKNOWN
    sensitivity: RuntimeSensitivityClassification | str = RuntimeSensitivityClassification.UNKNOWN
    description: str = ""

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        return absolute_path_or_var(v, field_name="path")

    @field_validator("entry_type", mode="before")
    @classmethod
    def normalize_entry_type(cls, v: RuntimeFilesystemEntryType | str) -> RuntimeFilesystemEntryType | str:
        return parse_runtime_enum_or_var(v, RuntimeFilesystemEntryType, field_name="entry_type")

    @field_validator("uid", "gid", mode="before")
    @classmethod
    def parse_identity_id(cls, v: int | str | None, info: ValidationInfo) -> int | str | None:
        return parse_int_or_var(v, minimum=0, field_name=info.field_name) if v is not None else v

    @field_validator("mode", mode="before")
    @classmethod
    def validate_mode(cls, v: str | int) -> str:
        if v is None or v == "" or is_variable_ref(v):
            return v
        if isinstance(v, bool):
            raise ValueError("mode must be octal permission bits")
        if isinstance(v, int):
            if 0 <= v <= 0o7777:
                return f"{v:04o}"
            raise ValueError("mode must be octal permission bits")
        text = str(v).strip()
        if re.fullmatch(r"(0o)?[0-7]{3,4}", text):
            return text
        raise ValueError("mode must be octal permission bits")

    @field_validator("size", mode="before")
    @classmethod
    def parse_size(cls, v: int | str | None) -> int | str | None:
        return parse_int_or_var(v, minimum=0, field_name="size") if v is not None else v

    @field_validator("stability", mode="before")
    @classmethod
    def normalize_stability(cls, v: RuntimeFilesystemStability | str) -> RuntimeFilesystemStability | str:
        return parse_runtime_enum_or_var(v, RuntimeFilesystemStability, field_name="stability")

    @field_validator("sensitivity", mode="before")
    @classmethod
    def normalize_sensitivity(
        cls,
        v: RuntimeSensitivityClassification | str,
    ) -> RuntimeSensitivityClassification | str:
        return parse_runtime_enum_or_var(v, RuntimeSensitivityClassification, field_name="sensitivity")

    @model_validator(mode="after")
    def validate_digest_pair(self) -> "RuntimeFilesystemEntry":
        if self.content_digest and not self.digest_algorithm:
            raise ValueError("content_digest requires digest_algorithm")
        if self.digest_algorithm and not self.content_digest:
            raise ValueError("digest_algorithm requires content_digest")
        return self
