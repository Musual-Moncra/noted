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


class RenameNoteModal(ModalScreen[Optional[str]]):
    """Modal dialog to rename an existing note."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(self, current_title: str):
        super().__init__()
        self.current_title = current_title

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("Rename Note", classes="dialog-title")
            yield Label("New Title:")
            yield VietnameseInput(value=self.current_title, placeholder="Enter new note title...", id="input-rename-title")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Rename", id="btn-rename", variant="primary")

    def on_mount(self) -> None:
        inp = self.query_one("#input-rename-title", VietnameseInput)
        inp.focus()
        inp.cursor_position = len(inp.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-rename":
            self._submit()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        raw_title = self.query_one("#input-rename-title", VietnameseInput).value.strip()
        title = unicodedata.normalize("NFC", raw_title) if raw_title else self.current_title
        self.dismiss(title)


class UnlockNoteModal(ModalScreen[Optional[str]]):
    """Modal dialog to enter password to unlock an encrypted note."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(self, note_title: str):
        super().__init__()
        self.note_title = note_title

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("🔓 Mở Khóa Ghi Chú", classes="dialog-title")
            yield Static(f"Ghi chú: [bold cyan]{self.note_title}[/bold cyan]")
            yield Label("Mật khẩu:")
            yield VietnameseInput(password=True, placeholder="Nhập mật khẩu...", id="input-unlock-password")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Mở khóa", id="btn-unlock", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#input-unlock-password", VietnameseInput).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-unlock":
            self._submit()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        pwd = self.query_one("#input-unlock-password", VietnameseInput).value
        self.dismiss(pwd if pwd else None)


class LockNoteModal(ModalScreen[Optional[str]]):
    """Modal dialog to set a password on an unencrypted note."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(self, note_title: str):
        super().__init__()
        self.note_title = note_title

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("🔒 Đặt Mật Khẩu Bảo Vệ Ghi Chú", classes="dialog-title")
            yield Static(f"Ghi chú: [bold cyan]{self.note_title}[/bold cyan]")
            yield Label("Mật khẩu mới:")
            yield VietnameseInput(password=True, placeholder="Nhập mật khẩu...", id="input-lock-pass1")
            yield Label("Xác nhận mật khẩu:")
            yield VietnameseInput(password=True, placeholder="Nhập lại mật khẩu...", id="input-lock-pass2")
            yield Static("", id="lock-error-msg", classes="error-msg")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Khóa ghi chú", id="btn-confirm-lock", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#input-lock-pass1", VietnameseInput).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm-lock":
            self._submit()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "input-lock-pass1":
            self.query_one("#input-lock-pass2", VietnameseInput).focus()
        else:
            self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        p1 = self.query_one("#input-lock-pass1", VietnameseInput).value
        p2 = self.query_one("#input-lock-pass2", VietnameseInput).value
        if not p1:
            self.query_one("#lock-error-msg", Static).update("[bold red]Mật khẩu không được để trống![/bold red]")
            return
        if p1 != p2:
            self.query_one("#lock-error-msg", Static).update("[bold red]Mật khẩu xác nhận không khớp![/bold red]")
            return
        self.dismiss(p1)


class ManageLockModal(ModalScreen[Optional[str]]):
    """Modal to manage an unlocked encrypted note: Change Password, Remove Lock, or Relock Now."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("1", "choose_change_password", "Đổi mật khẩu"),
        Binding("2", "choose_remove_lock", "Bỏ khóa"),
        Binding("3", "choose_relock", "Khóa lại ngay"),
    ]

    def __init__(self, note_title: str):
        super().__init__()
        self.note_title = note_title

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("🔐 Quản Lý Khóa Ghi Chú", classes="dialog-title")
            yield Static(f"Ghi chú: [bold cyan]{self.note_title}[/bold cyan]")
            yield Static("[dim]Chọn thao tác bảo mật bạn muốn thực hiện:[/dim]\n")
            with Vertical(id="manage-lock-options"):
                yield Button("🔑 1. Đổi mật khẩu mới", id="btn-opt-change-pass", variant="primary")
                yield Button("🔓 2. Bỏ khóa (Gỡ mật khẩu vĩnh viễn)", id="btn-opt-remove-lock", variant="warning")
                yield Button("🔒 3. Khóa lại ngay lập tức", id="btn-opt-relock", variant="default")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-opt-change-pass":
            self.dismiss("change_password")
        elif event.button.id == "btn-opt-remove-lock":
            self.dismiss("remove_lock")
        elif event.button.id == "btn-opt-relock":
            self.dismiss("relock")
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def action_choose_change_password(self) -> None:
        self.dismiss("change_password")

    def action_choose_remove_lock(self) -> None:
        self.dismiss("remove_lock")

    def action_choose_relock(self) -> None:
        self.dismiss("relock")

    def action_cancel(self) -> None:
        self.dismiss(None)


