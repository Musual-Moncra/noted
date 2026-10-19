from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, ListItem, Static
from noted.models import Note, NoteSummary

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
