import unicodedata
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.document._document import EditResult, Location
from textual.widgets import Button, Input, ListItem, Static, TextArea, Footer
from noted.models import Note, NoteSummary
from rich.text import Text
from noted.tui.theme import PALETTE

class VietnameseTextArea(TextArea):
    """Enhanced TextArea optimized for Vietnamese IMEs (GoTiengViet, EVKey, OpenKey, UniKey).

    Key enhancements:
    - Synchronous key dispatch for backspace, delete, and navigation in _on_key to eliminate
      the race condition where rapid synthetic backspaces and replacement characters interleave.
    - Normalizes all typed, pasted, or loaded text to standard Unicode NFC (precomposed).
    - Automatically combines standalone combining diacritical marks (Unicode category 'Mn', e.g. acute,
      grave, hook, tilde, dot-below) with preceding vowels, preventing double-vowels or dropped tone marks.
    - Preserves cursor position and smooth keyboard-first editing.
    """

    def load_text(self, text: str) -> None:
        """Loads text normalized to standard NFC."""
        if text:
            text = unicodedata.normalize("NFC", text)
        super().load_text(text)

    def replace(
        self,
        insert: str,
        start: Location,
        end: Location,
        *,
        maintain_selection_offset: bool = True,
    ) -> EditResult:
        if insert:
            insert = unicodedata.normalize("NFC", insert)
        return super().replace(insert, start, end, maintain_selection_offset=maintain_selection_offset)

    def action_copy(self) -> None:
        """Copy selected text (or entire content if nothing selected) to system clipboard."""
        from noted.clipboard import copy_to_clipboard
        text = self.selected_text or self.text
        if text:
            if copy_to_clipboard(text, app=self.app):
                msg = "Selection copied" if self.selected_text else "Note copied"
                self.notify(msg, severity="information")

    async def _on_key(self, event: events.Key) -> None:
        """Synchronously handle editing keys at the widget level.

        This eliminates race conditions with external IMEs (GoTiengViet, EVKey, OpenKey)
        where rapid bursts of synthetic Backspaces and replacement characters arrive in
        the same input buffer. Handling backspaces directly in _on_key ensures they execute
        in exact chronological order before subsequent printable characters are inserted.
        """
        if self.read_only:
            return

        if event.key == "backspace":
            event.stop()
            event.prevent_default()
            self.action_delete_left()
            return
        elif event.key == "delete":
            event.stop()
            event.prevent_default()
            self.action_delete_right()
            return
        elif event.key == "left":
            event.stop()
            event.prevent_default()
            self.action_cursor_left()
            return
        elif event.key == "right":
            event.stop()
            event.prevent_default()
            self.action_cursor_right()
            return
        elif event.key == "shift+left":
            event.stop()
            event.prevent_default()
            self.action_cursor_left(True)
            return
        elif event.key == "shift+right":
            event.stop()
            event.prevent_default()
            self.action_cursor_right(True)
            return

        await super()._on_key(event)

    def _replace_via_keyboard(
        self,
        insert: str,
        start: Location,
        end: Location,
    ) -> EditResult | None:
        if not insert or self.read_only:
            return super()._replace_via_keyboard(insert, start, end)

        norm_insert = unicodedata.normalize("NFC", insert)

        # Check if incoming character is a combining diacritical mark (Mn)
        if start == end and len(norm_insert) == 1 and unicodedata.category(norm_insert).startswith("M"):
            row, col = start
            if col > 0:
                line = self.document.get_line(row)
                prev_char = line[col - 1]
                combined = unicodedata.normalize("NFC", prev_char + norm_insert)
                if combined != prev_char + norm_insert:
                    # Replace preceding character with combined accented character
                    return self.replace(combined, (row, col - 1), (row, col), maintain_selection_offset=False)

        return super()._replace_via_keyboard(norm_insert, start, end)


class VietnameseInput(Input):
    """Enhanced Input widget optimized for Vietnamese IMEs (GoTiengViet, EVKey, OpenKey).

    Handles Backspace and Delete synchronously at the widget level to prevent
    out-of-order execution when typing search terms or note titles quickly.
    """

    def insert_text_at_cursor(self, text: str) -> None:
        if text:
            text = unicodedata.normalize("NFC", text)
        super().insert_text_at_cursor(text)

    def replace(self, text: str, start: int, end: int) -> None:
        if text:
            text = unicodedata.normalize("NFC", text)
        super().replace(text, start, end)

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "backspace":
            event.stop()
            event.prevent_default()
            self.action_delete_left()
            return
        elif event.key == "delete":
            event.stop()
            event.prevent_default()
            self.action_delete_right()
            return
        elif event.key == "left":
            event.stop()
            event.prevent_default()
            self.action_cursor_left()
            return
        elif event.key == "right":
            event.stop()
            event.prevent_default()
            self.action_cursor_right()
            return

        await super()._on_key(event)


