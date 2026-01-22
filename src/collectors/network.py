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
        self.ip_cache = self._load_ip_cache()

    def _load_ip_cache(self) -> Dict[str, Dict[str, str]]:
        """Load IP geo cache from disk."""
        import json
        import os
        from const import IP_CACHE_FILE
        
        if os.path.exists(IP_CACHE_FILE):
            try:
                with open(IP_CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load IP cache: {e}")
        return {}

    def _save_ip_cache(self) -> None:
        """Save IP geo cache to disk."""
        import json
        from const import IP_CACHE_FILE
        try:
            with open(IP_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.ip_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save IP cache: {e}")

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
            for jail_name in jail_names:
                jail_info = self._get_jail_info(jail_name)
                if jail_info:
                    result['jails'].append(jail_info)
                    total_banned += jail_info.get('currently_banned', 0)

            result['total_banned'] = total_banned

        except FileNotFoundError:
            logger.debug("fail2ban-client not found")
        except subprocess.TimeoutExpired:
            logger.warning("fail2ban-client timed out")
        except Exception as e:
            logger.error(f"Error getting fail2ban status: {e}")

        return result

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
                            # Get country and org in one call
                            geo_info = self._get_ip_info(ip)
                            ip_info = {
                                'ip': ip,
                                'country': geo_info.get('country', 'Unknown'),
                                'org': geo_info.get('org', 'Unknown'),
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

    def _get_ip_info(self, ip: str) -> Dict[str, str]:
        """Get country and organization for an IP address using ip-api.com."""
        if ip in self.ip_cache:
            return self.ip_cache[ip]

        try:
            import urllib.request
            import json

            url = f"http://ip-api.com/json/{ip}?fields=country,org"
            req = urllib.request.Request(url, headers={'User-Agent': 'utm'})

            with urllib.request.urlopen(req, timeout=2) as response:
                data = json.loads(response.read().decode())
                info = {
                    'country': data.get('country', 'Unknown'),
                    'org': data.get('org', 'Unknown')
                }
                self.ip_cache[ip] = info
                self._save_ip_cache()
                return info
        except Exception:
            return {'country': 'Unknown', 'org': 'Unknown'}

    def _get_ip_country(self, ip: str) -> str:
        """Get country name for an IP address (legacy wrapper)."""
        return self._get_ip_info(ip).get('country', 'Unknown')

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
