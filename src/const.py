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
BANS_DB_FILE = os.path.join(CACHE_DIR, 'bans_db.json')
SLOW_BOTS_FILE = os.path.join(CACHE_DIR, 'suspicious_ips.json')

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)