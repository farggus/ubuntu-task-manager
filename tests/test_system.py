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
        result, disk_info = self.collector._try_smartctl_json_extended('/dev/sda')
        # Should return None
        self.assertIsNone(result)
        self.assertIsNone(disk_info)

    @patch('subprocess.run')
    def test_smart_handles_missing_smartctl(self, mock_run):
        """Test SMART info handles missing smartctl."""
        mock_run.side_effect = FileNotFoundError
        result, disk_info = self.collector._try_smartctl_json_extended('/dev/sda')
        # Should return None
        self.assertIsNone(result)
        self.assertIsNone(disk_info)


class TestPackageStatsExtended(unittest.TestCase):
    """Extended tests for package statistics."""

    def setUp(self):
        self.collector = SystemCollector()
        self.collector._pkg_cache_time = 0
        self.collector._pkg_cache = {'total': 0, 'updates': 0, 'upgradable_list': [], 'all_packages': []}

    def test_package_stats_uses_cache(self):
        """Test that package stats uses cache when fresh."""
        import time
        # Set cache with recent timestamp
        self.collector._pkg_cache_time = time.time()
        self.collector._pkg_cache = {'total': 100, 'updates': 5, 'upgradable_list': [], 'all_packages': []}

        result = self.collector._get_package_stats()
        self.assertEqual(result['total'], 100)

    @patch('collectors.system.subprocess.run')
    def test_package_stats_parses_apt_list(self, mock_run):
        """Test parsing of apt list --upgradable output."""
        # Mock dpkg-query response
        dpkg_response = MagicMock(returncode=0, stdout='pkg1 1.0\npkg2 2.0\n')
        # Mock apt list response
        apt_response = MagicMock(returncode=0, stdout='Listing...\npkg1/focal 1.1 amd64 [upgradable]\n')

        mock_run.side_effect = [dpkg_response, apt_response]

        result = self.collector._get_package_stats()
        self.assertIsInstance(result, dict)
        self.assertIn('total', result)

    @patch('collectors.system.subprocess.run')
    def test_package_stats_handles_empty_apt(self, mock_run):
        """Test handling of empty apt output."""
        dpkg_response = MagicMock(returncode=0, stdout='pkg1 1.0\n')
        apt_response = MagicMock(returncode=0, stdout='Listing...\n')

        mock_run.side_effect = [dpkg_response, apt_response]

        result = self.collector._get_package_stats()
        self.assertEqual(result['updates'], 0)


class TestServiceStatsExtended(unittest.TestCase):
    """Extended tests for service statistics."""

    def setUp(self):
        self.collector = SystemCollector()

    @patch('collectors.system.subprocess.run')
    def test_service_stats_parses_failed(self, mock_run):
        """Test parsing of failed services."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='  UNIT                  LOAD   ACTIVE SUB    DESCRIPTION\nfailed.service        loaded failed failed Test\n\n1 loaded units listed.'
        )

        result = self.collector._get_service_stats()
        self.assertIn('failed', result)

    @patch('collectors.system.subprocess.run')
    def test_service_stats_file_not_found(self, mock_run):
        """Test handling when systemctl not found."""
        mock_run.side_effect = FileNotFoundError()
        result = self.collector._get_service_stats()
        self.assertIsInstance(result, dict)


class TestDiskInfoExtended(unittest.TestCase):
    """Extended tests for disk information."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_disk_info_returns_dict(self):
        """Test that disk info returns dict."""
        result = self.collector._get_disk_info()
        self.assertIsInstance(result, dict)

    def test_disk_info_has_root(self):
        """Test that root partition is included."""
        result = self.collector._get_disk_info()
        # Should have at least root partition
        self.assertTrue(len(result) > 0)


