"""Tests for UTMDashboard - main application class."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dashboard.app import UTMDashboard


class TestLoadConfig(unittest.TestCase):
    """Tests for load_config() method."""

    def test_loads_yaml_config(self):
        """Should load config from YAML file."""
        yaml_content = """
docker:
  enabled: true
  socket: /var/run/docker.sock
network:
  timeout: 30
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                with patch.object(UTMDashboard, '__init__', lambda x, y: None):
                    app = UTMDashboard.__new__(UTMDashboard)
                    config = app.load_config(f.name)

                self.assertTrue(config['docker']['enabled'])
                self.assertEqual(config['docker']['socket'], '/var/run/docker.sock')
                self.assertEqual(config['network']['timeout'], 30)
            finally:
                os.unlink(f.name)

    def test_returns_empty_if_file_not_exists(self):
        """Should return empty dict if config file doesn't exist."""
        with patch.object(UTMDashboard, '__init__', lambda x, y: None):
            app = UTMDashboard.__new__(UTMDashboard)
            config = app.load_config('/nonexistent/config.yaml')

        self.assertEqual(config, {})

    def test_env_override_docker_enabled(self):
        """Should override docker.enabled from environment."""
        yaml_content = "docker:\n  enabled: false"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                with patch.dict(os.environ, {'UTM_DOCKER_ENABLED': 'true'}):
                    with patch.object(UTMDashboard, '__init__', lambda x, y: None):
                        app = UTMDashboard.__new__(UTMDashboard)
                        config = app.load_config(f.name)

                self.assertTrue(config['docker']['enabled'])
            finally:
                os.unlink(f.name)

    def test_env_override_docker_socket(self):
        """Should override docker.socket from environment."""
        with patch.dict(os.environ, {'UTM_DOCKER_SOCKET': '/custom/docker.sock'}):
            with patch.object(UTMDashboard, '__init__', lambda x, y: None):
                app = UTMDashboard.__new__(UTMDashboard)
                config = app.load_config('/nonexistent.yaml')

        self.assertEqual(config['docker']['socket'], '/custom/docker.sock')

    def test_env_creates_docker_section_if_missing(self):
        """Should create docker section if not in config."""
        with patch.dict(os.environ, {'UTM_DOCKER_ENABLED': 'true'}):
            with patch.object(UTMDashboard, '__init__', lambda x, y: None):
                app = UTMDashboard.__new__(UTMDashboard)
                config = app.load_config('/nonexistent.yaml')

        self.assertIn('docker', config)
        self.assertTrue(config['docker']['enabled'])


class TestIntervalSteps(unittest.TestCase):
    """Tests for interval management."""

    def test_interval_steps_defined(self):
        """Should have interval steps defined."""
        self.assertIsInstance(UTMDashboard.INTERVAL_STEPS, list)
        self.assertGreater(len(UTMDashboard.INTERVAL_STEPS), 0)

    def test_interval_steps_ascending(self):
        """Interval steps should be in ascending order."""
        steps = UTMDashboard.INTERVAL_STEPS
        for i in range(len(steps) - 1):
            self.assertLess(steps[i], steps[i + 1])

    def test_min_interval_reasonable(self):
        """Minimum interval should be at least 500ms."""
        self.assertGreaterEqual(min(UTMDashboard.INTERVAL_STEPS), 500)

    def test_max_interval_reasonable(self):
        """Maximum interval should be at most 60 seconds."""
        self.assertLessEqual(max(UTMDashboard.INTERVAL_STEPS), 60000)


