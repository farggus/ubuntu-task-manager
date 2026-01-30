"""Tests for Fail2ban data models."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models.fail2ban import BannedIP, Fail2banStatus, JailInfo, JailType


class TestJailType(unittest.TestCase):
    """Tests for JailType enum."""

    def test_regular_value(self):
        """REGULAR should have correct value."""
        self.assertEqual(JailType.REGULAR.value, "regular")

    def test_history_value(self):
        """HISTORY should have correct value."""
        self.assertEqual(JailType.HISTORY.value, "history")

    def test_slow_detector_value(self):
        """SLOW_DETECTOR should have correct value."""
        self.assertEqual(JailType.SLOW_DETECTOR.value, "slow_detector")


class TestBannedIP(unittest.TestCase):
    """Tests for BannedIP dataclass."""

    def test_required_field(self):
        """Should require IP address."""
        ip = BannedIP(ip="192.168.1.1")
        self.assertEqual(ip.ip, "192.168.1.1")

    def test_default_values(self):
        """Should have sensible defaults."""
        ip = BannedIP(ip="192.168.1.1")

        self.assertEqual(ip.country, "Unknown")
        self.assertEqual(ip.org, "Unknown")
        self.assertEqual(ip.attempts, 0)
        self.assertEqual(ip.bantime, 0)
        self.assertEqual(ip.jail, "")
        self.assertIsNone(ip.unban_time)
        self.assertIsNone(ip.status)
        self.assertIsNone(ip.interval)
        self.assertIsNone(ip.target)

    def test_all_fields(self):
        """Should accept all fields."""
        ip = BannedIP(
            ip="192.168.1.1",
            country="US",
            org="Google LLC",
            attempts=50,
            bantime=3600,
            jail="sshd",
            unban_time="2024-01-15 12:00:00",
            status="EVASION",
            interval="30m",
            target="/admin"
        )

        self.assertEqual(ip.ip, "192.168.1.1")
        self.assertEqual(ip.country, "US")
        self.assertEqual(ip.org, "Google LLC")
        self.assertEqual(ip.attempts, 50)
        self.assertEqual(ip.bantime, 3600)
        self.assertEqual(ip.jail, "sshd")
        self.assertEqual(ip.unban_time, "2024-01-15 12:00:00")
        self.assertEqual(ip.status, "EVASION")
        self.assertEqual(ip.interval, "30m")
        self.assertEqual(ip.target, "/admin")


class TestJailInfo(unittest.TestCase):
    """Tests for JailInfo dataclass."""

    def test_required_field(self):
        """Should require name."""
        jail = JailInfo(name="sshd")
        self.assertEqual(jail.name, "sshd")

    def test_default_values(self):
        """Should have sensible defaults."""
        jail = JailInfo(name="sshd")

        self.assertEqual(jail.jail_type, JailType.REGULAR)
        self.assertEqual(jail.currently_banned, 0)
        self.assertEqual(jail.total_banned, 0)
        self.assertEqual(jail.filter_failures, 0)
        self.assertEqual(jail.banned_ips, [])

    def test_all_fields(self):
        """Should accept all fields."""
        banned = [BannedIP(ip="1.2.3.4")]
        jail = JailInfo(
            name="recidive",
            jail_type=JailType.HISTORY,
            currently_banned=5,
            total_banned=100,
            filter_failures=50,
            banned_ips=banned
        )

        self.assertEqual(jail.name, "recidive")
        self.assertEqual(jail.jail_type, JailType.HISTORY)
        self.assertEqual(jail.currently_banned, 5)
        self.assertEqual(jail.total_banned, 100)
        self.assertEqual(jail.filter_failures, 50)
        self.assertEqual(len(jail.banned_ips), 1)


class TestJailInfoFromDict(unittest.TestCase):
    """Tests for JailInfo.from_dict() class method."""

    def test_basic_conversion(self):
        """Should convert basic dict to JailInfo."""
        data = {
            'name': 'sshd',
            'currently_banned': 3,
            'total_banned': 50,
            'filter_failures': 100,
        }

        jail = JailInfo.from_dict(data)

        self.assertEqual(jail.name, 'sshd')
        self.assertEqual(jail.currently_banned, 3)
        self.assertEqual(jail.total_banned, 50)
        self.assertEqual(jail.filter_failures, 100)
        self.assertEqual(jail.jail_type, JailType.REGULAR)

    def test_history_jail_type(self):
        """Should detect HISTORY jail type."""
        data = {'name': 'HISTORY'}

        jail = JailInfo.from_dict(data)

        self.assertEqual(jail.jail_type, JailType.HISTORY)

    def test_slow_detector_jail_type(self):
        """Should detect SLOW_DETECTOR jail type."""
        data = {'name': 'SLOW ATTACK DETECTOR'}

        jail = JailInfo.from_dict(data)

        self.assertEqual(jail.jail_type, JailType.SLOW_DETECTOR)

    def test_converts_banned_ips_from_dicts(self):
        """Should convert banned_ips list of dicts to BannedIP objects."""
        data = {
            'name': 'sshd',
            'banned_ips': [
                {'ip': '1.2.3.4', 'country': 'US', 'attempts': 10},
                {'ip': '5.6.7.8', 'org': 'DigitalOcean'},
            ]
        }

        jail = JailInfo.from_dict(data)

        self.assertEqual(len(jail.banned_ips), 2)
        self.assertIsInstance(jail.banned_ips[0], BannedIP)
        self.assertEqual(jail.banned_ips[0].ip, '1.2.3.4')
        self.assertEqual(jail.banned_ips[0].country, 'US')
        self.assertEqual(jail.banned_ips[0].attempts, 10)
        self.assertEqual(jail.banned_ips[1].ip, '5.6.7.8')
        self.assertEqual(jail.banned_ips[1].org, 'DigitalOcean')

    def test_handles_banned_ips_as_strings(self):
        """Should handle banned_ips as list of IP strings."""
        data = {
            'name': 'sshd',
            'banned_ips': ['1.2.3.4', '5.6.7.8']
        }

        jail = JailInfo.from_dict(data)

        self.assertEqual(len(jail.banned_ips), 2)
        self.assertEqual(jail.banned_ips[0].ip, '1.2.3.4')
        self.assertEqual(jail.banned_ips[1].ip, '5.6.7.8')

    def test_handles_missing_fields(self):
        """Should handle missing fields gracefully."""
        data = {}

        jail = JailInfo.from_dict(data)

        self.assertEqual(jail.name, '')
        self.assertEqual(jail.currently_banned, 0)

    def test_preserves_all_banned_ip_fields(self):
        """Should preserve all fields when converting banned_ips."""
        data = {
            'name': 'traefik-auth',
            'banned_ips': [{
                'ip': '1.2.3.4',
                'country': 'CN',
                'org': 'Alibaba',
                'attempts': 100,
                'bantime': 86400,
                'jail': 'traefik-auth',
                'unban_time': '2024-01-20',
                'status': 'EVASION',
                'interval': '15m',
                'target': '/wp-admin',
            }]
        }

        jail = JailInfo.from_dict(data)
        banned = jail.banned_ips[0]

        self.assertEqual(banned.country, 'CN')
        self.assertEqual(banned.org, 'Alibaba')
        self.assertEqual(banned.attempts, 100)
        self.assertEqual(banned.bantime, 86400)
        self.assertEqual(banned.jail, 'traefik-auth')
        self.assertEqual(banned.unban_time, '2024-01-20')
        self.assertEqual(banned.status, 'EVASION')
        self.assertEqual(banned.interval, '15m')
        self.assertEqual(banned.target, '/wp-admin')


class TestFail2banStatus(unittest.TestCase):
    """Tests for Fail2banStatus dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        status = Fail2banStatus()

        self.assertFalse(status.installed)
        self.assertFalse(status.running)
        self.assertEqual(status.jails, [])
        self.assertEqual(status.total_banned, 0)

    def test_all_fields(self):
        """Should accept all fields."""
        jails = [JailInfo(name="sshd")]
        status = Fail2banStatus(
            installed=True,
            running=True,
            jails=jails,
            total_banned=10
        )

        self.assertTrue(status.installed)
        self.assertTrue(status.running)
        self.assertEqual(len(status.jails), 1)
        self.assertEqual(status.total_banned, 10)


