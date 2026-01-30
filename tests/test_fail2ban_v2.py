"""Tests for Fail2banV2Collector - log parser with database integration."""

import gzip
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from collectors.fail2ban_v2 import (
    FAIL2BAN_LOG,
    PATTERNS,
    Fail2banV2Collector,
)
from database.attacks_db import AttacksDatabase


class TestPatterns(unittest.TestCase):
    """Tests for regex patterns."""

    def test_ban_pattern_matches(self):
        """Should match ban log lines."""
        line = "2024-01-15 10:23:45,123 fail2ban.actions [12345]: NOTICE [sshd] Ban 192.168.1.1"
        match = PATTERNS['ban'].match(line)

        self.assertIsNotNone(match)
        self.assertEqual(match.group('timestamp'), "2024-01-15 10:23:45")
        self.assertEqual(match.group('jail'), "sshd")
        self.assertEqual(match.group('ip'), "192.168.1.1")

    def test_unban_pattern_matches(self):
        """Should match unban log lines."""
        line = "2024-01-15 10:23:45,123 fail2ban.actions [12345]: NOTICE [sshd] Unban 192.168.1.1"
        match = PATTERNS['unban'].match(line)

        self.assertIsNotNone(match)
        self.assertEqual(match.group('jail'), "sshd")
        self.assertEqual(match.group('ip'), "192.168.1.1")

    def test_found_pattern_matches(self):
        """Should match 'Found' log lines (failed attempts)."""
        line = "2024-01-15 10:23:45,123 fail2ban.filter [12345]: INFO [sshd] Found 192.168.1.1"
        match = PATTERNS['found'].match(line)

        self.assertIsNotNone(match)
        self.assertEqual(match.group('jail'), "sshd")
        self.assertEqual(match.group('ip'), "192.168.1.1")

    def test_patterns_handle_different_jails(self):
        """Should match various jail names."""
        jails = ["sshd", "recidive", "traefik-auth", "traefik-botsearch"]

        for jail in jails:
            line = f"2024-01-15 10:23:45,123 fail2ban.actions [1]: NOTICE [{jail}] Ban 1.2.3.4"
            match = PATTERNS['ban'].match(line)
            self.assertIsNotNone(match, f"Failed to match jail: {jail}")
            self.assertEqual(match.group('jail'), jail)

    def test_patterns_handle_ipv6(self):
        """Should match IPv6 addresses."""
        line = "2024-01-15 10:23:45,123 fail2ban.actions [1]: NOTICE [sshd] Ban 2001:db8::1"
        match = PATTERNS['ban'].match(line)

        self.assertIsNotNone(match)
        self.assertEqual(match.group('ip'), "2001:db8::1")


class TestFail2banV2CollectorInit(unittest.TestCase):
    """Tests for collector initialization."""

    def test_creates_database_if_not_provided(self):
        """Should create AttacksDatabase if not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(AttacksDatabase, '__init__', return_value=None):
                collector = Fail2banV2Collector()
                # Database should be created
                self.assertIsNotNone(collector._db)

    def test_uses_provided_database(self):
        """Should use provided AttacksDatabase instance."""
        mock_db = MagicMock(spec=AttacksDatabase)
        collector = Fail2banV2Collector(db=mock_db)

        self.assertIs(collector._db, mock_db)

    def test_db_property_returns_database(self):
        """db property should return database instance."""
        mock_db = MagicMock(spec=AttacksDatabase)
        collector = Fail2banV2Collector(db=mock_db)

        self.assertIs(collector.db, mock_db)


class TestParseLine(unittest.TestCase):
    """Tests for _parse_line() method."""

    def setUp(self):
        self.mock_db = MagicMock(spec=AttacksDatabase)
        self.collector = Fail2banV2Collector(db=self.mock_db)

    def test_parses_ban_line(self):
        """Should parse ban event."""
        line = "2024-01-15 10:23:45,123 fail2ban.actions [1]: NOTICE [sshd] Ban 192.168.1.1"

        result = self.collector._parse_line(line)

        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'ban')
        self.assertEqual(result['jail'], 'sshd')
        self.assertEqual(result['ip'], '192.168.1.1')
        self.assertIsNotNone(result['datetime'])

    def test_parses_unban_line(self):
        """Should parse unban event."""
        line = "2024-01-15 10:23:45,123 fail2ban.actions [1]: NOTICE [sshd] Unban 192.168.1.1"

        result = self.collector._parse_line(line)

        self.assertEqual(result['type'], 'unban')

    def test_parses_found_line(self):
        """Should parse found (attempt) event."""
        line = "2024-01-15 10:23:45,123 fail2ban.filter [1]: INFO [sshd] Found 192.168.1.1"

        result = self.collector._parse_line(line)

        self.assertEqual(result['type'], 'found')

    def test_returns_none_for_empty_line(self):
        """Should return None for empty line."""
        result = self.collector._parse_line("")
        self.assertIsNone(result)

    def test_returns_none_for_non_matching_line(self):
        """Should return None for lines that don't match patterns."""
        line = "2024-01-15 10:23:45 Some other log entry"
        result = self.collector._parse_line(line)
        self.assertIsNone(result)


