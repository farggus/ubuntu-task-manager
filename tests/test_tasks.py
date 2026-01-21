import unittest
from datetime import datetime
from collectors.tasks import TasksCollector

class TestTasksCollector(unittest.TestCase):
    def setUp(self):
        self.collector = TasksCollector()

    def test_parse_standard_cron(self):
        """Test parsing of a standard cron line."""
        # minute hour day month weekday command
        entry = "30 2 * * * /usr/bin/backup.sh"
        result = self.collector._parse_cron_entry(entry, "root", "/etc/crontab")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['command'], "/usr/bin/backup.sh")
        self.assertEqual(result['user'], "root")
        self.assertEqual(result['schedule']['minute'], "30")
        self.assertEqual(result['schedule']['hour'], "2")
        # Check human readable format logic
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

    def test_parse_complex_schedule(self):
        """Test parsing of complex schedule with ranges/lists."""
        # At minute 0 past hour 8, 14, and 20
        entry = "0 8,14,20 * * * /script/run"
        result = self.collector._parse_cron_entry(entry, "root", "test")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['schedule']['minute'], "0")
        self.assertEqual(result['schedule']['hour'], "8,14,20")
        # Matches current simple implementation: "at 8,14,20:00"
        self.assertEqual(result['schedule']['human'], "at 8,14,20:00")

    def test_invalid_entry(self):
        """Test parsing of invalid entry."""
        entry = "not a cron line"
        result = self.collector._parse_cron_entry(entry, "root", "test")
        self.assertIsNone(result)

    def test_cron_to_human(self):
        """Test specifically the human readable converter."""
        # Every minute
        self.assertEqual(
            self.collector._cron_to_human('*', '*', '*', '*', '*'),
            "Every minute"
        )
        # Specific time
        self.assertEqual(
            self.collector._cron_to_human('15', '14', '*', '*', '*'),
            "at 14:15"
        )
        # Interval
        self.assertIn(
            "every 5 minutes",
            self.collector._cron_to_human('*/5', '*', '*', '*', '*')
        )

if __name__ == '__main__':
    unittest.main()
