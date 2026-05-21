"""Shared parsing helpers for SDL runtime configuration models."""

import re
from enum import Enum
from typing import Any

from ._base import (
    is_variable_ref,
    parse_bool_or_var,
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
_RAM_MIN_BYTES_ERROR = "RAM must be >= 1 byte"
_WINDOWS_NAMED_PIPE_PREFIXES = ("\\\\.\\pipe\\", "\\\\?\\pipe\\")


def absolute_path_or_var(value: str, *, field_name: str) -> str:
    if is_variable_ref(value):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if not value.startswith("/"):
        raise ValueError(f"{field_name} must be an absolute path")
    return value


def is_windows_named_pipe(value: str) -> bool:
    return isinstance(value, str) and value.lower().startswith(_WINDOWS_NAMED_PIPE_PREFIXES)


def control_interface_path_or_var(value: str, *, field_name: str) -> str:
    if is_variable_ref(value):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if value.startswith("/") or is_windows_named_pipe(value):
        return value
    raise ValueError(f"{field_name} must be an absolute path or Windows named pipe")


def parse_runtime_enum_or_var(value: Any, enum_cls: type[Enum], *, field_name: str):
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


def parse_optional_bool_or_var(value: Any, *, field_name: str) -> bool | str | None:
    return parse_bool_or_var(value, field_name=field_name) if value is not None else value


def coerce_string_list(value: Any):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return value


def validate_absolute_paths(values: list[str], *, field_name: str) -> list[str]:
    return [absolute_path_or_var(value, field_name=field_name) for value in values]


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
            raise ValueError(_RAM_MIN_BYTES_ERROR)
        return value
    value_str = str(value).strip()
    if value_str.isdigit():
        parsed = int(value_str)
        if parsed < 1:
            raise ValueError(_RAM_MIN_BYTES_ERROR)
        return parsed
    match = _RAM_PATTERN.match(value_str)
    if not match:
        raise ValueError(f"Invalid RAM value: {value_str!r}. Use a number with a unit (e.g., '4 GiB', '2048 MiB').")
    amount = float(match.group(1))
    unit = match.group(2).lower()
    parsed = int(amount * _BYTE_UNITS[unit])
    if parsed < 1:
        raise ValueError(_RAM_MIN_BYTES_ERROR)
    return parsed
