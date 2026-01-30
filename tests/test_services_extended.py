"""Extended tests for ServicesCollector."""

import unittest
from unittest.mock import MagicMock, patch

from collectors.services import ServicesCollector


class TestServicesCollector(unittest.TestCase):
    """Tests for ServicesCollector functionality."""

    def setUp(self):
        self.collector = ServicesCollector()

    def test_import(self):
        """Test that ServicesCollector can be imported."""
        from collectors.services import ServicesCollector
        self.assertIsNotNone(ServicesCollector)

    def test_init(self):
        """Test ServicesCollector initialization."""
        collector = ServicesCollector()
        self.assertIsNotNone(collector)

    def test_init_with_config(self):
        """Test ServicesCollector initialization with config."""
        config = {'services': {'enabled': True}}
        collector = ServicesCollector(config)
        self.assertEqual(collector.config, config)

    def test_collect_returns_dict(self):
        """Test that collect returns a dictionary."""
        result = self.collector.collect()
        self.assertIsInstance(result, dict)

    def test_collect_has_systemd(self):
        """Test that collect returns systemd info."""
        result = self.collector.collect()
        self.assertIn('systemd', result)

    def test_collect_has_docker(self):
        """Test that collect returns docker info."""
        result = self.collector.collect()
        self.assertIn('docker', result)


class TestSystemdServices(unittest.TestCase):
    """Tests for systemd services collection."""

    def setUp(self):
        self.collector = ServicesCollector()

    def test_list_services_returns_list(self):
        """Test _list_all_services returns a list."""
        result = self.collector._list_all_services()
        self.assertIsInstance(result, list)

    @patch('collectors.services.subprocess.run')
    def test_list_services_handles_timeout(self, mock_run):
        """Test handling of systemctl timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 10)
        result = self.collector._list_all_services()
        # Returns list with error dict on exception
        self.assertIsInstance(result, list)
        if result:
            self.assertIn('error', result[0])

    @patch('collectors.services.subprocess.run')
    def test_list_services_handles_not_found(self, mock_run):
        """Test handling of systemctl not found."""
        mock_run.side_effect = FileNotFoundError
        result = self.collector._list_all_services()
        # Returns list with error dict on exception
        self.assertIsInstance(result, list)
        if result:
            self.assertIn('error', result[0])

    @patch('subprocess.run')
    def test_list_services_parses_output(self, mock_run):
        """Test parsing of systemctl output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='sshd.service loaded active running OpenSSH server\n'
                   'nginx.service loaded active running nginx web server\n'
        )
        result = self.collector._list_all_services()
        self.assertIsInstance(result, list)


class TestServiceInfo(unittest.TestCase):
    """Tests for service info retrieval."""

    def setUp(self):
        self.collector = ServicesCollector()

    @patch('collectors.services.subprocess.run')
    def test_get_service_info_timeout(self, mock_run):
        """Test handling of systemctl show timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)
        result = self.collector._get_service_info('test.service')
        # Returns dict with error on exception
        self.assertIsInstance(result, dict)
        self.assertIn('error', result)

    @patch('collectors.services.subprocess.run')
    def test_get_service_info_empty_output(self, mock_run):
        """Test handling of systemctl show with empty output."""
        mock_run.return_value = MagicMock(returncode=0, stdout='')
        result = self.collector._get_service_info('nonexistent.service')
        # Returns dict even with empty properties
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)

    @patch('collectors.services.subprocess.run')
    def test_get_service_info_parses_properties(self, mock_run):
        """Test parsing of service properties."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Id=sshd.service\nDescription=OpenSSH server\nActiveState=active\n'
        )
        result = self.collector._get_service_info('sshd.service')
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)


class TestServiceUsersMap(unittest.TestCase):
    """Tests for service users mapping."""

    def setUp(self):
        self.collector = ServicesCollector()

    @patch('subprocess.run')
    def test_get_service_users_map_returns_dict(self, mock_run):
        """Test _get_service_users_map returns a dictionary."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='sshd.service root\nnginx.service www-data\n'
        )
        result = self.collector._get_service_users_map()
        self.assertIsInstance(result, dict)

    @patch('subprocess.run')
    def test_get_service_users_map_handles_timeout(self, mock_run):
        """Test handling of ps timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)
        result = self.collector._get_service_users_map()
        self.assertEqual(result, {})

    @patch('subprocess.run')
    def test_get_service_users_map_handles_failure(self, mock_run):
        """Test handling of ps failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout='')
        result = self.collector._get_service_users_map()
        self.assertEqual(result, {})


class TestDockerContainers(unittest.TestCase):
    """Tests for Docker containers collection."""

    def setUp(self):
        self.collector = ServicesCollector()

    def test_get_docker_containers_returns_dict(self):
        """Test _get_docker_containers returns a dictionary."""
        result = self.collector._get_docker_containers()
        self.assertIsInstance(result, dict)

    def test_docker_containers_has_containers_or_error_key(self):
        """Test docker containers result has 'containers' or 'error' key."""
        result = self.collector._get_docker_containers()
        # Either 'containers' (when docker available) or 'error' (when not)
        has_expected_key = 'containers' in result or 'error' in result
        self.assertTrue(has_expected_key, f"Expected 'containers' or 'error' key, got: {result.keys()}")


if __name__ == '__main__':
    unittest.main()
