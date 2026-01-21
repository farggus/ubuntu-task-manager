"""Mount/Unmount modal for partitions."""

import subprocess
import os
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Label, Input
from rich.text import Text

from utils.logger import get_logger

logger = get_logger("mount_modal")


class MountModal(ModalScreen):
    """Modal screen for mounting/unmounting partitions."""

    DEFAULT_CSS = """
    MountModal {
        align: center middle;
    }
    #mount_container {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #mount_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #mount_info {
        margin-bottom: 1;
    }
    #mount_input_container {
        height: 3;
        margin-bottom: 1;
    }
    #mount_input_container Label {
        width: 15;
    }
    #mount_input_container Input {
        width: 1fr;
    }
    #mount_result {
        height: auto;
        margin-top: 1;
    }
    #mount_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    #mount_buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def __init__(self, device: str, mountpoint: str, action: str):
        super().__init__()
        self.device = device
        self.mountpoint = mountpoint
        self.action = action  # 'mount' or 'unmount'

    def compose(self) -> ComposeResult:
        title = "Unmount Partition" if self.action == 'unmount' else "Mount Partition"

        with Vertical(id="mount_container"):
            yield Label(title, id="mount_title")
            yield Static(id="mount_info")

            if self.action == 'mount':
                with Horizontal(id="mount_input_container"):
                    yield Label("Mountpoint:")
                    yield Input(placeholder="/mnt/mydisk", id="mountpoint_input")

            yield Static(id="mount_result")

            with Horizontal(id="mount_buttons"):
                if self.action == 'unmount':
                    yield Button("Unmount", id="action_btn", variant="error")
                else:
                    yield Button("Mount", id="action_btn", variant="success")
                yield Button("Cancel", id="cancel_btn", variant="default")

    def on_mount(self) -> None:
        """Display device info."""
        if self.action == 'unmount':
            info = Text()
            info.append("Device: ", style="cyan")
            info.append(f"{self.device}\n", style="white")
            info.append("Mountpoint: ", style="cyan")
            info.append(f"{self.mountpoint}\n", style="white")
            info.append("\nThis will unmount the partition.", style="yellow")
        else:
            info = Text()
            info.append("Device: ", style="cyan")
            info.append(f"{self.device}\n", style="white")
            info.append("\nEnter the mountpoint directory.", style="dim")

        self.query_one("#mount_info", Static).update(info)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "cancel_btn":
            self.dismiss()
        elif event.button.id == "action_btn":
            self._perform_action()

    def _perform_action(self) -> None:
        """Perform mount or unmount."""
        result_widget = self.query_one("#mount_result", Static)

        try:
            if self.action == 'unmount':
                # Unmount
                cmd = ['umount', self.mountpoint]
                if os.geteuid() != 0:
                    cmd = ['sudo'] + cmd

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    result_widget.update(Text("Successfully unmounted!", style="green bold"))
                    self.set_timer(1.5, self.dismiss)
                else:
                    error = result.stderr.strip() or "Unknown error"
                    result_widget.update(Text(f"Error: {error}", style="red"))

            else:
                # Mount
                mountpoint_input = self.query_one("#mountpoint_input", Input)
                mountpoint = mountpoint_input.value.strip()

                if not mountpoint:
                    result_widget.update(Text("Please enter a mountpoint.", style="yellow"))
                    return

                if not mountpoint.startswith('/'):
                    result_widget.update(Text("Mountpoint must be an absolute path.", style="yellow"))
                    return

                # Create mountpoint if it doesn't exist
                if not os.path.exists(mountpoint):
                    mkdir_cmd = ['mkdir', '-p', mountpoint]
                    if os.geteuid() != 0:
                        mkdir_cmd = ['sudo'] + mkdir_cmd
                    subprocess.run(mkdir_cmd, capture_output=True, timeout=10)

                # Mount
                cmd = ['mount', self.device, mountpoint]
                if os.geteuid() != 0:
                    cmd = ['sudo'] + cmd

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    result_widget.update(Text(f"Successfully mounted at {mountpoint}!", style="green bold"))
                    self.set_timer(1.5, self.dismiss)
                else:
                    error = result.stderr.strip() or "Unknown error"
                    result_widget.update(Text(f"Error: {error}", style="red"))

        except subprocess.TimeoutExpired:
            logger.warning(f"Mount/unmount operation timed out for {self.device}")
            result_widget.update(Text("Operation timed out.", style="red"))
        except Exception as e:
            logger.error(f"Mount/unmount error for {self.device}: {e}")
            result_widget.update(Text(f"Error: {e}", style="red"))

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()
