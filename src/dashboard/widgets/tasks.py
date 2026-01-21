"""Tasks tab widget."""

from textual import work
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static
from textual.binding import Binding
from rich.text import Text
from typing import Dict, Any

from collectors import TasksCollector
from utils.ui_helpers import update_table_preserving_scroll
from utils.logger import get_logger

logger = get_logger("tasks_tab")


class TasksExtendedTab(Vertical):
    """Tab displaying Cron jobs and Systemd Timers."""

    BINDINGS = [
        Binding("c", "show_cron", "Cron Jobs"),
        Binding("t", "show_timers", "Timers"),
    ]

    DEFAULT_CSS = """
    TasksExtendedTab {
        height: 1fr;
        padding: 0;
    }
    #tasks_header_container {
        height: 3;
        margin: 0;
        padding: 0 1;
        border: round $success;
        margin-bottom: 0;
    }
    #tasks_header {
        margin: 0;
        padding: 0;
        width: 100%;
    }
    #tasks_table {
        height: 1fr;
        margin: 0;
        padding: 0;
    }
    """

    def __init__(self, collector: TasksCollector):
        super().__init__()
        self.collector = collector
        self._show_cron = True  # True = Cron Jobs, False = Timers
        self._last_data = None

    def compose(self):
        with Static(id="tasks_header_container"):
            yield Label("[bold cyan]Cron Jobs[/bold cyan]", id="tasks_header")
        yield DataTable(id="tasks_table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Setup table and start updates."""
        self._setup_table_columns()
        self.update_data()
        self.set_interval(60, self.update_data)

    def _setup_table_columns(self) -> None:
        """Setup table columns based on current view mode."""
        try:
            table = self.query_one("#tasks_table", DataTable)
            table.clear(columns=True)

            if self._show_cron:
                table.add_columns("User", "Schedule", "Next Run", "Command")
            else:
                table.add_columns("Timer", "Enabled", "Active", "Next Run", "Last Run", "Description")
        except Exception as e:
            logger.error(f"Failed to setup table columns: {e}")

    def action_show_cron(self) -> None:
        """Switch to Cron Jobs view."""
        if self._show_cron:
            return  # Already showing cron
        self._show_cron = True
        self._setup_table_columns()
        self._update_view()

    def action_show_timers(self) -> None:
        """Switch to Timers view."""
        if not self._show_cron:
            return  # Already showing timers
        self._show_cron = False
        self._setup_table_columns()
        self._update_view()

    @work(exclusive=True, thread=True)
    def update_data(self) -> None:
        """Fetch data in background."""
        try:
            data = self.collector.update()
            self._last_data = data
            self.app.call_from_thread(self._update_view)
        except Exception as e:
            logger.error(f"Failed to update tasks data: {e}")

    def _update_view(self) -> None:
        """Update table with current view mode."""
        if not self._last_data:
            return

        try:
            table = self.query_one("#tasks_table", DataTable)
            header = self.query_one("#tasks_header", Label)

            # Get stats for header (always show both)
            cron_data = self._last_data.get('cron', {})
            cron_total = len(cron_data.get('all_jobs', []))

            timers_data = self._last_data.get('systemd_timers', {})
            timers_list = timers_data.get('timers', [])
            timers_total = len(timers_list)
            timers_enabled = sum(1 for t in timers_list if self._parse_timer_state(t.get('state', ''))[0] == 'enabled')
            timers_active = sum(1 for t in timers_list if t.get('next_run', 'n/a') != 'n/a')

            # Build header
            if self._show_cron:
                mode = "[bold cyan]► Cron Jobs[/bold cyan]"
            else:
                mode = "[bold cyan]► Timers[/bold cyan]"

            header_text = (
                f"{mode} │ "
                f"[dim]Cron:[/dim] [white]{cron_total}[/white] jobs │ "
                f"[dim]Timers:[/dim] [white]{timers_total}[/white] "
                f"([green]{timers_enabled} enabled[/green], [cyan]{timers_active} scheduled[/cyan])"
            )
            header.update(header_text)

            # Populate table
            if self._show_cron:
                self._populate_cron(table, self._last_data)
            else:
                self._populate_timers(table, self._last_data)
        except Exception as e:
            logger.error(f"Failed to update tasks view: {e}")

    def _parse_timer_state(self, state_str: str) -> tuple:
        """Parse timer state string into (enabled_state, preset).

        systemctl list-unit-files returns: 'enabled enabled', 'disabled enabled', 'static -', etc.
        """
        parts = state_str.split()
        enabled_state = parts[0] if parts else 'unknown'
        preset = parts[1] if len(parts) > 1 else '-'
        return enabled_state, preset

    # Colors for different users
    USER_COLORS = [
        'cyan', 'green', 'yellow', 'magenta', 'blue',
        'bright_cyan', 'bright_green', 'bright_magenta'
    ]

    def _get_user_color(self, user: str) -> str:
        """Get consistent color for a user."""
        if user == 'root':
            return 'bold red'
        # Hash username to get consistent color index
        color_idx = hash(user) % len(self.USER_COLORS)
        return self.USER_COLORS[color_idx]

    def _populate_cron(self, table: DataTable, data: Dict[str, Any]) -> None:
        """Populate table with cron jobs."""
        cron_data = data.get('cron', {})

        def populate(t):
            jobs = cron_data.get('all_jobs', [])
            if not jobs:
                t.add_row("No cron jobs found", "", "", "")
                return

            for job in jobs:
                try:
                    user = job.get('user', 'N/A')
                    sched = job.get('schedule', {}).get('human', 'N/A')
                    next_run = job.get('next_run_human', 'N/A')
                    command = job.get('command', 'N/A')

                    if user == 'root':
                        # Root: only username in red
                        t.add_row(
                            Text(user, style="bold red"),
                            sched,
                            next_run,
                            command
                        )
                    else:
                        # Other users: whole row in user color
                        user_color = self._get_user_color(user)
                        t.add_row(
                            Text(user, style=user_color),
                            Text(sched, style=user_color),
                            Text(next_run, style=user_color),
                            Text(command, style=user_color)
                        )
                except Exception as e:
                    logger.debug(f"Error processing cron job: {e}")
                    continue

        update_table_preserving_scroll(table, populate)

    def _populate_timers(self, table: DataTable, data: Dict[str, Any]) -> None:
        """Populate table with systemd timers."""
        timers_data = data.get('systemd_timers', {})

        def populate(t):
            timers = timers_data.get('timers', [])
            if not timers:
                t.add_row("No systemd timers found", "", "", "", "", "")
                return

            for tm in timers:
                try:
                    name = tm.get('name', 'N/A').replace('.timer', '')
                    state_raw = tm.get('state', 'unknown')
                    next_run = tm.get('next_run', 'n/a')
                    last_trigger = tm.get('last_trigger', 'n/a')
                    description = tm.get('description', '')

                    # Parse state into enabled_state and determine if active
                    enabled_state, _ = self._parse_timer_state(state_raw)
                    is_active = next_run != 'n/a'

                    # Color enabled state
                    if enabled_state == 'enabled':
                        enabled_text = Text(enabled_state, style="green")
                    elif enabled_state == 'disabled':
                        enabled_text = Text(enabled_state, style="red")
                    elif enabled_state == 'static':
                        enabled_text = Text(enabled_state, style="dim")
                    else:
                        enabled_text = Text(enabled_state, style="yellow")

                    # Color active state
                    if is_active:
                        active_text = Text("yes", style="bold green")
                    else:
                        active_text = Text("no", style="dim")

                    t.add_row(name, enabled_text, active_text, next_run, last_trigger, description)
                except Exception as e:
                    logger.debug(f"Error processing timer: {e}")
                    continue

        update_table_preserving_scroll(table, populate)
