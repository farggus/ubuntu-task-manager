"""Application constants."""

import os
from pathlib import Path

APP_NAME = "Ubuntu Task Manager"
APP_SLUG = "utm"
APP_VERSION = "2.0.0"
LOGGER_PREFIX = "utm"

# Paths
# src/const.py -> src/ -> root
BASE_DIR = Path(__file__).parent.parent.absolute()
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = str(LOG_DIR / "utm.log")
CONFIG_DIR = BASE_DIR / "config"
DEFAULT_CONFIG = str(CONFIG_DIR / "config.yaml")

CACHE_DIR = BASE_DIR / "cache"
BANS_DB_FILE = os.path.join(CACHE_DIR, "bans_db.json")
SLOW_BOTS_FILE = os.path.join(CACHE_DIR, "suspicious_ips.json")
WHITELIST_FILE = os.path.join(CACHE_DIR, "whitelist.json")
DISK_CACHE_FILE = os.path.join(CACHE_DIR, "disk_cache.json")
SERVICE_STATS_CACHE_FILE = os.path.join(CACHE_DIR, "service_stats_cache.json")
PACKAGE_STATS_CACHE_FILE = os.path.join(CACHE_DIR, "package_stats_cache.json")
DISK_HIERARCHY_CACHE_FILE = os.path.join(CACHE_DIR, "disk_hierarchy_cache.json")

# Time constants (seconds)
SECONDS_IN_MINUTE = 60
SECONDS_IN_HOUR = 3600
SECONDS_IN_DAY = 86400
SECONDS_IN_MONTH = 2592000  # 30 days
SECONDS_IN_YEAR = 31536000  # 365 days

# Fail2ban constants
IP_CACHE_TTL = 300  # 5 minutes - TTL for geo-data cache
UNBAN_HISTORY_LIMIT = 500  # Max entries in unban history
SLOW_BOT_MIN_INTERVAL = 600  # Minimum interval for slow bot detection (10 min)
ORG_DISPLAY_MAX_LEN = 20  # Max length for org name display
RECIDIVE_BANTIME = SECONDS_IN_YEAR * 3  # 3 years for permanent bans

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
