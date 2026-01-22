"""Tests for ProcessesCollector."""

import pytest
from unittest.mock import patch, MagicMock


class TestProcessesCollector:
    """Tests for ProcessesCollector class."""

    def test_import(self):
        """Test that ProcessesCollector can be imported."""
        from collectors.processes import ProcessesCollector
        assert ProcessesCollector is not None

    def test_init(self):
        """Test ProcessesCollector initialization."""
        from collectors.processes import ProcessesCollector
        collector = ProcessesCollector()
        assert collector is not None

    def test_collect_returns_dict(self):
        """Test that collect returns a dictionary."""
        from collectors.processes import ProcessesCollector
        collector = ProcessesCollector()
        data = collector.collect()
        assert isinstance(data, dict)

    def test_collect_has_processes(self):
        """Test that collect includes processes list."""
        from collectors.processes import ProcessesCollector
        collector = ProcessesCollector()
        data = collector.collect()
        assert 'processes' in data
        assert isinstance(data['processes'], list)

    def test_collect_has_stats(self):
        """Test that collect includes stats."""
        from collectors.processes import ProcessesCollector
        collector = ProcessesCollector()
        data = collector.collect()
        assert 'stats' in data
        stats = data['stats']
        assert 'total' in stats
        assert 'running' in stats
        assert 'sleeping' in stats

    def test_process_has_required_fields(self):
        """Test that process entries have required fields."""
        from collectors.processes import ProcessesCollector
        collector = ProcessesCollector()
        data = collector.collect()

        if data['processes']:
            process = data['processes'][0]
            required_fields = ['pid', 'name', 'cpu', 'mem_pct', 'status', 'user']
            for field in required_fields:
                assert field in process, f"Missing field: {field}"

    def test_stats_counts_are_non_negative(self):
        """Test that stats counts are non-negative integers."""
        from collectors.processes import ProcessesCollector
        collector = ProcessesCollector()
        data = collector.collect()
        stats = data['stats']

        assert stats['total'] >= 0
        assert stats['running'] >= 0
        assert stats['sleeping'] >= 0

    def test_total_equals_sum_of_states(self):
        """Test that total roughly equals sum of process states."""
        from collectors.processes import ProcessesCollector
        collector = ProcessesCollector()
        data = collector.collect()
        stats = data['stats']

        # Total should be >= sum of tracked states
        tracked = stats['running'] + stats['sleeping'] + stats.get('other', 0)
        assert stats['total'] >= tracked

    def test_processes_sorted_by_cpu(self):
        """Test that processes are sorted by CPU usage descending."""
        from collectors.processes import ProcessesCollector
        collector = ProcessesCollector()
        data = collector.collect()
        processes = data['processes']

        if len(processes) > 1:
            cpu_values = [p['cpu'] for p in processes]
            assert cpu_values == sorted(cpu_values, reverse=True), "Processes should be sorted by CPU descending"

    @patch('collectors.processes.psutil.process_iter')
    def test_handles_no_such_process(self, mock_iter):
        """Test handling of NoSuchProcess exception."""
        import psutil
        mock_iter.side_effect = psutil.NoSuchProcess(pid=1)

        from collectors.processes import ProcessesCollector
        collector = ProcessesCollector()
        # Should not raise exception
        data = collector.collect()
        assert isinstance(data, dict)

    @patch('collectors.processes.psutil.process_iter')
    def test_handles_access_denied(self, mock_iter):
        """Test handling of AccessDenied exception."""
        import psutil
        mock_iter.side_effect = psutil.AccessDenied(pid=1)

        from collectors.processes import ProcessesCollector
        collector = ProcessesCollector()
        # Should not raise exception
        data = collector.collect()
        assert isinstance(data, dict)


class TestProcessesEdgeCases:
    """Edge case tests for ProcessesCollector."""

    def test_get_data_after_update(self):
        """Test get_data returns collected data after update."""
        from collectors.processes import ProcessesCollector
        collector = ProcessesCollector()
        collector.update()
        data = collector.get_data()
        assert data is not None
        assert 'processes' in data

    def test_multiple_collects(self):
        """Test multiple collect calls work correctly."""
        from collectors.processes import ProcessesCollector
        collector = ProcessesCollector()

        data1 = collector.collect()
        data2 = collector.collect()

        assert isinstance(data1, dict)
        assert isinstance(data2, dict)
        assert 'processes' in data1
        assert 'processes' in data2
