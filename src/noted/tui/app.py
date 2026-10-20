import asyncio
import hashlib
import os
import unicodedata
from dataclasses import replace
from pathlib import Path
from rich.text import Text
from typing import Optional

os.environ.setdefault('TEXTUAL_DISABLE_KITTY_KEY', '1')
from textual.app import App, ComposeResult
from textual import events, work
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.worker import get_current_worker
from textual.widgets import Button, Checkbox, Footer, Header, Input, ListView, Markdown, Select, Static, TextArea, Tree
from noted.config import Config, load_config
from noted.db import DatabaseManager
from noted.indexer import NoteIndexer
from noted.models import Note, NoteSummary, normalize_tags
from noted.storage import StorageManager, ExternalChangeError
from noted.editor import open_in_editor
import noted.markdown_colors  # noqa: F401
from noted.tui.theme import PALETTE
from noted.tui.widgets import MetadataHeader, NoteListItem, VietnameseInput, VietnameseTextArea, NoteFooter
from noted.tui.screens import (NewNoteModal, RenameNoteModal, ConfirmDeleteModal, HelpModal,
    UnlockNoteModal, LockNoteModal, ManageLockModal, ChangePasswordModal,
    ConfirmRemoveLockModal, ColorFormatModal, TextPromptModal, ActionMenuModal,
    ConflictModal, FolderPickerModal, FilterNotesModal)

PAGE_SIZE = 100
LARGE_NOTE_BYTES = 256 * 1024


def fingerprint(text: str) -> bytes:
    return hashlib.blake2b(text.encode('utf-8'), digest_size=16).digest()


