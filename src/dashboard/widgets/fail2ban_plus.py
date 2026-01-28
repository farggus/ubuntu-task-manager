"""
Fail2ban+ tab widget - Placeholder for new implementation.

The actual database management is in the F2BDatabaseModal.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Static


class Fail2banPlusTab(Vertical, can_focus=True):
    """
    Fail2Ban+ tab - placeholder with keybinding to open database modal.
    """
    
    BINDINGS = [
        Binding("d", "open_db_modal", "F2B-db", show=True),
    ]
    
    def compose(self) -> ComposeResult:
        """Build the UI."""
        yield Static("")
    
    def action_open_db_modal(self) -> None:
        """Open the F2B Database Manager modal."""
        from dashboard.widgets.f2b_db_manage_modal import F2BDatabaseModal
        self.app.push_screen(F2BDatabaseModal())
