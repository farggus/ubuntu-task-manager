"""Fail2ban tab widget for the dashboard."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Label, Static

from collectors import NetworkCollector
from dashboard.widgets.analysis_modal import AnalysisModal
from dashboard.widgets.confirm_modal import ConfirmModal
from models.fail2ban import JailType
from utils.formatters import (
    format_attempts,
    format_bantime,
    format_banned_count,
    format_jail_status,
    format_org,
    format_status,
)
from utils.logger import get_logger
from utils.ui_helpers import update_table_preserving_scroll

logger = get_logger("fail2ban_tab")

# Section names
SECTION_HISTORY = "HISTORY"
SECTION_SLOW_DETECTOR = "SLOW BRUTE-FORCE DETECTOR"

# Virtual jail names (not real fail2ban jails)
VIRTUAL_JAILS = (SECTION_HISTORY, SECTION_SLOW_DETECTOR)


class Fail2banTab(Vertical):
    """Tab displaying Fail2ban information and controls."""

    BINDINGS = [
        Binding("a", "analyze_logs", "Analyze F2B"),
        Binding("ctrl+b", "ban_ip", "Ban IP"),
        Binding("ctrl+u", "unban_ip", "Unban IP"),
        Binding("R", "action_update_data", "Refresh"),
    ]

    DEFAULT_CSS = """
    Fail2banTab {
        height: 1fr;
        padding: 0;
    }
    #f2b_header_container {
        height: 3;
        margin: 0;
        padding: 0 1;
        border: round $success;
        margin-bottom: 0;
    }
    #f2b_header {
        margin: 0;
        padding: 0;
        width: 100%;
    }
    #f2b_table {
        height: 1fr;
        margin: 0;
        padding: 0;
    }
    """

    def __init__(self, collector: NetworkCollector):
        super().__init__()
        self.collector = collector
        self._last_data: Optional[Dict] = None
        self._last_update: Optional[datetime] = None

    def compose(self):
        with Static(id="f2b_header_container"):
            yield Label("[bold cyan]Loading Fail2ban data...[/bold cyan]", id="f2b_header")
        yield DataTable(id="f2b_table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Setup table and start updates."""
        self._setup_table()
        self.update_data()
        self.set_interval(60, self.update_data)

    def _setup_table(self) -> None:
        """Setup table columns."""
        table = self.query_one("#f2b_table", DataTable)
        table.clear(columns=True)
        table.add_columns(
            "Jail", "Status", "Banned IP", "Country", "Org",
            "Attempts", "Ban For", "Banned", "Fail"
        )

    # === Actions ===

    def action_update_data(self) -> None:
        """Manual refresh action."""
        self.notify("Refreshing Fail2ban data...")
        self.update_data()

    @work(exclusive=True, thread=True)
    def action_analyze_logs(self) -> None:
        """Run fail2ban analysis script."""
        logger.info("Action Analyze Logs triggered")
        self.app.call_from_thread(self.notify, "Running analysis... Please wait.")
        output = self.collector.run_f2b_analysis()
        self.app.call_from_thread(self.app.push_screen, AnalysisModal(output))
        self.app.call_from_thread(self.update_data)

    def action_ban_ip(self) -> None:
        """Show confirmation and ban selected IP."""
        ip, jail = self._get_selected_ip_info()

        if not ip or ip in ('-', '?', ''):
            self.notify("No valid IP selected", severity="warning")
            return

        # Show confirmation modal
        self.app.push_screen(
            ConfirmModal(
                title="Ban IP",
                message=f"Ban [bold red]{ip}[/bold red] permanently in recidive jail?",
                confirm_label="Ban"
            ),
            callback=lambda confirmed: self._do_ban_ip(ip, jail) if confirmed else None
        )

    @work(thread=True)
    def _do_ban_ip(self, ip: str, jail: Optional[str]) -> None:
        """Execute ban operation in background."""
        logger.info(f"Initiating ban for {ip}")
        self.app.call_from_thread(self.notify, f"Banning {ip}...")

        success = self.collector.ban_ip(ip, jail='recidive')

        if success:
            logger.info(f"Banned {ip} permanently")
            self.app.call_from_thread(self.notify, f"Banned {ip} permanently")

            # Remove from original jail if it was a temporary ban
            if jail and jail not in ('recidive', *VIRTUAL_JAILS):
                self.collector.unban_ip(ip, jail=jail)
                logger.info(f"Removed {ip} from {jail}")
                self.app.call_from_thread(self.notify, f"Removed {ip} from {jail}")

            self._schedule_refresh()
        else:
            self._notify_error(f"Failed to ban {ip}")

    def action_unban_ip(self) -> None:
        """Show confirmation and unban selected IP."""
        ip, jail = self._get_selected_ip_info()

        if not ip or ip in ('-', '?', ''):
            self.notify("No valid IP selected", severity="warning")
            return

        target_jail = jail if jail and jail not in VIRTUAL_JAILS else None
        jail_info = f" from {target_jail}" if target_jail else " from all jails"

        # Show confirmation modal
        self.app.push_screen(
            ConfirmModal(
                title="Unban IP",
                message=f"Unban [bold cyan]{ip}[/bold cyan]{jail_info}?",
                confirm_label="Unban"
            ),
            callback=lambda confirmed: self._do_unban_ip(ip, target_jail) if confirmed else None
        )

    @work(thread=True)
    def _do_unban_ip(self, ip: str, jail: Optional[str]) -> None:
        """Execute unban operation in background."""
        logger.info(f"Initiating unban for {ip}")
        self.app.call_from_thread(self.notify, f"Unbanning {ip}...")

        success = self.collector.unban_ip(ip, jail=jail)
        if success:
            logger.info(f"Unbanned {ip}")
            self.app.call_from_thread(self.notify, f"Unbanned {ip}")
            self._schedule_refresh()
        else:
            self._notify_error(f"Failed to unban {ip}")

    # === Helpers ===

    def _notify_warning(self, msg: str) -> None:
        """Show warning notification."""
        logger.warning(msg)
        self.app.call_from_thread(self.notify, msg, severity="warning")

    def _notify_error(self, msg: str) -> None:
        """Show error notification."""
        logger.error(msg)
        self.app.call_from_thread(self.notify, msg, severity="error")

    def _schedule_refresh(self) -> None:
        """Schedule data refresh after a short delay."""
        self.app.call_from_thread(lambda: self.set_timer(0.5, self.update_data))

    def _get_selected_ip_info(self) -> Tuple[Optional[str], Optional[str]]:
        """Extract IP and Jail from selected row."""
        try:
            table = self.query_one("#f2b_table", DataTable)
            if not table.cursor_coordinate:
                return None, None

            # Check if table has any rows
            if table.row_count == 0:
                return None, None

            curr_row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            curr_row_index = table.get_row_index(curr_row_key)
            row = table.get_row(curr_row_key)

            # Column 2 is "Banned IP"
            ip = str(row[2]).strip()

            # Determine if we're in a special section (HISTORY or SLOW)
            # by checking if column 0 starts with "Total:" or is a section name
            col0 = str(row[0]).strip()
            col1 = str(row[1]).strip()

            # For HISTORY/SLOW sections, jail is in column 1 (in brackets like "[sshd]")
            if col0.startswith("Total:") or col0 in VIRTUAL_JAILS:
                # Extract jail from column 1, removing brackets
                jail = col1.strip("[]")
            elif col1.startswith("[") and col1.endswith("]"):
                # Also in a special section row
                jail = col1.strip("[]")
            else:
                # Regular jail - find jail name in column 0
                jail = col0

                if not jail:
                    # Look up for grouped rows to find the jail name
                    for i in range(curr_row_index - 1, -1, -1):
                        try:
                            cell = table.get_cell_at(Coordinate(i, 0))
                            jail_candidate = str(cell).strip()
                            # Skip "Total:" entries and section headers
                            if jail_candidate and not jail_candidate.startswith("Total:") and jail_candidate not in VIRTUAL_JAILS:
                                jail = jail_candidate
                                break
                        except Exception:
                            break

            return ip, jail if jail else None
        except Exception as e:
            logger.error(f"Failed to get IP info: {e}")
            return None, None

    # === Data fetching ===

    @work(exclusive=True, thread=True)
    def update_data(self) -> None:
        """Fetch data in background."""
        try:
            data = self.collector.update()
            self._last_data = data
            self._last_update = datetime.now()
            try:
                self.app.call_from_thread(self._update_view)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to update fail2ban data: {e}", exc_info=True)

    def _update_view(self) -> None:
        """Update header and table."""
        if not self._last_data:
            return

        try:
            table = self.query_one("#f2b_table", DataTable)
            header = self.query_one("#f2b_header", Label)

            f2b = self._last_data.get('fail2ban', {})
            self._update_header(header, f2b)
            self._populate_table(table, f2b)
        except Exception as e:
            logger.error(f"Failed to update fail2ban view: {e}")

    def _update_header(self, header: Label, f2b: Dict) -> None:
        """Update header with status info."""
        f2b_jails = len(f2b.get('jails', [])) if f2b else 0
        f2b_banned = f2b.get('total_banned', 0) if f2b else 0
        status_str = "Running" if f2b.get('running') else "Stopped"

        # Add last update time
        update_time = ""
        if self._last_update:
            update_time = f" │ [dim]Updated: {self._last_update.strftime('%H:%M:%S')}[/dim]"

        header_text = (
            f"[bold cyan]Fail2ban:[/bold cyan] {status_str} │ "
            f"[white]{f2b_jails}[/white] jails │ "
            f"[red]{f2b_banned}[/red] banned{update_time}"
        )
        header.update(header_text)

    # === Table population ===

    def _populate_table(self, table: DataTable, f2b: Dict) -> None:
        """Populate table with fail2ban jail information."""

        def populate(t: DataTable) -> None:
            if not f2b or not f2b.get('installed'):
                t.add_row("fail2ban not installed", *[""] * 8)
                return

            if not f2b.get('running'):
                t.add_row("fail2ban not running", *[""] * 8)
                return

            jails = f2b.get('jails', [])
            if not jails:
                t.add_row("No jails configured", *[""] * 8)
                return

            # Sort jails: active with bans first, then recidive, then HISTORY, then SLOW
            jails = self._sort_jails(jails)

            for idx, jail in enumerate(jails):
                try:
                    name = jail.get('name', 'N/A')
                    jail_type = self._get_jail_type(name)

                    if jail_type == JailType.HISTORY:
                        self._render_history_section(t, jail)
                    elif jail_type == JailType.SLOW_DETECTOR:
                        self._render_slow_detector_section(t, jail)
                    else:
                        self._render_regular_jail(t, jail, idx)

                except Exception as e:
                    logger.debug(f"Error processing jail: {e}")
                    continue

        update_table_preserving_scroll(table, populate)

    def _sort_jails(self, jails: List[Dict]) -> List[Dict]:
        """Sort jails by priority."""
        def sort_key(j: Dict) -> int:
            name = j.get('name', '')
            banned = j.get('currently_banned', 0)

            if 'SLOW' in name:
                return 4
            if name == SECTION_HISTORY:
                return 3
            if name == 'recidive':
                return 2
            if banned > 0:
                return 1
            return 0

        return sorted(jails, key=sort_key)

    def _get_jail_type(self, name: str) -> JailType:
        """Determine jail type from name."""
        if name == SECTION_HISTORY:
            return JailType.HISTORY
        elif 'SLOW' in name:
            return JailType.SLOW_DETECTOR
        return JailType.REGULAR

    def _add_separator(self, t: DataTable) -> None:
        """Add empty row as visual separator."""
        t.add_row(*[""] * 9)

    # === Section renderers ===

    def _render_regular_jail(self, t: DataTable, jail: Dict, idx: int) -> None:
        """Render a regular jail with its banned IPs."""
        name = jail.get('name', 'N/A')
        currently_banned = jail.get('currently_banned', 0)
        filter_failures = jail.get('filter_failures', 0)
        banned_ips = jail.get('banned_ips', [])

        # Add separator between jails (except first)
        if idx > 0:
            self._add_separator(t)

        status_text = format_jail_status(currently_banned)
        banned_text = format_banned_count(currently_banned)

        if not banned_ips:
            # Jail with no banned IPs
            t.add_row(
                Text(name, style="bold"),
                status_text,
                "-", "-", "-", "-", "-",
                banned_text,
                str(filter_failures)
            )
        else:
            # First IP row includes jail name and stats
            first_ip = banned_ips[0]
            t.add_row(
                Text(name, style="bold"),
                status_text,
                Text(first_ip.get('ip', '?'), style="red"),
                first_ip.get('country', 'Unknown'),
                format_org(first_ip.get('org', '-')),
                format_attempts(first_ip.get('attempts', 0)),
                format_bantime(first_ip.get('bantime', 0)),
                banned_text,
                str(filter_failures)
            )

            # Additional IPs
            for ip_info in banned_ips[1:]:
                t.add_row(
                    "",  # Empty jail name
                    "",  # Empty status
                    Text(ip_info.get('ip', '?'), style="red"),
                    ip_info.get('country', 'Unknown'),
                    format_org(ip_info.get('org', '-')),
                    format_attempts(ip_info.get('attempts', 0)),
                    format_bantime(ip_info.get('bantime', 0)),
                    "",  # Empty count
                    ""   # Empty failures
                )

    def _render_history_section(self, t: DataTable, jail: Dict) -> None:
        """Render HISTORY section with unbanned IPs."""
        total_banned = jail.get('total_banned', 0)
        banned_ips = jail.get('banned_ips', [])

        # Section separator and header
        self._add_separator(t)
        t.add_row(
            Text(SECTION_HISTORY, style="bold blue"),
            Text("Jail", style="bold"),
            Text("IP", style="bold"),
            Text("Country", style="bold"),
            Text("Org", style="bold"),
            Text("Attempts", style="bold"),
            Text("Unbanned", style="bold"),
            "",
            ""
        )

        # Data rows
        for idx, ip_info in enumerate(banned_ips):
            col1 = Text(f"Total: {total_banned}", style="blue") if idx == 0 else ""
            jail_origin = ip_info.get('jail', '?')

            t.add_row(
                col1,
                Text(f"[{jail_origin}]", style="blue"),
                Text(ip_info.get('ip', '?'), style="red"),
                ip_info.get('country', 'Unknown'),
                format_org(ip_info.get('org', '-')),
                format_attempts(ip_info.get('attempts', 0)),
                ip_info.get('unban_time', ''),
                "",
                ""
            )

    def _render_slow_detector_section(self, t: DataTable, jail: Dict) -> None:
        """Render SLOW BRUTE-FORCE DETECTOR section."""
        total_banned = jail.get('total_banned', 0)
        banned_ips = jail.get('banned_ips', [])

        # Section separator and header
        self._add_separator(t)
        t.add_row(
            Text(SECTION_SLOW_DETECTOR, style="bold red"),
            Text("Jail", style="bold"),
            Text("IP", style="bold"),
            Text("Country", style="bold"),
            Text("Org", style="bold"),
            Text("Attempts", style="bold"),
            Text("Status", style="bold"),
            Text("Interval", style="bold"),
            ""
        )

        # Data rows
        for idx, ip_info in enumerate(banned_ips):
            col1 = Text(f"Total: {total_banned}", style="red") if idx == 0 else ""
            jail_origin = ip_info.get('jail', '?')
            status = ip_info.get('status', '')
            interval = ip_info.get('interval', '')

            t.add_row(
                col1,
                Text(f"[{jail_origin}]", style="blue"),
                Text(ip_info.get('ip', '?'), style="red"),
                ip_info.get('country', 'Unknown'),
                format_org(ip_info.get('org', '-')),
                format_attempts(ip_info.get('attempts', 0)),
                format_status(status),
                Text(interval, style="bold cyan") if interval else "",
                ""
            )
