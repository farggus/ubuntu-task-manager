"""Network tab widget."""

from typing import Any, Dict

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static

from collectors import NetworkCollector
from dashboard.widgets.analysis_modal import AnalysisModal
from utils.logger import get_logger
from utils.ui_helpers import update_table_preserving_scroll

logger = get_logger("network_tab")


class NetworkExtendedTab(Vertical):
    """Tab displaying detailed network information."""

    # View modes
    VIEW_PORTS = 'ports'
    VIEW_INTERFACES = 'interfaces'
    VIEW_FIREWALL = 'firewall'
    VIEW_ROUTES = 'routes'
    VIEW_FAIL2BAN = 'fail2ban'
    VIEW_IPTABLES = 'iptables'
    VIEW_NFTABLES = 'nftables'

    BINDINGS = [
        Binding("p", "show_ports", "Ports"),
        Binding("i", "show_interfaces", "Interfaces"),
        Binding("f", "show_firewall", "Firewall Check"),
        Binding("r", "show_routes", "Routes"),
        Binding("b", "show_fail2ban", "Fail2ban"),
        Binding("t", "show_iptables", "IPTables"),
        Binding("n", "show_nftables", "NFTables"),
        Binding("a", "analyze_logs", "Analyze F2B"),
        Binding("ctrl+b", "ban_ip", "Ban IP"),
        Binding("ctrl+u", "unban_ip", "Unban IP"),
    ]

    # Virtual interface prefixes (sorted to end)
    VIRTUAL_PREFIXES = ('br-', 'veth', 'docker', 'virbr', 'vnet', 'tun', 'tap', 'lo')

    DEFAULT_CSS = """
    NetworkExtendedTab {
        height: 1fr;
        padding: 0;
    }
    #network_header_container {
        height: 3;
        margin: 0;
        padding: 0 1;
        border: round $success;
        margin-bottom: 0;
    }
    #network_header {
        margin: 0;
        padding: 0;
        width: 100%;
    }
    #network_table {
        height: 1fr;
        margin: 0;
        padding: 0;
    }
    """

    def __init__(self, collector: NetworkCollector):
        super().__init__()
        self.collector = collector
        self._current_view = self.VIEW_PORTS
        self._last_data = None

    def compose(self):
        with Static(id="network_header_container"):
            yield Label("[bold cyan]Loading...[/bold cyan]", id="network_header")
        yield DataTable(id="network_table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Setup table and start updates."""
        self._setup_table_columns()
        self.update_data()
        self.set_interval(15, self.update_data)

    def _setup_table_columns(self) -> None:
        """Setup table columns based on current view mode."""
        try:
            table = self.query_one("#network_table", DataTable)
            table.clear(columns=True)
            table.fixed_columns = 0 # Allow all columns to be flexible

            if self._current_view == self.VIEW_PORTS:
                table.add_columns("Port", "Proto", "Address", "Process", "PID", "Conns")
            elif self._current_view == self.VIEW_INTERFACES:
                table.add_columns("Interface", "Status", "IP Address", "MAC", "Speed")
            elif self._current_view == self.VIEW_FIREWALL:
                table.add_columns("Rule")
            elif self._current_view == self.VIEW_ROUTES:
                table.add_columns("Destination", "Gateway", "Interface", "Flags")
            elif self._current_view == self.VIEW_FAIL2BAN:
                table.add_columns("Jail", "Status", "Banned IP", "Country", "Org", "Attempts", "Ban For", "Banned", "Fail")
            elif self._current_view == self.VIEW_IPTABLES:
                table.add_columns("Chain", "Num", "Target", "Prot", "Source", "Destination", "Options")
            elif self._current_view == self.VIEW_NFTABLES:
                table.add_column("Table")
                table.add_column("Chain")
                table.add_column("Type")
                table.add_column("Hook")
                table.add_column("Prio")
                table.add_column("Policy")
                # Rule Details with extra width for long IPv6 rules (~110 chars)
                table.add_column("Rule Details", width=115)
        except Exception as e:
            logger.error(f"Failed to setup table columns: {e}")

    def _switch_view(self, view: str) -> None:
        """Switch to a different view."""
        if self._current_view == view:
            return
        self._current_view = view
        self._setup_table_columns()
        self._update_view()

    def action_show_ports(self) -> None:
        self._switch_view(self.VIEW_PORTS)

    def action_show_interfaces(self) -> None:
        self._switch_view(self.VIEW_INTERFACES)

    def action_show_firewall(self) -> None:
        self._switch_view(self.VIEW_FIREWALL)

    def action_show_routes(self) -> None:
        self._switch_view(self.VIEW_ROUTES)

    def action_show_fail2ban(self) -> None:
        self._switch_view(self.VIEW_FAIL2BAN)

    def action_show_iptables(self) -> None:
        self._switch_view(self.VIEW_IPTABLES)

    def action_show_nftables(self) -> None:
        self._switch_view(self.VIEW_NFTABLES)

    @work(exclusive=True, thread=True)
    def action_analyze_logs(self) -> None:
        """Run fail2ban analysis script."""
        logger.info("Action Analyze Logs triggered")
        self.app.call_from_thread(self.notify, "Running analysis... Please wait.")
        output = self.collector.run_f2b_analysis()
        self.app.call_from_thread(self.app.push_screen, AnalysisModal(output))
        # Refresh data to show new pseudo-jail
        self.app.call_from_thread(self.update_data)

    def _get_selected_ip(self) -> str:
        """Extract IP from selected row."""
        try:
            table = self.query_one("#network_table", DataTable)
            if not table.cursor_coordinate:
                return None
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            row = table.get_row(row_key)
            
            if self._current_view == self.VIEW_FAIL2BAN:
                # Column 2 is "Banned IP" (index 2)
                # Jail, Status, Banned IP, Country ...
                # Note: Row content might be Text objects
                ip_cell = row[2] 
                return str(ip_cell).strip()
            
            return None
        except Exception as e:
            logger.error(f"Failed to get IP: {e}")
            return None

    def action_ban_ip(self) -> None:
        """Ban selected IP."""
        ip = self._get_selected_ip()
        if not ip or ip in ('-', '?', ''):
            self.notify("No valid IP selected (Select row in Fail2ban view)", severity="warning")
            return
            
        def do_ban():
            success = self.collector.ban_ip(ip)
            if success:
                self.app.call_from_thread(self.notify, f"Banned {ip}")
                self.app.call_from_thread(self.update_data)
            else:
                self.app.call_from_thread(self.notify, f"Failed to ban {ip}", severity="error")
        
        self.notify(f"Banning {ip}...")
        import threading
        threading.Thread(target=do_ban).start()

    def action_unban_ip(self) -> None:
        """Unban selected IP."""
        ip = self._get_selected_ip()
        if not ip or ip in ('-', '?', ''):
            self.notify("No valid IP selected", severity="warning")
            return
            
        def do_unban():
            success = self.collector.unban_ip(ip)
            if success:
                self.app.call_from_thread(self.notify, f"Unbanned {ip}")
                self.app.call_from_thread(self.update_data)
            else:
                self.app.call_from_thread(self.notify, f"Failed to unban {ip}", severity="error")
        
        self.notify(f"Unbanning {ip}...")
        import threading
        threading.Thread(target=do_unban).start()

    @work(exclusive=True, thread=True)
    def update_data(self) -> None:
        """Fetch data in background."""
        try:
            data = self.collector.update()
            self._last_data = data
            self.app.call_from_thread(self._update_view)
        except Exception as e:
            logger.error(f"Failed to update network data: {e}", exc_info=True)

    def _update_view(self) -> None:
        """Update table with current view mode."""
        if not self._last_data:
            return

        try:
            table = self.query_one("#network_table", DataTable)
            header = self.query_one("#network_header", Label)

            # Build header with stats from all views
            header_text = self._build_header()
            header.update(header_text)

            # Populate table based on current view
            if self._current_view == self.VIEW_PORTS:
                self._populate_ports(table)
            elif self._current_view == self.VIEW_INTERFACES:
                self._populate_interfaces(table)
            elif self._current_view == self.VIEW_FIREWALL:
                self._populate_firewall(table)
            elif self._current_view == self.VIEW_ROUTES:
                self._populate_routes(table)
            elif self._current_view == self.VIEW_FAIL2BAN:
                self._populate_fail2ban(table)
            elif self._current_view == self.VIEW_IPTABLES:
                self._populate_iptables(table)
            elif self._current_view == self.VIEW_NFTABLES:
                self._populate_nftables(table)
        except Exception as e:
            logger.error(f"Failed to update network view: {e}")

    def _build_header(self) -> str:
        """Build header string with stats."""
        data = self._last_data

        # Interfaces stats
        interfaces = data.get('interfaces', [])
        ifaces_up = sum(1 for i in interfaces if i.get('is_up'))
        ifaces_total = len(interfaces)

        # Ports stats
        ports = data.get('open_ports', [])
        valid_ports = [p for p in ports if 'error' not in p]
        ports_count = len(valid_ports)
        active_conns = sum(p.get('connections', 0) for p in valid_ports)

        # Firewall stats
        fw = data.get('firewall', {})
        fw_type = fw.get('type', 'none') if fw else 'none'
        fw_status = fw.get('status', 'unknown') if fw else 'N/A'
        
        # IPtables stats
        iptables_data = data.get('iptables', [])
        ipt_count = len(iptables_data) if isinstance(iptables_data, list) else 0

        # NFTables stats
        nft_data = data.get('nftables', {})
        nft_count = 0
        if isinstance(nft_data, dict) and 'nftables' in nft_data:
            nft_count = sum(1 for item in nft_data['nftables'] if 'rule' in item)

        # Firewall status color
        if fw_status in ['active', 'running', 'configured']:
            fw_status_str = f"[green]{fw_type}[/green] [dim]({fw_status})[/dim]"
        elif fw_status == 'inactive':
            fw_status_str = f"[yellow]{fw_type}[/yellow] [dim]({fw_status})[/dim]"
        elif fw_type == 'none':
            fw_status_str = "[dim]none[/dim]"
        else:
            fw_status_str = f"[red]{fw_type}[/red] [dim]({fw_status})[/dim]"

        # Routes stats
        routes = data.get('routing', [])
        routes_count = len(routes)

        # Fail2ban stats
        f2b = data.get('fail2ban', {})
        f2b_jails = len(f2b.get('jails', [])) if f2b else 0
        f2b_banned = f2b.get('total_banned', 0) if f2b else 0

        # Current view indicator
        view_labels = {
            self.VIEW_PORTS: '► Ports',
            self.VIEW_INTERFACES: '► Interfaces',
            self.VIEW_FIREWALL: '► FW Check',
            self.VIEW_ROUTES: '► Routes',
            self.VIEW_FAIL2BAN: '► Fail2ban',
            self.VIEW_IPTABLES: '► IPTables',
            self.VIEW_NFTABLES: '► NFTables',
        }
        current = f"[bold cyan]{view_labels.get(self._current_view, 'Unknown')}[/bold cyan]"

        return (
            f"{current} │ "
            f"[dim]Ifaces:[/dim] [green]{ifaces_up}[/green]/[white]{ifaces_total}[/white] │ "
            f"[dim]Ports:[/dim] [red]{active_conns}[/red]/[white]{ports_count}[/white] │ "
            f"[dim]IPT:[/dim] [white]{ipt_count}[/white] │ "
            f"[dim]NFT:[/dim] [white]{nft_count}[/white] │ "
            f"[dim]F2B:[/dim] [white]{f2b_jails}[/white] jails, [red]{f2b_banned}[/red] banned"
        )

    def _populate_ports(self, table: DataTable) -> None:
        """Populate table with open ports sorted by port number."""
        def populate(t):
            ports = self._last_data.get('open_ports', [])
            if not ports:
                t.add_row("No open ports found", "", "", "", "", "")
                return

            # Filter and sort by port number
            valid_ports = [p for p in ports if 'error' not in p]
            sorted_ports = sorted(valid_ports, key=lambda x: int(x.get('port', 0)) if str(x.get('port', '')).isdigit() else 99999)

            for p in sorted_ports:
                try:
                    port = str(p.get('port', 'N/A'))
                    proto = p.get('protocol', 'N/A')
                    addr = p.get('address', 'N/A')
                    process = p.get('process', 'N/A')
                    pid = str(p.get('pid') or '-')
                    conns = p.get('connections', 0)

                    # Color by protocol
                    if proto == 'TCP':
                        proto_text = Text(proto, style="cyan")
                    elif proto == 'UDP':
                        proto_text = Text(proto, style="yellow")
                    else:
                        proto_text = Text(proto)

                    # Highlight ports: active connections = yellow, common ports = green
                    port_num = int(port) if port.isdigit() else 0
                    if conns > 0:
                        # Active port with connections - highlight yellow
                        port_text = Text(port, style="bold yellow")
                    elif port_num in [22, 80, 443, 3306, 5432, 6379, 8080]:
                        # Common/well-known ports - green
                        port_text = Text(port, style="bold green")
                    else:
                        port_text = Text(port)

                    # Connections count with color
                    if conns > 0:
                        conns_text = Text(str(conns), style="bold yellow")
                    else:
                        conns_text = Text("-", style="dim")

                    t.add_row(port_text, proto_text, addr, process, pid, conns_text)
                except Exception as e:
                    logger.debug(f"Error processing port: {e}")
                    continue

        update_table_preserving_scroll(table, populate)

    def _populate_interfaces(self, table: DataTable) -> None:
        """Populate table with network interfaces sorted: physical first, virtual last."""
        def populate(t):
            interfaces = self._last_data.get('interfaces', [])
            if not interfaces:
                t.add_row("No interfaces found", "", "", "", "")
                return

            # Sort interfaces: physical first, virtual last
            def is_virtual(name):
                return any(name.startswith(prefix) for prefix in self.VIRTUAL_PREFIXES)

            sorted_interfaces = sorted(interfaces, key=lambda x: (is_virtual(x.get('name', '')), x.get('name', '')))

            for iface in sorted_interfaces:
                try:
                    name = iface.get('name', 'N/A')
                    is_up = iface.get('is_up', False)
                    speed = iface.get('speed', 0)
                    mac = iface.get('mac', 'N/A')

                    # Get IPv4 addresses
                    addrs = [a['address'] for a in iface.get('addresses', []) if '.' in a.get('address', '')]
                    addr_str = ", ".join(addrs) if addrs else "N/A"

                    # Status with color
                    if is_up:
                        status_text = Text("UP", style="bold green")
                    else:
                        status_text = Text("DOWN", style="red")

                    # Speed formatting
                    if speed and speed > 0:
                        if speed >= 1000:
                            speed_str = f"{speed // 1000} Gbps"
                        else:
                            speed_str = f"{speed} Mbps"
                    else:
                        speed_str = "-"

                    t.add_row(name, status_text, addr_str, mac or "-", speed_str)
                except Exception as e:
                    logger.debug(f"Error processing interface: {e}")
                    continue

        update_table_preserving_scroll(table, populate)

    def _populate_firewall(self, table: DataTable) -> None:
        """Populate table with firewall rules."""
        def populate(t):
            fw = self._last_data.get('firewall', {})
            if not fw:
                t.add_row("No firewall data available")
                return

            rules = fw.get('rules', [])
            if not rules:
                t.add_row("No firewall rules")
                return

            for rule in rules:
                try:
                    # Color ACCEPT/DROP/REJECT
                    if 'ACCEPT' in rule:
                        rule_text = Text(rule, style="green")
                    elif 'DROP' in rule or 'REJECT' in rule:
                        rule_text = Text(rule, style="red")
                    else:
                        rule_text = Text(rule)
                    t.add_row(rule_text)
                except Exception as e:
                    logger.debug(f"Error processing firewall rule: {e}")
                    continue

        update_table_preserving_scroll(table, populate)

    def _populate_routes(self, table: DataTable) -> None:
        """Populate table with routing table."""
        def populate(t):
            routes = self._last_data.get('routing', [])
            if not routes:
                t.add_row("No routes found", "", "", "")
                return

            for r in routes:
                try:
                    route_str = r.get('route', '')
                    # Parse route string if possible, otherwise show raw
                    parts = route_str.split()
                    if len(parts) >= 3:
                        dest = parts[0]
                        # Try to find gateway and interface
                        gateway = "-"
                        iface = "-"
                        flags = "-"

                        for i, part in enumerate(parts):
                            if part == 'via' and i + 1 < len(parts):
                                gateway = parts[i + 1]
                            elif part == 'dev' and i + 1 < len(parts):
                                iface = parts[i + 1]

                        # Highlight default route
                        if dest == 'default':
                            dest_text = Text(dest, style="bold cyan")
                        else:
                            dest_text = Text(dest)

                        t.add_row(dest_text, gateway, iface, flags)
                    else:
                        t.add_row(route_str, "", "", "")
                except Exception as e:
                    logger.debug(f"Error processing route: {e}")
                    continue

        update_table_preserving_scroll(table, populate)

    def _format_bantime(self, seconds: int) -> str:
        """Format bantime as human readable with expiry date."""
        from datetime import datetime, timedelta

        if seconds <= 0:
            return "-"

        # Calculate expiry date (approximate - from now)
        expiry = datetime.now() + timedelta(seconds=seconds)
        expiry_str = expiry.strftime("%d.%m.%y")

        # Format duration
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
        """Populate table with fail2ban jail information - each banned IP on separate row."""
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

            # Sort Jails: OK first, then Active, then recidive, then HISTORY, then SLOW...
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

                    # Add separator row between normal jails
                    if idx > 0 and name != 'HISTORY' and 'SLOW' not in name:
                        t.add_row("", "", "", "", "", "", "", "", "")

                    # Special handling for HISTORY and SLOW DETECTOR
                    if name in ('HISTORY', 'SLOW BRUTE-FORCE DETECTOR'):
                        # 1. Separator row
                        t.add_row("", "", "", "", "", "", "", "", "")
                        
                        # 2. Section Header Row
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
                            ""  # Fail col empty
                        )
                        
                        for idx, ip_info in enumerate(banned_ips):
                            ip_str = ip_info.get('ip', '?')
                            country = ip_info.get('country', 'Unknown')
                            org = ip_info.get('org', '-')
                            if len(org) > 20: org = org[:17] + '...'
                            attempts = ip_info.get('attempts', 0)
                            
                            # For HISTORY: unban_time. For SLOW: status
                            extra_info = ip_info.get('unban_time') or ip_info.get('status', '')
                            
                            jail_origin = ip_info.get('jail', '?')
                            
                            # First column: Total count on first row, then empty
                            col1 = Text(f"Total: {total_banned}", style="blue") if idx == 0 else ""
                            
                            # Second column: Original jail name
                            jail_status_display = Text(f"[{jail_origin}]", style="blue")
                            
                            # Attempts coloring
                            attempts_text = Text(str(attempts))
                            if attempts >= 100: attempts_text.style = "bold red"
                            elif attempts >= 20: attempts_text.style = "yellow"
                            
                            # Extra info coloring for SLOW DETECTOR
                            extra_text = Text(extra_info)
                            if 'EVASION' in extra_info:
                                extra_text.style = "bold red"
                            elif 'CAUGHT' in extra_info:
                                extra_text.style = "bold yellow"

                            # Interval
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
                                ""  # Fail col empty
                            )
                        continue

                    # Standard Logic for Active Jails
                    # Status based on currently banned
                    if currently_banned > 0:
                        status_text = Text("ACTIVE", style="bold red")
                    else:
                        status_text = Text("OK", style="green")

                    # Color banned count
                    if currently_banned > 0:
                        banned_text = Text(str(currently_banned), style="bold red")
                    else:
                        banned_text = Text(str(currently_banned), style="green")

                    if not banned_ips:
                        # No banned IPs - single row for jail
                        t.add_row(
                            Text(name, style="bold"),
                            status_text,
                            "-", "-", "-", "-", "-",
                            banned_text,
                            str(filter_failures)
                        )
                    else:
                        # First row with jail info and first IP
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

                        # Additional rows for remaining IPs
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

    def _populate_iptables(self, table: DataTable) -> None:
        """Populate table with iptables rules."""
        def populate(t):
            rules = self._last_data.get('iptables', [])
            if not rules:
                t.add_row("No iptables rules found (or permission denied)", "", "", "", "", "", "")
                return

            last_chain = None
            for rule in rules:
                chain = rule.get('chain', 'UNKNOWN')
                policy = rule.get('policy', '')
                
                # Add separator/header for new chain
                if chain != last_chain:
                    if last_chain is not None:
                         t.add_row("", "", "", "", "", "", "")
                    
                    chain_text = Text(chain, style="bold cyan")
                    if policy:
                        chain_text.append(f" (policy {policy})", style="dim")
                    t.add_row(chain_text, "", "", "", "", "", "")
                    last_chain = chain

                target = rule.get('target', '')
                if target == 'ACCEPT':
                    target_text = Text(target, style="green")
                elif target in ('DROP', 'REJECT'):
                    target_text = Text(target, style="bold red")
                else:
                    target_text = Text(target)

                t.add_row(
                    "", # Chain column empty for rules
                    str(rule.get('num', '')),
                    target_text,
                    rule.get('prot', ''),
                    rule.get('source', ''),
                    rule.get('destination', ''),
                    rule.get('extra', '')
                )
        
        update_table_preserving_scroll(table, populate)

    def _populate_nftables(self, table: DataTable) -> None:
        """Populate table with nftables rules."""
        def populate(t):
            data = self._last_data.get('nftables', {})
            if not data or 'error' in data:
                error = data.get('error', 'No data')
                t.add_row(f"Error: {error}", "", "", "", "", "", "")
                return
            
            items = data.get('nftables', [])
            if not items:
                t.add_row("No nftables rules found", "", "", "", "", "", "")
                return
            
            # Sort items: F2B related first
            def is_f2b(i):
                try:
                    if 'table' in i: return 'f2b' in i['table'].get('name', '')
                    if 'chain' in i: return 'f2b' in i['chain'].get('name', '') or 'f2b' in i['chain'].get('table', '')
                    if 'set' in i: return 'f2b' in i['set'].get('name', '') or 'f2b' in i['set'].get('table', '')
                    if 'rule' in i: return 'f2b' in i['rule'].get('chain', '') or 'f2b' in i['rule'].get('table', '')
                except:
                    return False
                return False

            f2b_items = [i for i in items if is_f2b(i)]
            other_items = [i for i in items if not is_f2b(i)]
            sorted_items = f2b_items + other_items
            
            current_table = None
            
            for item in sorted_items:
                if 'table' in item:
                    fam = item['table'].get('family', '')
                    name = item['table'].get('name', '')
                    current_table = f"{fam} {name}"
                    # t.add_row(Text(f"Table: {current_table}", style="bold magenta"), "", "", "", "", "", "")
                    
                elif 'chain' in item:
                    c = item['chain']
                    name = c.get('name')
                    type_ = c.get('type', '-')
                    hook = c.get('hook', '-')
                    prio = str(c.get('prio', '-'))
                    policy = c.get('policy', '-')
                    
                    policy_style = "green" if policy == 'accept' else "red" if policy == 'drop' else "white"
                    
                    t.add_row(
                        Text(current_table or "?", style="dim"),
                        Text(name, style="bold cyan"),
                        type_,
                        hook,
                        prio,
                        Text(policy, style=policy_style),
                        ""
                    )

                elif 'set' in item:
                    s = item['set']
                    name = s.get('name', 'unknown')
                    table_name = s.get('table', 'unknown')
                    family = s.get('family', 'inet')
                    set_type = s.get('type', '-')
                    raw_elements = s.get('elem', [])
                    count = len(raw_elements)
                    
                    t.add_row(
                        Text(f"{family} {table_name}", style="dim"),
                        Text(f"SET: {name}", style="bold yellow"),
                        set_type,
                        "", # Hook
                        "", # Prio
                        "", # Policy
                        f"Elements: {count}"
                    )
                    
                elif 'rule' in item:
                    r = item['rule']
                    
                    # Try to extract verdict and main match info
                    exprs = r.get('expr', [])
                    desc_parts = []
                    
                    for e in exprs:
                        key = list(e.keys())[0]
                        val = e[key]
                        
                        if key == 'verdict':
                            v_key = list(val.keys())[0]
                            color = "green" if v_key == 'accept' else "bold red" if v_key == 'drop' else "yellow"
                            desc_parts.append(f"[{color}]{v_key.upper()}[/{color}]")
                        elif key == 'match':
                            try:
                                # Try to interpret basic matches
                                left = val.get('left', {})
                                op = val.get('op', '')
                                right = val.get('right', {})
                                
                                field = "?"
                                if 'payload' in left:
                                    field = f"{left['payload'].get('protocol', '')}.{left['payload'].get('field', '')}"
                                elif 'meta' in left:
                                    field = left['meta'].get('key', '')
                                
                                desc_parts.append(f"{field} {op} {right}")
                            except:
                                desc_parts.append("match(...)")
                        elif key == 'counter':
                             pass # Skip counters
                        else:
                             # Convert complex dict to string representation for other keys
                             desc_parts.append(key)

                    rule_text = ", ".join(desc_parts)
                    if not rule_text:
                        rule_text = str(exprs)

                    t.add_row(
                        "", 
                        "", 
                        "", 
                        "", 
                        "", 
                        "", 
                        rule_text
                    )

        update_table_preserving_scroll(table, populate)
