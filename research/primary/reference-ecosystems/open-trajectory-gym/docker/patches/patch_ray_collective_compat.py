#!/usr/bin/env python3
"""Create ray.experimental.collective.util shim for Ray 2.54+ compatibility.

Ray 2.54 removed the ray.experimental.collective module that SkyRL 0.3.1 uses
for get_address_and_port(). This creates a minimal shim that provides the
function using standard socket operations.
"""
import pathlib
import sys


def main():
    # Find ray installation
    try:
        import ray

        ray_dir = pathlib.Path(ray.__file__).parent
    except ImportError:
        print("   Patch (ray collective compat): SKIP - ray not installed")
        return

    # Check if the module already exists (older Ray version or already patched)
    util_path = ray_dir / "experimental" / "collective" / "util.py"
    if util_path.exists():
        try:
            from ray.experimental.collective.util import get_address_and_port

            print("   Patch (ray collective compat): SKIP - module already exists")
            return
        except ImportError:
            pass  # File exists but broken, overwrite

    # Create directory structure
    collective_dir = ray_dir / "experimental" / "collective"
    collective_dir.mkdir(parents=True, exist_ok=True)

    # Ensure __init__.py files exist
    exp_init = ray_dir / "experimental" / "__init__.py"
    if not exp_init.exists():
        exp_init.write_text("")
    coll_init = collective_dir / "__init__.py"
    if not coll_init.exists():
        coll_init.write_text("")

    # Create util.py with get_address_and_port
    util_code = '''"""Compatibility shim for ray.experimental.collective.util (removed in Ray 2.54+).

Provides get_address_and_port() using standard socket operations.
"""
import socket


def get_address_and_port():
    """Get the node IP address and a free port for rendezvous."""
    hostname = socket.gethostname()
    try:
        address = socket.gethostbyname(hostname)
    except socket.gaierror:
        address = "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]
    return address, port
'''
    util_path.write_text(util_code)

    # Verify
    # Force reimport by clearing cached modules
    for mod_name in list(sys.modules.keys()):
        if "ray.experimental.collective" in mod_name:
            del sys.modules[mod_name]

    from ray.experimental.collective.util import get_address_and_port

    addr, port = get_address_and_port()
    print(f"   Patch (ray collective compat): APPLIED (verified: {addr}:{port})")


if __name__ == "__main__":
    main()
