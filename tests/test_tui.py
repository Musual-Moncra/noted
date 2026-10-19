import pytest
from pathlib import Path
from noted.config import Config
from noted.storage import StorageManager
from noted.db import DatabaseManager
from noted.indexer import NoteIndexer
from noted.tui.app import NotedApp

@pytest.mark.asyncio
async def test_tui_app_mount_and_navigation(tmp_path, monkeypatch):
    notes_dir = tmp_path / "tui_notes"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    # Seed test notes
    n1 = storage.create_note(title="First TUI Note", body="# Welcome\nTesting Textual TUI.", tags=["tui"])
    j1 = storage.get_or_create_today_journal()
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test() as pilot:
        # Verify app is mounted and has notes list
        assert app.is_mounted
        notes_list = app.query_one("#notes-list")
        assert len(notes_list.children) >= 2

        # Verify first note is loaded
        assert app.current_note is not None
        assert app.current_note.title in ["First TUI Note", f"Daily Journal - {j1.id}"]

        # Toggle edit mode with 'e'
        await pilot.pause()
        assert app.edit_mode is False
        await pilot.press("e")
        await pilot.pause()
        assert app.edit_mode is True

        # Exit edit mode back to view mode with escape
        await pilot.press("escape")
        await pilot.pause()
        assert app.edit_mode is False

        # Press 'slash' to focus search input
        await pilot.press("slash")
        search_input = app.query_one("#search-input")
        assert search_input.has_focus

@pytest.mark.asyncio
async def test_tui_edit_and_save(tmp_path, monkeypatch):
    notes_dir = tmp_path / "tui_notes_edit"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    n = storage.create_note(title="Editable Note", body="Original body", tags=["edit"])
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.current_note is not None

        # Enter edit mode
        await pilot.press("e")
        editor = app.query_one("#text-editor")
        editor.text = "Modified body text inside TUI editor."

        # Save with Ctrl+S
        await pilot.press("ctrl+s")
        await pilot.pause()

        # Verify on-disk file was updated
        updated_note = storage.read_note(n.filepath)
        assert "Modified body text inside TUI editor." in updated_note.body

@pytest.mark.asyncio
async def test_tui_new_note_and_journal(tmp_path, monkeypatch):
    notes_dir = tmp_path / "tui_notes_actions"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)

    app = NotedApp(custom_config=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        
        # Test today journal action 'j'
        await pilot.press("j")
        await pilot.pause()
        assert app.current_note is not None
        assert app.current_note.note_type == "journal"
        assert "Highlights" in app.current_note.body

@pytest.mark.asyncio
async def test_tui_formatting_shortcuts(tmp_path, monkeypatch):
    notes_dir = tmp_path / "tui_notes_formatting"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    storage.create_note(title="Formatting Note", body="")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Enter edit mode
        await pilot.press("e")
        await pilot.pause()
        assert app.edit_mode is True

        # Test bold formatting
        app.action_format_bold()
        editor = app.query_one("#text-editor")
        assert "**" in editor.text

        # Test heading formatting
        app.action_format_heading()
        assert "# " in editor.text

        # Test todo checkbox formatting
        app.action_format_todo()
        assert "- [ ]" in editor.text

@pytest.mark.asyncio
async def test_tui_auto_save_on_view_toggle(tmp_path, monkeypatch):
    notes_dir = tmp_path / "tui_auto_save"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    n = storage.create_note(title="Auto Save Note", body="Initial content")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Enter edit mode
        await pilot.press("e")
        await pilot.pause()
        assert app.edit_mode is True

        editor = app.query_one("#text-editor")
        editor.text = "New content that should auto-save on view toggle."

        # Switch to view mode without pressing ctrl+s
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert app.edit_mode is False

        # Verify on-disk file was updated automatically
        updated = storage.read_note(n.filepath)
        assert "New content that should auto-save on view toggle." in updated.body

@pytest.mark.asyncio
async def test_tui_split_mode_and_live_preview(tmp_path, monkeypatch):
    notes_dir = tmp_path / "tui_split_mode"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    n = storage.create_note(title="Split Test Note", body="Initial markdown")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Toggle split mode with ctrl+w
        await pilot.press("ctrl+w")
        await pilot.pause()
        assert app.note_mode == "split"
        assert app.edit_mode is True

        # Both edit and view containers should be visible
        assert app.query_one("#edit-container").display is True
        assert app.query_one("#view-container").display is True

        # Type in editor and verify live preview updates
        editor = app.query_one("#text-editor")
        editor.text = "# Live Rendered Title"
        await pilot.pause()

        # Switch to view mode via Escape
        await pilot.press("escape")
        await pilot.pause()
        assert app.note_mode == "view"

        # Verify auto-save worked
        updated = storage.read_note(n.filepath)
        assert "# Live Rendered Title" in updated.body

@pytest.mark.asyncio
async def test_tui_mode_buttons(tmp_path, monkeypatch):
    notes_dir = tmp_path / "tui_mode_buttons"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    storage.create_note(title="Mode Buttons Note", body="Testing buttons")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.note_mode == "view"

        # Click Edit button
        await pilot.click("#btn-mode-edit")
        await pilot.pause()
        assert app.note_mode == "edit"

        # Click Split button
        await pilot.click("#btn-mode-split")
        await pilot.pause()
        assert app.note_mode == "split"

        # Click View button
        await pilot.click("#btn-mode-view")
        await pilot.pause()
        assert app.note_mode == "view"
