"""Fail2ban v2 collector - log parser for unified attacks database."""

import glob
import gzip
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from database import AttacksDatabase
from utils.logger import get_logger

from .base import BaseCollector

logger = get_logger("fail2ban_v2")

# Log file locations
FAIL2BAN_LOG = Path("/var/log/fail2ban.log")
AUTH_LOG = Path("/var/log/auth.log")

# Regex patterns for fail2ban log parsing
PATTERNS = {
    # 2024-01-15 10:23:45,123 fail2ban.actions [12345]: NOTICE [sshd] Ban 192.168.1.1
    'ban': re.compile(
        r'(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}),\d+\s+'
        r'fail2ban\.\w+\s+\[\d+\]:\s+\w+\s+'
        r'\[(?P<jail>[^\]]+)\]\s+Ban\s+(?P<ip>\S+)'
    ),
    # 2024-01-15 10:23:45,123 fail2ban.actions [12345]: NOTICE [sshd] Unban 192.168.1.1
    'unban': re.compile(
        r'(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}),\d+\s+'
        r'fail2ban\.\w+\s+\[\d+\]:\s+\w+\s+'
        r'\[(?P<jail>[^\]]+)\]\s+Unban\s+(?P<ip>\S+)'
    ),
    # 2024-01-15 10:23:45,123 fail2ban.filter [12345]: INFO [sshd] Found 192.168.1.1
    'found': re.compile(
        r'(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}),\d+\s+'
        r'fail2ban\.filter\s+\[\d+\]:\s+INFO\s+'
        r'\[(?P<jail>[^\]]+)\]\s+Found\s+(?P<ip>\S+)'
    ),
}


