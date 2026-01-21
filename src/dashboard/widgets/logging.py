"""Logging tab widget."""

from textual import work
from textual.containers import Vertical
from textual.widgets import RichLog, Label
from const import LOG_FILE
import os

class LoggingTab(Vertical):
    """Tab displaying application logs."""

    def __init__(self):
        super().__init__()
        self.last_size = 0

    def compose(self):
        yield RichLog(id="log_view", highlight=True, markup=True)
        yield Label(f"[dim]Viewing {LOG_FILE}[/dim]", classes="help-text")

    def on_mount(self) -> None:
        """Initialize log view and start updates."""
        self.update_logs()
        self.set_interval(2, self.update_logs)

    @work(exclusive=True, thread=True)
    def update_logs(self) -> None:
        """Read new lines from log file."""
        if not os.path.exists(LOG_FILE):
            return

        try:
            current_size = os.path.getsize(LOG_FILE)
            if current_size < self.last_size:
                # Log file was truncated/rotated
                self.last_size = 0
                self.app.call_from_thread(self.query_one("#log_view", RichLog).clear)

            if current_size > self.last_size:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    f.seek(self.last_size)
                    new_lines = f.readlines()
                    self.last_size = current_size
                    
                    if new_lines:
                        for line in new_lines:
                            # Clean up line and send to widget
                            clean_line = line.strip()
                            if clean_line:
                                self.app.call_from_thread(self.query_one("#log_view", RichLog).write, clean_line)
        except Exception as e:
            # Don't use logger here to avoid recursion if logging fails
            pass