class ChangePasswordModal(ModalScreen[Optional[str]]):
    """Modal dialog to enter and confirm new password."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(self, note_title: str):
        super().__init__()
        self.note_title = note_title

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("🔑 Đổi Mật Khẩu Ghi Chú", classes="dialog-title")
            yield Static(f"Ghi chú: [bold cyan]{self.note_title}[/bold cyan]")
            yield Label("Mật khẩu mới:")
            yield VietnameseInput(password=True, placeholder="Nhập mật khẩu mới...", id="input-new-pass1")
            yield Label("Xác nhận mật khẩu mới:")
            yield VietnameseInput(password=True, placeholder="Nhập lại mật khẩu mới...", id="input-new-pass2")
            yield Static("", id="change-error-msg", classes="error-msg")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Lưu mật khẩu mới", id="btn-confirm-change", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#input-new-pass1", VietnameseInput).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm-change":
            self._submit()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "input-new-pass1":
            self.query_one("#input-new-pass2", VietnameseInput).focus()
        else:
            self._submit()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        p1 = self.query_one("#input-new-pass1", VietnameseInput).value
        p2 = self.query_one("#input-new-pass2", VietnameseInput).value
        if not p1:
            self.query_one("#change-error-msg", Static).update("[bold red]Mật khẩu mới không được để trống![/bold red]")
            return
        if p1 != p2:
            self.query_one("#change-error-msg", Static).update("[bold red]Mật khẩu xác nhận không khớp![/bold red]")
            return
        self.dismiss(p1)


class ConfirmRemoveLockModal(ModalScreen[bool]):
    """Confirmation modal before permanently removing password lock."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(self, note_title: str):
        super().__init__()
        self.note_title = note_title

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("Gỡ Bỏ Mật Khẩu Bảo Vệ?", classes="dialog-title")
            yield Static(
                f"Bạn có chắc muốn gỡ bỏ mật khẩu bảo vệ cho ghi chú [bold cyan]'{self.note_title}'[/bold cyan]?\n\n"
                "[yellow]Sau khi gỡ bỏ, ghi chú sẽ trở về dạng văn bản thường và ai cũng có thể đọc được.[/yellow]"
            )
            with Horizontal(classes="modal-buttons"):
                yield Button("Hủy", id="btn-cancel", variant="default")
                yield Button("Gỡ bỏ khóa", id="btn-confirm-remove", variant="warning")

    def on_mount(self) -> None:
        self.query_one("#btn-cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm-remove":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


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
        ("[bold cyan]c / ctrl+y[/bold cyan]", "Copy note content or selection to Clipboard"),
        ("[bold cyan]r[/bold cyan]", "Rename currently open note"),
        ("[bold cyan]u[/bold cyan]", "Unlock password-protected note"),
        ("[bold cyan]l[/bold cyan]", "Lock / protect note with password"),
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
        Binding("1", "select_opt_1", "Red"),
        Binding("2", "select_opt_2", "Green"),
        Binding("3", "select_opt_3", "Yellow"),
        Binding("4", "select_opt_4", "Blue"),
        Binding("5", "select_opt_5", "Purple"),
        Binding("6", "select_opt_6", "Orange"),
        Binding("7", "select_opt_7", "Cyan"),
        Binding("8", "select_opt_8", "Pink"),
        Binding("9", "select_opt_9", "Tip Box"),
        Binding("0", "select_opt_0", "Warning Box"),
    ]

    TEMPLATES = {
        "1": '<span style="color: #f7768e">{text}</span>',
        "2": '<span style="color: #9ece6a">{text}</span>',
        "3": '<span style="color: #e0af68">{text}</span>',
        "4": '<span style="color: #7aa2f7">{text}</span>',
        "5": '<span style="color: #bb9af7">{text}</span>',
        "6": '<span style="color: #ff9e64">{text}</span>',
        "7": '<span style="color: #7dcfff">{text}</span>',
        "8": '<span style="color: #f5c2e7">{text}</span>',
        "9": "> [!TIP]\n> {text}\n",
        "0": "> [!WARNING]\n> {text}\n",
    }

    OPTIONS = [
        ("1", "btn-c-1", "🔴 Chữ Đỏ (Red)", "1"),
        ("2", "btn-c-2", "🟢 Chữ Xanh lá (Green)", "2"),
        ("3", "btn-c-3", "🟡 Chữ Vàng (Yellow)", "3"),
        ("4", "btn-c-4", "🔵 Chữ Xanh dương (Blue)", "4"),
        ("5", "btn-c-5", "🟣 Chữ Tím (Purple)", "5"),
        ("6", "btn-c-6", "🟠 Chữ Cam (Orange)", "6"),
        ("7", "btn-c-7", "🔷 Chữ Xanh ngọc (Cyan)", "7"),
        ("8", "btn-c-8", "🌸 Chữ Hồng (Pink)", "8"),
        ("9", "btn-c-9", "💡 Khung Ghi chú (Tip Box)", "9"),
        ("0", "btn-c-0", "⚠️ Khung Cảnh báo (Warning Box)", "0"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("🎨 Chọn Màu Chữ & Định Dạng", classes="dialog-title")
            yield Static("[dim]Bấm số [bold cyan]1-8[/bold cyan] đổi màu chữ hoặc [bold cyan]9, 0[/bold cyan] đóng khung:[/dim]\n")
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
    def action_select_opt_0(self) -> None: self.dismiss(self.TEMPLATES["0"])