class TestFail2banStatusFromDict(unittest.TestCase):
    """Tests for Fail2banStatus.from_dict() class method."""

    def test_basic_conversion(self):
        """Should convert basic dict to Fail2banStatus."""
        data = {
            'installed': True,
            'running': True,
            'total_banned': 15,
            'jails': []
        }

        status = Fail2banStatus.from_dict(data)

        self.assertTrue(status.installed)
        self.assertTrue(status.running)
        self.assertEqual(status.total_banned, 15)

    def test_converts_jails_from_dicts(self):
        """Should convert jails list of dicts to JailInfo objects."""
        data = {
            'installed': True,
            'running': True,
            'jails': [
                {'name': 'sshd', 'currently_banned': 3},
                {'name': 'recidive', 'currently_banned': 5},
            ]
        }

        status = Fail2banStatus.from_dict(data)

        self.assertEqual(len(status.jails), 2)
        self.assertIsInstance(status.jails[0], JailInfo)
        self.assertEqual(status.jails[0].name, 'sshd')
        self.assertEqual(status.jails[1].name, 'recidive')

    def test_preserves_existing_jailinfo_objects(self):
        """Should preserve JailInfo objects that are already converted."""
        jail = JailInfo(name="sshd", currently_banned=10)
        data = {
            'installed': True,
            'jails': [jail, {'name': 'recidive'}]
        }

        status = Fail2banStatus.from_dict(data)

        self.assertEqual(len(status.jails), 2)
        self.assertIs(status.jails[0], jail)  # Same object
        self.assertIsInstance(status.jails[1], JailInfo)

    def test_handles_missing_fields(self):
        """Should handle missing fields gracefully."""
        data = {}

        status = Fail2banStatus.from_dict(data)

        self.assertFalse(status.installed)
        self.assertFalse(status.running)
        self.assertEqual(status.jails, [])


if __name__ == '__main__':
    unittest.main()
