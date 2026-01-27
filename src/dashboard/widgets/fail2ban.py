"""Fail2ban tab widget for the dashboard."""

import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from rich.text import Text
from textual import on, work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.timer import Timer
from textual.widgets import DataTable, Input, Label, Static

from collectors import Fail2banCollector
from dashboard.widgets.analysis_modal import AnalysisModal
from dashboard.widgets.confirm_modal import ConfirmModal
from dashboard.widgets.whitelist_modal import WhitelistModal
from models.fail2ban import JailType
from utils.formatters import (
    format_attempts,
    format_banned_count,
    format_bantime,
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


class SubTab(Enum):
    """Sub-tab types for Fail2ban view."""
    ACTIVE = "active"
    HISTORY = "history"
    SLOW = "slow"


class Fail2banTab(Vertical):
    """Tab displaying Fail2ban information and controls."""

    BINDINGS = [
        Binding("less", "prev_tab", "< Prev Tab", show=False),
        Binding("greater", "next_tab", "> Next Tab", show=False),
        Binding("a", "analyze_logs", "Analyze F2B"),
        Binding("ctrl+b", "ban_ip", "Ban IP"),
        Binding("ctrl+u", "unban_ip", "Unban IP"),
        Binding("ctrl+w", "manage_whitelist", "Whitelist"),
        Binding("ctrl+m", "migrate_bans", "Migrate to 3Y"),
        Binding("R", "update_data_manual", "Refresh"),
    ]

    DEFAULT_CSS = """
    Fail2banTab {
        height: 1fr;
        padding: 0;
    }
    #f2b_header_container {
        height: 4;
        margin: 0;
        padding: 0 1;
        border: round $success;
        margin-bottom: 0;
    }
    #f2b_header {
        margin: 0;
        padding: 0;
        width: auto;
    }
    #f2b_search {
        width: 1fr;
        margin-left: 2;
        border: none;
        background: transparent;
        color: $text;
    }
    #f2b_tabs {
        height: 2;
        margin: 0;
        padding: 0 1;
        align: left middle;
    }
    .tab-item {
        margin-right: 2;
        height: 2;
    }
    .tab-item:hover {
        background: $surface-lighten-1;
    }
    #f2b_table {
        height: 1fr;
        margin: 0;
        padding: 0;
    }
    """

    def __init__(self, collector: Fail2banCollector):
        super().__init__()
        self.collector = collector
        self._last_data: Optional[Dict] = None
        self._last_update: Optional[datetime] = None
        self._current_tab: SubTab = SubTab.ACTIVE
        self._search_term: str = ""
        self._search_timer: Optional[Timer] = None

    def compose(self):
        with Horizontal(id="f2b_header_container"):
            yield Label("[bold cyan]Loading Fail2ban data...[/bold cyan]", id="f2b_header")
            yield Input(placeholder="Search IP/jail...", id="f2b_search")
        with Horizontal(id="f2b_tabs"):
            yield Label("", id="tab_active", classes="tab-item")
            yield Label("", id="tab_history", classes="tab-item")
            yield Label("", id="tab_slow", classes="tab-item")
        yield DataTable(id="f2b_table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Setup table and load initial data."""
        self._setup_table()
        self._update_tab_bar()
        self.update_data()

    def on_click(self, event) -> None:
        """Handle tab clicks."""
        # Check if clicked widget is a tab
        widget = event.widget
        if hasattr(widget, 'id'):
            if widget.id == "tab_active":
                self._switch_to_tab(SubTab.ACTIVE)
            elif widget.id == "tab_history":
                self._switch_to_tab(SubTab.HISTORY)
            elif widget.id == "tab_slow":
                self._switch_to_tab(SubTab.SLOW)

    def on_key(self, event) -> None:
        """Handle key events for sub-tab switching."""
        if event.key == "less":
            self.action_prev_tab()
            event.stop()
        elif event.key == "greater":
            self.action_next_tab()
            event.stop()

    def action_prev_tab(self) -> None:
        """Switch to previous sub-tab."""
        tabs = [SubTab.ACTIVE, SubTab.HISTORY, SubTab.SLOW]
        current_idx = tabs.index(self._current_tab)
        new_idx = (current_idx - 1) % len(tabs)
        self._switch_to_tab(tabs[new_idx])

    def action_next_tab(self) -> None:
        """Switch to next sub-tab."""
        tabs = [SubTab.ACTIVE, SubTab.HISTORY, SubTab.SLOW]
        current_idx = tabs.index(self._current_tab)
        new_idx = (current_idx + 1) % len(tabs)
        self._switch_to_tab(tabs[new_idx])

    def _switch_to_tab(self, tab: SubTab) -> None:
        """Switch to the specified sub-tab."""
        if self._current_tab == tab:
            return

        self._current_tab = tab
        self._update_tab_bar()
        self._setup_table()
        self._update_view()

    def _update_tab_bar(self) -> None:
        """Update the tab bar display."""
        tabs_config = [
            ("tab_active", SubTab.ACTIVE, "< Active"),
            ("tab_history", SubTab.HISTORY, "History"),
            ("tab_slow", SubTab.SLOW, "Slow >"),
        ]

        for tab_id, tab_type, label in tabs_config:
            try:
                tab_label = self.query_one(f"#{tab_id}", Label)
                is_active = self._current_tab == tab_type

                if is_active:
                    tab_label.update(f"[bold reverse] {label} [/bold reverse]\n[bold]{'━' * (len(label) + 2)}[/bold]")
                else:
                    tab_label.update(f"[dim] {label} [/dim]\n[dim]{'─' * (len(label) + 2)}[/dim]")
            except Exception:
                pass

    def _setup_table(self) -> None:
        """Setup table columns based on current tab."""
        table = self.query_one("#f2b_table", DataTable)
        table.clear(columns=True)

        if self._current_tab == SubTab.ACTIVE:
            table.add_columns(
                "Jail", "Status", "Banned IP", "Country", "Org",
                "Attempts", "Ban For", "Banned", "Fail"
            )
        elif self._current_tab == SubTab.HISTORY:
            table.add_columns(
                "Total", "Jail", "IP", "Country", "Org",
                "Attempts", "Unbanned", "", ""
            )
        elif self._current_tab == SubTab.SLOW:
            table.add_columns(
                "Total", "Jail", "IP", "Country", "Org",
                "Attempts", "Status", "Interval", ""
            )

    # === Actions ===

    def action_update_data_manual(self) -> None:
        """Manual refresh action."""
        logger.info("Manual refresh triggered")
        header = self.query_one("#f2b_header", Label)
        header.update("[bold yellow]⟳ Refreshing...[/bold yellow]")
        self.update_data()

    @work(exclusive=True, thread=True)
    def action_analyze_logs(self) -> None:
        """Run fail2ban analysis script."""
        logger.info("Action Analyze Logs triggered")

        # Show analyzing state in header
        def show_analyzing():
            header = self.query_one("#f2b_header", Label)
            header.update("[bold yellow]⏳ Analyzing fail2ban logs... Please wait[/bold yellow]")

        self.app.call_from_thread(show_analyzing)

        # Run analysis
        output = self.collector.run_analysis()

        # Show results and switch to Slow tab
        def show_results():
            self.app.push_screen(AnalysisModal(output))
            self._switch_to_tab(SubTab.SLOW)
            self.update_data()

        self.app.call_from_thread(show_results)

    def action_ban_ip(self) -> None:
        """Show confirmation and ban selected IP."""
        t0 = time.time()
        logger.info("Manual ban action triggered")

        ip, jail = self._get_selected_ip_info()
        logger.debug(f"Selected IP info: ip={ip}, jail={jail}")

        if not ip or ip in ('-', '?', ''):
            self.notify("No valid IP selected", severity="warning")
            return

        logger.debug("Showing ban confirmation modal")
        # Show confirmation modal
        self.app.push_screen(
            ConfirmModal(
                title="Ban IP",
                message=f"Ban [bold red]{ip}[/bold red] permanently in recidive jail?",
                confirm_label="Ban"
            ),
            callback=lambda confirmed: self._do_ban_ip(ip, jail, time.time()) if confirmed else None
        )

    @work(thread=True)
    def _do_ban_ip(self, ip: str, jail: Optional[str], t0: float = None) -> None:
        """Execute ban operation in background."""
        if t0 is None:
            t0 = time.time()
        logger.debug(f"Starting ban operation in background thread for IP {ip}")

        self.app.call_from_thread(self.notify, f"Banning {ip}...")
        logger.debug("Notification sent, calling collector.ban_ip()")

        t1 = time.time()
        success = self.collector.ban_ip(ip, jail='recidive')
        duration = time.time() - t1
        logger.debug(f"collector.ban_ip() completed in {duration:.3f}s, success={success}")

        if success:
            self.app.call_from_thread(
                self.notify, f"✓ Banned {ip} permanently", severity="information"
            )
            logger.debug("Success notification sent")

            # Remove from original jail if it was a temporary ban
            if jail and jail not in ('recidive', *VIRTUAL_JAILS):
                logger.debug(f"Cleaning up from original jail: {jail}")
                t2 = time.time()
                if self.collector.unban_ip(ip, jail=jail):
                    logger.debug(f"Cleanup completed in {time.time()-t2:.3f}s")

            # Refresh to show updated state
            logger.debug("Scheduling update_data()")
            t3 = time.time()
            self.update_data()
            logger.debug(f"update_data() scheduled in {time.time()-t3:.3f}s")
            logger.info(f"Ban operation completed for IP {ip} in {time.time()-t0:.2f}s")
        else:
            self._notify_error(f"Failed to ban {ip}")
            logger.warning(f"Ban operation failed for IP {ip}")

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
            self.app.call_from_thread(
                self.notify, f"✓ Unbanned {ip}", severity="information"
            )
            # Refresh to show updated state
            self.update_data()
        else:
            self._notify_error(f"Failed to unban {ip}")

    def action_manage_whitelist(self) -> None:
        """Open whitelist management modal."""
        ip, _ = self._get_selected_ip_info()
        whitelist = self.collector.get_whitelist()

        def handle_result(result: Optional[str]) -> None:
            if result is None:
                return
            if result.startswith("add:"):
                ip_to_add = result[4:]
                if self.collector.add_to_whitelist(ip_to_add):
                    self.notify(f"✓ Added {ip_to_add} to whitelist", severity="information")
                    self.update_data()
            elif result.startswith("remove:"):
                ip_to_remove = result[7:]
                if self.collector.remove_from_whitelist(ip_to_remove):
                    self.notify(f"✓ Removed {ip_to_remove} from whitelist", severity="information")
                    self.update_data()

        self.app.push_screen(WhitelistModal(whitelist, ip), callback=handle_result)

    def action_migrate_bans(self) -> None:
        """Migrate all recidive bans to 3-year bantime."""
        self.app.push_screen(
            ConfirmModal(
                title="Migrate Bans",
                message="Migrate all recidive bans to [bold]3-year[/bold] bantime?",
                confirm_label="Migrate"
            ),
            callback=lambda confirmed: self._do_migrate_bans() if confirmed else None
        )

    @work(thread=True)
    def _do_migrate_bans(self) -> None:
        """Execute migration in background."""
        self.app.call_from_thread(self.notify, "Migrating recidive bans to 3 years...")

        success, total = self.collector.migrate_recidive_bans()

        if total == 0:
            self.app.call_from_thread(
                self.notify, "No bans to migrate", severity="warning"
            )
        else:
            self.app.call_from_thread(
                self.notify,
                f"✓ Migrated {success}/{total} bans to 3 years",
                severity="information"
            )
            self.update_data()

    # === Search ===

    @on(Input.Changed, "#f2b_search")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input changes with debounce."""
        self._search_term = event.value.lower()

        # Cancel existing timer
        if self._search_timer:
            self._search_timer.stop()

        # Start new debounce timer (300ms)
        self._search_timer = self.set_timer(0.3, self._do_search_refresh)

    def _do_search_refresh(self) -> None:
        """Refresh table view after search debounce."""
        self._update_view()

    def _matches_search(self, *values: str) -> bool:
        """Check if any of the values match the search term."""
        if not self._search_term:
            return True
        search = self._search_term.lower()
        return any(search in str(v).lower() for v in values if v)

    # === Helpers ===

    def _notify_warning(self, msg: str) -> None:
        """Show warning notification."""
        logger.warning(msg)
        self.app.call_from_thread(self.notify, msg, severity="warning")

    def _notify_error(self, msg: str) -> None:
        """Show error notification."""
        logger.error(msg)
        self.app.call_from_thread(self.notify, msg, severity="error")

    def _get_selected_ip_info(self) -> Tuple[Optional[str], Optional[str]]:
        """Extract IP and Jail from selected row."""
        try:
            table = self.query_one("#f2b_table", DataTable)
            if not table.cursor_coordinate:
                return None, None

            if table.row_count == 0:
                return None, None

            curr_row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            row = table.get_row(curr_row_key)

            if self._current_tab == SubTab.ACTIVE:
                # Column 2 is "Banned IP", column 0 is jail
                ip = str(row[2]).strip()
                jail = str(row[0]).strip()

                # If jail is empty, look up in previous rows
                if not jail:
                    curr_row_index = table.get_row_index(curr_row_key)
                    for i in range(curr_row_index - 1, -1, -1):
                        try:
                            cell = table.get_cell_at(Coordinate(i, 0))
                            jail_candidate = str(cell).strip()
                            if jail_candidate:
                                jail = jail_candidate
                                break
                        except Exception:
                            break
            else:
                # HISTORY and SLOW: column 2 is IP, column 1 is jail (in brackets)
                ip = str(row[2]).strip()
                jail = str(row[1]).strip().strip("[]")

            return ip, jail if jail else None
        except Exception as e:
            logger.error(f"Failed to get IP info: {e}")
            return None, None

    # === Data fetching ===

    @work(thread=True)
    def update_data(self) -> None:
        """Fetch data in background."""
        t0 = time.time()
        logger.debug("Starting Fail2Ban data update")
        try:
            t1 = time.time()
            f2b_data = self.collector.update()
            duration = time.time() - t1
            if duration > 10.0:
                logger.warning(f"Slow collector update took {duration:.2f}s")
            else:
                logger.debug(f"collector.update() completed in {duration:.3f}s")
            # Wrap in dict for compatibility with _update_view
            self._last_data = {'fail2ban': f2b_data}
            self._last_update = datetime.now()
            self.app.call_from_thread(self._update_view)
            logger.debug(f"Fail2Ban data update completed in {time.time()-t0:.2f}s")
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
        """Update header with unified 2-line status info."""
        # Collect global stats
        jails = [j for j in f2b.get('jails', []) if j.get('name') not in VIRTUAL_JAILS]
        total_banned = sum(j.get('currently_banned', 0) for j in jails)

        history_jail = next((j for j in f2b.get('jails', []) if j.get('name') == SECTION_HISTORY), None)
        unbanned_count = history_jail.get('total_banned', 0) if history_jail else 0

        slow_jail = next((j for j in f2b.get('jails', []) if 'SLOW' in j.get('name', '')), None)
        threats_count = slow_jail.get('total_banned', 0) if slow_jail else 0
        evasion_count = 0
        if slow_jail:
            evasion_count = sum(1 for ip in slow_jail.get('banned_ips', []) if 'EVASION' in ip.get('status', ''))

        # Line 1: Global status (always visible)
        status_str = "[green]Running[/green]" if f2b.get('running') else "[red]Stopped[/red]"
        evasion_alert = f" │ [bold red blink]{evasion_count} EVADING[/bold red blink]" if evasion_count else ""
        line1 = (
            f"[bold cyan]Fail2ban:[/bold cyan] {status_str} │ "
            f"[white]{len(jails)}[/white] jails │ "
            f"[red]{total_banned}[/red] banned │ "
            f"[blue]{unbanned_count}[/blue] unbanned │ "
            f"[yellow]{threats_count}[/yellow] threats{evasion_alert}"
        )

        # Line 2: Tab-specific info + update time
        update_time = ""
        if self._last_update:
            update_time = f"[dim]Updated: {self._last_update.strftime('%H:%M:%S')}[/dim]"

        if self._current_tab == SubTab.ACTIVE:
            active_jails = sum(1 for j in jails if j.get('currently_banned', 0) > 0)
            line2 = f"[cyan]Active:[/cyan] {active_jails}/{len(jails)} jails with bans"
        elif self._current_tab == SubTab.HISTORY:
            line2 = f"[blue]History:[/blue] Recently unbanned IPs from all jails"
        elif self._current_tab == SubTab.SLOW:
            excluded = slow_jail.get('excluded_count', 0) if slow_jail else 0
            excluded_text = f" ({excluded} already banned)" if excluded else ""
            line2 = f"[yellow]Slow Detector:[/yellow] IPs evading findtime{excluded_text}"

        if update_time:
            line2 = f"{line2} │ {update_time}"

        header.update(f"{line1}\n{line2}")

    # === Table population ===

    def _populate_table(self, table: DataTable, f2b: Dict) -> None:
        """Populate table based on current tab."""

        def populate(t: DataTable) -> None:
            if not f2b or not f2b.get('installed'):
                t.add_row("fail2ban not installed", *[""] * 8)
                return

            if not f2b.get('running'):
                t.add_row("fail2ban not running", *[""] * 8)
                return

            if self._current_tab == SubTab.ACTIVE:
                self._populate_active_tab(t, f2b)
            elif self._current_tab == SubTab.HISTORY:
                self._populate_history_tab(t, f2b)
            elif self._current_tab == SubTab.SLOW:
                self._populate_slow_tab(t, f2b)

        update_table_preserving_scroll(table, populate)

    def _populate_active_tab(self, t: DataTable, f2b: Dict) -> None:
        """Populate Active jails tab."""
        jails = [j for j in f2b.get('jails', []) if j.get('name') not in VIRTUAL_JAILS]

        if not jails:
            t.add_row("No jails configured", *[""] * 8)
            return

        # Sort: OK jails first, ACTIVE jails next, recidive always last
        def sort_key(j: Dict) -> tuple:
            name = j.get('name', '')
            has_bans = j.get('currently_banned', 0) > 0
            if name == 'recidive':
                return (2, name)  # Always last
            elif has_bans:
                return (1, name)  # ACTIVE jails in middle
            else:
                return (0, name)  # OK jails first

        jails = sorted(jails, key=sort_key)

        # Filter by search term
        if self._search_term:
            filtered_jails = []
            for jail in jails:
                name = jail.get('name', '')
                # Check jail name
                if self._matches_search(name):
                    filtered_jails.append(jail)
                    continue
                # Check banned IPs
                for ip_info in jail.get('banned_ips', []):
                    if self._matches_search(
                        ip_info.get('ip', ''),
                        ip_info.get('country', ''),
                        ip_info.get('org', '')
                    ):
                        filtered_jails.append(jail)
                        break
            jails = filtered_jails

        if not jails:
            t.add_row(f"No matches for '{self._search_term}'", *[""] * 8)
            return

        prev_had_bans = None
        for jail in jails:
            has_bans = jail.get('currently_banned', 0) > 0
            # Add separator only between OK→ACTIVE or ACTIVE→ACTIVE (not between OK→OK)
            need_separator = prev_had_bans is not None and (prev_had_bans or has_bans)
            self._render_regular_jail(t, jail, need_separator)
            prev_had_bans = has_bans

    def _populate_history_tab(self, t: DataTable, f2b: Dict) -> None:
        """Populate History tab."""
        history_jail = next((j for j in f2b.get('jails', []) if j.get('name') == SECTION_HISTORY), None)

        if not history_jail:
            t.add_row("No history data", *[""] * 8)
            return

        banned_ips = history_jail.get('banned_ips', [])
        total = history_jail.get('total_banned', 0)

        if not banned_ips:
            t.add_row("No recently unbanned IPs", *[""] * 8)
            return

        # Filter by search term
        if self._search_term:
            banned_ips = [
                ip for ip in banned_ips
                if self._matches_search(
                    ip.get('ip', ''),
                    ip.get('jail', ''),
                    ip.get('country', ''),
                    ip.get('org', '')
                )
            ]

        if not banned_ips:
            t.add_row(f"No matches for '{self._search_term}'", *[""] * 8)
            return

        for idx, ip_info in enumerate(banned_ips):
            col0 = Text(f"Total: {total}", style="blue") if idx == 0 else ""
            jail_origin = ip_info.get('jail', '?')

            t.add_row(
                col0,
                Text(f"[{jail_origin}]", style="cyan"),
                Text(ip_info.get('ip', '?'), style="yellow"),
                ip_info.get('country', 'Unknown'),
                format_org(ip_info.get('org', '-')),
                format_attempts(ip_info.get('attempts', 0)),
                ip_info.get('unban_time', ''),
                "",
                ""
            )

    def _populate_slow_tab(self, t: DataTable, f2b: Dict) -> None:
        """Populate Slow Detector tab."""
        slow_jail = next((j for j in f2b.get('jails', []) if 'SLOW' in j.get('name', '')), None)

        if not slow_jail:
            t.add_row("No analysis data. Press 'a' to analyze.", *[""] * 8)
            return

        banned_ips = slow_jail.get('banned_ips', [])
        total = slow_jail.get('total_banned', 0)
        excluded = slow_jail.get('excluded_count', 0)

        if not banned_ips:
            if excluded > 0:
                t.add_row(f"All {excluded} threats already banned!", *[""] * 8)
            else:
                t.add_row("No slow brute-force attacks detected", *[""] * 8)
            return

        # Filter out whitelisted IPs
        banned_ips = [ip for ip in banned_ips if not self.collector.is_whitelisted(ip.get('ip', ''))]

        # Filter by search term
        if self._search_term:
            banned_ips = [
                ip for ip in banned_ips
                if self._matches_search(
                    ip.get('ip', ''),
                    ip.get('jail', ''),
                    ip.get('country', ''),
                    ip.get('org', ''),
                    ip.get('status', '')
                )
            ]

        if not banned_ips:
            if self._search_term:
                t.add_row(f"No matches for '{self._search_term}'", *[""] * 8)
            else:
                t.add_row("All threats whitelisted or banned", *[""] * 8)
            return

        for idx, ip_info in enumerate(banned_ips):
            # First row shows total
            if idx == 0:
                if excluded > 0:
                    col0 = Text(f"Total: {total} ({excluded} banned)", style="red")
                else:
                    col0 = Text(f"Total: {total}", style="red")
            else:
                col0 = ""

            jail_origin = ip_info.get('jail', '?')
            status = ip_info.get('status', '')
            interval = ip_info.get('interval', '')

            # Highlight EVASION status
            status_style = "bold red" if "EVASION" in status else "yellow"

            t.add_row(
                col0,
                Text(f"[{jail_origin}]", style="cyan"),
                Text(ip_info.get('ip', '?'), style="red"),
                ip_info.get('country', 'Unknown'),
                format_org(ip_info.get('org', '-')),
                format_attempts(ip_info.get('attempts', 0)),
                Text(status, style=status_style),
                Text(interval, style="bold cyan") if interval else "",
                ""
            )

    def _render_regular_jail(self, t: DataTable, jail: Dict, add_separator: bool = False) -> None:
        """Render a regular jail with its banned IPs."""
        name = jail.get('name', 'N/A')
        currently_banned = jail.get('currently_banned', 0)
        filter_failures = jail.get('filter_failures', 0)
        banned_ips = jail.get('banned_ips', [])

        # Filter IPs by search term (if search doesn't match jail name)
        if self._search_term and not self._matches_search(name):
            banned_ips = [
                ip for ip in banned_ips
                if self._matches_search(
                    ip.get('ip', ''),
                    ip.get('country', ''),
                    ip.get('org', '')
                )
            ]

        # Add separator if needed
        if add_separator:
            t.add_row(*[""] * 9)

        status_text = format_jail_status(currently_banned)
        banned_text = format_banned_count(currently_banned)

        if not banned_ips:
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
                    "",
                    "",
                    Text(ip_info.get('ip', '?'), style="red"),
                    ip_info.get('country', 'Unknown'),
                    format_org(ip_info.get('org', '-')),
                    format_attempts(ip_info.get('attempts', 0)),
                    format_bantime(ip_info.get('bantime', 0)),
                    "",
                    ""
                )
