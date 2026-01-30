"""Tests for utils/logger.py module."""

import logging
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.logger import get_logger, setup_exception_logging, setup_logging


class TestGetLogger(unittest.TestCase):
    """Tests for get_logger() function."""

    def test_returns_logger_instance(self):
        """Should return a logging.Logger instance."""
        logger = get_logger("test_module")
        self.assertIsInstance(logger, logging.Logger)

    def test_logger_has_prefix(self):
        """Should prefix logger name with LOGGER_PREFIX."""
        logger = get_logger("mymodule")
        self.assertIn("mymodule", logger.name)

    def test_different_names_different_loggers(self):
        """Different names should return different loggers."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        self.assertNotEqual(logger1.name, logger2.name)

    def test_same_name_same_logger(self):
        """Same name should return same logger instance."""
        logger1 = get_logger("same_module")
        logger2 = get_logger("same_module")
        self.assertEqual(logger1.name, logger2.name)
        self.assertIs(logger1, logger2)


class TestSetupLogging(unittest.TestCase):
    """Tests for setup_logging() function."""

    def setUp(self):
        """Create temp directory for log files."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'test.log')

    def tearDown(self):
        """Cleanup temp files and reset logging."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Reset loggers
        from const import LOGGER_PREFIX
        logger = logging.getLogger(LOGGER_PREFIX)
        logger.handlers.clear()

    def test_creates_file_handler_by_default(self):
        """Should create RotatingFileHandler by default."""
        from logging.handlers import RotatingFileHandler
        setup_logging(self.log_file)

        from const import LOGGER_PREFIX
        logger = logging.getLogger(LOGGER_PREFIX)

        has_file_handler = any(
            isinstance(h, RotatingFileHandler)
            for h in logger.handlers
        )
        self.assertTrue(has_file_handler)

    def test_creates_stdout_handler_when_env_set(self):
        """Should create StreamHandler when LOG_DEST=stdout."""
        with patch.dict(os.environ, {'LOG_DEST': 'stdout'}):
            setup_logging(self.log_file)

            from const import LOGGER_PREFIX
            logger = logging.getLogger(LOGGER_PREFIX)

            has_stream_handler = any(
                isinstance(h, logging.StreamHandler) and not hasattr(h, 'baseFilename')
                for h in logger.handlers
            )
            self.assertTrue(has_stream_handler)

    def test_sets_log_level(self):
        """Should set specified log level."""
        setup_logging(self.log_file, level=logging.DEBUG)

        from const import LOGGER_PREFIX
        logger = logging.getLogger(LOGGER_PREFIX)

        self.assertEqual(logger.level, logging.DEBUG)

    def test_clears_existing_handlers(self):
        """Should clear existing handlers before adding new one."""
        from const import LOGGER_PREFIX
        logger = logging.getLogger(LOGGER_PREFIX)

        # Add dummy handlers
        logger.addHandler(logging.NullHandler())
        logger.addHandler(logging.NullHandler())
        self.assertEqual(len(logger.handlers), 2)

        setup_logging(self.log_file)

        # Should have only one handler now
        self.assertEqual(len(logger.handlers), 1)

    def test_disables_propagation(self):
        """Should disable log propagation."""
        setup_logging(self.log_file)

        from const import LOGGER_PREFIX
        logger = logging.getLogger(LOGGER_PREFIX)

        self.assertFalse(logger.propagate)

    def test_text_format_default(self):
        """Should use text formatter by default."""
        setup_logging(self.log_file)

        from const import LOGGER_PREFIX
        logger = logging.getLogger(LOGGER_PREFIX)

        handler = logger.handlers[0]
        self.assertIsInstance(handler.formatter, logging.Formatter)

    def test_writes_to_file(self):
        """Should actually write logs to file."""
        setup_logging(self.log_file, level=logging.INFO)

        from const import LOGGER_PREFIX
        logger = logging.getLogger(LOGGER_PREFIX)
        logger.info("Test message")

        # Force flush
        for handler in logger.handlers:
            handler.flush()

        self.assertTrue(os.path.exists(self.log_file))
        with open(self.log_file, 'r') as f:
            content = f.read()
        self.assertIn("Test message", content)

    def test_log_format_contains_timestamp(self):
        """Log format should contain timestamp."""
        setup_logging(self.log_file, level=logging.INFO)

        from const import LOGGER_PREFIX
        logger = logging.getLogger(LOGGER_PREFIX)
        logger.info("Timestamp test")

        for handler in logger.handlers:
            handler.flush()

        with open(self.log_file, 'r') as f:
            content = f.read()
        # Should have date format YYYY-MM-DD
        import re
        self.assertTrue(re.search(r'\d{4}-\d{2}-\d{2}', content))


class TestSetupExceptionLogging(unittest.TestCase):
    """Tests for setup_exception_logging() function."""

    def setUp(self):
        """Save original excepthook."""
        self.original_excepthook = sys.excepthook

    def tearDown(self):
        """Restore original excepthook."""
        sys.excepthook = self.original_excepthook

    def test_sets_excepthook(self):
        """Should set sys.excepthook."""
        setup_exception_logging()
        self.assertNotEqual(sys.excepthook, self.original_excepthook)

    def test_handles_keyboard_interrupt(self):
        """Should pass KeyboardInterrupt to original hook."""
        setup_exception_logging()

        with patch.object(sys, '__excepthook__') as mock_hook:
            sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
            mock_hook.assert_called_once()


class TestLoggingIntegration(unittest.TestCase):
    """Integration tests for logging system."""

    def setUp(self):
        """Create temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'integration.log')

    def tearDown(self):
        """Cleanup."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        from const import LOGGER_PREFIX
        logger = logging.getLogger(LOGGER_PREFIX)
        logger.handlers.clear()

    def test_full_logging_workflow(self):
        """Test complete logging workflow."""
        # Setup
        setup_logging(self.log_file, level=logging.DEBUG)

        # Get logger
        logger = get_logger("integration_test")

        # Log messages at different levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Flush handlers
        from const import LOGGER_PREFIX
        root_logger = logging.getLogger(LOGGER_PREFIX)
        for handler in root_logger.handlers:
            handler.flush()

        # Verify
        with open(self.log_file, 'r') as f:
            content = f.read()

        self.assertIn("Debug message", content)
        self.assertIn("Info message", content)
        self.assertIn("Warning message", content)
        self.assertIn("Error message", content)

    def test_logger_name_in_output(self):
        """Logger name should appear in log output."""
        setup_logging(self.log_file, level=logging.INFO)
        logger = get_logger("my_component")
        logger.info("Test message")

        from const import LOGGER_PREFIX
        root_logger = logging.getLogger(LOGGER_PREFIX)
        for handler in root_logger.handlers:
            handler.flush()

        with open(self.log_file, 'r') as f:
            content = f.read()
        self.assertIn("my_component", content)


if __name__ == '__main__':
    unittest.main()
