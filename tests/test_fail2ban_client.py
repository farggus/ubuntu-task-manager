"""Tests for Fail2banClient - fail2ban-client wrapper."""

import unittest
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from collectors.fail2ban_client import Fail2banClient


class TestFail2banClientInit(unittest.TestCase):
    """Tests for Fail2banClient initialization."""

    def test_default_timeout(self):
        """Default timeout should be 10 seconds."""
        client = Fail2banClient()
        self.assertEqual(client.timeout, 10)

    def test_custom_timeout(self):
        """Custom timeout should be used."""
        client = Fail2banClient(timeout=30)
        self.assertEqual(client.timeout, 30)

    def test_initial_state(self):
        """Initial cached state should be None."""
        client = Fail2banClient()
        self.assertIsNone(client._installed)
        self.assertIsNone(client._running)


class TestIsInstalled(unittest.TestCase):
    """Tests for is_installed() method."""

    @patch('collectors.fail2ban_client.subprocess.run')
    def test_installed_when_which_succeeds(self, mock_run):
        """Should return True when 'which fail2ban-client' succeeds."""
        mock_run.return_value = MagicMock(returncode=0)
        client = Fail2banClient()

        result = client.is_installed()

        self.assertTrue(result)
        mock_run.assert_called_once()
        self.assertTrue(client._installed)  # Should be cached

    @patch('collectors.fail2ban_client.subprocess.run')
    def test_not_installed_when_which_fails(self, mock_run):
        """Should return False when 'which fail2ban-client' fails."""
        mock_run.return_value = MagicMock(returncode=1)
        client = Fail2banClient()

        result = client.is_installed()

        self.assertFalse(result)
        self.assertFalse(client._installed)

    @patch('collectors.fail2ban_client.subprocess.run')
    def test_cached_result(self, mock_run):
        """Should return cached result on second call."""
        mock_run.return_value = MagicMock(returncode=0)
        client = Fail2banClient()

        client.is_installed()
        client.is_installed()  # Second call

        # Should only call subprocess once due to caching
        mock_run.assert_called_once()

    @patch('collectors.fail2ban_client.subprocess.run')
    def test_exception_returns_false(self, mock_run):
        """Should return False when exception occurs."""
        mock_run.side_effect = Exception("Command failed")
        client = Fail2banClient()

        result = client.is_installed()

        self.assertFalse(result)


class TestRunCommand(unittest.TestCase):
    """Tests for _run_command() internal method."""

    @patch('collectors.fail2ban_client.subprocess.run')
    def test_successful_command(self, mock_run):
        """Should return output on success."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="  output with spaces  \n",
            stderr=""
        )
        client = Fail2banClient()

        result = client._run_command(["status"])

        self.assertEqual(result, "output with spaces")
        mock_run.assert_called_with(
            ["sudo", "fail2ban-client", "status"],
            capture_output=True,
            text=True,
            timeout=10
        )

    @patch('collectors.fail2ban_client.subprocess.run')
    def test_failed_command(self, mock_run):
        """Should return None on non-zero exit code."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error message"
        )
        client = Fail2banClient()

        result = client._run_command(["status"])

        self.assertIsNone(result)

    @patch('collectors.fail2ban_client.subprocess.run')
    def test_timeout_returns_none(self, mock_run):
        """Should return None on timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 10)
        client = Fail2banClient()

        result = client._run_command(["status"])

        self.assertIsNone(result)

    @patch('collectors.fail2ban_client.subprocess.run')
    def test_exception_returns_none(self, mock_run):
        """Should return None on exception."""
        mock_run.side_effect = OSError("Permission denied")
        client = Fail2banClient()

        result = client._run_command(["status"])

        self.assertIsNone(result)


class TestIsRunning(unittest.TestCase):
    """Tests for is_running() method."""

    @patch.object(Fail2banClient, '_run_command')
    def test_running_when_output_contains_jail(self, mock_cmd):
        """Should return True when output contains 'Number of jail'."""
        mock_cmd.return_value = "Status\n|- Number of jail:\t3\n`- Jail list:\tsshd, recidive"
        client = Fail2banClient()

        result = client.is_running()

        self.assertTrue(result)
        self.assertTrue(client._running)

    @patch.object(Fail2banClient, '_run_command')
    def test_not_running_when_output_none(self, mock_cmd):
        """Should return False when command returns None."""
        mock_cmd.return_value = None
        client = Fail2banClient()

        result = client.is_running()

        self.assertFalse(result)

    @patch.object(Fail2banClient, '_run_command')
    def test_not_running_when_no_jail_keyword(self, mock_cmd):
        """Should return False when output doesn't contain 'Number of jail'."""
        mock_cmd.return_value = "Some other output"
        client = Fail2banClient()

        result = client.is_running()

        self.assertFalse(result)


