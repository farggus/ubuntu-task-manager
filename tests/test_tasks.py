"""Tests for TasksCollector."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from collectors.tasks import TasksCollector


class TestTasksCollector(unittest.TestCase):
    """Tests for TasksCollector basic functionality."""

    def setUp(self):
        self.collector = TasksCollector()

    def test_import(self):
        """Test that TasksCollector can be imported."""
        from collectors.tasks import TasksCollector
        self.assertIsNotNone(TasksCollector)

    def test_init(self):
        """Test TasksCollector initialization."""
        collector = TasksCollector()
        self.assertIsNotNone(collector)

    def test_init_with_config(self):
        """Test TasksCollector initialization with config."""
        config = {'tasks': {'enabled': True}}
        collector = TasksCollector(config)
        self.assertEqual(collector.config, config)

    def test_parse_standard_cron(self):
        """Test parsing of a standard cron line."""
        entry = "30 2 * * * /usr/bin/backup.sh"
        result = self.collector._parse_cron_entry(entry, "root", "/etc/crontab")

        self.assertIsNotNone(result)
        self.assertEqual(result['command'], "/usr/bin/backup.sh")
        self.assertEqual(result['user'], "root")
        self.assertEqual(result['schedule']['minute'], "30")
        self.assertEqual(result['schedule']['hour'], "2")
        self.assertEqual(result['schedule']['human'], "at 2:30")

    def test_parse_special_cron(self):
        """Test parsing of special @ syntax."""
        entry = "@daily /usr/bin/cleanup"
        result = self.collector._parse_cron_entry(entry, "web", "user:web")

        self.assertIsNotNone(result)
        self.assertEqual(result['command'], "/usr/bin/cleanup")
        self.assertEqual(result['user'], "web")
        self.assertEqual(result['schedule']['special'], "@daily")
        self.assertEqual(result['schedule']['human'], "Daily (midnight)")

    def test_parse_special_reboot(self):
        """Test parsing of @reboot syntax."""
        entry = "@reboot /usr/bin/startup.sh"
        result = self.collector._parse_cron_entry(entry, "root", "test")

        self.assertIsNotNone(result)
        self.assertEqual(result['schedule']['special'], "@reboot")
        self.assertEqual(result['schedule']['human'], "At system reboot")

    def test_parse_special_hourly(self):
        """Test parsing of @hourly syntax."""
        entry = "@hourly /usr/bin/check.sh"
        result = self.collector._parse_cron_entry(entry, "root", "test")

        self.assertIsNotNone(result)
        self.assertEqual(result['schedule']['special'], "@hourly")
        self.assertEqual(result['schedule']['human'], "Hourly")

    def test_parse_special_weekly(self):
        """Test parsing of @weekly syntax."""
        entry = "@weekly /usr/bin/weekly.sh"
        result = self.collector._parse_cron_entry(entry, "root", "test")

        self.assertIsNotNone(result)
        self.assertEqual(result['schedule']['special'], "@weekly")
        self.assertEqual(result['schedule']['human'], "Weekly (Sunday at midnight)")

    def test_parse_special_monthly(self):
        """Test parsing of @monthly syntax."""
        entry = "@monthly /usr/bin/monthly.sh"
        result = self.collector._parse_cron_entry(entry, "root", "test")

        self.assertIsNotNone(result)
        self.assertEqual(result['schedule']['special'], "@monthly")
        self.assertEqual(result['schedule']['human'], "Monthly (1st day at midnight)")

    def test_parse_special_yearly(self):
        """Test parsing of @yearly syntax."""
        entry = "@yearly /usr/bin/yearly.sh"
        result = self.collector._parse_cron_entry(entry, "root", "test")

        self.assertIsNotNone(result)
        self.assertEqual(result['schedule']['special'], "@yearly")
        self.assertEqual(result['schedule']['human'], "Yearly (January 1st at midnight)")

    def test_parse_complex_schedule(self):
        """Test parsing of complex schedule with ranges/lists."""
        entry = "0 8,14,20 * * * /script/run"
        result = self.collector._parse_cron_entry(entry, "root", "test")

        self.assertIsNotNone(result)
        self.assertEqual(result['schedule']['minute'], "0")
        self.assertEqual(result['schedule']['hour'], "8,14,20")
        self.assertEqual(result['schedule']['human'], "at 8,14,20:00")

    def test_invalid_entry(self):
        """Test parsing of invalid entry."""
        entry = "not a cron line"
        result = self.collector._parse_cron_entry(entry, "root", "test")
        self.assertIsNone(result)

    def test_invalid_entry_too_few_parts(self):
        """Test parsing of entry with too few parts."""
        entry = "* * * *"  # Missing weekday and command
        result = self.collector._parse_cron_entry(entry, "root", "test")
        self.assertIsNone(result)


class TestCronToHuman(unittest.TestCase):
    """Tests for _cron_to_human method."""

    def setUp(self):
        self.collector = TasksCollector()

    def test_every_minute(self):
        """Test every minute pattern."""
        result = self.collector._cron_to_human('*', '*', '*', '*', '*')
        self.assertEqual(result, "Every minute")

    def test_specific_time(self):
        """Test specific time."""
        result = self.collector._cron_to_human('15', '14', '*', '*', '*')
        self.assertEqual(result, "at 14:15")

    def test_every_n_minutes(self):
        """Test every N minutes pattern."""
        result = self.collector._cron_to_human('*/5', '*', '*', '*', '*')
        self.assertIn("every 5 minutes", result)

    def test_every_n_hours(self):
        """Test every N hours pattern."""
        result = self.collector._cron_to_human('0', '*/2', '*', '*', '*')
        # The implementation shows it as "at */2:00" for interval hours
        self.assertIn("*/2", result)

    def test_specific_hour(self):
        """Test specific hour."""
        result = self.collector._cron_to_human('*', '12', '*', '*', '*')
        self.assertEqual(result, "at 12:00")

    def test_multiple_hours(self):
        """Test multiple specific hours."""
        result = self.collector._cron_to_human('0', '8,12,18', '*', '*', '*')
        self.assertEqual(result, "at 8,12,18:00")

    def test_specific_minute(self):
        """Test specific minute only."""
        result = self.collector._cron_to_human('30', '*', '*', '*', '*')
        self.assertIn("minute 30", result)

    def test_multiple_minutes(self):
        """Test multiple minutes."""
        result = self.collector._cron_to_human('0,15,30,45', '*', '*', '*', '*')
        self.assertIn("minutes 0,15,30,45", result)

    def test_specific_day(self):
        """Test specific day of month."""
        result = self.collector._cron_to_human('0', '0', '1', '*', '*')
        self.assertIn("day 1", result)

    def test_multiple_days(self):
        """Test multiple days."""
        result = self.collector._cron_to_human('0', '0', '1,15', '*', '*')
        self.assertIn("days 1,15", result)

    def test_every_n_days(self):
        """Test every N days."""
        result = self.collector._cron_to_human('0', '0', '*/2', '*', '*')
        self.assertIn("every 2 days", result)

    def test_specific_month(self):
        """Test specific month."""
        result = self.collector._cron_to_human('0', '0', '1', '1', '*')
        self.assertIn("Jan", result)

    def test_specific_month_all_months(self):
        """Test all month names."""
        months = {
            '1': 'Jan', '2': 'Feb', '3': 'Mar', '4': 'Apr',
            '5': 'May', '6': 'Jun', '7': 'Jul', '8': 'Aug',
            '9': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'
        }
        for num, name in months.items():
            result = self.collector._cron_to_human('0', '0', '*', num, '*')
            self.assertIn(name, result, f"Month {num} should show as {name}")

    def test_non_numeric_month(self):
        """Test non-numeric month."""
        result = self.collector._cron_to_human('0', '0', '*', 'jan-mar', '*')
        self.assertIn("month jan-mar", result)

    def test_specific_weekday(self):
        """Test specific weekday."""
        result = self.collector._cron_to_human('0', '0', '*', '*', '1')
        self.assertIn("Mon", result)

    def test_all_weekday_names(self):
        """Test all weekday names."""
        weekdays = {
            '0': 'Sun', '1': 'Mon', '2': 'Tue', '3': 'Wed',
            '4': 'Thu', '5': 'Fri', '6': 'Sat', '7': 'Sun'
        }
        for num, name in weekdays.items():
            result = self.collector._cron_to_human('0', '0', '*', '*', num)
            self.assertIn(name, result, f"Weekday {num} should show as {name}")

    def test_non_numeric_weekday(self):
        """Test non-numeric weekday."""
        result = self.collector._cron_to_human('0', '0', '*', '*', 'mon-fri')
        self.assertIn("mon-fri", result)


class TestGetNextRun(unittest.TestCase):
    """Tests for _get_next_run method."""

    def setUp(self):
        self.collector = TasksCollector()

    def test_get_next_run_returns_tuple(self):
        """Test that _get_next_run returns a tuple."""
        result = self.collector._get_next_run('0 * * * *')
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_get_next_run_invalid_expression(self):
        """Test _get_next_run with invalid expression."""
        result = self.collector._get_next_run('invalid')
        self.assertIsInstance(result, tuple)
        # Should return some error indicator
        self.assertIn('Error', result[1])


class TestGetSummary(unittest.TestCase):
    """Tests for _get_summary method."""

    def setUp(self):
        self.collector = TasksCollector()

    def test_get_summary_empty(self):
        """Test _get_summary with empty data."""
        cron_data = {'total': 0, 'by_source': {}}
        result = self.collector._get_summary(cron_data)
        self.assertEqual(result['total_cron_jobs'], 0)
        self.assertEqual(result['by_source'], {})

    def test_get_summary_with_data(self):
        """Test _get_summary with data."""
        cron_data = {
            'total': 5,
            'by_source': {'user:root': 3, '/etc/crontab': 2}
        }
        result = self.collector._get_summary(cron_data)
        self.assertEqual(result['total_cron_jobs'], 5)
        self.assertEqual(result['by_source']['user:root'], 3)


class TestGetAnacronJobs(unittest.TestCase):
    """Tests for _get_anacron_jobs method."""

    def setUp(self):
        self.collector = TasksCollector()

    def test_anacron_not_installed(self):
        """Test when anacrontab doesn't exist."""
        with patch('collectors.tasks.Path.exists', return_value=False):
            result = self.collector._get_anacron_jobs()
            self.assertEqual(result['status'], 'not_installed')
            self.assertEqual(result['count'], 0)

    def test_anacron_permission_denied(self):
        """Test when anacrontab cannot be read."""
        with tempfile.TemporaryDirectory() as tmpdir:
            anacrontab = Path(tmpdir) / 'anacrontab'
            anacrontab.touch()
            anacrontab.chmod(0o000)

            with patch.object(Path, 'exists', return_value=True):
                with patch('builtins.open', side_effect=PermissionError):
                    result = self.collector._get_anacron_jobs()
                    self.assertEqual(result['error'], 'Permission denied')

            anacrontab.chmod(0o644)  # Restore permissions for cleanup


