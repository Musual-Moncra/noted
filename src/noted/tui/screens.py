import unicodedata
from typing import Optional, Tuple
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from noted.tui.widgets import VietnameseInput

class NewNoteModal(ModalScreen[Optional[Tuple[str, list[str]]]]):
    """Modal dialog to create a new note with Title and Tags."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("Create New Note", classes="dialog-title")
            yield Label("Title:")
            yield VietnameseInput(placeholder="e.g. Architecture Ideas", id="input-title")
            yield Label("Tags (comma-separated):")
            yield VietnameseInput(placeholder="e.g. dev, python, cli", id="input-tags")
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
        raw_title = self.query_one("#input-title", Input).value.strip()
        title = unicodedata.normalize("NFC", raw_title) if raw_title else "Untitled Note"
        tags_raw = self.query_one("#input-tags", Input).value.strip()
        tags = [unicodedata.normalize("NFC", t.strip()) for t in tags_raw.split(",") if t.strip()]
        self.dismiss((title, tags))


class ConfirmDeleteModal(ModalScreen[bool]):
    """Confirmation modal before deleting a note."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
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
        Binding("escape", "dismiss_help", "Close", priority=True),
        Binding("question_mark", "dismiss_help", "Close", priority=True),
        Binding("enter", "dismiss_help", "Close", priority=True),
    ]

    SHORTCUTS = [
        ("[bold cyan]ctrl+p / f2[/bold cyan]", "Toggle Preview & Edit (Auto-saves note)"),
        ("[bold cyan]ctrl+w[/bold cyan]", "Toggle Split Screen (Side-by-side live preview)"),
        ("[bold cyan]escape[/bold cyan]", "Return to View mode (Auto-saves) / Close modal"),
        ("[bold cyan]e[/bold cyan]", "Enter in-terminal Edit mode"),
        ("[bold cyan]ctrl+s[/bold cyan]", "Save note changes in TUI editor"),
        ("[bold cyan]n[/bold cyan]", "Create a new note"),
        ("[bold cyan]j[/bold cyan]", "Open/create today's journal"),
        ("[bold cyan]ctrl+b[/bold cyan]", "Bold selection or insert **bold**"),
        ("[bold cyan]ctrl+i[/bold cyan]", "Italic selection or insert *italic*"),
        ("[bold cyan]ctrl+k[/bold cyan]", "Code selection or insert `code`"),
        ("[bold cyan]ctrl+h[/bold cyan]", "Insert markdown # Heading"),
        ("[bold cyan]ctrl+t[/bold cyan]", "Insert interactive - [ ] Todo checkbox"),
        ("[bold cyan]ctrl+e[/bold cyan]", "Open note in external $EDITOR"),
        ("[bold cyan]d[/bold cyan]", "Delete current note"),
        ("[bold cyan]/[/bold cyan]", "Focus search bar"),
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


class ColorFormatModal(ModalScreen[Optional[str]]):
    """Modal dialog to pick color formats, callouts, or diff highlights."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("1", "select_opt_1", "Green"),
        Binding("2", "select_opt_2", "Blue"),
        Binding("3", "select_opt_3", "Yellow"),
        Binding("4", "select_opt_4", "Red"),
        Binding("5", "select_opt_5", "Purple"),
        Binding("6", "select_opt_6", "Diff Green"),
        Binding("7", "select_opt_7", "Diff Red"),
        Binding("8", "select_opt_8", "HTML Red"),
        Binding("9", "select_opt_9", "HTML Blue"),
    ]

    TEMPLATES = {
        "1": "> [!TIP]\n> {text}\n",
        "2": "> [!NOTE]\n> {text}\n",
        "3": "> [!WARNING]\n> {text}\n",
        "4": "> [!CAUTION]\n> {text}\n",
        "5": "> [!IMPORTANT]\n> {text}\n",
        "6": "```diff\n+ {text}\n```\n",
        "7": "```diff\n- {text}\n```\n",
        "8": '<span style="color: #e74c3c">{text}</span>',
        "9": '<span style="color: #3498db">{text}</span>',
    }

    OPTIONS = [
        ("1", "btn-c-1", "🟢 Xanh lá (Tip / Success)", "1"),
        ("2", "btn-c-2", "🔵 Xanh dương (Note / Info)", "2"),
        ("3", "btn-c-3", "🟡 Vàng (Cảnh báo / Warning)", "3"),
        ("4", "btn-c-4", "🔴 Đỏ (Nguy hiểm / Caution)", "4"),
        ("5", "btn-c-5", "🟣 Tím (Quan trọng / Important)", "5"),
        ("6", "btn-c-6", "🟩 Diff Xanh (Dòng thêm vào +)", "6"),
        ("7", "btn-c-7", "🟥 Diff Đỏ (Dòng lỗi/xóa -)", "7"),
        ("8", "btn-c-8", "🔴 Thẻ HTML Đỏ (#e74c3c)", "8"),
        ("9", "btn-c-9", "🔵 Thẻ HTML Xanh (#3498db)", "9"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("🎨 Chọn Định Dạng Màu Sắc Chữ", classes="dialog-title")
            yield Static("[dim]Bấm số [bold cyan]1-9[/bold cyan] hoặc click chuột để áp dụng màu:[/dim]\n")
            for key, btn_id, label, opt_key in self.OPTIONS:
                with Horizontal(classes="color-choice-row"):
                    yield Static(f"[bold cyan][{key}][/bold cyan]", classes="key-badge-small")
                    yield Button(label, id=btn_id, classes="color-choice-btn")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        for key, btn_id, label, opt_key in self.OPTIONS:
            if bid == btn_id:
                self.dismiss(self.TEMPLATES[opt_key])
                return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_select_opt_1(self) -> None: self.dismiss(self.TEMPLATES["1"])
    def action_select_opt_2(self) -> None: self.dismiss(self.TEMPLATES["2"])
    def action_select_opt_3(self) -> None: self.dismiss(self.TEMPLATES["3"])
    def action_select_opt_4(self) -> None: self.dismiss(self.TEMPLATES["4"])
    def action_select_opt_5(self) -> None: self.dismiss(self.TEMPLATES["5"])
    def action_select_opt_6(self) -> None: self.dismiss(self.TEMPLATES["6"])
    def action_select_opt_7(self) -> None: self.dismiss(self.TEMPLATES["7"])
    def action_select_opt_8(self) -> None: self.dismiss(self.TEMPLATES["8"])
    def action_select_opt_9(self) -> None: self.dismiss(self.TEMPLATES["9"])

