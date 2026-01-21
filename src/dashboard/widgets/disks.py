"""Disk usage tab widget with lsblk-style hierarchy display."""

from textual import work
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static
from textual.binding import Binding
from rich.text import Text
from typing import Dict, Any, List

from collectors import SystemCollector
from utils.logger import get_logger
from utils.ui_helpers import update_table_preserving_scroll, bytes_to_human_readable
from .smart_modal import SmartModal
from .fstab_modal import FstabModal

logger = get_logger("disks_tab")

# Color scheme by disk type
DISK_TYPE_COLORS = {
    'nvme': 'cyan',
    'ssd': 'green',
    'hdd': 'blue',
    'lvm': 'magenta',
    'part': 'white',
}

DISK_TYPE_LABELS = {
    'nvme': 'NVMe',
    'ssd': 'SSD',
    'hdd': 'HDD',
    'lvm': 'lvm',
    'part': 'part',
}

# Color scheme for filesystem types
FSTYPE_COLORS = {
    'ext4': 'green',
    'ext3': 'green',
    'ext2': 'green',
    'xfs': 'cyan',
    'btrfs': 'magenta',
    'zfs': 'magenta',
    'ntfs': 'yellow',
    'vfat': 'yellow',
    'fat32': 'yellow',
    'exfat': 'yellow',
    'swap': 'red',
    'LVM2_member': 'blue',
    'crypto_LUKS': 'red',
}