class NotedApp(App[None]):
    TITLE = 'NOTED'
    SUB_TITLE = 'A quiet space for your notes'
    CSS_PATH = 'styles.tcss'
    def get_css_variables(self):
        return {**super().get_css_variables(), **{'noted-' + k: v for k, v in PALETTE.items()}}
    BINDINGS = [
        Binding('ctrl+q', 'quit', 'Quit', priority=True),
        Binding('n', 'new_note', 'New'), Binding('j', 'today_journal', 'Journal', show=False),
        Binding('e', 'toggle_edit', 'Edit'),
        Binding('ctrl+n', 'quick_capture', 'Capture', priority=True, show=False),
        Binding('ctrl+o', 'toggle_navigation', 'Folders', priority=True),
        Binding('ctrl+l', 'toggle_list', 'Notes', priority=True, show=False),
        Binding('ctrl+p', 'toggle_preview', 'Preview', priority=True, show=False),
        Binding('f2', 'toggle_preview', 'View/Edit', priority=True, show=False),
        Binding('ctrl+w', 'toggle_split', 'Split', priority=True, show=False),
        Binding('ctrl+s', 'save_note', 'Save', priority=True),
        Binding('ctrl+b', 'format_bold', 'Bold', priority=True, show=False),
        Binding('ctrl+i', 'format_italic', 'Italic', priority=True, show=False),
        Binding('ctrl+k', 'format_code', 'Code', priority=True, show=False),
        Binding('ctrl+h', 'format_heading', 'Heading', priority=True, show=False),
        Binding('ctrl+t', 'format_todo', 'Todo', priority=True, show=False),
        Binding('ctrl+m', 'format_color', 'Color', priority=True, show=False),
        Binding('ctrl+e', 'open_external', 'External editor', show=False),
        Binding('c', 'copy_content', 'Copy', show=False),
        Binding('ctrl+y', 'copy_content', 'Copy', priority=True, show=False),
        Binding('r', 'rename_note', 'Rename', show=False),
        Binding('u', 'unlock_note', 'Unlock', show=False),
        Binding('l', 'lock_note', 'Lock', show=False),
        Binding('d', 'delete_note', 'Delete', show=False),
        Binding('slash', 'focus_search', 'Search'),
        Binding('escape', 'exit_edit_mode', 'Back', priority=True, show=False),
        Binding('question_mark', 'show_help', 'Help'),
    ]

    def __init__(self, custom_config: Config | None = None, **kwargs):
        super().__init__(**kwargs)
        self.custom_config = custom_config
        self.current_note = None
        self.note_mode = 'view'
        self.unlocked_notes: dict[str, str] = {}
        self.session_passwords: dict[str, str] = {}
        self._saved_digest = fingerprint('')
        self._preview_timer = self._autosave_timer = self._search_timer = self._status_timer = None
        self._index_pending = False
        self._conflict_open = False
        self._scope = 'all'
        self.selected_folder: Path | None = None
        self.selected_tags: list[str] = []
        self.selected_type: str | None = None
        self.page = self.total_notes = self._tag_page = 0
        self.save_state = 'Saved'
        self.large_note = False
        self._nav_open = self._list_open = None
        self._nav_animation_version = 0
        self._editor_position = (0, 0)
        self._editor_scroll = (0, 0)
        self._syncing = False
        self._resync_requested = False
        self._list_lock = asyncio.Lock()
        self._tags_lock = asyncio.Lock()
        self._binding_note_present = None

    def show_modal(self, screen, callback=None):
        def deliver(result):
            if self.is_running and not self._closing and self.screen_stack and callback is not None:
                return callback(result)
        return self.push_screen(screen, deliver if callback is not None else None)

    def main_query(self, selector, expect_type=None):
        return self.screen_stack[0].query_one(selector, expect_type)

    @property
    def edit_mode(self):
        return self.note_mode in ('edit', 'split')

    @edit_mode.setter
    def edit_mode(self, value):
        self.set_mode('edit' if value else 'view')

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id='main-container'):
            with VerticalScroll(id='navigation'):
                yield Button('+ Quick capture', id='nav-capture', variant='primary')
                for scope, label in [('all', 'All notes'), ('pinned', 'Pinned'), ('journals', 'Journals'), ('archive', 'Archive')]:
                    yield Button(label, id='nav-' + scope, classes='nav-btn', variant='primary' if scope == 'all' else 'default')
                yield Static('FOLDERS', classes='section-label')
                with Horizontal(classes='compact-row'):
                    yield Button('+ New', id='folder-create', classes='compact-btn')
                    yield Button('Manage', id='folder-manage', classes='compact-btn')
                yield Tree('notes/', id='folder-tree')
                yield Static('TAGS', classes='section-label')
                yield VietnameseInput(placeholder='Find tag…', id='tag-search', compact=True)
                yield ListView(id='tag-list')
                with Horizontal(classes='compact-row'):
                    yield Button('‹', id='tags-prev', classes='compact-btn')
                    yield Button('›', id='tags-next', classes='compact-btn')
            with Vertical(id='sidebar'):
                yield VietnameseInput(placeholder='Search notes… [/]', id='search-input')
                yield Static('All notes', id='list-scope', markup=False)
                with Horizontal(classes='compact-row'):
                    yield Select([('Updated', 'updated'), ('Created', 'created'), ('Title', 'title')], value='updated', allow_blank=False, id='sort-order', compact=True)
                    yield Button('Filter', id='filter-more', classes='compact-btn')
                yield Checkbox('Include subfolders', value=True, id='recursive-filter')
                yield Static('', id='active-filters', markup=False)
                yield ListView(id='notes-list')
                yield Static('', id='list-empty', markup=False)
                with Horizontal(id='page-controls'):
                    yield Button('‹', id='page-prev', classes='compact-btn')
                    yield Static('', id='page-status', markup=False)
                    yield Button('›', id='page-next', classes='compact-btn')
            with Vertical(id='content-area'):
                yield MetadataHeader(id='metadata-header')
                yield Static('', id='resource-status', markup=False)
                with Horizontal(id='main-workspace'):
                    with Vertical(id='edit-container'):
                        with Horizontal(id='formatting-toolbar'):
                            for label, name, tip in [('B', 'bold', 'Bold · Ctrl+B'), ('I', 'italic', 'Italic · Ctrl+I'),
                                ('</>', 'code', 'Code · Ctrl+K'), ('H#', 'heading', 'Heading · Ctrl+H'),
                                ('☑', 'todo', 'Checkbox · Ctrl+T'), ('❝', 'quote', 'Quote'),
                                ('Tip', 'callout', 'Callout'), ('Color', 'color', 'Colors · Ctrl+M')]:
                                yield Button(label, id='btn-fmt-' + name, classes='fmt-btn', tooltip=tip)
                        yield VietnameseTextArea(id='text-editor', max_checkpoints=20)
                    with VerticalScroll(id='view-container'):
                        with Vertical(id='locked-note-card'):
                            yield Static('🔒 PROTECTED NOTE', id='locked-card-title')
                            yield Static('This note is encrypted with AES-256.\nClick below or press [b]u[/b] to unlock:', id='locked-card-desc')
                            yield Button('🔓 Unlock note', id='btn-screen-unlock', variant='primary')
                        yield Markdown(id='markdown-viewer')
                        yield Button('Render full note', id='render-full')
                with Horizontal(id='empty-actions'):
                    yield Button('Create note', id='empty-create', variant='primary')
                    yield Button('Clear filters', id='empty-clear')
        yield NoteFooter()

    async def on_mount(self):
        self.config = self.custom_config or load_config()
        self.animation_level = 'none' if self.config.animation == 'off' else 'full'
        self.screen.set_class(self.config.animation != 'off', '-motion')
        self.storage = StorageManager(self.config)
        self.db = DatabaseManager(self.config.db_path)
        self.indexer = NoteIndexer(self.db, self.storage)
        self.build_folder_tree()
        await self.refresh_tags()
        await self.refresh_notes_list()
        self.set_mode('view')
        self.apply_layout()
        self.main_query('#view-container').can_focus = True
        self.main_query('#notes-list' if self.size.width >= 100 else '#view-container').focus()
        self.start_sync()

    def start_sync(self):
        if self._syncing:
            self._resync_requested = True
            return
        self._syncing = True
        self.main_query('#resource-status', Static).update('Indexing…')
        self._run_sync()

    @work(thread=True, group='index-sync')
    def _run_sync(self):
        worker = get_current_worker()
        error = None
        try:
            self.indexer.sync_all(cancelled=lambda: worker.is_cancelled)
        except Exception as exc:
            error = type(exc).__name__
        finally:
            if self.is_running and not self._closing and not worker.is_cancelled:
                self.call_from_thread(self._finish_sync, error)

    async def _finish_sync(self, error):
        self._syncing = False
        await self.sync_finished(error)
        if self._resync_requested and self.is_running and not self._closing:
            self._resync_requested = False
            self.start_sync()

    async def sync_finished(self, error):
        if not self.is_running or not self.screen_stack or self.screen_stack[0]._pruning:
            return
        if error:
            self.main_query('#resource-status', Static).update('Indexing failed · ' + error)
        else:
            await self.refresh_notes_list()
            if not self.is_running:
                return
            await self.refresh_tags()
            if not self.is_running:
                return
            self.update_resource_status()
            if self.indexer.sync_errors:
                self.notify('Some files could not be indexed. Use note sync to retry.', severity='warning')

    def filters(self):
        return dict(folder=self.selected_folder, recursive=self.main_query('#recursive-filter', Checkbox).value,
            tags=self.selected_tags, archived=self._scope == 'archive', pinned=self._scope == 'pinned',
            note_type='journal' if self._scope == 'journals' else self.selected_type,
            query=unicodedata.normalize('NFC', self.main_query('#search-input', Input).value.strip()))

    async def refresh_notes_list(self, select_id=None):
        async with self._list_lock:
            await self._refresh_notes_page(select_id)

    async def _refresh_notes_page(self, select_id=None):
        filters = self.filters()
        self.total_notes = self.indexer.count_notes(**filters)
        self.page = min(self.page, max(0, (self.total_notes - 1) // PAGE_SIZE))
        notes = self.indexer.list_notes(limit=PAGE_SIZE, offset=self.page * PAGE_SIZE,
            sort=self.main_query('#sort-order', Select).value, **filters)
        listing = self.main_query('#notes-list', ListView)
        await listing.clear()
        await listing.extend(NoteListItem(n) for n in notes)
        selected = select_id or (self.current_note.id if self.current_note else None)
        listing.index = next((i for i, n in enumerate(notes) if n.id == selected), None if self.current_note else 0 if notes else None)
        if not self.current_note and notes:
            for summary in notes:
                try:
                    self.open_note(self.storage.read_note(summary.filepath))
                    break
                except (OSError, ValueError):
                    continue
        self.main_query('#page-status', Static).update(f'{self.page + 1} / {max(1, (self.total_notes + 99) // 100)} · {self.total_notes}')
        self.main_query('#page-prev', Button).disabled = self.page == 0
        self.main_query('#page-next', Button).disabled = (self.page + 1) * PAGE_SIZE >= self.total_notes
        self.main_query('#list-empty', Static).update('No results. Clear filters or create a note.' if not notes else '')
        self.main_query('#empty-actions').display = not notes
        path = str(self.selected_folder.relative_to(self.config.notes_subdir.resolve())) if self.selected_folder else self._scope.title()
        self.main_query('#list-scope', Static).update(path or 'notes/')
        self.main_query('#active-filters', Static).update((self.selected_type.title() + ' · ' if self.selected_type else '') + ' '.join('#' + t for t in self.selected_tags))
        self.main_query('#recursive-filter').display = self.selected_folder is not None

    def body(self) -> str:
        if not self.current_note:
            return ''
        if self.edit_mode:
            return self.main_query('#text-editor', TextArea).text
        return self.unlocked_notes.get(self.current_note.id, '') if self.current_note.encrypted else self.current_note.body

    def is_unlocked(self):
        return bool(self.current_note and (not self.current_note.encrypted or self.current_note.id in self.unlocked_notes))

    def open_note(self, note: Note) -> bool:
        if self.current_note and not self.save_current_note(silent=True):
            return False
        self.cancel_content_timers()
        self.unlocked_notes.clear()
        self.current_note = note
        if note.encrypted and note.id in self.session_passwords:
            try:
                self.unlocked_notes[note.id] = self.storage.unlock_note(note, self.session_passwords[note.id])
            except Exception:
                self.session_passwords.pop(note.id, None)
        self._editor_position = self._editor_scroll = (0, 0)
        self._saved_digest = fingerprint(self.unlocked_notes.get(note.id, '') if note.encrypted else note.body)
        self._index_pending = False
        self.save_state = 'Saved'
        # Read view on selection avoids a stale editor saving into the new note.
        self.note_mode = 'view'
        self.display_mode()
        self.fade(self.main_query('#view-container'), 0.12)
        if self.size.width < 100:
            self._list_open = False
            self.apply_layout()
        return True

    def load_note_by_summary(self, summary):
        try:
            return self.open_note(self.storage.read_note(summary.filepath))
        except (OSError, ValueError) as exc:
            self.notify(f'Cannot open note: {exc}', severity='error')
            return False

    def cancel_content_timers(self):
        for name in ('_preview_timer', '_autosave_timer', '_status_timer'):
            timer = getattr(self, name)
            if timer:
                timer.stop()
                setattr(self, name, None)

    def fade(self, widget, duration=0.14):
        if self.config.animation != 'off':
            widget.styles.opacity = 0
            widget.styles.animate('opacity', 1, duration=duration, easing='out_cubic')

    def display_mode(self, draft=None):
        editor = self.main_query('#text-editor', TextArea)
        viewer = self.main_query('#markdown-viewer', Markdown)
        active_body = self.unlocked_notes.get(self.current_note.id, '') if self.current_note and self.current_note.encrypted else (self.current_note.body if self.current_note else '')
        if draft is not None:
            active_body = draft
        self.large_note = len(active_body.encode('utf-8')) >= LARGE_NOTE_BYTES
        editable = self.is_unlocked()
        editor.read_only = not editable
        self.main_query('#edit-container').display = self.edit_mode and editable
        self.main_query('#view-container').display = self.note_mode in ('view', 'split') or not editable
        self.main_query('#locked-note-card').display = bool(self.current_note and not editable)
        viewer.display = editable or self.current_note is None
        if self.edit_mode and editable:
            editor.language = None if self.large_note else 'markdown'
            if editor.text != active_body:
                editor.load_text(active_body)
                editor.move_cursor(self._editor_position)
                editor.scroll_to(x=self._editor_scroll[0], y=self._editor_scroll[1], animate=False)
            if self.note_mode == 'split' and not self.large_note:
                viewer.update(active_body or '*Empty note.*')
            else:
                viewer.update('')
                viewer.remove_children()
                if self.note_mode == 'split':
                    viewer.update('*Large note · use Preview or Render full note.*')
        else:
            self._editor_position = editor.cursor_location
            self._editor_scroll = (editor.scroll_x, editor.scroll_y)
            editor.load_text('')
            editor.language = None
            if editable:
                text = active_body
                if self.large_note:
                    text = text.encode('utf-8')[:LARGE_NOTE_BYTES].decode('utf-8', errors='ignore') + '\n\n*Preview limited to 256 KB.*'
                viewer.update(text or '*Empty note.*')
            else:
                viewer.update('' if self.current_note else '*Choose a note or create your first one.*')
                viewer.remove_children()
        self.main_query('#render-full').display = bool(self.current_note and self.large_note and editable)
        self.main_query('#formatting-toolbar').display = self.edit_mode
        self.update_header()
        self.update_resource_status()

    def update_header(self):
        self.main_query(MetadataHeader).update_metadata(self.current_note, self.note_mode,
            is_unlocked=bool(self.current_note and self.current_note.id in self.unlocked_notes))
        self.set_save_state(self.save_state)
        present = self.current_note is not None
        if self._binding_note_present != present:
            self._binding_note_present = present
            self.refresh_bindings()

    def update_resource_status(self):
        message = 'Large note · Live preview paused · Syntax highlighting off' if self.large_note else ''
        self.main_query('#resource-status', Static).update(message)

    def set_save_state(self, state):
        self.save_state = state
        status = self.main_query('#save-status', Static)
        status.update(state if self.current_note else '')
        status.styles.color = PALETTE['error' if state == 'Save failed' else 'warning' if state == 'Modified' else 'success' if state == 'Saved' else 'muted']
        if self._status_timer:
            self._status_timer.stop()
        if state == 'Saved':
            self._status_timer = self.set_timer(1.2, lambda: setattr(status.styles, 'color', PALETTE['muted']))

    def save_current_note(self, silent=False, *, force=False) -> bool:
        if not self.current_note:
            return True
        if self.current_note.encrypted and not self.is_unlocked():
            return True
        text = unicodedata.normalize('NFC', self.body())
        changed = fingerprint(text) != self._saved_digest
        if not changed and not self._index_pending:
            return True
        self.set_save_state('Saving')
        candidate = replace(self.current_note, body=text)
        try:
            if changed:
                if candidate.encrypted:
                    password = self.session_passwords.get(candidate.id)
                    if not password:
                        raise ValueError('Unlock this note before saving.')
                    if force:
                        # Validate the overwrite decision against the latest disk version.
                        if candidate.filepath.exists():
                            disk = self.storage.read_note(candidate.filepath)
                            candidate.mtime_ns, candidate.size_bytes = disk.mtime_ns, disk.size_bytes
                        else:
                            candidate.mtime_ns = candidate.size_bytes = 0
                    self.storage.lock_note(candidate, password)
                    self.unlocked_notes[candidate.id] = text
                else:
                    self.storage.save_note(candidate, force=force)
                self.current_note = candidate
                self._saved_digest = fingerprint(text)
                self._index_pending = True
            self.indexer.index_note(self.current_note)
            self._index_pending = False
            self.set_save_state('Saved')
            if self.note_mode == 'split' and not self.large_note:
                self._update_live_preview()
            return True
        except ExternalChangeError:
            self.set_save_state('Save failed')
            if not self._conflict_open:
                self._conflict_open = True
                conflicted_id = self.current_note.id
                def resolve(choice):
                    self._conflict_open = False
                    if not self.current_note or self.current_note.id != conflicted_id:
                        return
                    if choice == 'overwrite':
                        self.save_current_note(force=True)
                    elif choice == 'reload':
                        try:
                            disk = self.storage.read_note(self.current_note.filepath)
                        except (OSError, ValueError) as exc:
                            self.notify(f'Reload unavailable. Draft preserved: {exc}', severity='error')
                            self.set_save_state('Save failed')
                            return
                        self._saved_digest = fingerprint(self.body())
                        self.open_note(disk)
                self.show_modal(ConflictModal(), resolve)
            return False
        except (OSError, ValueError) as exc:
            self.set_save_state('Save failed')
            self.notify(f'Could not save: {exc}', severity='error')
            return False
        except Exception as exc:
            self.set_save_state('Save failed')
            self.notify(f'Index update failed ({type(exc).__name__}). Retry Save.', severity='error')
            return False

    def on_text_area_changed(self, event: TextArea.Changed):
        if not self.edit_mode or not self.current_note or not self.is_unlocked():
            return
        if fingerprint(event.text_area.text) == self._saved_digest:
            return
        self.large_note = len(event.text_area.text.encode('utf-8')) >= LARGE_NOTE_BYTES
        if self.large_note and event.text_area.language is not None:
            event.text_area.language = None
        if not self._conflict_open and self.save_state != 'Save failed':
            self.set_save_state('Modified')
        if self._autosave_timer:
            self._autosave_timer.stop()
        self._autosave_timer = self.set_timer(1, lambda: self.save_current_note(silent=True))
        if self.note_mode == 'split' and not self.large_note:
            if self._preview_timer:
                self._preview_timer.stop()
            self._preview_timer = self.set_timer(0.2, self._update_live_preview)
        self.update_resource_status()

    def _update_live_preview(self):
        if self.note_mode == 'split' and not self.large_note and self.is_unlocked():
            self.main_query('#markdown-viewer', Markdown).update(self.body() or '*Empty note.*')

    def set_mode(self, mode, *, save=True):
        if mode not in ('view', 'edit', 'split'):
            return
        if mode != 'view' and not self.is_unlocked():
            if self.current_note:
                self.action_unlock_note()
            return
        if mode == 'split' and self.size.width < 160:
            self.notify('Split view needs at least 160 columns.', severity='information')
            mode = 'edit'
        if mode == self.note_mode:
            return
        draft = self.body() if not save and self.edit_mode else None
        if save and not self.save_current_note(silent=True):
            return
        if save:
            self.cancel_content_timers()
        elif self._preview_timer:
            self._preview_timer.stop()
        self.note_mode = mode
        self.display_mode(draft=draft)
        self.fade(self.main_query('#edit-container' if self.edit_mode else '#view-container'))
        if self.edit_mode:
            self.main_query('#text-editor').focus()
        else:
            self.main_query('#notes-list' if self.size.width >= 100 else '#view-container').focus()

    def on_resize(self, event: events.Resize):
        if hasattr(self, 'config'):
            self._nav_open = self._list_open = None
            self._nav_animation_version += 1
            self.main_query('#navigation').styles.opacity = 1
            self.main_query('#navigation').styles.offset = (0, 0)
            self.apply_layout(event.size.width)
            self.call_after_refresh(self.update_header)

    def apply_layout(self, width=None):
        width = self.size.width if width is None else width
        self.screen_stack[0].set_class(width < 140, '-compact')
        self.screen_stack[0].set_class(width < 100, '-narrow')
        self.main_query('#navigation').display = width >= 140 if self._nav_open is None else self._nav_open
        self.main_query('#sidebar').display = width >= 100 if self._list_open is None else self._list_open
        if width < 160 and self.note_mode == 'split':
            self.set_mode('edit', save=False)
        if hasattr(self, 'config'):
            self.update_header()

    def action_toggle_navigation(self):
        nav = self.main_query('#navigation')
        self._nav_open = not (nav.display if self._nav_open is None else self._nav_open)
        self._nav_animation_version += 1
        version = self._nav_animation_version
        if self._nav_open:
            self.apply_layout()
            nav.styles.offset = (0, 0)
            target = nav.styles.offset
            if self.config.animation != 'off':
                nav.styles.offset = (-3, 0)
                nav.styles.opacity = 0
                nav.styles.animate('offset', target, duration=0.18, easing='out_cubic')
                nav.styles.animate('opacity', 1, duration=0.18)
            self.main_query('#folder-tree').focus()
        elif self.config.animation == 'off':
            self.apply_layout()
        else:
            def finish():
                if version == self._nav_animation_version and not self._nav_open:
                    self.apply_layout()
                    nav.styles.opacity = 1
                    nav.styles.offset = (0, 0)
            nav.styles.animate('opacity', 0, duration=0.1, on_complete=finish)

    def action_toggle_list(self):
        self._list_open = not self.main_query('#sidebar').display
        self.apply_layout()
        if self.main_query('#sidebar').display:
            self.main_query('#notes-list').focus()

    def on_list_view_selected(self, event: ListView.Selected):
        if event.list_view.id == 'notes-list' and isinstance(event.item, NoteListItem):
            if not self.current_note or event.item.summary.id != self.current_note.id:
                self.load_note_by_summary(event.item.summary)
        elif event.list_view.id == 'tag-list':
            tag = event.item.tag_value
            self.selected_tags = [t for t in self.selected_tags if t != tag] if tag in self.selected_tags else self.selected_tags + [tag]
            self.page = 0
            self.call_later(self.refresh_notes_list)
            self.call_later(self.refresh_tags)

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == 'search-input':
            if self._search_timer:
                self._search_timer.stop()
            self.page = 0
            self._search_timer = self.set_timer(0.15, self.refresh_notes_list)
        elif event.input.id == 'tag-search':
            self._tag_page = 0
            if self._search_timer:
                self._search_timer.stop()
            self._search_timer = self.set_timer(0.15, self.refresh_tags)

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == 'search-input':
            self.action_focus_list()

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == 'sort-order' and hasattr(self, 'indexer'):
            self.page = 0
            self.call_later(self.refresh_notes_list)

    def on_checkbox_changed(self, event: Checkbox.Changed):
        if hasattr(self, 'indexer'):
            self.page = 0
            self.call_later(self.refresh_notes_list)

    def action_next_page(self):
        if (self.page + 1) * PAGE_SIZE < self.total_notes:
            self.page += 1
            self.call_later(self.refresh_notes_list)

    def action_previous_page(self):
        self.page = max(0, self.page - 1)
        self.call_later(self.refresh_notes_list)

    def set_scope(self, scope):
        self._scope = scope
        self.selected_folder = None
        self.selected_tags = []
        self.selected_type = None
        self.page = 0
        for name in ('all', 'pinned', 'journals', 'archive'):
            self.main_query('#nav-' + name, Button).variant = 'primary' if name == scope else 'default'
        self.call_later(self.refresh_notes_list)
        if self.size.width < 140:
            self._nav_open = False
            self._list_open = True
            self.apply_layout()

    def build_folder_tree(self):
        tree = self.main_query('#folder-tree', Tree)
        tree.clear()
        tree.root.data = self.config.notes_subdir.resolve()
        self.populate_folder_node(tree.root)
        tree.root.expand()

    def populate_folder_node(self, node):
        if node.children:
            return
        try:
            for path in self.storage.child_folders(node.data):
                node.add(Text(path.name), path, allow_expand=True)
        except OSError:
            pass

    def on_tree_node_expanded(self, event: Tree.NodeExpanded):
        if event.control.id == 'folder-tree':
            self.populate_folder_node(event.node)

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed):
        if event.control.id == 'folder-tree':
            event.node.remove_children()

    def on_tree_node_selected(self, event: Tree.NodeSelected):
        if event.control.id == 'folder-tree':
            self.selected_folder = event.node.data
            self._scope = 'all'
            self.page = 0
            self.call_later(self.refresh_notes_list)
            if self.size.width < 140:
                self._nav_open = False
                self._list_open = True
                self.apply_layout()

    async def refresh_tags(self):
        async with self._tags_lock:
            await self._refresh_tags_page()

    async def _refresh_tags_page(self):
        from textual.widgets import ListItem
        values = self.indexer.list_tags(query=self.main_query('#tag-search', Input).value, limit=30, offset=self._tag_page * 30)
        listing = self.main_query('#tag-list', ListView)
        await listing.clear()
        items = []
        for tag, count in values:
            item = ListItem(Static(f'{"✓ " if tag in self.selected_tags else ""}#{tag}  {count}', markup=False))
            item.tag_value = tag
            items.append(item)
        await listing.extend(items)
        self.main_query('#tags-prev', Button).disabled = self._tag_page == 0
        self.main_query('#tags-next', Button).disabled = len(values) < 30

    def action_new_note(self):
        self.new_note_in(self.selected_folder)

    def action_quick_capture(self):
        self.new_note_in(self.storage.create_folder('Inbox'))

    def new_note_in(self, folder):
        if not self.save_current_note(silent=True):
            return
        def create(result):
            if result is None:
                return
            title, tags = result
            try:
                note = self.storage.create_note(title, tags=tags, folder=folder)
                self.indexer.index_note(note)
                if self.open_note(note):
                    self.set_mode('edit')
                self.call_later(self.refresh_notes_list, note.id)
                self.build_folder_tree()
            except (OSError, ValueError) as exc:
                self.notify(str(exc), severity='error')
        self.show_modal(NewNoteModal(), create)

    def action_today_journal(self):
        if not self.save_current_note(silent=True):
            return
        note = self.storage.get_or_create_today_journal()
        self.indexer.index_note(note)
        self.open_note(note)
        self.call_later(self.refresh_notes_list, note.id)

    def update_note_metadata(self, **changes):
        if not self.current_note or not self.save_current_note(silent=True):
            return False
        candidate = replace(self.current_note, **changes)
        try:
            self.storage.save_note(candidate)
            self.current_note = candidate
            self.indexer.index_note(candidate)
            self.update_header()
            self.call_later(self.refresh_notes_list, candidate.id)
            self.call_later(self.refresh_tags)
            return True
        except (OSError, ValueError) as exc:
            self.notify(str(exc), severity='error')
            return False

    def action_archive_note(self):
        if self.current_note:
            self.update_note_metadata(archived=not self.current_note.archived)

    def action_more(self):
        if not self.current_note:
            return
        note = self.current_note
        actions = [('rename', 'Rename'), ('tags', 'Edit tags'), ('move', 'Move to folder'),
            ('pin', 'Unpin' if note.pinned else 'Pin note'),
            ('archive', 'Restore from archive' if note.archived else 'Archive'),
            ('copy', 'Copy'), ('lock', 'Manage protection'), ('external', 'External editor'), ('delete', 'Delete')]
        self.show_modal(ActionMenuModal('Note actions', actions), self.handle_more)

    def handle_more(self, action):
        if action == 'tags':
            self.show_modal(TextPromptModal('Edit tags', ', '.join(self.current_note.tags),
                'Comma-separated tags. Suggestions update as you type.',
                suggestions=lambda value: 'Suggestions: ' + ', '.join(t for t, _ in self.indexer.list_tags(query=value.split(',')[-1].strip(), limit=8))),
                lambda value: self.update_note_metadata(tags=normalize_tags(value.split(','))) if value is not None else None)
        elif action == 'pin':
            self.update_note_metadata(pinned=not self.current_note.pinned)
        elif action == 'move':
            self.show_modal(FolderPickerModal(self.storage, self.current_note.filepath.parent), self.move_current_note)
        elif action:
            {'rename': self.action_rename_note, 'archive': self.action_archive_note,
             'copy': self.action_copy_content, 'lock': self.action_lock_note,
             'external': self.action_open_external, 'delete': self.action_delete_note}[action]()

    def move_current_note(self, folder):
        if folder is None or not self.save_current_note(silent=True):
            return
        try:
            self.storage.move_note(self.current_note, folder)
            self.indexer.index_note(self.current_note)
            self.update_header()
            self.call_later(self.refresh_notes_list)
            self.build_folder_tree()
        except (OSError, ValueError) as exc:
            self.notify(str(exc), severity='error')

    def folder_action(self, action):
        if action is None:
            return
        base = self.selected_folder or self.config.notes_subdir.resolve()
        if action == 'delete':
            try:
                self.storage.delete_folder(base)
                self.selected_folder = None
                self.build_folder_tree()
                self.call_later(self.refresh_notes_list)
            except (OSError, ValueError) as exc:
                self.notify(f'Only empty folders can be deleted: {exc}', severity='error')
            return
        def apply(value):
            if value is None or not value.strip() or not self.save_current_note(silent=True):
                return
            try:
                if action == 'create':
                    self.storage.create_folder(base / value)
                else:
                    destination = base.parent / value if action == 'rename' else self.config.notes_subdir.resolve() / value
                    self.storage.move_folder(base, destination)
                    if self.current_note and self.current_note.filepath.is_relative_to(base):
                        self.current_note.filepath = destination / self.current_note.filepath.relative_to(base)
                    self.selected_folder = destination
                    self.start_sync()
                self.build_folder_tree()
                self.call_later(self.refresh_notes_list)
                self.update_header()
            except (OSError, ValueError) as exc:
                self.notify(str(exc), severity='error')
        self.show_modal(TextPromptModal({'create': 'Create subfolder', 'rename': 'Rename folder', 'move': 'Move folder'}[action],
            hint='Relative to ' + str(base if action == 'create' else base.parent if action == 'rename' else self.config.notes_subdir)), apply)

    def action_rename_note(self):
        if not self.current_note or not self.save_current_note(silent=True):
            return
        def rename(title):
            if not title:
                return
            try:
                self.storage.rename_note(self.current_note, title)
                self.indexer.index_note(self.current_note)
                self.update_header()
                self.call_later(self.refresh_notes_list, self.current_note.id)
            except (OSError, ValueError) as exc:
                self.notify(str(exc), severity='error')
        self.show_modal(RenameNoteModal(self.current_note.title), rename)

    def action_delete_note(self):
        if not self.current_note:
            return
        note = self.current_note
        def delete(confirmed):
            if not confirmed:
                return
            try:
                self.storage.delete_note(note.filepath)
                self.indexer.remove_note(note.id)
                self.cancel_content_timers()
                self.unlocked_notes.clear()
                self.session_passwords.pop(note.id, None)
                self.current_note = None
                self.note_mode = 'view'
                self.display_mode()
                self.call_later(self.refresh_notes_list)
                self.call_later(self.refresh_tags)
            except OSError as exc:
                self.notify(str(exc), severity='error')
        self.show_modal(ConfirmDeleteModal(note.title), delete)

    def unlock_current(self, password):
        if not self.current_note:
            return
        try:
            text = self.storage.unlock_note(self.current_note, password)
            self.session_passwords[self.current_note.id] = password
            self.unlocked_notes.clear()
            self.unlocked_notes[self.current_note.id] = text
            self._saved_digest = fingerprint(text)
            self.display_mode()
            self.main_query('#notes-list').focus()
        except Exception:
            self.notify('Wrong password or damaged note.', severity='error')

    def action_unlock_note(self):
        if not self.current_note or not self.current_note.encrypted:
            return
        if self.is_unlocked():
            self.action_manage_lock()
        else:
            self.show_modal(UnlockNoteModal(self.current_note.title), lambda password: self.unlock_current(password) if password else None)

    def action_lock_note(self):
        if not self.current_note or not self.save_current_note(silent=True):
            return
        if self.current_note.encrypted:
            self.action_manage_lock() if self.is_unlocked() else self.action_unlock_note()
        else:
            self.show_modal(LockNoteModal(self.current_note.title), self.protect_current)

    def protect_current(self, password):
        if not password or not self.save_current_note(silent=True):
            return
        text = self.body()
        candidate = replace(self.current_note, body=text)
        try:
            self.storage.lock_note(candidate, password)
            self.current_note = candidate
            self.session_passwords[candidate.id] = password
            self.unlocked_notes.clear()
            self.unlocked_notes[candidate.id] = text
            self._saved_digest = fingerprint(text)
            self.indexer.index_note(candidate)
            self.update_header()
            self.call_later(self.refresh_notes_list, candidate.id)
        except (OSError, ValueError) as exc:
            self.notify(str(exc), severity='error')

    def action_manage_lock(self):
        if not self.current_note or not self.is_unlocked():
            return
        def choice(value):
            if value == 'relock':
                self._relock_current_note()
            elif value == 'change_password':
                self._prompt_change_password()
            elif value == 'remove_lock':
                self._prompt_remove_lock()
        self.show_modal(ManageLockModal(self.current_note.title), choice)

    def _prompt_change_password(self):
        self.show_modal(ChangePasswordModal(self.current_note.title), self.protect_current)

    def _prompt_remove_lock(self):
        def remove(confirmed):
            if not confirmed or not self.save_current_note(silent=True):
                return
            candidate = replace(self.current_note, body=self.body(), encrypted=False, salt=None, nonce=None)
            try:
                self.storage.save_note(candidate)
                self.current_note = candidate
                self.unlocked_notes.clear()
                self.session_passwords.pop(candidate.id, None)
                self.indexer.index_note(candidate)
                self.display_mode()
                self.call_later(self.refresh_notes_list, candidate.id)
            except (OSError, ValueError) as exc:
                self.notify(str(exc), severity='error')
        self.show_modal(ConfirmRemoveLockModal(self.current_note.title), remove)

    def _relock_current_note(self):
        if not self.current_note or not self.save_current_note(silent=True):
            return
        self.cancel_content_timers()
        self.note_mode = 'view'
        self.unlocked_notes.clear()
        self.session_passwords.pop(self.current_note.id, None)
        self.main_query('#markdown-viewer', Markdown).update('')
        self.main_query('#markdown-viewer').display = False
        self.main_query('#text-editor', TextArea).load_text('')
        self.display_mode()
        self.main_query('#notes-list').focus()

    def action_copy_content(self):
        if not self.current_note:
            return
        if not self.is_unlocked():
            self.action_unlock_note()
            return
        from noted.clipboard import copy_to_clipboard
        editor = self.main_query('#text-editor', TextArea)
        text = editor.selected_text if self.edit_mode and editor.selected_text else self.body()
        if not copy_to_clipboard(text, app=self):
            self.notify('Clipboard unavailable.', severity='error')
        else:
            self.notify('Copied')

    def action_open_external(self):
        if not self.current_note:
            return
        if self.current_note.encrypted:
            self.notify('External editor is unavailable for encrypted notes.', severity='warning')
            return
        if not self.save_current_note(silent=True):
            return
        with self.suspend():
            open_in_editor(self.current_note.filepath, preferred_editor=self.config.editor)
        self.open_note(self.storage.read_note(self.current_note.filepath))
        self.indexer.index_note(self.current_note)

    def action_quit(self):
        if self.save_current_note(silent=True):
            self.cancel_content_timers()
            self.unlocked_notes.clear()
            self.session_passwords.clear()
            self.exit()

    def check_action(self, action, parameters):
        if action in {'toggle_edit', 'save_note', 'copy_content', 'rename_note', 'delete_note', 'lock_note'}:
            return self.current_note is not None
        return True

    def action_save_note(self):
        self.save_current_note()

    def action_toggle_edit(self):
        self.set_mode('view' if self.edit_mode else 'edit')

    def action_toggle_preview(self):
        self.action_toggle_edit()

    def action_toggle_split(self):
        self.set_mode('view' if self.note_mode == 'split' else 'split')

    def action_exit_edit_mode(self):
        if len(self.screen_stack) > 1 and isinstance(self.screen, ModalScreen):
            self.screen.dismiss(None)
        elif self.edit_mode:
            self.set_mode('view')
        else:
            self.action_focus_list()

    def action_focus_list(self):
        if self.size.width < 100:
            self._list_open = True
            self.apply_layout()
        self.main_query('#notes-list').focus()

    def action_focus_search(self):
        self._list_open = True
        self.apply_layout()
        self.main_query('#search-input').focus()

    def action_show_help(self):
        self.show_modal(HelpModal())

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        name = event.button.id
        if name and name.startswith('footer-'):
            action = name.removeprefix('footer-')
            {'quit': self.action_quit, 'new': self.action_quick_capture,
             'edit': self.action_toggle_edit, 'view': self.action_toggle_preview,
             'folders': self.action_toggle_navigation, 'list': self.action_toggle_list,
             'save': self.action_save_note, 'search': self.action_focus_search,
             'help': self.action_show_help}[action]()
            return
        modes = {'btn-mode-view': 'view', 'btn-mode-edit': 'edit', 'btn-mode-split': 'split'}
        if name in modes:
            self.set_mode(modes[name])
        elif name.startswith('btn-fmt-'):
            getattr(self, 'action_format_' + name.removeprefix('btn-fmt-'))()
        elif name.startswith('nav-'):
            self.action_quick_capture() if name == 'nav-capture' else self.set_scope(name.removeprefix('nav-'))
        elif name == 'tags-prev' or name == 'tags-next':
            self._tag_page = max(0, self._tag_page + (1 if name == 'tags-next' else -1))
            self.call_later(self.refresh_tags)
        elif name == 'folder-create':
            self.folder_action('create')
        elif name == 'folder-manage':
            self.show_modal(ActionMenuModal('Folder actions', [('rename', 'Rename selected folder'), ('move', 'Move selected folder'), ('delete', 'Delete empty folder')]), self.folder_action)
        elif name == 'filter-more':
            self.show_modal(FilterNotesModal(self.selected_tags, self.filters()['note_type']), self.apply_filters)
        elif name == 'render-full':
            self.main_query('#markdown-viewer', Markdown).update(self.body())
        elif name == 'empty-clear':
            self.main_query('#search-input', Input).value = ''
            self.set_scope('all')
        else:
            actions = {'btn-mode-save': self.action_save_note, 'btn-mode-more': self.action_more,
                'btn-screen-unlock': self.action_unlock_note, 'page-prev': self.action_previous_page,
                'page-next': self.action_next_page, 'empty-create': self.action_new_note}
            if name in actions:
                actions[name]()

    def apply_filters(self, value):
        if value is not None:
            self.selected_type, self.selected_tags = value
            if self._scope == 'journals' and self.selected_type != 'journal':
                self._scope = 'all'
            self.page = 0
            self.call_later(self.refresh_notes_list)
            self.call_later(self.refresh_tags)

    def _wrap_or_insert(self, prefix: str, suffix: str, placeholder: str) -> None:
        if not self.edit_mode:
            self.action_toggle_edit()

        if not self.edit_mode or not self.is_unlocked():
            return
        editor = self.main_query("#text-editor", TextArea)
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
        editor = self.main_query("#text-editor", TextArea)
        if "\n" in editor.selected_text:
            self._wrap_or_insert("```python\n", "\n```\n", "")
        else:
            self._wrap_or_insert("`", "`", "code")

    def action_format_heading(self) -> None:
        """Inserts a markdown heading."""
        if not self.edit_mode:
            self.action_toggle_edit()
        if not self.edit_mode or not self.is_unlocked():
            return
        editor = self.main_query("#text-editor", TextArea)
        editor.insert("\n## Heading\n")
        editor.focus()

    def action_format_todo(self) -> None:
        """Inserts an interactive todo checkbox item."""
        if not self.edit_mode:
            self.action_toggle_edit()
        if not self.edit_mode or not self.is_unlocked():
            return
        editor = self.main_query("#text-editor", TextArea)
        editor.insert("\n- [ ] Todo item\n")
        editor.focus()

    def action_format_quote(self) -> None:
        """Inserts a blockquote."""
        if not self.edit_mode:
            self.action_toggle_edit()
        if not self.edit_mode or not self.is_unlocked():
            return
        editor = self.main_query("#text-editor", TextArea)
        editor.insert("\n> Blockquote text\n")
        editor.focus()

    def action_format_callout(self) -> None:
        """Inserts a colored callout block (e.g. [!TIP] or [!NOTE])."""
        if not self.edit_mode:
            self.action_toggle_edit()
        if not self.edit_mode or not self.is_unlocked():
            return
        editor = self.main_query("#text-editor", TextArea)
        editor.insert("\n> [!TIP]\n> Highlighted tip or note\n")
        editor.focus()

    def action_format_color(self) -> None:
        """Opens ColorFormatModal to apply colored highlights, alert blocks, or diff colors."""
        if not self.edit_mode:
            self.action_toggle_edit()

        if not self.edit_mode or not self.is_unlocked():
            return
        editor = self.main_query("#text-editor", TextArea)
        selected = editor.selected_text or "Highlighted text"

        def apply_template(template: Optional[str]) -> None:
            if not template:
                return
            formatted = template.format(text=selected)
            if editor.selected_text:
                editor.replace(formatted, editor.selection.start, editor.selection.end)
            else:
                editor.insert(formatted)
            editor.focus()

        self.show_modal(ColorFormatModal(), apply_template)

