"""Network information collector."""

import ipaddress
import shlex
import subprocess
import glob
import gzip
import statistics
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import psutil

from utils.binaries import (
    FAIL2BAN_CLIENT,
    FIREWALL_CMD,
    GREP,
    IP,
    IPTABLES,
    NFT,
    TAIL,
    UFW,
)
from utils.logger import get_logger

from .base import BaseCollector

logger = get_logger("network_collector")


def is_valid_ip(ip: str) -> bool:
    """Validate IP address (IPv4 or IPv6) to prevent injection attacks."""
    if not ip or not isinstance(ip, str):
        return False
    try:
        ipaddress.ip_address(ip.strip())
        return True
    except ValueError:
        return False


class NetworkCollector(BaseCollector):
    """Collects network information (interfaces, ports, firewall)."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.bans_db = self._load_bans_db()

    def _load_bans_db(self) -> Dict[str, Any]:
        """Load bans database from disk."""
        import json
        import os

        from const import BANS_DB_FILE
        
        if os.path.exists(BANS_DB_FILE):
            try:
                with open(BANS_DB_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load bans DB: {e}")
        return {}

    def _save_bans_db(self) -> None:
        """Save bans database to disk."""
        import json

        from const import BANS_DB_FILE
        try:
            with open(BANS_DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.bans_db, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save bans DB: {e}")

    def collect(self) -> Dict[str, Any]:
        """
        Collect network information.

        Returns:
            Dictionary with network data
        """
        return {
            'interfaces': self._get_interfaces(),
            'connections': self._get_connections(),
            'open_ports': self._get_open_ports() if self.config.get('network', {}).get('check_open_ports', True) else None,
            'firewall': self._get_firewall_rules() if self.config.get('network', {}).get('check_firewall', True) else None,
            'iptables': self._get_iptables_detailed(),
            'nftables': self._get_nftables_rules(),
            'routing': self._get_routing_table(),
            'fail2ban': self._get_fail2ban_status(),
        }

    def _get_interfaces(self) -> List[Dict[str, Any]]:
        """Get network interfaces information."""
        interfaces = []

        # Get network interface statistics
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()
        net_io_counters = psutil.net_io_counters(pernic=True)

        for interface_name, addrs in net_if_addrs.items():
            interface_info = {
                'name': interface_name,
                'addresses': [],
                'is_up': net_if_stats[interface_name].isup if interface_name in net_if_stats else False,
                'speed': net_if_stats[interface_name].speed if interface_name in net_if_stats else 0,
                'mtu': net_if_stats[interface_name].mtu if interface_name in net_if_stats else 0,
            }

            # Add addresses
            for addr in addrs:
                interface_info['addresses'].append({
                    'family': str(addr.family),
                    'address': addr.address,
                    'netmask': addr.netmask,
                    'broadcast': addr.broadcast,
                })

            # Add I/O statistics
            if interface_name in net_io_counters:
                io = net_io_counters[interface_name]
                interface_info['stats'] = {
                    'bytes_sent': io.bytes_sent,
                    'bytes_recv': io.bytes_recv,
                    'packets_sent': io.packets_sent,
                    'packets_recv': io.packets_recv,
                    'errin': io.errin,
                    'errout': io.errout,
                    'dropin': io.dropin,
                    'dropout': io.dropout,
                }

            interfaces.append(interface_info)

        return interfaces

    def _get_connections(self) -> Dict[str, Any]:
        """Get active network connections."""
        try:
            connections = psutil.net_connections(kind='inet')

            tcp_connections = []
            udp_connections = []

            for conn in connections:
                conn_info = {
                    'fd': conn.fd,
                    'family': str(conn.family),
                    'type': str(conn.type),
                    'local_addr': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                    'remote_addr': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                    'status': conn.status,
                    'pid': conn.pid,
                }

                if 'SOCK_STREAM' in str(conn.type):
                    tcp_connections.append(conn_info)
                elif 'SOCK_DGRAM' in str(conn.type):
                    udp_connections.append(conn_info)

            return {
                'tcp': tcp_connections,
                'udp': udp_connections,
                'total': len(connections),
                'tcp_count': len(tcp_connections),
                'udp_count': len(udp_connections),
            }
        except (PermissionError, psutil.AccessDenied):
            return {'error': 'Permission denied. Run with sudo for connection details.'}

    def _get_open_ports(self) -> List[Dict[str, Any]]:
        """Get listening ports with active connection counts."""
        try:
            listening = []
            connections = psutil.net_connections(kind='inet')

            # Count ESTABLISHED connections per port
            established_counts = {}
            for conn in connections:
                if conn.status == 'ESTABLISHED' and conn.laddr:
                    port = conn.laddr.port
                    established_counts[port] = established_counts.get(port, 0) + 1

            for conn in connections:
                if conn.status == 'LISTEN':
                    port = conn.laddr.port if conn.laddr else None
                    listening.append({
                        'port': port,
                        'address': conn.laddr.ip if conn.laddr else None,
                        'protocol': 'TCP' if 'SOCK_STREAM' in str(conn.type) else 'UDP',
                        'pid': conn.pid,
                        'connections': established_counts.get(port, 0),
                    })

            # Get process names for PIDs
            for item in listening:
                if item['pid']:
                    try:
                        process = psutil.Process(item['pid'])
                        item['process'] = process.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        item['process'] = 'unknown'

            return listening
        except (PermissionError, psutil.AccessDenied):
            return [{'error': 'Permission denied. Run with sudo for port details.'}]

    def _get_firewall_rules(self) -> Dict[str, Any]:
        """Get firewall rules (iptables/ufw/firewalld)."""
        firewall_info = {
            'type': None,
            'status': 'unknown',
            'rules': [],
        }

        # Try UFW first
        ufw_status = self._check_ufw()
        if ufw_status:
            firewall_info.update(ufw_status)
            return firewall_info

        # Try firewalld
        firewalld_status = self._check_firewalld()
        if firewalld_status:
            firewall_info.update(firewalld_status)
            return firewall_info

        # Fallback to iptables
        iptables_status = self._check_iptables()
        if iptables_status:
            firewall_info.update(iptables_status)

        return firewall_info

    def _check_ufw(self) -> Dict[str, Any]:
        """Check UFW firewall status."""
        try:
            result = subprocess.run(
                [UFW, 'status', 'numbered'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                lines = result.stdout.splitlines()
                status = 'active' if 'Status: active' in result.stdout else 'inactive'

                rules = []
                for line in lines:
                    if line.strip() and not line.startswith('Status:') and not line.startswith('To'):
                        rules.append(line.strip())

                return {
                    'type': 'ufw',
                    'status': status,
                    'rules': rules,
                }
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return {}

    def _check_firewalld(self) -> Dict[str, Any]:
        """Check firewalld status."""
        try:
            result = subprocess.run(
                [FIREWALL_CMD, '--state'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                return {
                    'type': 'firewalld',
                    'status': result.stdout.strip(),
                    'rules': [],  # Can be extended to fetch actual rules
                }
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return {}

    def _check_iptables(self) -> Dict[str, Any]:
        """Check iptables rules."""
        try:
            result = subprocess.run(
                [IPTABLES, '-L', '-n'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                return {
                    'type': 'iptables',
                    'status': 'configured',
                    'rules': result.stdout.splitlines(),
                }
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

        return {}

    def _get_iptables_detailed(self) -> List[Dict[str, Any]]:
        """Get detailed iptables rules with stats."""
        try:
            # sudo iptables -L -n -v --line-numbers
            result = subprocess.run(
                [IPTABLES, '-L', '-n', '-v', '--line-numbers'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return []

            rules = []
            current_chain = None
            current_policy = None

            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue

                if line.startswith('Chain'):
                    # Parse Chain header: Chain INPUT (policy DROP 123 packets, 456 bytes)
                    parts = line.split()
                    current_chain = parts[1]
                    current_policy = 'UNKNOWN'
                    if '(policy' in line:
                        try:
                            pol_idx = parts.index('(policy')
                            current_policy = parts[pol_idx + 1]
                        except ValueError:
                            pass
                    continue

                if line.startswith('num'):
                    continue

                # Parse rule line
                # num pkts bytes target prot opt in out source destination [options]
                parts = line.split()
                if len(parts) >= 9 and parts[0].isdigit():
                    rule = {
                        'chain': current_chain,
                        'policy': current_policy,
                        'num': parts[0],
                        'pkts': parts[1],
                        'bytes': parts[2],
                        'target': parts[3],
                        'prot': parts[4],
                        'opt': parts[5],
                        'in': parts[6],
                        'out': parts[7],
                        'source': parts[8],
                        'destination': parts[9],
                        'extra': ' '.join(parts[10:]) if len(parts) > 10 else ''
                    }
                    rules.append(rule)

            return rules
        except Exception as e:
            logger.debug(f"Error getting detailed iptables: {e}")
            return []

    def _get_nftables_rules(self) -> Dict[str, Any]:
        """Get nftables ruleset in JSON format."""
        import json
        
        if not NFT:
            return {'error': 'nft binary not found'}

        try:
            # sudo nft -j list ruleset
            result = subprocess.run(
                [NFT, '-j', 'list', 'ruleset'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return {'error': f"Command failed: {result.stderr}"}

            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {'error': 'Failed to parse JSON output'}
        except Exception as e:
            logger.debug(f"Error getting nftables rules: {e}")
            return {'error': str(e)}

    def _get_routing_table(self) -> List[Dict[str, str]]:
        """Get routing table."""
        try:
            result = subprocess.run(
                [IP, 'route', 'show'],
                capture_output=True,
                text=True,
                timeout=5
            )

            routes = []
            for line in result.stdout.splitlines():
                routes.append({'route': line.strip()})

            return routes
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return [{'error': 'Unable to get routing table'}]

    def _get_fail2ban_status(self) -> Dict[str, Any]:
        """Get fail2ban status and jail information."""
        result = {
            'installed': False,
            'running': False,
            'jails': [],
            'total_banned': 0,
        }

        try:
            # Check if fail2ban-client exists and get status
            status_result = subprocess.run(
                [FAIL2BAN_CLIENT, 'status'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if status_result.returncode != 0:
                return result

            result['installed'] = True
            result['running'] = True

            # Parse jail list from status output
            jail_names = []
            for line in status_result.stdout.splitlines():
                if 'Jail list:' in line:
                    # Format: "Jail list:   sshd, nginx-http-auth"
                    jail_part = line.split(':', 1)[1].strip()
                    if jail_part:
                        jail_names = [j.strip() for j in jail_part.split(',')]
                    break

            # Get detailed info for each jail
            total_banned = 0
            active_ips = set()
            for jail_name in jail_names:
                jail_info = self._get_jail_info(jail_name)
                if jail_info:
                    result['jails'].append(jail_info)
                    total_banned += jail_info.get('currently_banned', 0)
                    # Collect all active IPs
                    for b_ip in jail_info.get('banned_ips', []):
                        if b_ip.get('ip'):
                            active_ips.add(b_ip['ip'])

            result['total_banned'] = total_banned

            # Add Unbanned History (filtering out active IPs)
            unbans_jail = self._get_recent_unbans(exclude_ips=active_ips)
            if unbans_jail:
                result['jails'].append(unbans_jail)

            # Add Slow Brute-Force Analysis
            slow_bots = self._get_slow_bots_from_cache(exclude_ips=active_ips)
            if slow_bots:
                result['jails'].append(slow_bots)

        except FileNotFoundError:
            logger.debug("fail2ban-client not found")
        except subprocess.TimeoutExpired:
            logger.warning("fail2ban-client timed out")
        except Exception as e:
            logger.error(f"Error getting fail2ban status: {e}")

        return result

    def _get_recent_unbans(self, limit: int = 500, exclude_ips: set = None) -> Dict[str, Any]:
        """Get recently unbanned IPs from fail2ban log, excluding active ones."""
        import os
        log_file = '/var/log/fail2ban.log'
        unbans = []
        exclude_ips = exclude_ips or set()

        if not os.path.exists(log_file):
            return None

        try:
            # Read file and filter lines containing 'Unban' (safe, no shell)
            unban_lines = []
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if 'Unban' in line:
                        unban_lines.append(line.strip())

            # Take last limit*3 lines (equivalent to tail)
            unban_lines = unban_lines[-(limit * 3):]

            processed_ips = set()

            # Parse lines: "2023-10-27 10:00:00,123 fail2ban.actions [123]: NOTICE [sshd] Unban 1.2.3.4"
            for line in reversed(unban_lines): # Show newest first
                if len(unbans) >= limit:
                    break

                parts = line.split()
                # Expected minimal parts: Date, Time, ..., Jail, Unban, IP
                if len(parts) >= 6:
                    ip = parts[-1]
                    
                    # Filter: Skip if currently banned OR already added to this list
                    if ip in exclude_ips or ip in processed_ips:
                        continue

                    jail = 'unknown'
                    try:
                        # Find 'Unban' index
                        if 'Unban' in parts:
                            unban_idx = parts.index('Unban')
                            # Look backwards for [jail]
                            for i in range(unban_idx - 1, -1, -1):
                                if parts[i].startswith('[') and parts[i].endswith(']'):
                                    jail = parts[i].strip('[]')
                                    break
                    except (ValueError, IndexError):
                        pass
                        
                    timestamp = f"{parts[0]} {parts[1]}"
                    
                    # Enrich with geo info and attempts from DB
                    ip_data = self._get_ip_data(ip)
                    
                    unbans.append({
                        'ip': ip,
                        'country': ip_data.get('country', 'Unknown'),
                        'org': ip_data.get('org', 'Unknown'),
                        'jail': jail, # Store original jail name here
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

    def _get_slow_bots_from_cache(self, exclude_ips: set = None) -> Dict[str, Any]:
        """Load slow bots analysis from JSON cache."""
        import json
        from const import SLOW_BOTS_FILE
        
        if not os.path.exists(SLOW_BOTS_FILE):
            return None
            
        try:
            with open(SLOW_BOTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            banned_ips = []
            exclude_ips = exclude_ips or set()
            
            for item in data:
                ip = item.get('ip')
                if ip in exclude_ips:
                    continue
                    
                # Enrich with Geo info if possible
                ip_data = self._get_ip_data(ip)
                
                # Format interval
                avg_int = item.get('avg_int', 0)
                if avg_int < 60:
                    interval_str = f"{int(avg_int)}s"
                elif avg_int < 3600:
                    interval_str = f"{int(avg_int // 60)}m"
                else:
                    interval_str = f"{int(avg_int // 3600)}h"
                
                banned_ips.append({
                    'ip': ip,
                    'country': ip_data.get('country', 'Unknown'),
                    'org': ip_data.get('org', 'Unknown'),
                    'jail': item.get('jail', 'unknown'),
                    'attempts': item.get('count', 0),
                    'bantime': 0, 
                    'status': item.get('status', 'Detected'),
                    'interval': interval_str
                })
                
            if not banned_ips:
                return None
                
            return {
                'name': 'SLOW BRUTE-FORCE DETECTOR',
                'currently_banned': 0,
                'total_banned': len(banned_ips),
                'banned_ips': banned_ips,
                'filter_failures': 0
            }
        except Exception as e:
            logger.error(f"Failed to load slow bots: {e}")
            return None

    def run_f2b_analysis(self) -> str:
        """Run the analysis script and return its output."""
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts/analyze_f2b.py'))
        try:
            # Run with sudo
            result = subprocess.run(
                ['sudo', 'python3', script_path, '--json'], 
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.stdout
        except Exception as e:
            return f"Error running analysis: {e}"

    def ban_ip(self, ip: str, jail: str = 'recidive') -> bool:
        """Ban an IP manually."""
        try:
            subprocess.run(
                [FAIL2BAN_CLIENT, 'set', jail, 'banip', ip],
                check=True, timeout=5, capture_output=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to ban {ip}: {e}")
            return False

    def unban_ip(self, ip: str, jail: str = None) -> bool:
        """Unban an IP manually."""
        try:
            if jail:
                cmd = [FAIL2BAN_CLIENT, 'set', jail, 'unbanip', ip]
            else:
                cmd = [FAIL2BAN_CLIENT, 'unban', ip]
            
            subprocess.run(cmd, check=True, timeout=5, capture_output=True)
            return True
        except Exception as e:
            logger.error(f"Failed to unban {ip}: {e}")
            return False
            
    def cleanup(self):
        """Cleanup temporary files."""
        from const import SLOW_BOTS_FILE
        if os.path.exists(SLOW_BOTS_FILE):
            try:
                os.remove(SLOW_BOTS_FILE)
            except Exception as e:
                logger.error(f"Failed to cleanup slow bots file: {e}")

    def _get_jail_info(self, jail_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific fail2ban jail."""
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
                        # Get bantime for this jail
                        bantime = self._get_jail_bantime(jail_name)
                        is_traefik = 'traefik' in jail_name.lower()
                        jail_info['banned_ips'] = []
                        for ip in ips:
                            # Get country and org from DB
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
                        jail_info['banned_ips'].sort(key=lambda x: x.get('attempts', 0), reverse=True)
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

    def _count_ip_attempts(self, ip: str, jail_name: str) -> int:
        """Count failed attempts for an IP from logs (simplified/fast)."""
        
        # Only count for specific jails where logs are predictable and fast
        log_file = None
        
        if jail_name == 'sshd':
            log_file = '/var/log/auth.log'
        elif 'traefik' in jail_name:
            log_file = '/home/app_data/docker/traefik/logs/access.log'
            
        if not log_file:
            return 0

        try:
            # Simple fast grep on current log only
            cmd = [GREP, '-c', ip, log_file]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception as e:
            logger.debug(f"Failed to count attempts for {ip} in {log_file}: {e}")

        return 0

    def _get_ip_data(self, ip: str) -> Dict[str, Any]:
        """Get IP data (Geo, attempts) from DB or fetch/calc it."""
        import json
        import os
        import time
        import urllib.request

        # Default info structure
        info = {
            'country': 'Unknown',
            'org': 'Unknown',
            'attempts': 0,
            'last_updated': 0
        }

        # Validate IP before any operations (SSRF prevention)
        if not is_valid_ip(ip):
            logger.warning(f"Invalid IP address rejected: {ip}")
            return info

        # Check cache/DB
        if ip in self.bans_db:
            info = self.bans_db[ip]

        current_time = time.time()
        # Update if it's new OR if entry is older than 5 minutes (300 seconds)
        if current_time - info.get('last_updated', 0) > 300:

            # 1. Geo Info (Only if unknown or missing)
            if info.get('country', 'Unknown') == 'Unknown':
                try:
                    url = f"http://ip-api.com/json/{ip}?fields=country,org"
                    req = urllib.request.Request(url, headers={'User-Agent': 'utm'})
                    with urllib.request.urlopen(req, timeout=2) as response:
                        data = json.loads(response.read().decode())
                        info['country'] = data.get('country', 'Unknown')
                        info['org'] = data.get('org', 'Unknown')
                except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
                    logger.debug(f"Failed to fetch geo data for {ip}: {e}")

            # 2. Count attempts (Update count from all rotated logs)
            try:
                log_glob = '/var/log/fail2ban.log*'
                count = 0
                for log_file in glob.glob(log_glob):
                    try:
                        opener = gzip.open if log_file.endswith('.gz') else open
                        with opener(log_file, 'rt', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                if ip in line:
                                    count += 1
                    except Exception as e:
                        logger.debug(f"Error reading log {log_file}: {e}")
                info['attempts'] = count
            except Exception as e:
                logger.debug(f"Failed to count attempts for {ip}: {e}")

            info['last_updated'] = current_time
            self.bans_db[ip] = info
            self._save_bans_db()

        return info

    def _get_traefik_target_for_ip(self, ip: str, log_path: str = '/home/app_data/docker/traefik/logs/access.log') -> str:
        """Get target application/path from Traefik JSON log for a given IP."""
        import json

        # Validate IP
        if not is_valid_ip(ip):
            return '-'

        try:
            # Read last 1000 lines of log to find requests from this IP
            result = subprocess.run(
                [TAIL, '-1000', log_path],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return '-'

            targets = []
            for line in result.stdout.splitlines():
                if not line.startswith('{'):
                    continue
                try:
                    data = json.loads(line)
                    if data.get('ClientHost') == ip:
                        # Prefer RouterName if available, otherwise use RequestHost/Path
                        router = data.get('RouterName', '')
                        if router:
                            # RouterName format: "app-secure@docker" -> extract "app"
                            app_name = router.split('@')[0].replace('-secure', '')
                            targets.append(app_name)
                        else:
                            # No router matched - use host + path
                            host = data.get('RequestHost', '')
                            path = data.get('RequestPath', '/')
                            # Truncate path for display
                            if len(path) > 20:
                                path = path[:17] + '...'
                            targets.append(f"{host}{path}")
                except json.JSONDecodeError:
                    continue

            if targets:
                # Return most common target (or last few unique)
                from collections import Counter
                counter = Counter(targets)
                top_targets = [t for t, _ in counter.most_common(2)]
                return ', '.join(top_targets)

            return '-'
        except Exception as e:
            logger.debug(f"Error getting traefik target for {ip}: {e}")
            return '-'
