"""Processes tab widget with filtering."""

from textual import work
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static
from textual.binding import Binding
from rich.text import Text
import psutil
import os
import signal
from typing import Dict, Any

from collectors import ProcessesCollector
from utils.logger import get_logger
from utils.ui_helpers import update_table_preserving_scroll

logger = get_logger("processes_tab")


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

    def compose(self):
        # Header
        with Static(id="proc_header_container"):
            yield Label("Loading processes...", id="proc_header")

        # Single table for all views
        yield DataTable(id="proc_table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Setup table and start updates."""
        table = self.query_one(DataTable)
        table.add_columns("PID", "Name", "User", "Status", "CPU%", "Mem%", "Parent", "Command")
        self.update_data()
        self.set_interval(5, self.update_data)

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
        table = self.query_one(DataTable)
        
        processes = data.get('processes', [])
        
        def populate(t):
            # Filter based on view mode
            if self.view_mode == 'zombies':
                filtered_list = [p for p in processes if p.get('status') == psutil.STATUS_ZOMBIE]
            else:
                filtered_list = processes

            for p in filtered_list[:1000]: # Limit to 1000 rows for performance
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
