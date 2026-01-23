from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog

class AnalysisModal(ModalScreen):
    DEFAULT_CSS = """
    AnalysisModal {
        align: center middle;
    }
    #analysis_dialog {
        width: 90%;
        height: 80%;
        border: thick $background 80%;
        background: $surface;
    }
    #analysis_output {
        height: 1fr;
        border: solid $primary;
        margin: 1 0;
    }
    """

    def __init__(self, output: str):
        super().__init__()
        self.output = output

    def compose(self):
        with Vertical(id="analysis_dialog"):
            yield Label("[bold]Fail2ban Analysis Report[/bold]")
            log = RichLog(id="analysis_output", highlight=True, markup=True)
            yield log
            yield Button("Close", variant="primary", id="close_btn")

    def on_mount(self) -> None:
        log = self.query_one("#analysis_output", RichLog)
        log.write(self.output)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_btn":
            self.dismiss()
