import unittest
import sys
import os
import importlib

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestAppIntegrity(unittest.TestCase):
    def test_dashboard_import(self):
        """Test that dashboard.app can be imported successfully."""
        try:
            import dashboard.app
            # Force reload to catch errors if test is run multiple times
            importlib.reload(dashboard.app)
        except SyntaxError as e:
            self.fail(f"Syntax Error in dashboard/app.py: {e}")
        except NameError as e:
            self.fail(f"Name Error in dashboard/app.py (Class ordering?): {e}")
        except ImportError as e:
            self.fail(f"Import Error: {e}")
        except Exception as e:
            self.fail(f"Failed to import dashboard.app: {e}")

    def test_main_import(self):
        """Test that main.py can be imported."""
        try:
            import main
            importlib.reload(main)
        except Exception as e:
            self.fail(f"Failed to import main.py: {e}")

    def test_collectors_import(self):
        """Ensure all collectors are exposed correctly."""
        try:
            from collectors import (
                SystemCollector, ServicesCollector, NetworkCollector, 
                TasksCollector, UsersCollector, ProcessesCollector
            )
        except Exception as e:
            self.fail(f"Collectors package structure is broken: {e}")

if __name__ == '__main__':
    unittest.main()
