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


class TestWhitelist(unittest.TestCase):
    """Tests for whitelist functionality."""

    def setUp(self):
        """Set up test collector with mocked file operations."""
        with patch.object(Fail2banCollector, '_load_ip_cache'):
            with patch.object(Fail2banCollector, '_load_whitelist'):
                self.collector = Fail2banCollector()
                self.collector._whitelist = []
                self.collector._ip_cache = {}

    def test_get_whitelist_returns_copy(self):
        """get_whitelist should return a copy of whitelist."""
        self.collector._whitelist = ['1.2.3.4']
        result = self.collector.get_whitelist()
        result.append('5.6.7.8')
        self.assertEqual(len(self.collector._whitelist), 1)

    def test_add_to_whitelist_valid_ip(self):
        """Should add valid IP to whitelist."""
        with patch.object(self.collector, '_save_whitelist'):
            result = self.collector.add_to_whitelist('192.168.1.1')
            self.assertTrue(result)
            self.assertIn('192.168.1.1', self.collector._whitelist)

    def test_add_to_whitelist_invalid_ip(self):
        """Should reject invalid IP."""
        result = self.collector.add_to_whitelist('invalid')
        self.assertFalse(result)
        self.assertEqual(len(self.collector._whitelist), 0)

    def test_add_to_whitelist_duplicate(self):
        """Should not add duplicate IP."""
        self.collector._whitelist = ['1.2.3.4']
        with patch.object(self.collector, '_save_whitelist'):
            result = self.collector.add_to_whitelist('1.2.3.4')
            self.assertFalse(result)
            self.assertEqual(len(self.collector._whitelist), 1)

    def test_remove_from_whitelist(self):
        """Should remove IP from whitelist."""
        self.collector._whitelist = ['1.2.3.4', '5.6.7.8']
        with patch.object(self.collector, '_save_whitelist'):
            result = self.collector.remove_from_whitelist('1.2.3.4')
            self.assertTrue(result)
            self.assertNotIn('1.2.3.4', self.collector._whitelist)

    def test_remove_from_whitelist_not_exists(self):
        """Should return False if IP not in whitelist."""
        self.collector._whitelist = []
        result = self.collector.remove_from_whitelist('1.2.3.4')
        self.assertFalse(result)

    def test_is_whitelisted(self):
        """Should check if IP is whitelisted."""
        self.collector._whitelist = ['1.2.3.4']
        self.assertTrue(self.collector.is_whitelisted('1.2.3.4'))
        self.assertFalse(self.collector.is_whitelisted('5.6.7.8'))


class TestParseJailList(unittest.TestCase):
    """Tests for _parse_jail_list method."""

    def setUp(self):
        with patch.object(Fail2banCollector, '_load_ip_cache'):
            with patch.object(Fail2banCollector, '_load_whitelist'):
                self.collector = Fail2banCollector()

    def test_parses_single_jail(self):
        """Should parse single jail."""
        output = "Status\nJail list:\tsshd"
        result = self.collector._parse_jail_list(output)
        self.assertEqual(result, ['sshd'])

    def test_parses_multiple_jails(self):
        """Should parse multiple jails."""
        output = "Status\nJail list:\tsshd, recidive, nginx-http-auth"
        result = self.collector._parse_jail_list(output)
        self.assertEqual(result, ['sshd', 'recidive', 'nginx-http-auth'])

    def test_empty_jail_list(self):
        """Should handle empty jail list."""
        output = "Status\nJail list:\t"
        result = self.collector._parse_jail_list(output)
        self.assertEqual(result, [])

    def test_no_jail_list_line(self):
        """Should return empty if no Jail list line."""
        output = "Status\nSome other output"
        result = self.collector._parse_jail_list(output)
        self.assertEqual(result, [])


class TestExtractJailFromLogLine(unittest.TestCase):
    """Tests for _extract_jail_from_log_line method."""

    def setUp(self):
        with patch.object(Fail2banCollector, '_load_ip_cache'):
            with patch.object(Fail2banCollector, '_load_whitelist'):
                self.collector = Fail2banCollector()

    def test_extracts_jail_name(self):
        """Should extract jail name from log line parts."""
        parts = ['2024-01-01', '12:00:00', 'fail2ban', '[sshd]', 'Unban', '1.2.3.4']
        result = self.collector._extract_jail_from_log_line(parts)
        self.assertEqual(result, 'sshd')

    def test_returns_unknown_if_not_found(self):
        """Should return 'unknown' if jail not found."""
        parts = ['2024-01-01', '12:00:00', 'Unban', '1.2.3.4']
        result = self.collector._extract_jail_from_log_line(parts)
        self.assertEqual(result, 'unknown')


