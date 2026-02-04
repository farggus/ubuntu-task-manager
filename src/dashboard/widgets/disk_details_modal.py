"""Disk details modal showing extended information."""

import json
import os
import subprocess
from typing import Any, Dict, Optional

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from utils.binaries import LSBLK, SMARTCTL, SUDO
from utils.logger import get_logger

logger = get_logger("disk_details_modal")


class DiskDetailsModal(ModalScreen):
    """Modal screen showing detailed disk information."""

    DEFAULT_CSS = """
    DiskDetailsModal {
        align: center middle;
    }
    #disk_details_container {
        width: 90;
        height: auto;
        max-height: 40;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #disk_details_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #disk_details_content {
        height: auto;
        max-height: 30;
        overflow-y: auto;
    }
    #disk_details_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    #disk_details_buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def __init__(self, disk: Dict[str, Any], partition: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.disk = disk
        self.partition = partition

    def compose(self) -> ComposeResult:
        with Vertical(id="disk_details_container"):
            yield Label("Disk Details", id="disk_details_title")
            yield Static(id="disk_details_content")
            with Horizontal(id="disk_details_buttons"):
                yield Button("Close", id="close_btn", variant="primary")

    def on_mount(self) -> None:
        """Load and display disk details."""
        content = self._build_content()
        self.query_one("#disk_details_content", Static).update(content)

    def _build_content(self) -> Group:
        """Build the content for the modal."""
        elements = []

        # Basic disk info
        disk_table = Table(show_header=False, box=None, padding=(0, 1))
        disk_table.add_column("Property", style="cyan")
        disk_table.add_column("Value", style="white")

        disk_table.add_row("Device", self.disk.get("full_path", "N/A"))
        disk_table.add_row("Model", self.disk.get("model", "N/A") or "N/A")
        disk_table.add_row("Vendor", self.disk.get("vendor", "N/A") or "N/A")
        disk_table.add_row("Serial", self.disk.get("serial", "N/A") or "N/A")
        disk_table.add_row("Type", self.disk.get("type", "N/A").upper())
        disk_table.add_row("Transport", self.disk.get("transport", "N/A").upper() or "N/A")
        disk_table.add_row("Size", self._format_size(self.disk.get("size", 0)))

        elements.append(Panel(disk_table, title="[bold]Disk Information[/bold]", border_style="blue"))

        # Get extended SMART info
        smart_info = self._get_extended_smart_info()
        if smart_info:
            smart_table = Table(show_header=False, box=None, padding=(0, 1))
            smart_table.add_column("Property", style="cyan")
            smart_table.add_column("Value", style="white")

            smart_table.add_row("SMART Status", smart_info.get("status", "N/A"))
            smart_table.add_row(
                "Temperature", f"{smart_info.get('temperature', 'N/A')}°C" if smart_info.get("temperature") else "N/A"
            )

            if smart_info.get("power_on_hours") is not None:
                hours = smart_info["power_on_hours"]
                days = hours // 24
                smart_table.add_row("Power-On Hours", f"{hours:,} hrs ({days:,} days)")

            if smart_info.get("power_cycle_count") is not None:
                smart_table.add_row("Power Cycles", f"{smart_info['power_cycle_count']:,}")

            if smart_info.get("reallocated_sectors") is not None:
                val = smart_info["reallocated_sectors"]
                style = "red bold" if val > 0 else "green"
                smart_table.add_row("Reallocated Sectors", Text(str(val), style=style))

            if smart_info.get("pending_sectors") is not None:
                val = smart_info["pending_sectors"]
                style = "red bold" if val > 0 else "green"
                smart_table.add_row("Pending Sectors", Text(str(val), style=style))

            if smart_info.get("wear_level") is not None:
                val = smart_info["wear_level"]
                style = "red bold" if val < 20 else ("yellow" if val < 50 else "green")
                smart_table.add_row("SSD Wear Level", Text(f"{val}%", style=style))

            elements.append(Panel(smart_table, title="[bold]SMART Information[/bold]", border_style="green"))

        # Partition info if selected
        if self.partition:
            part_table = Table(show_header=False, box=None, padding=(0, 1))
            part_table.add_column("Property", style="cyan")
            part_table.add_column("Value", style="white")

            part_table.add_row("Device", self.partition.get("full_path", "N/A"))
            part_table.add_row("Type", self.partition.get("node_type", "N/A"))
            part_table.add_row("Filesystem", self.partition.get("fstype", "N/A") or "N/A")
            part_table.add_row("UUID", self.partition.get("uuid", "N/A") or "N/A")
            part_table.add_row("Size", self._format_size(self.partition.get("size", 0)))

            mountpoints = self.partition.get("mountpoints", [])
            if mountpoints:
                part_table.add_row("Mountpoint(s)", ", ".join(mountpoints))
            else:
                part_table.add_row("Mountpoint", "Not mounted")

            # Get label
            label = self._get_partition_label()
            part_table.add_row("Label", label or "N/A")

            elements.append(Panel(part_table, title="[bold]Partition Information[/bold]", border_style="magenta"))

        # Partition scheme
        scheme = self._get_partition_scheme()
        if scheme:
            elements.append(Text(f"Partition Scheme: {scheme}", style="dim"))

        return Group(*elements)

    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    def _get_extended_smart_info(self) -> Dict[str, Any]:
        """Get extended SMART information."""
        device = self.disk.get("full_path", "")
        if not device:
            return {}

        try:
            cmd = [SMARTCTL, "-A", "-H", "-j", device]
            if os.geteuid() != 0:
                cmd = [SUDO] + cmd

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if not result.stdout:
                return {}

            data = json.loads(result.stdout)
            info = {}

            # Status
            if data.get("smart_status", {}).get("passed") is False:
                info["status"] = "FAIL"
            elif data.get("smart_status", {}).get("passed") is True:
                info["status"] = "OK"
            else:
                info["status"] = "N/A"

            # Temperature
            temp = data.get("temperature", {}).get("current")
            if temp:
                info["temperature"] = temp

            # Parse ATA attributes
            for attr in data.get("ata_smart_attributes", {}).get("table", []):
                attr_id = attr.get("id")
                raw_value = attr.get("raw", {}).get("value", 0)

                if attr_id == 9:  # Power-On Hours
                    info["power_on_hours"] = raw_value
                elif attr_id == 12:  # Power Cycle Count
                    info["power_cycle_count"] = raw_value
                elif attr_id == 5:  # Reallocated Sectors Count
                    info["reallocated_sectors"] = raw_value
                elif attr_id == 197:  # Current Pending Sector Count
                    info["pending_sectors"] = raw_value
                elif attr_id in [177, 231, 233]:  # SSD Wear Level indicators
                    # Different manufacturers use different attributes
                    val = attr.get("value", 0)
                    if val > 0:
                        info["wear_level"] = val

            # NVMe specific
            nvme_log = data.get("nvme_smart_health_information_log", {})
            if nvme_log:
                if "power_on_hours" in nvme_log:
                    info["power_on_hours"] = nvme_log["power_on_hours"]
                if "power_cycles" in nvme_log:
                    info["power_cycle_count"] = nvme_log["power_cycles"]
                if "percentage_used" in nvme_log:
                    info["wear_level"] = 100 - nvme_log["percentage_used"]
                if "temperature" in nvme_log:
                    info["temperature"] = nvme_log["temperature"]

            return info

        except Exception as e:
            logger.error(f"Error getting SMART info: {e}")
            return {}

    def _get_partition_label(self) -> Optional[str]:
        """Get partition label."""
        if not self.partition:
            return None

        device = self.partition.get("full_path", "")
        if not device:
            return None

        try:
            result = subprocess.run([LSBLK, "-o", "LABEL", "-n", device], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip() or None
        except Exception as e:
            logger.debug(f"Failed to get partition label for {device}: {e}")

        return None

    def _get_partition_scheme(self) -> Optional[str]:
        """Get partition scheme (GPT/MBR)."""
        device = self.disk.get("full_path", "")
        if not device:
            return None

        try:
            result = subprocess.run([LSBLK, "-o", "PTTYPE", "-n", device], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                scheme = result.stdout.strip().upper()
                return scheme if scheme else None
        except Exception as e:
            logger.debug(f"Failed to get partition scheme for {device}: {e}")

        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "close_btn":
            self.dismiss()

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()
