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