class TestBanUnbanIP(unittest.TestCase):
    """Tests for ban_ip and unban_ip methods."""

    def setUp(self):
        with patch.object(Fail2banCollector, '_load_ip_cache'):
            with patch.object(Fail2banCollector, '_load_whitelist'):
                self.collector = Fail2banCollector()

    def test_ban_ip_invalid_ip(self):
        """Should reject invalid IP for ban."""
        result = self.collector.ban_ip('invalid_ip')
        self.assertFalse(result)

    @patch('collectors.fail2ban.subprocess.run')
    def test_ban_ip_success(self, mock_run):
        """Should successfully ban valid IP."""
        mock_run.return_value = MagicMock(returncode=0)
        result = self.collector.ban_ip('1.2.3.4', 'sshd')
        self.assertTrue(result)

    @patch('collectors.fail2ban.subprocess.run')
    def test_ban_ip_sets_recidive_bantime(self, mock_run):
        """Should set bantime for recidive jail."""
        mock_run.return_value = MagicMock(returncode=0)
        self.collector.ban_ip('1.2.3.4', 'recidive')
        # Should be called twice: set bantime + banip
        self.assertEqual(mock_run.call_count, 2)

    @patch('collectors.fail2ban.subprocess.run')
    def test_ban_ip_handles_error(self, mock_run):
        """Should handle ban errors."""
        mock_run.side_effect = Exception("Test error")
        result = self.collector.ban_ip('1.2.3.4')
        self.assertFalse(result)

    def test_unban_ip_invalid_ip(self):
        """Should reject invalid IP for unban."""
        result = self.collector.unban_ip('invalid_ip')
        self.assertFalse(result)

    @patch('collectors.fail2ban.subprocess.run')
    def test_unban_ip_success(self, mock_run):
        """Should successfully unban IP."""
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        result = self.collector.unban_ip('1.2.3.4')
        self.assertTrue(result)

    @patch('collectors.fail2ban.subprocess.run')
    def test_unban_ip_not_banned(self, mock_run):
        """Should return True if IP was not banned."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout='',
            stderr='1.2.3.4 is not banned'
        )
        result = self.collector.unban_ip('1.2.3.4')
        self.assertTrue(result)

    @patch('collectors.fail2ban.subprocess.run')
    def test_unban_ip_with_jail(self, mock_run):
        """Should unban from specific jail."""
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        self.collector.unban_ip('1.2.3.4', jail='sshd')
        call_args = mock_run.call_args[0][0]
        self.assertIn('sshd', call_args)

    @patch('collectors.fail2ban.subprocess.run')
    def test_unban_ip_timeout(self, mock_run):
        """Should handle timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)
        result = self.collector.unban_ip('1.2.3.4')
        self.assertFalse(result)


class TestCleanup(unittest.TestCase):
    """Tests for cleanup method."""

    def setUp(self):
        with patch.object(Fail2banCollector, '_load_ip_cache'):
            with patch.object(Fail2banCollector, '_load_whitelist'):
                self.collector = Fail2banCollector()

    @patch('collectors.fail2ban.os.path.exists')
    @patch('collectors.fail2ban.os.remove')
    def test_cleanup_removes_slow_bots_file(self, mock_remove, mock_exists):
        """Should remove slow bots file if exists."""
        mock_exists.return_value = True
        self.collector.cleanup()
        mock_remove.assert_called_once()

    @patch('collectors.fail2ban.os.path.exists')
    def test_cleanup_does_nothing_if_no_file(self, mock_exists):
        """Should do nothing if file doesn't exist."""
        mock_exists.return_value = False
        self.collector.cleanup()  # Should not raise


class TestGetIpData(unittest.TestCase):
    """Tests for _get_ip_data method."""

    def setUp(self):
        with patch.object(Fail2banCollector, '_load_ip_cache'):
            with patch.object(Fail2banCollector, '_load_whitelist'):
                self.collector = Fail2banCollector()
                self.collector._ip_cache = {}

    def test_returns_unknown_for_invalid_ip(self):
        """Should return unknown for invalid IP."""
        result = self.collector._get_ip_data('invalid')
        self.assertEqual(result['country'], 'Unknown')
        self.assertEqual(result['org'], 'Unknown')

    def test_returns_cached_data(self):
        """Should return cached data if available and fresh."""
        import time
        self.collector._ip_cache['1.2.3.4'] = {
            'country': 'US',
            'org': 'Test Org',
            'attempts': 5,
            'last_updated': time.time()
        }
        result = self.collector._get_ip_data('1.2.3.4')
        self.assertEqual(result['country'], 'US')
        self.assertEqual(result['org'], 'Test Org')


if __name__ == '__main__':
    unittest.main()
