from datetime import date
from pathlib import Path
import pytest
from noted.config import Config
from noted.db import DatabaseManager
from noted.indexer import NoteIndexer
from noted.models import Note
from noted.storage import StorageManager

@pytest.fixture
def indexer_setup(tmp_path):
    config = Config(notes_dir=tmp_path / "notes_idx")
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)
    return config, storage, db, indexer

def test_db_initialization(indexer_setup):
    config, storage, db, indexer = indexer_setup
    assert config.db_path.is_file()
    with db.get_connection() as conn:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "notes" in tables
        assert "note_tags" in tables
        assert "notes_fts" in tables

def test_index_and_list_notes(indexer_setup):
    config, storage, db, indexer = indexer_setup
    n1 = storage.create_note(title="Python Tips", body="List comprehensions are fast.", tags=["python", "tips"])
    n2 = storage.create_note(title="Rust Guide", body="Memory safety without GC.", tags=["rust", "tips"])
    j1 = storage.get_or_create_today_journal()

    indexer.sync_all()

    # List all
    all_notes = indexer.list_notes()
    assert len(all_notes) == 3

    # Filter by tag
    python_notes = indexer.list_notes(tag="python")
    assert len(python_notes) == 1
    assert python_notes[0].title == "Python Tips"

    tips_notes = indexer.list_notes(tag="tips")
    assert len(tips_notes) == 2

    # Filter by type
    journals = indexer.list_notes(note_type="journal")
    assert len(journals) == 1
    assert journals[0].id == date.today().isoformat()

def test_fts5_search(indexer_setup):
    config, storage, db, indexer = indexer_setup
    storage.create_note(title="Unix Philosophy", body="Write programs that do one thing well.", tags=["unix"])
    storage.create_note(title="Cooking Recipe", body="Delicious sourdough bread recipe.", tags=["food"])
    indexer.sync_all()

    results = indexer.search("philosophy")
    assert len(results) == 1
    assert results[0].note.title == "Unix Philosophy"
    assert "philosophy" in results[0].snippet.lower() or "programs" in results[0].snippet.lower()

    # Special characters query should not crash FTS5
    special_res = indexer.search("c++ OR 'broken\" : query")
    assert isinstance(special_res, list)

def test_sync_reconciliation(indexer_setup):
    config, storage, db, indexer = indexer_setup
    n1 = storage.create_note(title="Note A", body="Initial content")
    indexer.sync_all()

    assert len(indexer.list_notes()) == 1

    # Simulate external modification (changing file directly on disk)
    n1.body = "Updated external content with magical keywords"
    storage.save_note(n1)

    # Sync picks up the change
    updated_count = indexer.sync_all()
    assert updated_count >= 1

    res = indexer.search("magical")
    assert len(res) == 1
    assert res[0].note.id == n1.id

    # Simulate external deletion
    n1.filepath.unlink()
    indexer.sync_all()
    assert len(indexer.list_notes()) == 0

def test_get_note_by_id_or_date(indexer_setup):
    config, storage, db, indexer = indexer_setup
    n1 = storage.create_note(title="Important Note", body="Secret code 42", note_id="20261019-120000")
    j1 = storage.get_or_create_today_journal("2026-10-19")
    indexer.sync_all()

    # Lookup by ID
    found_note = indexer.get_note_by_id_or_date("20261019-120000")
    assert found_note is not None
    assert found_note.title == "Important Note"

    # Lookup by Date
    found_journal = indexer.get_note_by_id_or_date("2026-10-19")
    assert found_journal is not None
    assert found_journal.note_type == "journal"

    # Lookup non-existent
    assert indexer.get_note_by_id_or_date("nonexistent-id") is None

def test_encrypted_indexing(indexer_setup):
    config, storage, db, indexer = indexer_setup
    note = storage.create_note(title="Secret Financials", body="Bank account number 987654321", tags=["private"])
    storage.lock_note(note, "MySecretPass")
    indexer.sync_all()

    # Search by secret term in plaintext body MUST return 0 results
    res_secret = indexer.search("987654321")
    assert len(res_secret) == 0

    # Search by title still works
    res_title = indexer.search("Financials")
    assert len(res_title) == 1
    assert res_title[0].note.encrypted is True
    assert "[🔒 Encrypted note]" in res_title[0].snippet or "Financials" in res_title[0].snippet

    # List notes preserves encrypted flag
    summaries = indexer.list_notes()
    assert len(summaries) == 1
    assert summaries[0].encrypted is True

