"""Fail2ban information collector."""

import glob
import gzip
import json
import os
import subprocess
import time
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple

from const import (
    BANS_DB_FILE,
    IP_CACHE_TTL,
    RECIDIVE_BANTIME,
    SLOW_BOTS_FILE,
    UNBAN_HISTORY_LIMIT,
    WHITELIST_FILE,
)
from utils.binaries import FAIL2BAN_CLIENT, GREP, TAIL
from utils.formatters import format_interval
from utils.logger import get_logger

from .base import BaseCollector

logger = get_logger("fail2ban_collector")


def is_valid_ip(ip: str) -> bool:
    """Validate IP address (IPv4 or IPv6) to prevent injection attacks."""
    import ipaddress

    if not ip or not isinstance(ip, str):
        return False
    try:
        ipaddress.ip_address(ip.strip())
        return True
    except ValueError:
        return False


class Fail2banCollector(BaseCollector):
    """Collects Fail2ban status and manages IP bans."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._ip_cache: Dict[str, Dict[str, Any]] = {}
        self._whitelist: List[str] = []
        self._load_ip_cache()
        self._load_whitelist()

    def _load_ip_cache(self) -> None:
        """Load IP cache from disk."""
        if os.path.exists(BANS_DB_FILE):
            try:
                with open(BANS_DB_FILE, 'r', encoding='utf-8') as f:
                    self._ip_cache = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load IP cache: {e}")
                self._ip_cache = {}

    def _save_ip_cache(self) -> None:
        """Save IP cache to disk."""
        try:
            with open(BANS_DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._ip_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save IP cache: {e}")

    def _load_whitelist(self) -> None:
        """Load whitelist from disk."""
        if os.path.exists(WHITELIST_FILE):
            try:
                with open(WHITELIST_FILE, 'r', encoding='utf-8') as f:
                    self._whitelist = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load whitelist: {e}")
                self._whitelist = []

    def _save_whitelist(self) -> None:
        """Save whitelist to disk."""
        try:
            with open(WHITELIST_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._whitelist, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save whitelist: {e}")

    def get_whitelist(self) -> List[str]:
        """Get current whitelist."""
        return self._whitelist.copy()

    def add_to_whitelist(self, ip: str) -> bool:
        """Add IP to whitelist."""
        if not is_valid_ip(ip):
            logger.error(f"Invalid IP for whitelist: {ip}")
            return False
        if ip not in self._whitelist:
            self._whitelist.append(ip)
            self._save_whitelist()
            logger.info(f"Added {ip} to whitelist")
            return True
        return False

    def remove_from_whitelist(self, ip: str) -> bool:
        """Remove IP from whitelist."""
        if ip in self._whitelist:
            self._whitelist.remove(ip)
            self._save_whitelist()
            logger.info(f"Removed {ip} from whitelist")
            return True
        return False

    def is_whitelisted(self, ip: str) -> bool:
        """Check if IP is in whitelist."""
        return ip in self._whitelist

    def collect(self) -> Dict[str, Any]:
        """Collect Fail2ban status and jail information.

        Returns:
            Dictionary with fail2ban status data
        """
        t0 = time.time()
        logger.debug("Starting Fail2Ban data collection")

        result = {
            'installed': False,
            'running': False,
            'jails': [],
            'total_banned': 0,
        }

        try:
            t1 = time.time()
            status_result = subprocess.run(
                [FAIL2BAN_CLIENT, 'status'],
                capture_output=True,
                text=True,
                timeout=10
            )
            logger.debug(f"fail2ban-client status executed in {time.time()-t1:.3f}s")

            if status_result.returncode != 0:
                return result

            result['installed'] = True
            result['running'] = True

            # Parse jail list
            jail_names = self._parse_jail_list(status_result.stdout)
            logger.debug(f"Found {len(jail_names)} active jails: {jail_names}")

            # Collect active IPs for exclusion in history/slow bots
            active_ips: Set[str] = set()
            total_banned = 0

            for jail_name in jail_names:
                t2 = time.time()
                jail_info = self._get_jail_info(jail_name)
                duration = time.time() - t2
                if duration > 5.0:
                    logger.warning(f"Slow jail processing: '{jail_name}' took {duration:.2f}s")
                else:
                    logger.debug(f"Processed jail '{jail_name}' in {duration:.3f}s")
                if jail_info:
                    result['jails'].append(jail_info)
                    total_banned += jail_info.get('currently_banned', 0)
                    for ip_data in jail_info.get('banned_ips', []):
                        if ip_data.get('ip'):
                            active_ips.add(ip_data['ip'])

            result['total_banned'] = total_banned
            logger.debug(f"Processed all jails: {total_banned} IPs currently banned")

            # Add virtual jails (history and slow detector)
            t3 = time.time()
            unbans_jail = self._get_recent_unbans(exclude_ips=active_ips)
            duration = time.time() - t3
            if duration > 5.0:
                logger.warning(f"Slow unban history parsing took {duration:.2f}s")
            else:
                logger.debug(f"Loaded recent unbans in {duration:.3f}s")
            if unbans_jail:
                result['jails'].append(unbans_jail)

            t4 = time.time()
            slow_bots_jail = self._get_slow_bots_from_cache(exclude_ips=active_ips)
            logger.debug(f"Loaded slow bots cache in {time.time()-t4:.3f}s")
            if slow_bots_jail:
                result['jails'].append(slow_bots_jail)

            total_duration = time.time() - t0
            logger.info(
                f"Fail2Ban collection completed: "
                f"{total_banned} banned IPs, {len(jail_names)} jails, "
                f"duration={total_duration:.2f}s"
            )

        except FileNotFoundError:
            logger.debug("fail2ban-client not found")
            result['error'] = 'fail2ban not installed'
            result['error_type'] = 'not_installed'
        except subprocess.TimeoutExpired:
            logger.warning("fail2ban-client timed out")
            result['error'] = 'fail2ban-client timed out'
            result['error_type'] = 'timeout'
        except PermissionError:
            logger.warning("Permission denied accessing fail2ban")
            result['error'] = 'Permission denied (requires sudo)'
            result['error_type'] = 'permission'
        except Exception as e:
            logger.error(f"Error collecting fail2ban status: {e}")
            result['error'] = f'Error: {e}'
            result['error_type'] = 'unknown'

        return result

    def _parse_jail_list(self, output: str) -> List[str]:
        """Parse jail names from fail2ban-client status output."""
        for line in output.splitlines():
            if 'Jail list:' in line:
                jail_part = line.split(':', 1)[1].strip()
                if jail_part:
                    return [j.strip() for j in jail_part.split(',')]
        return []

    def _get_jail_info(self, jail_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific jail."""
        try:
            result = subprocess.run(
                [FAIL2BAN_CLIENT, 'status', jail_name],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return None

            jail_info = {
                'name': jail_name,
                'currently_banned': 0,
                'total_banned': 0,
                'banned_ips': [],
                'filter_failures': 0,
            }

            bantime = self._get_jail_bantime(jail_name)
            is_traefik = 'traefik' in jail_name.lower()

            for line in result.stdout.splitlines():
                line = line.strip()
                if 'Currently banned:' in line:
                    try:
                        jail_info['currently_banned'] = int(line.split(':')[1].strip())
                    except (ValueError, IndexError):
                        pass
                elif 'Total banned:' in line:
                    try:
                        jail_info['total_banned'] = int(line.split(':')[1].strip())
                    except (ValueError, IndexError):
                        pass
                elif 'Banned IP list:' in line:
                    ip_part = line.split(':', 1)[1].strip()
                    if ip_part:
                        ips = ip_part.split()
                        for ip in ips:
                            ip_data = self._get_ip_data(ip)
                            ip_info = {
                                'ip': ip,
                                'country': ip_data.get('country', 'Unknown'),
                                'org': ip_data.get('org', 'Unknown'),
                                'attempts': self._count_ip_attempts(ip, jail_name),
                                'bantime': bantime,
                            }
                            if is_traefik:
                                ip_info['target'] = self._get_traefik_target_for_ip(ip)
                            jail_info['banned_ips'].append(ip_info)
                        # Sort by attempts descending
                        jail_info['banned_ips'].sort(
                            key=lambda x: x.get('attempts', 0),
                            reverse=True
                        )
                elif 'Currently failed:' in line:
                    try:
                        jail_info['filter_failures'] = int(line.split(':')[1].strip())
                    except (ValueError, IndexError):
                        pass

            return jail_info

        except Exception as e:
            logger.debug(f"Error getting jail info for {jail_name}: {e}")
            return None

    def _get_jail_bantime(self, jail_name: str) -> int:
        """Get bantime for a jail in seconds."""
        try:
            result = subprocess.run(
                [FAIL2BAN_CLIENT, 'get', jail_name, 'bantime'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception:
            pass
        return 0

    def _get_recent_unbans(
        self,
        limit: int = UNBAN_HISTORY_LIMIT,
        exclude_ips: Optional[Set[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get recently unbanned IPs from fail2ban logs (including rotated)."""
        exclude_ips = exclude_ips or set()

        # Get all fail2ban log files, sorted newest first
        log_files = sorted(glob.glob('/var/log/fail2ban.log*'), reverse=True)
        if not log_files:
            return None

        try:
            unban_lines = []
            for log_file in log_files:
                try:
                    opener = gzip.open if log_file.endswith('.gz') else open
                    with opener(log_file, 'rt', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            if 'Unban' in line:
                                unban_lines.append(line.strip())
                except Exception as e:
                    logger.debug(f"Error reading log {log_file}: {e}")

            # Take last limit*3 lines (equivalent to tail)
            unban_lines = unban_lines[-(limit * 3):]

            unbans = []
            processed_ips: Set[str] = set()

            for line in reversed(unban_lines):
                if len(unbans) >= limit:
                    break

                parts = line.split()
                if len(parts) < 6:
                    continue

                ip = parts[-1]

                if ip in exclude_ips or ip in processed_ips:
                    continue

                jail = self._extract_jail_from_log_line(parts)
                timestamp = f"{parts[0]} {parts[1]}"

                ip_data = self._get_ip_data(ip)

                unbans.append({
                    'ip': ip,
                    'country': ip_data.get('country', 'Unknown'),
                    'org': ip_data.get('org', 'Unknown'),
                    'jail': jail,
                    'unban_time': timestamp,
                    'attempts': ip_data.get('attempts', 0),
                    'bantime': 0
                })
                processed_ips.add(ip)

            if not unbans:
                return None

            # Sort by attempts descending
            unbans.sort(key=lambda x: x.get('attempts', 0), reverse=True)

            return {
                'name': 'HISTORY',
                'currently_banned': 0,
                'total_banned': len(unbans),
                'banned_ips': unbans,
                'filter_failures': 0
            }

        except Exception as e:
            logger.error(f"Failed to get unbans: {e}")
            return None

    def _extract_jail_from_log_line(self, parts: List[str]) -> str:
        """Extract jail name from log line parts."""
        try:
            if 'Unban' in parts:
                unban_idx = parts.index('Unban')
                for i in range(unban_idx - 1, -1, -1):
                    if parts[i].startswith('[') and parts[i].endswith(']'):
                        return parts[i].strip('[]')
        except (ValueError, IndexError):
            pass
        return 'unknown'

    def _get_slow_bots_from_cache(
        self,
        exclude_ips: Optional[Set[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Load slow bots analysis from JSON cache."""
        if not os.path.exists(SLOW_BOTS_FILE):
            return None

        try:
            with open(SLOW_BOTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            exclude_ips = exclude_ips or set()
            banned_ips = []
            total_from_analysis = len(data)
            excluded_count = 0

            for item in data:
                ip = item.get('ip')
                if ip in exclude_ips:
                    excluded_count += 1
                    continue

                ip_data = self._get_ip_data(ip)
                avg_int = item.get('avg_int', 0)

                banned_ips.append({
                    'ip': ip,
                    'country': ip_data.get('country', 'Unknown'),
                    'org': ip_data.get('org', 'Unknown'),
                    'jail': item.get('jail', 'unknown'),
                    'attempts': item.get('count', 0),
                    'bantime': 0,
                    'status': item.get('status', 'Detected'),
                    'interval': format_interval(avg_int)
                })

            if not banned_ips and excluded_count == 0:
                return None

            return {
                'name': 'SLOW BRUTE-FORCE DETECTOR',
                'currently_banned': 0,
                'total_banned': len(banned_ips),
                'total_from_analysis': total_from_analysis,
                'excluded_count': excluded_count,
                'banned_ips': banned_ips,
                'filter_failures': 0
            }

        except Exception as e:
            logger.error(f"Failed to load slow bots: {e}")
            return None

    def _get_ip_data(self, ip: str) -> Dict[str, Any]:
        """Get IP data (geo, attempts) from cache or fetch it."""
        info = {
            'country': 'Unknown',
            'org': 'Unknown',
            'attempts': 0,
            'last_updated': 0
        }

        if not is_valid_ip(ip):
            logger.warning(f"Invalid IP address rejected: {ip}")
            return info

        # Check cache
        if ip in self._ip_cache:
            info = self._ip_cache[ip]

        current_time = time.time()

        # Update if new or expired
        if current_time - info.get('last_updated', 0) > IP_CACHE_TTL:
            # Fetch geo info if unknown
            if info.get('country', 'Unknown') == 'Unknown':
                geo_data = self._fetch_geo_data(ip)
                info.update(geo_data)

            # Count attempts from logs
            info['attempts'] = self._count_attempts_from_logs(ip)
            info['last_updated'] = current_time

            self._ip_cache[ip] = info
            self._save_ip_cache()

        return info

    def _fetch_geo_data(self, ip: str) -> Dict[str, str]:
        """Fetch geo data from ip-api.com."""
        try:
            url = f"http://ip-api.com/json/{ip}?fields=country,org"
            req = urllib.request.Request(url, headers={'User-Agent': 'utm'})
            with urllib.request.urlopen(req, timeout=2) as response:
                data = json.loads(response.read().decode())
                return {
                    'country': data.get('country', 'Unknown'),
                    'org': data.get('org', 'Unknown')
                }
        except Exception as e:
            logger.debug(f"Failed to fetch geo data for {ip}: {e}")
            return {'country': 'Unknown', 'org': 'Unknown'}

    def _count_attempts_from_logs(self, ip: str) -> int:
        """Count IP occurrences in fail2ban logs."""
        try:
            count = 0
            for log_file in glob.glob('/var/log/fail2ban.log*'):
                try:
                    opener = gzip.open if log_file.endswith('.gz') else open
                    with opener(log_file, 'rt', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            if ip in line:
                                count += 1
                except Exception as e:
                    logger.debug(f"Error reading log {log_file}: {e}")
            return count
        except Exception as e:
            logger.debug(f"Failed to count attempts for {ip}: {e}")
            return 0

    def _count_ip_attempts(self, ip: str, jail_name: str) -> int:
        """Count failed attempts for an IP from service logs (including rotated)."""
        log_pattern = None

        if jail_name == 'sshd':
            log_pattern = '/var/log/auth.log*'
        elif 'traefik' in jail_name:
            log_pattern = '/home/app_data/docker/traefik/logs/access.log*'

        if not log_pattern:
            return 0

        count = 0
        try:
            for log_file in glob.glob(log_pattern):
                try:
                    opener = gzip.open if log_file.endswith('.gz') else open
                    with opener(log_file, 'rt', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            if ip in line:
                                count += 1
                except Exception as e:
                    logger.debug(f"Error reading log {log_file}: {e}")
        except Exception as e:
            logger.debug(f"Failed to count attempts for {ip}: {e}")

        return count

    def _get_traefik_target_for_ip(
        self,
        ip: str,
        log_path: str = '/home/app_data/docker/traefik/logs/access.log'
    ) -> str:
        """Get target application from Traefik JSON log for a given IP."""
        if not is_valid_ip(ip):
            return '-'

        try:
            # Use grep to find the IP in the logs, pipe to tail
            # Avoid shell=True by using Popen with pipe
            grep_proc = subprocess.Popen(
                [GREP, '-a', ip, log_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            tail_proc = subprocess.Popen(
                [TAIL, '-n', '5'],
                stdin=grep_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True
            )
            grep_proc.stdout.close()

            try:
                output, _ = tail_proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                tail_proc.kill()
                grep_proc.kill()
                return '-'

            if not output:
                return '-'

            targets = []
            for line in output.splitlines():
                if not line.startswith('{'):
                    continue
                try:
                    data = json.loads(line)
                    if data.get('ClientHost') == ip:
                        router = data.get('RouterName', '')
                        if router:
                            app_name = router.split('@')[0].replace('-secure', '')
                            targets.append(app_name)
                        else:
                            host = data.get('RequestHost', '')
                            path = data.get('RequestPath', '/')
                            if len(path) > 20:
                                path = path[:17] + '...'
                            targets.append(f"{host}{path}")
                except json.JSONDecodeError:
                    continue

            if targets:
                from collections import Counter
                counter = Counter(targets)
                top_targets = [t for t, _ in counter.most_common(2)]
                return ', '.join(top_targets)

            return '-'

        except Exception as e:
            logger.debug(f"Error getting traefik target for {ip}: {e}")
            return '-'

    # Public API methods

    def ban_ip(self, ip: str, jail: str = 'recidive') -> bool:
        """Ban an IP manually with 3-year bantime for recidive."""
        t0 = time.time()
        logger.info(f"Banning IP {ip} in jail '{jail}'")

        if not is_valid_ip(ip):
            logger.error(f"Invalid IP address for ban: {ip}")
            return False
        logger.debug(f"IP validation passed for {ip}")

        try:
            # Set 3-year bantime for recidive jail
            if jail == 'recidive':
                logger.debug(f"Setting bantime to {RECIDIVE_BANTIME}s (3 years) for recidive jail")
                t1 = time.time()
                result = subprocess.run(
                    [FAIL2BAN_CLIENT, 'set', jail, 'bantime', str(RECIDIVE_BANTIME)],
                    timeout=5,
                    capture_output=True
                )
                logger.debug(f"Set bantime completed in {time.time()-t1:.3f}s, returncode={result.returncode}")

            logger.debug(f"Executing banip command")
            t2 = time.time()
            result = subprocess.run(
                [FAIL2BAN_CLIENT, 'set', jail, 'banip', ip],
                check=True,
                timeout=5,
                capture_output=True
            )
            logger.debug(f"Ban command executed in {time.time()-t2:.3f}s, returncode={result.returncode}")
            logger.info(f"Successfully banned IP {ip} in {time.time()-t0:.2f}s")
            return True
        except Exception as e:
            logger.error(f"Failed to ban IP {ip}: {e}")
            return False

    def migrate_recidive_bans(self) -> Tuple[int, int]:
        """Migrate all recidive bans to 3-year bantime.

        Returns:
            Tuple of (success_count, total_count)
        """
        # First set the bantime to 3 years
        try:
            subprocess.run(
                [FAIL2BAN_CLIENT, 'set', 'recidive', 'bantime', str(RECIDIVE_BANTIME)],
                timeout=5,
                capture_output=True
            )
        except Exception as e:
            logger.error(f"Failed to set recidive bantime: {e}")
            return (0, 0)

        # Get currently banned IPs in recidive
        try:
            result = subprocess.run(
                [FAIL2BAN_CLIENT, 'status', 'recidive'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return (0, 0)

            # Parse banned IPs
            banned_ips = []
            for line in result.stdout.splitlines():
                if 'Banned IP list:' in line:
                    ip_part = line.split(':', 1)[1].strip()
                    if ip_part:
                        banned_ips = ip_part.split()
                    break

            if not banned_ips:
                logger.info("No IPs to migrate in recidive")
                return (0, 0)

            # Re-ban each IP (unban + ban with new bantime)
            success = 0
            for ip in banned_ips:
                try:
                    # Unban
                    subprocess.run(
                        [FAIL2BAN_CLIENT, 'set', 'recidive', 'unbanip', ip],
                        timeout=5,
                        capture_output=True
                    )
                    # Re-ban with new bantime
                    subprocess.run(
                        [FAIL2BAN_CLIENT, 'set', 'recidive', 'banip', ip],
                        timeout=5,
                        capture_output=True
                    )
                    success += 1
                    logger.debug(f"Migrated {ip} to 3-year ban")
                except Exception as e:
                    logger.error(f"Failed to migrate {ip}: {e}")

            logger.info(f"Migrated {success}/{len(banned_ips)} recidive bans to 3 years")
            return (success, len(banned_ips))

        except Exception as e:
            logger.error(f"Failed to migrate recidive bans: {e}")
            return (0, 0)

    def unban_ip(self, ip: str, jail: Optional[str] = None) -> bool:
        """Unban an IP manually.

        Returns True if IP was successfully unbanned or was not banned.
        Returns False only on actual errors (timeout, permission denied, etc).
        """
        if not is_valid_ip(ip):
            logger.error(f"Invalid IP for unban: {ip}")
            return False

        try:
            if jail:
                cmd = [FAIL2BAN_CLIENT, 'set', jail, 'unbanip', ip]
            else:
                cmd = [FAIL2BAN_CLIENT, 'unban', ip]

            result = subprocess.run(cmd, timeout=5, capture_output=True, text=True)

            # Check both stdout and stderr for messages
            output_lower = (result.stdout + result.stderr).lower()

            if result.returncode == 0:
                logger.info(f"Unbanned {ip}" + (f" from {jail}" if jail else ""))
                return True

            # Check if IP was simply not banned (not an error)
            # fail2ban outputs various messages: "not banned", "is not banned", "not in jail"
            not_banned_patterns = ['not banned', 'is not banned', 'not in jail', 'not in the']
            if any(pattern in output_lower for pattern in not_banned_patterns):
                logger.debug(f"IP {ip} was not banned" + (f" in {jail}" if jail else ""))
                return True  # Not an error - goal achieved

            error_msg = result.stderr.strip() or result.stdout.strip()
            logger.warning(f"Unban command failed for {ip}: {error_msg}")
            return False

        except subprocess.TimeoutExpired:
            logger.error(f"Unban timed out for {ip}")
            return False
        except Exception as e:
            logger.error(f"Failed to unban {ip}: {e}")
            return False

    def run_analysis(self) -> str:
        """Run the slow brute-force analysis script."""
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../../scripts/analyze_f2b.py')
        )
        try:
            result = subprocess.run(
                ['sudo', 'python3', script_path, '--json'],
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.stdout
        except Exception as e:
            return f"Error running analysis: {e}"

    def cleanup(self) -> None:
        """Cleanup temporary files."""
        if os.path.exists(SLOW_BOTS_FILE):
            try:
                os.remove(SLOW_BOTS_FILE)
            except Exception as e:
                logger.error(f"Failed to cleanup slow bots file: {e}")
