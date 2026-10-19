from pathlib import Path
from typing import Optional
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Footer,
    Header,
    Input,
    ListView,
    Markdown,
    Static,
    TextArea,
)
from noted.config import Config, load_config
from noted.db import DatabaseManager
from noted.editor import open_in_editor
from noted.indexer import NoteIndexer
from noted.models import Note, NoteSummary
from noted.storage import StorageManager
from noted.tui.screens import ConfirmDeleteModal, HelpModal, NewNoteModal
from noted.tui.widgets import MetadataHeader, NoteListItem

class NotedApp(App[None]):
    """Main interactive Textual Terminal Application for noted."""

    TITLE = "NOTED"
    SUB_TITLE = "Terminal Note-Taking & Journal"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
        Binding("n", "new_note", "New Note", show=True),
        Binding("j", "today_journal", "Today", show=True),
        Binding("e", "toggle_edit", "Edit/View", show=True),
        Binding("ctrl+s", "save_note", "Save", show=True, priority=True),
        Binding("ctrl+e", "open_external", "$EDITOR", show=True),
        Binding("d", "delete_note", "Delete", show=True),
        Binding("slash", "focus_search", "Search", show=True),
        Binding("escape", "focus_list", "Focus List", show=False),
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
        self.edit_mode: bool = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            with Vertical(id="sidebar"):
                yield Input(placeholder="Search notes... [/]", id="search-input")
                yield ListView(id="notes-list")
            with Vertical(id="content-area"):
                yield MetadataHeader(id="metadata-header")
                with Container(id="view-container"):
                    yield Markdown(id="markdown-viewer")
                with Container(id="edit-container"):
                    yield TextArea(id="text-editor", language="markdown")
        yield Footer()

    def on_mount(self) -> None:
        self.config = self.custom_config or load_config()
        self.storage = StorageManager(self.config)
        self.db = DatabaseManager(self.config.db_path)
        self.indexer = NoteIndexer(self.db, self.storage)
        self.indexer.sync_all()

        # Initial view state: Markdown view active, TextArea hidden
        self.query_one("#edit-container").display = False
        self.query_one("#view-container").display = True

        self.refresh_notes_list()
        self.query_one("#notes-list", ListView).focus()

    def action_focus_list(self) -> None:
        """Shifts focus back to the notes list and exits edit mode if active."""
        if self.edit_mode:
            self.action_toggle_edit()
        else:
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
            self.query_one("#metadata-header", MetadataHeader).update_metadata(None, False)
            self.query_one("#markdown-viewer", Markdown).update("*No notes available. Press [bold cyan]n[/bold cyan] to create one or [bold cyan]j[/bold cyan] for today's journal.*")
            self.query_one("#text-editor", TextArea).text = ""

    def load_note_by_summary(self, summary: NoteSummary) -> None:
        """Loads full note details into the viewer and editor."""
        if summary.filepath.is_file():
            self.current_note = self.storage.read_note(summary.filepath)
        else:
            self.current_note = self.indexer.get_note_by_id_or_date(summary.id)

        if self.current_note:
            body = self.current_note.body or "*Empty note.*"
            self.query_one("#markdown-viewer", Markdown).update(body)
            self.query_one("#text-editor", TextArea).text = self.current_note.body
            self.query_one("#metadata-header", MetadataHeader).update_metadata(self.current_note, self.edit_mode)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, NoteListItem):
            self.load_note_by_summary(event.item.summary)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            query = event.value.strip()
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
                self.query_one("#metadata-header", MetadataHeader).update_metadata(None, False)
                self.query_one("#markdown-viewer", Markdown).update(f"*No notes match query '[bold]{query}[/bold]'.*")
                self.query_one("#text-editor", TextArea).text = ""

    def action_toggle_edit(self) -> None:
        """Toggles between View and Edit mode."""
        if not self.current_note:
            return

        self.edit_mode = not self.edit_mode
        view_container = self.query_one("#view-container")
        edit_container = self.query_one("#edit-container")

        if self.edit_mode:
            view_container.display = False
            edit_container.display = True
            editor = self.query_one("#text-editor", TextArea)
            editor.focus()
        else:
            # Update viewer with editor's current contents
            editor = self.query_one("#text-editor", TextArea)
            self.query_one("#markdown-viewer", Markdown).update(editor.text)
            edit_container.display = False
            view_container.display = True

        self.query_one("#metadata-header", MetadataHeader).update_metadata(self.current_note, self.edit_mode)

    def action_save_note(self) -> None:
        """Saves current note edits to disk and updates SQLite index."""
        if not self.current_note:
            return

        editor = self.query_one("#text-editor", TextArea)
        self.current_note.body = editor.text
        self.storage.save_note(self.current_note)
        self.indexer.index_note(self.current_note)

        # Update viewer
        self.query_one("#markdown-viewer", Markdown).update(self.current_note.body)
        self.notify("Note saved successfully!", title="Saved", severity="information")

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
