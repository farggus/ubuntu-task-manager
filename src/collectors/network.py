"""Network information collector."""

import subprocess
import shlex
import psutil
from typing import Dict, Any, List
from .base import BaseCollector
from utils.logger import get_logger

logger = get_logger("network_collector")


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
                shlex.split("ufw status numbered"),
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
                shlex.split("firewall-cmd --state"),
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
                shlex.split("iptables -L -n"),
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

    def _get_routing_table(self) -> List[Dict[str, str]]:
        """Get routing table."""
        try:
            result = subprocess.run(
                shlex.split("ip route show"),
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
                ['fail2ban-client', 'status'],
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

        except FileNotFoundError:
            logger.debug("fail2ban-client not found")
        except subprocess.TimeoutExpired:
            logger.warning("fail2ban-client timed out")
        except Exception as e:
            logger.error(f"Error getting fail2ban status: {e}")

        return result

    def _get_recent_unbans(self, limit: int = 50, exclude_ips: set = None) -> Dict[str, Any]:
        """Get recently unbanned IPs from fail2ban log, excluding active ones."""
        import os
        import subprocess
        log_file = '/var/log/fail2ban.log'
        unbans = []
        exclude_ips = exclude_ips or set()
        
        if not os.path.exists(log_file):
            return None

        try:
            # Grep "Unban" from log, take more to account for filtering
            cmd = f"grep 'Unban' {log_file} | tail -n {limit * 3}"
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=5
            )
            
            processed_ips = set()

            # Parse lines: "2023-10-27 10:00:00,123 fail2ban.actions [123]: NOTICE [sshd] Unban 1.2.3.4"
            for line in reversed(result.stdout.splitlines()): # Show newest first
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

    def _get_jail_info(self, jail_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific fail2ban jail."""
        try:
            result = subprocess.run(
                ['fail2ban-client', 'status', jail_name],
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
                ['fail2ban-client', 'get', jail_name, 'bantime'],
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
        """Count failed attempts for an IP from logs based on jail type."""
        try:
            # Determine log file and pattern based on jail
            if jail_name == 'sshd':
                log_file = '/var/log/auth.log'
                # Count Failed password and Invalid user entries
                result = subprocess.run(
                    ['grep', '-c', ip, log_file],
                    capture_output=True, text=True, timeout=5
                )
            elif jail_name == 'traefik-botsearch':
                log_file = '/home/app_data/docker/traefik/logs/access.log'
                result = subprocess.run(
                    ['grep', '-c', ip, log_file],
                    capture_output=True, text=True, timeout=5
                )
            elif jail_name == 'openvpn':
                log_file = '/var/log/syslog'
                result = subprocess.run(
                    f"grep 'ovpn-server.*{ip}' {log_file} | wc -l",
                    shell=True, capture_output=True, text=True, timeout=5
                )
            else:
                return 0

            if result.returncode == 0:
                return int(result.stdout.strip())
            return 0
        except Exception:
            return 0

    def _get_ip_data(self, ip: str) -> Dict[str, Any]:
        """Get IP data (Geo, attempts) from DB or fetch/calc it."""
        import os
        import subprocess
        import time
        import urllib.request
        import json
        
        # Default info structure
        info = {
            'country': 'Unknown',
            'org': 'Unknown',
            'attempts': 0,
            'last_updated': 0
        }

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
                except Exception:
                    pass

            # 2. Count attempts (Update count from log)
            try:
                log_file = '/var/log/fail2ban.log'
                if os.path.exists(log_file):
                    count_res = subprocess.run(
                        ['grep', '-c', ip, log_file],
                        capture_output=True, text=True, timeout=2
                    )
                    if count_res.returncode == 0:
                        info['attempts'] = int(count_res.stdout.strip())
            except Exception:
                pass

            info['last_updated'] = current_time
            self.bans_db[ip] = info
            self._save_bans_db()
            
        return info

    def _get_traefik_target_for_ip(self, ip: str, log_path: str = '/home/app_data/docker/traefik/logs/access.log') -> str:
        """Get target application/path from Traefik JSON log for a given IP."""
        import json

        try:
            # Read last 1000 lines of log to find requests from this IP
            result = subprocess.run(
                ['tail', '-1000', log_path],
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
