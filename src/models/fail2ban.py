"""Data models for Fail2ban module."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class JailType(Enum):
    """Type of Fail2ban jail."""

    REGULAR = "regular"
    HISTORY = "history"
    SLOW_DETECTOR = "slow_detector"


@dataclass
class BannedIP:
    """Represents a banned IP address with metadata."""

    ip: str
    country: str = "Unknown"
    org: str = "Unknown"
    attempts: int = 0
    bantime: int = 0
    jail: str = ""
    # For HISTORY section
    unban_time: Optional[str] = None
    # For SLOW DETECTOR section
    status: Optional[str] = None
    interval: Optional[str] = None
    # For Traefik jails
    target: Optional[str] = None


@dataclass
class JailInfo:
    """Represents a Fail2ban jail with its banned IPs."""

    name: str
    jail_type: JailType = JailType.REGULAR
    currently_banned: int = 0
    total_banned: int = 0
    filter_failures: int = 0
    banned_ips: List[BannedIP] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "JailInfo":
        """Create JailInfo from dictionary data."""
        name = data.get("name", "")

        # Determine jail type
        if name == "HISTORY":
            jail_type = JailType.HISTORY
        elif "SLOW" in name:
            jail_type = JailType.SLOW_DETECTOR
        else:
            jail_type = JailType.REGULAR

        # Convert banned_ips dicts to BannedIP objects
        banned_ips = []
        for ip_data in data.get("banned_ips", []):
            if isinstance(ip_data, dict):
                banned_ips.append(
                    BannedIP(
                        ip=ip_data.get("ip", "?"),
                        country=ip_data.get("country", "Unknown"),
                        org=ip_data.get("org", "Unknown"),
                        attempts=ip_data.get("attempts", 0),
                        bantime=ip_data.get("bantime", 0),
                        jail=ip_data.get("jail", ""),
                        unban_time=ip_data.get("unban_time"),
                        status=ip_data.get("status"),
                        interval=ip_data.get("interval"),
                        target=ip_data.get("target"),
                    )
                )
            else:
                # Handle case where banned_ips is a list of IP strings
                banned_ips.append(BannedIP(ip=str(ip_data)))

        return cls(
            name=name,
            jail_type=jail_type,
            currently_banned=data.get("currently_banned", 0),
            total_banned=data.get("total_banned", 0),
            filter_failures=data.get("filter_failures", 0),
            banned_ips=banned_ips,
        )


@dataclass
class Fail2banStatus:
    """Overall Fail2ban status."""

    installed: bool = False
    running: bool = False
    jails: List[JailInfo] = field(default_factory=list)
    total_banned: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "Fail2banStatus":
        """Create Fail2banStatus from dictionary data."""
        jails = [JailInfo.from_dict(j) if isinstance(j, dict) else j for j in data.get("jails", [])]
        return cls(
            installed=data.get("installed", False),
            running=data.get("running", False),
            jails=jails,
            total_banned=data.get("total_banned", 0),
        )
