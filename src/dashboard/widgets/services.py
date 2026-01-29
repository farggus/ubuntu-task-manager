"""Services tab widget."""

import subprocess
from typing import Any, Dict

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static

from collectors import ServicesCollector
from utils.binaries import SUDO, SYSTEMCTL
from utils.logger import get_logger
from utils.ui_helpers import update_table_preserving_scroll

logger = get_logger("services_tab")


class ServicesTab(Vertical):
    """Tab displaying systemd services using DataTable."""

    BINDINGS = [
        Binding("r", "restart_service", "Restart"),
        Binding("s", "start_service", "Start"),
        Binding("k", "stop_service", "Stop"),
    ]

    DEFAULT_CSS = """
    ServicesTab {
        height: 1fr;
        padding: 0;
    }
    #svc_header_container {
        height: 3;
        margin: 0;
        padding: 0 1;
        border: round $success;
        margin-bottom: 0;
    }
    #svc_header {
        margin: 0;
        padding: 0;
        width: 100%;
        text-align: left;
    }
    #services_table {
        margin: 0;
        padding: 0;
    }
    """

    def __init__(self, collector: ServicesCollector):
        super().__init__()
        self.collector = collector

    def compose(self):
        # Header
        with Static(id="svc_header_container"):
            yield Label("Loading services...", id="svc_header")

        yield DataTable(id="services_table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Setup table and start updates."""
        table = self.query_one(DataTable)
        table.add_column("Service", width=30)
        table.add_column("User", width=15)
        table.add_column("State", width=15)
        table.add_column("SubState", width=15)
        table.add_column("Description")
        
        self.update_data()

    def action_restart_service(self) -> None:
        self._manage_service("restart")

    def action_start_service(self) -> None:
        self._manage_service("start")

    def action_stop_service(self) -> None:
        self._manage_service("stop")

    def _manage_service(self, action: str) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            self.notify("No service selected", severity="warning")
            return
            
        try:
            row = table.get_row_at(table.cursor_row)
            service_name = str(row[0]) 
            self.notify(f"Initiating {action} for {service_name}...", severity="information")
            logger.info(f"User requested {action} for service: {service_name}")
            self.run_service_command(service_name, action)
        except Exception as e:
            logger.error(f"Error selecting service: {e}")
            self.notify(f"Error: {e}", severity="error")

    @work(thread=True)
    def run_service_command(self, service_name: str, action: str) -> None:
        """Run systemctl command in background."""
        if any(c in service_name for c in ';|&'):
             msg = f"Invalid service name: {service_name}"
             logger.warning(f"Security alert: {msg}")
             self.app.call_from_thread(self.notify, msg, severity="error")
             return

        try:
            cmd = [SUDO, SYSTEMCTL, action, service_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"Successfully {action}ed service: {service_name}")
                self.app.call_from_thread(self.notify, f"Successfully {action}ed {service_name}", severity="information")
                self.update_data()
            else:
                err_msg = result.stderr.strip() or "Unknown error"
                logger.error(f"Failed to {action} service {service_name}: {err_msg}")
                self.app.call_from_thread(self.notify, f"Failed to {action}: {err_msg}", severity="error")
        except Exception as e:
            logger.exception(f"Exception during {action} service {service_name}")
            self.app.call_from_thread(self.notify, f"Exception: {e}", severity="error")

    @work(exclusive=True, thread=True)
    def update_data(self) -> None:
        """Update services data in background."""
        data = self.collector.update()
        if data.get('error'):
            self.notify(f"Services Data Error: {data['error']}", severity="error")
        self.app.call_from_thread(self.update_table, data)

    def update_table(self, data: Dict[str, Any]) -> None:
        """Update table on main thread."""
        table = self.query_one(DataTable)
        
        systemd_data = data.get('systemd', {})
        services = systemd_data.get('services', [])
        
        # Sort logic
        def sort_key(s):
            state = s.get('state', '').lower()
            active = s.get('active', '').lower()
            if state == 'running': priority = 0
            elif state == 'failed' or active == 'failed': priority = 1
            elif active == 'active': priority = 2
            else: priority = 3
            return (priority, s.get('name', '').lower())

        services.sort(key=sort_key)
        
        def populate(t):
            for service in services[:500]:
                name = service.get('name', 'N/A')
                user = service.get('user', '')
                state = service.get('state', service.get('active', 'unknown'))
                sub_state = service.get('sub_state', service.get('sub', '-'))
                description = service.get('description', '')

                if state == 'running' or state == 'active':
                    state_styled = Text(state, style="green")
                elif state == 'exited' or state == 'failed':
                    state_styled = Text(state, style="red")
                elif state == 'dead':
                    state_styled = Text(state, style="yellow")
                elif state == 'inactive':
                    state_styled = Text(state, style="dim")
                else:
                    state_styled = Text(state, style="white")

                t.add_row(name, user, state_styled, sub_state, description)

        update_table_preserving_scroll(table, populate)
        
        # Update Header
        total = systemd_data.get('total', 0)
        active = systemd_data.get('active', 0)
        running = systemd_data.get('running', 0)
        failed = systemd_data.get('failed', 0)
        
        fail_color = "red" if failed > 0 else "green"
        
        header_text = (
            f"[bold cyan]Total Services: {total}[/bold cyan] | "
            f"[bold blue]Active: {active}[/bold blue] | "
            f"[bold green]Running: {running}[/bold green] | "
            f"[bold {fail_color}]Failed: {failed}[/bold {fail_color}]"
        )
        self.query_one("#svc_header", Label).update(header_text)