class TestBindings(unittest.TestCase):
    """Tests for keyboard bindings."""

    def test_has_quit_binding(self):
        """Should have ctrl+q for quit."""
        bindings = UTMDashboard.BINDINGS
        quit_bindings = [b for b in bindings if b.action == "quit"]
        self.assertEqual(len(quit_bindings), 1)
        self.assertEqual(quit_bindings[0].key, "ctrl+q")

    def test_has_refresh_binding(self):
        """Should have ctrl+r for refresh."""
        bindings = UTMDashboard.BINDINGS
        refresh_bindings = [b for b in bindings if b.action == "refresh"]
        self.assertEqual(len(refresh_bindings), 1)
        self.assertEqual(refresh_bindings[0].key, "ctrl+r")

    def test_has_export_binding(self):
        """Should have ctrl+e for export."""
        bindings = UTMDashboard.BINDINGS
        export_bindings = [b for b in bindings if b.action == "export_snapshot"]
        self.assertEqual(len(export_bindings), 1)

    def test_has_tab_navigation_bindings(self):
        """Should have number keys for tab navigation."""
        bindings = UTMDashboard.BINDINGS
        switch_tab_bindings = [b for b in bindings if "switch_tab" in b.action]
        # Should have bindings for tabs 1-8, 0, F, shift+f
        self.assertGreaterEqual(len(switch_tab_bindings), 10)

    def test_has_interval_bindings(self):
        """Should have +/- for interval control."""
        bindings = UTMDashboard.BINDINGS
        increase_bindings = [b for b in bindings if b.action == "increase_interval"]
        decrease_bindings = [b for b in bindings if b.action == "decrease_interval"]
        self.assertGreaterEqual(len(increase_bindings), 1)
        self.assertGreaterEqual(len(decrease_bindings), 1)


class TestCSS(unittest.TestCase):
    """Tests for CSS styles."""

    def test_has_css_defined(self):
        """Should have CSS styles defined."""
        self.assertIsInstance(UTMDashboard.CSS, str)
        self.assertGreater(len(UTMDashboard.CSS), 0)

    def test_css_contains_screen_layout(self):
        """CSS should define screen layout."""
        self.assertIn("Screen", UTMDashboard.CSS)

    def test_css_contains_main_container(self):
        """CSS should define main container styles."""
        self.assertIn("main-container", UTMDashboard.CSS)


class TestActionIncreaseInterval(unittest.TestCase):
    """Tests for action_increase_interval()."""

    def setUp(self):
        """Set up test app with mocked dependencies."""
        with patch.object(UTMDashboard, '__init__', lambda x, y: None):
            self.app = UTMDashboard.__new__(UTMDashboard)
            # Use internal storage for reactive to avoid Textual init issues
            self.app._update_interval = 2000
            self.app.notify = MagicMock()

        # Patch update_interval property
        type(self.app).update_interval = property(
            lambda self: self._update_interval,
            lambda self, v: setattr(self, '_update_interval', v)
        )

    def test_increases_to_next_step(self):
        """Should increase to next interval step."""
        self.app._update_interval = 2000
        self.app.action_increase_interval()
        self.assertEqual(self.app._update_interval, 3000)

    def test_increases_from_minimum(self):
        """Should increase from minimum interval."""
        self.app._update_interval = 500
        self.app.action_increase_interval()
        self.assertEqual(self.app._update_interval, 1000)

    def test_notifies_at_maximum(self):
        """Should notify when already at maximum."""
        self.app._update_interval = 60000
        self.app.action_increase_interval()
        self.app.notify.assert_called_once()
        self.assertIn("Maximum", self.app.notify.call_args[0][0])


class TestActionDecreaseInterval(unittest.TestCase):
    """Tests for action_decrease_interval()."""

    def setUp(self):
        """Set up test app with mocked dependencies."""
        with patch.object(UTMDashboard, '__init__', lambda x, y: None):
            self.app = UTMDashboard.__new__(UTMDashboard)
            self.app._update_interval = 2000
            self.app.notify = MagicMock()

        # Patch update_interval property
        type(self.app).update_interval = property(
            lambda self: self._update_interval,
            lambda self, v: setattr(self, '_update_interval', v)
        )

    def test_decreases_to_previous_step(self):
        """Should decrease to previous interval step."""
        self.app._update_interval = 3000
        self.app.action_decrease_interval()
        self.assertEqual(self.app._update_interval, 2000)

    def test_decreases_from_maximum(self):
        """Should decrease from maximum interval."""
        self.app._update_interval = 60000
        self.app.action_decrease_interval()
        self.assertEqual(self.app._update_interval, 30000)

    def test_notifies_at_minimum(self):
        """Should notify when already at minimum."""
        self.app._update_interval = 500
        self.app.action_decrease_interval()
        self.app.notify.assert_called_once()
        self.assertIn("Minimum", self.app.notify.call_args[0][0])