class TestProcessEvent(unittest.TestCase):
    """Tests for _process_event() method."""

    def setUp(self):
        self.mock_db = MagicMock(spec=AttacksDatabase)
        self.mock_db.get_ip.return_value = None  # New IP
        self.collector = Fail2banV2Collector(db=self.mock_db)

    def test_process_ban_event(self):
        """Should record ban in database."""
        event = {'type': 'ban', 'ip': '1.2.3.4', 'jail': 'sshd'}
        stats = {'bans': 0, 'unbans': 0, 'attempts': 0, 'new_ips': 0}

        self.collector._process_event(event, stats)

        self.mock_db.record_ban.assert_called_once()
        self.assertEqual(stats['bans'], 1)
        self.assertEqual(stats['new_ips'], 1)

    def test_process_unban_event(self):
        """Should record unban in database."""
        event = {'type': 'unban', 'ip': '1.2.3.4', 'jail': 'sshd'}
        stats = {'bans': 0, 'unbans': 0, 'attempts': 0, 'new_ips': 0}

        self.collector._process_event(event, stats)

        self.mock_db.record_unban.assert_called_once()
        self.assertEqual(stats['unbans'], 1)

    def test_process_found_event(self):
        """Should record attempt in database."""
        event = {'type': 'found', 'ip': '1.2.3.4', 'jail': 'sshd'}
        stats = {'bans': 0, 'unbans': 0, 'attempts': 0, 'new_ips': 0}

        self.collector._process_event(event, stats)

        self.mock_db.record_attempt.assert_called_once()
        self.assertEqual(stats['attempts'], 1)

    def test_existing_ip_not_counted_as_new(self):
        """Should not increment new_ips for existing IP."""
        self.mock_db.get_ip.return_value = {"some": "data"}  # Existing IP
        event = {'type': 'ban', 'ip': '1.2.3.4', 'jail': 'sshd'}
        stats = {'bans': 0, 'unbans': 0, 'attempts': 0, 'new_ips': 0}

        self.collector._process_event(event, stats)

        self.assertEqual(stats['new_ips'], 0)

    def test_ignores_event_without_ip(self):
        """Should ignore events without IP address."""
        event = {'type': 'ban', 'jail': 'sshd'}  # No IP
        stats = {'bans': 0, 'unbans': 0, 'attempts': 0, 'new_ips': 0}

        self.collector._process_event(event, stats)

        self.mock_db.record_ban.assert_not_called()


class TestGetJailBantime(unittest.TestCase):
    """Tests for _get_jail_bantime() method."""

    def setUp(self):
        self.mock_db = MagicMock(spec=AttacksDatabase)
        self.collector = Fail2banV2Collector(db=self.mock_db)

    def test_recidive_bantime(self):
        """Should return 7 days for recidive."""
        result = self.collector._get_jail_bantime("recidive")
        self.assertEqual(result, 604800)  # 7 days in seconds

    def test_sshd_bantime(self):
        """Should return 10 minutes for sshd."""
        result = self.collector._get_jail_bantime("sshd")
        self.assertEqual(result, 600)

    def test_default_bantime(self):
        """Should return 10 minutes for unknown jail."""
        result = self.collector._get_jail_bantime("unknown-jail")
        self.assertEqual(result, 600)


