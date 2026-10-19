from rich import box
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from noted.models import Note, NoteSummary, SearchResult

def format_tags(tags: list[str]) -> str:
    if not tags:
        return "[dim]none[/dim]"
    return " ".join(f"[bold blue]#{t}[/bold blue]" for t in tags)

def format_date(date_str: str) -> str:
    # Truncate ISO timestamp to readable date & time (e.g. 2026-10-19 14:30)
    cleaned = date_str.replace("T", " ")
    return cleaned[:16]

def build_notes_table(notes: list[NoteSummary]) -> Table:
    """Builds a styled Rich Table for listing notes and journals."""
    table = Table(
        title="Notes & Journals",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta", no_wrap=True)
    table.add_column("Date", style="dim", no_wrap=True)
    table.add_column("Title", style="bold white")
    table.add_column("Tags", style="blue")

    for n in notes:
        table.add_row(
            n.id,
            f"📓 {n.note_type}" if n.note_type == "journal" else f"📝 {n.note_type}",
            format_date(n.date),
            n.title,
            format_tags(n.tags),
        )

    return table

def build_search_table(results: list[SearchResult]) -> Table:
    """Builds a styled Rich Table for search results with highlighted excerpts."""
    table = Table(
        title=f"Search Results ({len(results)} matches)",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold white", no_wrap=False, max_width=25)
    table.add_column("Excerpt", style="white")
    table.add_column("Tags", style="blue", no_wrap=True)
    table.add_column("Date", style="dim", no_wrap=True)

    for r in results:
        # Convert [[HIGHLIGHT]] tags from SQLite snippet into Rich bold yellow
        formatted_snip = (
            r.snippet.replace("[[HIGHLIGHT]]", "[bold yellow]")
            .replace("[[/HIGHLIGHT]]", "[/bold yellow]")
            .replace("\n", " ")
        )
        table.add_row(
            r.note.id,
            r.note.title,
            formatted_snip,
            format_tags(r.note.tags),
            format_date(r.note.date),
        )

    return table

def build_note_panel(note: Note) -> Panel:
    """Builds a styled Rich Panel rendering the note's Markdown body and metadata."""
    md = Markdown(note.body.strip(), code_theme="monokai")
    meta_header = (
        f"[bold cyan]ID:[/bold cyan] {note.id}   "
        f"[bold magenta]Type:[/bold magenta] {note.note_type}   "
        f"[bold green]Date:[/bold green] {format_date(note.date)}\n"
        f"[bold yellow]Tags:[/bold yellow] {format_tags(note.tags)}"
    )

    content = Table.grid(padding=1)
    content.add_row(meta_header)
    content.add_row("─" * 40)
    content.add_row(md)

    return Panel(
        content,
        title=f"[bold]{note.title}[/bold]",
        subtitle=f"[dim]{note.filepath}[/dim]" if note.filepath else None,
        box=box.ROUNDED,
        border_style="cyan",
        padding=(1, 2),
    )