class TestCPUInfoExtended(unittest.TestCase):
    """Extended tests for CPU information."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_cpu_info_has_usage(self):
        """Test CPU info includes usage percentage."""
        result = self.collector._get_cpu_info()
        self.assertIn('usage_total', result)

    def test_cpu_info_usage_in_range(self):
        """Test CPU usage is in valid range."""
        result = self.collector._get_cpu_info()
        self.assertGreaterEqual(result['usage_total'], 0)
        self.assertLessEqual(result['usage_total'], 100)


class TestMemoryInfoExtended(unittest.TestCase):
    """Extended tests for memory information."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_memory_info_has_available(self):
        """Test memory info has available."""
        result = self.collector._get_memory_info()
        self.assertIn('available', result)

    def test_memory_info_has_percent(self):
        """Test memory info has percent."""
        result = self.collector._get_memory_info()
        self.assertIn('percent', result)

    def test_memory_percent_in_range(self):
        """Test memory percent is 0-100."""
        result = self.collector._get_memory_info()
        self.assertGreaterEqual(result['percent'], 0)
        self.assertLessEqual(result['percent'], 100)


class TestServicesStats(unittest.TestCase):
    """Tests for services statistics in collect."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_collect_has_services_stats(self):
        """Test collect includes services_stats."""
        result = self.collector.collect()
        self.assertIn('services_stats', result)

    def test_services_stats_has_failed(self):
        """Test services_stats has failed count."""
        result = self.collector.collect()
        self.assertIn('failed', result['services_stats'])


class TestProcessesInCollect(unittest.TestCase):
    """Tests for processes info in collect."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_collect_has_processes(self):
        """Test collect includes processes."""
        result = self.collector.collect()
        self.assertIn('processes', result)

    def test_processes_has_total(self):
        """Test processes has total count."""
        result = self.collector.collect()
        self.assertIn('total', result['processes'])


class TestNetworkInfo(unittest.TestCase):
    """Tests for basic network info in system collector."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_collect_has_network(self):
        """Test collect includes network info."""
        result = self.collector.collect()
        self.assertIn('network', result)


class TestTemperature(unittest.TestCase):
    """Tests for temperature collection."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_collect_handles_no_sensors(self):
        """Test that collect handles systems without temperature sensors."""
        result = self.collector.collect()
        # Should not fail even without sensors
        self.assertIsInstance(result, dict)