class TestActionExportSnapshot(unittest.TestCase):
    """Tests for action_export_snapshot()."""

    def setUp(self):
        """Set up test app with mocked collectors."""
        with patch.object(UTMDashboard, '__init__', lambda x, y: None):
            self.app = UTMDashboard.__new__(UTMDashboard)

            # Mock collectors
            self.app.system_collector = MagicMock()
            self.app.system_collector.get_data.return_value = {"cpu": "test"}

            self.app.services_collector = MagicMock()
            self.app.services_collector.get_data.return_value = {"services": []}

            self.app.network_collector = MagicMock()
            self.app.network_collector.get_data.return_value = {"interfaces": []}

            self.app.tasks_collector = MagicMock()
            self.app.tasks_collector.get_data.return_value = {"tasks": []}

            self.app.processes_collector = MagicMock()
            self.app.processes_collector.get_data.return_value = {"processes": []}

            self.app.users_collector = MagicMock()
            self.app.users_collector.get_data.return_value = {"users": []}

            self.app.notify = MagicMock()

    def test_creates_snapshot_file(self):
        """Should create JSON snapshot file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                self.app._do_export_snapshot()

                # Find created file
                files = list(Path(tmpdir).glob("utm_snapshot_*.json"))
                self.assertEqual(len(files), 1)

                # Verify content
                with open(files[0]) as f:
                    data = json.load(f)

                self.assertIn("timestamp", data)
                self.assertIn("hostname", data)
                self.assertIn("system", data)
                self.assertIn("services", data)
                self.assertIn("network", data)
            finally:
                os.chdir(original_cwd)

    def test_notifies_on_success(self):
        """Should notify user on successful export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                self.app._do_export_snapshot()

                self.app.notify.assert_called_once()
                self.assertIn("Snapshot", self.app.notify.call_args[0][0])
            finally:
                os.chdir(original_cwd)

    def test_handles_export_error(self):
        """Should handle export errors gracefully."""
        self.app.system_collector.get_data.side_effect = Exception("Test error")

        self.app._do_export_snapshot()

        self.app.notify.assert_called_once()
        call_kwargs = self.app.notify.call_args[1]
        self.assertEqual(call_kwargs.get('severity'), 'error')


class TestActionSwitchTab(unittest.TestCase):
    """Tests for action_switch_tab()."""

    def setUp(self):
        """Set up test app with mocked UI."""
        with patch.object(UTMDashboard, '__init__', lambda x, y: None):
            self.app = UTMDashboard.__new__(UTMDashboard)
            self.mock_tabs = MagicMock()
            self.app.query_one = MagicMock(return_value=self.mock_tabs)

    def test_switches_to_specified_tab(self):
        """Should set active tab to specified ID."""
        self.app.action_switch_tab("services")
        self.assertEqual(self.mock_tabs.active, "services")

    def test_switches_to_processes(self):
        """Should switch to processes tab."""
        self.app.action_switch_tab("processes")
        self.assertEqual(self.mock_tabs.active, "processes")

    def test_switches_to_fail2ban(self):
        """Should switch to fail2ban tab."""
        self.app.action_switch_tab("fail2ban")
        self.assertEqual(self.mock_tabs.active, "fail2ban")


