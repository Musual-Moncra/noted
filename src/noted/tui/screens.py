from typing import Optional, Tuple
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

class NewNoteModal(ModalScreen[Optional[Tuple[str, list[str]]]]):
    """Modal dialog to create a new note with Title and Tags."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("Create New Note", classes="dialog-title")
            yield Label("Title:")
            yield Input(placeholder="e.g. Architecture Ideas", id="input-title")
            yield Label("Tags (comma-separated):")
            yield Input(placeholder="e.g. dev, python, cli", id="input-tags")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Create", id="btn-create", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#input-title", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-create":
            self._submit()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "input-title":
            self.query_one("#input-tags", Input).focus()
        else:
            self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        title = self.query_one("#input-title", Input).value.strip() or "Untitled Note"
        tags_raw = self.query_one("#input-tags", Input).value.strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        self.dismiss((title, tags))


class ConfirmDeleteModal(ModalScreen[bool]):
    """Confirmation modal before deleting a note."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, note_title: str):
        super().__init__()
        self.note_title = note_title

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("Delete Note", classes="dialog-title")
            yield Static(f"Are you sure you want to permanently delete:\n[bold red]{self.note_title}[/bold red]?")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Delete", id="btn-delete", variant="error")

    def on_mount(self) -> None:
        self.query_one("#btn-cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-delete":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class HelpModal(ModalScreen[None]):
    """Modal displaying keyboard shortcuts and usage tips."""

    BINDINGS = [
        Binding("escape", "dismiss_help", "Close"),
        Binding("question_mark", "dismiss_help", "Close"),
        Binding("enter", "dismiss_help", "Close"),
    ]

    SHORTCUTS = [
        ("[bold cyan]n[/bold cyan]", "Create a new note"),
        ("[bold cyan]j[/bold cyan]", "Open/create today's journal"),
        ("[bold cyan]e[/bold cyan]", "Toggle in-terminal Edit / View mode"),
        ("[bold cyan]ctrl+s[/bold cyan]", "Save note changes in TUI editor"),
        ("[bold cyan]ctrl+b[/bold cyan]", "Bold selection or insert **bold**"),
        ("[bold cyan]ctrl+i[/bold cyan]", "Italic selection or insert *italic*"),
        ("[bold cyan]ctrl+k[/bold cyan]", "Code selection or insert `code`"),
        ("[bold cyan]ctrl+h[/bold cyan]", "Insert markdown # Heading"),
        ("[bold cyan]ctrl+t[/bold cyan]", "Insert interactive - [ ] Todo checkbox"),
        ("[bold cyan]ctrl+e[/bold cyan]", "Open note in external $EDITOR"),
        ("[bold cyan]d[/bold cyan]", "Delete current note"),
        ("[bold cyan]/[/bold cyan]", "Focus search bar"),
        ("[bold cyan]escape[/bold cyan]", "Unfocus search / Exit edit mode / Close modal"),
        ("[bold cyan]?[/bold cyan]", "Show this help screen"),
        ("[bold cyan]q / ctrl+q[/bold cyan]", "Quit application"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("Keyboard Shortcuts & Help", classes="dialog-title")
            for key, desc in self.SHORTCUTS:
                with Horizontal(classes="help-row"):
                    yield Static(key, classes="key-badge")
                    yield Static(desc)
            with Horizontal(classes="modal-buttons"):
                yield Button("Close", id="btn-close", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#btn-close", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
