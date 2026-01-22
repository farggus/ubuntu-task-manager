"""Network tab widget."""

from textual import work
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static
from textual.binding import Binding
from rich.text import Text
from typing import Dict, Any

from collectors import NetworkCollector
from utils.ui_helpers import update_table_preserving_scroll
from utils.logger import get_logger

logger = get_logger("network_tab")


class NetworkExtendedTab(Vertical):
    """Tab displaying detailed network information."""

    # View modes
    VIEW_PORTS = 'ports'
    VIEW_INTERFACES = 'interfaces'
    VIEW_FIREWALL = 'firewall'
    VIEW_ROUTES = 'routes'
    VIEW_FAIL2BAN = 'fail2ban'

    BINDINGS = [
        Binding("p", "show_ports", "Ports"),
        Binding("i", "show_interfaces", "Interfaces"),
        Binding("f", "show_firewall", "Firewall"),
        Binding("r", "show_routes", "Routes"),
        Binding("b", "show_fail2ban", "Fail2ban"),
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
        ports_count = len([p for p in ports if 'error' not in p])

        # Firewall stats
        fw = data.get('firewall', {})
        fw_type = fw.get('type', 'none') if fw else 'none'
        fw_status = fw.get('status', 'unknown') if fw else 'N/A'
        fw_rules = len(fw.get('rules', [])) if fw else 0

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
            self.VIEW_FIREWALL: '► Firewall',
            self.VIEW_ROUTES: '► Routes',
            self.VIEW_FAIL2BAN: '► Fail2ban',
        }
        current = f"[bold cyan]{view_labels[self._current_view]}[/bold cyan]"

        return (
            f"{current} │ "
            f"[dim]Ifaces:[/dim] [green]{ifaces_up}[/green]/[white]{ifaces_total}[/white] │ "
            f"[dim]Ports:[/dim] [white]{ports_count}[/white] │ "
            f"[dim]FW:[/dim] {fw_status_str} │ "
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

            # Sort Jails: OK first, then Active, then recidive, then HISTORY
            def sort_jails(j):
                name = j.get('name', '')
                banned = j.get('currently_banned', 0)
                
                if name == 'HISTORY':
                    return 3
                if name == 'recidive':
                    return 2
                if banned > 0:
                    return 1
                return 0

            jails.sort(key=sort_jails)

            for jail in jails:
                try:
                    name = jail.get('name', 'N/A')
                    currently_banned = jail.get('currently_banned', 0)
                    total_banned = jail.get('total_banned', 0)
                    filter_failures = jail.get('filter_failures', 0)
                    banned_ips = jail.get('banned_ips', [])

                    # Special handling for HISTORY
                    if name == 'HISTORY':
                        # 1. Separator row
                        t.add_row("", "", "", "", "", "", "", "", "")
                        
                        # 2. Section Header Row (acting as custom headers for this section)
                        t.add_row(
                            Text("HISTORY", style="bold blue"),
                            Text("Jail", style="bold"),
                            Text("Banned IP", style="bold"),
                            Text("Country", style="bold"),
                            Text("Org", style="bold"),
                            Text("Attempts", style="bold"),
                            Text("Unbanned:", style="bold"),
                            "", "" # Banned and Fail columns empty
                        )
                        
                        for idx, ip_info in enumerate(banned_ips):
                            ip_str = ip_info.get('ip', '?')
                            country = ip_info.get('country', 'Unknown')
                            org = ip_info.get('org', '-')
                            if len(org) > 20: org = org[:17] + '...'
                            attempts = ip_info.get('attempts', 0)
                            unban_time = ip_info.get('unban_time', '')
                            jail_origin = ip_info.get('jail', '?')
                            
                            # First column: Total count on first row, then empty
                            col1 = Text(f"Total: {total_banned}", style="blue") if idx == 0 else ""
                            
                            # Second column: Original jail name
                            jail_status_display = Text(f"[{jail_origin}]", style="blue")
                            
                            # Attempts coloring
                            attempts_text = Text(str(attempts))
                            if attempts >= 100: attempts_text.style = "bold red"
                            elif attempts >= 20: attempts_text.style = "yellow"

                            t.add_row(
                                col1,
                                jail_status_display,
                                Text(ip_str, style="red"),
                                country,
                                org,
                                attempts_text,
                                unban_time, # Displays in "Ban For" column
                                "", # Banned col empty
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
