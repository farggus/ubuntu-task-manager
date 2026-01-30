"""Tests for formatting utilities."""

import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from rich.text import Text

from utils.formatters import (
    format_attempts,
    format_banned_count,
    format_bantime,
    format_interval,
    format_jail_status,
    format_org,
    format_status,
)


class TestFormatAttempts(unittest.TestCase):
    """Tests for format_attempts() function."""

    def test_returns_rich_text(self):
        """Should return Rich Text object."""
        result = format_attempts(10)
        self.assertIsInstance(result, Text)

    def test_low_attempts_no_style(self):
        """Should have no special style for low attempts."""
        result = format_attempts(5)
        self.assertEqual(str(result), "5")
        # No bold red or yellow style
        self.assertNotIn("red", str(result.style) if result.style else "")

    def test_medium_attempts_yellow(self):
        """Should be yellow for 20-99 attempts."""
        result = format_attempts(50)
        self.assertEqual(str(result), "50")
        self.assertEqual(result.style, "yellow")

    def test_high_attempts_red(self):
        """Should be bold red for 100+ attempts."""
        result = format_attempts(100)
        self.assertEqual(str(result), "100")
        self.assertEqual(result.style, "bold red")

    def test_boundary_20(self):
        """Should be yellow at exactly 20."""
        result = format_attempts(20)
        self.assertEqual(result.style, "yellow")

    def test_boundary_100(self):
        """Should be bold red at exactly 100."""
        result = format_attempts(100)
        self.assertEqual(result.style, "bold red")

    def test_zero_attempts(self):
        """Should handle zero attempts."""
        result = format_attempts(0)
        self.assertEqual(str(result), "0")


class TestFormatBantime(unittest.TestCase):
    """Tests for format_bantime() function."""

    def test_zero_returns_dash(self):
        """Should return '-' for zero or negative."""
        self.assertEqual(format_bantime(0), "-")
        self.assertEqual(format_bantime(-1), "-")

    def test_minutes(self):
        """Should format as minutes for short durations."""
        result = format_bantime(300)  # 5 minutes
        self.assertEqual(result, "5m")

    def test_hours(self):
        """Should format as hours with expiry date."""
        result = format_bantime(3600)  # 1 hour
        self.assertIn("1h", result)
        self.assertIn("til", result)

    def test_days(self):
        """Should format as days with expiry date."""
        result = format_bantime(86400 * 7)  # 7 days
        self.assertIn("7d", result)
        self.assertIn("til", result)

    def test_years(self):
        """Should format as years with expiry date."""
        result = format_bantime(31536000 * 3)  # 3 years
        self.assertIn("3Y", result)
        self.assertIn("til", result)

    def test_expiry_format(self):
        """Should include expiry date in DD.MM.YY format."""
        seconds = 86400  # 1 day
        result = format_bantime(seconds)

        # Should contain date part like "til 01.02.24"
        self.assertIn("til", result)
        self.assertRegex(result, r"\d{2}\.\d{2}\.\d{2}")


class TestFormatOrg(unittest.TestCase):
    """Tests for format_org() function."""

    def test_short_org_unchanged(self):
        """Should not truncate short names."""
        result = format_org("Google")
        self.assertEqual(result, "Google")

    def test_long_org_truncated(self):
        """Should truncate long names with ellipsis."""
        long_name = "A" * 30
        result = format_org(long_name, max_len=20)
        self.assertEqual(len(result), 20)
        self.assertTrue(result.endswith("..."))

    def test_empty_returns_dash(self):
        """Should return '-' for empty or None."""
        self.assertEqual(format_org(""), "-")
        self.assertEqual(format_org(None), "-")

    def test_dash_returns_dash(self):
        """Should return '-' if input is '-'."""
        self.assertEqual(format_org("-"), "-")

    def test_exact_max_length(self):
        """Should not truncate if exactly max length."""
        name = "A" * 20
        result = format_org(name, max_len=20)
        self.assertEqual(result, name)

    def test_custom_max_length(self):
        """Should respect custom max_len."""
        result = format_org("ABCDEFGHIJ", max_len=8)
        self.assertEqual(len(result), 8)
        self.assertEqual(result, "ABCDE...")


