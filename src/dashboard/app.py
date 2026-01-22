"""Main dashboard application using Textual with tabbed interface."""

import json
import os as os_module
import platform
import subprocess
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Label, Sparkline, Static, TabbedContent, TabPane

from collectors import (
    NetworkCollector,
    ProcessesCollector,
    ServicesCollector,
    SystemCollector,
    TasksCollector,
    UsersCollector,
)
from dashboard.widgets.containers import ContainersTab
from dashboard.widgets.disks import DisksTab
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
        Binding("ctrl+r", "refresh", "Refresh All"),
        Binding("ctrl+s", "export_snapshot", "Export Snapshot JSON"),
        # Update interval controls
        Binding("plus", "increase_interval", "+", show=False),
        Binding("equals", "increase_interval", "+", show=False),  # For keyboards without numpad
        Binding("minus", "decrease_interval", "-", show=False),
        # Navigation (Hidden)
        Binding("1", "switch_tab('processes')", "Processes", show=False),
        Binding("2", "switch_tab('services')", "Services", show=False),
        Binding("3", "switch_tab('packages')", "Packages", show=False),
        Binding("4", "switch_tab('containers')", "Containers", show=False),
        Binding("5", "switch_tab('tasks')", "Tasks", show=False),
        Binding("6", "switch_tab('network')", "Network", show=False),
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
        self.system_collector = SystemCollector(self.config)
        self.services_collector = ServicesCollector(self.config)
        self.network_collector = NetworkCollector(self.config)
        self.tasks_collector = TasksCollector(self.config)
        self.processes_collector = ProcessesCollector(self.config)
        self.users_collector = UsersCollector(self.config)

    def load_config(self, config_path: str) -> Dict[str, Any]:
        path = Path(config_path)
        config = {}
        if path.exists():
            with open(path, 'r') as f:
                config = yaml.safe_load(f) or {}
        
        # Environment variable overrides
        # Docker settings
        if os_module.getenv('UTM_DOCKER_ENABLED'):
            if 'docker' not in config: config['docker'] = {}
            config['docker']['enabled'] = os_module.getenv('UTM_DOCKER_ENABLED').lower() == 'true'
            
        if os_module.getenv('UTM_DOCKER_SOCKET'):
             if 'docker' not in config: config['docker'] = {}
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

                with TabPane("[b green]7[/] Users", id="users"):
                    yield UsersTab(self.users_collector)

                with TabPane("[b green]8[/] Disks", id="disks"):
                    yield DisksTab(self.system_collector)

                with TabPane("[b green]0[/] Logging", id="logging"):
                    yield LoggingTab()
        
        yield Footer()

    def action_refresh(self) -> None:
        for widget in self.query(Static):
            if hasattr(widget, 'update_data'):
                widget.update_data()
        for widget in self.query(Vertical):
             if hasattr(widget, 'update_data'):
                widget.update_data()
        for widget in self.query(Horizontal): # CompactSystemInfo
             if hasattr(widget, 'update_data'):
                widget.update_data()

    def action_export_snapshot(self) -> None:
        """Export current state of all collectors to a JSON file."""
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
                "processes": self.processes_collector.get_data(), # Note: this might be large
                "users": self.users_collector.get_data()
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, default=str)
                
            logger.info(f"Snapshot exported to {filename}")
            self.notify(f"Snapshot saved to {filename}", severity="information")
            
        except Exception as e:
            logger.error(f"Failed to export snapshot: {e}")
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
        except Exception as e:
            logger.debug(f"Could not update system info interval display: {e}")

        # Update DisksTab interval
        try:
            disks_tab = self.query_one(DisksTab)
            disks_tab.set_update_interval(new_interval)
        except Exception as e:
            logger.debug(f"Could not update DisksTab interval: {e}")