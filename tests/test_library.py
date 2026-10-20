from pathlib import Path
import os
import pytest
from noted.config import Config, load_config
from noted.storage import StorageManager
from noted.db import DatabaseManager
from noted.indexer import NoteIndexer


@pytest.fixture
def library(tmp_path):
    storage = StorageManager(Config(notes_dir=tmp_path / 'library'))
    return storage, NoteIndexer(DatabaseManager(storage.config.db_path), storage)


def test_nested_move_preserves_identity_metadata_and_encryption(library):
    storage, indexer = library
    folder = storage.create_folder('Work/Research')
    note = storage.create_note('Private', 'secret', tags=[' Dev ', 'DEV', 'Tiếng Việt'])
    note.extra_metadata['custom'] = {'value': 42}
    note.pinned = True
    storage.lock_note(note, 'password')
    original = note.filepath
    storage.move_note(note, folder)
    assert not original.exists()
    indexer.sync_all()
    loaded = indexer.get_note_by_id_or_date(note.id)
    assert loaded.filepath.parent == folder
    assert loaded.pinned and loaded.extra_metadata['custom'] == {'value': 42}
    assert loaded.tags == ['dev', 'tiếng việt']
    assert storage.unlock_note(loaded, 'password') == 'secret'
    assert 'secret' not in loaded.filepath.read_text()


def test_failed_rename_keeps_original_and_model(library, monkeypatch):
    storage, _ = library
    note = storage.create_note('Original', 'body')
    old = note.filepath
    def fail(*args):
        raise OSError('disk full')
    monkeypatch.setattr('noted.storage.os.replace', fail)
    with pytest.raises(OSError):
        storage.rename_note(note, 'Replacement')
    assert old.exists() and note.filepath == old and note.title == 'Original'
    assert list(old.parent.iterdir()) == [old]


def test_conflict_and_folder_boundaries(library, tmp_path):
    from noted.storage import ExternalChangeError
    storage, _ = library
    note = storage.create_note('Original', 'body')
    note.filepath.write_text(note.filepath.read_text() + 'external')
    note.body = 'overwrite'
    with pytest.raises(ExternalChangeError):
        storage.save_note(note)
    for name in ['../outside', '/tmp/outside', 'bad:name', 'Work/../Other']:
        with pytest.raises(ValueError):
            storage.create_folder(name)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (storage.config.notes_subdir / 'link').symlink_to(outside, target_is_directory=True)
    note = storage.read_note(note.filepath)
    with pytest.raises(ValueError):
        storage.move_note(note, storage.config.notes_subdir / 'link')
    root = storage.create_folder('Work/Research')
    with pytest.raises(ValueError):
        storage.move_folder(root.parent, root / 'inside')


def test_combined_filters_pagination_archive_and_size_sync(library):
    storage, indexer = library
    folder = storage.create_folder('Work')
    child = storage.create_folder('Work/Sub')
    a = storage.create_note('Alpha', 'apple content', tags=['dev', 'work'], folder=folder)
    b = storage.create_note('Beta', 'apple content', tags=['dev'], folder=child)
    b.pinned = True
    storage.save_note(b)
    indexer.sync_all()
    assert indexer.list_notes(folder=folder, tags=['dev', 'work'])[0].id == a.id
    assert indexer.count_notes(folder=folder) == 2
    assert indexer.count_notes(folder=folder, recursive=False) == 1
    assert indexer.list_notes(limit=1)[0].id == b.id
    assert indexer.list_notes(limit=1, offset=1)[0].id == a.id
    assert len(indexer.search('apple', folder=folder)) == 2
    a.archived = True
    storage.save_note(a)
    indexer.index_note(a)
    assert indexer.count_notes() == 1
    assert indexer.count_notes(archived=True) == 1
    assert indexer.list_notes(archived=True)[0].id == a.id
    assert indexer.list_tags() == [('dev', 1)]
    old_stat = b.filepath.stat()
    b.filepath.write_text(b.filepath.read_text() + '\nnewword')
    os.utime(b.filepath, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
    assert indexer.sync_all() == 1
    assert indexer.search('newword')[0].note.id == b.id


def test_rename_folder_reconciles_paths(library):
    storage, indexer = library
    folder = storage.create_folder('Work/Sub')
    n = storage.create_note('Nested', folder=folder)
    indexer.sync_all()
    storage.move_folder(folder.parent, storage.config.notes_subdir / 'Projects')
    indexer.sync_all()
    assert indexer.get_note_by_id_or_date(n.id).filepath.parent.name == 'Sub'
    assert indexer.count_notes() == 1


def test_animation_config(tmp_path, monkeypatch):
    monkeypatch.delenv('NOTES_DIR', raising=False)
    config = tmp_path / 'config.toml'
    config.write_text('[ui]\nanimation = "off"\n')
    assert load_config(config).animation == 'off'


def test_read_and_index_use_same_file_revision(library, monkeypatch):
    storage, indexer = library
    note = storage.create_note('Snapshot', 'original')
    original_read = Path.read_text
    replacement = note.filepath.read_text().replace('original', 'external replacement')
    changed = False
    def racing_read(path, *args, **kwargs):
        nonlocal changed
        text = original_read(path, *args, **kwargs)
        if path == note.filepath and not changed:
            changed = True
            path.write_text(replacement)
        return text
    monkeypatch.setattr(Path, 'read_text', racing_read)
    snapshot = storage.read_note(note.filepath)
    assert 'external replacement' in snapshot.body
    # A later change must remain detectable on the next sync, never stamped as current.
    snapshot.filepath.write_text(replacement + '\nlater revision')
    indexer.index_note(snapshot)
    assert indexer.sync_all() == 1
    assert indexer.search('later')[0].note.id == note.id


def test_note_ids_support_large_bursts():
    from noted.frontmatter import generate_note_id
    ids = [generate_note_id() for _ in range(10000)]
    assert len(set(ids)) == len(ids)


def test_plain_markdown_in_nested_folders_has_unique_stable_identity(library):
    storage, indexer = library
    a = storage.create_folder('A') / 'ideas.md'
    b = storage.create_folder('B') / 'ideas.md'
    a.write_text('First external note')
    b.write_text('Second external note')
    indexer.sync_all()
    assert indexer.count_notes() == 2
    note = storage.read_note(a)
    original_id = note.id
    storage.move_note(note, storage.create_folder('Inbox'))
    assert storage.read_note(note.filepath).id == original_id
    assert storage.find_folders('inbox') == [note.filepath.parent]


def test_search_excerpt_shows_match_outside_initial_excerpt(library):
    storage, indexer = library
    storage.create_note('Long note', 'introduction ' * 100 + ' searchable_unique_needle and context')
    indexer.sync_all()
    result = indexer.search('searchable_unique_needle')[0]
    assert '[[HIGHLIGHT]]searchable_unique_needle' in result.snippet
    assert len(result.snippet) <= 200
