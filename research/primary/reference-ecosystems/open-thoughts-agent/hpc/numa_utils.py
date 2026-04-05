"""GPU NUMA affinity utilities for multi-socket and unified memory architectures (e.g., GH200).

On GH200 nodes, each GPU has its own NUMA node for HBM memory (e.g., nodes 4, 12, 20, 28)
which is separate from the CPU NUMA node (0, 1, 2, 3). This module detects the correct
CPU NUMA affinity for each GPU and binds the calling process accordingly.

Detection strategy (in priority order):
1. nvidia-smi topo -m (most direct, but fails under proxychains/CUDA_VISIBLE_DEVICES)
2. Pure sysfs + numactl (no nvidia-smi needed — enumerates NVIDIA PCI devices, reads
   their NUMA nodes, then maps GPU NUMA nodes to CPU NUMA nodes via distance matrix)

Activation: Set SKYRL_ENABLE_NUMA_AFFINITY=1 in the environment. When unset, all functions
are no-ops to avoid interfering with systems that don't need NUMA binding.

Ported from SkyRL (skyrl_train/utils/numa.py).
"""

import logging
import os
import re
import subprocess
from ctypes import CDLL, Structure, POINTER, c_ulong, c_char_p, c_int
from ctypes.util import find_library
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def is_numa_affinity_enabled() -> bool:
    """Check if NUMA affinity binding is enabled via environment variable."""
    return os.environ.get("SKYRL_ENABLE_NUMA_AFFINITY", "0") == "1"


def _nvidia_smi_env() -> Dict[str, str]:
    """Get environment for nvidia-smi subprocesses with CUDA_VISIBLE_DEVICES removed.

    nvidia-smi respects CUDA_VISIBLE_DEVICES on some driver versions, which remaps
    GPU indices (e.g., physical GPU 2 becomes GPU0). We need the real physical
    indices to map GPUs to their correct NUMA nodes, so we strip the variable.
    """
    env = os.environ.copy()
    env.pop("CUDA_VISIBLE_DEVICES", None)
    return env


