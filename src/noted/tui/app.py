import os
import sys
import unicodedata
from pathlib import Path
from typing import Optional

# Disable Kitty extended keyboard protocol early to ensure Vietnamese IMEs
# (Telex, Simple Telex, EVKey, OpenKey, UniKey) work seamlessly without dropped backspaces or duplicated vowels.
os.environ.setdefault("TEXTUAL_DISABLE_KITTY_KEY", "1")
try:
    import textual.constants as _tc
    _tc.DISABLE_KITTY_KEY = True
except Exception:
    pass

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListView,
    Markdown,
    Static,
    TextArea,
)
from noted.config import Config, load_config
from noted.db import DatabaseManager
from noted.editor import open_in_editor
from noted.indexer import NoteIndexer
import noted.markdown_colors  # noqa: F401
from noted.models import Note, NoteSummary
from noted.storage import StorageManager
from noted.tui.screens import (
    ChangePasswordModal,
    ColorFormatModal,
    ConfirmDeleteModal,
    ConfirmRemoveLockModal,
    HelpModal,
    LockNoteModal,
    ManageLockModal,
    NewNoteModal,
    RenameNoteModal,
    UnlockNoteModal,
)
from noted.tui.widgets import MetadataHeader, NoteListItem, VietnameseInput, VietnameseTextArea


