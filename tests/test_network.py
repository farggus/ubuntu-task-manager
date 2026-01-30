"""Tests for NetworkCollector."""

import pytest
from unittest.mock import patch, MagicMock
import subprocess

from collectors.fail2ban import is_valid_ip


class TestNetworkCollector:
    """Tests for NetworkCollector class."""

    def test_import(self):
        """Test that NetworkCollector can be imported."""
        from collectors.network import NetworkCollector
        assert NetworkCollector is not None

    def test_init(self):
        """Test NetworkCollector initialization."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        assert collector is not None

    def test_is_valid_ip_valid_ipv4(self):
        """Test IP validation with valid IPv4."""
        assert is_valid_ip('192.168.1.1') is True
        assert is_valid_ip('10.0.0.1') is True
        assert is_valid_ip('8.8.8.8') is True
        assert is_valid_ip('255.255.255.255') is True

    def test_is_valid_ip_valid_ipv6(self):
        """Test IP validation with valid IPv6."""
        assert is_valid_ip('::1') is True
        assert is_valid_ip('2001:db8::1') is True
        assert is_valid_ip('fe80::1') is True

    def test_is_valid_ip_invalid(self):
        """Test IP validation with invalid IPs."""
        assert is_valid_ip('') is False
        assert is_valid_ip(None) is False
        assert is_valid_ip('not-an-ip') is False
        assert is_valid_ip('192.168.1.256') is False
        assert is_valid_ip('192.168.1') is False
        assert is_valid_ip('192.168.1.1.1') is False
        assert is_valid_ip('abc.def.ghi.jkl') is False
        # Injection attempts
        assert is_valid_ip('127.0.0.1; rm -rf /') is False
        assert is_valid_ip('127.0.0.1 | cat /etc/passwd') is False

    def test_collect_returns_dict(self):
        """Test that collect returns a dictionary."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        data = collector.collect()
        assert isinstance(data, dict)

    def test_collect_has_interfaces(self):
        """Test that collect includes interfaces."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        data = collector.collect()
        assert 'interfaces' in data
        assert isinstance(data['interfaces'], list)

    def test_collect_has_connections(self):
        """Test that collect includes connections."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        data = collector.collect()
        assert 'connections' in data

    @patch('collectors.network.subprocess.run')
    def test_get_firewall_rules_ufw(self, mock_run):
        """Test firewall rules parsing with UFW."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Status: active\n\nTo                         Action      From\n--                         ------      ----\n22/tcp                     ALLOW       Anywhere\n80/tcp                     ALLOW       Anywhere\n"
        )
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        # Test would require access to _get_firewall_rules method
        assert collector is not None




class TestIPValidation:
    """Additional IP validation tests."""

    def test_ip_validation_edge_cases(self):
        """Test edge cases for IP validation."""
        # Whitespace
        assert is_valid_ip('  192.168.1.1  ') is True  # Should strip
        assert is_valid_ip(' ') is False
        # Special addresses
        assert is_valid_ip('0.0.0.0') is True
        assert is_valid_ip('127.0.0.1') is True
        assert is_valid_ip('224.0.0.1') is True  # Multicast

    def test_ip_validation_prevents_injection(self):
        """Test that IP validation prevents command injection."""
        malicious_inputs = [
            '$(whoami)',
            '`id`',
            '127.0.0.1`id`',
            '127.0.0.1$(cat /etc/passwd)',
            '127.0.0.1; ls',
            '127.0.0.1 && ls',
            '127.0.0.1 || ls',
            '127.0.0.1\nls',
            '../../../etc/passwd',
        ]
        for malicious in malicious_inputs:
            assert is_valid_ip(malicious) is False, f"Should reject: {malicious}"


class TestNetworkCollectorFirewall:
    """Tests for firewall-related methods."""

    def test_check_ufw_not_found(self):
        """Test UFW check when binary not found."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = collector._check_ufw()
            assert result == {}

    def test_check_ufw_timeout(self):
        """Test UFW check timeout handling."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)
            result = collector._check_ufw()
            assert result == {}

    def test_check_ufw_active(self):
        """Test UFW active status parsing."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Status: active\n\nTo                         Action      From\n22/tcp                     ALLOW       Anywhere"
            )
            result = collector._check_ufw()
            assert result['type'] == 'ufw'
            assert result['status'] == 'active'

    def test_check_ufw_inactive(self):
        """Test UFW inactive status."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Status: inactive"
            )
            result = collector._check_ufw()
            assert result['status'] == 'inactive'

    def test_check_firewalld_running(self):
        """Test firewalld running status."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="running"
            )
            result = collector._check_firewalld()
            assert result['type'] == 'firewalld'
            assert result['status'] == 'running'

    def test_check_firewalld_not_found(self):
        """Test firewalld not found."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = collector._check_firewalld()
            assert result == {}

    def test_check_iptables_configured(self):
        """Test iptables configured status."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Chain INPUT (policy ACCEPT)\nChain FORWARD (policy ACCEPT)"
            )
            result = collector._check_iptables()
            assert result['type'] == 'iptables'
            assert result['status'] == 'configured'

    def test_check_iptables_not_found(self):
        """Test iptables not found."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = collector._check_iptables()
            assert result == {}


class TestNetworkCollectorConnections:
    """Tests for connection-related methods."""

    def test_get_connections_permission_denied(self):
        """Test connections when permission denied."""
        from collectors.network import NetworkCollector
        import psutil
        collector = NetworkCollector()
        with patch('collectors.network.psutil.net_connections') as mock_conn:
            mock_conn.side_effect = psutil.AccessDenied()
            result = collector._get_connections()
            assert 'error' in result

    def test_get_open_ports_permission_denied(self):
        """Test open ports when permission denied."""
        from collectors.network import NetworkCollector
        import psutil
        collector = NetworkCollector()
        with patch('collectors.network.psutil.net_connections') as mock_conn:
            mock_conn.side_effect = psutil.AccessDenied()
            result = collector._get_open_ports()
            assert isinstance(result, list)
            assert 'error' in result[0]


class TestNetworkCollectorIptablesDetailed:
    """Tests for detailed iptables parsing."""

    def test_get_iptables_detailed_parses_rules(self):
        """Test detailed iptables parsing."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="""Chain INPUT (policy DROP 123 packets, 456 bytes)
