"""System information collector."""

import datetime
import json
import os
import platform
import re
import shlex
import socket
import subprocess
import time
from datetime import timedelta
from typing import Any, Dict

import psutil

from utils.binaries import APT, DPKG_QUERY, LSBLK, SMARTCTL, SUDO, SYSTEMCTL
from utils.logger import get_logger

from .base import BaseCollector

logger = get_logger(__name__)

class SystemCollector(BaseCollector):
    """Collects system information (CPU, RAM, disk, uptime, OS info)."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._last_disk_io = {}
        self._last_io_time = time.time()
        self._pkg_cache = {'total': 0, 'updates': 0}
        self._pkg_cache_time = 0

    def collect(self) -> Dict[str, Any]:
        """
        Collect system information.

        Returns:
            Dictionary with system data
        """
        return {
            'timestamp': datetime.datetime.now().strftime("%a %d %b %Y %H:%M:%S"),
            'os': self._get_os_info(),
            'cpu': self._get_cpu_info(),
            'memory': self._get_memory_info(),
            'disk': self._get_disk_info(),
            'uptime': self._get_uptime(),
            'hostname': platform.node(),
            'network': self._get_primary_ip(),
            'users': self._get_users_count(),
            'processes': self._get_process_stats(),
            'services_stats': self._get_service_stats(),
            'packages': self._get_package_stats(),
        }

    def _get_package_stats(self) -> Dict[str, Any]:
        """Get total packages and updates count/list (cached for 30 min)."""
        now = time.time()
        # Update cache every 30 minutes (1800 seconds)
        if now - self._pkg_cache_time < 1800 and self._pkg_cache['total'] > 0:
            return self._pkg_cache

        total = 0
        updates = 0
        upgradable_list = []
        all_packages = []
        
        try:
            # 1. Get all installed packages (fast)
            res_total = subprocess.run(
                [DPKG_QUERY, '-W', '-f=${Package} ${Version}\n'],
                capture_output=True, text=True, timeout=5
            )
            if res_total.returncode == 0:
                lines = res_total.stdout.splitlines()
                total = len(lines)
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        all_packages.append({
                            'name': parts[0], 
                            'current_version': parts[1],
                            'new_version': '-' # No update available
                        })

            # 2. Get list of upgradable packages using apt list --upgradable
            res_list = subprocess.run(
                [APT, 'list', '--upgradable'],
                capture_output=True, text=True, timeout=10
            )
            
            if res_list.returncode == 0:
                lines = res_list.stdout.splitlines()
                upgradable_names = []
                
                for line in lines:
                    if "..." in line or not line.strip():
                        continue
                    
                    # Format: package/release series version arch ...
                    try:
                        parts = line.split('/')
                        if len(parts) > 1:
                            pkg_name = parts[0]

                            # Extract new version (second word)
                            rest = line.split()
                            new_ver = rest[1] if len(rest) > 1 else '?'

                            upgradable_list.append({
                                'name': pkg_name,
                                'new_version': new_ver,
                                'current_version': '?' # Placeholder
                            })
                            upgradable_names.append(pkg_name)
                    except (IndexError, ValueError):
                        pass
                
                # Enhance with current versions using dpkg-query (reliable)
                if upgradable_names:
                    # Get current versions for these packages
                    # dpkg-query -W -f='${Package} ${Version}\n' [names...]
                    # But command line might be too long. Let's use the all_packages map we already have!
                    
                    # We already fetched all_packages in step 1. Let's use it.
                    installed_map = {p['name']: p['current_version'] for p in all_packages}
                    
                    for pkg in upgradable_list:
                        name = pkg['name']
                        if name in installed_map:
                            pkg['current_version'] = installed_map[name]
                
                updates = len(upgradable_list)

            # Update all_packages with upgradable info
            # Create a dict for faster lookup
            upgradable_map = {p['name']: p for p in upgradable_list}
            
            # Mark updates in all_packages
            for p in all_packages:
                if p['name'] in upgradable_map:
                    p['new_version'] = upgradable_map[p['name']]['new_version']
                    p['upgradable'] = True
                else:
                    p['upgradable'] = False

            # Fallbacks for count if list failed
            if updates == 0 and not upgradable_list:
                # Try apt-check
                apt_check_path = "/usr/lib/update-notifier/apt-check"
                if os.path.exists(apt_check_path):
                    res_upd = subprocess.run(
                        [apt_check_path], 
                        capture_output=True, text=True, timeout=10
                    )
                    if res_upd.returncode == 0:
                        parts = res_upd.stderr.strip().split(';')
                        if len(parts) >= 1:
                            updates = int(parts[0])
        except Exception:
            pass

        self._pkg_cache = {
            'total': total, 
            'updates': updates,
            'upgradable_list': upgradable_list,
            'all_packages': all_packages
        }
        self._pkg_cache_time = now
        return self._pkg_cache

    def _get_service_stats(self) -> Dict[str, int]:
        """Get systemd service statistics (failed count)."""
        failed = 0
        total = 0 # Getting total is expensive, maybe just failed is enough?
        # Let's try to get failed count quickly
        try:
            # systemctl list-units --state=failed --no-legend --count
            # Output is usually just number of lines if piped to wc -l, or we parse.
            # actually --count prints a summary at end, without it it prints lines.
            
            result = subprocess.run(
                [SYSTEMCTL, 'list-units', '--state=failed', '--no-legend'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                failed = len([l for l in result.stdout.splitlines() if l.strip()])
                
            # For total services, we can get active ones quickly
            # systemctl list-units --type=service --no-legend
            res_total = subprocess.run(
                [SYSTEMCTL, 'list-units', '--type=service', '--state=active', '--no-legend'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if res_total.returncode == 0:
                total = len([l for l in res_total.stdout.splitlines() if l.strip()])
                
        except Exception:
            pass
            
        return {'failed': failed, 'active': total}

    def _get_os_info(self) -> Dict[str, str]:
        """Get OS information."""
        os_info = {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
        }
        
        # Try to get a pretty name (e.g. "Ubuntu 24.04.1 LTS")
        pretty_name = f"{os_info['system']} {os_info['release']}"
        try:
            # freedesktop_os_release is available in Python 3.10+
            if hasattr(platform, 'freedesktop_os_release'):
                release_info = platform.freedesktop_os_release()
                pretty_name = release_info.get('PRETTY_NAME', pretty_name)
            else:
                # Fallback for older python or non-freedesktop systems
                if os.path.exists('/etc/os-release'):
                    with open('/etc/os-release') as f:
                        for line in f:
                            if line.startswith('PRETTY_NAME='):
                                pretty_name = line.split('=')[1].strip().strip('"')
                                break
        except Exception:
            pass
            
        os_info['pretty_name'] = pretty_name
        return os_info

    def _get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information."""
        cpu_freq = psutil.cpu_freq()
        
        # Try to get temperature
        temp = 0.0
        try:
            temps = psutil.sensors_temperatures()
            # Common names for CPU temp
            for name in ['coretemp', 'cpu_thermal', 'k10temp', 'zenpower']:
                if name in temps:
                    # Average of all cores or just the first input
                    entries = temps[name]
                    if entries:
                        temp = entries[0].current
                        break
        except (AttributeError, KeyError, OSError, IOError):
            pass

        return {
            'physical_cores': psutil.cpu_count(logical=False),
            'total_cores': psutil.cpu_count(logical=True),
            'frequency': {
                'current': round(cpu_freq.current, 2) if cpu_freq else 0,
                'min': round(cpu_freq.min, 2) if cpu_freq else 0,
                'max': round(cpu_freq.max, 2) if cpu_freq else 0,
            },
            'usage_per_core': [round(x, 1) for x in psutil.cpu_percent(interval=1, percpu=True)],
            'usage_total': round(psutil.cpu_percent(interval=1), 1),
            'temperature': temp
        }

    def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory information."""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return {
            'total': mem.total,
            'available': mem.available,
            'used': mem.used,
            'percent': round(mem.percent, 1),
            'swap': {
                'total': swap.total,
                'used': swap.used,
                'free': swap.free,
                'percent': round(swap.percent, 1),
            }
        }

    def _get_disk_info(self) -> Dict[str, Any]:
        """Get disk information with full hierarchy like lsblk (disk → part → lvm)."""
        hierarchy = []

        # Get mountpoints and usage from psutil
        mountpoints = {}  # device -> list of {mountpoint, fstype}
        for partition in psutil.disk_partitions(all=False):
            if '/snap/' in partition.mountpoint or '/loop' in partition.device:
                continue
            dev = partition.device
            if dev not in mountpoints:
                mountpoints[dev] = []
            mountpoints[dev].append({
                'mountpoint': partition.mountpoint,
                'fstype': partition.fstype,
            })

        def get_usage(mountpoint):
            """Get disk usage for a mountpoint."""
            try:
                usage = psutil.disk_usage(mountpoint)
                return {
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': round(usage.percent, 1),
                }
            except (PermissionError, OSError, FileNotFoundError):
                return None

        # Get SMART cache
        smart_cache = getattr(self, '_smart_cache', {})
        smart_cache_time = getattr(self, '_smart_cache_time', 0)

        # Parse lsblk with full hierarchy
        disk_info_map = {}
        try:
            result = subprocess.run(
                [LSBLK, '-o', 'NAME,VENDOR,MODEL,SERIAL,ROTA,TYPE,SIZE,TRAN,UUID,FSTYPE', '-J', '-b'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lsblk_data = json.loads(result.stdout)

                # Build disk_info_map for SMART lookup
                for device in lsblk_data.get('blockdevices', []):
                    if device.get('type') == 'disk':
                        name = f"/dev/{device.get('name', '')}"
                        disk_info_map[name] = {'type': 'disk'}

                # Update SMART cache every 5 minutes
                if time.time() - smart_cache_time > 300:
                    smart_cache = self._get_smart_info(disk_info_map)
                    self._smart_cache = smart_cache
                    self._smart_cache_time = time.time()

                # Process each disk
                for device in lsblk_data.get('blockdevices', []):
                    if device.get('type') != 'disk':
                        continue

                    dev_name = device.get('name', '')
                    full_dev = f"/dev/{dev_name}"

                    # Skip loop and optical devices
                    if 'loop' in dev_name or dev_name.startswith('sr'):
                        continue

                    model = (device.get('model') or '').strip()
                    vendor = (device.get('vendor') or '').strip()
                    transport = (device.get('tran') or '').lower()
                    is_usb = transport == 'usb'
                    is_ssd = not device.get('rota', True) or self._is_ssd_model(model)
                    smart = smart_cache.get(full_dev, {})

                    disk_type = 'nvme' if 'nvme' in dev_name else ('ssd' if is_ssd else 'hdd')

                    disk_entry = {
                        'name': dev_name,  # Just 'sda', not '/dev/sda'
                        'full_path': full_dev,
                        'type': disk_type,
                        'transport': transport,  # sata, usb, nvme, etc.
                        'is_usb': is_usb,
                        'model': model,
                        'vendor': vendor,
                        'serial': (device.get('serial') or '').strip(),
                        'size': device.get('size', 0),
                        'temperature': smart.get('temperature'),
                        'smart_status': smart.get('status', 'N/A'),
                        'children': [],
                    }

                    # Process partitions (children)
                    for child in device.get('children', []):
                        child_name = child.get('name', '')
                        child_full = f"/dev/{child_name}"
                        child_type = child.get('type', '')

                        # Get mount info for this partition (may have multiple bind mounts)
                        mount_list = mountpoints.get(child_full, [])
                        all_mounts = [m['mountpoint'] for m in mount_list]
                        primary_mount = all_mounts[0] if all_mounts else ''
                        # Prefer fstype from mount, fallback to lsblk
                        fstype = mount_list[0]['fstype'] if mount_list else (child.get('fstype') or '')
                        usage = get_usage(primary_mount) if primary_mount else None

                        part_entry = {
                            'name': child_name,
                            'full_path': child_full,
                            'node_type': child_type,  # 'part', 'lvm', etc.
                            'size': child.get('size', 0),
                            'mountpoint': primary_mount,  # Primary for usage calc
                            'mountpoints': all_mounts,    # All mountpoints for display
                            'fstype': fstype,
                            'uuid': child.get('uuid', ''),
                            'usage': usage,
                            'children': [],
                        }

                        # Process LVM volumes on partition (grandchildren)
                        for grandchild in child.get('children', []):
                            gc_name = grandchild.get('name', '')
                            gc_full = f"/dev/mapper/{gc_name}"
                            gc_type = grandchild.get('type', '')

                            gc_mount_list = mountpoints.get(gc_full, [])
                            gc_all_mounts = [m['mountpoint'] for m in gc_mount_list]
                            gc_primary_mount = gc_all_mounts[0] if gc_all_mounts else ''
                            # Prefer fstype from mount, fallback to lsblk
                            gc_fstype = gc_mount_list[0]['fstype'] if gc_mount_list else (grandchild.get('fstype') or '')
                            gc_usage = get_usage(gc_primary_mount) if gc_primary_mount else None

                            lvm_entry = {
                                'name': gc_name,
                                'full_path': gc_full,
                                'node_type': gc_type,
                                'size': grandchild.get('size', 0),
                                'mountpoint': gc_primary_mount,
                                'mountpoints': gc_all_mounts,
                                'fstype': gc_fstype,
                                'uuid': grandchild.get('uuid', ''),
                                'usage': gc_usage,
                            }
                            part_entry['children'].append(lvm_entry)

                        disk_entry['children'].append(part_entry)

                    # Calculate aggregated disk usage from all mounted children
                    total_used = 0
                    total_size = disk_entry['size']
                    has_mounted = False

                    for part in disk_entry['children']:
                        if part.get('usage'):
                            total_used += part['usage'].get('used', 0)
                            has_mounted = True
                        # Also check LVM children
                        for lvm in part.get('children', []):
                            if lvm.get('usage'):
                                total_used += lvm['usage'].get('used', 0)
                                has_mounted = True

                    if has_mounted and total_size > 0:
                        disk_entry['usage'] = {
                            'total': total_size,
                            'used': total_used,
                            'free': total_size - total_used,
                            'percent': round((total_used / total_size) * 100, 1),
                        }

                    hierarchy.append(disk_entry)

        except (json.JSONDecodeError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Sort: nvme first, then sd* alphabetically
        hierarchy.sort(key=lambda d: (0 if d['name'].startswith('nvme') else 1, d['name']))

        # I/O stats
        current_io = psutil.disk_io_counters(perdisk=True)
        global_io = psutil.disk_io_counters()
        current_time = time.time()
        dt = current_time - self._last_io_time
        if dt <= 0:
            dt = 1.0
        per_disk_stats = {}
        if current_io:
            for disk, counters in current_io.items():
                stats = counters._asdict()
                if disk in self._last_disk_io:
                    prev = self._last_disk_io[disk]
                    read_diff = counters.read_bytes - prev.read_bytes
                    write_diff = counters.write_bytes - prev.write_bytes
                    if read_diff < 0:
                        read_diff = 0
                    if write_diff < 0:
                        write_diff = 0
                    stats['read_rate'] = read_diff / dt
                    stats['write_rate'] = write_diff / dt
                else:
                    stats['read_rate'] = 0
                    stats['write_rate'] = 0
                per_disk_stats[disk] = stats
            self._last_disk_io = current_io
            self._last_io_time = current_time

        io_stats = {
            'read_bytes': global_io.read_bytes if global_io else 0,
            'write_bytes': global_io.write_bytes if global_io else 0,
            'read_count': global_io.read_count if global_io else 0,
            'write_count': global_io.write_count if global_io else 0,
            'per_disk': per_disk_stats
        }

        # Build flat partitions list for System Info widget compatibility
        partitions = []
        for disk in hierarchy:
            for part in disk.get('children', []):
                usage = part.get('usage')
                if usage and part.get('mountpoint'):
                    partitions.append({
                        'device': part.get('full_path', ''),
                        'mountpoint': part.get('mountpoint', ''),
                        'fstype': part.get('fstype', ''),
                        'total': usage.get('total', 0),
                        'used': usage.get('used', 0),
                        'free': usage.get('free', 0),
                        'percent': usage.get('percent', 0),
                    })
                # Also include LVM children
                for lvm in part.get('children', []):
                    lvm_usage = lvm.get('usage')
                    if lvm_usage and lvm.get('mountpoint'):
                        partitions.append({
                            'device': lvm.get('full_path', ''),
                            'mountpoint': lvm.get('mountpoint', ''),
                            'fstype': lvm.get('fstype', ''),
                            'total': lvm_usage.get('total', 0),
                            'used': lvm_usage.get('used', 0),
                            'free': lvm_usage.get('free', 0),
                            'percent': lvm_usage.get('percent', 0),
                        })

        return {
            'hierarchy': hierarchy,
            'partitions': partitions,  # For System Info widget
            'io': io_stats,
        }

    def _is_ssd_model(self, model: str) -> bool:
        """Detect if disk is SSD by model name (for USB devices where rotational flag lies)."""
        if not model:
            return False
        model_upper = model.upper()
        # Common SSD indicators in model names
        ssd_indicators = ['SSD', 'NVME', 'SA400', 'SA500', 'A400', 'MX500', 'BX500',
                          'EVO', '860', '870', '980', '970', 'CRUCIAL', 'SANDISK']
        return any(indicator in model_upper for indicator in ssd_indicators)

    def _get_smart_info(self, disk_info_map: Dict[str, Any]) -> Dict[str, Any]:
        """Get SMART status and temperature for physical disks."""
        smart_info = {}

        for disk_name, info in disk_info_map.items():
            if info.get('type') != 'disk':
                continue
            if 'loop' in disk_name or 'mapper' in disk_name:
                continue

            # Try different device types for USB bridges
            device_types = [None, 'sat', 'usbsunplus', 'usbjmicron', 'usbcypress', 'usbprolific']

            best_result = None
            for dev_type in device_types:
                result = self._try_smartctl_json(disk_name, dev_type)
                if result:
                    # Keep the result with temperature if we have one
                    if result.get('temperature') is not None:
                        best_result = result
                        break  # Found temperature, stop trying
                    elif best_result is None:
                        best_result = result  # Keep first valid result as fallback

            if best_result:
                smart_info[disk_name] = best_result

            # Fallback: try reading temperature from sysfs
            if disk_name not in smart_info:
                temp = self._get_temp_from_sysfs(disk_name)
                if temp is not None:
                    smart_info[disk_name] = {'status': 'N/A', 'temperature': temp}

        return smart_info

    def _try_smartctl_json(self, disk_name: str, device_type: str = None) -> Dict[str, Any]:
        """Try to get SMART info via smartctl JSON output."""
        try:
            cmd = [SMARTCTL, '-H', '-A', '-j']
            if device_type:
                cmd.extend(['-d', device_type])
            cmd.append(disk_name)

            if os.geteuid() != 0:
                cmd = [SUDO] + cmd

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if not result.stdout or 'specify device type' in result.stdout.lower():
                return None

            data = json.loads(result.stdout)

            # SMART status
            smart_status = 'OK'
            if data.get('smart_status', {}).get('passed') is False:
                smart_status = 'FAIL'

            # Temperature - try multiple locations
            temp = None

            # 1. Direct temperature object
            temp_attr = data.get('temperature', {})
            if temp_attr:
                temp = temp_attr.get('current')

            # 2. ATA SMART attributes (ID 190 or 194)
            if temp is None:
                for attr in data.get('ata_smart_attributes', {}).get('table', []):
                    if attr.get('id') in [190, 194]:
                        raw_val = attr.get('raw', {}).get('value')
                        if raw_val is not None and 0 < raw_val < 100:
                            temp = raw_val
                            break

            # 3. SCSI temperature (for USB devices)
            if temp is None:
                scsi_temp = data.get('scsi_temperature', {})
                if scsi_temp:
                    temp = scsi_temp.get('current')

            # 4. NVMe temperature
            if temp is None:
                nvme_temp = data.get('nvme_smart_health_information_log', {})
                if nvme_temp:
                    temp = nvme_temp.get('temperature')

            return {'status': smart_status, 'temperature': temp}

        except (json.JSONDecodeError, FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
            return None

    def _get_temp_from_sysfs(self, disk_name: str) -> int:
        """Try to read disk temperature from sysfs hwmon."""
        try:
            disk_short = disk_name.replace('/dev/', '')
            hwmon_path = f'/sys/block/{disk_short}/device/hwmon'
            if os.path.exists(hwmon_path):
                for hwmon in os.listdir(hwmon_path):
                    temp_file = f'{hwmon_path}/{hwmon}/temp1_input'
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
        host_proc_paths = ['/host/proc/uptime', '/host_proc/uptime']
        found_host_uptime = False
        
        for path in host_proc_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
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
            'boot_time': boot_time,
            'uptime_seconds': int(uptime_seconds),
            'uptime_formatted': str(uptime_delta),
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
                s.connect(('10.255.255.255', 1))
                ip = s.getsockname()[0]
            except Exception:
                ip = '127.0.0.1'
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

        return {'ip': ip, 'interface': interface}

    def _get_users_count(self) -> int:
        """Get number of logged in users."""
        try:
            return len(psutil.users())
        except (psutil.AccessDenied, OSError):
            return 0

    def _get_process_stats(self) -> Dict[str, int]:
        """Get process count and zombies."""
        total = 0
        zombies = 0
        try:
            # Iterating processes is heavy, optimize by fetching only status
            for p in psutil.process_iter(['status']):
                total += 1
                if p.info['status'] == psutil.STATUS_ZOMBIE:
                    zombies += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

        return {'total': total, 'zombies': zombies}