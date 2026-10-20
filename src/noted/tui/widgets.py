import unicodedata
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.document._document import EditResult, Location
from textual.widgets import Button, Input, ListItem, Static, TextArea
from noted.models import Note, NoteSummary

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
                msg = "Đã copy đoạn chọn vào Clipboard! ✓" if self.selected_text else "Đã copy nội dung vào Clipboard! ✓"
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
    """A list item representing a note summary in the sidebar."""

    def __init__(self, summary: NoteSummary):
        super().__init__()
        self.summary = summary

    def compose(self) -> ComposeResult:
        if self.summary.encrypted:
            icon = "🔒"
        elif self.summary.note_type == "journal":
            icon = "📓"
        else:
            icon = "📝"
        short_date = self.summary.date.replace("T", " ")[:10]
        tags_str = " ".join(f"#{t}" for t in self.summary.tags[:3])
        if tags_str:
            tags_str = f" [#7dcfff]{tags_str}[/#7dcfff]"

        title = self.summary.title
        if len(title) > 22:
            title = title[:21] + "…"

        text = (
            f"{icon} [bold #c0caf5]{title}[/bold #c0caf5]\n"
            f"   [#565f89]{short_date}[/#565f89]{tags_str}"
        )
        yield Static(text, classes="note-item-text")


class MetadataHeader(Vertical):
    """Header bar showing current note metadata in top row and interactive mode buttons in bottom row."""

    def compose(self) -> ComposeResult:
        yield Static("[#565f89]No note selected[/#565f89]", id="metadata-info")
        with Horizontal(id="mode-button-group"):
            yield Button("👁 Xem", id="btn-mode-view", classes="mode-btn -active")
            yield Button("📝 Soạn", id="btn-mode-edit", classes="mode-btn")
            yield Button("◫ Song song", id="btn-mode-split", classes="mode-btn")
            yield Button("✏ Đổi tên", id="btn-mode-rename", classes="mode-btn")
            yield Button("📋 Copy", id="btn-mode-copy", classes="mode-btn")
            yield Button("🔒 Khóa", id="btn-mode-lock", classes="mode-btn")
            yield Button("🚀 Editor", id="btn-mode-ext", classes="mode-btn")
            yield Button("💾 Lưu", id="btn-mode-save", classes="mode-btn")

    def update_metadata(self, note: Note | None, current_mode: str, is_unlocked: bool = False) -> None:
        info_widget = self.query_one("#metadata-info", Static)
        if not note:
            info_widget.update("[#565f89]No note selected[/#565f89]")
            return

        if note.encrypted:
            icon = "🔓" if is_unlocked else "🔒"
        elif note.note_type == "journal":
            icon = "📓"
        else:
            icon = "📝"
        tags_badge = " ".join(f"[#7dcfff]#{t}[/#7dcfff]" for t in note.tags) if note.tags else "[#565f89]none[/#565f89]"
        formatted_date = note.date.replace("T", " ")[:16]

        content = (
            f"{icon} [bold #c0caf5]{note.title}[/bold #c0caf5]  "
            f"[#565f89]({formatted_date})[/#565f89]  "
            f"Tags: {tags_badge}"
        )
        info_widget.update(content)

        # Update active classes on mode buttons
        for mode in ["view", "edit", "split"]:
            try:
                btn = self.query_one(f"#btn-mode-view" if mode == "view" else f"#btn-mode-{mode}", Button)
                if mode == current_mode:
                    btn.add_class("-active")
                else:
                    btn.remove_class("-active")
            except Exception:
                pass

        # Update lock button text
        try:
            lock_btn = self.query_one("#btn-mode-lock", Button)
            if not note.encrypted:
                lock_btn.label = "🔒 Khóa"
            elif is_unlocked:
                lock_btn.label = "🔐 Quản lý"
            else:
                lock_btn.label = "🔓 Mở khóa"
        except Exception:
            pass
