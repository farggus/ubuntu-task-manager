"""Tests for BaseCollector."""

import pytest
from unittest.mock import patch


class TestBaseCollector:
    """Tests for BaseCollector abstract class."""

    def test_import(self):
        """Test that BaseCollector can be imported."""
        from collectors.base import BaseCollector
        assert BaseCollector is not None

    def test_cannot_instantiate_directly(self):
        """Test that BaseCollector cannot be instantiated directly."""
        from collectors.base import BaseCollector
        with pytest.raises(TypeError):
            BaseCollector()

    def test_concrete_implementation(self):
        """Test creating a concrete implementation."""
        from collectors.base import BaseCollector

        class TestCollector(BaseCollector):
            def collect(self):
                return {'test': 'data'}

        collector = TestCollector()
        assert collector is not None
        data = collector.collect()
        assert data == {'test': 'data'}

    def test_get_data_before_collect(self):
        """Test get_data returns empty dict before collect."""
        from collectors.base import BaseCollector

        class TestCollector(BaseCollector):
            def collect(self):
                return {'test': 'data'}

        collector = TestCollector()
        data = collector.get_data()
        assert data == {}

    def test_get_data_after_collect(self):
        """Test get_data returns collected data."""
        from collectors.base import BaseCollector

        class TestCollector(BaseCollector):
            def collect(self):
                return {'test': 'data'}

        collector = TestCollector()
        collector.update()
        data = collector.get_data()
        assert data == {'test': 'data'}

    def test_update_calls_collect(self):
        """Test that update() calls collect()."""
        from collectors.base import BaseCollector

        class TestCollector(BaseCollector):
            def __init__(self):
                super().__init__()
                self.collect_count = 0

            def collect(self):
                self.collect_count += 1
                return {'count': self.collect_count}

        collector = TestCollector()
        assert collector.collect_count == 0

        collector.update()
        assert collector.collect_count == 1

        collector.update()
        assert collector.collect_count == 2

    def test_name_property(self):
        """Test the name property."""
        from collectors.base import BaseCollector

        class MyTestCollector(BaseCollector):
            def collect(self):
                return {}

        collector = MyTestCollector()
        assert collector.name == 'MyTest'

    def test_has_errors_initially_false(self):
        """Test has_errors is False initially."""
        from collectors.base import BaseCollector

        class TestCollector(BaseCollector):
            def collect(self):
                return {}

        collector = TestCollector()
        assert collector.has_errors() is False

    def test_config_is_stored(self):
        """Test that config is stored."""
        from collectors.base import BaseCollector

        class TestCollector(BaseCollector):
            def collect(self):
                return {}

        config = {'key': 'value'}
        collector = TestCollector(config)
        assert collector.config == config

    def test_default_config_is_empty_dict(self):
        """Test that default config is empty dict."""
        from collectors.base import BaseCollector

        class TestCollector(BaseCollector):
            def collect(self):
                return {}

        collector = TestCollector()
        assert collector.config == {}


class TestBaseCollectorErrorHandling:
    """Test error handling in BaseCollector."""

    def test_collect_exception_is_handled(self):
        """Test that exceptions in collect are handled."""
        from collectors.base import BaseCollector

        class FailingCollector(BaseCollector):
            def collect(self):
                raise ValueError("Test error")

        collector = FailingCollector()
        # update() should handle the exception
        collector.update()
        # After failed update, data should still be accessible
        data = collector.get_data()
        assert isinstance(data, dict)
