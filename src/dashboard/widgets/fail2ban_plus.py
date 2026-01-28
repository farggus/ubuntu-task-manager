"""
Fail2ban+ tab widget - New implementation with unified attacks database.

The actual database management is in the F2BDatabaseModal.
"""

from datetime import datetime
from typing import Dict, Optional, Set

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Label

from database.attacks_db import AttacksDatabase
from utils.logger import get_logger

logger = get_logger("fail2ban_plus")


class Fail2banPlusTab(Vertical, can_focus=True):
    """
    Fail2Ban+ tab with unified attacks database.
    """
    
    BINDINGS = [
        Binding("d", "open_db_modal", "F2B-db", show=True),
        Binding("R", "update_data_manual", "Refresh"),
    ]
    
    DEFAULT_CSS = """
    Fail2banPlusTab {
        height: 1fr;
        padding: 0;
    }
    #f2b_plus_header_container {
        height: 4;
        margin: 0;
        padding: 0 1;
        border: round $success;
        margin-bottom: 0;
    }
    #f2b_plus_header {
        margin: 0;
        padding: 0;
        width: auto;
    }
    #f2b_plus_search {
        width: 1fr;
        margin-left: 2;
        border: none;
        background: transparent;
        color: $text;
    }
    """
    
    def __init__(self):
        super().__init__()
        self._db: Optional[AttacksDatabase] = None
        self._last_update: Optional[datetime] = None
    
    def compose(self) -> ComposeResult:
        """Build the UI."""
        with Horizontal(id="f2b_plus_header_container"):
            yield Label("[bold cyan]Loading database...[/bold cyan]", id="f2b_plus_header")
            yield Input(placeholder="Search IP/jail...", id="f2b_plus_search")
    
    def on_mount(self) -> None:
        """Load initial data."""
        self._db = AttacksDatabase()
        self._last_update = datetime.now()
        self._update_header()
    
    def action_open_db_modal(self) -> None:
        """Open the F2B Database Manager modal."""
        from dashboard.widgets.f2b_db_manage_modal import F2BDatabaseModal
        self.app.push_screen(F2BDatabaseModal())
    
    def action_update_data_manual(self) -> None:
        """Manual refresh action."""
        header = self.query_one("#f2b_plus_header", Label)
        header.update("[bold yellow]⟳ Refreshing...[/bold yellow]")
        self._refresh_db()
    
    @work(thread=True)
    def _refresh_db(self) -> None:
        """Reload database in background."""
        try:
            self._db = AttacksDatabase()
            self._last_update = datetime.now()
            self.app.call_from_thread(self._update_header)
        except Exception as e:
            logger.error(f"Failed to refresh database: {e}")
    
    def _update_header(self) -> None:
        """Update header with database stats (same format as Fail2ban tab)."""
        try:
            header = self.query_one("#f2b_plus_header", Label)
            
            if not self._db:
                header.update("[red]Database not loaded[/red]")
                return
            
            stats = self._db.get_stats()
            all_ips = self._db.get_all_ips()
            
            # Count unique jails from all IPs
            all_jails: Set[str] = set()
            jails_with_bans: Set[str] = set()
            
            total_banned = 0
            unbanned_count = 0
            threats_count = 0
            
            for ip, data in all_ips.items():
                # Collect jails
                by_jail = data.get('attempts', {}).get('by_jail', {})
                all_jails.update(by_jail.keys())
                
                # Count active bans per jail
                if data.get('bans', {}).get('active'):
                    total_banned += 1
                    current_jail = data.get('bans', {}).get('current_jail')
                    if current_jail:
                        jails_with_bans.add(current_jail)
                
                # Count unbanned (total bans - active)
                unbanned_count += data.get('unbans', {}).get('total', 0)
                
                # Count threats (danger_score >= 50)
                if data.get('danger_score', 0) >= 50:
                    threats_count += 1
            
            jails_count = len(all_jails) if all_jails else 0
            active_jails = len(jails_with_bans)
            
            # Line 1: Fail2ban: Running │ X jails │ Y banned │ Z unbanned │ W threats
            line1 = (
                f"[bold cyan]Fail2ban:[/bold cyan] [green]Running[/green] │ "
                f"[white]{jails_count}[/white] jails │ "
                f"[red]{total_banned}[/red] banned │ "
                f"[blue]{unbanned_count}[/blue] unbanned │ "
                f"[yellow]{threats_count}[/yellow] threats"
            )
            
            # Line 2: Active: X/Y jails with bans │ Updated: HH:MM:SS
            update_time = ""
            if self._last_update:
                update_time = f"[dim]Updated: {self._last_update.strftime('%H:%M:%S')}[/dim]"
            
            line2 = f"[cyan]Active:[/cyan] {active_jails}/{jails_count} jails with bans"
            if update_time:
                line2 = f"{line2} │ {update_time}"
            
            header.update(f"{line1}\n{line2}")
            
        except Exception as e:
            logger.error(f"Failed to update header: {e}")
