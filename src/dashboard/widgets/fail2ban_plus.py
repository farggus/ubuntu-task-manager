"""
Fail2ban+ tab widget - New implementation with unified attacks database.

The actual database management is in the F2BDatabaseModal.
"""

from datetime import datetime
from typing import Dict, Optional

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
            yield Input(placeholder="Search IP...", id="f2b_plus_search")
    
    def on_mount(self) -> None:
        """Load initial data."""
        self._db = AttacksDatabase()
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
        """Update header with database stats."""
        try:
            header = self.query_one("#f2b_plus_header", Label)
            
            if not self._db:
                header.update("[red]Database not loaded[/red]")
                return
            
            stats = self._db.get_stats()
            total_ips = stats.get('total_ips', 0)
            total_attempts = stats.get('total_attempts', 0)
            total_bans = stats.get('total_bans', 0)
            active_bans = stats.get('active_bans', 0)
            top_country = stats.get('top_country', 'N/A')
            
            # Line 1: Database status
            line1 = (
                f"[bold cyan]F2B+ Database:[/bold cyan] [green]Loaded[/green] │ "
                f"[white]{total_ips}[/white] IPs │ "
                f"[yellow]{total_attempts}[/yellow] attempts │ "
                f"[red]{total_bans}[/red] bans │ "
                f"[magenta]{active_bans}[/magenta] active"
            )
            
            # Line 2: Top country + update time
            update_time = ""
            if self._last_update:
                update_time = f"[dim]Updated: {self._last_update.strftime('%H:%M:%S')}[/dim]"
            else:
                update_time = "[dim]Loaded from disk[/dim]"
            
            line2 = f"[cyan]Top:[/cyan] {top_country} │ {update_time}"
            
            header.update(f"{line1}\n{line2}")
            
        except Exception as e:
            logger.error(f"Failed to update header: {e}")
