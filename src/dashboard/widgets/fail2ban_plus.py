"""
Fail2ban+ tab widget - Placeholder for new implementation.

The actual database management is in the F2BDatabaseModal.
Press [D] to open the database manager.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Center
from textual.widgets import Label, Static


class Fail2banPlusTab(Vertical):
    """
    Fail2Ban+ tab - placeholder with keybinding to open database modal.
    """
    
    BINDINGS = [
        Binding("d", "open_db_modal", "F2B Database"),
    ]
    
    def compose(self) -> ComposeResult:
        """Build the UI."""
        with Center():
            with Vertical():
                yield Static("")
                yield Label("�️ Fail2Ban+ (v2)", classes="header")
                yield Static("")
                yield Static("Press [D] to open F2B Database Manager", classes="muted")
    
    def action_open_db_modal(self) -> None:
        """Open the F2B Database Manager modal."""
        from dashboard.widgets.f2b_db_manage_modal import F2BDatabaseModal
        self.app.push_screen(F2BDatabaseModal())
