"""Tests for process_cache module."""

import time
from unittest.mock import MagicMock, patch

import psutil
import pytest

from utils.process_cache import (
    CACHE_TTL,
    get_process_list,
    get_process_stats,
    invalidate_cache,
)


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset cache before each test."""
    invalidate_cache()
    yield
    invalidate_cache()


class TestGetProcessList:
    """Tests for get_process_list function."""

    def test_returns_list_of_dicts(self):
        """Should return a list of process info dictionaries."""
        result = get_process_list(['pid', 'status'])

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(p, dict) for p in result)
        assert all('pid' in p and 'status' in p for p in result)

    def test_caches_results(self):
        """Should return cached results on subsequent calls."""
        with patch('utils.process_cache.psutil.process_iter') as mock_iter:
            mock_process = MagicMock()
            mock_process.info = {'pid': 1, 'status': 'running'}
            mock_iter.return_value = [mock_process]

            # First call
            result1 = get_process_list(['pid', 'status'])
            assert mock_iter.call_count == 1

            # Second call - should use cache
            result2 = get_process_list(['pid', 'status'])
            assert mock_iter.call_count == 1  # Not called again

            assert result1 == result2

    def test_refreshes_cache_after_ttl(self):
        """Should refresh cache after TTL expires."""
        with patch('utils.process_cache.psutil.process_iter') as mock_iter:
            mock_process = MagicMock()
            mock_process.info = {'pid': 1, 'status': 'running'}
            mock_iter.return_value = [mock_process]

            # First call
            get_process_list(['pid', 'status'])
            assert mock_iter.call_count == 1

            # Wait for TTL to expire
            time.sleep(CACHE_TTL + 0.1)

            # Should refresh
            get_process_list(['pid', 'status'])
            assert mock_iter.call_count == 2

    def test_refreshes_when_more_attrs_requested(self):
        """Should refresh cache when new call requests more attributes."""
        with patch('utils.process_cache.psutil.process_iter') as mock_iter:
            mock_process = MagicMock()
            mock_process.info = {'pid': 1, 'status': 'running', 'name': 'test'}
            mock_iter.return_value = [mock_process]

            # First call with fewer attrs
            get_process_list(['pid'])
            assert mock_iter.call_count == 1

            # Second call with more attrs - should refresh
            get_process_list(['pid', 'status', 'name'])
            assert mock_iter.call_count == 2

    def test_uses_cache_when_subset_requested(self):
        """Should use cache when requested attrs are subset of cached."""
        with patch('utils.process_cache.psutil.process_iter') as mock_iter:
            mock_process = MagicMock()
            mock_process.info = {'pid': 1, 'status': 'running', 'name': 'test'}
            mock_iter.return_value = [mock_process]

            # First call with more attrs
            get_process_list(['pid', 'status', 'name'])
            assert mock_iter.call_count == 1

            # Second call with fewer attrs - should use cache
            get_process_list(['pid'])
            assert mock_iter.call_count == 1

    def test_handles_process_exceptions(self):
        """Should skip processes that raise exceptions."""
        with patch('utils.process_cache.psutil.process_iter') as mock_iter:
            good_process = MagicMock()
            good_process.info = {'pid': 1, 'status': 'running'}

            # Create a bad process that raises exception when .info is accessed
            bad_process = MagicMock()
            type(bad_process).info = property(
                lambda self: (_ for _ in ()).throw(psutil.NoSuchProcess(123))
            )

            mock_iter.return_value = [good_process, bad_process]

            result = get_process_list(['pid', 'status'])
            assert len(result) == 1
            assert result[0]['pid'] == 1


class TestGetProcessStats:
    """Tests for get_process_stats function."""

    def test_returns_total_and_zombies(self):
        """Should return dictionary with total and zombies counts."""
        result = get_process_stats()

        assert isinstance(result, dict)
        assert 'total' in result
        assert 'zombies' in result
        assert result['total'] > 0
        assert result['zombies'] >= 0

    def test_counts_zombies_correctly(self):
        """Should count zombie processes correctly."""
        with patch('utils.process_cache.psutil.process_iter') as mock_iter:
            mock_iter.return_value = [
                MagicMock(info={'status': psutil.STATUS_RUNNING}),
                MagicMock(info={'status': psutil.STATUS_SLEEPING}),
                MagicMock(info={'status': psutil.STATUS_ZOMBIE}),
                MagicMock(info={'status': psutil.STATUS_ZOMBIE}),
            ]

            result = get_process_stats()

            assert result['total'] == 4
            assert result['zombies'] == 2


class TestInvalidateCache:
    """Tests for invalidate_cache function."""

    def test_forces_refresh_on_next_call(self):
        """Should force a fresh fetch after invalidation."""
        with patch('utils.process_cache.psutil.process_iter') as mock_iter:
            mock_process = MagicMock()
            mock_process.info = {'pid': 1, 'status': 'running'}
            mock_iter.return_value = [mock_process]

            # First call
            get_process_list(['pid', 'status'])
            assert mock_iter.call_count == 1

            # Invalidate
            invalidate_cache()

            # Next call should fetch fresh data
            get_process_list(['pid', 'status'])
            assert mock_iter.call_count == 2