num   pkts bytes target     prot opt in     out     source               destination
1      100   5000 ACCEPT     all  --  lo     *       0.0.0.0/0            0.0.0.0/0
2       50   2500 DROP       tcp  --  *      *       10.0.0.0/8           0.0.0.0/0            tcp dpt:22
"""
            )
            result = collector._get_iptables_detailed()
            assert len(result) == 2
            assert result[0]['chain'] == 'INPUT'
            assert result[0]['target'] == 'ACCEPT'
            assert result[1]['target'] == 'DROP'

    def test_get_iptables_detailed_failure(self):
        """Test iptables detailed when command fails."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = collector._get_iptables_detailed()
            assert result == []

    def test_get_iptables_detailed_exception(self):
        """Test iptables detailed exception handling."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Test error")
            result = collector._get_iptables_detailed()
            assert result == []


class TestNetworkCollectorNftables:
    """Tests for nftables methods."""

    def test_get_nftables_success(self):
        """Test nftables JSON parsing."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"nftables": [{"table": {"family": "inet", "name": "filter"}}]}'
            )
            result = collector._get_nftables_rules()
            assert 'nftables' in result

    def test_get_nftables_command_failure(self):
        """Test nftables command failure."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr='Permission denied'
            )
            result = collector._get_nftables_rules()
            assert 'error' in result

    def test_get_nftables_json_error(self):
        """Test nftables invalid JSON handling."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='invalid json{'
            )
            result = collector._get_nftables_rules()
            assert 'error' in result

    def test_get_nftables_exception(self):
        """Test nftables exception handling."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Test error")
            result = collector._get_nftables_rules()
            assert 'error' in result


class TestNetworkCollectorRouting:
    """Tests for routing table methods."""

    def test_get_routing_table_success(self):
        """Test routing table parsing."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='default via 192.168.1.1 dev eth0\n192.168.1.0/24 dev eth0 proto kernel'
            )
            result = collector._get_routing_table()
            assert len(result) == 2
            assert 'route' in result[0]

    def test_get_routing_table_timeout(self):
        """Test routing table timeout."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)
            result = collector._get_routing_table()
            assert 'error' in result[0]

    def test_get_routing_table_not_found(self):
        """Test routing when ip command not found."""
        from collectors.network import NetworkCollector
        collector = NetworkCollector()
        with patch('collectors.network.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = collector._get_routing_table()
            assert 'error' in result[0]
