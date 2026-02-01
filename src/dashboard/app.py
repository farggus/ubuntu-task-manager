"""Main dashboard application using Textual with tabbed interface."""

import json
import os as os_module
import platform
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import Footer, Header, TabbedContent, TabPane

from collectors import (
    Fail2banCollector,
    NetworkCollector,
    ProcessesCollector,
    ServicesCollector,
    SystemCollector,
    TasksCollector,
    UsersCollector,
)
from dashboard.widgets.containers import ContainersTab
from dashboard.widgets.disks import DisksTab
from dashboard.widgets.fail2ban import Fail2banTab
from dashboard.widgets.fail2ban_plus import Fail2banPlusTab
from dashboard.widgets.logging import LoggingTab
from dashboard.widgets.network import NetworkExtendedTab
from dashboard.widgets.packages import PackagesTab
from dashboard.widgets.processes import ProcessesTab
from dashboard.widgets.services import ServicesTab
from dashboard.widgets.system_info import CompactSystemInfo
from dashboard.widgets.tasks import TasksExtendedTab
from dashboard.widgets.users import UsersTab
from utils.logger import get_logger

logger = get_logger("dashboard")


class UTMDashboard(App):
    """Main dashboard application with tabbed interface."""

    # Global update interval in ms (default 2000)
    update_interval = reactive(2000)

    CSS = """
    Screen {
        layout: vertical;
        padding: 0;
    }
    .main-container {
        height: 1fr;
        padding: 0 2;
    }
    TabbedContent {
        height: 1fr;
    }
    DataTable, RichLog {
        height: 1fr;
        border: solid $secondary;
    }
    .help-text {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $boost;
    }
    """

    BINDINGS = [
        # System bindings (Left)
        Binding("ctrl+q", "quit", "Quit"),
        # Update interval controls
        Binding("plus", "increase_interval", "+", show=False),
        Binding("equals", "increase_interval", "+", show=False),  # For keyboards without numpad
        Binding("minus", "decrease_interval", "-", show=False),
        # Global UI Toggles
        Binding("ctrl+s", "toggle_system_info", "Toggle System Info", show=False),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("ctrl+e", "export_snapshot", "Export Snapshot JSON"),
        # Navigation (Hidden)
        Binding("1", "switch_tab('processes')", "Processes", show=False),
        Binding("2", "switch_tab('services')", "Services", show=False),
        Binding("3", "switch_tab('packages')", "Packages", show=False),
        Binding("4", "switch_tab('containers')", "Containers", show=False),
        Binding("5", "switch_tab('tasks')", "Tasks", show=False),
        Binding("6", "switch_tab('network')", "Network", show=False),
        Binding("F", "switch_tab('fail2ban')", "Fail2ban", show=False),
        Binding("shift+f", "switch_tab('fail2ban_plus')", "Fail2ban+", show=False),
        Binding("7", "switch_tab('users')", "Users", show=False),
        Binding("8", "switch_tab('disks')", "Disks", show=False),
        Binding("0", "switch_tab('logging')", "Logging", show=False),
    ]

    # Interval steps in ms
    INTERVAL_STEPS = [500, 1000, 2000, 3000, 5000, 10000, 30000, 60000]

    def __init__(self, config_path: str = "config.yaml"):
        super().__init__()
        self.title = f"{platform.node()} UTM"
        self.config = self.load_config(config_path)
        # Lazy-initialized collectors (created on first access)
        self._system_collector: SystemCollector | None = None
        self._services_collector: ServicesCollector | None = None
        self._network_collector: NetworkCollector | None = None
        self._fail2ban_collector: Fail2banCollector | None = None
        self._tasks_collector: TasksCollector | None = None
        self._processes_collector: ProcessesCollector | None = None
        self._users_collector: UsersCollector | None = None

    @property
    def system_collector(self) -> SystemCollector:
        """Lazy-initialized SystemCollector."""
        if self._system_collector is None:
            self._system_collector = SystemCollector(self.config)
        return self._system_collector

    @system_collector.setter
    def system_collector(self, value: SystemCollector) -> None:
        self._system_collector = value

    @property
    def services_collector(self) -> ServicesCollector:
        """Lazy-initialized ServicesCollector."""
        if self._services_collector is None:
            self._services_collector = ServicesCollector(self.config)
        return self._services_collector

    @services_collector.setter
    def services_collector(self, value: ServicesCollector) -> None:
        self._services_collector = value

    @property
    def network_collector(self) -> NetworkCollector:
        """Lazy-initialized NetworkCollector."""
        if self._network_collector is None:
            self._network_collector = NetworkCollector(self.config)
        return self._network_collector

    @network_collector.setter
    def network_collector(self, value: NetworkCollector) -> None:
        self._network_collector = value

    @property
    def fail2ban_collector(self) -> Fail2banCollector:
        """Lazy-initialized Fail2banCollector."""
        if self._fail2ban_collector is None:
            self._fail2ban_collector = Fail2banCollector(self.config)
        return self._fail2ban_collector

    @fail2ban_collector.setter
    def fail2ban_collector(self, value: Fail2banCollector) -> None:
        self._fail2ban_collector = value

    @property
    def tasks_collector(self) -> TasksCollector:
        """Lazy-initialized TasksCollector."""
        if self._tasks_collector is None:
            self._tasks_collector = TasksCollector(self.config)
        return self._tasks_collector

    @tasks_collector.setter
    def tasks_collector(self, value: TasksCollector) -> None:
        self._tasks_collector = value

    @property
    def processes_collector(self) -> ProcessesCollector:
        """Lazy-initialized ProcessesCollector."""
        if self._processes_collector is None:
            self._processes_collector = ProcessesCollector(self.config)
        return self._processes_collector

    @processes_collector.setter
    def processes_collector(self, value: ProcessesCollector) -> None:
        self._processes_collector = value

    @property
    def users_collector(self) -> UsersCollector:
        """Lazy-initialized UsersCollector."""
        if self._users_collector is None:
            self._users_collector = UsersCollector(self.config)
        return self._users_collector

    @users_collector.setter
    def users_collector(self, value: UsersCollector) -> None:
        self._users_collector = value

    def load_config(self, config_path: str) -> Dict[str, Any]:
        path = Path(config_path)
        config = {}
        if path.exists():
            with open(path, 'r') as f:
                config = yaml.safe_load(f) or {}

        # Environment variable overrides
        # Docker settings
        if os_module.getenv('UTM_DOCKER_ENABLED'):
            if 'docker' not in config:
                config['docker'] = {}
            config['docker']['enabled'] = os_module.getenv('UTM_DOCKER_ENABLED').lower() == 'true'

        if os_module.getenv('UTM_DOCKER_SOCKET'):
            if 'docker' not in config:
                config['docker'] = {}
            config['docker']['socket'] = os_module.getenv('UTM_DOCKER_SOCKET')

        return config

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(classes="main-container"):
            yield CompactSystemInfo(self.system_collector)

            with TabbedContent(initial="processes"):
                with TabPane("[b green]1[/] Processes", id="processes"):
                    yield ProcessesTab(self.processes_collector)

                with TabPane("[b green]2[/] Services", id="services"):
                    yield ServicesTab(self.services_collector)

                with TabPane("[b green]3[/] Packages", id="packages"):
                    yield PackagesTab(self.system_collector)

                with TabPane("[b green]4[/] Containers", id="containers"):
                    yield ContainersTab(self.services_collector)

                with TabPane("[b green]5[/] Tasks", id="tasks"):
                    yield TasksExtendedTab(self.tasks_collector)

                with TabPane("[b green]6[/] Network", id="network"):
                    yield NetworkExtendedTab(self.network_collector)

                with TabPane("[b green]F[/] Fail2ban", id="fail2ban"):
                    yield Fail2banTab(self.fail2ban_collector)

                with TabPane("[b cyan]F+[/] Fail2ban+", id="fail2ban_plus"):
                    yield Fail2banPlusTab()

                with TabPane("[b green]7[/] Users", id="users"):
                    yield UsersTab(self.users_collector)

                with TabPane("[b green]8[/] Disks", id="disks"):
                    yield DisksTab(self.system_collector)

                with TabPane("[b green]0[/] Logging", id="logging"):
                    yield LoggingTab()

        yield Footer()

    def action_toggle_system_info(self) -> None:
        """Toggle visibility of the System Information widget."""
        system_info = self.query_one(CompactSystemInfo)
        system_info.display = not system_info.display

    def action_refresh(self) -> None:
        """Refresh only CompactSystemInfo and the active tab."""
        # Always refresh system info panel
        try:
            self.query_one(CompactSystemInfo).update_data()
        except Exception:
            pass

        # Refresh only the active tab widget
        try:
            active_tab_id = self.query_one(TabbedContent).active
            # Find the widget inside the active TabPane
            active_pane = self.query_one(f"#--content-tab-{active_tab_id}")
            for child in active_pane.children:
                if hasattr(child, 'update_data'):
                    child.update_data()
                    break
        except Exception as e:
            logger.debug(f"Could not refresh active tab: {e}")

    @work(thread=True)
    def action_export_snapshot(self) -> None:
        """Export current state of all collectors to a JSON file (non-blocking wrapper)."""
        self._do_export_snapshot(notify_via_thread=True)

    def _do_export_snapshot(self, notify_via_thread: bool = False) -> None:
        """Export current state of all collectors to a JSON file.

        Args:
            notify_via_thread: If True, use call_from_thread for notifications (when called from @work).
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"utm_snapshot_{timestamp}.json"

            # Collect data from all collectors
            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "hostname": platform.node(),
                "system": self.system_collector.get_data(),
                "services": self.services_collector.get_data(),
                "network": self.network_collector.get_data(),
                "tasks": self.tasks_collector.get_data(),
                "processes": self.processes_collector.get_data(),
                "users": self.users_collector.get_data()
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, default=str)

            logger.info(f"Snapshot exported to {filename}")
            if notify_via_thread:
                self.call_from_thread(self.notify, f"Snapshot saved to {filename}", severity="information")
            else:
                self.notify(f"Snapshot saved to {filename}", severity="information")

        except Exception as e:
            logger.error(f"Failed to export snapshot: {e}")
            if notify_via_thread:
                self.call_from_thread(self.notify, f"Export failed: {e}", severity="error")
            else:
                self.notify(f"Export failed: {e}", severity="error")

    def action_switch_tab(self, tab_id: str) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = tab_id

    def action_increase_interval(self) -> None:
        """Increase update interval (slower updates)."""
        current = self.update_interval
        for step in self.INTERVAL_STEPS:
            if step > current:
                self.update_interval = step
                return
        # Already at max
        self.notify("Maximum interval reached", severity="warning")

    def action_decrease_interval(self) -> None:
        """Decrease update interval (faster updates)."""
        current = self.update_interval
        for step in reversed(self.INTERVAL_STEPS):
            if step < current:
                self.update_interval = step
                return
        # Already at min
        self.notify("Minimum interval reached", severity="warning")

    def watch_update_interval(self, new_interval: int) -> None:
        """React to interval changes - update system info display and widgets."""
        try:
            system_info = self.query_one(CompactSystemInfo)
            system_info.update_interval_display(new_interval)
            system_info.update_timer_interval(new_interval)
        except Exception as e:
            logger.debug(f"Could not update system info interval display: {e}")
