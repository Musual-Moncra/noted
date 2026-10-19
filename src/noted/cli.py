import sys
from datetime import date
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from noted.config import Config, load_config
from noted.db import DatabaseManager
from noted.editor import open_in_editor
from noted.indexer import NoteIndexer
from noted.renderer import (
    build_note_panel,
    build_notes_table,
    build_search_table,
)
from noted.storage import StorageManager

app = typer.Typer(
    name="noted",
    help="Fast, keyboard-first Terminal Note-Taking & Journaling CLI & TUI.",
    add_completion=False,
)

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

console = Console()

def get_services(custom_config_path: Path | None = None) -> tuple[Config, StorageManager, DatabaseManager, NoteIndexer]:
    config = load_config(custom_config_path)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)
    # Quick incremental sync so SQLite is always up to date
    indexer.sync_all()
    return config, storage, db, indexer

def launch_tui() -> None:
    try:
        from noted.tui.app import NotedApp
        app_instance = NotedApp()
        app_instance.run()
    except ImportError:
        console.print("[yellow]Interactive TUI module is loading or unavailable in this environment.[/yellow]")

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Default entrypoint. Launches interactive TUI if running in interactive terminal."""
    if ctx.invoked_subcommand is None:
        if sys.stdin.isatty() and sys.stdout.isatty():
            launch_tui()
        else:
            console.print(ctx.get_help())

@app.command(name="ui", help="Launch the full-screen interactive Terminal User Interface.")
@app.command(name="tui", hidden=True)
def ui_cmd() -> None:
    launch_tui()

@app.command(name="add", help="Quickly capture a note.")
def add_cmd(
    content: str = typer.Argument(..., help="Note content or thought"),
    tag: Optional[str] = typer.Option(None, "-t", "--tag", help="Comma-separated tags"),
    title: Optional[str] = typer.Option(None, "--title", help="Custom note title"),
    edit: bool = typer.Option(False, "-e", "--edit", help="Open in editor after creating"),
) -> None:
    config, storage, db, indexer = get_services()
    
    tags = [t.strip() for t in tag.split(",") if t.strip()] if tag else []
    
    # Auto-generate title if not specified
    if not title:
        first_line = content.strip().split("\n")[0]
        title = first_line[:40].strip() or "Quick Note"

    note = storage.create_note(title=title, body=content, tags=tags)
    indexer.index_note(note)

    console.print(f"[bold green]✓[/bold green] Created note: [bold cyan]{note.id}[/bold cyan] ([bold white]{note.title}[/bold white])")

    if edit:
        if open_in_editor(note.filepath, preferred_editor=config.editor):
            # Re-index edited note
            updated_note = storage.read_note(note.filepath)
            indexer.index_note(updated_note)

@app.command(name="today", help="Open or view today's daily journal entry.")
@app.command(name="journal", hidden=True)
def today_cmd(
    view: bool = typer.Option(False, "-v", "--view", help="Render today's journal in terminal"),
    edit: bool = typer.Option(False, "-e", "--edit", help="Explicitly open in editor"),
) -> None:
    config, storage, db, indexer = get_services()
    journal = storage.get_or_create_today_journal()
    indexer.index_note(journal)

    if view and not edit:
        console.print(build_note_panel(journal))
    else:
        # Default is to open editor for journaling unless --view was requested
        if open_in_editor(journal.filepath, preferred_editor=config.editor):
            updated_journal = storage.read_note(journal.filepath)
            indexer.index_note(updated_journal)

@app.command(name="list", help="List recent notes and journals.")
def list_cmd(
    limit: int = typer.Option(10, "-l", "--limit", help="Number of notes to display"),
    tag: Optional[str] = typer.Option(None, "-t", "--tag", help="Filter by tag"),
    type: Optional[str] = typer.Option(None, "--type", help="Filter by type ('note' or 'journal')"),
) -> None:
    config, storage, db, indexer = get_services()
    notes = indexer.list_notes(tag=tag, note_type=type, limit=limit)
    if not notes:
        console.print("[dim]No notes found matching criteria.[/dim]")
        return
    console.print(build_notes_table(notes))

@app.command(name="search", help="Full-text search notes and journals.")
def search_cmd(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(20, "-l", "--limit", help="Max search results"),
) -> None:
    config, storage, db, indexer = get_services()
    results = indexer.search(query=query, limit=limit)
    if not results:
        console.print(f"[dim]No results found for '[bold]{query}[/bold]'.[/dim]")
        return
    console.print(build_search_table(results))

@app.command(name="view", help="Render a note in the terminal.")
def view_cmd(
    identifier: str = typer.Argument(..., help="Note ID, journal date (YYYY-MM-DD), or title keyword"),
) -> None:
    config, storage, db, indexer = get_services()
    note = indexer.get_note_by_id_or_date(identifier)
    if not note:
        console.print(f"[bold red]Error:[/bold red] Note matching '[yellow]{identifier}[/yellow]' not found.")
        raise typer.Exit(code=1)
    console.print(build_note_panel(note))

@app.command(name="edit", help="Open a note in $EDITOR.")
def edit_cmd(
    identifier: str = typer.Argument(..., help="Note ID, journal date, or title keyword"),
) -> None:
    config, storage, db, indexer = get_services()
    note = indexer.get_note_by_id_or_date(identifier)
    if not note or not note.filepath:
        console.print(f"[bold red]Error:[/bold red] Note matching '[yellow]{identifier}[/yellow]' not found.")
        raise typer.Exit(code=1)

    if open_in_editor(note.filepath, preferred_editor=config.editor):
        updated = storage.read_note(note.filepath)
        indexer.index_note(updated)
        console.print(f"[bold green]✓[/bold green] Updated [bold cyan]{updated.id}[/bold cyan]")

@app.command(name="sync", help="Synchronize the SQLite search index with filesystem notes.")
def sync_cmd() -> None:
    config, storage, db, indexer = get_services()
    count = indexer.sync_all()
    console.print(f"[bold green]✓[/bold green] Synced index. Re-indexed [bold cyan]{count}[/bold cyan] note(s).")

if __name__ == "__main__":
    app()