class TestActionToggleSystemInfo(unittest.TestCase):
    """Tests for action_toggle_system_info()."""

    def setUp(self):
        """Set up test app with mocked UI."""
        with patch.object(UTMDashboard, '__init__', lambda x, y: None):
            self.app = UTMDashboard.__new__(UTMDashboard)
            self.mock_widget = MagicMock()
            self.mock_widget.display = True
            self.app.query_one = MagicMock(return_value=self.mock_widget)

    def test_toggles_visibility_to_false(self):
        """Should toggle display from True to False."""
        self.mock_widget.display = True
        self.app.action_toggle_system_info()
        self.assertFalse(self.mock_widget.display)

    def test_toggles_visibility_to_true(self):
        """Should toggle display from False to True."""
        self.mock_widget.display = False
        self.app.action_toggle_system_info()
        self.assertTrue(self.mock_widget.display)


class TestActionRefresh(unittest.TestCase):
    """Tests for action_refresh()."""

    def setUp(self):
        """Set up test app with mocked UI."""
        with patch.object(UTMDashboard, '__init__', lambda x, y: None):
            self.app = UTMDashboard.__new__(UTMDashboard)

    def test_refreshes_system_info_and_active_tab(self):
        """Should refresh CompactSystemInfo and the active tab widget."""
        mock_system_info = MagicMock()
        mock_system_info.update_data = MagicMock()

        mock_tab_widget = MagicMock()
        mock_tab_widget.update_data = MagicMock()

        mock_tabbed_content = MagicMock()
        mock_tabbed_content.active = "processes"

        mock_active_pane = MagicMock()
        mock_active_pane.children = [mock_tab_widget]

        def mock_query_one(selector):
            from dashboard.widgets.system_info import CompactSystemInfo
            from textual.widgets import TabbedContent
            if selector == CompactSystemInfo:
                return mock_system_info
            if selector == TabbedContent:
                return mock_tabbed_content
            if selector == "#--content-tab-processes":
                return mock_active_pane
            raise Exception(f"Unknown selector: {selector}")

        self.app.query_one = mock_query_one
        self.app.action_refresh()

        mock_system_info.update_data.assert_called()
        mock_tab_widget.update_data.assert_called()

    def test_handles_missing_widgets_gracefully(self):
        """Should not raise if widgets are not found."""
        def mock_query_one(selector):
            raise Exception("Widget not found")

        self.app.query_one = mock_query_one
        # Should not raise
        self.app.action_refresh()


class TestWatchUpdateInterval(unittest.TestCase):
    """Tests for watch_update_interval()."""

    def setUp(self):
        """Set up test app with mocked UI."""
        with patch.object(UTMDashboard, '__init__', lambda x, y: None):
            self.app = UTMDashboard.__new__(UTMDashboard)
            self.mock_system_info = MagicMock()
            self.app.query_one = MagicMock(return_value=self.mock_system_info)

    def test_updates_interval_display(self):
        """Should update system info interval display."""
        self.app.watch_update_interval(5000)
        self.mock_system_info.update_interval_display.assert_called_with(5000)

    def test_updates_timer_interval(self):
        """Should update system info timer interval."""
        self.app.watch_update_interval(5000)
        self.mock_system_info.update_timer_interval.assert_called_with(5000)

    def test_handles_query_exception(self):
        """Should handle exception when widget not found."""
        self.app.query_one.side_effect = Exception("Widget not found")
        # Should not raise
        self.app.watch_update_interval(5000)


class TestDefaultUpdateInterval(unittest.TestCase):
    """Tests for default update interval."""

    def test_default_interval_in_steps(self):
        """Default interval (2000ms) should be in interval steps."""
        self.assertIn(2000, UTMDashboard.INTERVAL_STEPS)

    def test_interval_steps_contain_default(self):
        """Interval steps should contain reasonable defaults."""
        steps = UTMDashboard.INTERVAL_STEPS
        # Should contain common intervals like 1s, 2s, 5s
        self.assertIn(1000, steps)
        self.assertIn(2000, steps)
        self.assertIn(5000, steps)


if __name__ == '__main__':
    unittest.main()
