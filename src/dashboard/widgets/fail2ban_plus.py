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
        self._last_result: str = "Not run yet"
    
    def compose(self) -> ComposeResult:
        """Build the UI."""
        yield Label("🛡️ Fail2Ban+ (v2 Testing)", id="f2b-plus-header", classes="header")
        
        with Horizontal(id="f2b-plus-controls"):
            yield Button("▶ Test Collection", id="btn-test", variant="primary")
            yield Button("📥 Migrate from Cache", id="btn-migrate", variant="default")
            yield Button("📊 Show Stats", id="btn-stats", variant="default")
            yield Button("💾 Save DB", id="btn-save", variant="success")
        
        yield Label("Status: Ready", id="f2b-plus-status", classes="status-label")
        
        yield DataTable(id="f2b-plus-table")
    
    def on_mount(self) -> None:
        """Initialize on mount."""
        # Initialize database
        self._db = AttacksDatabase()
        
        # Setup table
        table = self.query_one("#f2b-plus-table", DataTable)
        table.add_columns("IP", "Country", "Org", "Attempts", "Bans", "Status", "Danger")
        table.cursor_type = "row"
        table.zebra_stripes = True
        
        self._update_status("Database loaded. Ready for testing.")
        self._refresh_table()
    
    @on(Button.Pressed, "#btn-test")
    def on_test_button(self) -> None:
        """Handle test button click."""
        self.action_test_collection()
    
    @on(Button.Pressed, "#btn-migrate")
    def on_migrate_button(self) -> None:
        """Handle migrate button click."""
        self.action_migrate_data()
    
    @on(Button.Pressed, "#btn-stats")
    def on_stats_button(self) -> None:
        """Handle stats button click."""
        self.action_show_stats()
    
    @on(Button.Pressed, "#btn-save")
    def on_save_button(self) -> None:
        """Handle save button click."""
        self.action_save_db()
    
    def action_test_collection(self) -> None:
        """Test data collection into new database."""
        self._update_status("🔄 Running test collection...")
        self._do_test_collection()
    
    @work(thread=True)
    def _do_test_collection(self) -> None:
        """Background worker for test collection."""
        t0 = time.time()
        
        try:
            if not self._db:
                self._db = AttacksDatabase()
            
            # Simulate collecting some test data
            # In real implementation, this would parse fail2ban logs
            test_ips = [
                ("192.168.1.100", "Test Country", "Test Org", 10),
                ("10.0.0.1", "Another Country", "Another Org", 5),
            ]
            
            for ip, country, org, attempts in test_ips:
                for _ in range(attempts):
                    self._db.record_attempt(ip, "sshd")
                self._db.set_geo(ip, country, org)
            
            # Recalculate
            self._db.recalculate_stats()
            self._db.recalculate_danger_scores()
            
            duration = time.time() - t0
            
            # Update UI on main thread
            self.app.call_from_thread(
                self._update_status,
                f"✅ Test collection completed in {duration:.2f}s. Added {len(test_ips)} test IPs."
            )
            self.app.call_from_thread(self._refresh_table)
            
            logger.info(f"Test collection completed in {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Test collection failed: {e}")
            self.app.call_from_thread(
                self._update_status,
                f"❌ Error: {str(e)}"
            )
    
    def action_migrate_data(self) -> None:
        """Migrate data from old cache files."""
        self._update_status("🔄 Migrating from cache files...")
        self._do_migrate()
    
    @work(thread=True)
    def _do_migrate(self) -> None:
        """Background worker for migration."""
        t0 = time.time()
        
        try:
            if not self._db:
                self._db = AttacksDatabase()
            
            if not CACHE_DIR.exists():
                self.app.call_from_thread(
                    self._update_status,
                    f"❌ Cache directory not found: {CACHE_DIR}"
                )
                return
            
            stats = self._db.migrate_from_cache(CACHE_DIR)
            self._db.save()
            
            duration = time.time() - t0
            
            msg = (f"✅ Migration completed in {duration:.2f}s. "
                   f"IPs: {stats['ips_migrated']}, "
                   f"Geo: {stats['geo_migrated']}, "
                   f"Whitelist: {stats['whitelist_migrated']}")
            
            self.app.call_from_thread(self._update_status, msg)
            self.app.call_from_thread(self._refresh_table)
            
            logger.info(msg)
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.app.call_from_thread(
                self._update_status,
                f"❌ Migration error: {str(e)}"
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
