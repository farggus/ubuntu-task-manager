"""Tests for SystemCollector."""

import unittest
from unittest.mock import MagicMock, patch

from collectors.system import SystemCollector


class TestSystemCollector(unittest.TestCase):
    """Tests for SystemCollector basic functionality."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_import(self):
        """Test that SystemCollector can be imported."""
        from collectors.system import SystemCollector
        self.assertIsNotNone(SystemCollector)

    def test_init(self):
        """Test SystemCollector initialization."""
        collector = SystemCollector()
        self.assertIsNotNone(collector)

    def test_init_with_config(self):
        """Test SystemCollector initialization with config."""
        config = {'system': {'collect_packages': True}}
        collector = SystemCollector(config)
        self.assertEqual(collector.config, config)

    def test_collect_returns_dict(self):
        """Test that collect returns a dictionary."""
        result = self.collector.collect()
        self.assertIsInstance(result, dict)

    def test_collect_has_expected_keys(self):
        """Test that collect returns expected keys."""
        result = self.collector.collect()
        # Based on actual collect() method
        expected_keys = ['os', 'cpu', 'memory', 'disk', 'uptime', 'hostname', 'network']
        for key in expected_keys:
            self.assertIn(key, result)

    def test_collect_has_timestamp(self):
        """Test that collect includes timestamp."""
        result = self.collector.collect()
        self.assertIn('timestamp', result)

    def test_collect_has_packages(self):
        """Test that collect includes packages info."""
        result = self.collector.collect()
        self.assertIn('packages', result)


class TestOSInfo(unittest.TestCase):
    """Tests for OS information collection."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_get_os_info_returns_dict(self):
        """Test _get_os_info returns a dictionary."""
        result = self.collector._get_os_info()
        self.assertIsInstance(result, dict)

    def test_os_info_has_system(self):
        """Test OS info has system."""
        result = self.collector._get_os_info()
        self.assertIn('system', result)

    def test_os_info_has_release(self):
        """Test OS info has release."""
        result = self.collector._get_os_info()
        self.assertIn('release', result)

    def test_os_info_has_pretty_name(self):
        """Test OS info has pretty_name."""
        result = self.collector._get_os_info()
        self.assertIn('pretty_name', result)


class TestCPUInfo(unittest.TestCase):
    """Tests for CPU information collection."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_get_cpu_info_returns_dict(self):
        """Test _get_cpu_info returns a dictionary."""
        result = self.collector._get_cpu_info()
        self.assertIsInstance(result, dict)

    def test_cpu_has_total_cores(self):
        """Test CPU info has total_cores count."""
        result = self.collector._get_cpu_info()
        self.assertIn('total_cores', result)

    def test_cpu_has_physical_cores(self):
        """Test CPU info has physical_cores count."""
        result = self.collector._get_cpu_info()
        self.assertIn('physical_cores', result)

    def test_cpu_total_cores_is_positive(self):
        """Test CPU total_cores is positive."""
        result = self.collector._get_cpu_info()
        self.assertGreater(result['total_cores'], 0)


class TestMemoryInfo(unittest.TestCase):
    """Tests for memory information collection."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_get_memory_info_returns_dict(self):
        """Test _get_memory_info returns a dictionary."""
        result = self.collector._get_memory_info()
        self.assertIsInstance(result, dict)

    def test_memory_has_total(self):
        """Test memory info has total."""
        result = self.collector._get_memory_info()
        self.assertIn('total', result)

    def test_memory_total_is_positive(self):
        """Test memory total is positive."""
        result = self.collector._get_memory_info()
        self.assertGreater(result['total'], 0)


class TestServiceStats(unittest.TestCase):
    """Tests for service statistics."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_get_service_stats_returns_dict(self):
        """Test _get_service_stats returns a dictionary."""
        result = self.collector._get_service_stats()
        self.assertIsInstance(result, dict)

    def test_service_stats_has_failed_key(self):
        """Test service stats has 'failed' key."""
        result = self.collector._get_service_stats()
        self.assertIn('failed', result)

    @patch('subprocess.run')
    def test_service_stats_handles_timeout(self, mock_run):
        """Test handling of systemctl timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 2)
        result = self.collector._get_service_stats()
        # Should return dict with default values
        self.assertIsInstance(result, dict)