class Fail2banV2Collector(BaseCollector):
    """
    Fail2ban v2 collector with unified database integration.
    
    Parses fail2ban logs directly and stores data in AttacksDatabase.
    Supports incremental parsing via log position tracking.
    """
    
    def __init__(self, config: Dict[str, Any] = None, db: AttacksDatabase = None):
        """
        Initialize collector.
        
        Args:
            config: Optional configuration dict
            db: Optional AttacksDatabase instance (creates new one if not provided)
        """
        super().__init__(config)
        self._db = db or AttacksDatabase()
        self._last_parse_time: float = 0
        self._parse_interval: float = 60.0  # Minimum seconds between full parses
    
    @property
    def db(self) -> AttacksDatabase:
        """Get database instance."""
        return self._db
    
    def collect(self) -> Dict[str, Any]:
        """
        Collect fail2ban data by parsing logs.
        
        Returns:
            Dictionary with collection results
        """
        t0 = time.time()
        logger.debug("Starting Fail2Ban v2 collection")
        
        result = {
            'success': False,
            'bans_found': 0,
            'unbans_found': 0,
            'attempts_found': 0,
            'new_ips': 0,
            'parse_time': 0,
            'logs_parsed': [],
        }
        
        try:
            # Parse fail2ban logs
            stats = self._parse_fail2ban_logs()
            
            result['bans_found'] = stats.get('bans', 0)
            result['unbans_found'] = stats.get('unbans', 0)
            result['attempts_found'] = stats.get('attempts', 0)
            result['new_ips'] = stats.get('new_ips', 0)
            result['logs_parsed'] = stats.get('logs_parsed', [])
            result['success'] = True
            
            # Save database
            self._db.save()
            
            result['parse_time'] = time.time() - t0
            logger.info(
                f"Fail2Ban v2 collection completed: "
                f"{result['bans_found']} bans, {result['unbans_found']} unbans, "
                f"{result['attempts_found']} attempts, duration={result['parse_time']:.2f}s"
            )
            
        except Exception as e:
            logger.error(f"Error in Fail2Ban v2 collection: {e}")
            result['error'] = str(e)
        
        return result
    
    def _parse_fail2ban_logs(self) -> Dict[str, int]:
        """
        Parse fail2ban log files (including rotated).
        
        Returns:
            Dict with counts of parsed events
        """
        stats = {
            'bans': 0,
            'unbans': 0,
            'attempts': 0,
            'new_ips': 0,
            'logs_parsed': [],
        }
        
        # Get all fail2ban log files
        log_files = self._get_log_files()
        if not log_files:
            logger.warning("No fail2ban log files found")
            return stats
        
        for log_file in log_files:
            try:
                file_stats = self._parse_single_log(log_file)
                stats['bans'] += file_stats.get('bans', 0)
                stats['unbans'] += file_stats.get('unbans', 0)
                stats['attempts'] += file_stats.get('attempts', 0)
                stats['new_ips'] += file_stats.get('new_ips', 0)
                stats['logs_parsed'].append(str(log_file))
            except Exception as e:
                logger.error(f"Error parsing {log_file}: {e}")
        
        return stats
    
    def _get_log_files(self) -> List[Path]:
        """
        Get list of fail2ban log files, sorted oldest first.
        
        Returns:
            List of Path objects for log files
        """
        log_pattern = str(FAIL2BAN_LOG) + "*"
        files = [Path(f) for f in glob.glob(log_pattern)]
        
        # Sort: oldest first (rotated logs first, then current)
        # fail2ban.log.2.gz, fail2ban.log.1, fail2ban.log
        def sort_key(p: Path) -> Tuple[int, str]:
            name = p.name
            if name == 'fail2ban.log':
                return (0, '')  # Current log last
            # Extract rotation number if present
            try:
                num = int(name.replace('fail2ban.log.', '').replace('.gz', ''))
                return (1, -num)  # Higher numbers first (older)
            except ValueError:
                return (1, name)
        
        return sorted(files, key=sort_key, reverse=True)
    
    def _parse_single_log(self, log_path: Path) -> Dict[str, int]:
        """
        Parse a single log file.
        
        Args:
            log_path: Path to log file
            
        Returns:
            Dict with counts of parsed events
        """
        stats = {'bans': 0, 'unbans': 0, 'attempts': 0, 'new_ips': 0}
        log_key = str(log_path)
        
        # Get last known position (default to 0 if None)
        last_position = self._db.get_log_position(log_key) or 0
        current_position = 0
        
        # Open file (handle gzip)
        opener = gzip.open if log_path.suffix == '.gz' else open
        
        try:
            with opener(log_path, 'rt', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    current_position = line_num
                    
                    # Skip already processed lines (for current log only)
                    if not log_path.name.endswith('.gz') and line_num <= last_position:
                        continue
                    
                    # Try to match patterns
                    event = self._parse_line(line)
                    if event:
                        self._process_event(event, stats)
            
            # Update position for current log (not rotated)
            if not log_path.name.endswith('.gz'):
                self._db.set_log_position(log_key, current_position)
                
        except Exception as e:
            logger.error(f"Error reading {log_path}: {e}")
        
        return stats
    
    def _parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single log line.
        
        Args:
            line: Log line to parse
            
        Returns:
            Dict with event data or None
        """
        line = line.strip()
        if not line:
            return None
        
        # Try each pattern
        for event_type, pattern in PATTERNS.items():
            match = pattern.match(line)
            if match:
                data = match.groupdict()
                data['type'] = event_type
                
                # Parse timestamp
                try:
                    dt = datetime.strptime(data['timestamp'], '%Y-%m-%d %H:%M:%S')
                    data['datetime'] = dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    data['datetime'] = None
                
                return data
        
        return None
    
    def _process_event(self, event: Dict[str, Any], stats: Dict[str, int]) -> None:
        """
        Process a parsed event and update database.
        
        Args:
            event: Parsed event data
            stats: Stats dict to update
        """
        ip = event.get('ip')
        jail = event.get('jail', 'unknown')
        event_type = event.get('type')
        timestamp = event.get('datetime')
        
        if not ip:
            return
        
        # Check if IP is new
        existing = self._db.get_ip(ip)
        if not existing:
            stats['new_ips'] += 1
        
        if event_type == 'ban':
            # Get jail bantime (default 600s for unknown)
            duration = self._get_jail_bantime(jail)
            self._db.record_ban(ip, jail, duration=duration)
            stats['bans'] += 1
            logger.debug(f"Recorded ban: {ip} in {jail}")
            
        elif event_type == 'unban':
            self._db.record_unban(ip, jail)
            stats['unbans'] += 1
            logger.debug(f"Recorded unban: {ip} from {jail}")
            
        elif event_type == 'found':
            self._db.record_attempt(ip, jail)
            stats['attempts'] += 1
    
    def _get_jail_bantime(self, jail: str) -> int:
        """
        Get bantime for a jail.
        
        Args:
            jail: Jail name
            
        Returns:
            Bantime in seconds
        """
        # Known bantimes
        bantimes = {
            'recidive': 604800,  # 7 days
            'sshd': 600,         # 10 minutes
            'traefik-auth': 3600,
            'traefik-botsearch': 86400,
        }
        return bantimes.get(jail, 600)  # Default 10 min
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of current database state.
        
        Returns:
            Dict with database summary
        """
        stats = self._db.get_stats()
        active_bans = self._db.get_active_bans()
        top_threats = self._db.get_top_threats(limit=10)
        
        return {
            'total_ips': stats.get('total_ips', 0),
            'total_attempts': stats.get('total_attempts', 0),
            'total_bans': stats.get('total_bans', 0),
            'active_bans': len(active_bans),
            'top_country': stats.get('top_country'),
            'top_org': stats.get('top_org'),
            'top_threats': [
                {
                    'ip': ip,
                    'danger_score': data.get('danger_score', 0),
                    'attempts': data.get('attempts', {}).get('total', 0),
                    'bans': data.get('bans', {}).get('total', 0),
                }
                for ip, data in top_threats
            ],
        }
    
    def parse_full(self, reset_positions: bool = False) -> Dict[str, int]:
        """
        Force full parse of all logs.
        
        Args:
            reset_positions: If True, reset all log positions first
            
        Returns:
            Dict with parse statistics
        """
        if reset_positions:
            # Clear log positions to force full re-parse
            self._db._data['metadata']['log_positions'] = {}
        
        stats = self._parse_fail2ban_logs()
        self._db.recalculate_stats()
        self._db.save()
        
        return stats
