"""Tests for utils/ui_helpers.py module."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.ui_helpers import bytes_to_human_readable, update_table_preserving_scroll


class TestBytesToHumanReadable(unittest.TestCase):
    """Tests for bytes_to_human_readable function."""

    def test_none_input(self):
        """Should return N/A for None input."""
        result = bytes_to_human_readable(None)
        self.assertEqual(result, "N/A")

    def test_bytes(self):
        """Should format bytes correctly."""
        result = bytes_to_human_readable(500)
        self.assertIn("500", result)
        self.assertIn("B", result)

    def test_kilobytes(self):
        """Should format kilobytes correctly."""
        result = bytes_to_human_readable(1024)
        self.assertIn("K", result)

    def test_megabytes(self):
        """Should format megabytes correctly."""
        result = bytes_to_human_readable(1024 * 1024)
        self.assertIn("M", result)

    def test_gigabytes(self):
        """Should format gigabytes correctly."""
        result = bytes_to_human_readable(1024 * 1024 * 1024)
        self.assertIn("G", result)

    def test_terabytes(self):
        """Should format terabytes correctly."""
        result = bytes_to_human_readable(1024 ** 4)
        self.assertIn("T", result)

    def test_petabytes(self):
        """Should format petabytes correctly."""
        result = bytes_to_human_readable(1024 ** 5)
        self.assertIn("P", result)

    def test_zero(self):
        """Should handle zero bytes."""
        result = bytes_to_human_readable(0)
        self.assertIn("0", result)

    def test_custom_suffix(self):
        """Should use custom suffix."""
        result = bytes_to_human_readable(1024, suffix="b")
        self.assertIn("Kb", result)

    def test_negative_bytes(self):
        """Should handle negative values."""
        result = bytes_to_human_readable(-1024)
        self.assertIn("K", result)

    def test_large_value(self):
        """Should handle very large values."""
        result = bytes_to_human_readable(1024 ** 8)
        self.assertIn("Y", result)


class TestUpdateTablePreservingScroll(unittest.TestCase):
    """Tests for update_table_preserving_scroll function."""

    def test_calls_clear_and_populate(self):
        """Should call clear and populate function."""
        mock_table = MagicMock()
        mock_table.cursor_row = 5
        mock_table.scroll_y = 100
        mock_table.is_valid_row_index.return_value = True
        mock_populate = MagicMock()

        update_table_preserving_scroll(mock_table, mock_populate)

        mock_table.clear.assert_called_once()
        mock_populate.assert_called_once_with(mock_table)

    def test_restores_cursor_position(self):
        """Should restore cursor position if valid."""
        mock_table = MagicMock()
        mock_table.cursor_row = 3
        mock_table.scroll_y = 50
        mock_table.is_valid_row_index.return_value = True
        mock_populate = MagicMock()

        update_table_preserving_scroll(mock_table, mock_populate)

        mock_table.move_cursor.assert_called_once_with(row=3)

    def test_skips_invalid_cursor(self):
        """Should skip cursor restore if position invalid."""
        mock_table = MagicMock()
        mock_table.cursor_row = 10
        mock_table.scroll_y = 50
        mock_table.is_valid_row_index.return_value = False
        mock_populate = MagicMock()

        update_table_preserving_scroll(mock_table, mock_populate)

        mock_table.move_cursor.assert_not_called()

    def test_schedules_scroll_restore(self):
        """Should schedule scroll restore after refresh."""
        mock_table = MagicMock()
        mock_table.cursor_row = None
        mock_table.scroll_y = 100
        mock_populate = MagicMock()

        update_table_preserving_scroll(mock_table, mock_populate)

        mock_table.call_after_refresh.assert_called_once()


if __name__ == '__main__':
    unittest.main()
