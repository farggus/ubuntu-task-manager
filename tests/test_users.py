"""Tests for UsersCollector."""

from unittest.mock import patch


class TestUsersCollector:
    """Tests for UsersCollector class."""

    def test_import(self):
        """Test that UsersCollector can be imported."""
        from collectors.users import UsersCollector
        assert UsersCollector is not None

    def test_init(self):
        """Test UsersCollector initialization."""
        from collectors.users import UsersCollector
        collector = UsersCollector()
        assert collector is not None

    def test_collect_returns_dict(self):
        """Test that collect returns a dictionary."""
        from collectors.users import UsersCollector
        collector = UsersCollector()
        data = collector.collect()
        assert isinstance(data, dict)

    def test_collect_has_sessions(self):
        """Test that collect includes sessions."""
        from collectors.users import UsersCollector
        collector = UsersCollector()
        data = collector.collect()
        assert 'sessions' in data
        assert isinstance(data['sessions'], list)

    def test_collect_has_users_list(self):
        """Test that collect includes users_list."""
        from collectors.users import UsersCollector
        collector = UsersCollector()
        data = collector.collect()
        assert 'users_list' in data
        assert isinstance(data['users_list'], list)

    def test_session_has_required_fields(self):
        """Test that session entries have required fields."""
        from collectors.users import UsersCollector
        collector = UsersCollector()
        data = collector.collect()

        if data['sessions']:
            session = data['sessions'][0]
            # At minimum should have user and terminal
            assert 'user' in session or 'name' in session

    def test_user_has_required_fields(self):
        """Test that user entries have required fields."""
        from collectors.users import UsersCollector
        collector = UsersCollector()
        data = collector.collect()

        if data['users_list']:
            user = data['users_list'][0]
            # Check for common fields
            assert 'name' in user or 'username' in user

    @patch('collectors.users.psutil.users')
    def test_handles_no_sessions(self, mock_users):
        """Test handling when no users are logged in."""
        mock_users.return_value = []

        from collectors.users import UsersCollector
        collector = UsersCollector()
        data = collector.collect()

        assert isinstance(data, dict)
        assert 'sessions' in data
        assert data['sessions'] == []

    @patch('collectors.users.psutil.users')
    def test_handles_psutil_exception(self, mock_users):
        """Test handling of psutil exceptions."""
        import psutil
        mock_users.side_effect = psutil.AccessDenied(pid=1)

        from collectors.users import UsersCollector
        collector = UsersCollector()
        # Should not raise exception
        data = collector.collect()
        assert isinstance(data, dict)


class TestUsersClassification:
    """Tests for user classification logic."""

    def test_system_users_filtered(self):
        """Test that system users are properly identified."""
        from collectors.users import UsersCollector
        collector = UsersCollector()
        data = collector.collect()

        # Root should be classified as system user if present
        users = data.get('users', [])
        for user in users:
            if user.get('name') == 'root' or user.get('username') == 'root':
                # Root is a system user
                assert user.get('uid', 0) == 0 or user.get('type') in ['system', 'root']
                break

    def test_get_data_returns_collected(self):
        """Test get_data returns collected data after update."""
        from collectors.users import UsersCollector
        collector = UsersCollector()
        collector.update()
        data = collector.get_data()
        assert data is not None
        assert 'sessions' in data or 'users_list' in data
