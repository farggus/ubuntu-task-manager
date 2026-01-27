"""
Fail2ban+ tab widget - New implementation with unified attacks database.

This is the testing version for the new AttacksDatabase-based approach.
"""

import time
from pathlib import Path
from typing import Dict, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Label, Static

from collectors.fail2ban_v2 import Fail2banV2Collector
from database.attacks_db import AttacksDatabase
from utils.logger import get_logger

logger = get_logger("fail2ban_plus")

# Cache directory for migration
CACHE_DIR = Path(__file__).parent.parent.parent.parent / "cache"


class Fail2banPlusTab(Vertical):
    """
    Fail2Ban+ tab - testing ground for new unified database approach.
    
    Features:
    - Single "Test Collection" button
    - Status display showing last operation result
    - Eventually: full replacement for old Fail2ban tab
    """
    
    BINDINGS = [
        Binding("t", "test_collection", "Test Collection"),
        Binding("m", "migrate_data", "Migrate Data"),
        Binding("s", "show_stats", "Show Stats"),
    ]
    
    def __init__(self):
        """Initialize Fail2Ban+ tab."""
        super().__init__()
        self._db: Optional[AttacksDatabase] = None
        self._collector: Optional[Fail2banV2Collector] = None
        self._last_result: str = "Not run yet"
    
    def compose(self) -> ComposeResult:
        """Build the UI."""
        yield Label("🛡️ Fail2Ban+ (v2 Testing)", id="f2b-plus-header", classes="header")
        
        with Horizontal(id="f2b-plus-controls"):
            yield Button("▶ Parse Logs", id="btn-test", variant="primary")
            yield Button("🔄 Full Parse", id="btn-full", variant="warning")
            yield Button("📊 Show Stats", id="btn-stats", variant="default")
            yield Button("💾 Save DB", id="btn-save", variant="success")
        
        yield Label("Status: Ready", id="f2b-plus-status", classes="status-label")
        
        yield DataTable(id="f2b-plus-table")
    
    def on_mount(self) -> None:
        """Initialize on mount."""
        # Initialize database and collector
        self._db = AttacksDatabase()
        self._collector = Fail2banV2Collector(db=self._db)
        
        # Setup table
        table = self.query_one("#f2b-plus-table", DataTable)
        table.add_columns("IP", "Country", "Org", "Attempts", "Bans", "Status", "Danger")
        table.cursor_type = "row"
        table.zebra_stripes = True
        
        self._update_status("Database loaded. Ready for log parsing.")
        self._refresh_table()
    
    @on(Button.Pressed, "#btn-test")
    def on_test_button(self) -> None:
        """Handle test button click."""
        self.action_test_collection()
    
    @on(Button.Pressed, "#btn-full")
    def on_full_parse_button(self) -> None:
        """Handle full parse button click."""
        self.action_full_parse()
    
    @on(Button.Pressed, "#btn-stats")
    def on_stats_button(self) -> None:
        """Handle stats button click."""
        self.action_show_stats()
    
    @on(Button.Pressed, "#btn-save")
    def on_save_button(self) -> None:
        """Handle save button click."""
        self.action_save_db()
    
    def action_test_collection(self) -> None:
        """Run incremental log parsing."""
        self._update_status("🔄 Parsing fail2ban logs...")
        self._do_parse_logs()
    
    @work(thread=True)
    def _do_parse_logs(self) -> None:
        """Background worker for log parsing."""
        try:
            if not self._collector:
                self._db = AttacksDatabase()
                self._collector = Fail2banV2Collector(db=self._db)
            
            # Run collection (incremental parse)
            result = self._collector.collect()
            
            if result.get('success'):
                msg = (f"✅ Parsed in {result['parse_time']:.2f}s: "
                       f"{result['bans_found']} bans, "
                       f"{result['unbans_found']} unbans, "
                       f"{result['attempts_found']} attempts, "
                       f"{result['new_ips']} new IPs")
            else:
                msg = f"❌ Parse failed: {result.get('error', 'Unknown error')}"
            
            self.app.call_from_thread(self._update_status, msg)
            self.app.call_from_thread(self._refresh_table)
            
            logger.info(msg)
            
        except Exception as e:
            logger.error(f"Log parsing failed: {e}")
            self.app.call_from_thread(
                self._update_status,
                f"❌ Error: {str(e)}"
            )
    
    def action_full_parse(self) -> None:
        """Force full parse of all logs (reset positions)."""
        self._update_status("🔄 Full parse - resetting positions...")
        self._do_full_parse()
    
    @work(thread=True)
    def _do_full_parse(self) -> None:
        """Background worker for full parse."""
        t0 = time.time()
        
        try:
            if not self._collector:
                self._db = AttacksDatabase()
                self._collector = Fail2banV2Collector(db=self._db)
            
            # Force full parse
            stats = self._collector.parse_full(reset_positions=True)
            duration = time.time() - t0
            
            msg = (f"✅ Full parse in {duration:.2f}s: "
                   f"{stats['bans']} bans, "
                   f"{stats['unbans']} unbans, "
                   f"{stats['attempts']} attempts, "
                   f"{stats['new_ips']} new IPs")
            
            self.app.call_from_thread(self._update_status, msg)
            self.app.call_from_thread(self._refresh_table)
            
            logger.info(msg)
            
        except Exception as e:
            logger.error(f"Full parse failed: {e}")
            self.app.call_from_thread(
                self._update_status,
                f"❌ Error: {str(e)}"
            )
    

    
    def action_show_stats(self) -> None:
        """Show database statistics."""
        if not self._db:
            self._update_status("❌ Database not loaded")
            return
        
        stats = self._db.get_stats()
        msg = (f"📊 Stats: {stats['total_ips']} IPs, "
               f"{stats['total_attempts']} attempts, "
               f"{stats['total_bans']} bans, "
               f"{stats['active_bans']} active")
        
        if stats.get('top_country'):
            msg += f" | Top: {stats['top_country']}"
        
        self._update_status(msg)
    
    def action_save_db(self) -> None:
        """Save database to disk."""
        if not self._db:
            self._update_status("❌ Database not loaded")
            return
        
        if self._db.save():
            self._update_status("💾 Database saved successfully")
        else:
            self._update_status("❌ Failed to save database")
    
    def _update_status(self, message: str) -> None:
        """Update status label."""
        try:
            label = self.query_one("#f2b-plus-status", Label)
            label.update(f"Status: {message}")
        except Exception:
            pass  # Widget may not exist yet
    
    def _refresh_table(self) -> None:
        """Refresh the data table with current database contents."""
        try:
            table = self.query_one("#f2b-plus-table", DataTable)
            table.clear()
            
            if not self._db:
                return
            
            # Get top threats for display
            threats = self._db.get_top_threats(limit=100)
            
            for item in threats:
                ip = item["ip"]
                geo = item.get("geo", {})
                attempts = item.get("attempts", {})
                bans = item.get("bans", {})
                
                status = "🔒 BANNED" if bans.get("active") else "⚪ Free"
                danger = item.get("danger_score", 0)
                danger_str = f"{'🔴' if danger >= 70 else '🟡' if danger >= 40 else '🟢'} {danger}"
                
                table.add_row(
                    ip,
                    geo.get("country", "Unknown"),
                    geo.get("org", "Unknown")[:30],
                    str(attempts.get("total", 0)),
                    str(bans.get("total", 0)),
                    status,
                    danger_str,
                    key=ip
                )
        except Exception as e:
            logger.error(f"Failed to refresh table: {e}")