class TestGetJails(unittest.TestCase):
    """Tests for get_jails() method."""

    @patch.object(Fail2banClient, '_run_command')
    def test_parses_jail_list(self, mock_cmd):
        """Should parse comma-separated jail list."""
        mock_cmd.return_value = "Status\n|- Number of jail:\t3\n`- Jail list:\tsshd, recidive, traefik-auth"
        client = Fail2banClient()

        result = client.get_jails()

        self.assertEqual(result, ["sshd", "recidive", "traefik-auth"])

    @patch.object(Fail2banClient, '_run_command')
    def test_empty_list_when_no_output(self, mock_cmd):
        """Should return empty list when command fails."""
        mock_cmd.return_value = None
        client = Fail2banClient()

        result = client.get_jails()

        self.assertEqual(result, [])

    @patch.object(Fail2banClient, '_run_command')
    def test_empty_list_when_no_match(self, mock_cmd):
        """Should return empty list when regex doesn't match."""
        mock_cmd.return_value = "Invalid output format"
        client = Fail2banClient()

        result = client.get_jails()

        self.assertEqual(result, [])

    @patch.object(Fail2banClient, '_run_command')
    def test_single_jail(self, mock_cmd):
        """Should handle single jail correctly."""
        mock_cmd.return_value = "Status\n`- Jail list:\tsshd"
        client = Fail2banClient()

        result = client.get_jails()

        self.assertEqual(result, ["sshd"])


class TestGetJailStatus(unittest.TestCase):
    """Tests for get_jail_status() method."""

    @patch.object(Fail2banClient, '_run_command')
    def test_parses_full_status(self, mock_cmd):
        """Should parse all status fields."""
        mock_cmd.return_value = """Status for the jail: sshd
|- Filter
|  |- Currently failed:\t5
|  `- Total failed:\t100
`- Actions
   |- Currently banned:\t3
   |- Total banned:\t50
   `- Banned IP list:\t1.2.3.4 5.6.7.8 9.10.11.12"""
        client = Fail2banClient()

        result = client.get_jail_status("sshd")

        self.assertEqual(result["name"], "sshd")
        self.assertEqual(result["currently_failed"], 5)
        self.assertEqual(result["total_failed"], 100)
        self.assertEqual(result["currently_banned"], 3)
        self.assertEqual(result["total_banned"], 50)
        self.assertEqual(result["banned_ips"], ["1.2.3.4", "5.6.7.8", "9.10.11.12"])

    @patch.object(Fail2banClient, '_run_command')
    def test_empty_dict_when_no_output(self, mock_cmd):
        """Should return empty dict when command fails."""
        mock_cmd.return_value = None
        client = Fail2banClient()

        result = client.get_jail_status("sshd")

        self.assertEqual(result, {})

    @patch.object(Fail2banClient, '_run_command')
    def test_empty_banned_list(self, mock_cmd):
        """Should handle empty banned IP list."""
        mock_cmd.return_value = """Status for the jail: sshd
|- Filter
|  |- Currently failed:\t0
|  `- Total failed:\t10
`- Actions
   |- Currently banned:\t0
   |- Total banned:\t10
   `- Banned IP list:\t"""
        client = Fail2banClient()

        result = client.get_jail_status("sshd")

        self.assertEqual(result["banned_ips"], [])
        self.assertEqual(result["currently_banned"], 0)


class TestGetJailConfig(unittest.TestCase):
    """Tests for get_jail_config() method."""

    @patch.object(Fail2banClient, '_run_command')
    def test_parses_config_values(self, mock_cmd):
        """Should parse findtime, bantime, maxretry."""
        mock_cmd.side_effect = ["600", "3600", "5"]
        client = Fail2banClient()

        result = client.get_jail_config("sshd")

        self.assertEqual(result["findtime"], 600)
        self.assertEqual(result["bantime"], 3600)
        self.assertEqual(result["maxretry"], 5)

    @patch.object(Fail2banClient, '_run_command')
    def test_none_values_on_failure(self, mock_cmd):
        """Should have None values when commands fail."""
        mock_cmd.return_value = None
        client = Fail2banClient()

        result = client.get_jail_config("sshd")

        self.assertIsNone(result["findtime"])
        self.assertIsNone(result["bantime"])
        self.assertIsNone(result["maxretry"])


