"""Processes tab widget with filtering."""

import os
import signal
from typing import Any, Dict

import psutil
from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static

from collectors import ProcessesCollector
from utils.logger import get_logger
from utils.ui_helpers import update_table_preserving_scroll

logger = get_logger("processes_tab")

# Column key to process data field mapping
COLUMN_SORT_KEYS = {
    "PID": ("pid", int),
    "Name": ("name", str),
    "User": ("user", str),
    "Status": ("status", str),
    "CPU%": ("cpu", float),
    "Mem%": ("mem_pct", float),
    "Parent": ("ppid", int),
    "Command": ("command", str),
}


class ProcessesTab(Vertical):
    """Tab displaying running processes with filtering."""

    BINDINGS = [
        Binding("a", "view_all", "All Processes"),
        Binding("z", "view_zombies", "Zombies"),
        Binding("c", "clean_zombie", "Clean Zombie (SIGCHLD)"),
        Binding("k", "kill_parent", "Kill Parent (SIGTERM)"),
    ]

    DEFAULT_CSS = """
    ProcessesTab {
        height: 1fr;
        padding: 0;
    }
    #proc_header_container {
        height: 3;
        margin: 0;
        padding: 0 1;
        border: round $success;
        margin-bottom: 0;
    }
    #proc_header {
        margin: 0;
        padding: 0;
        width: 100%;
        text-align: left;
    }
    #proc_table {
        height: 1fr;
        margin: 0;
        padding: 0;
    }
    """

    def __init__(self, collector: ProcessesCollector):
        super().__init__()
        self.collector = collector
        self.view_mode = 'all'  # 'all' or 'zombies'
        self.sort_column = "CPU%"  # Default sort column
        self.sort_reverse = True  # Default descending (highest CPU first)
        self._last_data: Dict[str, Any] = {}  # Cache for re-sorting
        self._data_loaded = False  # Lazy loading flag

    def compose(self):
        # Header
        with Static(id="proc_header_container"):
            yield Label("Loading processes...", id="proc_header")

        # Single table for all views
        yield DataTable(id="proc_table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Setup table structure (no data loading)."""
        table = self.query_one(DataTable)
        table.add_columns("PID", "Name", "User", "Status", "CPU%", "Mem%", "Parent", "Command")

    def on_show(self) -> None:
        """Load data when tab becomes visible."""
        if not self._data_loaded:
            self._data_loaded = True
            self.update_data()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle click on column header to sort by that column."""
        column_label = str(event.label)
        if column_label in COLUMN_SORT_KEYS:
            if self.sort_column == column_label:
                # Toggle sort direction if clicking same column
                self.sort_reverse = not self.sort_reverse
            else:
                # New column: set default direction
                self.sort_column = column_label
                # Numeric columns default to descending, text to ascending
                self.sort_reverse = column_label in ("CPU%", "Mem%", "PID", "Parent")

            direction = "↓" if self.sort_reverse else "↑"
            self.notify(f"Sorted by {column_label} {direction}")
            # Re-render with cached data using new sort order
            if self._last_data:
                self.update_table(self._last_data)

    def action_view_all(self) -> None:
        """Switch to 'all' processes view."""
        if self.view_mode != 'all':
            self.view_mode = 'all'
            self.notify("Showing all processes")
            self.update_data()

    def action_view_zombies(self) -> None:
        """Switch to 'zombies' view."""
        if self.view_mode != 'zombies':
            self.view_mode = 'zombies'
            self.notify("Showing zombie processes")
            self.update_data()

    def action_clean_zombie(self) -> None:
        """Send SIGCHLD to the parent of the selected zombie process."""
        self._signal_parent(signal.SIGCHLD, "clean")

    def action_kill_parent(self) -> None:
        """Send SIGTERM to the parent of the selected zombie process."""
        self._signal_parent(signal.SIGTERM, "kill")

    def _signal_parent(self, sig, action_name: str) -> None:
        """Helper to send a signal to the parent process."""
        table = self.query_one("#proc_table", DataTable)
        if self.view_mode != 'zombies' or table.cursor_row is None:
            self.notify("This action is only for zombies in the Zombies view", severity="warning")
            return

        try:
            row = table.get_row_at(table.cursor_row)
            ppid_str = str(row[6]) # Parent PID is 7th column
            if ppid_str and ppid_str.isdigit():
                ppid = int(ppid_str)
                os.kill(ppid, sig)
                sig_name = "SIGTERM" if sig == signal.SIGTERM else "SIGCHLD"
                self.notify(f"Sent {sig_name} to parent PID {ppid}", severity="information")
                self.update_data()
            else:
                self.notify("Could not find Parent PID", severity="error")
        except (ProcessLookupError, ValueError, IndexError) as e:
            self.notify(f"Error sending signal: {e}", severity="error")

    @work(exclusive=True, thread=True)
    def update_data(self) -> None:
        """Update data in background."""
        data = self.collector.update()
        self.app.call_from_thread(self.update_table, data)

    def update_table(self, data: Dict[str, Any]) -> None:
        """Update table and header on main thread."""
        self._last_data = data  # Cache for re-sorting
        table = self.query_one(DataTable)

        processes = data.get('processes', [])

        def populate(t):
            # Filter based on view mode
            if self.view_mode == 'zombies':
                filtered_list = [p for p in processes if p.get('status') == psutil.STATUS_ZOMBIE]
            else:
                filtered_list = processes

            # Apply sorting
            if self.sort_column in COLUMN_SORT_KEYS:
                field, type_fn = COLUMN_SORT_KEYS[self.sort_column]
                try:
                    filtered_list = sorted(
                        filtered_list,
                        key=lambda x: type_fn(x.get(field, 0) or 0),
                        reverse=self.sort_reverse
                    )
                except (ValueError, TypeError):
                    pass  # Fall back to original order if sorting fails

            for p in filtered_list[:1000]:  # Limit to 1000 rows for performance
                pid = str(p.get('pid', ''))
                name = p.get('name', '')
                user = p.get('user', '')
                status = p.get('status', '')
                cpu = f"{p.get('cpu', 0):.1f}"
                mem = f"{p.get('mem_pct', 0):.1f}"
                cmd = p.get('command', '')
                ppid = str(p.get('ppid', ''))

                # Display running* for sleeping processes with CPU usage
                status_display = status
                status_style = "white"

                if status == psutil.STATUS_SLEEPING and p.get('cpu', 0.0) > 0.0:
                    status_display = "running*"
                    status_style = "bold green"
                elif status == psutil.STATUS_RUNNING:
                    status_style = "bold green"
                elif status == psutil.STATUS_ZOMBIE:
                    status_style = "bold red"
                elif status == psutil.STATUS_STOPPED:
                    status_style = "dim"

                t.add_row(pid, name, user, Text(status_display, style=status_style), cpu, mem, ppid, cmd)

        update_table_preserving_scroll(table, populate)

        # Update Header
        stats = data.get('stats', {})
        total = stats.get('total', 0)
        running = stats.get('running', 0)
        sleeping = stats.get('sleeping', 0)
        zombies = stats.get('zombies', 0)
        other = stats.get('other', 0)

        zombie_color = "red" if zombies > 0 else "green"

        header_text = (
            f"[bold cyan]Total: {total}[/bold cyan] | "
            f"[bold green]Running: {running}[/bold green] | "
            f"[bold blue]Sleeping: {sleeping}[/bold blue] | "
            f"[bold {zombie_color}]Zombies: {zombies}[/bold {zombie_color}] | "
            f"[dim white]Other: {other}[/dim white]"
        )
        self.query_one("#proc_header", Label).update(header_text)
