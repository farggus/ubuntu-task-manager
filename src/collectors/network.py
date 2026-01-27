"""Network information collector."""

import subprocess
from typing import Any, Dict, List, Optional

import psutil

from utils.binaries import (
    FIREWALL_CMD,
    IP,
    IPTABLES,
    NFT,
    UFW,
)
from utils.logger import get_logger

from .base import BaseCollector

logger = get_logger("network_collector")


class NetworkCollector(BaseCollector):
    """Collects network information (interfaces, ports, firewall)."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)

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