class TestGetLogFiles(unittest.TestCase):
    """Tests for _get_log_files() method."""

    def setUp(self):
        self.mock_db = MagicMock(spec=AttacksDatabase)
        self.collector = Fail2banV2Collector(db=self.mock_db)

    @patch('collectors.fail2ban_v2.glob.glob')
    def test_sorts_files_correctly(self, mock_glob):
        """Should sort files: rotated (oldest first) then current."""
        mock_glob.return_value = [
            "/var/log/fail2ban.log",
            "/var/log/fail2ban.log.1",
            "/var/log/fail2ban.log.2.gz",
        ]

        result = self.collector._get_log_files()

        # Based on actual sort_key: current log last, rotated sorted by number descending
        # The actual implementation sorts: .2.gz first (oldest), then .1, then current log last
        names = [p.name for p in result]
        self.assertEqual(len(names), 3)
        self.assertIn("fail2ban.log", names)
        self.assertIn("fail2ban.log.1", names)
        self.assertIn("fail2ban.log.2.gz", names)
        # Current log should be last
        self.assertEqual(result[-1].name, "fail2ban.log")

    @patch('collectors.fail2ban_v2.glob.glob')
    def test_returns_empty_when_no_files(self, mock_glob):
        """Should return empty list when no log files found."""
        mock_glob.return_value = []

        result = self.collector._get_log_files()

        self.assertEqual(result, [])


class TestParseSingleLog(unittest.TestCase):
    """Tests for _parse_single_log() method."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mock_db = MagicMock(spec=AttacksDatabase)
        self.mock_db.get_log_position.return_value = None
        self.mock_db.get_ip.return_value = None
        self.collector = Fail2banV2Collector(db=self.mock_db)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_parses_regular_log(self):
        """Should parse regular (non-gzipped) log file."""
        log_path = Path(self.tmpdir) / "fail2ban.log"
        log_content = """2024-01-15 10:00:00,000 fail2ban.actions [1]: NOTICE [sshd] Ban 1.2.3.4
2024-01-15 10:01:00,000 fail2ban.actions [1]: NOTICE [sshd] Unban 1.2.3.4
2024-01-15 10:02:00,000 fail2ban.filter [1]: INFO [sshd] Found 5.6.7.8
"""
        log_path.write_text(log_content)

        result = self.collector._parse_single_log(log_path)

        self.assertEqual(result['bans'], 1)
        self.assertEqual(result['unbans'], 1)
        self.assertEqual(result['attempts'], 1)

    def test_parses_gzipped_log(self):
        """Should parse gzipped log file."""
        log_path = Path(self.tmpdir) / "fail2ban.log.1.gz"
        log_content = "2024-01-15 10:00:00,000 fail2ban.actions [1]: NOTICE [sshd] Ban 1.2.3.4\n"

        with gzip.open(log_path, 'wt') as f:
            f.write(log_content)

        result = self.collector._parse_single_log(log_path)

        self.assertEqual(result['bans'], 1)

    def test_skips_already_parsed_lines(self):
        """Should skip lines already parsed (for current log)."""
        log_path = Path(self.tmpdir) / "fail2ban.log"
        log_content = """2024-01-15 10:00:00,000 fail2ban.actions [1]: NOTICE [sshd] Ban 1.1.1.1