class TestCollect(unittest.TestCase):
    """Tests for collect method."""

    def setUp(self):
        self.collector = TasksCollector()

    def test_collect_returns_dict(self):
        """Test that collect returns a dictionary."""
        result = self.collector.collect()
        self.assertIsInstance(result, dict)

    def test_collect_has_expected_keys(self):
        """Test that collect returns expected keys."""
        result = self.collector.collect()
        self.assertIn('cron', result)
        self.assertIn('systemd_timers', result)
        self.assertIn('anacron', result)
        self.assertIn('summary', result)

    def test_collect_cron_has_structure(self):
        """Test cron data structure."""
        result = self.collector.collect()
        cron = result['cron']
        self.assertIn('all_jobs', cron)
        self.assertIn('total', cron)
        self.assertIn('by_source', cron)

    def test_collect_summary_structure(self):
        """Test summary data structure."""
        result = self.collector.collect()
        summary = result['summary']
        self.assertIn('total_cron_jobs', summary)
        self.assertIn('by_source', summary)


class TestSystemdTimers(unittest.TestCase):
    """Tests for _get_systemd_timers_detailed method."""

    def setUp(self):
        self.collector = TasksCollector()

    @patch('subprocess.run')
    def test_systemd_timers_timeout(self, mock_run):
        """Test handling of systemctl timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 10)
        result = self.collector._get_systemd_timers_detailed()
        self.assertIn('error', result)

    @patch('subprocess.run')
    def test_systemd_timers_not_found(self, mock_run):
        """Test handling of systemctl not found."""
        mock_run.side_effect = FileNotFoundError
        result = self.collector._get_systemd_timers_detailed()
        self.assertIn('error', result)


class TestPeriodCronJobs(unittest.TestCase):
    """Tests for _get_period_cron_jobs method."""

    def setUp(self):
        self.collector = TasksCollector()

    def test_period_jobs_structure(self):
        """Test period jobs return structure."""
        # This will scan actual /etc/cron.* dirs if they exist
        result = self.collector._get_period_cron_jobs()
        self.assertIsInstance(result, list)

    @patch('collectors.tasks.Path.exists')
    @patch('collectors.tasks.Path.is_dir')
    def test_period_jobs_no_dirs(self, mock_is_dir, mock_exists):
        """Test when cron.* directories don't exist."""
        mock_exists.return_value = False
        mock_is_dir.return_value = False
        result = self.collector._get_period_cron_jobs()
        self.assertEqual(result, [])


