"""Modal screen for displaying SMART report."""

import os
import subprocess

from rich.markup import escape
from textual import work
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import RichLog, Static

from utils.binaries import SMARTCTL, SUDO, WHICH
from utils.logger import get_logger

logger = get_logger("smart_modal")


class SmartModal(ModalScreen):
    """A modal screen to display SMART report for a disk."""

    CSS = """
    SmartModal {
        align: center middle;
    }
    #smart_modal_container {
        width: 90%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }
    #smart_report_view {
        height: 1fr;
        border: round $primary;
        margin-top: 1;
    }
    #modal_hint {
        text-align: center;
    }
    """

    def __init__(self, disk_device: str, name: str):
        super().__init__()
        self.disk_device = disk_device
        self.report_name = name

    def compose(self):
        with Vertical(id="smart_modal_container"):
            yield Static(f"SMART Report for [b]{self.report_name}[/b]")
            yield RichLog(id="smart_report_view", wrap=True, highlight=False, markup=False)  # No markup
            yield Static("[dim]Press Esc to close[/dim]", id="modal_hint")

    def on_mount(self) -> None:
        """Fetch SMART report when the modal is mounted."""
        self.query_one(RichLog).write(f"""[dim]Fetching SMART report for {self.disk_device}...
This may take a moment.[/dim]""")
        self.fetch_smart_report()

    @work(thread=True, exclusive=True)
    def fetch_smart_report(self) -> None:
        """Fetch SMART report in a background thread."""
        log_view = self.query_one(RichLog)

        # Check if smartctl is installed
        if subprocess.run([WHICH, "smartctl"], capture_output=True).returncode != 0:
            self.app.call_from_thread(
                log_view.write,
                "[bold red]Error: `smartctl` command not found. Please install `smartmontools`.[/bold red]",
            )
            return

        # Try different device types for USB devices
        device_types = [None, "sat", "usbsunplus", "usbjmicron", "usbcypress"]

        for dev_type in device_types:
            result = self._try_smartctl(dev_type)
            if result and result.stdout and "specify device type" not in result.stdout.lower():
                # Success - got valid output
                self.app.call_from_thread(log_view.clear)
                self.app.call_from_thread(log_view.write, escape(result.stdout))
                if result.stderr:
                    self.app.call_from_thread(log_view.write, f"\n[dim]{escape(result.stderr)}[/dim]")
                return

        # All device types failed
        self.app.call_from_thread(log_view.clear)
        self.app.call_from_thread(
            log_view.write, f"[bold red]Could not read SMART data for {self.disk_device}[/bold red]\n"
        )
        self.app.call_from_thread(
            log_view.write,
            "[dim]This may be a USB device that doesn't support SMART passthrough, or the disk doesn't support SMART.[/dim]",
        )

    def _try_smartctl(self, device_type: str = None) -> subprocess.CompletedProcess:
        """Try to run smartctl with optional device type."""
        try:
            if os.geteuid() == 0:
                cmd = [SMARTCTL, "-a"]
            else:
                cmd = [SUDO, SMARTCTL, "-a"]

            if device_type:
                cmd.extend(["-d", device_type])

            cmd.append(self.disk_device)

            return subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            logger.warning(f"SMART query timed out for {self.disk_device}")
            return None
        except FileNotFoundError:
            logger.error("smartctl not found")
            return None
        except Exception as e:
            logger.error(f"Error running smartctl for {self.disk_device}: {e}")
            return None

    def on_key(self, event) -> None:
        """Dismiss on escape."""
        if event.key == "escape":
            self.dismiss()
