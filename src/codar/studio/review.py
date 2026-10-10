"""Comparação de alterações e seleção de versões anteriores."""

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList, RichLog, SelectionList, Static
from textual.widgets.option_list import Option

from codar.workspace import Change, diff, hunks, select_hunks


class ReviewScreen(ModalScreen[list[str] | None]):
    DEFAULT_CSS = """
    ReviewScreen { align: center middle; background: $codar-bg 75%; }
    #review-card { width: 120; max-width: 95%; height: 92%; border: round $codar-orange; padding: 1 2; }
    #review-hunks { height: 7; margin: 1 0; }
    #review-diff { height: 1fr; border: solid $codar-line; }
    #review-status { height: auto; max-height: 4; }
    #review-buttons { height: 3; margin-top: 1; }
    #review-buttons Button { margin-right: 2; }
    """
    BINDINGS = [("escape", "cancel", "Cancelar")]

    def __init__(self, changes: list[Change], checks: list[dict] | None = None):
        super().__init__()
        self.changes = changes
        self.checks = checks or []
        self.hunks = [h for change in changes for h in hunks(change)]

    def compose(self) -> ComposeResult:
        with Vertical(id="review-card"):
            yield Label("REVISAR ALTERAÇÕES · selecione os trechos que deseja aplicar")
            status = "\n".join(f"{c['path']}: {c['status']} {c.get('message', '').strip()}" for c in self.checks)
            yield Static(Text(status or "O original será guardado no histórico."), id="review-status")
            yield SelectionList(*[(f"{h['path']} · linha {h['start']}", h["id"], True) for h in self.hunks], id="review-hunks")
            yield RichLog(id="review-diff", wrap=False, markup=False, max_lines=4000)
            with Horizontal(id="review-buttons"):
                yield Button("Aplicar selecionados", id="review-apply", variant="success")
                yield Button("Cancelar", id="review-cancel")

    def on_mount(self):
        self.render_diff()
        self.query_one("#review-hunks", SelectionList).focus()

    def on_selection_list_selected_changed(self, event):
        self.render_diff()

    def render_diff(self):
        selected = set(self.query_one("#review-hunks", SelectionList).selected)
        changes = [select_hunks(change, selected) for change in self.changes]
        log = self.query_one("#review-diff", RichLog)
        log.clear()
        for line in diff(changes).splitlines():
            color = "green" if line.startswith("+") else "red" if line.startswith("-") else "cyan" if line.startswith("@@") else "white"
            log.write(Text(line, style=color))
        self.query_one("#review-apply", Button).disabled = not selected

    def on_button_pressed(self, event: Button.Pressed):
        selected = list(self.query_one("#review-hunks", SelectionList).selected)
        self.dismiss(selected if event.button.id == "review-apply" else None)

    def action_cancel(self):
        self.dismiss(None)


class ChoiceScreen(ModalScreen[str | None]):
    DEFAULT_CSS = """
    ChoiceScreen { align: center middle; background: $codar-bg 75%; }
    #choice-card { width: 100; max-width: 95%; height: 70%; border: round $codar-orange; padding: 1 2; }
    #choices { height: 1fr; margin-top: 1; }
    """
    BINDINGS = [("escape", "cancel", "Cancelar")]

    def __init__(self, title: str, choices: list[tuple[str, str]]):
        super().__init__()
        self.title_text, self.choices = title, choices

    def compose(self) -> ComposeResult:
        with Vertical(id="choice-card"):
            yield Label(Text(self.title_text))
            yield OptionList(*[Option(Text(label), id=identity) for identity, label in self.choices], id="choices")

    def on_mount(self):
        self.query_one("#choices", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        self.dismiss(event.option.id)

    def action_cancel(self):
        self.dismiss(None)