class TestFormatStatus(unittest.TestCase):
    """Tests for format_status() function."""

    def test_returns_rich_text(self):
        """Should return Rich Text object."""
        result = format_status("EVASION")
        self.assertIsInstance(result, Text)

    def test_evasion_red(self):
        """Should be bold red for EVASION."""
        result = format_status("EVASION")
        self.assertEqual(str(result), "EVASION")
        self.assertEqual(result.style, "bold red")

    def test_evasion_active_red(self):
        """Should be bold red for EVASION ACTIVE."""
        result = format_status("EVASION ACTIVE")
        self.assertEqual(result.style, "bold red")

    def test_caught_yellow(self):
        """Should be bold yellow for CAUGHT."""
        result = format_status("CAUGHT")
        self.assertEqual(str(result), "CAUGHT")
        self.assertEqual(result.style, "bold yellow")

    def test_other_status_no_style(self):
        """Should have no special style for other statuses."""
        result = format_status("NORMAL")
        self.assertEqual(str(result), "NORMAL")


class TestFormatInterval(unittest.TestCase):
    """Tests for format_interval() function."""

    def test_seconds(self):
        """Should format as seconds for short intervals."""
        result = format_interval(45)
        self.assertEqual(result, "45s")

    def test_minutes(self):
        """Should format as minutes for medium intervals."""
        result = format_interval(300)  # 5 minutes
        self.assertEqual(result, "5m")

    def test_hours(self):
        """Should format as hours for long intervals."""
        result = format_interval(7200)  # 2 hours
        self.assertEqual(result, "2h")

    def test_boundary_60_seconds(self):
        """Should format as 1m at 60 seconds."""
        result = format_interval(60)
        self.assertEqual(result, "1m")

    def test_boundary_3600_seconds(self):
        """Should format as 1h at 3600 seconds."""
        result = format_interval(3600)
        self.assertEqual(result, "1h")

    def test_zero(self):
        """Should handle zero."""
        result = format_interval(0)
        self.assertEqual(result, "0s")


class TestFormatJailStatus(unittest.TestCase):
    """Tests for format_jail_status() function."""

    def test_returns_rich_text(self):
        """Should return Rich Text object."""
        result = format_jail_status(0)
        self.assertIsInstance(result, Text)

    def test_no_bans_ok_green(self):
        """Should show 'OK' in green when no bans."""
        result = format_jail_status(0)
        self.assertEqual(str(result), "OK")
        self.assertEqual(result.style, "green")

    def test_with_bans_active_red(self):
        """Should show 'ACTIVE' in bold red when bans exist."""
        result = format_jail_status(5)
        self.assertEqual(str(result), "ACTIVE")
        self.assertEqual(result.style, "bold red")

    def test_single_ban(self):
        """Should show ACTIVE for single ban."""
        result = format_jail_status(1)
        self.assertEqual(str(result), "ACTIVE")


class TestFormatBannedCount(unittest.TestCase):
    """Tests for format_banned_count() function."""

    def test_returns_rich_text(self):
        """Should return Rich Text object."""
        result = format_banned_count(0)
        self.assertIsInstance(result, Text)

    def test_zero_green(self):
        """Should be green for zero count."""
        result = format_banned_count(0)
        self.assertEqual(str(result), "0")
        self.assertEqual(result.style, "green")

    def test_positive_red(self):
        """Should be bold red for positive count."""
        result = format_banned_count(10)
        self.assertEqual(str(result), "10")
        self.assertEqual(result.style, "bold red")

    def test_single_ban_red(self):
        """Should be red for count of 1."""
        result = format_banned_count(1)
        self.assertEqual(result.style, "bold red")


if __name__ == '__main__':
    unittest.main()
