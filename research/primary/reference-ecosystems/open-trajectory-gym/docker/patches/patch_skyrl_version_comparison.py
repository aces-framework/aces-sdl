#!/usr/bin/env python3
"""Patch SkyRL's torch version comparison to be numeric and idempotent.

SkyRL 0.3.1 `distributed/utils.py` used:
    str(torch.__version__) >= "2.6"

This is a string comparison, so "2.10" < "2.6" lexicographically.
For torch 2.10+, this picks the wrong kwarg (`pg_options`) and breaks
_new_process_group_helper().
"""

import re


def _canonical_version_block(indent: str = "    ") -> str:
    """Return a version-parsing block that has no extra import dependencies."""
    return "\n".join(
        [
            f'{indent}_torch_ver_parts = torch.__version__.split(".")[:2]',
            f'{indent}_torch_ver_minor = "".join(ch for ch in _torch_ver_parts[1] if ch.isdigit())',
            f'{indent}_torch_ver_tuple = (int(_torch_ver_parts[0]), int(_torch_ver_minor or "0"))',
            f'{indent}pg_options_param_name = "backend_options" if _torch_ver_tuple >= (2, 6) else "pg_options"',
        ]
    )


def apply():
    try:
        import skyrl_train.distributed.utils as du

        source_file = du.__file__
    except ImportError:
        print("   skyrl_train not installed, skipping version comparison patch")
        return

    with open(source_file) as f:
        content = f.read()

    good_marker = (
        '_torch_ver_minor = "".join(ch for ch in _torch_ver_parts[1] if ch.isdigit())'
    )
    if good_marker in content:
        print("   Patch (version comparison): already applied")
        return

    old_string_compare = 'pg_options_param_name = "backend_options" if str(torch.__version__) >= "2.6" else "pg_options"'

    # Replace old string comparison directly.
    if old_string_compare in content:
        content = content.replace(old_string_compare, _canonical_version_block(), 1)
        with open(source_file, "w") as f:
            f.write(content)
        print(
            "   Patch (version comparison): applied (string compare -> numeric tuple)"
        )
        return

    # Replace older patched variant that used re.sub(...) but may miss import re.
    legacy_block = re.compile(
        r'(?m)^(?P<indent>\s*)_torch_ver_parts = torch\.__version__\.split\("\."\)\[:2\]\n'
        r'(?P=indent)_torch_ver_tuple = \(int\(_torch_ver_parts\[0\]\), int\(re\.sub\(r"\[\^0-9\]", "", _torch_ver_parts\[1\]\)\)\)\n'
        r'(?P=indent)pg_options_param_name = "backend_options" if _torch_ver_tuple >= \(2, 6\) else "pg_options"$'
    )
    m = legacy_block.search(content)
    if m:
        indent = m.group("indent")
        content = legacy_block.sub(_canonical_version_block(indent), content, count=1)
        with open(source_file, "w") as f:
            f.write(content)
        print("   Patch (version comparison): upgraded legacy tuple patch")
        return

    # If upstream changed code structure, do not fail hard.
    print("   Patch (version comparison): pattern not found, skipping")


if __name__ == "__main__":
    apply()
