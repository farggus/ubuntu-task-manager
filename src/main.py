#!/usr/bin/env python3
"""
Ubuntu Task Manager (UTM)
A TUI dashboard for monitoring and managing Ubuntu server configuration.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Performance profiling from start
_startup_start = time.time()
_startup_marks = {}

def _mark(label: str):
    """Record startup timing mark."""
    elapsed = (time.time() - _startup_start) * 1000
    _startup_marks[label] = elapsed
    print(f"[STARTUP] {label}: {elapsed:.1f}ms", flush=True)

_mark("Python start")

import sentry_sdk
from dotenv import load_dotenv

_mark("Imports sentry_sdk/dotenv done")

# Ensure src is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_mark("Before const import")
from const import APP_NAME, APP_VERSION, DEFAULT_CONFIG, LOGGER_PREFIX, SLOW_BOTS_FILE  # noqa: E402
_mark("After const import")

_mark("Skipping dashboard import at module level")

_mark("Before logger import")
from utils.logger import setup_exception_logging, setup_logging  # noqa: E402
_mark("After logger import")

# Load environment variables from .env file
load_dotenv()


if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )


def main():
    """Main entry point."""
    _mark("main() start")

    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} - Monitor your server"
    )
    _mark("ArgumentParser created")

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

    _mark("Before args.parse_args()")
    args = parser.parse_args()
    _mark("After args.parse_args()")

    # Configure logging
    _mark("Before setup_logging()")
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(level=log_level)
    setup_exception_logging()
    logger = logging.getLogger(f"{LOGGER_PREFIX}.main")
    _mark("After setup_logging()")

    # Check if config exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Warning: Config file '{args.config}' not found. Using defaults.")
        logger.warning(f"Config file '{args.config}' not found. Using defaults.")
        print("Create a config.yaml file from the example to customize settings.")

    try:
        _mark("Before app initialization")
        logger.info(f"========== Starting {APP_NAME} ==========")

        # Lazy import dashboard - done here instead of module level to avoid blocking startup
        _mark("Before dashboard import in main()")
        from dashboard import UTMDashboard  # noqa: E402
        _mark("After dashboard import in main()")

        # Time app initialization
        start = time.time()
        app = UTMDashboard(config_path=str(config_path))
        init_time = (time.time() - start) * 1000
        logger.info(f"App initialized in {init_time:.1f}ms")
        _mark(f"After app init ({init_time:.1f}ms)")

        # Time app.run()
        _mark("Before app.run()")
        start = time.time()
        app.run()
        run_time = (time.time() - start) * 1000
        logger.info(f"App.run() completed in {run_time:.1f}ms")
        _mark(f"After app.run() ({run_time:.1f}ms)")

    except KeyboardInterrupt:
        print("\nExiting...")
        logger.info("Application stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if os.path.exists(SLOW_BOTS_FILE):
            try:
                os.remove(SLOW_BOTS_FILE)
            except Exception as e:
                logger.error(f"Failed to remove temporary file {SLOW_BOTS_FILE}: {e}")

        # Print final summary
        _mark("Shutdown")
        print("\n[STARTUP PROFILE SUMMARY]")
        for label, elapsed in _startup_marks.items():
            print(f"  {label}: {elapsed:.1f}ms")


if __name__ == "__main__":
    main()
