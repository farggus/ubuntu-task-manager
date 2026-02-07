"""
Fail2ban+ tab widget - New implementation with unified attacks database.

Uses hybrid data sources:
- Fail2banClient: real-time jail status, active bans
- AttacksDatabase: historical analytics, threats, unbanned IPs
"""

from datetime import datetime
from typing import Optional

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Label

from collectors.fail2ban_client import Fail2banClient
from database.attacks_db import AttacksDatabase
from utils.logger import get_logger

logger = get_logger("fail2ban_plus")


class Fail2banPlusTab(Vertical, can_focus=True):
    """
    Fail2Ban+ tab with unified attacks database.

    Hybrid data sources:
    - Real-time: jails, banned IPs (from fail2ban-client)
    - Analytics: threats, unbanned, history (from AttacksDatabase)
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
        self._f2b_client: Optional[Fail2banClient] = None
        self._last_update: Optional[datetime] = None
        self._data_loaded: bool = False

    def compose(self) -> ComposeResult:
        """Build the UI."""
        with Horizontal(id="f2b_plus_header_container"):
            yield Label("[bold cyan]Loading...[/bold cyan]", id="f2b_plus_header")
            yield Input(placeholder="Search IP/jail...", id="f2b_plus_search")

    def on_mount(self) -> None:
        """Setup UI (no data loading - deferred to on_show)."""
        pass  # Data loading moved to on_show for lazy initialization

    def on_show(self) -> None:
        """Load data when tab becomes visible (lazy loading)."""
        if not self._data_loaded:
            self._data_loaded = True
            self._db = AttacksDatabase()
            self._f2b_client = Fail2banClient()
            self._refresh_data()

    def action_open_db_modal(self) -> None:
        """Open the F2B Database Manager modal."""
        from dashboard.widgets.f2b_db_manage_modal import F2BDatabaseModal

        self.app.push_screen(F2BDatabaseModal())

    def action_update_data_manual(self) -> None:
        """Manual refresh action."""
        header = self.query_one("#f2b_plus_header", Label)
        header.update("[bold yellow]⟳ Refreshing...[/bold yellow]")
        self._refresh_data()

    @work(thread=True)
    def _refresh_data(self) -> None:
        """Reload all data in background (auto-parse logs)."""
        try:
            # Initialize/refresh database
            self._db = AttacksDatabase()

            # Auto-parse logs to populate/update database
            from collectors.fail2ban_v2 import Fail2banV2Collector

            collector = Fail2banV2Collector(db=self._db)
            parse_stats = collector.collect()
            logger.info(f"Auto-parsed logs: {parse_stats}")

            # Save database after parsing
            self._db.save()

            # Get real-time data from fail2ban-client
            if not self._f2b_client:
                self._f2b_client = Fail2banClient()

            self._last_update = datetime.now()
            self.app.call_from_thread(self._update_header)
        except Exception as e:
            logger.error(f"Failed to refresh data: {e}")
            self.app.call_from_thread(self._show_error, str(e))

    def _show_error(self, message: str) -> None:
        """Show error in header."""
        try:
            header = self.query_one("#f2b_plus_header", Label)
            header.update(f"[red]Error: {message}[/red]")
        except Exception:
            pass

    def _update_header(self) -> None:
        """Update header with hybrid data (fail2ban-client + AttacksDatabase)."""
        try:
            header = self.query_one("#f2b_plus_header", Label)

            # === Real-time data from fail2ban-client ===
            f2b_summary = {}
            if self._f2b_client:
                f2b_summary = self._f2b_client.get_summary()

            is_running = f2b_summary.get("running", False)
            jails_count = f2b_summary.get("jails_count", 0)
            jails_with_bans = f2b_summary.get("jails_with_bans", 0)
            total_banned = f2b_summary.get("total_banned", 0)

            status_str = "[green]Running[/green]" if is_running else "[red]Stopped[/red]"

            # === Analytics from AttacksDatabase ===
            unbanned_count = 0
            threats_count = 0
            evasion_count = 0
            caught_count = 0

            if self._db:
                all_ips = self._db.get_all_ips()
                logger.debug(f"Loaded {len(all_ips)} IPs from database")

                for ip, data in all_ips.items():
                    # Unbanned = IPs with bans.total > 0 but not currently active
                    bans = data.get("bans", {})
                    if bans.get("total", 0) > 0 and not bans.get("active"):
                        unbanned_count += 1

                    analysis = data.get("analysis", {})
                    
                    # Threats = evasion_detected (slow brute-force, never banned)
                    if analysis.get("evasion_detected"):
                        threats_count += 1

                    # Currently evading (active within 72h)
                    if analysis.get("evasion_active"):
                        evasion_count += 1
                    
                    # Caught = threat_detected (slow brute-force that was banned)
                    if analysis.get("threat_detected"):
                        caught_count += 1

                logger.debug(f"Calculated: unbanned={unbanned_count}, threats={threats_count}, evasion={evasion_count}, caught={caught_count}")

            # === Build header ===
            # Line 1: Fail2ban: Running │ X jails │ Y banned │ Z unbanned │ W threats (N EVADING) │ M caught
            if evasion_count > 0:
                threats_display = f"[yellow]{threats_count}[/yellow] threats ([bold red]{evasion_count} EVADING[/bold red])"
            else:
                threats_display = f"[yellow]{threats_count}[/yellow] threats"
            
            caught_display = f" │ [green]{caught_count}[/green] caught" if caught_count > 0 else ""
            
            line1 = (
                f"[bold cyan]Fail2ban:[/bold cyan] {status_str} │ "
                f"[white]{jails_count}[/white] jails │ "
                f"[red]{total_banned}[/red] banned │ "
                f"[blue]{unbanned_count}[/blue] unbanned │ "
                f"{threats_display}{caught_display}"
            )

            # Line 2: Active: X/Y jails with bans │ Updated: HH:MM:SS
            update_time = ""
            if self._last_update:
                update_time = f"[dim]Updated: {self._last_update.strftime('%H:%M:%S')}[/dim]"

            line2 = f"[cyan]Active:[/cyan] {jails_with_bans}/{jails_count} jails with bans"
            if update_time:
                line2 = f"{line2} │ {update_time}"

            header.update(f"{line1}\n{line2}")

        except Exception as e:
            logger.error(f"Failed to update header: {e}")
