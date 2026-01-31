"""Users collector."""

import datetime
import pwd
from typing import Any, Dict, List

import psutil

from utils.logger import get_logger

from .base import BaseCollector

logger = get_logger("users_collector")


class UsersCollector(BaseCollector):
    """Collects information about system users and login sessions."""

    def collect(self) -> Dict[str, Any]:
        """
        Collect users information.

        Returns:
            Dictionary with users data
        """
        return {
            'sessions': self._get_user_sessions(),
            'users_list': self._get_all_users()
        }

    def _get_user_sessions(self) -> List[Dict[str, Any]]:
        """Get currently logged in users via psutil."""
        sessions = []
        try:
            current_time = datetime.datetime.now().timestamp()

            for user in psutil.users():
                login_dt = datetime.datetime.fromtimestamp(user.started)
                duration_seconds = current_time - user.started
                duration = str(datetime.timedelta(seconds=int(duration_seconds)))

                sessions.append({
                    'name': user.name,
                    'terminal': user.terminal or '?',
                    'host': user.host or 'local',
                    'started': user.started,
                    'login_time': login_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    'duration': duration,
                    'pid': user.pid
                })
        except Exception as e:
            self.errors.append(f"Error getting sessions: {e}")

        return sessions

    def _get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users from /etc/passwd."""
        users = []
        try:
            for p in pwd.getpwall():
                # Determine user type
                # Root (0) and UID >= 1000 are usually humans/admins
                if p.pw_uid == 0 or p.pw_uid >= 1000:
                    u_type = 'human'
                else:
                    u_type = 'system'

                # Exclude nobody/nologin only if strictly needed, but request said "System Users", so keep them.
                # Just keeping 'nobody' as system.

                users.append({
                    'name': p.pw_name,
                    'uid': p.pw_uid,
                    'gid': p.pw_gid,
                    'shell': p.pw_shell,
                    'home': p.pw_dir,
                    'description': p.pw_gecos,
                    'type': u_type
                })
        except Exception as e:
            self.errors.append(f"Error reading passwd: {e}")

        return sorted(users, key=lambda x: x['name'])