class NotedApp(App[None]):
    """Main interactive Textual Terminal Application for noted."""

    TITLE = "NOTED"
    SUB_TITLE = "Terminal Note-Taking & Journal"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
        Binding("n", "new_note", "New", show=True),
        Binding("j", "today_journal", "Today", show=True),
        Binding("e", "toggle_edit", "Edit/View", show=True),
        Binding("ctrl+p", "toggle_preview", "Preview", show=False, priority=True),
        Binding("f2", "toggle_preview", "View/Edit", show=False, priority=True),
        Binding("ctrl+w", "toggle_split", "Split", show=True, priority=True),
        Binding("ctrl+s", "save_note", "Save", show=False, priority=True),
        Binding("ctrl+b", "format_bold", "Bold", show=False, priority=True),
        Binding("ctrl+i", "format_italic", "Italic", show=False, priority=True),
        Binding("ctrl+k", "format_code", "Code", show=False, priority=True),
        Binding("ctrl+h", "format_heading", "Heading", show=False, priority=True),
        Binding("ctrl+t", "format_todo", "Todo", show=False, priority=True),
        Binding("ctrl+m", "format_color", "Color", show=False, priority=True),
        Binding("ctrl+e", "open_external", "$EDITOR", show=False),
        Binding("c", "copy_content", "Copy", show=True),
        Binding("ctrl+y", "copy_content", "Copy", show=False, priority=True),
        Binding("r", "rename_note", "Rename", show=True),
        Binding("u", "unlock_note", "Unlock", show=True),
        Binding("l", "lock_note", "Lock", show=True),
        Binding("d", "delete_note", "Delete", show=True),
        Binding("slash", "focus_search", "Search", show=True),
        Binding("escape", "exit_edit_mode", "View/List", show=False, priority=True),
        Binding("question_mark", "show_help", "Help", show=True),
    ]

    def __init__(self, custom_config: Optional[Config] = None, **kwargs):
        super().__init__(**kwargs)
        self.custom_config = custom_config
        self.config: Config
        self.storage: StorageManager
        self.db: DatabaseManager
        self.indexer: NoteIndexer
        self.current_note: Optional[Note] = None
        self.note_mode: str = "view"  # "view", "edit", or "split"
        self._preview_timer = None
        self.unlocked_notes: dict[str, str] = {}  # session cache: note_id -> decrypted body

    @property
    def edit_mode(self) -> bool:
        return self.note_mode in ["edit", "split"]

    @edit_mode.setter
    def edit_mode(self, val: bool) -> None:
        self.set_mode("edit" if val else "view")

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            with Vertical(id="sidebar"):
                yield VietnameseInput(placeholder="🔍 Tìm kiếm... [/]", id="search-input")
                yield ListView(id="notes-list")
            with Vertical(id="content-area"):
                yield MetadataHeader(id="metadata-header")
                with Horizontal(id="main-workspace"):
                    with Container(id="edit-container"):
                        with Horizontal(id="formatting-toolbar"):
                            yield Button("𝐁", id="btn-fmt-bold", classes="fmt-btn")
                            yield Button("𝐼", id="btn-fmt-italic", classes="fmt-btn")
                            yield Button("</>", id="btn-fmt-code", classes="fmt-btn")
                            yield Button("H#", id="btn-fmt-heading", classes="fmt-btn")
                            yield Button("☑", id="btn-fmt-todo", classes="fmt-btn")
                            yield Button("❝", id="btn-fmt-quote", classes="fmt-btn")
                            yield Button("💡", id="btn-fmt-callout", classes="fmt-btn")
                            yield Button("🎨", id="btn-fmt-color", classes="fmt-btn")
                        yield VietnameseTextArea(id="text-editor", language="markdown")
                    with Container(id="view-container"):
                        with Vertical(id="locked-note-card"):
                            yield Label("🔒 GHI CHÚ ĐÃ ĐƯỢC BẢO VỆ", id="locked-card-title")
                            yield Static(
                                "Ghi chú đã được mã hóa an toàn bằng AES-256.\n"
                                "Nhấn nút bên dưới hoặc phím [b]u[/b] để mở khóa:",
                                id="locked-card-desc",
                            )
                            yield Button("🔓 Mở khóa ghi chú", id="btn-screen-unlock", variant="primary")
                        yield Markdown(id="markdown-viewer")

        yield Footer()


    def on_mount(self) -> None:
        # Explicitly instruct terminal to exit any active Kitty keyboard protocol state
        if sys.platform != "win32" and sys.stdout.isatty():
            try:
                sys.stdout.write("\x1b[<u")
                sys.stdout.flush()
            except Exception:
                pass

        self.config = self.custom_config or load_config()
        self.storage = StorageManager(self.config)
        self.db = DatabaseManager(self.config.db_path)
        self.indexer = NoteIndexer(self.db, self.storage)
        self.indexer.sync_all()

        # Initial view state: populate list first so note is loaded, then activate View mode
        self.refresh_notes_list()
        self.set_mode("view")
        self.query_one("#notes-list", ListView).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self.action_focus_list()

    def refresh_notes_list(self, select_id: Optional[str] = None) -> None:
        """Reloads all notes from indexer and repopulates the sidebar list."""
        notes = self.indexer.list_notes(limit=100)
        list_view = self.query_one("#notes-list", ListView)
        list_view.clear()

        target_index: Optional[int] = None
        for i, note_sum in enumerate(notes):
            list_view.append(NoteListItem(note_sum))
            if select_id and note_sum.id == select_id:
                target_index = i

        if notes:
            selected_idx = target_index if target_index is not None else 0
            list_view.index = selected_idx
            self.load_note_by_summary(notes[selected_idx])
        else:
            self.current_note = None
            self.query_one("#metadata-header", MetadataHeader).update_metadata(None, "view")
            self.query_one("#markdown-viewer", Markdown).update("*No notes available. Press [bold cyan]n[/bold cyan] to create one or [bold cyan]j[/bold cyan] for today's journal.*")
            self.query_one("#text-editor", TextArea).text = ""

    def load_note_by_summary(self, summary: NoteSummary) -> None:
        """Loads full note details into the viewer and editor."""
        if summary.filepath.is_file():
            self.current_note = self.storage.read_note(summary.filepath)
        else:
            self.current_note = self.indexer.get_note_by_id_or_date(summary.id)

        if self.current_note:
            is_unlocked = False
            if self.current_note.encrypted:
                if self.current_note.id in self.unlocked_notes:
                    is_unlocked = True
                    body = self.unlocked_notes[self.current_note.id] or "*Empty note.*"
                else:
                    body = ""
            else:
                body = self.current_note.body or "*Empty note.*"

            locked_card = self.query_one("#locked-note-card")
            viewer = self.query_one("#markdown-viewer", Markdown)
            editor = self.query_one("#text-editor", TextArea)

            if self.current_note.encrypted and not is_unlocked:
                locked_card.display = True
                viewer.display = False
                editor.text = ""
            else:
                locked_card.display = False
                viewer.display = True
                viewer.update(body)
                editor.text = body if body != "*Empty note.*" else ""

            self.query_one("#metadata-header", MetadataHeader).update_metadata(
                self.current_note, self.note_mode, is_unlocked=is_unlocked
            )


    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, NoteListItem):
            # Auto-save current note before switching to another note!
            if self.note_mode in ["edit", "split"] and self.current_note:
                self.save_current_note(silent=True)
            self.load_note_by_summary(event.item.summary)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            query = unicodedata.normalize("NFC", event.value.strip())
            list_view = self.query_one("#notes-list", ListView)
            list_view.clear()

            if not query:
                notes = self.indexer.list_notes(limit=100)
            else:
                results = self.indexer.search(query=query, limit=50)
                notes = [r.note for r in results]

            for note_sum in notes:
                list_view.append(NoteListItem(note_sum))

            if notes:
                list_view.index = 0
                self.load_note_by_summary(notes[0])
            else:
                self.current_note = None
                self.query_one("#metadata-header", MetadataHeader).update_metadata(None, "view")
                self.query_one("#markdown-viewer", Markdown).update(f"*No notes match query '[bold]{query}[/bold]'.*")
                self.query_one("#text-editor", TextArea).text = ""

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Debounced live-update of the markdown viewer in Split mode."""
        if self.note_mode == "split":
            if getattr(self, "_preview_timer", None) is not None:
                self._preview_timer.stop()
            self._preview_timer = self.set_timer(0.2, self._update_live_preview)

    def _update_live_preview(self) -> None:
        if self.note_mode == "split":
            try:
                editor = self.query_one("#text-editor", TextArea)
                self.query_one("#markdown-viewer", Markdown).update(editor.text or "*Empty note.*")
            except Exception:
                pass

    def set_mode(self, mode: str) -> None:
        """Switches between 'view', 'edit', and 'split' mode with automatic saving."""
        if self.note_mode in ["edit", "split"] and mode == "view" and self.current_note:
            self.save_current_note(silent=True)

        self.note_mode = mode
        view_container = self.query_one("#view-container")
        edit_container = self.query_one("#edit-container")
        editor = self.query_one("#text-editor", TextArea)
        viewer = self.query_one("#markdown-viewer", Markdown)
        locked_card = self.query_one("#locked-note-card")

        if not self.current_note:
            if mode == "view":
                edit_container.display = False
                view_container.display = True
            elif mode == "edit":
                edit_container.display = True
                view_container.display = False
            elif mode == "split":
                edit_container.display = True
                view_container.display = True
            return

        if mode == "view":
            if self.current_note.encrypted and self.current_note.id not in self.unlocked_notes:
                locked_card.display = True
                viewer.display = False
            else:
                locked_card.display = False
                viewer.display = True
                viewer.update(editor.text or "*Empty note.*")
            edit_container.display = False
            view_container.display = True
            self.query_one("#notes-list", ListView).focus()
        elif mode == "edit":
            if self.current_note.encrypted and self.current_note.id not in self.unlocked_notes:
                self.notify("Vui lòng mở khóa ghi chú trước khi soạn thảo.", severity="warning")
                self.action_unlock_note()
                return
            edit_container.display = True
            view_container.display = False
            editor.focus()
        elif mode == "split":
            if self.current_note.encrypted and self.current_note.id not in self.unlocked_notes:
                self.notify("Vui lòng mở khóa ghi chú trước khi soạn thảo.", severity="warning")
                self.action_unlock_note()
                return
            locked_card.display = False
            viewer.display = True
            viewer.update(editor.text or "*Empty note.*")
            edit_container.display = True
            view_container.display = True
            editor.focus()

        is_unlocked = bool(self.current_note and self.current_note.id in self.unlocked_notes)
        self.query_one("#metadata-header", MetadataHeader).update_metadata(self.current_note, self.note_mode, is_unlocked=is_unlocked)


    def action_toggle_edit(self) -> None:
        """Toggles between View and Edit mode with automatic saving."""
        if self.note_mode == "view":
            self.set_mode("edit")
        else:
            self.set_mode("view")

    def action_toggle_preview(self) -> None:
        """One-key toggle between preview and edit mode with auto-save."""
        if self.note_mode in ["edit", "split"]:
            self.set_mode("view")
        else:
            self.set_mode("edit")

    def action_toggle_split(self) -> None:
        """Toggles side-by-side editing and live preview."""
        if self.note_mode == "split":
            self.set_mode("view")
        else:
            self.set_mode("split")

    def action_exit_edit_mode(self) -> None:
        """Exits active modal screen or edit/split mode, auto-saves, and focuses the notes list."""
        if len(self.screen_stack) > 1 and isinstance(self.screen, ModalScreen):
            if hasattr(self.screen, "action_cancel"):
                self.screen.action_cancel()
            elif hasattr(self.screen, "action_dismiss_help"):
                self.screen.action_dismiss_help()
            else:
                self.screen.dismiss(None)
            return

        if self.note_mode in ["edit", "split"]:
            self.set_mode("view")
        else:
            self.query_one("#notes-list", ListView).focus()

    def action_focus_list(self) -> None:
        self.action_exit_edit_mode()

    def save_current_note(self, silent: bool = False) -> None:
        """Persists current note edits to disk and updates SQLite index."""
        if not self.current_note:
            return

        editor = self.query_one("#text-editor", TextArea)
        raw_text = unicodedata.normalize("NFC", editor.text)

        if self.current_note.encrypted:
            session_pwd = getattr(self, "session_passwords", {}).get(self.current_note.id)
            if session_pwd:
                self.current_note.body = raw_text
                self.storage.lock_note(self.current_note, session_pwd)
                self.unlocked_notes[self.current_note.id] = raw_text
            else:
                self.current_note.body = raw_text
                self.storage.save_note(self.current_note)
        else:
            self.current_note.body = raw_text
            self.storage.save_note(self.current_note)

        self.indexer.index_note(self.current_note)

        # Update viewer
        display_body = raw_text or "*Empty note.*"
        self.query_one("#markdown-viewer", Markdown).update(display_body)
        if not silent:
            self.notify("Đã lưu ghi chú thành công!", title="Saved", severity="information")
        else:
            self.notify("Tự động lưu ✓", severity="information")


    def action_save_note(self) -> None:
        """Manual save via Ctrl+S or Save button."""
        self.save_current_note(silent=False)

    def action_new_note(self) -> None:
        """Opens modal to create a new note."""
        def handle_new_note(result: Optional[tuple[str, list[str]]]) -> None:
            if not result:
                return
            title, tags = result
            note = self.storage.create_note(title=title, body="", tags=tags)
            self.indexer.index_note(note)
            self.refresh_notes_list(select_id=note.id)
            if not self.edit_mode:
                self.action_toggle_edit()

        self.push_screen(NewNoteModal(), handle_new_note)

    def action_today_journal(self) -> None:
        """Loads or creates today's journal entry."""
        journal = self.storage.get_or_create_today_journal()
        self.indexer.index_note(journal)
        self.refresh_notes_list(select_id=journal.id)

    def action_delete_note(self) -> None:
        """Deletes current note after confirmation."""
        if not self.current_note or not self.current_note.filepath:
            return

        def handle_delete(confirmed: bool) -> None:
            if confirmed and self.current_note and self.current_note.filepath:
                nid = self.current_note.id
                self.storage.delete_note(self.current_note.filepath)
                self.indexer.remove_note(nid)
                self.notify("Note deleted.", severity="warning")
                self.refresh_notes_list()

        self.push_screen(ConfirmDeleteModal(self.current_note.title), handle_delete)

    def action_open_external(self) -> None:
        """Suspends TUI and opens note in external $EDITOR."""
        if not self.current_note or not self.current_note.filepath:
            return

        # Save any in-progress edits first
        if self.edit_mode:
            self.action_save_note()

        with self.suspend():
            open_in_editor(self.current_note.filepath, preferred_editor=self.config.editor)

        # Re-read and re-index upon return
        self.current_note = self.storage.read_note(self.current_note.filepath)
        self.indexer.index_note(self.current_note)
        self.load_note_by_summary(
            NoteSummary(
                id=self.current_note.id,
                title=self.current_note.title,
                date=self.current_note.date,
                note_type=self.current_note.note_type,
                tags=self.current_note.tags,
                filepath=self.current_note.filepath,
            )
        )

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    def _wrap_or_insert(self, prefix: str, suffix: str, placeholder: str) -> None:
        if not self.edit_mode:
            self.action_toggle_edit()

        editor = self.query_one("#text-editor", TextArea)
        if editor.selected_text:
            editor.replace(
                f"{prefix}{editor.selected_text}{suffix}",
                editor.selection.start,
                editor.selection.end,
            )
        else:
            editor.insert(f"{prefix}{placeholder}{suffix}")
        editor.focus()

    def action_format_bold(self) -> None:
        """Wraps selected text in **bold** or inserts **bold text**."""
        self._wrap_or_insert("**", "**", "bold text")

    def action_format_italic(self) -> None:
        """Wraps selected text in *italic* or inserts *italic text*."""
        self._wrap_or_insert("*", "*", "italic text")

    def action_format_code(self) -> None:
        """Wraps selected text in inline code or block."""
        editor = self.query_one("#text-editor", TextArea)
        if "\n" in editor.selected_text:
            self._wrap_or_insert("```python\n", "\n```\n", "")
        else:
            self._wrap_or_insert("`", "`", "code")

    def action_format_heading(self) -> None:
        """Inserts a markdown heading."""
        if not self.edit_mode:
            self.action_toggle_edit()
        editor = self.query_one("#text-editor", TextArea)
        editor.insert("\n## Heading\n")
        editor.focus()

    def action_format_todo(self) -> None:
        """Inserts an interactive todo checkbox item."""
        if not self.edit_mode:
            self.action_toggle_edit()
        editor = self.query_one("#text-editor", TextArea)
        editor.insert("\n- [ ] Todo item\n")
        editor.focus()

    def action_format_quote(self) -> None:
        """Inserts a blockquote."""
        if not self.edit_mode:
            self.action_toggle_edit()
        editor = self.query_one("#text-editor", TextArea)
        editor.insert("\n> Blockquote text\n")
        editor.focus()

    def action_format_callout(self) -> None:
        """Inserts a colored callout block (e.g. [!TIP] or [!NOTE])."""
        if not self.edit_mode:
            self.action_toggle_edit()
        editor = self.query_one("#text-editor", TextArea)
        editor.insert("\n> [!TIP]\n> Highlighted tip or note\n")
        editor.focus()

    def action_format_color(self) -> None:
        """Opens ColorFormatModal to apply colored highlights, alert blocks, or diff colors."""
        if not self.edit_mode:
            self.action_toggle_edit()

        editor = self.query_one("#text-editor", TextArea)
        selected = editor.selected_text or "Nội dung cần làm nổi bật"

        def apply_template(template: Optional[str]) -> None:
            if not template:
                return
            formatted = template.format(text=selected)
            if editor.selected_text:
                editor.replace(formatted, editor.selection.start, editor.selection.end)
            else:
                editor.insert(formatted)
            editor.focus()

        self.push_screen(ColorFormatModal(), apply_template)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-mode-view":
            self.set_mode("view")
        elif btn_id == "btn-mode-edit":
            self.set_mode("edit")
        elif btn_id == "btn-mode-split":
            self.set_mode("split")
        elif btn_id == "btn-mode-ext":
            self.action_open_external()
        elif btn_id == "btn-mode-save":
            self.action_save_note()
        elif btn_id == "btn-fmt-bold":
            self.action_format_bold()
        elif btn_id == "btn-fmt-italic":
            self.action_format_italic()
        elif btn_id == "btn-fmt-code":
            self.action_format_code()
        elif btn_id == "btn-fmt-heading":
            self.action_format_heading()
        elif btn_id == "btn-fmt-todo":
            self.action_format_todo()
        elif btn_id == "btn-fmt-quote":
            self.action_format_quote()
        elif btn_id == "btn-fmt-callout":
            self.action_format_callout()
        elif btn_id == "btn-fmt-color":
            self.action_format_color()
        elif btn_id in ("btn-mode-copy", "btn-fmt-copy"):
            self.action_copy_content()
        elif btn_id == "btn-mode-rename":
            self.action_rename_note()
        elif btn_id in ("btn-screen-unlock", "btn-mode-lock"):
            if self.current_note and self.current_note.encrypted:
                if self.current_note.id in self.unlocked_notes:
                    self.action_manage_lock()
                else:
                    self.action_unlock_note()
            else:
                self.action_lock_note()

    def action_unlock_note(self) -> None:
        """Opens modal to unlock current encrypted note."""
        if not self.current_note or not self.current_note.encrypted:
            self.notify("Ghi chú này không bị khóa mật khẩu.", severity="information")
            return

        if self.current_note.id in self.unlocked_notes:
            self.action_manage_lock()
            return

        def handle_unlock(password: Optional[str]) -> None:
            if not password:
                return

            try:
                decrypted = self.storage.unlock_note(self.current_note, password)
                if not hasattr(self, "session_passwords"):
                    self.session_passwords = {}
                self.session_passwords[self.current_note.id] = password
                self.unlocked_notes[self.current_note.id] = decrypted

                self.query_one("#locked-note-card").display = False
                viewer = self.query_one("#markdown-viewer", Markdown)
                viewer.display = True
                viewer.update(decrypted or "*Empty note.*")
                self.query_one("#text-editor", TextArea).text = decrypted
                self.query_one("#metadata-header", MetadataHeader).update_metadata(
                    self.current_note, self.note_mode, is_unlocked=True
                )
                self.refresh_notes_list(select_id=self.current_note.id)
                self.query_one("#notes-list", ListView).focus()
                self.notify("Đã mở khóa ghi chú thành công! ✓", title="Unlocked", severity="information")
            except Exception:
                self.notify("Sai mật khẩu! Không thể mở khóa.", title="Error", severity="error")

        self.push_screen(UnlockNoteModal(self.current_note.title), handle_unlock)

    def action_lock_note(self) -> None:
        """Opens modal to lock or manage lock for the current note."""
        if not self.current_note:
            self.notify("Không có ghi chú nào được chọn.", severity="warning")
            return

        if self.current_note.encrypted:
            if self.current_note.id in self.unlocked_notes:
                self.action_manage_lock()
            else:
                self.action_unlock_note()
            return

        def handle_lock(password: Optional[str]) -> None:
            if not password:
                return

            if not hasattr(self, "session_passwords"):
                self.session_passwords = {}
            self.session_passwords[self.current_note.id] = password
            plain_body = self.unlocked_notes.get(self.current_note.id, self.current_note.body)
            self.current_note.body = plain_body
            self.storage.lock_note(self.current_note, password)
            self.indexer.index_note(self.current_note)
            self.unlocked_notes[self.current_note.id] = plain_body

            self.query_one("#metadata-header", MetadataHeader).update_metadata(
                self.current_note, self.note_mode, is_unlocked=True
            )
            self.refresh_notes_list(select_id=self.current_note.id)
            self.query_one("#notes-list", ListView).focus()
            self.notify("Đã khóa ghi chú bằng mật khẩu thành công! ✓", title="Locked", severity="information")

        self.push_screen(LockNoteModal(self.current_note.title), handle_lock)

    def action_manage_lock(self) -> None:
        """Opens modal to manage an unlocked encrypted note (Change Password, Remove Lock, Relock)."""
        if not self.current_note or not self.current_note.encrypted:
            return

        if self.current_note.id not in self.unlocked_notes:
            self.action_unlock_note()
            return

        def handle_manage_choice(choice: Optional[str]) -> None:
            if not choice or not self.current_note:
                return

            if choice == "change_password":
                self._prompt_change_password()
            elif choice == "remove_lock":
                self._prompt_remove_lock()
            elif choice == "relock":
                self._relock_current_note()

        self.push_screen(ManageLockModal(self.current_note.title), handle_manage_choice)

    def _prompt_change_password(self) -> None:
        if not self.current_note:
            return

        def handle_new_password(new_pwd: Optional[str]) -> None:
            if not new_pwd or not self.current_note:
                return

            plain_body = self.unlocked_notes.get(self.current_note.id, self.current_note.body)
            self.current_note.body = plain_body
            self.storage.lock_note(self.current_note, new_pwd)
            self.indexer.index_note(self.current_note)

            if not hasattr(self, "session_passwords"):
                self.session_passwords = {}
            self.session_passwords[self.current_note.id] = new_pwd
            self.unlocked_notes[self.current_note.id] = plain_body

            self.notify("Đã đổi mật khẩu thành công! ✓", title="Password Changed", severity="information")

        self.push_screen(ChangePasswordModal(self.current_note.title), handle_new_password)

    def _prompt_remove_lock(self) -> None:
        if not self.current_note:
            return

        def handle_confirm_remove(confirmed: bool) -> None:
            if not confirmed or not self.current_note:
                return

            plain_body = self.unlocked_notes.get(self.current_note.id, self.current_note.body)
            self.current_note.body = plain_body
            self.current_note.encrypted = False
            self.current_note.salt = None
            self.current_note.nonce = None
            self.storage.save_note(self.current_note)
            self.indexer.index_note(self.current_note)

            self.unlocked_notes.pop(self.current_note.id, None)
            if hasattr(self, "session_passwords"):
                self.session_passwords.pop(self.current_note.id, None)

            self.query_one("#metadata-header", MetadataHeader).update_metadata(
                self.current_note, self.note_mode, is_unlocked=False
            )
            self.refresh_notes_list(select_id=self.current_note.id)
            self.query_one("#notes-list", ListView).focus()
            self.notify("Đã bỏ khóa ghi chú thành công! ✓", title="Unlocked", severity="information")

        self.push_screen(ConfirmRemoveLockModal(self.current_note.title), handle_confirm_remove)

    def _relock_current_note(self) -> None:
        if not self.current_note:
            return

        if self.note_mode in ["edit", "split"]:
            self.save_current_note(silent=True)

        self.unlocked_notes.pop(self.current_note.id, None)
        if hasattr(self, "session_passwords"):
            self.session_passwords.pop(self.current_note.id, None)

        self.set_mode("view")
        self.query_one("#locked-note-card").display = True
        self.query_one("#markdown-viewer").display = False
        self.query_one("#text-editor", TextArea).text = ""

        self.query_one("#metadata-header", MetadataHeader).update_metadata(
            self.current_note, self.note_mode, is_unlocked=False
        )
        self.refresh_notes_list(select_id=self.current_note.id)
        self.query_one("#notes-list", ListView).focus()
        self.notify("Đã khóa lại ghi chú trong phiên hiện tại.", title="Locked", severity="information")

    def action_copy_content(self) -> None:
        """Copies note content or current selection to the system clipboard."""
        if not self.current_note:
            self.notify("Không có ghi chú nào để copy.", severity="warning")
            return

        text_to_copy = ""
        is_selection = False

        if self.note_mode in ["edit", "split"]:
            try:
                editor = self.query_one("#text-editor", VietnameseTextArea)
                if editor.selected_text:
                    text_to_copy = editor.selected_text
                    is_selection = True
                else:
                    text_to_copy = editor.text
            except Exception:
                text_to_copy = self.current_note.body
        else:
            text_to_copy = self.current_note.body

        if not text_to_copy:
            text_to_copy = self.current_note.title or ""

        from noted.clipboard import copy_to_clipboard
        if copy_to_clipboard(text_to_copy, app=self):
            if is_selection:
                self.notify("Đã copy đoạn chọn vào Clipboard! ✓", title="Copied", severity="information")
            else:
                self.notify(f"Đã copy nội dung ghi chú vào Clipboard! ✓", title="Copied", severity="information")
        else:
            self.notify("Không thể truy cập Clipboard hệ thống.", severity="error")

    def action_rename_note(self) -> None:
        """Opens modal to rename the currently loaded note."""
        if not self.current_note:
            self.notify("Không có ghi chú nào được chọn để đổi tên.", severity="warning")
            return

        def handle_rename(new_title: Optional[str]) -> None:
            if not new_title or new_title == self.current_note.title:
                return

            old_title = self.current_note.title
            self.storage.rename_note(self.current_note, new_title)
            self.indexer.index_note(self.current_note)

            is_unlocked = bool(self.current_note.id in self.unlocked_notes)
            self.query_one("#metadata-header", MetadataHeader).update_metadata(
                self.current_note, self.note_mode, is_unlocked=is_unlocked
            )
            self.refresh_notes_list(select_id=self.current_note.id)
            self.notify(f"Đã đổi tên: '{old_title}' → '{new_title}'", title="Renamed ✓", severity="information")

        self.push_screen(RenameNoteModal(self.current_note.title), handle_rename)