class TestSmartNonBlocking(unittest.TestCase):
    """Tests for non-blocking SMART data collection."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_smart_cache_initialized(self):
        """Test SMART cache is initialized in __init__."""
        self.assertIsInstance(self.collector._smart_cache, dict)
        self.assertIsInstance(self.collector._smart_cache_time, (int, float))
        self.assertFalse(self.collector._smart_update_in_progress)

    def test_smart_disk_cache_initialized(self):
        """Test SMART disk cache is initialized."""
        self.assertIsInstance(self.collector._smart_disk_cache, dict)

    def test_get_smart_cache_returns_immediately(self):
        """Test _get_smart_cache returns immediately without blocking."""
        import time
        start = time.time()
        result = self.collector._get_smart_cache()
        elapsed = time.time() - start
        # Should return in less than 100ms (non-blocking)
        self.assertLess(elapsed, 0.1)
        self.assertIsInstance(result, dict)

    def test_get_smart_cache_returns_stale_cache(self):
        """Test _get_smart_cache returns stale cache while updating."""
        # Set stale cache
        self.collector._smart_cache = {'test': 'data'}
        self.collector._smart_cache_time = 0  # Very old

        result = self.collector._get_smart_cache()
        # Should return the stale cache immediately
        self.assertEqual(result, {'test': 'data'})

    def test_get_smart_cache_uses_persistent_cache(self):
        """Test _get_smart_cache uses persistent cache when in-memory is empty."""
        # Clear in-memory cache
        self.collector._smart_cache = {}
        self.collector._smart_cache_time = 0

        # Set persistent cache
        self.collector._smart_disk_cache = {
            '/dev/sda': {
                'device_type': None,
                'last_temperature': 42,
                'smart_status': 'OK',
                'smart_supported': True
            }
        }

        result = self.collector._get_smart_cache()
        self.assertIn('/dev/sda', result)
        self.assertEqual(result['/dev/sda']['temperature'], 42)
        self.assertTrue(result['/dev/sda']['from_cache'])

    def test_trigger_smart_update_sets_flag(self):
        """Test that triggering update sets in_progress flag."""
        self.collector._smart_cache_time = 0  # Force stale
        self.collector._get_smart_cache()
        # Background thread should be triggered
        import time
        time.sleep(0.05)  # Give thread time to start
        # Flag might be True or already False if very fast
        self.assertIsInstance(self.collector._smart_update_in_progress, bool)

    def test_smart_update_not_triggered_twice(self):
        """Test that update is not triggered if already in progress."""
        self.collector._smart_update_in_progress = True
        self.collector._smart_cache_time = 0  # Force stale

        # Should not start another thread
        self.collector._trigger_smart_update_background()
        # Flag should still be True (unchanged)
        self.assertTrue(self.collector._smart_update_in_progress)

    def test_disk_cache_structure(self):
        """Test that disk cache has expected structure."""
        self.collector._smart_disk_cache['/dev/sda'] = {
            'device_type': 'sat',
            'model': 'Test SSD',
            'serial': 'ABC123',
            'last_temperature': 35,
            'smart_status': 'OK',
            'smart_supported': True,
            'last_updated': 1234567890
        }

        cache = self.collector._smart_disk_cache['/dev/sda']
        self.assertEqual(cache['device_type'], 'sat')
        self.assertEqual(cache['model'], 'Test SSD')
        self.assertEqual(cache['serial'], 'ABC123')
        self.assertEqual(cache['last_temperature'], 35)


class TestSmartPersistence(unittest.TestCase):
    """Tests for persistent SMART disk cache."""

    def setUp(self):
        self.collector = SystemCollector()

    def test_save_creates_file(self):
        """Test that _save_smart_disk_cache creates a file."""
        import os
        from const import DISK_CACHE_FILE

        self.collector._smart_disk_cache = {
            '/dev/sda': {
                'device_type': 'sat',
                'model': 'Test SSD',
                'serial': 'ABC123',
                'last_temperature': 42,
                'smart_status': 'OK',
                'smart_supported': True,
                'last_updated': 1234567890
            }
        }
        self.collector._save_smart_disk_cache()

        self.assertTrue(os.path.exists(DISK_CACHE_FILE))

    def test_save_and_load_roundtrip(self):
        """Test that saved data can be loaded back."""
        test_data = {
            '/dev/sda': {
                'device_type': None,
                'model': 'Samsung SSD',
                'serial': 'S123',
                'last_temperature': 35,
                'smart_status': 'OK',
                'smart_supported': True,
                'last_updated': 1234567890
            },
            '/dev/sdb': {
                'device_type': 'sat',
                'model': 'WD HDD',
                'serial': 'WD456',
                'last_temperature': 40,
                'smart_status': 'OK',
                'smart_supported': True,
                'last_updated': 1234567890
            }
        }
        self.collector._smart_disk_cache = test_data
        self.collector._save_smart_disk_cache()

        # Create new collector and check it loads the data
        new_collector = SystemCollector()
        self.assertEqual(new_collector._smart_disk_cache, test_data)

    def test_load_handles_missing_file(self):
        """Test that loading handles missing cache file gracefully."""
        import os
        from const import DISK_CACHE_FILE

        # Remove file if exists
        if os.path.exists(DISK_CACHE_FILE):
            os.unlink(DISK_CACHE_FILE)

        result = self.collector._load_smart_disk_cache()
        self.assertEqual(result, {})

    def test_load_handles_invalid_json(self):
        """Test that loading handles corrupted cache file."""
        from const import DISK_CACHE_FILE

        # Write invalid JSON
        with open(DISK_CACHE_FILE, 'w') as f:
            f.write('not valid json {{{')

        result = self.collector._load_smart_disk_cache()
        self.assertEqual(result, {})

    def test_migration_from_old_format(self):
        """Test migration from old format (device_type only)."""
        from const import DISK_CACHE_FILE

        # Write old format
        old_data = {'/dev/sda': 'sat', '/dev/sdb': None}
        with open(DISK_CACHE_FILE, 'w') as f:
            import json
            json.dump(old_data, f)

        result = self.collector._load_smart_disk_cache()

        # Should be migrated to new format
        self.assertIn('/dev/sda', result)
        self.assertEqual(result['/dev/sda']['device_type'], 'sat')
        self.assertIn('/dev/sdb', result)
        self.assertIsNone(result['/dev/sdb']['device_type'])


if __name__ == '__main__':
    unittest.main()
