"""Logging tab widget."""

import os
import re
from collections import Counter, deque
from datetime import datetime
from typing import Optional, Set, Tuple

from rich.markup import escape
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Input, Label, RichLog, Select, Static

from const import LOG_DIR, LOG_FILE


class LoggingTab(Vertical):
    """Tab displaying application logs with filtering."""

    BINDINGS = [
        Binding("d", "toggle_level('DEBUG')", "DEBUG"),
        Binding("i", "toggle_level('INFO')", "INFO"),
        Binding("w", "toggle_level('WARNING')", "WARNING"),
        Binding("e", "toggle_level('ERROR')", "ERROR"),
        Binding("c", "toggle_level('CRITICAL')", "CRITICAL"),
        Binding("x", "reset_filters", "Reset"),
        Binding("f", "toggle_follow", "Follow"),
        Binding("g", "scroll_top", "Top"),
        Binding("G", "scroll_bottom", "Bottom", key_display="G"),
        Binding("s", "export_logs", "Export"),
    ]

    DEFAULT_CSS = """
    LoggingTab {
        height: 1fr;
        padding: 0;
    }

    #log_header_container {
        height: 3;
        margin: 0;
        padding: 0 1;
        border: round $success;
        margin-bottom: 0;
    }

    #log_header {
        margin: 0;
        padding: 0;
        width: auto;
    }

    #log_search {
        width: 1fr;
        margin-left: 2;
        border: none;
        background: transparent;
        color: $text;
    }

    #log_toolbar {
        height: 3;
        padding: 0 1;
        background: $boost;
    }

    #log_module_filter {
        width: 100%;
        border: none;
        background: transparent;
    }

    #log_view {
        height: 1fr;
        scrollbar-gutter: stable;
        border-title-align: left;
    }
    """

    def __init__(self):
        super().__init__()
        self.last_size = 0
        # Store (line, level, module) tuples for caching
        self.all_logs: deque[Tuple[str, str, str]] = deque(maxlen=5000)

        self.all_levels_set = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        self.active_levels: Set[str] = self.all_levels_set.copy()
        self.is_custom_filter = False
        self.search_term = ""
        self.module_filter: Optional[str] = None  # None = all modules
        self.shown_count = 0
        self.total_count = 0

        # Statistics by level
        self.level_counts: Counter = Counter()

        # Known modules for filter dropdown
        self.known_modules: Set[str] = set()

        # Debounce timer for search
        self._search_timer: Optional[Timer] = None

        # Auto-scroll to new logs
        self.auto_scroll = True

    def compose(self) -> ComposeResult:
        with Horizontal(id="log_header_container"):
            yield Label("[bold cyan]Loading logs...[/bold cyan]", id="log_header")
            yield Input(placeholder="Search logs...", id="log_search")

        with Horizontal(id="log_toolbar"):
            yield Select(
                [("All modules", None)],
                value=None,
                id="log_module_filter",
                allow_blank=False,
            )

        yield RichLog(id="log_view", highlight=True, markup=True)
        yield Label(f"[dim]{LOG_FILE}[/dim]", classes="help-text")

    def on_mount(self) -> None:
        """Initialize log view and start updates."""
        self._update_border_title()
        self._update_header()
        self.update_logs()
        self.set_interval(1.0, self.update_logs)

    def action_reset_filters(self) -> None:
        """Reset all filters to default (Show All)."""
        self.active_levels = self.all_levels_set.copy()
        self.is_custom_filter = False
        self.search_term = ""
        self.module_filter = None

        inp = self.query_one("#log_search", Input)
        inp.value = ""

        module_select = self.query_one("#log_module_filter", Select)
        module_select.value = None

        self.refresh_log_view()
        self.notify("Filters reset: Showing ALL logs")

    def action_toggle_level(self, level: str) -> None:
        """Toggle log level filter. First press selects only that level, subsequent presses add/remove levels."""
        if self.is_custom_filter and level in self.active_levels:
            # Remove level from filter
            self.active_levels.discard(level)
            if not self.active_levels:
                # If no levels left, reset to all
                self.active_levels = self.all_levels_set.copy()
                self.is_custom_filter = False
                self.notify("Filter reset: Showing ALL logs")
            else:
                self.notify(f"Removed {level} from filter")
        else:
            if not self.is_custom_filter:
                # First custom selection - show only this level
                self.active_levels = {level}
            else:
                # Add level to existing filter
                self.active_levels.add(level)
            self.is_custom_filter = True
            self.notify(f"Filter: {', '.join(sorted(self.active_levels))}")

        self.refresh_log_view()

    def action_toggle_follow(self) -> None:
        """Toggle auto-scroll to new logs."""
        self.auto_scroll = not self.auto_scroll
        status = "ON" if self.auto_scroll else "OFF"
        self.notify(f"Auto-scroll: {status}")
        self._update_border_title()

        if self.auto_scroll:
            # Scroll to bottom when enabling
            log_view = self.query_one("#log_view", RichLog)
            log_view.scroll_end(animate=False)

    def action_scroll_top(self) -> None:
        """Scroll to the beginning of logs."""
        log_view = self.query_one("#log_view", RichLog)
        log_view.scroll_home(animate=False)
        self.auto_scroll = False
        self._update_border_title()

    def action_scroll_bottom(self) -> None:
        """Scroll to the end of logs."""
        log_view = self.query_one("#log_view", RichLog)
        log_view.scroll_end(animate=False)

    @work(thread=True)
    def action_export_logs(self) -> None:
        """Export filtered logs to a file."""
        if not self.all_logs:
            self.app.call_from_thread(self.notify, "No logs to export", severity="warning")
            return

        # Build filtered logs
        filtered_lines = []
        for line, level, module in self.all_logs:
            if self._should_show(line, level, module):
                filtered_lines.append(line)

        if not filtered_lines:
            self.app.call_from_thread(self.notify, "No logs match current filters", severity="warning")
            return

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = os.path.join(LOG_DIR, f"export_{timestamp}.log")

        try:
            with open(export_file, "w", encoding="utf-8") as f:
                f.write("\n".join(filtered_lines))
            self.app.call_from_thread(
                self.notify, f"Exported {len(filtered_lines)} lines to {export_file}"
            )
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Export failed: {e}", severity="error"
            )

    @on(Input.Changed, "#log_search")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input changes with debounce."""
        self.search_term = event.value.lower()

        # Cancel existing timer
        if self._search_timer:
            self._search_timer.stop()

        # Start new debounce timer (300ms)
        self._search_timer = self.set_timer(0.3, self._do_search_refresh)

    def _do_search_refresh(self) -> None:
        """Execute search refresh after debounce."""
        self._search_timer = None
        self.refresh_log_view()

    @on(Select.Changed, "#log_module_filter")
    def on_module_changed(self, event: Select.Changed) -> None:
        """Handle module filter changes."""
        self.module_filter = event.value
        self.refresh_log_view()

    def _update_border_title(self) -> None:
        """Update border title with filter status and counts."""
        log_view = self.query_one("#log_view", RichLog)

        # Build filter indicator
        if not self.is_custom_filter:
            filter_text = "ALL"
            filter_style = "cyan"
        else:
            abbrev = {"DEBUG": "D", "INFO": "I", "WARNING": "W", "ERROR": "E", "CRITICAL": "C"}
            level_order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            filter_text = "".join(
                abbrev[lvl] for lvl in level_order if lvl in self.active_levels
            )
            filter_style = "yellow"

        # Module indicator
        module_text = ""
        if self.module_filter:
            module_text = f" [magenta]{self.module_filter}[/magenta]"

        # Follow indicator
        follow_text = " [green]●[/green]" if self.auto_scroll else " [dim]○[/dim]"

        # Format: "Logs │ [FILTER] module shown/total ●"
        log_view.border_title = (
            f"[bold]Logs[/bold] │ [{filter_style}]{filter_text}[/{filter_style}]"
            f"{module_text} [dim]{self.shown_count}/{self.total_count}[/dim]{follow_text}"
        )

    def _update_header(self) -> None:
        """Update header with level statistics."""
        header = self.query_one("#log_header", Label)

        d = self.level_counts.get("DEBUG", 0)
        i = self.level_counts.get("INFO", 0)
        w = self.level_counts.get("WARNING", 0)
        e = self.level_counts.get("ERROR", 0)
        c = self.level_counts.get("CRITICAL", 0)

        header.update(
            f"[grey50]DEBUG:{d}[/grey50] "
            f"[green]INFO:{i}[/green] "
            f"[yellow]WARN:{w}[/yellow] "
            f"[red]ERROR:{e}[/red] "
            f"[bold red]CRIT:{c}[/bold red]"
        )

    def _update_module_select(self) -> None:
        """Update module filter dropdown with known modules."""
        module_select = self.query_one("#log_module_filter", Select)
        current_value = module_select.value

        # Build options: "All modules" + sorted module names
        options = [("All modules", None)]
        for mod in sorted(self.known_modules):
            # Show short name without "utm." prefix
            short_name = mod.replace("utm.", "") if mod.startswith("utm.") else mod
            options.append((short_name, mod))

        module_select.set_options(options)

        # Restore selection if still valid
        if current_value in self.known_modules or current_value is None:
            module_select.value = current_value

    def _parse_level(self, line: str) -> str:
        """Extract log level from line."""
        if " - DEBUG - " in line or " DEBUG " in line:
            return "DEBUG"
        if " - INFO - " in line or " INFO " in line:
            return "INFO"
        if " - WARNING - " in line or " WARNING " in line:
            return "WARNING"
        if " - ERROR - " in line or " ERROR " in line:
            return "ERROR"
        if " - CRITICAL - " in line or " CRITICAL " in line:
            return "CRITICAL"
        return "UNKNOWN"

    def _parse_module(self, line: str) -> str:
        """Extract module name from line. Format: [utm.module_name]"""
        match = re.search(r"\[([^\]]+)\]", line)
        if match:
            return match.group(1)
        return "unknown"

    def _should_show(self, line: str, level: str, module: str) -> bool:
        """Check if line matches all filters."""
        # Level filter
        if level != "UNKNOWN" and level not in self.active_levels:
            return False

        # Module filter
        if self.module_filter and module != self.module_filter:
            return False

        # Search filter
        if self.search_term and self.search_term not in line.lower():
            return False

        return True

    def refresh_log_view(self) -> None:
        """Clear and rebuild log view based on filters."""
        log_view = self.query_one("#log_view", RichLog)
        log_view.clear()

        self.total_count = len(self.all_logs)
        self.shown_count = 0

        for line, level, module in self.all_logs:
            if self._should_show(line, level, module):
                styled_line = self._colorize_line(line, level)
                log_view.write(styled_line)
                self.shown_count += 1

        self._update_border_title()

    def _colorize_line(self, line: str, level: str) -> str:
        """Add color markup to log line with search term highlighting."""
        color_map = {
            "DEBUG": "grey50",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }
        color = color_map.get(level, "white")

        escaped_line = escape(line)

        # Highlight search term if present
        if self.search_term:
            # Case-insensitive replacement with highlighting
            pattern = re.compile(re.escape(self.search_term), re.IGNORECASE)
            escaped_line = pattern.sub(
                lambda m: f"[reverse]{m.group()}[/reverse]",
                escaped_line
            )

        return f"[{color}]{escaped_line}[/{color}]"

    @work(exclusive=True, thread=True)
    def update_logs(self) -> None:
        """Read new lines from log file."""
        if not os.path.exists(LOG_FILE):
            return

        try:
            current_size = os.path.getsize(LOG_FILE)

            # Reset if file rotated
            if current_size < self.last_size:
                self.last_size = 0
                self.all_logs.clear()
                self.total_count = 0
                self.shown_count = 0
                self.level_counts.clear()
                self.known_modules.clear()
                self.app.call_from_thread(self.query_one("#log_view", RichLog).clear)
                self.app.call_from_thread(self._update_border_title)
                self.app.call_from_thread(self._update_header)
                self.app.call_from_thread(self._update_module_select)

            if current_size > self.last_size:
                with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(self.last_size)
                    new_lines = f.readlines()
                    self.last_size = current_size

                    if new_lines:
                        log_view = self.query_one("#log_view", RichLog)

                        # Get last known level from previous log entry for context continuity
                        last_level = self.all_logs[-1][1] if self.all_logs else "UNKNOWN"
                        last_module = self.all_logs[-1][2] if self.all_logs else "unknown"

                        new_shown = 0
                        modules_added = False

                        for line in new_lines:
                            clean_line = line.rstrip()
                            if clean_line:
                                level = self._parse_level(clean_line)
                                module = self._parse_module(clean_line)

                                # Inherit level/module from previous line (for tracebacks)
                                if level == "UNKNOWN" and last_level != "UNKNOWN":
                                    level = last_level
                                    module = last_module
                                elif level != "UNKNOWN":
                                    last_level = level
                                    last_module = module

                                # Update statistics
                                if level != "UNKNOWN":
                                    self.level_counts[level] += 1

                                # Track modules
                                if module not in self.known_modules and module != "unknown":
                                    self.known_modules.add(module)
                                    modules_added = True

                                # Store tuple (line, level, module) for caching
                                self.all_logs.append((clean_line, level, module))

                                if self._should_show(clean_line, level, module):
                                    styled = self._colorize_line(clean_line, level)
                                    self.app.call_from_thread(log_view.write, styled)
                                    new_shown += 1

                        # Update counts and UI
                        self.total_count = len(self.all_logs)
                        self.shown_count += new_shown
                        self.app.call_from_thread(self._update_border_title)
                        self.app.call_from_thread(self._update_header)

                        if modules_added:
                            self.app.call_from_thread(self._update_module_select)

                        # Auto-scroll to bottom if enabled
                        if self.auto_scroll and new_shown > 0:
                            self.app.call_from_thread(log_view.scroll_end, animate=False)

        except Exception:
            pass
