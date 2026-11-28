# -*- coding: utf-8 -*-
"""System information retrieval module."""

from __future__ import annotations

import logging
import os
import pathlib
import platform
from typing import Any, Dict, Optional

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)


def get_system_info() -> Dict[str, Any]:
    """Get system information.

    Returns:
        A dictionary containing system information, including:
        - os: Operating system name
        - os_version: Operating system version
        - platform: Platform information
        - architecture: System architecture
        - cpu_count: Number of CPU cores
        - cpu_percent: CPU usage (percentage)
        - memory_total: Total memory (GB)
        - memory_available: Available memory (GB)
        - memory_percent: Memory usage (percentage)
        - disk_total: Total disk space (GB)
        - disk_available: Available disk space (GB)
        - disk_percent: Disk usage (percentage)
    """
    info: Dict[str, Any] = {}

    try:
        # Basic system information (does not depend on psutil)
        info["os"] = platform.system()
        info["os_version"] = platform.version()
        info["platform"] = platform.platform()
        info["architecture"] = platform.machine()

        if PSUTIL_AVAILABLE:
            # CPU information
            info["cpu_count"] = psutil.cpu_count(logical=True)
            # CPU usage (non-blocking mode, returns the average since the last call)
            info["cpu_percent"] = psutil.cpu_percent(interval=None)

            # Memory information
            memory = psutil.virtual_memory()
            info["memory_total"] = round(memory.total / (1024**3), 2)  # GB
            info["memory_available"] = round(memory.available / (1024**3), 2)  # GB
            info["memory_percent"] = memory.percent

            # Disk information (dynamically obtain the system disk)
            try:
                partitions = psutil.disk_partitions(all=False)
                for part in partitions:
                    if part.mountpoint == "/" or (
                        platform.system() == "Windows"
                        and part.device.startswith(("C:", "\\\\?\\\\C:"))
                    ):
                        disk = psutil.disk_usage(part.mountpoint)
                        info["disk_total"] = round(disk.total / (1024**3), 2)  # GB
                        info["disk_available"] = round(disk.free / (1024**3), 2)  # GB
                        info["disk_percent"] = disk.percent
                        break
                else:
                    logger.warning("Could not find system disk partition")
            except Exception as e:
                logger.error(f"Failed to get disk usage: {e}")
        else:
            logger.warning("psutil not available, limited system info")
            info["cpu_count"] = None
            info["cpu_percent"] = None
            info["memory_total"] = None
            info["memory_available"] = None
            info["memory_percent"] = None
            info["disk_total"] = None
            info["disk_available"] = None
            info["disk_percent"] = None
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")

    return info


MAX_DESCRIPTION_SIZE = 10 * 1024  # 10KB


def get_node_description(data_dir: Optional[str] = None) -> str:
    """Get the node description.

    Reads the node description from the gateway/node_description.md file under the data directory.
    If the file does not exist, returns an empty string.
    Truncates and logs a warning when the size limit is exceeded.

    Args:
        data_dir: Data directory path, defaults to ~/.haijunbot

    Returns:
        Node description text
    """
    try:
        if data_dir is None:
            data_dir = os.path.expanduser("~/.haijunbot")

        description_file = pathlib.Path(data_dir) / "gateway" / "node_description.md"

        if description_file.exists():
            content = description_file.read_text(encoding="utf-8")
            if len(content) > MAX_DESCRIPTION_SIZE:
                logger.warning(
                    f"Node description file too large ({len(content)} bytes), truncating to {MAX_DESCRIPTION_SIZE} bytes"
                )
                content = content[:MAX_DESCRIPTION_SIZE]
            return content.strip()
    except Exception as e:
        logger.error(f"Failed to read node description: {e}")

    return ""