# ---------------------------------------------------------------------------
# Method 1: nvidia-smi topo -m (fastest, but unreliable under proxychains)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _parse_nvidia_smi_topo() -> Optional[Dict[int, Tuple[List[int], int]]]:
    """Parse nvidia-smi topo -m to get GPU -> (cpu_list, numa_node) mapping.

    Returns:
        Dict mapping GPU index to (cpu_affinity_list, cpu_numa_node), or None on failure.
        Example on GH200: {0: ([0..71], 0), 1: ([72..143], 1), ...}
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "topo", "-m"],
            capture_output=True, text=True, timeout=10,
            env=_nvidia_smi_env(),
        )
        if result.returncode != 0:
            return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

    gpu_map = {}
    for line in result.stdout.splitlines():
        # Match lines starting with "GPU0", "GPU1", etc.
        match = re.match(r"^GPU(\d+)\s+", line)
        if not match:
            continue

        gpu_idx = int(match.group(1))

        # Split by whitespace — the CPU Affinity and NUMA Affinity columns
        # are the last two (or three with GPU NUMA ID) tab-separated fields.
        # Format: GPU0 <connections...> <CPU Affinity> <NUMA Affinity> [<GPU NUMA ID>]
        parts = line.split()

        # Find CPU Affinity field: looks like "0-71" or "0-71,144-215"
        cpu_affinity_str = None
        numa_node = None
        for i, part in enumerate(parts):
            if re.match(r"^\d+(-\d+)?(,\d+(-\d+)?)*$", part) and "-" in part:
                cpu_affinity_str = part
                # Next numeric field after CPU Affinity is NUMA Affinity
                if i + 1 < len(parts) and parts[i + 1].isdigit():
                    numa_node = int(parts[i + 1])
                break

        if cpu_affinity_str is not None and numa_node is not None:
            cpus = _parse_cpu_range(cpu_affinity_str)
            gpu_map[gpu_idx] = (cpus, numa_node)

    return gpu_map if gpu_map else None


def _parse_cpu_range(cpu_str: str) -> List[int]:
    """Parse CPU range string like '0-71' or '0-71,144-215' into list of CPU IDs."""
    cpus = []
    for part in cpu_str.split(","):
        if "-" in part:
            start, end = part.split("-", 1)
            cpus.extend(range(int(start), int(end) + 1))
        else:
            cpus.append(int(part))
    return cpus


# ---------------------------------------------------------------------------
# Method 2: Pure sysfs + numactl (no nvidia-smi needed)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _enumerate_gpus_from_sysfs() -> Optional[Dict[int, int]]:
    """Enumerate NVIDIA GPUs and their NUMA nodes directly from sysfs.

    Scans /sys/bus/pci/devices/ for NVIDIA GPUs (vendor 0x10de, class 0x03xxxx)
    and reads their numa_node. GPUs are ordered by PCI bus ID, matching nvidia-smi
    GPU index ordering.

    Returns:
        Dict mapping GPU index (0-based, ordered by bus ID) to NUMA node ID,
        or None on failure.
    """
    pci_base = "/sys/bus/pci/devices"
    nvidia_gpus = []
    try:
        for dev in sorted(os.listdir(pci_base)):
            dev_path = os.path.join(pci_base, dev)
            try:
                with open(os.path.join(dev_path, "vendor")) as f:
                    vendor = f.read().strip()
                with open(os.path.join(dev_path, "class")) as f:
                    dev_class = f.read().strip()
                # NVIDIA vendor = 0x10de, display/3D controller class = 0x03xxxx
                if vendor == "0x10de" and dev_class.startswith("0x03"):
                    with open(os.path.join(dev_path, "numa_node")) as f:
                        numa = int(f.read().strip())
                    nvidia_gpus.append((dev, numa))
            except (FileNotFoundError, ValueError):
                continue
    except FileNotFoundError:
        return None

    if not nvidia_gpus:
        return None

    result = {i: numa for i, (_, numa) in enumerate(nvidia_gpus)}
    logger.debug("NUMA: sysfs GPU enumeration: %s", result)
    return result


@lru_cache(maxsize=1)
def _parse_numactl_hardware() -> Optional[Dict[int, List[int]]]:
    """Parse numactl --hardware to get NUMA node -> CPU list mapping.

    Returns:
        Dict mapping NUMA node ID to list of CPU IDs (only nodes with CPUs),
        or None on failure.
    """
    try:
        result = subprocess.run(
            ["numactl", "--hardware"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

    node_cpus = {}
    for line in result.stdout.splitlines():
        # Match lines like "node 0 cpus: 0 1 2 3 ... 71"
        match = re.match(r"^node\s+(\d+)\s+cpus:\s*(.+)$", line)
        if match:
            node_id = int(match.group(1))
            cpu_str = match.group(2).strip()
            if cpu_str:
                cpus = [int(c) for c in cpu_str.split()]
                if cpus:
                    node_cpus[node_id] = cpus

    if node_cpus:
        node_summary = {k: f"{v[0]}-{v[-1]}" for k, v in sorted(node_cpus.items())}
        logger.debug("NUMA: numactl found %d nodes with CPUs: %s", len(node_cpus), node_summary)
    return node_cpus if node_cpus else None


def _find_closest_cpu_numa_node(
    gpu_numa_node: int, cpu_nodes: Dict[int, List[int]]
) -> Optional[int]:
    """Find the CPU NUMA node closest to a GPU NUMA node using the kernel distance matrix.

    On GH200, GPU NUMA nodes (4, 12, 20, 28) have no CPUs — their HBM memory lives
    there. The closest CPU NUMA node (0, 1, 2, 3) is the one on the same SoC,
    determined by reading /sys/devices/system/node/nodeN/distance.
    """
    if gpu_numa_node in cpu_nodes:
        return gpu_numa_node  # GPU NUMA node has CPUs directly

    # Read distance from gpu_numa_node to all other nodes
    dist_path = f"/sys/devices/system/node/node{gpu_numa_node}/distance"
    try:
        with open(dist_path) as f:
            distances = [int(d) for d in f.read().strip().split()]
    except (FileNotFoundError, ValueError):
        logger.debug("NUMA: could not read distance matrix for node %d", gpu_numa_node)
        return None

    # Find the CPU node with the smallest distance
    best_node = None
    best_dist = float("inf")
    for node_id in cpu_nodes:
        if node_id < len(distances) and distances[node_id] < best_dist:
            best_dist = distances[node_id]
            best_node = node_id

    if best_node is not None:
        logger.debug(
            "NUMA: GPU NUMA node %d -> closest CPU NUMA node %d (distance=%d)",
            gpu_numa_node, best_node, best_dist,
        )
    return best_node


def _get_affinity_via_sysfs_numactl(gpu_physical_id: int) -> Optional[Tuple[List[int], int]]:
    """Get GPU CPU affinity using sysfs GPU enumeration + numactl, no nvidia-smi.

    Steps:
    1. Enumerate NVIDIA GPUs from /sys/bus/pci/devices/ to get GPU -> NUMA node map
    2. Parse numactl --hardware to get NUMA node -> CPU list map
    3. If GPU's NUMA node has no CPUs (GH200 HBM node), find the closest CPU NUMA node
       via the kernel distance matrix
    """
    gpu_numa_map = _enumerate_gpus_from_sysfs()
    if not gpu_numa_map or gpu_physical_id not in gpu_numa_map:
        return None

    gpu_numa = gpu_numa_map[gpu_physical_id]

    numactl = _parse_numactl_hardware()
    if not numactl:
        return None

    # Direct match: GPU's NUMA node has CPUs
    if gpu_numa in numactl:
        return (numactl[gpu_numa], gpu_numa)

    # GH200 case: GPU NUMA node is HBM-only, find closest CPU NUMA node
    closest = _find_closest_cpu_numa_node(gpu_numa, numactl)
    if closest is not None:
        return (numactl[closest], closest)

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_gpu_cpu_affinity(gpu_physical_id: int) -> Optional[Tuple[List[int], int]]:
    """Get the optimal CPU list and NUMA node for a GPU.

    Args:
        gpu_physical_id: Physical GPU index (as seen by nvidia-smi, not CUDA logical index).

    Returns:
        Tuple of (cpu_list, numa_node) or None if detection fails.
    """
    # Method 1: nvidia-smi topo (most direct, but fails under proxychains)
    topo = _parse_nvidia_smi_topo()
    if topo and gpu_physical_id in topo:
        return topo[gpu_physical_id]

    # Method 2: sysfs + numactl (no nvidia-smi needed, handles GH200 correctly)
    result = _get_affinity_via_sysfs_numactl(gpu_physical_id)
    if result is not None:
        return result

    return None


def set_numa_affinity_for_gpu(gpu_id: int) -> None:
    """Set CPU and memory affinity for the calling process to match a GPU's NUMA node.

    This binds the process to the CPUs closest to the specified GPU and sets the
    memory allocation policy to prefer the GPU's NUMA node.

    Args:
        gpu_id: Physical GPU index.

    No-op if:
        - SKYRL_ENABLE_NUMA_AFFINITY != "1"
        - GPU NUMA topology cannot be detected
        - libnuma is not available
    """
    if not is_numa_affinity_enabled():
        return

    affinity = get_gpu_cpu_affinity(gpu_id)
    if affinity is None:
        logger.warning("NUMA affinity: could not detect topology for GPU %d", gpu_id)
        return

    cpu_list, numa_node = affinity

    # Try os.sched_setaffinity (doesn't need libnuma)
    target_cpus = set(cpu_list)
    try:
        allowed_cpus = os.sched_getaffinity(0)
    except (OSError, AttributeError):
        allowed_cpus = None

    if allowed_cpus is not None and not target_cpus.issubset(allowed_cpus):
        overlap = target_cpus & allowed_cpus
        logger.warning(
            "NUMA affinity: target CPUs %d-%d (NUMA %d) "
            "not fully within allowed cpuset %d-%d "
            "(%d CPUs). This is likely a SLURM cgroup restriction. "
            "Consider adding '--cpu-bind=none' to srun or setting "
            "'TaskPluginParam=none' in slurm.conf.",
            cpu_list[0], cpu_list[-1], numa_node,
            min(allowed_cpus), max(allowed_cpus), len(allowed_cpus),
        )
        if overlap:
            target_cpus = overlap
            logger.info(
                "NUMA affinity: falling back to %d overlapping CPUs for GPU %d",
                len(overlap), gpu_id,
            )
        else:
            logger.warning(
                "NUMA affinity: no overlap between target and allowed CPUs for GPU %d, "
                "skipping CPU binding",
                gpu_id,
            )
            return

    try:
        os.sched_setaffinity(0, target_cpus)
        logger.info(
            "NUMA affinity: bound process to CPUs %d-%d (NUMA node %d) for GPU %d",
            min(target_cpus), max(target_cpus), numa_node, gpu_id,
        )
    except (OSError, AttributeError) as e:
        logger.warning("NUMA affinity: os.sched_setaffinity failed: %s", e)
        return

    # Also set memory binding via libnuma if available
    _set_membind_via_libnuma(numa_node)


def _set_membind_via_libnuma(numa_node: int) -> None:
    """Set memory binding policy to prefer the specified NUMA node using libnuma."""
    try:
        libnuma = CDLL(find_library("numa"))
    except (OSError, TypeError):
        # libnuma not installed — CPU affinity is already set, memory binding is optional
        return

    class bitmask_t(Structure):
        _fields_ = [
            ("size", c_ulong),
            ("maskp", POINTER(c_ulong)),
        ]

    try:
        libnuma.numa_parse_nodestring.argtypes = [c_char_p]
        libnuma.numa_parse_nodestring.restype = POINTER(bitmask_t)
        libnuma.numa_set_preferred.argtypes = [c_int]
        libnuma.numa_set_preferred.restype = None

        # Use numa_set_preferred (soft) instead of numa_set_membind (hard)
        # to avoid OOM when the local NUMA node is full
        libnuma.numa_set_preferred(c_int(numa_node))
        logger.debug("NUMA affinity: set memory preferred to NUMA node %d", numa_node)
    except Exception as e:
        logger.debug("NUMA affinity: libnuma membind failed: %s", e)


def apply_numa_affinity(gpu_id: int = 0) -> None:
    """Safe wrapper around set_numa_affinity_for_gpu for use in startup code.

    Catches all exceptions to avoid aborting the process if NUMA detection
    fails for any reason. Logs the outcome at INFO level.

    Args:
        gpu_id: Physical GPU index (default: 0 for head/controller processes).
    """
    if not is_numa_affinity_enabled():
        return

    try:
        set_numa_affinity_for_gpu(gpu_id)
    except Exception as e:
        logger.warning("NUMA affinity: unexpected error during setup: %s", e)
