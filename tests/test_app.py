"""Tests for dashboard app module."""

import unittest


class TestDashboardApp(unittest.TestCase):
    """Tests for Dashboard App."""

    def test_import(self):
        """Test that dashboard app can be imported."""
        from dashboard.app import UTMDashboard
        self.assertIsNotNone(UTMDashboard)

    def test_dashboard_is_textual_app(self):
        """Test that UTMDashboard is a Textual App."""
        from textual.app import App
        from dashboard.app import UTMDashboard
        self.assertTrue(issubclass(UTMDashboard, App))


if __name__ == '__main__':
    unittest.main()