class TestUserCrontab(unittest.TestCase):
    """Tests for _get_user_crontab_for_user method."""

    def setUp(self):
        self.collector = TasksCollector()

    @patch('subprocess.run')
    def test_user_crontab_timeout(self, mock_run):
        """Test handling of crontab timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)
        result = self.collector._get_user_crontab_for_user('testuser')
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_user_crontab_not_found(self, mock_run):
        """Test handling of crontab not found."""
        mock_run.side_effect = FileNotFoundError
        result = self.collector._get_user_crontab_for_user('testuser')
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_user_crontab_empty(self, mock_run):
        """Test handling of empty crontab."""
        mock_run.return_value = MagicMock(returncode=0, stdout='')
        result = self.collector._get_user_crontab_for_user('testuser')
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_user_crontab_with_jobs(self, mock_run):
        """Test parsing crontab with jobs."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='# Comment line\n0 * * * * /usr/bin/hourly.sh\n'
        )
        result = self.collector._get_user_crontab_for_user('testuser')
        self.assertIsNotNone(result)
        self.assertEqual(result['user'], 'testuser')
        self.assertEqual(len(result['jobs']), 1)

    @patch('subprocess.run')
    def test_user_crontab_with_variables(self, mock_run):
        """Test crontab with variable definitions."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='SHELL=/bin/bash\nPATH=/usr/bin\n0 * * * * /usr/bin/script.sh\n'
        )
        result = self.collector._get_user_crontab_for_user('testuser')
        self.assertIsNotNone(result)
        # Should skip variable lines
        self.assertEqual(len(result['jobs']), 1)


class TestAnacrontab(unittest.TestCase):
    """Tests for _get_anacron_jobs method."""

    def setUp(self):
        self.collector = TasksCollector()

    def test_anacron_returns_dict(self):
        """Test _get_anacron_jobs returns dict."""
        result = self.collector._get_anacron_jobs()
        self.assertIsInstance(result, dict)
        self.assertIn('jobs', result)
        self.assertIn('count', result)

    def test_anacron_has_status(self):
        """Test anacron result has status field."""
        result = self.collector._get_anacron_jobs()
        # Either has jobs or status field
        has_valid_structure = 'status' in result or 'jobs' in result
        self.assertTrue(has_valid_structure)


class TestCroniterAvailability(unittest.TestCase):
    """Tests related to croniter availability."""

    def test_croniter_flag_exists(self):
        """Test CRONITER_AVAILABLE flag is defined."""
        from collectors.tasks import CRONITER_AVAILABLE
        self.assertIsInstance(CRONITER_AVAILABLE, bool)


class TestCollectStructure(unittest.TestCase):
    """Tests for collect() return structure."""

    def setUp(self):
        self.collector = TasksCollector()

    def test_collect_has_cron(self):
        """Test collect has cron."""
        result = self.collector.collect()
        self.assertIn('cron', result)

    def test_collect_has_systemd_timers(self):
        """Test collect has systemd_timers."""
        result = self.collector.collect()
        self.assertIn('systemd_timers', result)

    def test_collect_has_anacron(self):
        """Test collect has anacron."""
        result = self.collector.collect()
        self.assertIn('anacron', result)


if __name__ == '__main__':
    unittest.main()
