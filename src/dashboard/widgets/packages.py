"""Packages tab widget."""

import subprocess
from typing import Any, Dict

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static

from collectors import SystemCollector
from utils.binaries import APT_GET, SUDO
from utils.logger import get_logger
from utils.ui_helpers import update_table_preserving_scroll

logger = get_logger("packages_tab")


class PackagesTab(Vertical):
    """Tab displaying system packages and updates."""

    BINDINGS = [
        Binding("a", "toggle_all_packages", "Toggle All/Updates"),
        Binding("u", "update_package", "Update Selected"),
        Binding("U", "update_all", "Update All"),
    ]

    DEFAULT_CSS = """
    PackagesTab {
        height: 1fr;
        padding: 0;
    }
    #pkg_header_container {
        height: 3;
        margin: 0;
        padding: 0 1;
        border: round $success;
        margin-bottom: 0;
    }
    #pkg_header {
        margin: 0;
        padding: 0;
        width: 100%;
        text-align: left;
    }
    #pkg_table {
        height: 1fr;
        margin: 0;
        padding: 0;
    }
    .help-text {
        height: 1;
        margin-top: 0;
        padding: 0 1;
        color: $text-disabled;
    }
    """

    def __init__(self, collector: SystemCollector):
        super().__init__()
        self.collector = collector
        self.show_all = False
        self.filter_char = None
        self._data_loaded = False

    def compose(self):
        # Header with counts wrapped in a border
        with Static(id="pkg_header_container"):
            yield Label("Checking packages...", id="pkg_header")

        # Table
        yield DataTable(id="pkg_table", cursor_type="row", zebra_stripes=True)

        # Simple text hint at the bottom of the widget
        yield Label("[dim]Type a-z to jump[/dim]", classes="help-text")

    def on_mount(self) -> None:
        """Setup table structure (no data loading)."""
        table = self.query_one(DataTable)
        table.add_columns("Package", "Current Version", "New Version")

    def on_show(self) -> None:
        """Load data when tab becomes visible."""
        if not self._data_loaded:
            self._data_loaded = True
            self.update_data()

    def on_key(self, event) -> None:
        # Jump to letter logic
        if event.character and event.character.isalpha() and len(event.character) == 1:
            char = event.character.upper()

            # Ignore keys that are used for bindings
            if char in ['A', 'U']:
                return

            table = self.query_one(DataTable)
            for i in range(table.row_count):
                try:
                    row_val = table.get_row_at(i)[0]
                    pkg_name = str(row_val).strip()
                    if pkg_name.upper().startswith(char):
                        table.move_cursor(row=i, animate=False)
                        self.notify(f"Jump to '{char}'")
                        return
                except Exception as e:
                    logger.debug(f"Error reading row {i}: {e}")
                    continue

            self.notify(f"No package starting with '{char}'")

    def action_toggle_all_packages(self) -> None:
        """Toggle between showing all packages and only updates."""
        self.show_all = not self.show_all
        mode = "ALL packages" if self.show_all else "UPDATES only"
        self.notify(f"Showing {mode}")
        self.update_data()

    def update_package(self) -> None:
        """Update selected package (internal method)."""
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            self.notify("No package selected", severity="warning")
            return

        try:
            row = table.get_row_at(table.cursor_row)
            pkg_name_cell = row[0]
            pkg_name = str(pkg_name_cell).split()[0]

            self.notify(f"Updating {pkg_name}...", severity="information")
            self.run_update_command([SUDO, APT_GET, "install", "--only-upgrade", "-y", pkg_name])
        except Exception as e:
            logger.error(f"Error selecting package for update: {e}")
            self.notify("Error selecting package", severity="error")

    def action_update_package(self) -> None:
        self.update_package()

    def action_update_all(self) -> None:
        """Update all packages."""
        self.notify("Starting full system upgrade...", severity="warning")
        self.run_update_command([SUDO, APT_GET, "upgrade", "-y"])

    @work(thread=True)
    def run_update_command(self, cmd: list) -> None:
        """Run apt command in background."""
        try:
            logger.info(f"Running update command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                self.app.call_from_thread(self.notify, "Update completed successfully!", severity="information")
                self.collector._pkg_cache_time = 0
                self.update_data()
            else:
                err_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                logger.error(f"Update failed: {err_msg}")
                self.app.call_from_thread(self.notify, f"Update failed: {err_msg[:100]}...", severity="error")
        except Exception as e:
            logger.exception("Exception during update")
            self.app.call_from_thread(self.notify, f"Error: {e}", severity="error")

    @work(exclusive=True, thread=True)
    def update_data(self) -> None:
        data = self.collector.update()
        self.app.call_from_thread(self.update_table, data)

    def update_table(self, data: Dict[str, Any]) -> None:
        table = self.query_one(DataTable)
        pkg_stats = data.get('packages', {})

        if self.show_all:
            source_list = pkg_stats.get('all_packages', [])
        else:
            source_list = pkg_stats.get('upgradable_list', [])

        def populate(t):
            count_shown = 0
            if not source_list:
                if not self.show_all and pkg_stats.get('updates', 0) == 0:
                    t.add_row("System is up to date", "", "")
                else:
                    t.add_row("No packages found", "", "")
            else:
                for pkg in source_list[:2000]:
                    name = pkg.get('name', 'N/A')
                    curr = pkg.get('current_version', '?')
                    new = pkg.get('new_version', '-')

                    if pkg.get('upgradable', False) or (not self.show_all):
                        name_styled = Text(name, style="bold yellow")
                        new_styled = Text(new, style="bold green")
                    else:
                        name_styled = Text(name)
                        new_styled = Text(new, style="dim")

                    t.add_row(name_styled, curr, new_styled)
                    count_shown += 1

            total = pkg_stats.get('total', 0)
            updates = pkg_stats.get('updates', 0)

            # Middle section always shows Upgradable Packages info
            upd_color = "red" if updates > 0 else "green"

            header_text = (
                f"[bold cyan]Total installed: {total}[/bold cyan] | "
                f"[bold {upd_color}]Upgradable Packages: {updates}[/bold {upd_color}] | "
                f"[bold white]Showing: {count_shown}[/bold white]"
            )

            if self.filter_char:
                header_text += f" | [bold magenta]Filter: '{self.filter_char}'[/bold magenta]"

            self.query_one("#pkg_header", Label).update(header_text)

        update_table_preserving_scroll(table, populate)
