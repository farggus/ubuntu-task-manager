"""Whitelist management modal dialog."""

from typing import List, Optional

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView


class WhitelistModal(ModalScreen[Optional[str]]):
    """Modal dialog for managing IP whitelist."""

    DEFAULT_CSS = """
    WhitelistModal {
        align: center middle;
        background: $background 60%;
    }
    #whitelist_dialog {
        width: 50;
        height: 22;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }
    #whitelist_title {
        text-align: center;
        width: 100%;
        height: 1;
        margin-bottom: 1;
    }
    #whitelist_list {
        height: 8;
        border: solid $primary;
        margin-bottom: 1;
    }
    #whitelist_input_row {
        height: 3;
        margin-bottom: 1;
    }
    #whitelist_input {
        width: 1fr;
    }
    #whitelist_buttons {
        align: center middle;
        width: 100%;
        height: 3;
    }
    #whitelist_buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, whitelist: List[str], selected_ip: Optional[str] = None):
        super().__init__()
        self._whitelist = whitelist.copy()
        self._selected_ip = selected_ip
        self._action: Optional[str] = None

    def compose(self):
        with Vertical(id="whitelist_dialog"):
            yield Label("[bold]Manage IP Whitelist[/bold]", id="whitelist_title")
            yield ListView(*[ListItem(Label(ip)) for ip in self._whitelist], id="whitelist_list")
            with Horizontal(id="whitelist_input_row"):
                yield Input(placeholder="Enter IP to whitelist...", id="whitelist_input", value=self._selected_ip or "")
                yield Button("Add", id="add_btn", variant="success")
            with Horizontal(id="whitelist_buttons"):
                yield Button("Remove Selected", id="remove_btn", variant="error")
                yield Button("Close", id="close_btn")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#whitelist_input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_btn":
            self.dismiss(None)
        elif event.button.id == "add_btn":
            ip_input = self.query_one("#whitelist_input", Input)
            ip = ip_input.value.strip()
            if ip and ip not in self._whitelist:
                self.dismiss(f"add:{ip}")
            elif ip in self._whitelist:
                self.notify("IP already in whitelist", severity="warning")
        elif event.button.id == "remove_btn":
            listview = self.query_one("#whitelist_list", ListView)
            if listview.highlighted_child:
                idx = listview.index
                if 0 <= idx < len(self._whitelist):
                    ip = self._whitelist[idx]
                    self.dismiss(f"remove:{ip}")

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter":
            ip_input = self.query_one("#whitelist_input", Input)
            ip = ip_input.value.strip()
            if ip and ip not in self._whitelist:
                self.dismiss(f"add:{ip}")