class DisksTab(Vertical):
    """Tab displaying disk hierarchy like lsblk."""

    BINDINGS = [
        Binding("s", "view_smart", "SMART"),
        Binding("d", "view_disk_details", "Details"),
        Binding("f", "edit_fstab", "fstab"),
        Binding("c", "copy_uuid", "Copy UUID"),
        Binding("m", "mount_unmount", "Mount"),
        Binding("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    DisksTab {
        height: 1fr;
        padding: 0;
    }
    #disks_header_container {
        height: 4;
        margin: 0;
        padding: 0 1;
        border: round $success;
        margin-bottom: 0;
    }
    #disks_header_line1 {
        margin: 0;
        padding: 0;
        width: 100%;
    }
    #disks_header_line2 {
        margin: 0;
        padding: 0;
        width: 100%;
    }
    #disks_table {
        height: 1fr;
        margin: 0;
        padding: 0;
    }
    """

    def __init__(self, collector: SystemCollector):
        super().__init__()
        self.collector = collector
        self._hierarchy = []  # Store for SMART lookup
        self._update_timer = None  # Reference to update timer

    def compose(self):
        with Static(id="disks_header_container"):
            yield Label("[dim]Loading...[/dim]", id="disks_header_line1")
            yield Label("", id="disks_header_line2")
        yield DataTable(id="disks_table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Setup table and start updates."""
        table = self.query_one(DataTable)
        table.add_columns(
            "Name",
            "Type",
            "Conn",
            "Temp",
            "SMART",
            "I/O",
            "Size",
            "Used",
            "Free",
            "Use%",
            "Bar",
            "Mountpoint",
            "UUID",
        )
        self.update_data()
        self._start_update_timer()

    def _start_update_timer(self) -> None:
        """Start or restart the update timer with current interval."""
        if self._update_timer:
            self._update_timer.stop()
        interval_ms = getattr(self.app, 'update_interval', 2000)
        self._update_timer = self.set_interval(interval_ms / 1000, self.update_data)

    def set_update_interval(self, interval_ms: int) -> None:
        """Update the refresh interval."""
        self._start_update_timer()

    @work(exclusive=True, thread=True)
    def update_data(self) -> None:
        """Update data in background."""
        data = self.collector.update()
        if data:
            disk_data = data.get('disk', {})
            self.app.call_from_thread(self.update_table, disk_data)

    def update_table(self, data: Dict[str, Any]) -> None:
        """Update table with hierarchical disk data."""
        if not data:
            return
        table = self.query_one(DataTable)

        hierarchy = data.get('hierarchy', [])
        self._hierarchy = hierarchy  # Store for SMART lookup

        # Update header with stats
        self._update_header(hierarchy)

        # Get I/O stats
        io_stats = data.get('io', {}).get('per_disk', {})

        def populate(t):
            for disk_idx, disk in enumerate(hierarchy):
                disk_name = disk.get('name', '')
                disk_io = io_stats.get(disk_name, {})
                self._add_disk_row(t, disk, disk_io)
                children = disk.get('children', [])
                for i, part in enumerate(children):
                    is_last_part = (i == len(children) - 1)
                    self._add_child_row(t, part, level=1, is_last=is_last_part, parent_type=disk.get('type'))
                    # LVM children of partition
                    lvm_children = part.get('children', [])
                    for j, lvm in enumerate(lvm_children):
                        is_last_lvm = (j == len(lvm_children) - 1)
                        self._add_child_row(t, lvm, level=2, is_last=is_last_lvm, parent_type='lvm')

                # Add empty separator row after each disk (except the last one)
                if disk_idx < len(hierarchy) - 1:
                    t.add_row(*[Text("") for _ in range(13)])

        update_table_preserving_scroll(table, populate)

    def _update_header(self, hierarchy: List[Dict[str, Any]]) -> None:
        """Update header with disk statistics."""
        # Count disks by type and collect stats
        type_counts = {'nvme': 0, 'ssd': 0, 'hdd': 0}
        usb_by_type = {'nvme': 0, 'ssd': 0, 'hdd': 0}  # USB disks per type
        total_size = 0
        total_used = 0
        smart_ok = 0
        smart_fail = 0
        warnings = []  # High usage warnings
        temperatures = []  # (temp, disk_name)
        bind_mounts = 0

        for disk in hierarchy:
            disk_type = disk.get('type', 'hdd')
            if disk_type in type_counts:
                type_counts[disk_type] += 1
            if disk.get('is_usb') and disk_type in usb_by_type:
                usb_by_type[disk_type] += 1
            total_size += disk.get('size', 0)

            # SMART status
            smart_status = disk.get('smart_status', 'N/A')
            if smart_status == 'OK':
                smart_ok += 1
            elif smart_status == 'FAIL':
                smart_fail += 1

            # Temperature
            temp = disk.get('temperature')
            if temp is not None:
                temperatures.append((temp, disk.get('name', '')))

            # Sum used space from disk usage (aggregated from mounted children)
            usage = disk.get('usage')
            if usage:
                total_used += usage.get('used', 0)

            # Check children for high usage warnings and bind mounts
            for part in disk.get('children', []):
                part_usage = part.get('usage')
                if part_usage and part_usage.get('percent', 0) >= 90:
                    warnings.append(f"{part.get('name')} {part_usage['percent']:.0f}%")
                # Count bind mounts
                mountpoints = part.get('mountpoints', [])
                if len(mountpoints) > 1:
                    bind_mounts += len(mountpoints) - 1
                # Also check LVM children
                for lvm in part.get('children', []):
                    lvm_usage = lvm.get('usage')
                    if lvm_usage and lvm_usage.get('percent', 0) >= 90:
                        warnings.append(f"{lvm.get('name')} {lvm_usage['percent']:.0f}%")
                    lvm_mounts = lvm.get('mountpoints', [])
                    if len(lvm_mounts) > 1:
                        bind_mounts += len(lvm_mounts) - 1

        total_disks = sum(type_counts.values())

        # Build type breakdown string with USB count per type
        type_parts = []
        if type_counts['nvme'] > 0:
            usb_suffix = f" [yellow]({usb_by_type['nvme']} USB)[/yellow]" if usb_by_type['nvme'] > 0 else ""
            type_parts.append(f"[cyan]{type_counts['nvme']} NVMe[/cyan]{usb_suffix}")
        if type_counts['ssd'] > 0:
            usb_suffix = f" [yellow]({usb_by_type['ssd']} USB)[/yellow]" if usb_by_type['ssd'] > 0 else ""
            type_parts.append(f"[green]{type_counts['ssd']} SSD[/green]{usb_suffix}")
        if type_counts['hdd'] > 0:
            usb_suffix = f" [yellow]({usb_by_type['hdd']} USB)[/yellow]" if usb_by_type['hdd'] > 0 else ""
            type_parts.append(f"[blue]{type_counts['hdd']} HDD[/blue]{usb_suffix}")

        type_str = ", ".join(type_parts) if type_parts else "none"

        # SMART status string
        if smart_fail > 0:
            smart_str = f"[bold red]SMART: {smart_fail} FAIL ❌[/bold red]"
        elif smart_ok > 0:
            smart_str = f"[green]SMART: {smart_ok} OK ✅[/green]"
        else:
            smart_str = "[dim]SMART: N/A[/dim]"

        # Temperature string
        if temperatures:
            temps_sorted = sorted(temperatures, key=lambda x: x[0])
            min_temp = temps_sorted[0][0]
            max_temp, hottest_disk = temps_sorted[-1]

            if max_temp >= 50:
                # Hot disk warning
                temp_str = f"[bold red]Hot: {hottest_disk} {max_temp}°C 🔥[/bold red]"
            elif len(temperatures) > 1:
                temp_str = f"[dim]Temp:[/dim] {min_temp}-{max_temp}°C"
            else:
                temp_str = f"[dim]Temp:[/dim] {max_temp}°C"
        else:
            temp_str = ""

        # Line 1: disk count, types, SMART, and temperature
        line1 = f"[bold]{total_disks} disks:[/bold] {type_str} │ {smart_str}"
        if temp_str:
            line1 += f" │ {temp_str}"

        # Line 2: total / used + warnings + bind mounts
        total_str = bytes_to_human_readable(total_size)
        used_str = bytes_to_human_readable(total_used)
        percent = (total_used / total_size * 100) if total_size > 0 else 0

        # Color percent based on usage
        if percent > 90:
            percent_style = "bold red"
        elif percent > 70:
            percent_style = "yellow"
        else:
            percent_style = "green"

        line2 = f"Total: [bold]{total_str}[/bold] │ Used: [bold]{used_str}[/bold] ([{percent_style}]{percent:.1f}%[/{percent_style}])"

        # Add warnings if any
        if warnings:
            warn_str = ", ".join(warnings[:2])  # Limit to 2 warnings
            if len(warnings) > 2:
                warn_str += f" +{len(warnings) - 2}"
            line2 += f" │ [bold red]⛔ {warn_str}[/bold red]"

        # Add bind mounts count
        if bind_mounts > 0:
            line2 += f" │ [yellow]{bind_mounts} bind mount{'s' if bind_mounts > 1 else ''}[/yellow]"

        # Update labels (line2 first - total/used, line1 second - disk types)
        self.query_one("#disks_header_line1", Label).update(line2)
        self.query_one("#disks_header_line2", Label).update(line1)

    def _add_disk_row(self, table, disk: Dict[str, Any], io_data: Dict[str, Any] = None) -> None:
        """Add a physical disk row."""
        name = disk.get('name', '')
        disk_type = disk.get('type', 'hdd')
        model = disk.get('model', '')
        transport = disk.get('transport', '')
        size = disk.get('size', 0)
        temp = disk.get('temperature')
        smart_status = disk.get('smart_status', 'N/A')
        usage = disk.get('usage')
        io_data = io_data or {}

        type_color = DISK_TYPE_COLORS.get(disk_type, 'white')
        type_label = DISK_TYPE_LABELS.get(disk_type, disk_type.upper())

        # Check for problems (SMART fail or high temp)
        is_problem = smart_status == 'FAIL' or (temp is not None and temp >= 50)

        # Name with model (blink if problematic)
        name_text = Text()
        name_style = f"bold {type_color}"
        if is_problem:
            name_style = "bold red blink"
        name_text.append(name, style=name_style)
        if model:
            name_text.append(" [", style="dim")
            name_text.append(model, style="dim")
            name_text.append("]", style="dim")

        # Type
        type_text = Text(type_label, style=f"bold {type_color}")

        # Connection interface
        conn_colors = {'usb': 'yellow', 'sata': 'white', 'nvme': 'cyan', 'ata': 'white'}
        conn_label = transport.upper() if transport else "-"
        conn_color = conn_colors.get(transport, 'dim')
        conn_text = Text(conn_label, style=conn_color)

        # Temperature
        if temp is not None:
            temp_color = "green"
            if temp >= 50:
                temp_color = "bold red"
            elif temp >= 40:
                temp_color = "yellow"
            temp_text = Text(f"{temp}°C", style=temp_color)
        else:
            temp_text = Text("-", style="dim")

        # SMART
        if smart_status == 'OK':
            smart_text = Text("✅", style="bold green")
        elif smart_status == 'FAIL':
            smart_text = Text("❌", style="bold red blink")
        else:
            smart_text = Text("-", style="dim")

        # I/O rate
        read_rate = io_data.get('read_rate', 0)
        write_rate = io_data.get('write_rate', 0)
        if read_rate > 0 or write_rate > 0:
            # Format as compact string: R:1.2M W:500K
            def fmt_rate(r):
                if r >= 1024 * 1024:
                    return f"{r / (1024 * 1024):.1f}M"
                elif r >= 1024:
                    return f"{r / 1024:.0f}K"
                elif r > 0:
                    return f"{r:.0f}B"
                return "0"
            io_text = Text()
            io_text.append(f"R:{fmt_rate(read_rate)}", style="green")
            io_text.append(" ", style="dim")
            io_text.append(f"W:{fmt_rate(write_rate)}", style="yellow")
        else:
            io_text = Text("-", style="dim")

        # Size
        size_text = Text(bytes_to_human_readable(size), style=f"bold {type_color}")

        # Usage stats for disk (aggregated from children)
        if usage:
            used = usage.get('used', 0)
            free = usage.get('free', 0)
            percent = usage.get('percent', 0)

            used_text = Text(bytes_to_human_readable(used), style=f"bold {type_color}")
            free_text = Text(bytes_to_human_readable(free), style=f"bold {type_color}")
            percent_text = Text(f"{percent:.1f}%", style=f"bold {type_color}")

            # Bar
            bar_length = 10
            filled = int(bar_length * (percent / 100))
            bar = "█" * filled + "░" * (bar_length - filled)

            bar_color = type_color
            if percent > 90:
                bar_color = "bold red"
            elif percent > 70:
                bar_color = "yellow"
            bar_text = Text(bar, style=bar_color)
        else:
            used_text = Text("-", style="dim")
            free_text = Text("-", style="dim")
            percent_text = Text("-", style="dim")
            bar_text = Text("░░░░░░░░░░", style="dim")

        table.add_row(
            name_text,
            type_text,
            conn_text,
            temp_text,
            smart_text,
            io_text,
            size_text,
            used_text,
            free_text,
            percent_text,
            bar_text,
            Text("", style="dim"),  # No mountpoint for disk
            Text("", style="dim"),  # No UUID for disk
        )

    def _add_child_row(self, table, node: Dict[str, Any], level: int, is_last: bool, parent_type: str) -> None:
        """Add a partition or LVM child row with tree indentation."""
        name = node.get('name', '')
        node_type = node.get('node_type', 'part')
        size = node.get('size', 0)
        mountpoints = node.get('mountpoints', [])
        fstype = node.get('fstype', '')
        uuid = node.get('uuid', '')
        usage = node.get('usage')

        # Tree prefix
        if level == 1:
            prefix = "└─" if is_last else "├─"
        else:
            prefix = "  └─" if is_last else "  ├─"

        # Determine color based on node type
        if node_type == 'lvm':
            type_color = DISK_TYPE_COLORS['lvm']
            type_label = 'lvm'
        else:
            type_color = 'white'
            type_label = 'part'

        has_mount = len(mountpoints) > 0
        name_text = Text(f"{prefix}{name}", style="dim" if not has_mount else "")

        # Type (part/lvm or fstype if available) with color coding
        if fstype:
            fstype_color = FSTYPE_COLORS.get(fstype, 'white')
            type_text = Text(fstype, style=fstype_color)
        else:
            type_text = Text(type_label, style=f"{type_color}")

        # Size
        size_text = Text(bytes_to_human_readable(size), style="")

        # Usage info
        if usage:
            used = usage.get('used', 0)
            free = usage.get('free', 0)
            percent = usage.get('percent', 0)

            used_text = Text(bytes_to_human_readable(used), style="")
            free_text = Text(bytes_to_human_readable(free), style="")
            percent_text = Text(f"{percent:.1f}%", style="")

            # Bar
            bar_length = 10
            filled = int(bar_length * (percent / 100))
            bar = "█" * filled + "░" * (bar_length - filled)

            bar_color = "green"
            if percent > 90:
                bar_color = "bold red"
            elif percent > 70:
                bar_color = "yellow"
            bar_text = Text(bar, style=bar_color)
        else:
            used_text = Text("-", style="dim")
            free_text = Text("-", style="dim")
            percent_text = Text("-", style="dim")
            bar_text = Text("░░░░░░░░░░", style="dim")

        # Mountpoint(s) - show all with different colors
        mount_colors = ['white', 'yellow', 'cyan', 'magenta']
        if len(mountpoints) > 1:
            mount_text = Text()
            for i, mp in enumerate(mountpoints):
                if i > 0:
                    mount_text.append(" ", style="dim")
                color = mount_colors[i % len(mount_colors)]
                mount_text.append(mp, style=color)
        elif mountpoints:
            mount_text = Text(mountpoints[0], style="")
        else:
            mount_text = Text("-", style="dim")

        # UUID
        uuid_text = Text(uuid if uuid else "-", style="dim")

        table.add_row(
            name_text,
            type_text,
            Text("", style="dim"),  # No conn for partitions
            Text("", style="dim"),  # No temp for partitions
            Text("", style="dim"),  # No SMART for partitions
            Text("", style="dim"),  # No I/O for partitions
            size_text,
            used_text,
            free_text,
            percent_text,
            bar_text,
            mount_text,
            uuid_text,
        )

    def action_view_smart(self) -> None:
        """Show SMART report for the selected physical disk."""
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            self.notify("No disk selected.", severity="warning")
            return

        try:
            selected_row_cells = table.get_row_at(table.cursor_row)
            name_text = str(selected_row_cells[0]).strip()

            # Remove tree prefixes and model info
            name_clean = name_text.replace("└─", "").replace("├─", "").strip()
            if "[" in name_clean:
                name_clean = name_clean.split("[")[0].strip()

            # Find disk in hierarchy
            target_disk = None
            for disk in self._hierarchy:
                if disk.get('name') == name_clean:
                    target_disk = disk.get('full_path')
                    break
                # Check if it's a partition - find parent disk
                for part in disk.get('children', []):
                    if part.get('name') == name_clean:
                        target_disk = disk.get('full_path')
                        break
                    for lvm in part.get('children', []):
                        if lvm.get('name') == name_clean:
                            target_disk = disk.get('full_path')
                            break

            if target_disk:
                self.app.push_screen(SmartModal(disk_device=target_disk, name=name_clean))
            else:
                self.notify("Could not determine disk device.", severity="error")

        except Exception as e:
            logger.error(f"Error in action_view_smart: {e}")
            self.notify(f"Error: {e}", severity="error")

    def action_edit_fstab(self) -> None:
        """Open /etc/fstab editor modal."""
        self.app.push_screen(FstabModal())

    def action_view_disk_details(self) -> None:
        """Show detailed disk information modal."""
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            self.notify("No disk selected.", severity="warning")
            return

        try:
            selected_row_cells = table.get_row_at(table.cursor_row)
            name_text = str(selected_row_cells[0]).strip()

            # Remove tree prefixes and model info
            name_clean = name_text.replace("└─", "").replace("├─", "").strip()
            if "[" in name_clean:
                name_clean = name_clean.split("[")[0].strip()

            # Find disk in hierarchy
            target_disk = None
            target_part = None
            for disk in self._hierarchy:
                if disk.get('name') == name_clean:
                    target_disk = disk
                    break
                for part in disk.get('children', []):
                    if part.get('name') == name_clean:
                        target_disk = disk
                        target_part = part
                        break
                    for lvm in part.get('children', []):
                        if lvm.get('name') == name_clean:
                            target_disk = disk
                            target_part = lvm
                            break

            if target_disk:
                from .disk_details_modal import DiskDetailsModal
                self.app.push_screen(DiskDetailsModal(disk=target_disk, partition=target_part))
            else:
                self.notify("Could not find disk info.", severity="error")

        except Exception as e:
            logger.error(f"Error in action_view_disk_details: {e}")
            self.notify(f"Error: {e}", severity="error")

    def action_copy_uuid(self) -> None:
        """Copy UUID of selected partition to clipboard."""
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            self.notify("No partition selected.", severity="warning")
            return

        try:
            selected_row_cells = table.get_row_at(table.cursor_row)
            # UUID is the last column (index 12)
            uuid_text = str(selected_row_cells[12]).strip()

            if uuid_text and uuid_text != "-":
                # Use Textual's built-in copy_to_clipboard (uses OSC 52)
                self.app.copy_to_clipboard(uuid_text)
                self.notify(f"Copied: {uuid_text}", severity="information")
            else:
                self.notify("No UUID for this item.", severity="warning")

        except Exception as e:
            logger.error(f"Error in action_copy_uuid: {e}")
            self.notify(f"Error: {e}", severity="error")

    def action_mount_unmount(self) -> None:
        """Mount or unmount selected partition."""
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            self.notify("No partition selected.", severity="warning")
            return

        try:
            selected_row_cells = table.get_row_at(table.cursor_row)
            name_text = str(selected_row_cells[0]).strip()

            # Remove tree prefixes
            name_clean = name_text.replace("└─", "").replace("├─", "").strip()
            if "[" in name_clean:
                name_clean = name_clean.split("[")[0].strip()

            # Find partition in hierarchy
            target_part = None
            for disk in self._hierarchy:
                if disk.get('name') == name_clean:
                    self.notify("Cannot mount/unmount a physical disk.", severity="warning")
                    return
                for part in disk.get('children', []):
                    if part.get('name') == name_clean:
                        target_part = part
                        break
                    for lvm in part.get('children', []):
                        if lvm.get('name') == name_clean:
                            target_part = lvm
                            break

            if target_part:
                mountpoint = target_part.get('mountpoint', '')
                device = target_part.get('full_path', '')

                if mountpoint:
                    # Unmount
                    from .mount_modal import MountModal
                    self.app.push_screen(MountModal(device=device, mountpoint=mountpoint, action='unmount'))
                else:
                    # Mount
                    from .mount_modal import MountModal
                    self.app.push_screen(MountModal(device=device, mountpoint='', action='mount'))
            else:
                self.notify("Could not find partition.", severity="error")

        except Exception as e:
            logger.error(f"Error in action_mount_unmount: {e}")
            self.notify(f"Error: {e}", severity="error")

    def action_refresh(self) -> None:
        """Force refresh disk data."""
        self.notify("Refreshing disk data...", severity="information")
        self.update_data()
