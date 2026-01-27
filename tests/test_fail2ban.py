"""Tests for Fail2banCollector."""

import unittest
from unittest.mock import MagicMock, patch

from collectors.fail2ban import Fail2banCollector, is_valid_ip


class TestFail2banCollector(unittest.TestCase):
    """Tests for Fail2banCollector functionality."""

    def setUp(self):
        self.collector = Fail2banCollector()

    def test_collect_returns_dict(self):
        """Test collect returns a dictionary."""
        result = self.collector.collect()
        self.assertIsInstance(result, dict)

    def test_fail2ban_has_installed_key(self):
        """Test fail2ban result has 'installed' key."""
        result = self.collector.collect()
        self.assertIn('installed', result)

    def test_fail2ban_has_running_key(self):
        """Test fail2ban result has 'running' key."""
        result = self.collector.collect()
        self.assertIn('running', result)

    def test_fail2ban_has_jails_key(self):
        """Test fail2ban result has 'jails' key."""
        result = self.collector.collect()
        self.assertIn('jails', result)

    @patch('collectors.fail2ban.subprocess.run')
    def test_fail2ban_handles_timeout(self, mock_run):
        """Test handling of fail2ban-client timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 10)
        result = self.collector.collect()
        self.assertFalse(result['running'])

    @patch('collectors.fail2ban.subprocess.run')
    def test_fail2ban_handles_not_found(self, mock_run):
        """Test handling of fail2ban-client not found."""
        mock_run.side_effect = FileNotFoundError
        result = self.collector.collect()
        self.assertFalse(result['installed'])

    @patch('collectors.fail2ban.subprocess.run')
    def test_get_jail_info_handles_failure(self, mock_run):
        """Test handling of jail info failure."""
        mock_run.return_value = MagicMock(returncode=1)
        result = self.collector._get_jail_info('sshd')
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
        with patch.object(self.collector, '_get_jail_bantime', return_value=600):
            with patch.object(self.collector, '_get_ip_data', return_value={'country': 'US', 'org': 'Test'}):
                with patch.object(self.collector, '_count_ip_attempts', return_value=10):
                    result = self.collector._get_jail_info('sshd')
                    self.assertIsNotNone(result)
                    self.assertEqual(result['name'], 'sshd')

    @patch('collectors.fail2ban.subprocess.run')
    def test_get_jail_bantime_parses_output(self, mock_run):
        """Test parsing of bantime."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='600\n'
        )
        result = self.collector._get_jail_bantime('sshd')
        self.assertEqual(result, 600)

    @patch('collectors.fail2ban.subprocess.run')
    def test_get_jail_bantime_handles_failure(self, mock_run):
        """Test handling of bantime failure."""
        mock_run.return_value = MagicMock(returncode=1)
        result = self.collector._get_jail_bantime('sshd')
        self.assertEqual(result, 0)

    def test_bans_db_initialized(self):
        """Test that IP cache is initialized."""
        self.assertIsInstance(self.collector._ip_cache, dict)

class TestIPValidation(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
