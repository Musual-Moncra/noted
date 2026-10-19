from textual.app import ComposeResult
from textual.widgets import ListItem, Static
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

class MetadataHeader(Static):
    """Header bar showing current note metadata and editing mode."""

    def update_metadata(self, note: Note | None, edit_mode: bool) -> None:
        if not note:
            self.update("[dim]No note selected[/dim]")
            return

        mode_badge = "[bold yellow on dark_goldenrod] EDIT [/bold yellow on dark_goldenrod]" if edit_mode else "[bold white on dark_green] VIEW [/bold white on dark_green]"
        icon = "📓" if note.note_type == "journal" else "📝"
        tags_badge = " ".join(f"[blue]#{t}[/blue]" for t in note.tags) if note.tags else "[dim]none[/dim]"
        formatted_date = note.date.replace("T", " ")[:16]

        content = (
            f"{mode_badge}  {icon} [bold white]{note.title}[/bold white]   "
            f"[dim]({formatted_date})[/dim]   "
            f"Tags: {tags_badge}"
        )
        self.update(content)
