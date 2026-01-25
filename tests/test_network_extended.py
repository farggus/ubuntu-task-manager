"""Extended tests for NetworkCollector."""

import unittest
from unittest.mock import MagicMock, patch

from collectors.fail2ban import is_valid_ip
from collectors.network import NetworkCollector


class TestNetworkCollectorExtended(unittest.TestCase):
    """Extended tests for NetworkCollector functionality."""

    def setUp(self):
        self.collector = NetworkCollector()

    def test_collect_has_routing(self):
        """Test that collect returns routing info."""
        result = self.collector.collect()
        self.assertIn('routing', result)

    def test_collect_has_firewall(self):
        """Test that collect returns firewall info."""
        result = self.collector.collect()
        self.assertIn('firewall', result)

    def test_collect_has_fail2ban(self):
        """Test that collect returns fail2ban info."""
        result = self.collector.collect()
        self.assertIn('fail2ban', result)


class TestInterfaces(unittest.TestCase):
    """Tests for network interfaces collection."""

    def setUp(self):
        self.collector = NetworkCollector()

    def test_get_interfaces_returns_list(self):
        """Test _get_interfaces returns a list."""
        result = self.collector._get_interfaces()
        self.assertIsInstance(result, list)

    def test_interfaces_not_empty(self):
        """Test interfaces list is not empty."""
        result = self.collector._get_interfaces()
        self.assertGreater(len(result), 0)

    def test_interface_has_name(self):
        """Test interface has name."""
        result = self.collector._get_interfaces()
        if result:
            self.assertIn('name', result[0])

    def test_interface_has_addresses(self):
        """Test interface has addresses."""
        result = self.collector._get_interfaces()
        if result:
            self.assertIn('addresses', result[0])


class TestConnections(unittest.TestCase):
    """Tests for network connections collection."""

    def setUp(self):
        self.collector = NetworkCollector()

    def test_get_connections_returns_dict(self):
        """Test _get_connections returns a dictionary."""
        result = self.collector._get_connections()
        self.assertIsInstance(result, dict)

    def test_connections_has_tcp(self):
        """Test connections has 'tcp' key."""
        result = self.collector._get_connections()
        # May have 'error' key if not running as root
        if 'error' not in result:
            self.assertIn('tcp', result)


class TestOpenPorts(unittest.TestCase):
    """Tests for open ports collection."""

    def setUp(self):
        self.collector = NetworkCollector()

    def test_get_open_ports_returns_list(self):
        """Test _get_open_ports returns a list."""
        result = self.collector._get_open_ports()
        self.assertIsInstance(result, list)


class TestFirewall(unittest.TestCase):
    """Tests for firewall rules collection."""

    def setUp(self):
        self.collector = NetworkCollector()

    def test_get_firewall_rules_returns_dict(self):
        """Test _get_firewall_rules returns a dictionary."""
        result = self.collector._get_firewall_rules()
        self.assertIsInstance(result, dict)

    def test_firewall_has_type(self):
        """Test firewall result has 'type' key."""
        result = self.collector._get_firewall_rules()
        self.assertIn('type', result)

    def test_firewall_has_status(self):
        """Test firewall result has 'status' key."""
        result = self.collector._get_firewall_rules()
        self.assertIn('status', result)


