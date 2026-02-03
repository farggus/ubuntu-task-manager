"""
F2B Database Manager Modal - Modal screen for AttacksDatabase management.

This modal provides access to the unified attacks database with
parsing controls, statistics, and data table view.
"""

import time
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label

from collectors.fail2ban_v2 import Fail2banV2Collector
from database.attacks_db import AttacksDatabase
from utils.logger import get_logger

logger = get_logger("f2b_db_modal")


class F2BDatabaseModal(ModalScreen):
    """
    Modal screen for managing the unified attacks database.

    Shows parsing controls, statistics, and IP data table.
    """

    BINDINGS = [
        Binding("escape", "close_modal", "Close"),
        Binding("t", "parse_logs", "Parse Logs"),
        Binding("f", "full_parse", "Full Parse"),
        Binding("s", "show_stats", "Stats"),
    ]

    CSS = """
    F2BDatabaseModal {
        align: center middle;
    }

    #f2b-modal-container {
        width: 90%;
        height: 85%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #f2b-modal-header {
        text-style: bold;
        color: $primary;
        padding: 1 0;
    }

    #f2b-modal-controls {
        height: 3;
        padding: 0 0 1 0;
    }

    #f2b-modal-controls Button {
        margin-right: 1;
    }

    #f2b-modal-status {
        height: 1;
        padding: 0 0 1 0;
        color: $text-muted;
    }

    #f2b-modal-table {
        height: 1fr;
    }
    """

    def __init__(self):
        """Initialize modal."""
        super().__init__()
        self._db: Optional[AttacksDatabase] = None
        self._collector: Optional[Fail2banV2Collector] = None

    def compose(self) -> ComposeResult:
        """Build the modal UI."""
        with Vertical(id="f2b-modal-container"):
            yield Label("🗄️ F2B Database Manager", id="f2b-modal-header")

            with Horizontal(id="f2b-modal-controls"):
                yield Button("▶ Parse Logs", id="btn-parse", variant="primary")
                yield Button("🔄 Full Parse", id="btn-full", variant="warning")
                yield Button("📊 Stats", id="btn-stats", variant="default")
                yield Button("💾 Save", id="btn-save", variant="success")
                yield Button("✕ Close", id="btn-close", variant="error")

            yield Label("Status: Ready", id="f2b-modal-status")
            yield DataTable(id="f2b-modal-table")

    def on_mount(self) -> None:
        """Initialize on mount."""
        self._db = AttacksDatabase()
        self._collector = Fail2banV2Collector(db=self._db)

        # Setup table
        table = self.query_one("#f2b-modal-table", DataTable)
        table.add_columns("IP", "Country", "Org", "Attempts", "Bans", "Status", "Danger")
        table.cursor_type = "row"
        table.zebra_stripes = True

        self._update_status("Database loaded. Ready.")
        self._refresh_table()

    @on(Button.Pressed, "#btn-parse")
    def on_parse_button(self) -> None:
        """Handle parse button."""
        self.action_parse_logs()

    @on(Button.Pressed, "#btn-full")
    def on_full_button(self) -> None:
        """Handle full parse button."""
        self.action_full_parse()

    @on(Button.Pressed, "#btn-stats")
    def on_stats_button(self) -> None:
        """Handle stats button."""
        self.action_show_stats()

    @on(Button.Pressed, "#btn-save")
    def on_save_button(self) -> None:
        """Handle save button."""
        self._save_db()

    @on(Button.Pressed, "#btn-close")
    def on_close_button(self) -> None:
        """Handle close button."""
        self.action_close_modal()

    def action_close_modal(self) -> None:
        """Close the modal."""
        self.dismiss()

    def action_parse_logs(self) -> None:
        """Run incremental log parsing."""
        self._update_status("🔄 Parsing logs...")
        self._do_parse()

    @work(thread=True)
    def _do_parse(self) -> None:
        """Background worker for parsing."""
        try:
            if not self._collector:
                self._db = AttacksDatabase()
                self._collector = Fail2banV2Collector(db=self._db)

            result = self._collector.collect()

            if result.get('success'):
                msg = (f"✅ Parsed: {result['bans_found']} bans, "
                       f"{result['attempts_found']} attempts, "
                       f"{result['new_ips']} new IPs ({result['parse_time']:.1f}s)")
            else:
                msg = f"❌ Failed: {result.get('error', 'Unknown')}"

            self.app.call_from_thread(self._update_status, msg)
            self.app.call_from_thread(self._refresh_table)

        except Exception as e:
            logger.error(f"Parse failed: {e}")
            self.app.call_from_thread(self._update_status, f"❌ Error: {e}")

    def action_full_parse(self) -> None:
        """Force full parse."""
        self._update_status("🔄 Full parse...")
        self._do_full_parse()

    @work(thread=True)
    def _do_full_parse(self) -> None:
        """Background worker for full parse."""
        t0 = time.time()
        try:
            if not self._collector:
                self._db = AttacksDatabase()
                self._collector = Fail2banV2Collector(db=self._db)

            stats = self._collector.parse_full(reset_positions=True)
            duration = time.time() - t0

            msg = (f"✅ Full: {stats['bans']} bans, "
                   f"{stats['attempts']} attempts, "
                   f"{stats['new_ips']} new IPs ({duration:.1f}s)")

            self.app.call_from_thread(self._update_status, msg)
            self.app.call_from_thread(self._refresh_table)

        except Exception as e:
            logger.error(f"Full parse failed: {e}")
            self.app.call_from_thread(self._update_status, f"❌ Error: {e}")

    def action_show_stats(self) -> None:
        """Show database stats."""
        if not self._db:
            self._update_status("❌ DB not loaded")
            return

        stats = self._db.get_stats()
        msg = (f"📊 {stats['total_ips']} IPs, "
               f"{stats['total_attempts']} attempts, "
               f"{stats['total_bans']} bans, "
               f"{stats['active_bans']} active")

        if stats.get('top_country'):
            msg += f" | Top: {stats['top_country']}"

        self._update_status(msg)

    def _save_db(self) -> None:
        """Save database."""
        if not self._db:
            self._update_status("❌ DB not loaded")
            return

        if self._db.save():
            self._update_status("💾 Saved")
        else:
            self._update_status("❌ Save failed")

    def _update_status(self, message: str) -> None:
        """Update status label."""
        try:
            label = self.query_one("#f2b-modal-status", Label)
            label.update(f"Status: {message}")
        except Exception:
            pass

    def _refresh_table(self) -> None:
        """Refresh the data table."""
        try:
            table = self.query_one("#f2b-modal-table", DataTable)
            table.clear()

            if not self._db:
                return

            threats = self._db.get_top_threats(limit=100)

            for item in threats:
                ip = item["ip"]
                geo = item.get("geo") or {}
                attempts = item.get("attempts") or {}
                bans = item.get("bans") or {}

                status = "🔒 BAN" if bans.get("active") else "⚪"
                danger = item.get("danger_score", 0)
                danger_str = f"{'🔴' if danger >= 70 else '🟡' if danger >= 40 else '🟢'} {danger}"

                table.add_row(
                    ip,
                    geo.get("country", "?")[:15],
                    geo.get("org", "?")[:25],
                    str(attempts.get("total", 0)),
                    str(bans.get("total", 0)),
                    status,
                    danger_str,
                    key=ip
                )
        except Exception as e:
            logger.error(f"Table refresh failed: {e}")
