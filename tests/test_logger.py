"""Tests for utils/logger module."""

import logging
import unittest


class TestLogger(unittest.TestCase):
    """Tests for logger functionality."""

    def test_import(self):
        """Test that logger module can be imported."""
        from utils.logger import get_logger
        self.assertIsNotNone(get_logger)

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        from utils.logger import get_logger
        logger = get_logger('test')
        self.assertIsInstance(logger, logging.Logger)

    def test_get_logger_includes_name(self):
        """Test that get_logger creates logger with correct name suffix."""
        from utils.logger import get_logger
        logger = get_logger('my_test_logger')
        # Logger name may include a prefix like 'utm.my_test_logger'
        self.assertTrue(logger.name.endswith('my_test_logger'))

    def test_get_same_logger_twice(self):
        """Test that get_logger returns the same logger for same name."""
        from utils.logger import get_logger
        logger1 = get_logger('same_name')
        logger2 = get_logger('same_name')
        self.assertIs(logger1, logger2)

    def test_different_names_different_loggers(self):
        """Test that different names create different loggers."""
        from utils.logger import get_logger
        logger1 = get_logger('logger_a')
        logger2 = get_logger('logger_b')
        self.assertIsNot(logger1, logger2)


if __name__ == '__main__':
    unittest.main()