class TestUFW(unittest.TestCase):
    """Tests for UFW firewall check."""

    def setUp(self):
        self.collector = NetworkCollector()

    @patch('subprocess.run')
    def test_check_ufw_handles_timeout(self, mock_run):
        """Test handling of ufw timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)
        result = self.collector._check_ufw()
        self.assertEqual(result, {})

    @patch('subprocess.run')
    def test_check_ufw_handles_not_found(self, mock_run):
        """Test handling of ufw not found."""
        mock_run.side_effect = FileNotFoundError
        result = self.collector._check_ufw()
        self.assertEqual(result, {})

    @patch('subprocess.run')
    def test_check_ufw_parses_active(self, mock_run):
        """Test parsing of active ufw status."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Status: active\n[ 1] 22/tcp ALLOW IN Anywhere\n'
        )
        result = self.collector._check_ufw()
        self.assertEqual(result.get('status'), 'active')
        self.assertEqual(result.get('type'), 'ufw')

    @patch('subprocess.run')
    def test_check_ufw_parses_inactive(self, mock_run):
        """Test parsing of inactive ufw status."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Status: inactive\n'
        )
        result = self.collector._check_ufw()
        self.assertEqual(result.get('status'), 'inactive')


class TestFirewalld(unittest.TestCase):
    """Tests for firewalld check."""

    def setUp(self):
        self.collector = NetworkCollector()

    @patch('subprocess.run')
    def test_check_firewalld_handles_timeout(self, mock_run):
        """Test handling of firewall-cmd timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)
        result = self.collector._check_firewalld()
        self.assertEqual(result, {})

    @patch('subprocess.run')
    def test_check_firewalld_handles_not_found(self, mock_run):
        """Test handling of firewall-cmd not found."""
        mock_run.side_effect = FileNotFoundError
        result = self.collector._check_firewalld()
        self.assertEqual(result, {})


class TestIPTables(unittest.TestCase):
    """Tests for iptables check."""

    def setUp(self):
        self.collector = NetworkCollector()

    @patch('subprocess.run')
    def test_check_iptables_handles_timeout(self, mock_run):
        """Test handling of iptables timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)
        result = self.collector._check_iptables()
        self.assertEqual(result, {})

    @patch('subprocess.run')
    def test_check_iptables_handles_permission_denied(self, mock_run):
        """Test handling of iptables permission denied."""
        mock_run.side_effect = PermissionError
        result = self.collector._check_iptables()
        self.assertEqual(result, {})


class TestRouting(unittest.TestCase):
    """Tests for routing table collection."""

    def setUp(self):
        self.collector = NetworkCollector()

    def test_get_routing_table_returns_list(self):
        """Test _get_routing_table returns a list."""
        result = self.collector._get_routing_table()
        self.assertIsInstance(result, list)

    @patch('subprocess.run')
    def test_routing_handles_timeout(self, mock_run):
        """Test handling of ip route timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)
        result = self.collector._get_routing_table()
        self.assertIn('error', result[0])

    @patch('subprocess.run')
    def test_routing_handles_not_found(self, mock_run):
        """Test handling of ip command not found."""
        mock_run.side_effect = FileNotFoundError
        result = self.collector._get_routing_table()
        self.assertIn('error', result[0])


