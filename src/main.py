#!/usr/bin/env python3
"""
Ubuntu Task Manager (UTM)
A TUI dashboard for monitoring and managing Ubuntu server configuration.
"""

import argparse
import sys
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure src is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from const import APP_NAME, APP_VERSION, LOGGER_PREFIX, DEFAULT_CONFIG
from utils.logger import setup_logging, setup_exception_logging
from dashboard import UTMDashboard

# Load environment variables from .env file
load_dotenv()

# Initialize Sentry for error tracking
import sentry_sdk
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} - Monitor your server"
    )
    parser.add_argument(
        '-c', '--config',
        default=DEFAULT_CONFIG,
        help=f'Path to configuration file (default: {DEFAULT_CONFIG})'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'{APP_NAME} {APP_VERSION}'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(level=log_level)
    setup_exception_logging()
    logger = logging.getLogger(f"{LOGGER_PREFIX}.main")

    # Check if config exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Warning: Config file '{args.config}' not found. Using defaults.")
        logger.warning(f"Config file '{args.config}' not found. Using defaults.")
        print(f"Create a config.yaml file from the example to customize settings.")

    try:
        logger.info(f"Starting {APP_NAME}")
        # Run the dashboard
        app = UTMDashboard(config_path=str(config_path))
        app.run()
    except KeyboardInterrupt:
        print("\nExiting...")
        logger.info("Application stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()