class TestBanUnbanIP(unittest.TestCase):
    """Tests for ban_ip() and unban_ip() methods."""

    @patch.object(Fail2banClient, '_run_command')
    def test_ban_ip_success(self, mock_cmd):
        """Should return True on successful ban."""
        mock_cmd.return_value = "1"  # Success output
        client = Fail2banClient()

        result = client.ban_ip("1.2.3.4", "sshd")

        self.assertTrue(result)
        mock_cmd.assert_called_with(["set", "sshd", "banip", "1.2.3.4"])

    @patch.object(Fail2banClient, '_run_command')
    def test_ban_ip_default_jail(self, mock_cmd):
        """Should use 'recidive' as default jail."""
        mock_cmd.return_value = "1"
        client = Fail2banClient()

        client.ban_ip("1.2.3.4")

        mock_cmd.assert_called_with(["set", "recidive", "banip", "1.2.3.4"])

    @patch.object(Fail2banClient, '_run_command')
    def test_ban_ip_failure(self, mock_cmd):
        """Should return False on failed ban."""
        mock_cmd.return_value = None
        client = Fail2banClient()

        result = client.ban_ip("1.2.3.4", "sshd")

        self.assertFalse(result)

    @patch.object(Fail2banClient, '_run_command')
    def test_unban_ip_specific_jail(self, mock_cmd):
        """Should unban from specific jail."""
        mock_cmd.return_value = "1"
        client = Fail2banClient()

        result = client.unban_ip("1.2.3.4", "sshd")

        self.assertTrue(result)
        mock_cmd.assert_called_with(["set", "sshd", "unbanip", "1.2.3.4"])

    @patch.object(Fail2banClient, '_run_command')
    def test_unban_ip_all_jails(self, mock_cmd):
        """Should unban from all jails when jail is None."""
        mock_cmd.return_value = "1"
        client = Fail2banClient()

        result = client.unban_ip("1.2.3.4")

        self.assertTrue(result)
        mock_cmd.assert_called_with(["unban", "1.2.3.4"])


class TestGetAllBannedIPs(unittest.TestCase):
    """Tests for get_all_banned_ips() method."""

    @patch.object(Fail2banClient, 'get_jail_status')
    @patch.object(Fail2banClient, 'get_jails')
    def test_aggregates_banned_ips(self, mock_jails, mock_status):
        """Should aggregate banned IPs from all jails."""
        mock_jails.return_value = ["sshd", "recidive"]
        mock_status.side_effect = [
            {"banned_ips": ["1.2.3.4", "5.6.7.8"]},
            {"banned_ips": ["9.10.11.12"]},
        ]
        client = Fail2banClient()

        result = client.get_all_banned_ips()

        self.assertEqual(result, {
            "sshd": ["1.2.3.4", "5.6.7.8"],
            "recidive": ["9.10.11.12"],
        })

    @patch.object(Fail2banClient, 'get_jail_status')
    @patch.object(Fail2banClient, 'get_jails')
    def test_skips_empty_jails(self, mock_jails, mock_status):
        """Should skip jails with no banned IPs."""
        mock_jails.return_value = ["sshd", "recidive"]
        mock_status.side_effect = [
            {"banned_ips": ["1.2.3.4"]},
            {"banned_ips": []},  # Empty
        ]
        client = Fail2banClient()

        result = client.get_all_banned_ips()

        self.assertEqual(result, {"sshd": ["1.2.3.4"]})


class TestGetSummary(unittest.TestCase):
    """Tests for get_summary() method."""

    @patch.object(Fail2banClient, 'is_running')
    @patch.object(Fail2banClient, 'is_installed')
    @patch.object(Fail2banClient, 'get_jail_status')
    @patch.object(Fail2banClient, 'get_jails')
    def test_summary_structure(self, mock_jails, mock_status, mock_installed, mock_running):
        """Should return complete summary dict."""
        mock_jails.return_value = ["sshd", "recidive"]
        mock_status.side_effect = [
            {"currently_banned": 3},
            {"currently_banned": 5},
        ]
        mock_installed.return_value = True
        mock_running.return_value = True
        client = Fail2banClient()

        result = client.get_summary()

        self.assertEqual(result["installed"], True)
        self.assertEqual(result["running"], True)
        self.assertEqual(result["jails_count"], 2)
        self.assertEqual(result["jails_with_bans"], 2)
        self.assertEqual(result["total_banned"], 8)
        self.assertEqual(result["jails"], ["sshd", "recidive"])


if __name__ == '__main__':
    unittest.main()
