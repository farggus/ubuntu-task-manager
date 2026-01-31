"""
Fail2ban Client - Helper for real-time fail2ban queries.

This module provides a wrapper for fail2ban-client commands
to get real-time jail status, banned IPs, and ban/unban operations.
"""

import re
import subprocess
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger("fail2ban_client")


class Fail2banClient:
    """
    Wrapper for fail2ban-client commands.

    Usage:
        client = Fail2banClient()
        jails = client.get_jails()
        status = client.get_jail_status("sshd")
        client.ban_ip("192.168.1.100", "sshd")
    """

    def __init__(self, timeout: int = 10):
        """
        Initialize Fail2ban client.

        Args:
            timeout: Command timeout in seconds
        """
        self.timeout = timeout
        self._installed: Optional[bool] = None
        self._running: Optional[bool] = None

    def _run_command(self, cmd: List[str]) -> Optional[str]:
        """
        Run fail2ban-client command.

        Returns:
            Command output or None on error
        """
        try:
            full_cmd = ["sudo", "fail2ban-client"] + cmd
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.warning(f"Command failed: {' '.join(full_cmd)}: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {cmd}")
            return None
        except Exception as e:
            logger.error(f"Command error: {e}")
            return None

    def is_installed(self) -> bool:
        """Check if fail2ban is installed."""
        if self._installed is not None:
            return self._installed

        try:
            result = subprocess.run(
                ["which", "fail2ban-client"],
                capture_output=True,
                timeout=5
            )
            self._installed = result.returncode == 0
        except Exception:
            self._installed = False

        return self._installed

    def is_running(self) -> bool:
        """Check if fail2ban service is running."""
        output = self._run_command(["status"])
        self._running = output is not None and "Number of jail" in output
        return self._running

    def get_jails(self) -> List[str]:
        """
        Get list of active jail names.

        Returns:
            List of jail names
        """
        output = self._run_command(["status"])
        if not output:
            return []

        # Parse "Jail list:	sshd, recidive, ..."
        match = re.search(r"Jail list:\s*(.+)", output)
        if match:
            jails_str = match.group(1)
            return [j.strip() for j in jails_str.split(",") if j.strip()]

        return []

    def get_jail_status(self, jail: str) -> Dict[str, Any]:
        """
        Get status of a specific jail.

        Returns:
            Dict with jail status info
        """
        output = self._run_command(["status", jail])
        if not output:
            return {}

        result = {
            "name": jail,
            "currently_failed": 0,
            "total_failed": 0,
            "currently_banned": 0,
            "total_banned": 0,
            "banned_ips": []
        }

        # Parse status output
        for line in output.split("\n"):
            line = line.strip()
            if "Currently failed:" in line:
                match = re.search(r"Currently failed:\s*(\d+)", line)
                if match:
                    result["currently_failed"] = int(match.group(1))
            elif "Total failed:" in line:
                match = re.search(r"Total failed:\s*(\d+)", line)
                if match:
                    result["total_failed"] = int(match.group(1))
            elif "Currently banned:" in line:
                match = re.search(r"Currently banned:\s*(\d+)", line)
                if match:
                    result["currently_banned"] = int(match.group(1))
            elif "Total banned:" in line:
                match = re.search(r"Total banned:\s*(\d+)", line)
                if match:
                    result["total_banned"] = int(match.group(1))
            elif "Banned IP list:" in line:
                match = re.search(r"Banned IP list:\s*(.+)?$", line)
                if match and match.group(1):
                    ips = match.group(1).strip()
                    result["banned_ips"] = [ip.strip() for ip in ips.split() if ip.strip()]

        return result

    def get_jail_config(self, jail: str) -> Dict[str, Any]:
        """
        Get jail configuration (findtime, bantime, maxretry).

        Returns:
            Dict with jail config
        """
        result = {
            "findtime": None,
            "bantime": None,
            "maxretry": None
        }

        for key in ["findtime", "bantime", "maxretry"]:
            output = self._run_command(["get", jail, key])
            if output:
                try:
                    result[key] = int(output)
                except ValueError:
                    pass

        return result

    def get_all_banned_ips(self) -> Dict[str, List[str]]:
        """
        Get all currently banned IPs grouped by jail.

        Returns:
            Dict mapping jail name to list of banned IPs
        """
        result = {}
        for jail in self.get_jails():
            status = self.get_jail_status(jail)
            if status.get("banned_ips"):
                result[jail] = status["banned_ips"]
        return result

    def get_total_banned_count(self) -> int:
        """Get total count of currently banned IPs across all jails."""
        total = 0
        for jail in self.get_jails():
            status = self.get_jail_status(jail)
            total += status.get("currently_banned", 0)
        return total

    def ban_ip(self, ip: str, jail: str = "recidive") -> bool:
        """
        Ban an IP in the specified jail.

        Args:
            ip: IP address to ban
            jail: Jail name (default: recidive for permanent)

        Returns:
            True if successful
        """
        output = self._run_command(["set", jail, "banip", ip])
        success = output is not None
        if success:
            logger.info(f"Banned {ip} in {jail}")
        return success

    def unban_ip(self, ip: str, jail: Optional[str] = None) -> bool:
        """
        Unban an IP from specified jail or all jails.

        Args:
            ip: IP address to unban
            jail: Jail name or None for all jails

        Returns:
            True if successful
        """
        if jail:
            output = self._run_command(["set", jail, "unbanip", ip])
            success = output is not None
        else:
            # Unban from all jails
            output = self._run_command(["unban", ip])
            success = output is not None

        if success:
            logger.info(f"Unbanned {ip}" + (f" from {jail}" if jail else " from all jails"))
        return success

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of fail2ban status.

        Returns:
            Dict with summary info for header display
        """
        jails = self.get_jails()
        jails_with_bans = 0
        total_banned = 0

        for jail in jails:
            status = self.get_jail_status(jail)
            banned = status.get("currently_banned", 0)
            if banned > 0:
                jails_with_bans += 1
                total_banned += banned

        return {
            "installed": self.is_installed(),
            "running": self.is_running(),
            "jails_count": len(jails),
            "jails_with_bans": jails_with_bans,
            "total_banned": total_banned,
            "jails": jails
        }
