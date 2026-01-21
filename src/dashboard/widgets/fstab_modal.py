"""Modal for editing /etc/fstab."""

from textual.screen import ModalScreen
from textual.widgets import TextArea, Static, Button
from textual.containers import Vertical, Horizontal
from textual.binding import Binding
from textual import work
import subprocess
import os
import tempfile

from utils.logger import get_logger

logger = get_logger("fstab_modal")


class FstabModal(ModalScreen):
    """Modal screen to edit /etc/fstab."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]

    CSS = """
    FstabModal {
        align: center middle;
    }
    #fstab_modal_container {
        width: 95%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }
    #fstab_header {
        height: 1;
        margin-bottom: 1;
    }
    #fstab_editor {
        height: 1fr;
        border: round $primary;
    }
    #fstab_footer {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    #fstab_footer Button {
        margin: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        self._original_content = ""

    def compose(self):
        with Vertical(id="fstab_modal_container"):
            yield Static("[bold]Edit /etc/fstab[/bold] [dim](Ctrl+S - Save, Esc - Cancel)[/dim]", id="fstab_header")
            yield TextArea(id="fstab_editor", language="bash", show_line_numbers=True)
            with Horizontal(id="fstab_footer"):
                yield Button("Save", variant="success", id="btn_save")
                yield Button("Cancel", variant="error", id="btn_cancel")

    def on_mount(self) -> None:
        """Load fstab content."""
        self.load_fstab()

    @work(thread=True)
    def load_fstab(self) -> None:
        """Load /etc/fstab content."""
        try:
            with open("/etc/fstab", "r") as f:
                content = f.read()
            self._original_content = content
            self.app.call_from_thread(self._set_content, content)
        except PermissionError:
            logger.warning("Permission denied reading /etc/fstab")
            self.app.call_from_thread(self._set_content, "# Error: Permission denied reading /etc/fstab\n# Run dashboard with sudo")
        except Exception as e:
            logger.error(f"Error loading /etc/fstab: {e}")
            self.app.call_from_thread(self._set_content, f"# Error loading /etc/fstab: {e}")

    def _set_content(self, content: str) -> None:
        """Set editor content on main thread."""
        editor = self.query_one("#fstab_editor", TextArea)
        editor.load_text(content)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn_save":
            self.action_save()
        elif event.button.id == "btn_cancel":
            self.action_cancel()

    def action_cancel(self) -> None:
        """Close without saving."""
        self.dismiss()

    def action_save(self) -> None:
        """Save fstab changes."""
        editor = self.query_one("#fstab_editor", TextArea)
        new_content = editor.text

        if new_content == self._original_content:
            self.notify("No changes to save", severity="information")
            self.dismiss()
            return

        self.save_fstab(new_content)

    @work(thread=True)
    def save_fstab(self, content: str) -> None:
        """Save content to /etc/fstab."""
        try:
            # Create backup first
            backup_path = "/etc/fstab.bak"

            if os.geteuid() == 0:
                # Running as root - direct write
                # Backup
                with open("/etc/fstab", "r") as f:
                    backup_content = f.read()
                with open(backup_path, "w") as f:
                    f.write(backup_content)

                # Write new content
                with open("/etc/fstab", "w") as f:
                    f.write(content)

                self.app.call_from_thread(self.notify, f"Saved! Backup at {backup_path}", severity="information")
                self.app.call_from_thread(self.dismiss)
            else:
                # Need sudo - use temp file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.fstab', delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name

                try:
                    # Backup original
                    result = subprocess.run(
                        ['sudo', 'cp', '/etc/fstab', backup_path],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode != 0:
                        raise Exception(f"Backup failed: {result.stderr}")

                    # Copy new content
                    result = subprocess.run(
                        ['sudo', 'cp', tmp_path, '/etc/fstab'],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode != 0:
                        raise Exception(f"Save failed: {result.stderr}")

                    self.app.call_from_thread(self.notify, f"Saved! Backup at {backup_path}", severity="information")
                    self.app.call_from_thread(self.dismiss)
                finally:
                    os.unlink(tmp_path)

        except Exception as e:
            logger.error(f"Error saving /etc/fstab: {e}")
            self.app.call_from_thread(self.notify, f"Error saving: {e}", severity="error")

    def validate_fstab(self, content: str) -> bool:
        """Basic validation of fstab content."""
        lines = content.strip().split('\n')
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 4:
                self.notify(f"Line {i}: Invalid format (need at least 4 fields)", severity="warning")
                return False
        return True
