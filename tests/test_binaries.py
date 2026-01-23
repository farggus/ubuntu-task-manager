"""Tests for utils/binaries module."""

import unittest
from unittest.mock import patch


class TestBinaries(unittest.TestCase):
    """Tests for binary path resolution."""

    def test_import(self):
        """Test that binaries module can be imported."""
        from utils.binaries import get_binary, get_binary_or_raise
        self.assertIsNotNone(get_binary)
        self.assertIsNotNone(get_binary_or_raise)

    def test_get_binary_returns_path(self):
        """Test get_binary returns a path for common binaries."""
        from utils.binaries import get_binary
        # /bin/ls or /usr/bin/ls should exist on any Linux
        path = get_binary('ls')
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith('ls'))

    def test_get_binary_unknown_returns_none(self):
        """Test get_binary returns None for unknown binary."""
        from utils.binaries import get_binary
        path = get_binary('definitely_not_a_real_binary_xyz123')
        self.assertIsNone(path)

    def test_get_binary_or_raise_returns_path(self):
        """Test get_binary_or_raise returns path for known binary."""
        from utils.binaries import get_binary_or_raise
        path = get_binary_or_raise('ls')
        self.assertIsNotNone(path)

    def test_get_binary_or_raise_raises_for_unknown(self):
        """Test get_binary_or_raise raises FileNotFoundError."""
        from utils.binaries import get_binary_or_raise
        with self.assertRaises(FileNotFoundError):
            get_binary_or_raise('definitely_not_a_real_binary_xyz123')

    def test_binary_constants_exist(self):
        """Test that binary constants are defined."""
        from utils.binaries import (
            APT,
            CP,
            DPKG_QUERY,
            GREP,
            MKDIR,
            PS,
            SUDO,
            SYSTEMCTL,
            TAIL,
        )
        # These should all be defined (may be None if not installed)
        # Just checking they're importable
        self.assertTrue(True)

    def test_caching_works(self):
        """Test that binary paths are cached."""
        from utils.binaries import _binary_cache, get_binary
        # Clear cache first
        _binary_cache.clear()

        # First call should populate cache
        path1 = get_binary('ls')
        self.assertIn('ls', _binary_cache)

        # Second call should use cache
        path2 = get_binary('ls')
        self.assertEqual(path1, path2)

    @patch('shutil.which')
    def test_fallback_to_default(self, mock_which):
        """Test fallback to default paths when which fails."""
        from utils.binaries import _DEFAULT_PATHS, _binary_cache, get_binary
        _binary_cache.clear()

        # Make shutil.which return None
        mock_which.return_value = None

        # Should use default path
        path = get_binary('systemctl')
        expected = _DEFAULT_PATHS.get('systemctl')
        self.assertEqual(path, expected)


class TestBinaryPaths(unittest.TestCase):
    """Tests for specific binary paths."""

    def test_common_binaries_found(self):
        """Test that common system binaries are found."""
        from utils.binaries import GREP, PS, TAIL
        # These should exist on any Linux system
        common = [GREP, PS, TAIL]
        for binary in common:
            self.assertIsNotNone(binary, f"Common binary not found")

    def test_binary_paths_are_absolute(self):
        """Test that binary paths are absolute."""
        from utils.binaries import GREP, PS, TAIL
        for binary in [GREP, PS, TAIL]:
            if binary:
                self.assertTrue(
                    binary.startswith('/'),
                    f"Binary path {binary} is not absolute"
                )


if __name__ == '__main__':
    unittest.main()
