"""Users tab widget."""

import os
import signal
from typing import Any, Dict

from rich.text import Text
from textual import work
from textual._context import NoActiveAppError
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static

from collectors import UsersCollector
from utils.logger import get_logger
from utils.ui_helpers import update_table_preserving_scroll

logger = get_logger("users_widget")


class UsersTab(Vertical):
    """Tab displaying user sessions and system users."""

    VIEW_ALL = 'all'
    VIEW_USERS = 'users'
    VIEW_SYSTEM = 'system'
    VIEW_SESSIONS = 'sessions'

    BINDINGS = [
        Binding("a", "show_all", "All Users"),
        Binding("u", "show_users", "Users"),
        Binding("s", "show_system", "System"),
        Binding("e", "show_sessions", "Sessions"),
        Binding("k", "kill_session", "Kill Session", show=False),
    ]

    DEFAULT_CSS = """
    UsersTab {
        height: 1fr;
        padding: 0;
    }
    #users_header_container {
        height: 3;
        margin: 0;
        padding: 0 1;
        border: round $success;
        margin-bottom: 0;
    }
    #users_header {
        margin: 0;
        padding: 0;
        width: 100%;
    }
    #users_table {
        height: 1fr;
        margin: 0;
        padding: 0;
    }
    """

    # Colors for different users
    USER_COLORS = ['cyan', 'green', 'yellow', 'magenta', 'blue', 'bright_cyan', 'bright_green', 'bright_magenta']

    def __init__(self, collector: UsersCollector):
        super().__init__()
        self.collector = collector
        self._current_view = self.VIEW_ALL
        self._last_data = None
        self._user_color_map = {}

    def compose(self):
        with Static(id="users_header_container"):
            yield Label("[bold cyan]Loading...[/bold cyan]", id="users_header")
        yield DataTable(id="users_table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Setup table and start updates."""
        self.update_data()

    @work(exclusive=True, thread=True)

    def _setup_table_columns(self) -> None:
        """Setup table columns based on current view mode."""
        try:
            table = self.query_one("#users_table", DataTable)
            table.clear(columns=True)

            if self._current_view == self.VIEW_SESSIONS:
                table.add_columns("User", "Terminal", "Host", "Login Time", "Duration", "PID")
            else:
                table.add_columns("User", "UID", "GID", "Shell", "Home", "Description")
        except Exception as e:
            logger.error(f"Failed to setup table columns: {e}")

    def _switch_view(self, view: str) -> None:
        """Switch to a different view."""
        if self._current_view == view:
            return
        self._current_view = view
        self._setup_table_columns()
        self._update_view()

    def action_show_all(self) -> None:
        self._switch_view(self.VIEW_ALL)

    def action_show_users(self) -> None:
        self._switch_view(self.VIEW_USERS)

    def action_show_system(self) -> None:
        self._switch_view(self.VIEW_SYSTEM)

    def action_show_sessions(self) -> None:
        self._switch_view(self.VIEW_SESSIONS)

    def action_kill_session(self) -> None:
        """Kill the selected session."""
        if self._current_view != self.VIEW_SESSIONS:
            self.notify("Switch to Sessions view to kill sessions", severity="warning")
            return

        try:
            table = self.query_one("#users_table", DataTable)
            if table.cursor_row is None:
                return

            row_key = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key
            row_data = table.get_row(row_key)

            if len(row_data) < 6:
                return

            pid_text = row_data[5]
            pid_str = pid_text.plain if isinstance(pid_text, Text) else str(pid_text)

            if pid_str and pid_str != '-' and pid_str.isdigit():
                pid = int(pid_str)
                try:
                    os.kill(pid, signal.SIGTERM)
                    self.notify(f"Session (PID {pid}) terminated", severity="information")
                    self.update_data()
                except ProcessLookupError:
                    self.notify(f"Process {pid} not found", severity="warning")
                except PermissionError:
                    self.notify(f"Permission denied to kill PID {pid}", severity="error")
            else:
                self.notify("Cannot determine session PID", severity="warning")
        except Exception as e:
            logger.error(f"Error killing session: {e}")
            self.notify(f"Error: {e}", severity="error")

    @work(exclusive=True, thread=True)
    def update_data(self) -> None:
        """Fetch data in background."""
        try:
            data = self.collector.update()
            self._last_data = data
            self.app.call_from_thread(self._update_view)
        except NoActiveAppError:
            # App not ready or shutting down - ignore silently
            pass
        except Exception as e:
            logger.error(f"Failed to update users data: {type(e).__name__}: {e}")

    def _update_view(self) -> None:
        """Update table with current view mode."""
        if not self._last_data:
            return

        try:
            table = self.query_one("#users_table", DataTable)
            header = self.query_one("#users_header", Label)

            # Build header with stats
            header_text = self._build_header()
            header.update(header_text)

            # Populate table based on current view
            if self._current_view == self.VIEW_SESSIONS:
                self._populate_sessions(table)
            elif self._current_view == self.VIEW_USERS:
                self._populate_users(table, user_type='human')
            elif self._current_view == self.VIEW_SYSTEM:
                self._populate_users(table, user_type='system')
            else:  # VIEW_ALL
                self._populate_users(table, user_type=None)

        except Exception as e:
            logger.error(f"Error updating view: {e}", exc_info=True)

    def _build_header(self) -> str:
        """Build header with stats from all views."""
        data = self._last_data or {}

        # Users stats
        users_list = data.get('users_list', [])
        total_users = len(users_list)
        human_users = len([u for u in users_list if u.get('type') == 'human'])
        system_users = len([u for u in users_list if u.get('type') == 'system'])

        # Sessions stats
        sessions = data.get('sessions', [])
        sessions_count = len(sessions)
        unique_session_users = len(set(s.get('name') for s in sessions))

        # Current view indicator
        view_labels = {
            self.VIEW_ALL: '► All Users',
            self.VIEW_USERS: '► Users',
            self.VIEW_SYSTEM: '► System',
            self.VIEW_SESSIONS: '► Sessions',
        }
        current = f"[bold cyan]{view_labels[self._current_view]}[/bold cyan]"

        return (
            f"{current} │ "
            f"[dim]Total:[/dim] [white]{total_users}[/white] │ "
            f"[dim]Users:[/dim] [green]{human_users}[/green] │ "
            f"[dim]System:[/dim] [dim]{system_users}[/dim] │ "
            f"[dim]Sessions:[/dim] [yellow]{sessions_count}[/yellow] ({unique_session_users} users)"
        )

    def _get_user_color(self, username: str) -> str:
        """Get consistent color for a username."""
        if username not in self._user_color_map:
            color_idx = len(self._user_color_map) % len(self.USER_COLORS)
            self._user_color_map[username] = self.USER_COLORS[color_idx]
        return self._user_color_map[username]

    def _populate_sessions(self, table: DataTable) -> None:
        """Populate table with active sessions."""
        def populate(t):
            sessions = self._last_data.get('sessions', [])
            if not sessions:
                t.add_row("No active sessions", "", "", "", "", "")
                return

            for s in sessions:
                try:
                    name = s.get('name', 'N/A')
                    terminal = s.get('terminal', '?')
                    host = s.get('host', 'local')
                    login_time = s.get('login_time', 'N/A')
                    duration = s.get('duration', 'N/A')
                    pid = s.get('pid', '-')

                    # Color username
                    user_color = self._get_user_color(name)
                    name_text = Text(name, style=f"bold {user_color}")

                    # Color terminal (pts = cyan, tty = green)
                    if terminal.startswith('pts'):
                        term_text = Text(terminal, style="cyan")
                    elif terminal.startswith('tty'):
                        term_text = Text(terminal, style="green")
                    else:
                        term_text = Text(terminal, style="dim")

                    # Color host (local = dim, remote = yellow)
                    if host == 'local' or host == ':0' or not host:
                        host_text = Text(host or 'local', style="dim")
                    else:
                        host_text = Text(host, style="yellow")

                    # PID
                    pid_text = Text(str(pid) if pid else '-', style="dim")

                    t.add_row(name_text, term_text, host_text, login_time, duration, pid_text)
                except Exception as e:
                    logger.debug(f"Error processing session: {e}")
                    continue

        update_table_preserving_scroll(table, populate)

    def _populate_users(self, table: DataTable, user_type: str = None) -> None:
        """Populate table with users, optionally filtered by type."""
        def populate(t):
            users = self._last_data.get('users_list', [])
            if not users:
                t.add_row("No users found", "", "", "", "", "")
                return

            # Filter by type if specified
            if user_type:
                users = [u for u in users if u.get('type') == user_type]

            if not users:
                t.add_row(f"No {user_type} users found", "", "", "", "", "")
                return

            # Sort: human users first, then by name
            users = sorted(users, key=lambda x: (x.get('type') != 'human', x.get('name', '')))

            for u in users:
                try:
                    name = u.get('name', 'N/A')
                    uid = u.get('uid', 0)
                    gid = u.get('gid', 0)
                    shell = u.get('shell', 'N/A')
                    home = u.get('home', 'N/A')
                    desc = u.get('description', '')
                    u_type = u.get('type', 'system')

                    # Color based on user type
                    if uid == 0:
                        # Root user - red
                        name_text = Text(name, style="bold red")
                        uid_text = Text(str(uid), style="red")
                    elif u_type == 'human':
                        # Regular users - green
                        name_text = Text(name, style="bold green")
                        uid_text = Text(str(uid), style="green")
                    else:
                        # System users - dim
                        name_text = Text(name, style="dim")
                        uid_text = Text(str(uid), style="dim")

                    # Color shell (nologin/false = dim red, bash/zsh/fish = green)
                    shell_name = shell.split('/')[-1] if shell else ''
                    if shell_name in ['nologin', 'false']:
                        shell_text = Text(shell, style="dim red")
                    elif shell_name in ['bash', 'zsh', 'fish', 'sh']:
                        shell_text = Text(shell, style="green")
                    else:
                        shell_text = Text(shell, style="dim")

                    # Home directory
                    if home.startswith('/home/'):
                        home_text = Text(home, style="cyan")
                    elif home == '/root':
                        home_text = Text(home, style="red")
                    else:
                        home_text = Text(home, style="dim")

                    t.add_row(
                        name_text,
                        uid_text,
                        str(gid),
                        shell_text,
                        home_text,
                        desc or '-'
                    )
                except Exception as e:
                    logger.debug(f"Error processing user: {e}")
                    continue

        update_table_preserving_scroll(table, populate)
