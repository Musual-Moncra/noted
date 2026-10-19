from datetime import date
from pathlib import Path
import pytest
from noted.config import Config
from noted.models import Note
from noted.storage import StorageManager

@pytest.fixture
def storage(tmp_path):
    config = Config(notes_dir=tmp_path / "notes_test")
    return StorageManager(config)

def test_storage_initializes_dirs(storage):
    assert storage.config.notes_dir.is_dir()
    assert storage.config.notes_subdir.is_dir()
    assert storage.config.journal_subdir.is_dir()

def test_create_and_read_note(storage):
    note = storage.create_note(
        title="Architecture Decision",
        body="Use SQLite with FTS5.",
        tags=["architecture", "decision"],
    )
    assert note.filepath is not None
    assert note.filepath.is_file()
    assert note.filepath.parent == storage.config.notes_subdir
    assert "architecture-decision" in note.filepath.name
    assert note.mtime_ns > 0

    # Read back from disk
    loaded = storage.read_note(note.filepath)
    assert loaded.id == note.id
    assert loaded.title == "Architecture Decision"
    assert loaded.tags == ["architecture", "decision"]
    assert "Use SQLite with FTS5." in loaded.body

def test_today_journal(storage):
    today_str = date.today().isoformat()
    journal = storage.get_or_create_today_journal()
    assert journal.id == today_str
    assert journal.note_type == "journal"
    assert journal.filepath == storage.config.journal_subdir / f"{today_str}.md"
    assert journal.filepath.is_file()
    assert "Highlights" in journal.body

    # Modify journal content and save
    journal.body += "\nAdded an evening reflection."
    storage.save_note(journal)

    # Calling get_or_create_today_journal again should return existing content without overwriting!
    journal_again = storage.get_or_create_today_journal()
    assert "Added an evening reflection." in journal_again.body

def test_delete_note(storage):
    note = storage.create_note(title="Temporary Note", body="Will be deleted.")
    assert note.filepath.is_file()
    
    deleted = storage.delete_note(note.filepath)
    assert deleted is True
    assert not note.filepath.exists()

    # Deleting non-existent file returns False
    assert storage.delete_note(note.filepath) is False

def test_list_note_files(storage):
    n1 = storage.create_note(title="Note 1", body="Content 1")
    n2 = storage.create_note(title="Note 2", body="Content 2")
    j1 = storage.get_or_create_today_journal()

    all_files = storage.list_note_files()
    assert len(all_files) == 3
    assert n1.filepath in all_files
    assert n2.filepath in all_files
    assert j1.filepath in all_files

def test_rename_note(storage):
    note = storage.create_note(title="Old Title", body="Body content")
    old_path = note.filepath
    assert old_path.exists()
    assert "old-title" in old_path.name

    new_path = storage.rename_note(note, "Tiêu Đề Mới (New Title)")
    assert new_path.exists()
    assert not old_path.exists()
    assert note.title == "Tiêu Đề Mới (New Title)"
    assert note.filepath == new_path

    # Reload from disk
    loaded = storage.read_note(new_path)
    assert loaded.title == "Tiêu Đề Mới (New Title)"
    assert loaded.body.strip() == "Body content"


