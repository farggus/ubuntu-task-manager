"""Confirmation modal dialog."""

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class ConfirmModal(ModalScreen[bool]):
    """Modal dialog for confirming dangerous actions."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
        background: $background 60%;
    }
    #confirm_dialog {
        width: 45;
        height: 13;
        border: round $error;
        background: $surface;
        padding: 0 2;
    }
    #confirm_title {
        text-align: center;
        width: 100%;
        height: 1;
        margin-bottom: 1;
    }
    #confirm_message {
        text-align: center;
        height: 3;
        margin-bottom: 1;
    }
    #confirm_buttons {
        align: center middle;
        width: 100%;
        height: 3;
    }
    #confirm_buttons Button {
        margin: 0 1;
        width: 10;
        height: 3;
        min-width: 10;
    }
    #cancel {
        border: tall $secondary;
        color: $text;
        background: transparent;
        text-style: none;
    }
    #cancel:hover {
        background: $secondary;
        text-style: none;
    }
    #cancel:focus {
        background: transparent;
        text-style: none;
    }
    #cancel:focus:hover {
        background: $secondary;
        text-style: none;
    }
    #confirm {
        border: tall $error;
        color: $error;
        background: transparent;
        text-style: none;
    }
    #confirm:hover {
        background: $error;
        color: $text;
        text-style: none;
    }
    #confirm:focus {
        background: transparent;
        text-style: none;
    }
    """

    def __init__(self, title: str, message: str, confirm_label: str = "Confirm"):
        super().__init__()
        self.title_text = title
        self.message = message
        self.confirm_label = confirm_label

    def compose(self):
        with Vertical(id="confirm_dialog"):
            yield Label(f"[bold]{self.title_text}[/bold]", id="confirm_title")
            yield Static(self.message, id="confirm_message")
            with Horizontal(id="confirm_buttons"):
                yield Button("Cancel", id="cancel")
                yield Button(self.confirm_label, id="confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(False)
        elif event.key == "enter":
            self.dismiss(True)
