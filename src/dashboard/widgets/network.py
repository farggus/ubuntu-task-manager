"""Network tab widget."""

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static

from collectors import NetworkCollector
from utils.logger import get_logger
from utils.ui_helpers import update_table_preserving_scroll

logger = get_logger("network_tab")


class NetworkExtendedTab(Vertical):
    """Tab displaying detailed network information."""

    # View modes
    VIEW_PORTS = "ports"
    VIEW_INTERFACES = "interfaces"
    VIEW_FIREWALL = "firewall"
    VIEW_ROUTES = "routes"
    VIEW_IPTABLES = "iptables"
    VIEW_NFTABLES = "nftables"

    BINDINGS = [
        Binding("p", "show_ports", "Ports"),
        Binding("i", "show_interfaces", "Interfaces"),
        Binding("f", "show_firewall", "Firewall Check"),
        Binding("r", "show_routes", "Routes"),
        Binding("t", "show_iptables", "IPTables"),
        Binding("n", "show_nftables", "NFTables"),
    ]

    # Virtual interface prefixes (sorted to end)
    VIRTUAL_PREFIXES = ("br-", "veth", "docker", "virbr", "vnet", "tun", "tap", "lo")

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
        self._data_loaded = False

    def compose(self):
        with Static(id="network_header_container"):
            yield Label("[bold cyan]Loading...[/bold cyan]", id="network_header")
        yield DataTable(id="network_table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Setup table structure (no data loading)."""
        self._setup_table_columns()

    def on_show(self) -> None:
        """Load data when tab becomes visible."""
        if not self._data_loaded:
            self._data_loaded = True
            self.update_data()

    def _setup_table_columns(self) -> None:
        """Setup table columns based on current view mode."""
        try:
            table = self.query_one("#network_table", DataTable)
            table.clear(columns=True)
            table.fixed_columns = 0  # Allow all columns to be flexible

            if self._current_view == self.VIEW_PORTS:
                table.add_columns("Port", "Proto", "Address", "Process", "PID", "Conns")
            elif self._current_view == self.VIEW_INTERFACES:
                table.add_columns("Interface", "Status", "IP Address", "MAC", "Speed")
            elif self._current_view == self.VIEW_FIREWALL:
                table.add_columns("Rule")
            elif self._current_view == self.VIEW_ROUTES:
                table.add_columns("Destination", "Gateway", "Interface", "Flags")
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

    def action_show_iptables(self) -> None:
        self._switch_view(self.VIEW_IPTABLES)

    def action_show_nftables(self) -> None:
        self._switch_view(self.VIEW_NFTABLES)

    @work(exclusive=True, thread=True)
    def update_data(self) -> None:
        """Fetch data in background."""
        try:
            data = self.collector.update()
            self._last_data = data
            try:
                self.app.call_from_thread(self._update_view)
            except Exception as e:
                # Handle app shutdown case gracefully but with logging
                if "NoActiveAppError" in str(e) or "NoActiveAppError" in str(type(e)):
                    logger.debug("Skipping UI update: App is shutting down.")
                else:
                    logger.error(f"Failed to schedule UI update: {e}")
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
        interfaces = data.get("interfaces", [])
        ifaces_up = sum(1 for i in interfaces if i.get("is_up"))
        ifaces_total = len(interfaces)

        # Ports stats
        ports = data.get("open_ports", [])
        valid_ports = [p for p in ports if "error" not in p]
        ports_count = len(valid_ports)
        active_conns = sum(p.get("connections", 0) for p in valid_ports)

        # IPtables stats
        iptables_data = data.get("iptables", [])
        ipt_count = len(iptables_data) if isinstance(iptables_data, list) else 0

        # NFTables stats
        nft_data = data.get("nftables", {})
        nft_count = 0
        if isinstance(nft_data, dict) and "nftables" in nft_data:
            nft_count = sum(1 for item in nft_data["nftables"] if "rule" in item)

        # Current view indicator
        view_labels = {
            self.VIEW_PORTS: "► Ports",
            self.VIEW_INTERFACES: "► Interfaces",
            self.VIEW_FIREWALL: "► FW Check",
            self.VIEW_ROUTES: "► Routes",
            self.VIEW_IPTABLES: "► IPTables",
            self.VIEW_NFTABLES: "► NFTables",
        }
        current = f"[bold cyan]{view_labels.get(self._current_view, 'Unknown')}[/bold cyan]"

        return (
            f"{current} │ "
            f"[dim]Ifaces:[/dim] [green]{ifaces_up}[/green]/[white]{ifaces_total}[/white] │ "
            f"[dim]Ports:[/dim] [red]{active_conns}[/red]/[white]{ports_count}[/white] │ "
            f"[dim]IPT:[/dim] [white]{ipt_count}[/white] │ "
            f"[dim]NFT:[/dim] [white]{nft_count}[/white]"
        )

    def _populate_ports(self, table: DataTable) -> None:
        """Populate table with open ports sorted by port number."""

        def populate(t):
            ports = self._last_data.get("open_ports", [])
            if not ports:
                t.add_row("No open ports found", "", "", "", "", "")
                return

            # Filter and sort by port number
            valid_ports = [p for p in ports if "error" not in p]
            sorted_ports = sorted(
                valid_ports, key=lambda x: int(x.get("port", 0)) if str(x.get("port", "")).isdigit() else 99999
            )

            for p in sorted_ports:
                try:
                    port = str(p.get("port", "N/A"))
                    proto = p.get("protocol", "N/A")
                    addr = p.get("address", "N/A")
                    process = p.get("process", "N/A")
                    pid = str(p.get("pid") or "-")
                    conns = p.get("connections", 0)

                    # Color by protocol
                    if proto == "TCP":
                        proto_text = Text(proto, style="cyan")
                    elif proto == "UDP":
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
            interfaces = self._last_data.get("interfaces", [])
            if not interfaces:
                t.add_row("No interfaces found", "", "", "", "")
                return

            # Sort interfaces: physical first, virtual last
            def is_virtual(name):
                return any(name.startswith(prefix) for prefix in self.VIRTUAL_PREFIXES)

            sorted_interfaces = sorted(interfaces, key=lambda x: (is_virtual(x.get("name", "")), x.get("name", "")))

            for iface in sorted_interfaces:
                try:
                    name = iface.get("name", "N/A")
                    is_up = iface.get("is_up", False)
                    speed = iface.get("speed", 0)
                    mac = iface.get("mac", "N/A")

                    # Get IPv4 addresses
                    addrs = [a["address"] for a in iface.get("addresses", []) if "." in a.get("address", "")]
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
            fw = self._last_data.get("firewall", {})
            if not fw:
                t.add_row("No firewall data available")
                return

            rules = fw.get("rules", [])
            if not rules:
                t.add_row("No firewall rules")
                return

            for rule in rules:
                try:
                    # Color ACCEPT/DROP/REJECT
                    if "ACCEPT" in rule:
                        rule_text = Text(rule, style="green")
                    elif "DROP" in rule or "REJECT" in rule:
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
            routes = self._last_data.get("routing", [])
            if not routes:
                t.add_row("No routes found", "", "", "")
                return

            for r in routes:
                try:
                    route_str = r.get("route", "")
                    # Parse route string if possible, otherwise show raw
                    parts = route_str.split()
                    if len(parts) >= 3:
                        dest = parts[0]
                        # Try to find gateway and interface
                        gateway = "-"
                        iface = "-"
                        flags = "-"

                        for i, part in enumerate(parts):
                            if part == "via" and i + 1 < len(parts):
                                gateway = parts[i + 1]
                            elif part == "dev" and i + 1 < len(parts):
                                iface = parts[i + 1]

                        # Highlight default route
                        if dest == "default":
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

    def _populate_iptables(self, table: DataTable) -> None:
        """Populate table with iptables rules."""

        def populate(t):
            rules = self._last_data.get("iptables", [])
            if not rules:
                t.add_row("No iptables rules found (or permission denied)", "", "", "", "", "", "")
                return

            last_chain = None
            for rule in rules:
                chain = rule.get("chain", "UNKNOWN")
                policy = rule.get("policy", "")

                # Add separator/header for new chain
                if chain != last_chain:
                    if last_chain is not None:
                        t.add_row("", "", "", "", "", "", "")

                    chain_text = Text(chain, style="bold cyan")
                    if policy:
                        chain_text.append(f" (policy {policy})", style="dim")
                    t.add_row(chain_text, "", "", "", "", "", "")
                    last_chain = chain

                target = rule.get("target", "")
                if target == "ACCEPT":
                    target_text = Text(target, style="green")
                elif target in ("DROP", "REJECT"):
                    target_text = Text(target, style="bold red")
                else:
                    target_text = Text(target)

                t.add_row(
                    "",  # Chain column empty for rules
                    str(rule.get("num", "")),
                    target_text,
                    rule.get("prot", ""),
                    rule.get("source", ""),
                    rule.get("destination", ""),
                    rule.get("extra", ""),
                )

        update_table_preserving_scroll(table, populate)

    def _populate_nftables(self, table: DataTable) -> None:
        """Populate table with nftables rules."""

        def populate(t):
            data = self._last_data.get("nftables", {})
            if not data or "error" in data:
                error = data.get("error", "No data")
                t.add_row(f"Error: {error}", "", "", "", "", "", "")
                return

            items = data.get("nftables", [])
            if not items:
                t.add_row("No nftables rules found", "", "", "", "", "", "")
                return

            # Sort items: F2B related first
            def is_f2b(i):
                try:
                    if "table" in i:
                        return "f2b" in i["table"].get("name", "")
                    if "chain" in i:
                        return "f2b" in i["chain"].get("name", "") or "f2b" in i["chain"].get("table", "")
                    if "set" in i:
                        return "f2b" in i["set"].get("name", "") or "f2b" in i["set"].get("table", "")
                    if "rule" in i:
                        return "f2b" in i["rule"].get("chain", "") or "f2b" in i["rule"].get("table", "")
                except Exception:
                    return False
                return False

            f2b_items = [i for i in items if is_f2b(i)]
            other_items = [i for i in items if not is_f2b(i)]
            sorted_items = f2b_items + other_items

            current_table = None

            for item in sorted_items:
                if "table" in item:
                    fam = item["table"].get("family", "")
                    name = item["table"].get("name", "")
                    current_table = f"{fam} {name}"

                elif "chain" in item:
                    c = item["chain"]
                    name = c.get("name")
                    type_ = c.get("type", "-")
                    hook = c.get("hook", "-")
                    prio = str(c.get("prio", "-"))
                    policy = c.get("policy", "-")

                    policy_style = "green" if policy == "accept" else "red" if policy == "drop" else "white"

                    t.add_row(
                        Text(current_table or "?", style="dim"),
                        Text(name, style="bold cyan"),
                        type_,
                        hook,
                        prio,
                        Text(policy, style=policy_style),
                        "",
                    )

                elif "set" in item:
                    s = item["set"]
                    name = s.get("name", "unknown")
                    table_name = s.get("table", "unknown")
                    family = s.get("family", "inet")
                    set_type = s.get("type", "-")
                    raw_elements = s.get("elem", [])
                    count = len(raw_elements)

                    t.add_row(
                        Text(f"{family} {table_name}", style="dim"),
                        Text(f"SET: {name}", style="bold yellow"),
                        set_type,
                        "",  # Hook
                        "",  # Prio
                        "",  # Policy
                        f"Elements: {count}",
                    )

                elif "rule" in item:
                    r = item["rule"]

                    # Try to extract verdict and main match info
                    exprs = r.get("expr", [])
                    desc_parts = []

                    for e in exprs:
                        key = list(e.keys())[0]
                        val = e[key]

                        if key == "verdict":
                            v_key = list(val.keys())[0]
                            color = "green" if v_key == "accept" else "bold red" if v_key == "drop" else "yellow"
                            desc_parts.append(f"[{color}]{v_key.upper()}[/{color}]")
                        elif key == "match":
                            try:
                                # Try to interpret basic matches
                                left = val.get("left", {})
                                op = val.get("op", "")
                                right = val.get("right", {})

                                field = "?"
                                if "payload" in left:
                                    field = f"{left['payload'].get('protocol', '')}.{left['payload'].get('field', '')}"
                                elif "meta" in left:
                                    field = left["meta"].get("key", "")

                                desc_parts.append(f"{field} {op} {right}")
                            except Exception:
                                desc_parts.append("match(...)")
                        elif key == "counter":
                            pass  # Skip counters
                        else:
                            # Convert complex dict to string representation for other keys
                            desc_parts.append(key)

                    rule_text = ", ".join(desc_parts)
                    if not rule_text:
                        rule_text = str(exprs)

                    t.add_row("", "", "", "", "", "", rule_text)

        update_table_preserving_scroll(table, populate)
