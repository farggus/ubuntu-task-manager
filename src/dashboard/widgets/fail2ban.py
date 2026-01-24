from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Label, Static

from collectors import NetworkCollector
from dashboard.widgets.analysis_modal import AnalysisModal
from utils.logger import get_logger
from utils.ui_helpers import update_table_preserving_scroll

import time

logger = get_logger("fail2ban_tab")


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
        self._last_data = None

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
        table.add_columns("Jail", "Status", "Banned IP", "Country", "Org", "Attempts", "Ban For", "Banned", "Fail")

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

    def _get_selected_ip_info(self) -> tuple:
        """Extract IP and Jail from selected row. Returns (ip, jail)."""
        try:
            table = self.query_one("#f2b_table", DataTable)
            if not table.cursor_coordinate:
                return None, None
            
            curr_row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            curr_row_index = table.get_row_index(curr_row_key)
            row = table.get_row(curr_row_key)
            
            # Column 2 is "Banned IP"
            ip_cell = row[2]
            ip = str(ip_cell).strip()
            
            # Find jail (Column 0)
            jail = str(row[0]).strip()
            
            if not jail:
                for i in range(curr_row_index - 1, -1, -1):
                    try:
                        cell = table.get_cell_at(Coordinate(i, 0))
                        jail_candidate = str(cell).strip()
                        if jail_candidate:
                            jail = jail_candidate
                            break
                    except:
                        break
                        
            return ip, jail
        except Exception as e:
            logger.error(f"Failed to get IP info: {e}")
            return None, None

    @work(thread=True)
    def action_ban_ip(self) -> None:
        """Ban selected IP."""
        ip, jail = self._get_selected_ip_info()
        
        if not ip or ip in ('-', '?', ''):
            msg = "No valid IP selected"
            logger.warning(msg)
            self.app.call_from_thread(self.notify, msg, severity="warning")
            return
            
        logger.info(f"Initiating ban for {ip}")
        self.app.call_from_thread(self.notify, f"Banning {ip}...")
        
        success = self.collector.ban_ip(ip, jail='recidive')
        
        if success:
            msg = f"Banned {ip} permanently"
            logger.info(msg)
            self.app.call_from_thread(self.notify, msg)
            
            if jail and jail not in ('recidive', 'HISTORY', 'SLOW BRUTE-FORCE DETECTOR'):
                    self.collector.unban_ip(ip, jail=jail)
                    msg_rem = f"Removed {ip} from {jail}"
                    logger.info(msg_rem)
                    self.app.call_from_thread(self.notify, msg_rem)

            time.sleep(0.5)
            self.app.call_from_thread(self.update_data)
        else:
            msg = f"Failed to ban {ip}"
            logger.error(msg)
            self.app.call_from_thread(self.notify, msg, severity="error")

    @work(thread=True)
    def action_unban_ip(self) -> None:
        """Unban selected IP."""
        ip, jail = self._get_selected_ip_info()
        
        if not ip or ip in ('-', '?', ''):
            msg = "No valid IP selected"
            logger.warning(msg)
            self.app.call_from_thread(self.notify, msg, severity="warning")
            return
            
        logger.info(f"Initiating unban for {ip}")
        self.app.call_from_thread(self.notify, f"Unbanning {ip}...")
        
        target_jail = jail if jail and jail not in ('HISTORY', 'SLOW BRUTE-FORCE DETECTOR') else None
        
        success = self.collector.unban_ip(ip, jail=target_jail)
        if success:
            msg = f"Unbanned {ip}"
            logger.info(msg)
            self.app.call_from_thread(self.notify, msg)
            
            time.sleep(0.5)
            self.app.call_from_thread(self.update_data)
        else:
            msg = f"Failed to unban {ip}"
            logger.error(msg)
            self.app.call_from_thread(self.notify, msg, severity="error")

    @work(exclusive=True, thread=True)
    def update_data(self) -> None:
        """Fetch data in background."""
        try:
            # We still use NetworkCollector as it collects fail2ban status
            data = self.collector.update()
            self._last_data = data
            try:
                self.app.call_from_thread(self._update_view)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to update fail2ban data: {e}", exc_info=True)

    def _update_view(self) -> None:
        """Update table."""
        if not self._last_data:
            return

        try:
            table = self.query_one("#f2b_table", DataTable)
            header = self.query_one("#f2b_header", Label)

            f2b = self._last_data.get('fail2ban', {})
            f2b_jails = len(f2b.get('jails', [])) if f2b else 0
            f2b_banned = f2b.get('total_banned', 0) if f2b else 0
            
            status_str = "Running" if f2b.get('running') else "Stopped"
            header_text = f"[bold cyan]Fail2ban Status:[/bold cyan] {status_str} │ [white]{f2b_jails}[/white] jails │ [red]{f2b_banned}[/red] total banned"
            header.update(header_text)

            self._populate_fail2ban(table)
        except Exception as e:
            logger.error(f"Failed to update fail2ban view: {e}")

    def _format_bantime(self, seconds: int) -> str:
        """Format bantime as human readable with expiry date."""
        from datetime import datetime, timedelta

        if seconds <= 0:
            return "-"

        expiry = datetime.now() + timedelta(seconds=seconds)
        expiry_str = expiry.strftime("%d.%m.%y")

        if seconds >= 2592000:  # 30 days
            days = seconds // 86400
            return f"{days}d (til {expiry_str})"
        elif seconds >= 86400:  # 1 day
            days = seconds // 86400
            return f"{days}d (til {expiry_str})"
        elif seconds >= 3600:  # 1 hour
            hours = seconds // 3600
            return f"{hours}h (til {expiry_str})"
        else:
            mins = seconds // 60
            return f"{mins}m"

    def _populate_fail2ban(self, table: DataTable) -> None:
        """Populate table with fail2ban jail information."""
        def populate(t):
            f2b = self._last_data.get('fail2ban', {})

            if not f2b or not f2b.get('installed'):
                t.add_row("fail2ban not installed", "", "", "", "", "", "", "", "")
                return

            if not f2b.get('running'):
                t.add_row("fail2ban not running", "", "", "", "", "", "", "", "")
                return

            jails = f2b.get('jails', [])
            if not jails:
                t.add_row("No jails configured", "", "", "", "", "", "", "", "")
                return

            def sort_jails(j):
                name = j.get('name', '')
                banned = j.get('currently_banned', 0)
                
                if 'SLOW' in name: return 4
                if name == 'HISTORY': return 3
                if name == 'recidive': return 2
                if banned > 0: return 1
                return 0

            jails.sort(key=sort_jails)

            for idx, jail in enumerate(jails):
                try:
                    name = jail.get('name', 'N/A')
                    currently_banned = jail.get('currently_banned', 0)
                    total_banned = jail.get('total_banned', 0)
                    filter_failures = jail.get('filter_failures', 0)
                    banned_ips = jail.get('banned_ips', [])

                    if idx > 0 and name != 'HISTORY' and 'SLOW' not in name:
                        t.add_row("", "", "", "", "", "", "", "", "")

                    if name in ('HISTORY', 'SLOW BRUTE-FORCE DETECTOR'):
                        t.add_row("", "", "", "", "", "", "", "", "")
                        
                        header_style = "bold blue" if name == 'HISTORY' else "bold red"
                        header_label = "Unbanned:" if name == 'HISTORY' else "Risk Status:"
                        interval_header = Text("Interval", style="bold") if 'SLOW' in name else ""
                        
                        t.add_row(
                            Text(name, style=header_style),
                            Text("Jail", style="bold"),
                            Text("Banned IP", style="bold"),
                            Text("Country", style="bold"),
                            Text("Org", style="bold"),
                            Text("Attempts", style="bold"),
                            Text(header_label, style="bold"),
                            interval_header, 
                            ""
                        )
                        
                        for idx, ip_info in enumerate(banned_ips):
                            ip_str = ip_info.get('ip', '?')
                            country = ip_info.get('country', 'Unknown')
                            org = ip_info.get('org', '-')
                            if len(org) > 20: org = org[:17] + '...'
                            attempts = ip_info.get('attempts', 0)
                            
                            extra_info = ip_info.get('unban_time') or ip_info.get('status', '')
                            jail_origin = ip_info.get('jail', '?')
                            
                            col1 = Text(f"Total: {total_banned}", style="blue") if idx == 0 else ""
                            jail_status_display = Text(f"[{jail_origin}]", style="blue")
                            
                            attempts_text = Text(str(attempts))
                            if attempts >= 100: attempts_text.style = "bold red"
                            elif attempts >= 20: attempts_text.style = "yellow"
                            
                            extra_text = Text(extra_info)
                            if 'EVASION' in extra_info:
                                extra_text.style = "bold red"
                            elif 'CAUGHT' in extra_info:
                                extra_text.style = "bold yellow"

                            interval_val = ip_info.get('interval', '')
                            interval_text = Text(interval_val, style="bold cyan") if interval_val else ""

                            t.add_row(
                                col1,
                                jail_status_display,
                                Text(ip_str, style="red"),
                                country,
                                org,
                                attempts_text,
                                extra_text, 
                                interval_text,
                                ""
                            )
                        continue

                    if currently_banned > 0:
                        status_text = Text("ACTIVE", style="bold red")
                    else:
                        status_text = Text("OK", style="green")

                    if currently_banned > 0:
                        banned_text = Text(str(currently_banned), style="bold red")
                    else:
                        banned_text = Text(str(currently_banned), style="green")

                    if not banned_ips:
                        t.add_row(
                            Text(name, style="bold"),
                            status_text,
                            "-", "-", "-", "-", "-",
                            banned_text,
                            str(filter_failures)
                        )
                    else:
                        first_ip = banned_ips[0]
                        ip_str = first_ip.get('ip', '?') if isinstance(first_ip, dict) else str(first_ip)
                        country = first_ip.get('country', 'Unknown') if isinstance(first_ip, dict) else 'Unknown'
                        org = first_ip.get('org', '-') if isinstance(first_ip, dict) else '-'
                        if len(org) > 20:
                            org = org[:17] + '...'
                        attempts = first_ip.get('attempts', 0) if isinstance(first_ip, dict) else 0
                        bantime = first_ip.get('bantime', 0) if isinstance(first_ip, dict) else 0
                        
                        jail_display = Text(name, style="bold")
                        ban_for = self._format_bantime(bantime)
                        
                        attempts_text = Text(str(attempts))
                        if attempts >= 100: attempts_text.style = "bold red"
                        elif attempts >= 20: attempts_text.style = "yellow"

                        t.add_row(
                            jail_display,
                            status_text,
                            Text(ip_str, style="red"),
                            country,
                            org,
                            attempts_text,
                            ban_for,
                            banned_text,
                            str(filter_failures)
                        )

                        for ip_info in banned_ips[1:]:
                            ip_str = ip_info.get('ip', '?') if isinstance(ip_info, dict) else str(ip_info)
                            country = ip_info.get('country', 'Unknown') if isinstance(ip_info, dict) else 'Unknown'
                            org = ip_info.get('org', '-') if isinstance(ip_info, dict) else '-'
                            if len(org) > 20:
                                org = org[:17] + '...'
                            attempts = ip_info.get('attempts', 0) if isinstance(ip_info, dict) else 0
                            bantime = ip_info.get('bantime', 0) if isinstance(ip_info, dict) else 0
                            
                            ban_for = self._format_bantime(bantime)
                            attempts_text = Text(str(attempts))
                            if attempts >= 100: attempts_text.style = "bold red"
                            elif attempts >= 20: attempts_text.style = "yellow"

                            t.add_row(
                                "",  # Empty jail name
                                "",  # Empty status
                                Text(ip_str, style="red"),
                                country,
                                org,
                                attempts_text,
                                ban_for,
                                "",  # Empty count
                                ""   # Empty failures
                            )

                except Exception as e:
                    logger.debug(f"Error processing jail: {e}")
                    continue

        update_table_preserving_scroll(table, populate)
