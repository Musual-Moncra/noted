import unicodedata
from rich.markup import escape
from rich.text import Text
from typing import Optional, Tuple
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, Tree
from pathlib import Path

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
            yield Static("", id="new-tag-suggestions", markup=False)
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Create", id="btn-create", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#input-title", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "input-tags":
            query = event.value.split(',')[-1].strip()
            tags = self.app.indexer.list_tags(query=query, limit=8)
            self.query_one('#new-tag-suggestions', Static).update('Suggestions: ' + ', '.join(tag for tag, _ in tags))

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
            yield Label("🔓 Unlock Note", classes="dialog-title")
            yield Static(f"Note: [bold cyan]{escape(self.note_title)}[/bold cyan]")
            yield Label("Password:")
            yield VietnameseInput(password=True, placeholder="Enter password...", id="input-unlock-password")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Unlock", id="btn-unlock", variant="primary")

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
            yield Label("🔒 Protect Note", classes="dialog-title")
            yield Static(f"Note: [bold cyan]{escape(self.note_title)}[/bold cyan]")
            yield Label("New password:")
            yield VietnameseInput(password=True, placeholder="Enter password...", id="input-lock-pass1")
            yield Label("Confirm password:")
            yield VietnameseInput(password=True, placeholder="Repeat password...", id="input-lock-pass2")
            yield Static("", id="lock-error-msg", classes="error-msg")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Protect note", id="btn-confirm-lock", variant="primary")

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
            self.query_one("#lock-error-msg", Static).update("[bold red]Password must not be empty.[/bold red]")
            return
        if p1 != p2:
            self.query_one("#lock-error-msg", Static).update("[bold red]Passwords do not match.[/bold red]")
            return
        self.dismiss(p1)


