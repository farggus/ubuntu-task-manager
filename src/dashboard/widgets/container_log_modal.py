"""Modal screen for displaying Docker container logs."""

import threading

from rich.markup import escape
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import RichLog, Static

from utils.logger import get_logger

logger = get_logger("container_log_modal")

try:
    import docker
    from docker.errors import NotFound
except ImportError:
    docker = None
    NotFound = None


class ContainerLogModal(ModalScreen):
    """A modal screen to display Docker container logs."""

    CSS = """
    ContainerLogModal {
        align: center middle;
    }
    #log_modal_container {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }
    #container_log_view {
        height: 1fr;
        border: round $primary;
        margin-top: 1;
    }
    #modal_hint {
        text-align: center;
    }
    """

    def __init__(self, container_id: str, container_name: str):
        super().__init__()
        self.container_id = container_id
        self.container_name = container_name
        self._stop_event = threading.Event()
        self._log_thread: threading.Thread | None = None

    def compose(self):
        with Vertical(id="log_modal_container"):
            yield Static(f"Logs for [b]{self.container_name}[/b] ({self.container_id})")
            yield RichLog(id="container_log_view", wrap=True, highlight=True, markup=True)
            yield Static("[dim]Press Esc to close[/dim]", id="modal_hint")

    def on_mount(self) -> None:
        """Start a daemon thread to stream logs."""
        if not docker:
            self.query_one(RichLog).write("[bold red]Docker SDK not installed.[/bold red]")
            return

        self._log_thread = threading.Thread(target=self.stream_logs_thread, daemon=True)  # This is the crucial part
        self._log_thread.start()

    def stream_logs_thread(self) -> None:
        """The actual method that runs in a thread to stream logs."""
        log_view = self.query_one(RichLog)
        try:
            client = docker.from_env()
            container = client.containers.get(self.container_id)

            # Initial logs
            log_content = container.logs(tail=200).decode("utf-8", errors="ignore")
            initial_logs_list = log_content.strip().splitlines()[-50:]

            def write_initial():
                log_view.clear()
                for line in initial_logs_list:
                    log_view.write(escape(line))

            self.app.call_from_thread(write_initial)

            # Stream new logs
            log_stream = container.logs(stream=True, follow=True)
            for line in log_stream:
                if self._stop_event.is_set():
                    break
                decoded_line = line.decode("utf-8", errors="ignore").strip()
                self.app.call_from_thread(log_view.write, escape(decoded_line))

        except NotFound:
            logger.warning(f"Container {self.container_id} not found")
            self.app.call_from_thread(
                log_view.write, f"[bold red]Error: Container {self.container_id} not found.[/bold red]"
            )
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"Error streaming logs for container {self.container_id}: {e}")
                self.app.call_from_thread(log_view.write, f"[bold red]Error: {escape(str(e))}[/bold red]")

    def on_key(self, event) -> None:
        """Handle key presses."""
        if event.key == "escape":
            self._stop_event.set()  # Signal the thread to stop
            self.dismiss()
