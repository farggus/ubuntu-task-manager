"""Logging configuration for the dashboard."""

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

from const import LOG_FILE, LOGGER_PREFIX


def setup_logging(log_file: str = LOG_FILE, level: int = logging.INFO) -> None:
    """
    Configure application logging.

    Args:
        log_file: Path to the log file.
        level: Logging level (default: logging.INFO).
    """
    logger = logging.getLogger(LOGGER_PREFIX)
    logger.setLevel(level)

    # Check environment variables
    log_format = os.getenv('LOG_FORMAT', 'text').lower()
    log_dest = os.getenv('LOG_DEST', 'file').lower()

    if log_dest == 'stdout':
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = RotatingFileHandler(
            log_file,
            maxBytes=1 * 1024 * 1024,  # 1 MB
            backupCount=10,
            encoding='utf-8'
        )

    # Import JsonFormatter if available and requested
    json_formatter = None
    if log_format == 'json':
        try:
            from pythonjsonlogger import jsonlogger
            json_formatter = jsonlogger.JsonFormatter(
                '%(asctime)s %(levelname)s %(name)s %(message)s',
                timestamp=True
            )
        except ImportError:
            pass

    if json_formatter:
        formatter = json_formatter
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    handler.setFormatter(formatter)

    # Remove existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(handler)
    logger.propagate = False

def setup_exception_logging():
    """
    Set up a global exception hook to log uncaught exceptions.
    """
    logger = get_logger("exception_handler")

    def handle_exception(exc_type, exc_value, exc_traceback):
        """
        Log uncaught exceptions using the configured logger.
        """
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the app prefix."""
    return logging.getLogger(f"{LOGGER_PREFIX}.{name}")