class TestFail2ban(unittest.TestCase):
    """Tests for fail2ban status collection."""

    def setUp(self):
        self.collector = NetworkCollector()

    def test_get_fail2ban_status_returns_dict(self):
        """Test collect returns a dictionary."""
        result = self.collector.fail2ban.collect()
        self.assertIsInstance(result, dict)

    def test_fail2ban_has_installed_key(self):
        """Test fail2ban result has 'installed' key."""
        result = self.collector.fail2ban.collect()
        self.assertIn('installed', result)

    def test_fail2ban_has_running_key(self):
        """Test fail2ban result has 'running' key."""
        result = self.collector.fail2ban.collect()
        self.assertIn('running', result)

    def test_fail2ban_has_jails_key(self):
        """Test fail2ban result has 'jails' key."""
        result = self.collector.fail2ban.collect()
        self.assertIn('jails', result)

    @patch('collectors.fail2ban.subprocess.run')
    def test_fail2ban_handles_timeout(self, mock_run):
        """Test handling of fail2ban-client timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 10)
        result = self.collector.fail2ban.collect()
        self.assertFalse(result['running'])

    @patch('collectors.fail2ban.subprocess.run')
    def test_fail2ban_handles_not_found(self, mock_run):
        """Test handling of fail2ban-client not found."""
        mock_run.side_effect = FileNotFoundError
        result = self.collector.fail2ban.collect()
        self.assertFalse(result['installed'])


class TestJailInfo(unittest.TestCase):
    """Tests for fail2ban jail info."""

    def setUp(self):
        self.collector = NetworkCollector()

    @patch('collectors.fail2ban.subprocess.run')
    def test_get_jail_info_handles_failure(self, mock_run):
        """Test handling of jail info failure."""
        mock_run.return_value = MagicMock(returncode=1)
        result = self.collector.fail2ban._get_jail_info('sshd')
        self.assertIsNone(result)

    @patch('collectors.fail2ban.subprocess.run')
    def test_get_jail_info_parses_output(self, mock_run):
        """Test parsing of jail info."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Status for the jail: sshd\n'
                   'Currently banned: 5\n'
                   'Total banned: 100\n'
                   'Banned IP list: 1.2.3.4 5.6.7.8\n'
        )
        # Mock the bantime call too
        with patch.object(self.collector.fail2ban, '_get_jail_bantime', return_value=600):
            with patch.object(self.collector.fail2ban, '_get_ip_data', return_value={'country': 'US', 'org': 'Test'}):
                with patch.object(self.collector.fail2ban, '_count_ip_attempts', return_value=10):
                    result = self.collector.fail2ban._get_jail_info('sshd')
                    self.assertIsNotNone(result)
                    self.assertEqual(result['name'], 'sshd')


class TestJailBantime(unittest.TestCase):
    """Tests for jail bantime retrieval."""

    def setUp(self):
        self.collector = NetworkCollector()

    @patch('collectors.fail2ban.subprocess.run')
    def test_get_jail_bantime_parses_output(self, mock_run):
        """Test parsing of bantime."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='600\n'
        )
        result = self.collector.fail2ban._get_jail_bantime('sshd')
        self.assertEqual(result, 600)

    @patch('collectors.fail2ban.subprocess.run')
    def test_get_jail_bantime_handles_failure(self, mock_run):
        """Test handling of bantime failure."""
        mock_run.return_value = MagicMock(returncode=1)
        result = self.collector.fail2ban._get_jail_bantime('sshd')
        self.assertEqual(result, 0)


class TestIPValidationExtended(unittest.TestCase):
    """Extended tests for IP validation."""

    def test_valid_ipv4_addresses(self):
        """Test various valid IPv4 addresses."""
        valid_ips = [
            '0.0.0.0',
            '127.0.0.1',
            '192.168.1.1',
            '255.255.255.255',
            '10.0.0.1',
            '172.16.0.1',
        ]
        for ip in valid_ips:
            self.assertTrue(is_valid_ip(ip), f"{ip} should be valid")

    def test_valid_ipv6_addresses(self):
        """Test various valid IPv6 addresses."""
        valid_ips = [
            '::1',
            '::',
            'fe80::1',
            '2001:db8::1',
            '2001:0db8:0000:0000:0000:0000:0000:0001',
        ]
        for ip in valid_ips:
            self.assertTrue(is_valid_ip(ip), f"{ip} should be valid")

    def test_invalid_addresses(self):
        """Test various invalid addresses."""
        invalid_ips = [
            '',
            None,
            '256.1.1.1',
            '1.2.3.4.5',
            'not_an_ip',
            '192.168.1',
            '192.168.1.1.1',
            'localhost',
            'example.com',
            '1.2.3.4; rm -rf /',
            '$(whoami)',
            '`id`',
        ]
        for ip in invalid_ips:
            self.assertFalse(is_valid_ip(ip), f"{ip} should be invalid")


class TestBansDB(unittest.TestCase):
    """Tests for bans database operations."""

    def setUp(self):
        self.collector = NetworkCollector()

    def test_bans_db_initialized(self):
        """Test that IP cache is initialized."""
        self.assertIsInstance(self.collector.fail2ban._ip_cache, dict)


if __name__ == '__main__':
    unittest.main()
