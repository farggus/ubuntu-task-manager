"""Containers tab widget."""

from textual import work
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static
from textual.binding import Binding
from rich.text import Text
from typing import Dict, Any, List

# We need docker library for control, not just collection
try:
    import docker
except ImportError:
    docker = None

from collectors import ServicesCollector
from utils.logger import get_logger
from utils.ui_helpers import update_table_preserving_scroll
from .container_log_modal import ContainerLogModal

logger = get_logger("containers_tab")


class ContainersTab(Vertical):
    """Tab displaying Docker containers."""

    BINDINGS = [
        Binding("a", "view_all", "All"),
        Binding("r", "view_running", "Running"),
        Binding("s", "view_stopped", "Stopped"),
        Binding("x", "start_container", "Start"),
        Binding("k", "stop_container", "Stop"),
        Binding("R", "restart_container", "Restart"),
        Binding("l", "view_log", "Log"),
    ]

    DEFAULT_CSS = """
    ContainersTab {
        height: 1fr;
        padding: 0;
    }
    #container_header_container {
        height: 3;
        margin: 0;
        padding: 0 1;
        border: round $success;
        margin-bottom: 0;
    }
    #container_header {
        margin: 0;
        padding: 0;
        width: 100%;
        text-align: left;
    }
    #containers_table {
        height: 1fr;
        margin: 0;
        padding: 0;
    }
    """

    def __init__(self, collector: ServicesCollector):
        super().__init__()
        self.collector = collector
        self.view_mode = 'all'  # 'all', 'running', 'stopped'

    def compose(self):
        with Static(id="container_header_container"):
            yield Label("Loading containers...", id="container_header")
        yield DataTable(id="containers_table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("ID", "Name", "Stack", "Image", "Status", "IP Address", "Ports")
        self.update_data()
        self.set_interval(15, self.update_data)

    def action_view_all(self):
        self._set_view_mode('all', "Showing all containers")

    def action_view_running(self):
        self._set_view_mode('running', "Showing running containers")

    def action_view_stopped(self):
        self._set_view_mode('stopped', "Showing stopped containers")

    def _set_view_mode(self, mode: str, message: str):
        if self.view_mode != mode:
            self.view_mode = mode
            self.notify(message)
            self.update_data()

    def action_start_container(self):
        self._manage_container("start")
    
    def action_stop_container(self):
        self._manage_container("stop")

    def action_restart_container(self):
        self._manage_container("restart")

    def action_view_log(self):
        """Show logs for the selected container in a modal."""
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            self.notify("No container selected.", severity="warning")
            return
        
        try:
            row = table.get_row_at(table.cursor_row)
            container_id = str(row[0])
            container_name = str(row[1])
            self.app.push_screen(ContainerLogModal(container_id=container_id, container_name=container_name))
        except Exception as e:
            logger.error(f"Error getting container info: {e}")
            self.notify(f"Error getting container info: {e}", severity="error")

    def _manage_container(self, action: str):
        if not docker:
            self.notify("Docker library not installed.", severity="error")
            return
            
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            self.notify("No container selected.", severity="warning")
            return
        
        try:
            row = table.get_row_at(table.cursor_row)
            container_id = str(row[0])
            self.notify(f"Requesting '{action}' for {container_id}...", severity="information")
            self.run_docker_command(container_id, action)
        except Exception as e:
            logger.error(f"Error selecting container for {action}: {e}")
            self.notify(f"Error selecting container: {e}", severity="error")

    @work(thread=True)
    def run_docker_command(self, container_id: str, action: str):
        try:
            client = docker.from_env()
            container = client.containers.get(container_id)
            
            if action == 'start':
                container.start()
            elif action == 'stop':
                container.stop()
            elif action == 'restart':
                container.restart()
            
            msg = f"Container {container_id} {action}ed successfully."
            logger.info(msg)
            self.app.call_from_thread(self.notify, msg, severity="information")
            self.update_data()
        except docker.errors.DockerException as e:
            err_msg = f"Docker error: {e}"
            logger.error(err_msg)
            self.app.call_from_thread(self.notify, err_msg, severity="error")
        except Exception as e:
            err_msg = f"An unexpected error occurred: {e}"
            logger.exception(err_msg)
            self.app.call_from_thread(self.notify, err_msg, severity="error")

    @work(exclusive=True, thread=True)
    def update_data(self) -> None:
        data = self.collector.update()
        if data.get('error'):
            self.notify(f"Collector Error: {data['error']}", severity="error")
        self.app.call_from_thread(self.update_table, data.get('docker', {}))

    def update_table(self, data: Dict[str, Any]) -> None:
        table = self.query_one(DataTable)
        
        containers = data.get('containers', [])
        
        def populate(t):
            # Filter
            filtered_list: List[Dict[str, Any]] = []
            if self.view_mode == 'running':
                filtered_list = [c for c in containers if 'running' in c.get('status', '').lower()]
            elif self.view_mode == 'stopped':
                filtered_list = [c for c in containers if 'running' not in c.get('status', '').lower()]
            else:
                filtered_list = containers

            # Sort
            filtered_list.sort(key=lambda c: (c.get('stack', ''), c.get('name', '')))

            # Populate
            for container in filtered_list:
                cid = container.get('id', '')
                name = container.get('name', '')
                stack = container.get('stack', '')
                image = container.get('image', '')
                status = container.get('status', '')
                ip_address = container.get('ip_address', 'N/A')
                
                ports_dict = container.get('ports', {})
                ports_list = []
                if ports_dict:
                    for internal, host_list in ports_dict.items():
                        if host_list:
                            for host_spec in host_list:
                                ports_list.append(f"{host_spec['HostIp']}:{host_spec['HostPort']}->{internal}")
                ports_str = ", ".join(ports_list)
                
                style = "green" if "running" in status.lower() else "red" if "exited" in status.lower() else "yellow"
                t.add_row(cid, name, stack, image, Text(status, style=style), ip_address, ports_str)

        update_table_preserving_scroll(table, populate)
        
        # Update Header
        total = data.get('total', 0)
        running = data.get('running', 0)
        stopped = data.get('stopped', 0)
        
        stopped_color = "red" if stopped > 0 else "green"
        header_text = (
            f"[bold cyan]Total: {total}[/bold cyan] | "
            f"[bold green]Running: {running}[/bold green] | "
            f"[bold {stopped_color}]Stopped: {stopped}[/bold {stopped_color}]"
        )
        self.query_one("#container_header", Label).update(header_text)
