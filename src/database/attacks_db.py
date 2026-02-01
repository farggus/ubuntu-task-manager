"""
Attacks Database - Unified storage for Fail2Ban attack data.

This module provides a single JSON-based database for storing:
- IP addresses with attack history
- Geolocation data
- Ban/unban events
- Whitelist and blacklist
- Analytics and danger scores
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger("attacks_db")

# Default database location
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "attacks.db.json"


def _now_iso() -> str:
    """Get current timestamp in ISO8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _now_unix() -> float:
    """Get current timestamp as Unix time."""
    return datetime.now(timezone.utc).timestamp()


class AttacksDatabase:
    """
    Unified database for Fail2Ban attack data.

    Thread-safe JSON file storage with atomic writes.

    Usage:
        db = AttacksDatabase()
        db.record_attempt("192.168.1.1", "sshd")
        db.record_ban("192.168.1.1", "sshd", duration=600)
        db.save()
    """

    SCHEMA_VERSION = "2.0"

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database.

        Args:
            db_path: Path to database file. Defaults to data/attacks.db.json
        """
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self._dirty = False

        self._load()

    # =========================================================================
    # File I/O
    # =========================================================================

    def _load(self) -> None:
        """Load database from disk or create new if not exists."""
        with self._lock:
            if self.db_path.exists():
                try:
                    with open(self.db_path, 'r', encoding='utf-8') as f:
                        self._data = json.load(f)
                    logger.debug(f"Loaded database from {self.db_path}")
                except (json.JSONDecodeError, IOError) as e:
                    logger.error(f"Failed to load database: {e}")
                    self._data = self._create_empty_db()
            else:
                logger.info(f"Creating new database at {self.db_path}")
                self._data = self._create_empty_db()
                self._dirty = True

    def save(self) -> bool:
        """
        Save database to disk with atomic write.

        Returns:
            True if saved successfully, False otherwise.
        """
        with self._lock:
            if not self._dirty:
                logger.debug("Database unchanged, skipping save")
                return True

            try:
                # Ensure directory exists
                self.db_path.parent.mkdir(parents=True, exist_ok=True)

                # Update last_updated
                self._data["last_updated"] = _now_iso()

                # Atomic write: write to temp file, then rename
                tmp_path = self.db_path.with_suffix('.tmp')
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)

                # Atomic rename (works on POSIX, mostly atomic on Windows)
                tmp_path.replace(self.db_path)

                self._dirty = False
                logger.debug(f"Saved database to {self.db_path}")
                return True

            except (IOError, OSError) as e:
                logger.error(f"Failed to save database: {e}")
                return False

    def _create_empty_db(self) -> Dict[str, Any]:
        """Create empty database structure."""
        return {
            "version": self.SCHEMA_VERSION,
            "created_at": _now_iso(),
            "last_updated": _now_iso(),

            "stats": {
                "total_ips": 0,
                "total_attempts": 0,
                "total_bans": 0,
                "active_bans": 0,
                "threats_count": 0,
                "evasion_active_count": 0,
                "top_country": None,
                "top_org": None
            },

            "metadata": {
                "log_positions": {},
                "last_full_sync": None,
                "schema_version": self.SCHEMA_VERSION
            },

            "whitelist": [],
            "blacklist": [],
            "ips": {}
        }

    # =========================================================================
    # IP CRUD Operations
    # =========================================================================

    def get_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """
        Get IP record from database.

        Args:
            ip: IP address

        Returns:
            IP record dict or None if not found
        """
        with self._lock:
            return self._data["ips"].get(ip)

    def upsert_ip(self, ip: str, data: Dict[str, Any]) -> None:
        """
        Update or insert IP record.

        Args:
            ip: IP address
            data: Data to merge into IP record
        """
        with self._lock:
            if ip not in self._data["ips"]:
                self._data["ips"][ip] = self._create_empty_ip_record()
                self._data["stats"]["total_ips"] += 1

            # Deep merge data
            self._deep_merge(self._data["ips"][ip], data)
            self._data["ips"][ip]["last_updated"] = _now_unix()
            self._dirty = True

    def _create_empty_ip_record(self) -> Dict[str, Any]:
        """Create empty IP record structure."""
        now = _now_iso()
        return {
            "first_seen": now,
            "last_seen": now,
            "last_updated": _now_unix(),

            "geo": {
                "country": None,
                "country_code": None,
                "country_name": None,
                "org": None,
                "asn": None,
                "city": None,
                "region": None,
                "is_vpn": None,
                "is_datacenter": None,
                "fetched_at": None
            },

            "attempts": {
                "total": 0,
                "by_jail": {},
                "by_day": {},
                "first_attempt": None,
                "last_attempt": None
            },

            "bans": {
                "total": 0,
                "active": False,
                "current_jail": None,
                "current_ban_start": None,
                "current_ban_duration": None,
                "history": []
            },

            "unbans": {
                "total": 0,
                "last": None
            },

            "status": "watching",
            "danger_score": 0,
            "tags": [],

            "analysis": {
                "avg_interval": None,
                "min_interval": None,
                "max_interval": None,
                "attack_duration": None,
                "attack_pattern": None,
                "attack_series": [],
                "priority": 3,
                "evasion_detected": False,
                "evasion_active": False,
                "threat_detected": False,
                "fails_before_ban": 0,
                "last_analysis": None
            },

            "user_comment": None,
            "notes": [],
            "custom": {}
        }

    def _deep_merge(self, base: Dict, update: Dict) -> None:
        """Recursively merge update into base dict."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    # =========================================================================
    # Event Recording
    # =========================================================================

    def record_attempt(self, ip: str, jail: str) -> None:
        """
        Record a failed authentication attempt.

        Args:
            ip: IP address
            jail: Fail2ban jail name
        """
        with self._lock:
            if ip not in self._data["ips"]:
                self._data["ips"][ip] = self._create_empty_ip_record()
                self._data["stats"]["total_ips"] += 1

            record = self._data["ips"][ip]
            record["last_seen"] = _now_iso()
            record["last_updated"] = _now_unix()
            record["attempts"]["total"] += 1
            record["attempts"]["by_jail"][jail] = record["attempts"]["by_jail"].get(jail, 0) + 1

            # Track by day
            today = datetime.now().strftime("%Y-%m-%d")
            record["attempts"]["by_day"][today] = record["attempts"]["by_day"].get(today, 0) + 1

            # Update global stats
            self._data["stats"]["total_attempts"] += 1

            self._dirty = True

    def record_ban(self, ip: str, jail: str, duration: int = 0,
                   trigger_count: int = 0, timestamp: Optional[str] = None) -> None:
        """
        Record a ban event.

        Args:
            ip: IP address
            jail: Fail2ban jail name
            duration: Ban duration in seconds
            trigger_count: Number of attempts that triggered ban
            timestamp: Ban timestamp (defaults to now)
        """
        with self._lock:
            if ip not in self._data["ips"]:
                self._data["ips"][ip] = self._create_empty_ip_record()
                self._data["stats"]["total_ips"] += 1

            record = self._data["ips"][ip]
            ban_time = timestamp or _now_iso()

            record["last_seen"] = ban_time
            record["last_updated"] = _now_unix()
            record["bans"]["total"] += 1
            record["bans"]["active"] = True
            record["bans"]["current_jail"] = jail
            record["bans"]["current_ban_start"] = ban_time
            record["bans"]["current_ban_duration"] = duration
            record["status"] = "active_ban"

            # Add to history
            record["bans"]["history"].append({
                "jail": jail,
                "start": ban_time,
                "end": None,
                "duration": duration,
                "trigger_count": trigger_count
            })

            # Update global stats
            self._data["stats"]["total_bans"] += 1
            self._data["stats"]["active_bans"] += 1

            self._dirty = True

    def record_unban(self, ip: str, jail: str, timestamp: Optional[str] = None) -> None:
        """
        Record an unban event.

        Args:
            ip: IP address
            jail: Fail2ban jail name
            timestamp: Unban timestamp (defaults to now)
        """
        with self._lock:
            if ip not in self._data["ips"]:
                return  # Nothing to unban

            record = self._data["ips"][ip]
            unban_time = timestamp or _now_iso()

            record["last_updated"] = _now_unix()
            record["unbans"]["total"] += 1
            record["unbans"]["last"] = unban_time

            # Update ban status
            if record["bans"]["current_jail"] == jail:
                record["bans"]["active"] = False
                record["bans"]["current_jail"] = None
                record["bans"]["current_ban_start"] = None
                record["bans"]["current_ban_duration"] = None
                record["status"] = "unbanned"

                # Update last history entry
                if record["bans"]["history"]:
                    record["bans"]["history"][-1]["end"] = unban_time

                # Update global stats
                self._data["stats"]["active_bans"] = max(0, self._data["stats"]["active_bans"] - 1)

            self._dirty = True

    # =========================================================================
    # Geo Data
    # =========================================================================

    def set_geo(self, ip: str, country: str, org: str,
                country_code: Optional[str] = None,
                asn: Optional[str] = None,
                city: Optional[str] = None) -> None:
        """
        Set geolocation data for an IP.

        Args:
            ip: IP address
            country: Country name
            org: Organization/ISP
            country_code: ISO country code
            asn: Autonomous System Number
            city: City name
        """
        with self._lock:
            if ip not in self._data["ips"]:
                self._data["ips"][ip] = self._create_empty_ip_record()
                self._data["stats"]["total_ips"] += 1

            record = self._data["ips"][ip]
            record["geo"] = {
                "country": country,
                "country_code": country_code,
                "org": org,
                "asn": asn,
                "city": city,
                "fetched_at": _now_iso()
            }
            record["last_updated"] = _now_unix()
            self._dirty = True

    def set_user_comment(self, ip: str, comment: str) -> None:
        """
        Set user comment for an IP.

        Args:
            ip: IP address
            comment: User comment/note
        """
        with self._lock:
            if ip not in self._data["ips"]:
                self._data["ips"][ip] = self._create_empty_ip_record()
                self._data["stats"]["total_ips"] += 1

            self._data["ips"][ip]["user_comment"] = comment
            self._data["ips"][ip]["last_updated"] = _now_unix()
            self._dirty = True

    # =========================================================================
    # Whitelist / Blacklist
    # =========================================================================

    def add_to_whitelist(self, ip: str, reason: str = "", added_by: str = "system") -> None:
        """Add IP to whitelist."""
        with self._lock:
            # Check if already in whitelist
            for entry in self._data["whitelist"]:
                if entry["ip"] == ip:
                    return

            self._data["whitelist"].append({
                "ip": ip,
                "added": _now_iso(),
                "reason": reason,
                "added_by": added_by
            })

            # Update IP status if exists
            if ip in self._data["ips"]:
                self._data["ips"][ip]["status"] = "whitelisted"
                self._data["ips"][ip]["last_updated"] = _now_unix()

            self._dirty = True

    def add_to_blacklist(self, ip: str, reason: str = "",
                         added_by: str = "system", expires: Optional[str] = None) -> None:
        """Add IP to blacklist."""
        with self._lock:
            # Check if already in blacklist
            for entry in self._data["blacklist"]:
                if entry["ip"] == ip:
                    return

            self._data["blacklist"].append({
                "ip": ip,
                "added": _now_iso(),
                "reason": reason,
                "added_by": added_by,
                "expires": expires
            })

            # Update IP status if exists
            if ip in self._data["ips"]:
                self._data["ips"][ip]["status"] = "blacklisted"
                self._data["ips"][ip]["last_updated"] = _now_unix()

            self._dirty = True

    def is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted."""
        with self._lock:
            return any(entry["ip"] == ip for entry in self._data["whitelist"])

    def is_blacklisted(self, ip: str) -> bool:
        """Check if IP is blacklisted."""
        with self._lock:
            return any(entry["ip"] == ip for entry in self._data["blacklist"])

    # =========================================================================
    # Queries
    # =========================================================================

    def get_all_ips(self) -> Dict[str, Dict[str, Any]]:
        """Get all IP records."""
        with self._lock:
            return dict(self._data["ips"])

    def get_active_bans(self) -> List[Dict[str, Any]]:
        """Get list of currently banned IPs with their data."""
        with self._lock:
            result = []
            for ip, data in self._data["ips"].items():
                if data.get("bans", {}).get("active", False):
                    result.append({"ip": ip, **data})
            return result

    def get_top_threats(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get IPs sorted by danger score (highest first)."""
        with self._lock:
            sorted_ips = sorted(
                self._data["ips"].items(),
                key=lambda x: x[1].get("danger_score", 0),
                reverse=True
            )
            return [{"ip": ip, **data} for ip, data in sorted_ips[:limit]]

    def get_recent_activity(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get IPs sorted by last_seen (most recent first)."""
        with self._lock:
            sorted_ips = sorted(
                self._data["ips"].items(),
                key=lambda x: x[1].get("last_seen", ""),
                reverse=True
            )
            return [{"ip": ip, **data} for ip, data in sorted_ips[:limit]]

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._lock:
            return dict(self._data["stats"])

    def get_whitelist(self) -> List[Dict[str, Any]]:
        """Get whitelist entries."""
        with self._lock:
            return list(self._data["whitelist"])

    def get_blacklist(self) -> List[Dict[str, Any]]:
        """Get blacklist entries."""
        with self._lock:
            return list(self._data["blacklist"])

    # =========================================================================
    # Analytics
    # =========================================================================

    def recalculate_stats(self) -> None:
        """Recalculate aggregate statistics."""
        with self._lock:
            ips = self._data["ips"]

            total_attempts = 0
            total_bans = 0
            active_bans = 0
            country_counts: Dict[str, int] = {}
            org_counts: Dict[str, int] = {}

            for ip_data in ips.values():
                total_attempts += ip_data.get("attempts", {}).get("total", 0)
                total_bans += ip_data.get("bans", {}).get("total", 0)
                if ip_data.get("bans", {}).get("active", False):
                    active_bans += 1

                country = ip_data.get("geo", {}).get("country")
                if country:
                    country_counts[country] = country_counts.get(country, 0) + 1

                org = ip_data.get("geo", {}).get("org")
                if org:
                    org_counts[org] = org_counts.get(org, 0) + 1

            self._data["stats"] = {
                "total_ips": len(ips),
                "total_attempts": total_attempts,
                "total_bans": total_bans,
                "active_bans": active_bans,
                "top_country": max(country_counts, key=country_counts.get) if country_counts else None,
                "top_org": max(org_counts, key=org_counts.get) if org_counts else None
            }
            self._dirty = True

    def calculate_danger_score(self, ip: str) -> int:
        """
        Calculate danger score for an IP (0-100).

        Factors:
        - Number of attempts
        - Number of bans
        - Recidive jail involvement
        - Recent activity
        - Attack pattern
        """
        with self._lock:
            if ip not in self._data["ips"]:
                return 0

            record = self._data["ips"][ip]
            score = 0

            # Attempts (max 25 points)
            attempts = record.get("attempts", {}).get("total", 0)
            score += min(attempts // 10, 25)

            # Bans (max 25 points)
            bans = record.get("bans", {}).get("total", 0)
            score += min(bans * 3, 25)

            # Recidive involvement (20 points)
            if "recidive" in record.get("attempts", {}).get("by_jail", {}):
                score += 20

            # Recent activity (max 20 points)
            last_seen = record.get("last_seen", "")
            if last_seen:
                try:
                    last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                    days_ago = (datetime.now(timezone.utc) - last_seen_dt).days
                    if days_ago < 1:
                        score += 20
                    elif days_ago < 7:
                        score += 10
                    elif days_ago < 30:
                        score += 5
                except (ValueError, TypeError):
                    pass

            # Currently banned (10 points)
            if record.get("bans", {}).get("active", False):
                score += 10

            return min(score, 100)

    def recalculate_danger_scores(self) -> None:
        """Recalculate danger scores for all IPs."""
        with self._lock:
            for ip in self._data["ips"]:
                self._data["ips"][ip]["danger_score"] = self.calculate_danger_score(ip)
                self._data["ips"][ip]["analysis"]["last_analysis"] = _now_iso()
            self._dirty = True

    # =========================================================================
    # Log Position Tracking (for incremental parsing)
    # =========================================================================

    def get_log_position(self, log_file: str) -> Optional[Dict[str, Any]]:
        """Get saved position for a log file."""
        with self._lock:
            return self._data["metadata"]["log_positions"].get(log_file)

    def set_log_position(self, log_file: str, position: int,
                         inode: int = 0, last_line: Optional[str] = None) -> None:
        """Save position for a log file."""
        with self._lock:
            self._data["metadata"]["log_positions"][log_file] = {
                "position": position,
                "inode": inode,
                "last_line": last_line
            }
            self._dirty = True
