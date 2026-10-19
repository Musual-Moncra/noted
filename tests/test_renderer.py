from pathlib import Path
from rich.table import Table
from rich.panel import Panel
from noted.models import Note, NoteSummary, SearchResult
from noted.renderer import (
    build_notes_table,
    build_search_table,
    build_note_panel,
)

def test_build_notes_table():
    notes = [
        NoteSummary(
            id="20261019-100000",
            title="First Note",
            date="2026-10-19T10:00:00",
            note_type="note",
            tags=["work", "dev"],
            filepath=Path("/tmp/first.md"),
        )
    ]
    table = build_notes_table(notes)
    assert isinstance(table, Table)
    assert table.row_count == 1
    # Check column names
    col_names = [col.header for col in table.columns]
    assert "ID" in col_names
    assert "Title" in col_names
    assert "Tags" in col_names

def test_build_search_table():
    results = [
        SearchResult(
            note=NoteSummary(
                id="20261019-100000",
                title="Matched Note",
                date="2026-10-19T10:00:00",
                note_type="note",
                tags=["search"],
                filepath=Path("/tmp/matched.md"),
            ),
            snippet="Matched in [[HIGHLIGHT]]keyword[[/HIGHLIGHT]] excerpt",
        )
    ]
    table = build_search_table(results)
    assert isinstance(table, Table)
    assert table.row_count == 1

def test_build_note_panel():
    note = Note(
        id="20261019-100000",
        title="Rendered Note",
        date="2026-10-19T10:00:00",
        note_type="note",
        tags=["python", "rich"],
        body="# Heading\n\n- item 1\n- item 2\n",
    )
    panel = build_note_panel(note)
    assert isinstance(panel, Panel)
