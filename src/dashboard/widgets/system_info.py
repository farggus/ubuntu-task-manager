"""Compact System Information widget."""

import os as os_module
from collections import deque
from datetime import datetime
from typing import Any, Dict

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual import work
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Sparkline, Static

from collectors.system import SystemCollector
from utils.logger import get_logger

logger = get_logger("system_info")


class CompactSystemInfo(Horizontal):
    """Enhanced system information widget with 3 column layout."""

    DEFAULT_CSS = """
    CompactSystemInfo {
        height: 14;
        padding: 0 0;
        padding-bottom: 0;
        border: solid magenta;
        margin: 0;
        border-subtitle-align: right;
    }
    .column-1 {
        width: 1.3fr;
        padding: 0 1;
        padding-bottom: 0;
        border-right: solid $secondary;
    }
    .column-2 {
        width: 1.7fr;
        padding: 0 1;
        padding-bottom: 0;
        border-right: solid $secondary;
    }
    .column-3 {
        width: 1fr;
        padding: 0 1;
        padding-bottom: 0;
    }
    .column-1 > Label, .column-2 > Label, .column-3 > Label {
        margin-top: 0;
        margin-bottom: 1;
        height: 1;
        text-style: bold;
    }
    .spark-label {
        margin-top: 1;
        margin-bottom: 0;
        text-style: bold;
    }
    #cpu_label {
        margin-top: 0;
    }
    #freq_label {
        margin-top: 1;
    }
    .ms-container {
        height: auto;
        margin-top: 0;
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .res-group {
        width: 1fr;
        margin-right: 2;
    }
    .spark-row {
        height: 2;
        width: 100%;
        margin-bottom: 0;
    }
    .spark-row Sparkline {
        width: 1fr;
        margin: 0;
        color: $accent;
    }
    .spark-row Label {
        width: 7;
        margin-left: 1;
        text-align: right;
    }
    Sparkline {
        height: 2;
        margin: 0;
        color: $accent;
    }
    Label {
        margin-top: 1;
        margin-bottom: 0;
        text-style: bold;
    }
    .warning-text {
        color: $error;
        text-style: bold;
    }
    #basic_info, #disk_info {
        height: auto;
        padding-bottom: 0;
        margin-bottom: 0;
    }
    """

    def __init__(self, collector: SystemCollector):
        super().__init__()
        self.collector = collector
        self.cpu_history: deque = deque(maxlen=60)
        self.freq_history: deque = deque(maxlen=60)
        self.mem_history: deque = deque(maxlen=60)
        self.swap_history: deque = deque(maxlen=60)
        self.os_name = "Loading..."
        self._clock_timer = None

    def compose(self):
        # Column 1: Overview
        with Vertical(classes="column-1"):
            yield Label("Overview")
            yield Static(id="basic_info")

        # Column 2: Resources
        with Vertical(classes="column-2"):
            yield Label("Resources History")

            yield Label("CPU Load: N/A | Load Avg: N/A", id="cpu_label", classes="spark-label")
            yield Sparkline([], summary_function=max, id="cpu_spark")

            yield Label("CPU Frequency: N/A", id="freq_label", classes="spark-label")
            yield Sparkline([], summary_function=max, id="freq_spark")

            # Memory and Swap
            with Horizontal(classes="ms-container"):
                # Memory
                with Vertical(classes="res-group"):
                    yield Label("RAM Usage", id="mem_header", classes="spark-label")
                    with Horizontal(classes="spark-row"):
                        yield Sparkline([], summary_function=max, id="mem_spark")
                        yield Label("N/A%", id="mem_percent")

                # Swap
                with Vertical(classes="res-group"):
                    yield Label("SWAP Usage", id="swap_header", classes="spark-label")
                    with Horizontal(classes="spark-row"):
                        yield Sparkline([], summary_function=max, id="swap_spark")
                        yield Label("N/A%", id="swap_percent")

        # Column 3: Disk
        with Vertical(classes="column-3"):
            yield Label("System Disk Usage")
            yield Static(id="disk_info")

    def on_mount(self) -> None:
        """Update data when mounted."""
        # Initialize interval display
        interval = getattr(self.app, 'update_interval', 2000)
        self.border_subtitle = f"[dim]-[/dim] [bold cyan]{interval}[/bold cyan] [dim]+[/dim]"

        # Initial fetch of OS info
        self._fetch_initial_os_info()

        # Start clock timer (independent of data update)
        self.update_header_clock()
        self._clock_timer = self.set_interval(1.0, self.update_header_clock)

        self.update_data()
        # Use initial interval from app (convert ms to seconds)
        self._update_timer = self.set_interval(interval / 1000, self.update_data)

    @work(thread=True)
    def _fetch_initial_os_info(self) -> None:
        """Fetch OS info once asynchronously."""
        try:
            os_info = self.collector._get_os_info()
            self.os_name = os_info.get('pretty_name', 'Linux')
            # Trigger immediate header update
            self.app.call_from_thread(self.update_header_clock)
        except Exception as e:
            logger.debug(f"Failed to fetch initial OS info: {e}")

    def update_header_clock(self) -> None:
        """Update header with current time and OS info."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.border_title = f"[dim]^S[/dim] [bold magenta]System Information | {self.os_name} | {timestamp}[/bold magenta]"

    def update_timer_interval(self, interval_ms: int) -> None:
        """Update the refresh timer with new interval."""
        if hasattr(self, '_update_timer'):
            self._update_timer.stop()

        # Convert ms to seconds for set_interval
        self._update_timer = self.set_interval(interval_ms / 1000, self.update_data)
        logger.debug(f"System info interval updated to {interval_ms}ms")

    @work(exclusive=True, thread=True)
    def update_data(self) -> None:
        """Update system data in background."""
        data = self.collector.update()
        if data.get('error'):
            self.notify(f"System Info Error: {data['error']}", severity="error")
        self.app.call_from_thread(self.update_ui, data)

    def update_ui(self, data: Dict[str, Any]) -> None:
        """Update UI elements on main thread."""
        if not data:
            return

        # Border title is handled by update_header_clock

        # Update interval display
        interval = getattr(self.app, 'update_interval', 2000)
        self.border_subtitle = f"[dim]-[/dim] [bold cyan]{interval}[/bold cyan] [dim]+[/dim]"

        # 1. Update Sparklines and Labels

        # CPU Load & Load Avg
        cpu_usage = data.get('cpu', {}).get('usage_total', 0)
        self.cpu_history.append(cpu_usage)
        self.query_one("#cpu_spark", Sparkline).data = list(self.cpu_history)

        cpu_text = Text()
        cpu_text.append("CPU Load ", style="bold cyan")
        cpu_text.append(f"{cpu_usage}%", style="bold white")

        try:
            load_avg = os_module.getloadavg()
            load_str = f"{load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}"
            cpu_text.append(" | ", style="dim")
            cpu_text.append("Load Avg ", style="bold cyan")
            cpu_text.append(load_str, style="bold yellow")
        except Exception as e:
            logger.debug(f"Failed to get load average: {e}")

        self.query_one("#cpu_label", Label).update(cpu_text)

        # Frequency
        cpu_freq = data.get('cpu', {}).get('frequency', {})
        current_freq = cpu_freq.get('current', 0)
        self.freq_history.append(current_freq)
        self.query_one("#freq_spark", Sparkline).data = list(self.freq_history)

        freq_text = Text()
        freq_text.append("CPU Frequency ", style="bold cyan")
        freq_text.append(f"{current_freq:.0f} MHz", style="bold white")
        self.query_one("#freq_label", Label).update(freq_text)

        # Memory
        try:
            mem_info = data.get('memory', {})
            mem_percent = mem_info.get('percent', 0)
            mem_used_gb = mem_info.get('used', 0) / (1024**3)
            mem_total_gb = mem_info.get('total', 0) / (1024**3)

            self.mem_history.append(mem_percent)
            self.query_one("#mem_spark", Sparkline).data = list(self.mem_history)

            mem_text = Text()
            mem_text.append("RAM Usage ", style="bold cyan")
            mem_text.append(f"[{mem_used_gb:.1f}GB of {mem_total_gb:.1f}GB]", style="dim white")
            self.query_one("#mem_header", Label).update(mem_text)

            p_style = "green"
            if mem_percent > 80:
                p_style = "red"
            elif mem_percent > 60:
                p_style = "yellow"
            self.query_one("#mem_percent", Label).update(Text(f"{mem_percent}%", style=f"bold {p_style}"))
        except Exception as e:
            logger.debug(f"Failed to update memory info: {e}")

        # Swap
        try:
            swap_info = mem_info.get('swap', {})
            swap_percent = swap_info.get('percent', 0)
            swap_used_gb = swap_info.get('used', 0) / (1024**3)
            swap_total_gb = swap_info.get('total', 0) / (1024**3)

            self.swap_history.append(swap_percent)
            self.query_one("#swap_spark", Sparkline).data = list(self.swap_history)

            swap_text = Text()
            swap_text.append("SWAP Usage ", style="bold cyan")
            swap_text.append(f"[{swap_used_gb:.1f}GB of {swap_total_gb:.1f}GB]", style="dim white")
            self.query_one("#swap_header", Label).update(swap_text)

            p_style = "green"
            if swap_percent > 50:
                p_style = "red"
            elif swap_percent > 20:
                p_style = "yellow"
            self.query_one("#swap_percent", Label).update(Text(f"{swap_percent}%", style=f"bold {p_style}"))
        except Exception as e:
            logger.debug(f"Failed to update swap info: {e}")

        # 2. Update Basic Info Column
        try:
            basic_info_panel = self._render_basic_info(data)
            self.query_one("#basic_info", Static).update(basic_info_panel)
        except Exception as e:
            logger.error(f"Failed to update basic info: {e}")

        # 3. Update Disk Info Column
        try:
            disk_info_panel = self._render_disk_info(data)
            self.query_one("#disk_info", Static).update(disk_info_panel)
        except Exception as e:
            logger.error(f"Failed to update disk info: {e}")

    def _format_uptime(self, seconds: int) -> str:
        """Helper to format uptime in a clear way."""
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        return " ".join(parts) if parts else "< 1m"

    def _render_basic_info(self, data: Dict[str, Any]) -> Table:
        """Render basic system information table."""
        os_info = data.get('os', {})
        cpu_info = data.get('cpu', {})
        uptime_info = data.get('uptime', {})
        hostname = data.get('hostname', 'N/A')
        processes_info = data.get('processes', {})
        network_info = data.get('network', {})

        # Compact table, no extra padding
        table = Table(show_header=False, box=None, padding=(0, 1, 0, 1), expand=False)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Hostname", Text(hostname, style="bold cyan"))
        table.add_row("IP Address", Text(network_info.get('ip', 'N/A'), style="green"))

        # Display Kernel release
        table.add_row("Kernel", os_info.get('release', 'N/A'))

        # Formatted Uptime
        uptime_secs = uptime_info.get('uptime_seconds', 0)
        table.add_row("Uptime", self._format_uptime(uptime_secs))

        cpu_cores = f"{cpu_info.get('physical_cores', 0)}/{cpu_info.get('total_cores', 0)}"
        table.add_row("Cores (P/T)", cpu_cores)

        # Temperature
        temp = cpu_info.get('temperature', 0)
        temp_style = "red" if temp > 75 else "yellow" if temp > 60 else "green"
        table.add_row("Temperature", Text(f"{temp:.1f}°C", style=temp_style) if temp > 0 else "N/A")

        # Users
        users_count = data.get('users', 0)
        table.add_row("Users logged in", str(users_count))

        # Processes
        total_procs = processes_info.get('total', 0)
        zombies = processes_info.get('zombies', 0)

        proc_text = Text(f"{total_procs}", style="white")
        if zombies > 0:
            proc_text.append(f" ({zombies} zombies)", style="bold red")
        table.add_row("Processes", proc_text)

        # Services
        services_stats = data.get('services_stats', {})
        active_svc = services_stats.get('active', 0)
        failed_svc = services_stats.get('failed', 0)

        svc_text = Text(f"{active_svc}", style="white")
        if failed_svc > 0:
            svc_text.append(f" ({failed_svc} failed)", style="bold red")
        table.add_row("Services", svc_text)

        # Packages
        pkg_stats = data.get('packages', {})
        pkg_total = pkg_stats.get('total', 0)
        pkg_upd = pkg_stats.get('updates', 0)

        pkg_text = Text(f"{pkg_total}", style="white")
        if pkg_upd > 0:
            pkg_text.append(f" ({pkg_upd} updates available)", style="bold red")
        table.add_row("Packages", pkg_text)

        return table

    def _render_disk_info(self, data: Dict[str, Any]) -> Group:
        """Render disk usage information."""
        disk_info = data.get('disk', {})
        partitions = disk_info.get('partitions', [])

        # Priority partitions
        priority_mounts = ['/', '/boot', '/boot/efi', '/home']
        main_partitions = []

        # Filter and sort by priority
        for mount in priority_mounts:
            for p in partitions:
                if p.get('mountpoint') == mount:
                    main_partitions.append(p)
                    break

        # Table for main partitions
        table = Table(show_header=True, box=None, padding=(0, 1), expand=True)
        table.add_column("Mount", style="cyan")
        table.add_column("Used", style="white")
        table.add_column("Size", style="dim")
        table.add_column("%", style="bold")

        for p in main_partitions:
            mount = p.get('mountpoint')
            total = p.get('total', 0) / (1024**3)
            used = p.get('used', 0) / (1024**3)
            percent = p.get('percent', 0)

            style = "green"
            if percent > 90:
                style = "red"
            elif percent > 75:
                style = "yellow"

            table.add_row(
                mount,
                f"{used:.1f}G",
                f"{total:.1f}G",
                Text(f"{percent}%", style=style)
            )

        # Warning section for ANY full disks
        warnings = []
        for p in partitions:
            if p.get('percent', 0) > 90:
                mount = p.get('mountpoint')
                percent = p.get('percent')
                warnings.append(Text(f"⚠  {mount}: {percent}% FULL", style="bold red"))

        if warnings:
            return Group(table, "", *warnings)

        return Group(table)

    def update_interval_display(self, interval: int) -> None:
        """Update the interval display in border subtitle."""
        self.border_subtitle = f"[dim]-[/dim] [bold cyan]{interval}[/bold cyan] [dim]+[/dim]"