class TestPackageStats(unittest.TestCase):
    """Tests for package statistics collection."""

    def setUp(self):
        self.collector = SystemCollector()
        # Reset cache for each test
        self.collector._pkg_cache_time = 0

    def test_get_package_stats_returns_dict(self):
        """Test _get_package_stats returns a dictionary."""
        result = self.collector._get_package_stats()
        self.assertIsInstance(result, dict)

    def test_package_stats_has_total(self):
        """Test package stats has 'total' key."""
        result = self.collector._get_package_stats()
        self.assertIn('total', result)

    def test_package_stats_has_updates(self):
        """Test package stats has 'updates' key."""
        result = self.collector._get_package_stats()
        self.assertIn('updates', result)

    @patch('subprocess.run')
    def test_package_stats_handles_timeout(self, mock_run):
        """Test handling of dpkg-query timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)
        result = self.collector._get_package_stats()
        # Should return dict even on error
        self.assertIsInstance(result, dict)


class TestDiskInfo(unittest.TestCase):
    """Tests for disk information collection."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_get_disk_info_returns_dict(self):
        """Test _get_disk_info returns a dictionary."""
        result = self.collector._get_disk_info()
        self.assertIsInstance(result, dict)

    def test_disk_info_not_empty(self):
        """Test disk info is not empty."""
        result = self.collector._get_disk_info()
        self.assertTrue(len(result) > 0)


class TestUptime(unittest.TestCase):
    """Tests for uptime information."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_get_uptime_returns_dict(self):
        """Test _get_uptime returns a dictionary."""
        result = self.collector._get_uptime()
        self.assertIsInstance(result, dict)

    def test_uptime_has_seconds(self):
        """Test uptime has uptime_seconds."""
        result = self.collector._get_uptime()
        self.assertIn('uptime_seconds', result)

    def test_uptime_has_formatted(self):
        """Test uptime has uptime_formatted."""
        result = self.collector._get_uptime()
        self.assertIn('uptime_formatted', result)

    def test_uptime_has_boot_time(self):
        """Test uptime has boot_time."""
        result = self.collector._get_uptime()
        self.assertIn('boot_time', result)


class TestPrimaryIP(unittest.TestCase):
    """Tests for primary IP detection."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_get_primary_ip_returns_dict(self):
        """Test _get_primary_ip returns a dictionary."""
        result = self.collector._get_primary_ip()
        self.assertIsInstance(result, dict)

    def test_primary_ip_has_ip(self):
        """Test primary IP result has 'ip' key."""
        result = self.collector._get_primary_ip()
        self.assertIn('ip', result)


class TestProcessStats(unittest.TestCase):
    """Tests for process statistics."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_get_process_stats_returns_dict(self):
        """Test _get_process_stats returns a dictionary."""
        result = self.collector._get_process_stats()
        self.assertIsInstance(result, dict)

    def test_process_stats_has_total(self):
        """Test process stats has 'total' key."""
        result = self.collector._get_process_stats()
        self.assertIn('total', result)


class TestUsersCount(unittest.TestCase):
    """Tests for users count."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_get_users_count_returns_int(self):
        """Test _get_users_count returns an integer."""
        result = self.collector._get_users_count()
        self.assertIsInstance(result, int)

    def test_users_count_non_negative(self):
        """Test users count is non-negative."""
        result = self.collector._get_users_count()
        self.assertGreaterEqual(result, 0)


class TestSMARTInfo(unittest.TestCase):
    """Tests for SMART information collection."""

    def setUp(self):
        self.collector = SystemCollector()

    @patch('subprocess.run')
    def test_smart_handles_timeout(self, mock_run):
        """Test SMART info handles timeout gracefully."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 10)
        result = self.collector._try_smartctl_json('/dev/sda')
        # Should return empty dict or None
        self.assertTrue(result == {} or result is None)

    @patch('subprocess.run')
    def test_smart_handles_missing_smartctl(self, mock_run):
        """Test SMART info handles missing smartctl."""
        mock_run.side_effect = FileNotFoundError
        result = self.collector._try_smartctl_json('/dev/sda')
        # Should return empty dict or None
        self.assertTrue(result == {} or result is None)


if __name__ == '__main__':
    unittest.main()