2024-01-15 10:01:00,000 fail2ban.actions [1]: NOTICE [sshd] Ban 2.2.2.2
2024-01-15 10:02:00,000 fail2ban.actions [1]: NOTICE [sshd] Ban 3.3.3.3
"""
        log_path.write_text(log_content)

        # Simulate already parsed 2 lines
        self.mock_db.get_log_position.return_value = {'position': 2}

        result = self.collector._parse_single_log(log_path)

        # Should only count 1 ban (line 3)
        self.assertEqual(result['bans'], 1)

    def test_updates_log_position(self):
        """Should update log position for current log."""
        log_path = Path(self.tmpdir) / "fail2ban.log"
        log_path.write_text("line1\nline2\n")

        self.collector._parse_single_log(log_path)

        self.mock_db.set_log_position.assert_called()


class TestCollect(unittest.TestCase):
    """Tests for collect() method."""

    def setUp(self):
        self.mock_db = MagicMock(spec=AttacksDatabase)
        self.mock_db.get_stats.return_value = {}
        self.mock_db.get_active_bans.return_value = []
        self.mock_db.get_top_threats.return_value = []
        self.collector = Fail2banV2Collector(db=self.mock_db)

    @patch.object(Fail2banV2Collector, '_sync_with_fail2ban')
    @patch.object(Fail2banV2Collector, '_parse_fail2ban_logs')
    def test_returns_success_result(self, mock_parse, mock_sync):
        """Should return success result dict."""
        mock_parse.return_value = {
            'bans': 5, 'unbans': 3, 'attempts': 10,
            'new_ips': 2, 'logs_parsed': ['/var/log/fail2ban.log']
        }
        mock_sync.return_value = {'synced': 1}

        result = self.collector.collect()

        self.assertTrue(result['success'])
        self.assertEqual(result['bans_found'], 5)
        self.assertEqual(result['unbans_found'], 3)
        self.assertEqual(result['attempts_found'], 10)
        self.assertEqual(result['new_ips'], 2)
        self.mock_db.save.assert_called_once()

    @patch.object(Fail2banV2Collector, '_parse_fail2ban_logs')
    def test_handles_exception(self, mock_parse):
        """Should handle exceptions gracefully."""
        mock_parse.side_effect = Exception("Parse error")

        result = self.collector.collect()

        self.assertFalse(result['success'])
        self.assertIn('error', result)


class TestGetSummary(unittest.TestCase):
    """Tests for get_summary() method."""

    def test_returns_summary_dict(self):
        """Should return summary from database."""
        mock_db = MagicMock(spec=AttacksDatabase)
        mock_db.get_stats.return_value = {
            'total_ips': 100,
            'total_attempts': 500,
            'total_bans': 50,
            'top_country': 'CN',
            'top_org': 'DigitalOcean'
        }
        mock_db.get_active_bans.return_value = [{'ip': '1.2.3.4'}]
        mock_db.get_top_threats.return_value = [
            ('1.2.3.4', {'danger_score': 80, 'attempts': {'total': 50}, 'bans': {'total': 5}})
        ]
        collector = Fail2banV2Collector(db=mock_db)

        result = collector.get_summary()

        self.assertEqual(result['total_ips'], 100)
        self.assertEqual(result['total_attempts'], 500)
        self.assertEqual(result['active_bans'], 1)
        self.assertEqual(len(result['top_threats']), 1)


class TestSyncWithFail2ban(unittest.TestCase):
    """Tests for _sync_with_fail2ban() method."""

    def setUp(self):
        self.mock_db = MagicMock(spec=AttacksDatabase)
        self.mock_db.get_all_ips.return_value = {}
        self.collector = Fail2banV2Collector(db=self.mock_db)

    @patch('collectors.fail2ban_client.Fail2banClient')
    def test_skips_when_not_running(self, mock_client_class):
        """Should skip sync when fail2ban not running."""
        mock_client = MagicMock()
        mock_client.is_running.return_value = False
        mock_client_class.return_value = mock_client

        result = self.collector._sync_with_fail2ban()

        self.assertEqual(result['synced'], 0)

    @patch('collectors.fail2ban_client.Fail2banClient')
    def test_activates_banned_ips(self, mock_client_class):
        """Should activate IPs that are actually banned."""
        mock_client = MagicMock()
        mock_client.is_running.return_value = True
        mock_client.get_all_banned_ips.return_value = {'sshd': ['1.2.3.4']}
        mock_client_class.return_value = mock_client

        # Set up internal _data structure for the collector's db
        self.collector._db._data = {'ips': {
            '1.2.3.4': {'bans': {'active': False}}
        }}
        self.collector._db.get_all_ips.return_value = self.collector._db._data['ips']
        self.collector._db._create_empty_ip_record.return_value = {'bans': {'active': False}}

        result = self.collector._sync_with_fail2ban()

        self.assertEqual(result['activated'], 1)
        self.assertTrue(self.collector._db._data['ips']['1.2.3.4']['bans']['active'])


if __name__ == '__main__':
    unittest.main()
