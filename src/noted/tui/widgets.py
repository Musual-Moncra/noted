import unicodedata
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.document._document import EditResult, Location
from textual.widgets import Button, ListItem, Static, TextArea
from noted.models import Note, NoteSummary

class VietnameseTextArea(TextArea):
    """Enhanced TextArea optimized for Vietnamese IMEs (Telex, Simple Telex, EVKey, OpenKey, UniKey).

    Key enhancements:
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

class NoteListItem(ListItem):
    """A list item representing a note summary in the sidebar."""

    def __init__(self, summary: NoteSummary):
        super().__init__()
        self.summary = summary

    def compose(self) -> ComposeResult:
        icon = "📓" if self.summary.note_type == "journal" else "📝"
        short_date = self.summary.date.replace("T", " ")[:10]
        tags_str = " ".join(f"#{t}" for t in self.summary.tags[:3])
        if tags_str:
            tags_str = f" [dim blue]{tags_str}[/dim blue]"

        text = (
            f"{icon} [bold]{self.summary.title}[/bold]\n"
            f"   [dim]{short_date}[/dim]{tags_str}"
        )
        yield Static(text, classes="note-item-text")

class MetadataHeader(Horizontal):
    """Header bar showing current note metadata and interactive mode buttons."""

    def compose(self) -> ComposeResult:
        yield Static("[dim]No note selected[/dim]", id="metadata-info")
        with Horizontal(id="mode-button-group"):
            yield Button("👁 Xem (Ctrl+P)", id="btn-mode-view", classes="mode-btn -active")
            yield Button("📝 Soạn", id="btn-mode-edit", classes="mode-btn")
            yield Button("◫ Song song", id="btn-mode-split", classes="mode-btn")
            yield Button("🚀 Mở Editor", id="btn-mode-ext", classes="mode-btn")
            yield Button("💾 Lưu", id="btn-mode-save", classes="mode-btn")

    def update_metadata(self, note: Note | None, current_mode: str) -> None:
        info_widget = self.query_one("#metadata-info", Static)
        if not note:
            info_widget.update("[dim]No note selected[/dim]")
            return

        icon = "📓" if note.note_type == "journal" else "📝"
        tags_badge = " ".join(f"[blue]#{t}[/blue]" for t in note.tags) if note.tags else "[dim]none[/dim]"
        formatted_date = note.date.replace("T", " ")[:16]

        content = (
            f"{icon} [bold white]{note.title}[/bold white]  "
            f"[dim]({formatted_date})[/dim]  "
            f"Tags: {tags_badge}"
        )
        info_widget.update(content)

        # Update active classes on mode buttons
        for mode in ["view", "edit", "split"]:
            btn = self.query_one(f"#btn-mode-view" if mode == "view" else f"#btn-mode-{mode}", Button)
            if mode == current_mode:
                btn.add_class("-active")
            else:
                btn.remove_class("-active")
