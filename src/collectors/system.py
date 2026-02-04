"""System information collector."""

import datetime
import json
import os
import platform
import socket
import subprocess
import threading
import time
from datetime import timedelta
from typing import Any, Dict, Optional

import psutil

from const import DISK_CACHE_FILE, DISK_HIERARCHY_CACHE_FILE, PACKAGE_STATS_CACHE_FILE, SERVICE_STATS_CACHE_FILE
from utils.binaries import APT, DPKG_QUERY, LSBLK, SMARTCTL, SUDO, SYSTEMCTL
from utils.logger import get_logger
from utils.process_cache import get_process_stats

from .base import BaseCollector

logger = get_logger(__name__)


class SystemCollector(BaseCollector):
    """Collects system information (CPU, RAM, disk, uptime, OS info)."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._last_disk_io = {}
        self._last_io_time = time.time()

        # Package stats collection (non-blocking)
        self._pkg_cache: Dict[str, Any] = {}
        self._pkg_cache_time: float = 0
        self._pkg_update_lock = threading.Lock()
        self._pkg_update_in_progress = False
        self._pkg_persistent_cache: Dict[str, Any] = self._load_package_cache()

        # Service stats collection (non-blocking)
        self._service_cache: Dict[str, int] = {}
        self._service_cache_time: float = 0
        self._service_update_lock = threading.Lock()
        self._service_update_in_progress = False
        self._service_persistent_cache: Dict[str, int] = self._load_service_cache()

        # Disk hierarchy collection (non-blocking)
        self._disk_hierarchy_cache: list = []
        self._disk_hierarchy_cache_time: float = 0
        self._disk_hierarchy_update_lock = threading.Lock()
        self._disk_hierarchy_update_in_progress = False
        self._disk_hierarchy_persistent_cache: list = self._load_disk_hierarchy_cache()

        # SMART data collection (non-blocking)
        self._smart_cache: Dict[str, Any] = {}
        self._smart_cache_time: float = 0
        self._smart_update_lock = threading.Lock()
        self._smart_update_in_progress = False
        self._smart_disk_cache: Dict[str, Dict[str, Any]] = self._load_smart_disk_cache()

        # Initialize CPU percent counters
        psutil.cpu_percent(interval=0, percpu=True)
        psutil.cpu_percent(interval=0)

    def collect(self) -> Dict[str, Any]:
        """
        Collect system information.

        Returns:
            Dictionary with system data
        """
        return {
            "timestamp": datetime.datetime.now().strftime("%a %d %b %Y %H:%M:%S"),
            "os": self._get_os_info(),
            "cpu": self._get_cpu_info(),
            "memory": self._get_memory_info(),
            "disk": self._get_disk_info(),
            "uptime": self._get_uptime(),
            "hostname": platform.node(),
            "network": self._get_primary_ip(),
            "users": self._get_users_count(),
            "processes": self._get_process_stats(),
            "services_stats": self._get_service_stats(),
            "packages": self._get_package_stats(),
        }

    def collect_progressive(self) -> list:
        """
        Collect system information progressively (yields chunks as they become available).

        Returns:
            List of tuples (data_type, data) where data_type identifies what was collected.
            Yields fast data first (OS, hostname, uptime) before slower data.
        """
        timestamp = datetime.datetime.now().strftime("%a %d %b %Y %H:%M:%S")
        result = []

        # Phase 1: Instant data (no system calls needed or cached)
        result.append(("timestamp", timestamp))
        result.append(("os", self._get_os_info()))
        result.append(("hostname", platform.node()))
        result.append(("uptime", self._get_uptime()))
        result.append(("network", self._get_primary_ip()))
        result.append(("users", self._get_users_count()))

        # Phase 2: Fast data (usually <100ms)
        result.append(("cpu", self._get_cpu_info()))
        result.append(("memory", self._get_memory_info()))
        result.append(("processes", self._get_process_stats()))

        # Phase 3: Cached/background data (returns immediately if cached)
        result.append(("services_stats", self._get_service_stats()))
        result.append(("packages", self._get_package_stats()))

        # Phase 4: Slower disk data (may take time but uses cached hierarchy)
        result.append(("disk", self._get_disk_info()))

        return result

    def _get_package_stats(self) -> Dict[str, Any]:
        """Get package stats (non-blocking). Triggers background update if stale.

        Returns cached data from persistent storage if in-memory cache is empty.
        This allows showing package counts immediately on startup.
        """
        now = time.time()
        cache_age = now - self._pkg_cache_time

        # If cache is stale (>30 min), trigger background update
        if cache_age > 1800:
            self._trigger_package_update_background()

        # If in-memory cache is empty, try to use persistent cache
        if not self._pkg_cache and self._pkg_persistent_cache:
            return self._pkg_persistent_cache

        # Return cached data or empty defaults
        return self._pkg_cache or {"total": 0, "updates": 0, "upgradable_list": [], "all_packages": []}

    def _trigger_package_update_background(self) -> None:
        """Start background package data collection if not already running."""
        with self._pkg_update_lock:
            if self._pkg_update_in_progress:
                return
            self._pkg_update_in_progress = True

        # Run in background thread
        thread = threading.Thread(target=self._update_package_stats_background, daemon=True)
        thread.start()

    def _update_package_stats_background(self) -> None:
        """Background worker for package stats collection."""
        try:
            logger.debug("Starting background package stats collection")
            start_time = time.time()

            data = self._collect_package_stats()

            # Update cache atomically
            self._pkg_cache = data
            self._pkg_cache_time = time.time()

            # Persist package cache for faster startup next time
            self._save_package_cache()

            duration = time.time() - start_time
            logger.debug(f"Package stats collection completed in {duration:.1f}s")

        except Exception as e:
            logger.error(f"Background package collection failed: {e}")
        finally:
            with self._pkg_update_lock:
                self._pkg_update_in_progress = False

    def _load_package_cache(self) -> Dict[str, Any]:
        """Load package cache from persistent storage."""
        if not os.path.exists(PACKAGE_STATS_CACHE_FILE):
            return {}

        try:
            with open(PACKAGE_STATS_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.debug(f"Loaded package cache with {data.get('total', 0)} packages")
            return data

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load package cache: {e}")
            return {}

    def _save_package_cache(self) -> None:
        """Save package cache to persistent storage (atomic write)."""
        try:
            # Ensure cache directory exists
            cache_dir = os.path.dirname(PACKAGE_STATS_CACHE_FILE)
            os.makedirs(cache_dir, exist_ok=True)

            tmp_path = PACKAGE_STATS_CACHE_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._pkg_cache, f, indent=2)
            os.replace(tmp_path, PACKAGE_STATS_CACHE_FILE)
            logger.debug("Saved package cache")
        except (IOError, OSError) as e:
            logger.warning(f"Failed to save package cache: {e}")

    def _collect_package_stats(self) -> Dict[str, Any]:
        """Collect package statistics (blocking operation, run in background thread)."""
        total = 0
        updates = 0
        upgradable_list = []
        all_packages = []

        try:
            # 1. Get all installed packages (fast)
            res_total = subprocess.run(
                [DPKG_QUERY, "-W", "-f=${Package} ${Version}\n"], capture_output=True, text=True, timeout=5
            )
            if res_total.returncode == 0:
                lines = res_total.stdout.splitlines()
                total = len(lines)
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        all_packages.append(
                            {"name": parts[0], "current_version": parts[1], "new_version": "-"}  # No update available
                        )

            # 2. Get list of upgradable packages using apt list --upgradable
            res_list = subprocess.run([APT, "list", "--upgradable"], capture_output=True, text=True, timeout=10)

            if res_list.returncode == 0:
                lines = res_list.stdout.splitlines()
                upgradable_names = []

                for line in lines:
                    if "..." in line or not line.strip():
                        continue

                    # Format: package/release series version arch ...
                    try:
                        parts = line.split("/")
                        if len(parts) > 1:
                            pkg_name = parts[0]

                            # Extract new version (second word)
                            rest = line.split()
                            new_ver = rest[1] if len(rest) > 1 else "?"

                            upgradable_list.append(
                                {"name": pkg_name, "new_version": new_ver, "current_version": "?"}  # Placeholder
                            )
                            upgradable_names.append(pkg_name)
                    except (IndexError, ValueError):
                        pass

                # Enhance with current versions using dpkg-query (reliable)
                if upgradable_names:
                    # Get current versions for these packages
                    # dpkg-query -W -f='${Package} ${Version}\n' [names...]
                    # But command line might be too long. Let's use the all_packages map we already have!

                    # We already fetched all_packages in step 1. Let's use it.
                    installed_map = {p["name"]: p["current_version"] for p in all_packages}

                    for pkg in upgradable_list:
                        name = pkg["name"]
                        if name in installed_map:
                            pkg["current_version"] = installed_map[name]

                updates = len(upgradable_list)

            # Update all_packages with upgradable info
            # Create a dict for faster lookup
            upgradable_map = {p["name"]: p for p in upgradable_list}

            # Mark updates in all_packages
            for p in all_packages:
                if p["name"] in upgradable_map:
                    p["new_version"] = upgradable_map[p["name"]]["new_version"]
                    p["upgradable"] = True
                else:
                    p["upgradable"] = False

            # Fallbacks for count if list failed
            if updates == 0 and not upgradable_list:
                # Try apt-check
                apt_check_path = "/usr/lib/update-notifier/apt-check"
                if os.path.exists(apt_check_path):
                    res_upd = subprocess.run([apt_check_path], capture_output=True, text=True, timeout=10)
                    if res_upd.returncode == 0:
                        parts = res_upd.stderr.strip().split(";")
                        if len(parts) >= 1:
                            updates = int(parts[0])
        except Exception:
            pass

        return {"total": total, "updates": updates, "upgradable_list": upgradable_list, "all_packages": all_packages}

    def _get_service_stats(self) -> Dict[str, int]:
        """Get service stats (non-blocking). Triggers background update if stale.

        Returns cached data from persistent storage if in-memory cache is empty.
        This allows showing service counts immediately on startup.
        """
        now = time.time()
        cache_age = now - self._service_cache_time

        # If cache is stale (>60 sec), trigger background update
        if cache_age > 60:
            self._trigger_service_update_background()

        # If in-memory cache is empty, try to use persistent cache
        if not self._service_cache and self._service_persistent_cache:
            return self._service_persistent_cache

        # Return cached data or empty defaults
        return self._service_cache or {"failed": 0, "active": 0}

    def _trigger_service_update_background(self) -> None:
        """Start background service stats collection if not already running."""
        with self._service_update_lock:
            if self._service_update_in_progress:
                return
            self._service_update_in_progress = True

        # Run in background thread
        thread = threading.Thread(target=self._update_service_stats_background, daemon=True)
        thread.start()

    def _update_service_stats_background(self) -> None:
        """Background worker for service stats collection."""
        try:
            logger.debug("Starting background service stats collection")
            start_time = time.time()

            data = self._collect_service_stats()

            # Update cache atomically
            self._service_cache = data
            self._service_cache_time = time.time()

            # Persist service cache for faster startup next time
            self._save_service_cache()

            duration = time.time() - start_time
            logger.debug(f"Service stats collection completed in {duration:.1f}s")

        except Exception as e:
            logger.error(f"Background service collection failed: {e}")
        finally:
            with self._service_update_lock:
                self._service_update_in_progress = False

    def _load_service_cache(self) -> Dict[str, int]:
        """Load service cache from persistent storage."""
        if not os.path.exists(SERVICE_STATS_CACHE_FILE):
            return {}

        try:
            with open(SERVICE_STATS_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.debug(f"Loaded service cache with {data.get('active', 0)} active services")
            return data

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load service cache: {e}")
            return {}

    def _save_service_cache(self) -> None:
        """Save service cache to persistent storage (atomic write)."""
        try:
            # Ensure cache directory exists
            cache_dir = os.path.dirname(SERVICE_STATS_CACHE_FILE)
            os.makedirs(cache_dir, exist_ok=True)

            tmp_path = SERVICE_STATS_CACHE_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._service_cache, f, indent=2)
            os.replace(tmp_path, SERVICE_STATS_CACHE_FILE)
            logger.debug("Saved service cache")
        except (IOError, OSError) as e:
            logger.warning(f"Failed to save service cache: {e}")

    def _collect_service_stats(self) -> Dict[str, int]:
        """Collect service statistics (blocking operation, run in background thread).

        Uses single systemctl call with --all flag and counts statuses in Python.
        Output format: UNIT LOAD ACTIVE SUB DESCRIPTION
        """
        failed = 0
        active = 0
        try:
            result = subprocess.run(
                [SYSTEMCTL, "list-units", "--type=service", "--no-legend", "--all"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 3:
                        # Column 3 is ACTIVE state: active, inactive, failed, etc.
                        state = parts[2]
                        if state == "failed":
                            failed += 1
                        elif state == "active":
                            active += 1
        except Exception:
            pass

        return {"failed": failed, "active": active}

    def _get_os_info(self) -> Dict[str, str]:
        """Get OS information."""
        os_info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }

        # Try to get a pretty name (e.g. "Ubuntu 24.04.1 LTS")
        pretty_name = f"{os_info['system']} {os_info['release']}"
        try:
            # freedesktop_os_release is available in Python 3.10+
            if hasattr(platform, "freedesktop_os_release"):
                release_info = platform.freedesktop_os_release()
                pretty_name = release_info.get("PRETTY_NAME", pretty_name)
            else:
                # Fallback for older python or non-freedesktop systems
                if os.path.exists("/etc/os-release"):
                    with open("/etc/os-release") as f:
                        for line in f:
                            if line.startswith("PRETTY_NAME="):
                                pretty_name = line.split("=")[1].strip().strip('"')
                                break
        except Exception:
            pass

        os_info["pretty_name"] = pretty_name
        return os_info

    def _get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information."""
        cpu_freq = psutil.cpu_freq()

        # Try to get temperature
        temp = 0.0
        try:
            temps = psutil.sensors_temperatures()
            # Common names for CPU temp
            for name in ["coretemp", "cpu_thermal", "k10temp", "zenpower"]:
                if name in temps:
                    # Average of all cores or just the first input
                    entries = temps[name]
                    if entries:
                        temp = entries[0].current
                        break
        except (AttributeError, KeyError, OSError, IOError):
            pass

        return {
            "physical_cores": psutil.cpu_count(logical=False),
            "total_cores": psutil.cpu_count(logical=True),
            "frequency": {
                "current": round(cpu_freq.current, 2) if cpu_freq else 0,
                "min": round(cpu_freq.min, 2) if cpu_freq else 0,
                "max": round(cpu_freq.max, 2) if cpu_freq else 0,
            },
            # Use interval=0 for non-blocking calls (first call returns 0)
            "usage_per_core": [round(x, 1) for x in psutil.cpu_percent(interval=0, percpu=True)],
            "usage_total": round(psutil.cpu_percent(interval=0), 1),
            "temperature": temp,
        }

    def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory information."""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": round(mem.percent, 1),
            "swap": {
                "total": swap.total,
                "used": swap.used,
                "free": swap.free,
                "percent": round(swap.percent, 1),
            },
        }

    def _get_disk_info(self) -> Dict[str, Any]:
        """Get disk information with full hierarchy like lsblk (disk → part → lvm).

        Triggers background update of hierarchy if cache is stale.
        Returns cached hierarchy immediately while background update runs.
        """
        now = time.time()
        cache_age = now - self._disk_hierarchy_cache_time

        # If cache is stale (>5 min), trigger background update
        if cache_age > 300:
            self._trigger_disk_hierarchy_update_background()

        # Get hierarchy: use in-memory cache if available, fallback to persistent, then parse
        if self._disk_hierarchy_cache:
            hierarchy = self._disk_hierarchy_cache
        elif self._disk_hierarchy_persistent_cache:
            hierarchy = self._disk_hierarchy_persistent_cache
        else:
            # No cache available, collect synchronously (first startup)
            mountpoints = self._get_mountpoints()
            smart_cache = self._get_smart_cache()
            hierarchy = self._parse_disk_hierarchy(mountpoints, smart_cache)

        hierarchy_copy = list(hierarchy)
        hierarchy_copy.sort(key=lambda d: (0 if d["name"].startswith("nvme") else 1, d["name"]))

        return {
            "hierarchy": hierarchy_copy,
            "partitions": self._build_partitions_list(hierarchy_copy),
            "io": self._get_io_stats(),
        }

    def _trigger_disk_hierarchy_update_background(self) -> None:
        """Start background disk hierarchy collection if not already running."""
        with self._disk_hierarchy_update_lock:
            if self._disk_hierarchy_update_in_progress:
                return
            self._disk_hierarchy_update_in_progress = True

        # Run in background thread
        thread = threading.Thread(target=self._update_disk_hierarchy_background, daemon=True)
        thread.start()

    def _update_disk_hierarchy_background(self) -> None:
        """Background worker for disk hierarchy collection."""
        try:
            logger.debug("Starting background disk hierarchy collection")
            start_time = time.time()

            mountpoints = self._get_mountpoints()
            smart_cache = self._get_smart_cache()
            hierarchy = self._parse_disk_hierarchy(mountpoints, smart_cache)

            # Update cache atomically
            self._disk_hierarchy_cache = hierarchy
            self._disk_hierarchy_cache_time = time.time()

            # Persist disk hierarchy cache for faster startup next time
            self._save_disk_hierarchy_cache()

            duration = time.time() - start_time
            logger.debug(f"Disk hierarchy collection completed in {duration:.1f}s for {len(hierarchy)} disks")

        except Exception as e:
            logger.error(f"Background disk hierarchy collection failed: {e}")
        finally:
            with self._disk_hierarchy_update_lock:
                self._disk_hierarchy_update_in_progress = False

    def _load_disk_hierarchy_cache(self) -> list:
        """Load disk hierarchy cache from persistent storage."""
        if not os.path.exists(DISK_HIERARCHY_CACHE_FILE):
            return []

        try:
            with open(DISK_HIERARCHY_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.debug(f"Loaded disk hierarchy cache for {len(data)} disks")
            return data

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load disk hierarchy cache: {e}")
            return []

    def _save_disk_hierarchy_cache(self) -> None:
        """Save disk hierarchy cache to persistent storage (atomic write)."""
        try:
            # Ensure cache directory exists
            cache_dir = os.path.dirname(DISK_HIERARCHY_CACHE_FILE)
            os.makedirs(cache_dir, exist_ok=True)

            tmp_path = DISK_HIERARCHY_CACHE_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._disk_hierarchy_cache, f, indent=2)
            os.replace(tmp_path, DISK_HIERARCHY_CACHE_FILE)
            logger.debug(f"Saved disk hierarchy cache for {len(self._disk_hierarchy_cache)} disks")
        except (IOError, OSError) as e:
            logger.warning(f"Failed to save disk hierarchy cache: {e}")

    def _get_mountpoints(self) -> Dict[str, list]:
        """Get mountpoints and filesystem types from psutil."""
        mountpoints = {}
        for partition in psutil.disk_partitions(all=False):
            if "/snap/" in partition.mountpoint or "/loop" in partition.device:
                continue
            dev = partition.device
            if dev not in mountpoints:
                mountpoints[dev] = []
            mountpoints[dev].append(
                {
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                }
            )
        return mountpoints

    def _get_disk_usage(self, mountpoint: str) -> Dict[str, Any] | None:
        """Get disk usage for a mountpoint."""
        try:
            usage = psutil.disk_usage(mountpoint)
            return {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": round(usage.percent, 1),
            }
        except (PermissionError, OSError, FileNotFoundError):
            return None

    def _get_smart_cache(self) -> Dict[str, Any]:
        """Get SMART cache (non-blocking). Triggers background update if stale.

        Returns cached data from persistent storage if in-memory cache is empty.
        This allows showing temperatures immediately on startup.
        """
        cache_age = time.time() - self._smart_cache_time

        # If cache is stale (>5 min), trigger background update
        if cache_age > 300:
            self._trigger_smart_update_background()

        # If in-memory cache is empty, try to use persistent cache
        if not self._smart_cache and self._smart_disk_cache:
            return {
                disk: {
                    "status": info.get("smart_status", "N/A"),
                    "temperature": info.get("last_temperature"),
                    "from_cache": True,
                }
                for disk, info in self._smart_disk_cache.items()
                if info.get("smart_supported", True)
            }

        return self._smart_cache

    def _trigger_smart_update_background(self) -> None:
        """Start background SMART data collection if not already running."""
        with self._smart_update_lock:
            if self._smart_update_in_progress:
                return
            self._smart_update_in_progress = True

        # Run in background thread
        thread = threading.Thread(target=self._update_smart_background, daemon=True)
        thread.start()

    def _update_smart_background(self) -> None:
        """Background worker for SMART data collection."""
        try:
            logger.debug("Starting background SMART data collection")
            start_time = time.time()

            disk_info_map = self._get_disk_list_for_smart()
            smart_data = self._get_smart_info(disk_info_map)

            # Update cache atomically
            self._smart_cache = smart_data
            self._smart_cache_time = time.time()

            # Persist SMART disk cache for faster startup next time
            self._save_smart_disk_cache()

            duration = time.time() - start_time
            logger.debug(f"SMART data collection completed in {duration:.1f}s for {len(smart_data)} disks")

        except Exception as e:
            logger.error(f"Background SMART collection failed: {e}")
        finally:
            with self._smart_update_lock:
                self._smart_update_in_progress = False

    def _load_smart_disk_cache(self) -> Dict[str, Dict[str, Any]]:
        """Load disk cache from persistent storage.

        Supports migration from old formats.
        """
        # Try new location first, then old
        cache_file = DISK_CACHE_FILE
        old_cache_file = str(DISK_CACHE_FILE).replace("disk_cache.json", "smart_device_types.json")

        if not os.path.exists(cache_file):
            if os.path.exists(old_cache_file):
                cache_file = old_cache_file
                logger.info("Migrating from old cache file location")
            else:
                return {}

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Migrate old format: {"disk": "type"} -> {"disk": {"device_type": "type", ...}}
            if data and isinstance(next(iter(data.values()), None), (str, type(None))):
                logger.info("Migrating disk cache from old format")
                data = {disk: {"device_type": dtype} for disk, dtype in data.items()}

            # Save to new location if migrated
            if cache_file != DISK_CACHE_FILE:
                self._smart_disk_cache = data
                self._save_smart_disk_cache()
                try:
                    os.remove(old_cache_file)
                except OSError:
                    pass

            logger.debug(f"Loaded disk cache for {len(data)} disks")
            return data

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load disk cache: {e}")
            return {}

    def _save_smart_disk_cache(self) -> None:
        """Save disk cache to persistent storage (atomic write)."""
        try:
            tmp_path = DISK_CACHE_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._smart_disk_cache, f, indent=2)
            os.replace(tmp_path, DISK_CACHE_FILE)
            logger.debug(f"Saved disk cache for {len(self._smart_disk_cache)} disks")
        except (IOError, OSError) as e:
            logger.warning(f"Failed to save disk cache: {e}")

    def _get_cached_smart_data(self, disk_name: str) -> Optional[Dict[str, Any]]:
        """Get cached SMART data for instant display at startup."""
        cache_entry = self._smart_disk_cache.get(disk_name)
        if not cache_entry:
            return None

        return {
            "status": cache_entry.get("smart_status", "N/A"),
            "temperature": cache_entry.get("last_temperature"),
            "from_cache": True,
        }

    def _get_disk_list_for_smart(self) -> Dict[str, Any]:
        """Get list of physical disks for SMART queries with extended info."""
        disk_info_map = {}
        try:
            result = subprocess.run(
                [LSBLK, "-o", "NAME,TYPE,SIZE,TRAN,ROTA,MODEL", "-J", "-b"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lsblk_data = json.loads(result.stdout)
                for device in lsblk_data.get("blockdevices", []):
                    if device.get("type") == "disk":
                        name = f"/dev/{device.get('name', '')}"
                        transport = (device.get("tran") or "").lower()
                        is_rotational = device.get("rota", True)
                        model = (device.get("model") or "").strip()
                        size_bytes = device.get("size", 0)

                        # Determine disk type
                        if "nvme" in name:
                            disk_type = "NVMe"
                        elif not is_rotational or self._is_ssd_model(model):
                            disk_type = "SSD"
                        else:
                            disk_type = "HDD"

                        # Format transport
                        transport_map = {
                            "sata": "SATA",
                            "usb": "USB",
                            "nvme": "NVMe",
                            "sas": "SAS",
                            "ata": "ATA",
                            "": "Unknown",
                        }
                        transport_fmt = transport_map.get(transport, transport.upper() or "Unknown")

                        disk_info_map[name] = {
                            "type": "disk",
                            "disk_type": disk_type,
                            "transport": transport_fmt,
                            "size_bytes": size_bytes,
                        }
        except (json.JSONDecodeError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return disk_info_map

    def _parse_disk_hierarchy(self, mountpoints: Dict, smart_cache: Dict) -> list:
        """Parse lsblk output and build disk hierarchy."""
        hierarchy = []
        try:
            result = subprocess.run(
                [LSBLK, "-o", "NAME,VENDOR,MODEL,SERIAL,ROTA,TYPE,SIZE,TRAN,UUID,FSTYPE", "-J", "-b"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return hierarchy

            lsblk_data = json.loads(result.stdout)
            for device in lsblk_data.get("blockdevices", []):
                if device.get("type") != "disk":
                    continue

                disk_entry = self._build_disk_entry(device, smart_cache)
                if disk_entry is None:
                    continue

                for child in device.get("children", []):
                    part_entry = self._build_partition_entry(child, mountpoints)
                    for grandchild in child.get("children", []):
                        lvm_entry = self._build_lvm_entry(grandchild, mountpoints)
                        part_entry["children"].append(lvm_entry)
                    disk_entry["children"].append(part_entry)

                self._calculate_disk_usage(disk_entry)
                hierarchy.append(disk_entry)

        except (json.JSONDecodeError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return hierarchy

    def _build_disk_entry(self, device: Dict, smart_cache: Dict) -> Dict[str, Any] | None:
        """Build disk entry from lsblk device data."""
        dev_name = device.get("name", "")
        if "loop" in dev_name or dev_name.startswith("sr"):
            return None

        full_dev = f"/dev/{dev_name}"
        model = (device.get("model") or "").strip()
        transport = (device.get("tran") or "").lower()
        is_ssd = not device.get("rota", True) or self._is_ssd_model(model)
        smart = smart_cache.get(full_dev, {})

        return {
            "name": dev_name,
            "full_path": full_dev,
            "type": "nvme" if "nvme" in dev_name else ("ssd" if is_ssd else "hdd"),
            "transport": transport,
            "is_usb": transport == "usb",
            "model": model,
            "vendor": (device.get("vendor") or "").strip(),
            "serial": (device.get("serial") or "").strip(),
            "size": device.get("size", 0),
            "temperature": smart.get("temperature"),
            "smart_status": smart.get("status", "N/A"),
            "children": [],
        }

    def _build_partition_entry(self, child: Dict, mountpoints: Dict) -> Dict[str, Any]:
        """Build partition entry from lsblk child data."""
        child_name = child.get("name", "")
        child_full = f"/dev/{child_name}"
        mount_list = mountpoints.get(child_full, [])
        all_mounts = [m["mountpoint"] for m in mount_list]
        primary_mount = all_mounts[0] if all_mounts else ""
        fstype = mount_list[0]["fstype"] if mount_list else (child.get("fstype") or "")

        return {
            "name": child_name,
            "full_path": child_full,
            "node_type": child.get("type", ""),
            "size": child.get("size", 0),
            "mountpoint": primary_mount,
            "mountpoints": all_mounts,
            "fstype": fstype,
            "uuid": child.get("uuid", ""),
            "usage": self._get_disk_usage(primary_mount) if primary_mount else None,
            "children": [],
        }

    def _build_lvm_entry(self, grandchild: Dict, mountpoints: Dict) -> Dict[str, Any]:
        """Build LVM entry from lsblk grandchild data."""
        gc_name = grandchild.get("name", "")
        gc_full = f"/dev/mapper/{gc_name}"
        gc_mount_list = mountpoints.get(gc_full, [])
        gc_all_mounts = [m["mountpoint"] for m in gc_mount_list]
        gc_primary_mount = gc_all_mounts[0] if gc_all_mounts else ""
        gc_fstype = gc_mount_list[0]["fstype"] if gc_mount_list else (grandchild.get("fstype") or "")

        return {
            "name": gc_name,
            "full_path": gc_full,
            "node_type": grandchild.get("type", ""),
            "size": grandchild.get("size", 0),
            "mountpoint": gc_primary_mount,
            "mountpoints": gc_all_mounts,
            "fstype": gc_fstype,
            "uuid": grandchild.get("uuid", ""),
            "usage": self._get_disk_usage(gc_primary_mount) if gc_primary_mount else None,
        }

    def _calculate_disk_usage(self, disk_entry: Dict) -> None:
        """Calculate aggregated disk usage from all mounted children."""
        total_used = 0
        total_size = disk_entry["size"]
        has_mounted = False

        for part in disk_entry["children"]:
            if part.get("usage"):
                total_used += part["usage"].get("used", 0)
                has_mounted = True
            for lvm in part.get("children", []):
                if lvm.get("usage"):
                    total_used += lvm["usage"].get("used", 0)
                    has_mounted = True

        if has_mounted and total_size > 0:
            disk_entry["usage"] = {
                "total": total_size,
                "used": total_used,
                "free": total_size - total_used,
                "percent": round((total_used / total_size) * 100, 1),
            }

    def _get_io_stats(self) -> Dict[str, Any]:
        """Get disk I/O statistics."""
        current_io = psutil.disk_io_counters(perdisk=True)
        global_io = psutil.disk_io_counters()
        current_time = time.time()
        dt = max(current_time - self._last_io_time, 1.0)

        per_disk_stats = {}
        if current_io:
            for disk, counters in current_io.items():
                stats = counters._asdict()
                if disk in self._last_disk_io:
                    prev = self._last_disk_io[disk]
                    read_diff = max(0, counters.read_bytes - prev.read_bytes)
                    write_diff = max(0, counters.write_bytes - prev.write_bytes)
                    stats["read_rate"] = read_diff / dt
                    stats["write_rate"] = write_diff / dt
                else:
                    stats["read_rate"] = 0
                    stats["write_rate"] = 0
                per_disk_stats[disk] = stats
            self._last_disk_io = current_io
            self._last_io_time = current_time

        return {
            "read_bytes": global_io.read_bytes if global_io else 0,
            "write_bytes": global_io.write_bytes if global_io else 0,
            "read_count": global_io.read_count if global_io else 0,
            "write_count": global_io.write_count if global_io else 0,
            "per_disk": per_disk_stats,
        }

    def _build_partitions_list(self, hierarchy: list) -> list:
        """Build flat partitions list for System Info widget compatibility."""
        partitions = []
        for disk in hierarchy:
            for part in disk.get("children", []):
                usage = part.get("usage")
                if usage and part.get("mountpoint"):
                    partitions.append(
                        {
                            "device": part.get("full_path", ""),
                            "mountpoint": part.get("mountpoint", ""),
                            "fstype": part.get("fstype", ""),
                            "total": usage.get("total", 0),
                            "used": usage.get("used", 0),
                            "free": usage.get("free", 0),
                            "percent": usage.get("percent", 0),
                        }
                    )
                for lvm in part.get("children", []):
                    lvm_usage = lvm.get("usage")
                    if lvm_usage and lvm.get("mountpoint"):
                        partitions.append(
                            {
                                "device": lvm.get("full_path", ""),
                                "mountpoint": lvm.get("mountpoint", ""),
                                "fstype": lvm.get("fstype", ""),
                                "total": lvm_usage.get("total", 0),
                                "used": lvm_usage.get("used", 0),
                                "free": lvm_usage.get("free", 0),
                                "percent": lvm_usage.get("percent", 0),
                            }
                        )
        return partitions

    def _is_ssd_model(self, model: str) -> bool:
        """Detect if disk is SSD by model name (for USB devices where rotational flag lies)."""
        if not model:
            return False
        model_upper = model.upper()
        # Common SSD indicators in model names
        ssd_indicators = [
            "SSD",
            "NVME",
            "SA400",
            "SA500",
            "A400",
            "MX500",
            "BX500",
            "EVO",
            "860",
            "870",
            "980",
            "970",
            "CRUCIAL",
            "SANDISK",
        ]
        return any(indicator in model_upper for indicator in ssd_indicators)

    def _get_smart_info(self, disk_info_map: Dict[str, Any]) -> Dict[str, Any]:
        """Get SMART status and temperature for physical disks."""
        smart_info = {}

        for disk_name, info in disk_info_map.items():
            if info.get("type") != "disk":
                continue
            if "loop" in disk_name or "mapper" in disk_name:
                continue

            result = self._get_smart_for_disk(disk_name, info)
            if result:
                smart_info[disk_name] = result

        return smart_info

    def _get_smart_for_disk(
        self, disk_name: str, lsblk_info: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get SMART data for a single disk, using cached device_type if known."""
        cache_entry = self._smart_disk_cache.get(disk_name, {})
        cached_type = cache_entry.get("device_type")
        cached_serial = cache_entry.get("serial")

        # Check if SMART was previously marked as unsupported
        if cache_entry.get("smart_supported") is False:
            return None

        # First, try known working device_type from cache
        if cached_type is not None or "device_type" in cache_entry:
            result, disk_info = self._try_smartctl_json_extended(disk_name, cached_type)
            if result and result.get("temperature") is not None:
                # Verify it's the same disk (serial match)
                if cached_serial and disk_info.get("serial") and cached_serial != disk_info.get("serial"):
                    logger.info(f"Disk {disk_name} serial changed, re-probing device type")
                else:
                    self._update_disk_cache(disk_name, cached_type, result, disk_info, lsblk_info)
                    return result
            # Cached type no longer works, will re-probe below

        # Try different device types for USB bridges
        device_types = [None, "sat", "usbsunplus", "usbjmicron", "usbcypress", "usbprolific"]

        best_result = None
        best_type = None
        best_disk_info = None

        for dev_type in device_types:
            result, disk_info = self._try_smartctl_json_extended(disk_name, dev_type)
            if result:
                if result.get("temperature") is not None:
                    # Found temperature - cache and return
                    self._update_disk_cache(disk_name, dev_type, result, disk_info, lsblk_info)
                    return result
                elif best_result is None:
                    best_result = result
                    best_type = dev_type
                    best_disk_info = disk_info

        # Cache best working type even without temperature
        if best_result:
            self._update_disk_cache(disk_name, best_type, best_result, best_disk_info, lsblk_info)
            return best_result

        # Fallback: try reading temperature from sysfs
        temp = self._get_temp_from_sysfs(disk_name)
        if temp is not None:
            return {"status": "N/A", "temperature": temp}

        # Mark as unsupported to skip in future
        self._smart_disk_cache[disk_name] = {
            "device_type": None,
            "smart_supported": False,
            "last_updated": int(time.time()),
        }
        return None

    def _update_disk_cache(
        self,
        disk_name: str,
        device_type: Optional[str],
        result: Dict[str, Any],
        disk_info: Optional[Dict[str, Any]],
        lsblk_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update the disk cache with latest data."""
        self._smart_disk_cache[disk_name] = {
            "device_type": device_type,
            "model": disk_info.get("model") if disk_info else None,
            "serial": disk_info.get("serial") if disk_info else None,
            "disk_type": lsblk_info.get("disk_type") if lsblk_info else None,
            "transport": lsblk_info.get("transport") if lsblk_info else None,
            "size_bytes": lsblk_info.get("size_bytes") if lsblk_info else None,
            "last_temperature": result.get("temperature"),
            "smart_status": result.get("status", "N/A"),
            "smart_supported": True,
            "last_updated": int(time.time()),
        }

    def _try_smartctl_json_extended(
        self, disk_name: str, device_type: Optional[str] = None
    ) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Try to get SMART info via smartctl JSON output. Returns (smart_result, disk_info)."""
        try:
            cmd = [SMARTCTL, "-H", "-A", "-i", "-j"]  # Added -i for disk info
            if device_type:
                cmd.extend(["-d", device_type])
            cmd.append(disk_name)

            if os.geteuid() != 0:
                cmd = [SUDO] + cmd

            proc_result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if not proc_result.stdout or "specify device type" in proc_result.stdout.lower():
                return None, None

            data = json.loads(proc_result.stdout)

            # Extract disk info (model, serial)
            disk_info = {}
            if "model_name" in data:
                disk_info["model"] = data.get("model_name", "").strip()
            elif "scsi_model_name" in data:
                disk_info["model"] = data.get("scsi_model_name", "").strip()

            if "serial_number" in data:
                disk_info["serial"] = data.get("serial_number", "").strip()
            elif "scsi_serial_number" in data:
                disk_info["serial"] = data.get("scsi_serial_number", "").strip()

            # SMART status
            smart_status = "OK"
            if data.get("smart_status", {}).get("passed") is False:
                smart_status = "FAIL"

            # Temperature - try multiple locations
            temp = None

            # 1. Direct temperature object
            temp_attr = data.get("temperature", {})
            if temp_attr:
                temp = temp_attr.get("current")

            # 2. ATA SMART attributes (ID 190 or 194)
            if temp is None:
                for attr in data.get("ata_smart_attributes", {}).get("table", []):
                    if attr.get("id") in [190, 194]:
                        raw_val = attr.get("raw", {}).get("value")
                        if raw_val is not None and 0 < raw_val < 100:
                            temp = raw_val
                            break

            # 3. SCSI temperature (for USB devices)
            if temp is None:
                scsi_temp = data.get("scsi_temperature", {})
                if scsi_temp:
                    temp = scsi_temp.get("current")

            # 4. NVMe temperature
            if temp is None:
                nvme_temp = data.get("nvme_smart_health_information_log", {})
                if nvme_temp:
                    temp = nvme_temp.get("temperature")

            return {"status": smart_status, "temperature": temp}, disk_info

        except (
            json.JSONDecodeError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
            subprocess.SubprocessError,
            Exception,
        ):
            return None, None

    def _get_temp_from_sysfs(self, disk_name: str) -> int:
        """Try to read disk temperature from sysfs hwmon."""
        try:
            disk_short = disk_name.replace("/dev/", "")
            hwmon_path = f"/sys/block/{disk_short}/device/hwmon"
            if os.path.exists(hwmon_path):
                for hwmon in os.listdir(hwmon_path):
                    temp_file = f"{hwmon_path}/{hwmon}/temp1_input"
                    if os.path.exists(temp_file):
                        with open(temp_file) as f:
                            return int(f.read().strip()) // 1000
        except Exception:
            pass
        return None

    def _get_uptime(self) -> Dict[str, Any]:
        """Get system uptime, trying to read host uptime if in container."""
        uptime_seconds = 0.0
        boot_time = 0.0

        # Check for host proc mounts common in containers
        host_proc_paths = ["/host/proc/uptime", "/host_proc/uptime"]
        found_host_uptime = False

        for path in host_proc_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        uptime_seconds = float(f.read().split()[0])
                        boot_time = time.time() - uptime_seconds
                        found_host_uptime = True
                        break
                except Exception:
                    pass

        if not found_host_uptime:
            # Fallback to standard psutil (container or host native)
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time

        uptime_delta = timedelta(seconds=int(uptime_seconds))

        return {
            "boot_time": boot_time,
            "uptime_seconds": int(uptime_seconds),
            "uptime_formatted": str(uptime_delta),
        }

    def _get_primary_ip(self) -> Dict[str, str]:
        """Get primary interface IP."""
        ip = "N/A"
        interface = "N/A"
        try:
            # Trick to get the interface used for default route
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            try:
                # doesn't even have to be reachable
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
            except Exception:
                ip = "127.0.0.1"
            finally:
                s.close()

            # Find interface name for this IP
            for iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.address == ip:
                        interface = iface
                        break
        except (OSError, socket.error, AttributeError):
            pass

        return {"ip": ip, "interface": interface}

    def _get_users_count(self) -> int:
        """Get number of logged in users."""
        try:
            return len(psutil.users())
        except (psutil.AccessDenied, OSError):
            return 0

    def _get_process_stats(self) -> Dict[str, int]:
        """Get process count and zombies.

        Uses shared cache to avoid duplicate iteration with ProcessesCollector.
        """
        return get_process_stats()