class NoteListItem(ListItem):
    def __init__(self, summary: NoteSummary):
        super().__init__()
        self.summary = summary
        self.tooltip = str(summary.filepath)

    def compose(self) -> ComposeResult:
        note = self.summary
        prefix = "* " if note.pinned else ""
        if note.encrypted:
            prefix += "[locked] "
        text = Text(prefix + note.title + "\n", style=PALETTE['text'])
        text.stylize("bold", 0, len(prefix + note.title))
        from datetime import datetime
        updated = datetime.fromtimestamp(note.mtime_ns / 1e9).strftime('%b %d') if note.mtime_ns else note.date[:10]
        text.append(updated + "  " + " ".join('#' + t for t in note.tags[:2]) + "\n", style=PALETTE['secondary'])
        text.append(note.filepath.parent.name + " / ", style=PALETTE['muted'])
        import re
        highlighted = False
        for part in re.split(r'(\[\[/?HIGHLIGHT\]\])', note.excerpt):
            if part == '[[HIGHLIGHT]]':
                highlighted = True
            elif part == '[[/HIGHLIGHT]]':
                highlighted = False
            else:
                text.append(part, style=('bold ' + PALETTE['accent']) if highlighted else PALETTE['muted'])
        yield Static(text, classes="note-item-text")


class MetadataHeader(Vertical):
    def compose(self) -> ComposeResult:
        yield Static("No note selected", id="metadata-info", markup=False)
        yield Static("", id="metadata-details", markup=False)
        with Horizontal(id="mode-button-group"):
            for label, name, tip in [
                ('View', 'view', 'View note (Ctrl+P)'), ('Edit', 'edit', 'Edit note (e)'),
                ('Split', 'split', 'Live preview (Ctrl+W, terminal ≥160 columns)'),
                ('Save', 'save', 'Save now (Ctrl+S)'), ('More', 'more', 'Organize and manage note')]:
                yield Button(label, id=f"btn-mode-{name}", classes="mode-btn", tooltip=tip)
            yield Static("Saved", id="save-status", markup=False)

    def update_metadata(self, note: Note | None, current_mode: str, is_unlocked: bool = False) -> None:
        title = self.query_one('#metadata-info', Static)
        title.update(note.title if note else 'No note selected')
        title.tooltip = note.title if note else ''
        details = self.query_one('#metadata-details', Static)
        if note:
            state = ('Unlocked' if is_unlocked else 'Locked') if note.encrypted else note.note_type.title()
            root = getattr(getattr(self.app, 'config', None), 'notes_dir', None)
            path = str(note.filepath.parent.resolve().relative_to(root.resolve())) if root and note.filepath else ''
            details.update(f"{path} · {state}  " + ' '.join('#' + t for t in note.tags))
            details.tooltip = str(note.filepath)
        else:
            details.update('Create a note or choose one from the list.')
        for mode in ('view', 'edit', 'split'):
            btn = self.query_one(f'#btn-mode-{mode}', Button)
            btn.variant = 'primary' if mode == current_mode else 'default'
        for button in self.query(Button):
            button.disabled = note is None
        self.query_one('#btn-mode-split', Button).disabled = note is None or self.app.size.width < 160


class NoteFooter(Footer):
    """Stable controls: avoid rebuilding and binding footer widgets on every focus change."""
    CONTROLS = [('quit', '^Q Quit'), ('new', '^N Capture'), ('edit', 'e Edit'),
                ('view', '^P View'), ('folders', '^O Folders'), ('list', '^L Notes'),
                ('save', '^S Save'), ('search', '/ Search'), ('help', '? Help')]

    def compose(self):
        for action, label in self.CONTROLS:
            yield Button(label, id='footer-' + action, classes='footer-btn')

    def bindings_changed(self, screen):
        if not self.is_mounted:
            return
        editing = getattr(self.app, 'edit_mode', False)
        has_note = getattr(self.app, 'current_note', None) is not None
        for action, _ in self.CONTROLS:
            control = self.query_one('#footer-' + action, Button)
            control.display = (action != 'edit' or has_note and not editing) and (action != 'view' or editing) and (action != 'save' or editing) and (action not in {'search', 'help'} or not editing)
