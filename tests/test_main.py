"""Tests for main module."""

import unittest


class TestMainModule(unittest.TestCase):
    """Tests for main module functionality."""

    def test_import(self):
        """Test that main module can be imported."""
        import main
        self.assertIsNotNone(main)

    def test_has_main_function(self):
        """Test that main module has a main function."""
        import main
        self.assertTrue(hasattr(main, 'main'))

    def test_has_setup_logging(self):
        """Test that main module has setup_logging function."""
        import main
        self.assertTrue(hasattr(main, 'setup_logging'))

    def test_utm_dashboard_importable(self):
        """Test that UTMDashboard can be imported from dashboard module."""
        # UTMDashboard is lazy-imported in main() for startup performance
        from dashboard import UTMDashboard
        self.assertIsNotNone(UTMDashboard)


class TestConst(unittest.TestCase):
    """Tests for const module."""

    def test_import(self):
        """Test that const module can be imported."""
        import const
        self.assertIsNotNone(const)

    def test_has_app_version(self):
        """Test that const has APP_VERSION."""
        import const
        self.assertTrue(hasattr(const, 'APP_VERSION'))

    def test_has_app_name(self):
        """Test that const has APP_NAME."""
        import const
        self.assertTrue(hasattr(const, 'APP_NAME'))

    def test_has_app_slug(self):
        """Test that const has APP_SLUG."""
        import const
        self.assertTrue(hasattr(const, 'APP_SLUG'))

    def test_has_base_dir(self):
        """Test that const has BASE_DIR."""
        import const
        self.assertTrue(hasattr(const, 'BASE_DIR'))

    def test_has_config_dir(self):
        """Test that const has CONFIG_DIR."""
        import const
        self.assertTrue(hasattr(const, 'CONFIG_DIR'))


if __name__ == '__main__':
    unittest.main()