class ManageLockModal(ModalScreen[Optional[str]]):
    """Modal to manage an unlocked encrypted note: Change Password, Remove Lock, or Relock Now."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("1", "choose_change_password", "Change password"),
        Binding("2", "choose_remove_lock", "Remove protection"),
        Binding("3", "choose_relock", "Relock"),
    ]

    def __init__(self, note_title: str):
        super().__init__()
        self.note_title = note_title

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("🔐 Manage Protection", classes="dialog-title")
            yield Static(f"Note: [bold cyan]{escape(self.note_title)}[/bold cyan]")
            yield Static("[dim]Choose a security action:[/dim]\n")
            with Vertical(id="manage-lock-options"):
                yield Button("🔑 1. Change password", id="btn-opt-change-pass", variant="primary")
                yield Button("🔓 2. Remove password protection", id="btn-opt-remove-lock", variant="warning")
                yield Button("🔒 3. Relock now", id="btn-opt-relock", variant="default")
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
            yield Label("🔑 Change Password", classes="dialog-title")
            yield Static(f"Note: [bold cyan]{escape(self.note_title)}[/bold cyan]")
            yield Label("New password:")
            yield VietnameseInput(password=True, placeholder="Enter new password...", id="input-new-pass1")
            yield Label("Confirm new password:")
            yield VietnameseInput(password=True, placeholder="Repeat new password...", id="input-new-pass2")
            yield Static("", id="change-error-msg", classes="error-msg")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Save password", id="btn-confirm-change", variant="primary")

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
            self.query_one("#change-error-msg", Static).update("[bold red]Password must not be empty.[/bold red]")
            return
        if p1 != p2:
            self.query_one("#change-error-msg", Static).update("[bold red]Passwords do not match.[/bold red]")
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
            yield Label("Remove Password Protection?", classes="dialog-title")
            yield Static(
                f"Remove password protection from [bold cyan]'{escape(self.note_title)}'[/bold cyan]?\n\n"
                "[yellow]The note will be stored as readable plain text.[/yellow]"
            )
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Remove protection", id="btn-confirm-remove", variant="warning")

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
            yield Static(f"Are you sure you want to permanently delete:\n[bold red]{escape(self.note_title)}[/bold red]?")
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
        ("[bold cyan]ctrl+q[/bold cyan]", "Save and quit"),
        ("[bold cyan]ctrl+n[/bold cyan]", "Quick capture into Inbox"),
        ("[bold cyan]ctrl+o[/bold cyan]", "Toggle folders and tags navigation"),
        ("[bold cyan]ctrl+l[/bold cyan]", "Toggle notes list"),
        ("[bold cyan]More[/bold cyan]", "Tags, pin, archive, move, lock and rename"),
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
        ("1", "btn-c-1", "🔴 Red", "1"),
        ("2", "btn-c-2", "🟢 Green", "2"),
        ("3", "btn-c-3", "🟡 Yellow", "3"),
        ("4", "btn-c-4", "🔵 Blue", "4"),
        ("5", "btn-c-5", "🟣 Purple", "5"),
        ("6", "btn-c-6", "🟠 Orange", "6"),
        ("7", "btn-c-7", "🔷 Cyan", "7"),
        ("8", "btn-c-8", "🌸 Pink", "8"),
        ("9", "btn-c-9", "💡 Tip callout", "9"),
        ("0", "btn-c-0", "⚠️ Warning callout", "0"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("🎨 Text Colors & Formatting", classes="dialog-title")
            yield Static("[dim]Press [bold cyan]1-8[/bold cyan] for text colors or [bold cyan]9, 0[/bold cyan] for callouts:[/dim]\n")
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



class TextPromptModal(ModalScreen[str | None]):
    BINDINGS = [Binding('escape', 'cancel', 'Cancel', priority=True)]

    def __init__(self, title: str, value: str = '', hint: str = '', suggestions=None):
        super().__init__()
        self.prompt_title, self.value, self.hint = title, value, hint
        self.suggestions = suggestions

    def compose(self):
        with Vertical(classes='modal-dialog'):
            yield Label(self.prompt_title, classes='dialog-title')
            yield Static(self.hint, markup=False)
            yield VietnameseInput(value=self.value, id='prompt-value')
            yield Static('', id='prompt-suggestions', markup=False)
            with Horizontal(classes='modal-buttons'):
                yield Button('Cancel', id='prompt-cancel')
                yield Button('Apply', id='prompt-apply', variant='primary')

    def on_mount(self):
        self.query_one('#prompt-value', Input).focus()
        self.update_suggestions(self.value)

    def update_suggestions(self, value):
        if self.suggestions:
            self.query_one('#prompt-suggestions', Static).update(self.suggestions(value))

    def on_input_changed(self, event: Input.Changed):
        self.update_suggestions(event.value)

    def on_input_submitted(self):
        self.dismiss(self.query_one('#prompt-value', Input).value)

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(self.query_one('#prompt-value', Input).value if event.button.id == 'prompt-apply' else None)

    def action_cancel(self):
        self.dismiss(None)


class ActionMenuModal(ModalScreen[str | None]):
    BINDINGS = [Binding('escape', 'cancel', 'Cancel', priority=True)]

    def __init__(self, title, actions):
        super().__init__()
        self.menu_title, self.actions = title, actions

    def compose(self):
        with Vertical(classes='modal-dialog'):
            yield Label(self.menu_title, classes='dialog-title')
            for action, label in self.actions:
                yield Button(label, id='menu-' + action, classes='menu-action')
            yield Button('Cancel', id='menu-cancel', classes='menu-action')

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        action = event.button.id.removeprefix('menu-')
        self.dismiss(None if action == 'cancel' else action)

    def action_cancel(self):
        self.dismiss(None)


class ConflictModal(ActionMenuModal):
    def __init__(self):
        super().__init__('File changed outside Noted', [
            ('reload', 'Reload disk version (discard draft)'),
            ('overwrite', 'Overwrite with current draft')])


class FolderPickerModal(ModalScreen[Path | None]):
    BINDINGS = [Binding('escape', 'cancel', 'Cancel', priority=True)]

    def __init__(self, storage, current):
        super().__init__()
        self.storage, self.current = storage, current
        self.destination = storage.config.notes_subdir.resolve()

    def compose(self):
        with Vertical(classes='modal-dialog'):
            yield Label('Move note', classes='dialog-title')
            yield Static(f'Current: {self.current}', markup=False)
            yield VietnameseInput(placeholder='Find folder: Work/Project', id='folder-search')
            yield Tree('notes/', self.destination, id='folder-picker-tree')
            yield VietnameseInput(placeholder='New folder name inside selection', id='folder-new-name')
            yield Static('Destination: notes/', id='folder-destination', markup=False)
            with Horizontal(classes='modal-buttons'):
                yield Button('New folder', id='folder-new')
                yield Button('Cancel', id='folder-cancel')
                yield Button('Move', id='folder-move', variant='primary')

    def on_mount(self):
        tree = self.query_one(Tree)
        self.populate(tree.root)
        tree.root.expand()

    def populate(self, node):
        if node.children:
            return
        for path in self.storage.child_folders(node.data):
            node.add(Text(path.name), path, allow_expand=True)

    def on_tree_node_expanded(self, event: Tree.NodeExpanded):
        self.populate(event.node)

    def on_tree_node_selected(self, event: Tree.NodeSelected):
        self.destination = event.node.data
        self.query_one('#folder-destination', Static).update('Destination: ' + str(self.destination.relative_to(self.storage.config.notes_subdir.resolve())))

    def on_input_changed(self, event: Input.Changed):
        if event.input.id != 'folder-search':
            return
        if getattr(self, '_folder_search_timer', None):
            self._folder_search_timer.stop()
        self._folder_search_timer = self.set_timer(.15, self.search_folders)

    def search_folders(self):
        query = self.query_one('#folder-search', Input).value.strip()
        tree = self.query_one('#folder-picker-tree', Tree)
        tree.clear()
        tree.root.data = self.storage.config.notes_subdir.resolve()
        if query:
            for path in self.storage.find_folders(query):
                tree.root.add_leaf(Text(str(path.relative_to(tree.root.data))), path)
        else:
            self.populate(tree.root)
        tree.root.expand()

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if event.button.id == 'folder-move':
            self.dismiss(self.destination)
        elif event.button.id == 'folder-cancel':
            self.dismiss(None)
        elif event.button.id == 'folder-new':
            try:
                name = self.query_one('#folder-new-name', Input).value.strip()
                if not name:
                    raise ValueError('Enter a folder name.')
                self.destination = self.storage.create_folder(self.destination / name)
                self.query_one('#folder-destination', Static).update('Destination: ' + str(self.destination))
            except (OSError, ValueError) as exc:
                self.notify(str(exc), severity='error')

    def action_cancel(self):
        self.dismiss(None)


class FilterNotesModal(ModalScreen[tuple[str | None, list[str]] | None]):
    BINDINGS = [Binding('escape', 'cancel', 'Cancel', priority=True)]

    def __init__(self, tags, note_type):
        super().__init__()
        self.tags, self.note_type = tags, note_type

    def compose(self):
        from textual.widgets import Select
        with Vertical(classes='modal-dialog'):
            yield Label('Filter notes', classes='dialog-title')
            yield Label('Type')
            yield Select([('All types', 'all'), ('Notes', 'note'), ('Journals', 'journal')],
                         value=self.note_type or 'all', allow_blank=False, id='filter-type')
            yield Label('Tags · match all, comma-separated')
            yield VietnameseInput(value=', '.join(self.tags), id='filter-tags')
            yield Static('', id='filter-suggestions', markup=False)
            with Horizontal(classes='modal-buttons'):
                yield Button('Clear', id='filter-clear')
                yield Button('Cancel', id='filter-cancel')
                yield Button('Apply', id='filter-apply', variant='primary')

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == 'filter-tags':
            tags = self.app.indexer.list_tags(query=event.value.split(',')[-1].strip(), limit=8)
            self.query_one('#filter-suggestions', Static).update('Suggestions: ' + ', '.join(t for t, _ in tags))

    def submit(self):
        from textual.widgets import Select
        from noted.models import normalize_tags
        kind = self.query_one('#filter-type', Select).value
        self.dismiss((None if kind == 'all' else kind,
                      normalize_tags(self.query_one('#filter-tags', Input).value.split(','))))

    def on_input_submitted(self):
        self.submit()

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if event.button.id == 'filter-clear':
            self.dismiss((None, []))
        elif event.button.id == 'filter-apply':
            self.submit()
        else:
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)
