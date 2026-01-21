import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from collectors.system import SystemCollector
from collectors.services import ServicesCollector
from collectors.network import NetworkCollector
from collectors.tasks import TasksCollector
from collectors.users import UsersCollector
from collectors.processes import ProcessesCollector
from utils.ui import generate_braille_sparkline

class TestUtils(unittest.TestCase):
    def test_braille_generator(self):
        # Basic functionality
        res = generate_braille_sparkline([0, 50, 100], width=5, max_val=100)
        self.assertEqual(len(res), 5)
        # Empty
        self.assertEqual(generate_braille_sparkline([], width=10), " " * 10)
        # Zero max_val (auto-scale)
        res = generate_braille_sparkline([10, 20], width=5, max_val=0)
        self.assertEqual(len(res), 5)

class TestSystemCollector(unittest.TestCase):
    def setUp(self):
        self.c = SystemCollector()

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    def test_cpu_memory(self, mock_mem, mock_cpu):
        # First call is percpu=True (list), second is total (float)
        mock_cpu.side_effect = [[10.0, 20.0], 15.5]
        mock_mem.return_value = MagicMock(total=1000, available=500, used=500, percent=50.0)
        
        data = self.c.collect()
        self.assertEqual(data['cpu']['usage_total'], 15.5)
        self.assertEqual(data['memory']['percent'], 50.0)

    @patch('socket.socket')
    def test_get_primary_ip(self, mock_socket):
        m = MagicMock()
        m.getsockname.return_value = ['10.0.0.5']
        mock_socket.return_value = m
        
        res = self.c._get_primary_ip()
        self.assertEqual(res['ip'], '10.0.0.5')

class TestServicesCollector(unittest.TestCase):
    def setUp(self):
        self.c = ServicesCollector({'docker': {'enabled': True}})

    @patch('subprocess.run')
    def test_systemd_services(self, mock_run):
        # Mock systemctl output
        mock_run.return_value.stdout = "ssh.service loaded active running OpenSSH Server"
        
        # We need to mock the config to monitor specific services or all
        self.c.config['services'] = {'monitor_all': True}
        
        res = self.c._get_systemd_services()
        self.assertEqual(len(res['services']), 1)
        self.assertEqual(res['services'][0]['name'], 'ssh')

    @patch('docker.from_env')
    def test_docker_containers(self, mock_docker):
        # Mock container
        container = MagicMock()
        container.short_id = 'abc'
        container.name = 'test-web'
        container.image.tags = ['nginx:latest']
        container.status = 'running'
        container.attrs = {'State': {'Status': 'running'}, 'Created': '2024-01-01'}
        container.ports = {'80/tcp': None}
        
        mock_docker.return_value.containers.list.return_value = [container]
        
        res = self.c._get_docker_containers()
        self.assertEqual(res['total'], 1)
        self.assertEqual(res['containers'][0]['name'], 'test-web')

class TestNetworkCollector(unittest.TestCase):
    def setUp(self):
        self.c = NetworkCollector()

    @patch('psutil.net_if_addrs')
    @patch('psutil.net_if_stats')
    def test_interfaces(self, mock_stats, mock_addrs):
        from collections import namedtuple
        snic = namedtuple('snic', ['family', 'address', 'netmask', 'broadcast', 'ptp'])
        snic_stats = namedtuple('snic_stats', ['isup', 'duplex', 'speed', 'mtu'])
        import socket
        
        mock_addrs.return_value = {'eth0': [snic(socket.AF_INET, '1.2.3.4', '255.0.0.0', None, None)]}
        mock_stats.return_value = {'eth0': snic_stats(True, 2, 1000, 1500)}
        
        res = self.c._get_interfaces()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['name'], 'eth0')
        self.assertTrue(res[0]['is_up'])

class TestTasksCollector(unittest.TestCase):
    def setUp(self):
        self.c = TasksCollector()

    def test_cron_parsing(self):
        # Valid
        res = self.c._parse_cron_entry("*/5 * * * * /run.sh", "root", "test")
        self.assertEqual(res['schedule']['minute'], "*/5")
        
        # Special
        res = self.c._parse_cron_entry("@daily /run.sh", "root", "test")
        self.assertEqual(res['schedule']['human'], "Daily (midnight)")
        
        # Invalid
        res = self.c._parse_cron_entry("invalid cron", "root", "test")
        self.assertIsNone(res)

class TestUsersCollector(unittest.TestCase):
    def setUp(self):
        self.c = UsersCollector()

    @patch('pwd.getpwall')
    def test_users_classification(self, mock_pwd):
        from collections import namedtuple
        struct_passwd = namedtuple('struct_passwd', ['pw_name', 'pw_passwd', 'pw_uid', 'pw_gid', 'pw_gecos', 'pw_dir', 'pw_shell'])
        
        mock_pwd.return_value = [
            struct_passwd('root', 'x', 0, 0, 'root', '/root', '/bin/bash'),
            struct_passwd('user', 'x', 1000, 1000, 'User', '/home/user', '/bin/bash'),
            struct_passwd('www', 'x', 33, 33, 'Web', '/var/www', '/bin/false')
        ]
        
        res = self.c._get_all_users()
        # Find types
        root = next(u for u in res if u['name'] == 'root')
        user = next(u for u in res if u['name'] == 'user')
        www = next(u for u in res if u['name'] == 'www')
        
        self.assertEqual(root['type'], 'human')
        self.assertEqual(user['type'], 'human')
        self.assertEqual(www['type'], 'system')

if __name__ == '__main__':
    unittest.main()
