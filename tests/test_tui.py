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

@pytest.mark.asyncio
async def test_tui_modal_centering(tmp_path, monkeypatch):
    from noted.tui.screens import NewNoteModal, HelpModal, ConfirmDeleteModal
    notes_dir = tmp_path / "tui_modal_centering"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    storage.create_note(title="Centered Modal Note", body="Testing popups")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Test NewNoteModal is centered
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, NewNoteModal)
        assert app.screen.styles.align_horizontal == "center"
        assert app.screen.styles.align_vertical == "middle"
        await pilot.press("escape")
        await pilot.pause()

        # Test HelpModal is centered
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpModal)
        assert app.screen.styles.align_horizontal == "center"
        assert app.screen.styles.align_vertical == "middle"
        await pilot.press("escape")
        await pilot.pause()

        # Test ConfirmDeleteModal is centered
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDeleteModal)
        assert app.screen.styles.align_horizontal == "center"
        assert app.screen.styles.align_vertical == "middle"
        await pilot.press("escape")
        await pilot.pause()

@pytest.mark.asyncio
async def test_tui_color_format_modal(tmp_path, monkeypatch):
    from noted.tui.screens import ColorFormatModal
    notes_dir = tmp_path / "tui_color_modal"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    storage.create_note(title="Color Test Note", body="Important line")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Enter edit mode
        await pilot.press("e")
        await pilot.pause()

        # Trigger color formatting modal
        app.action_format_color()
        await pilot.pause()

        assert isinstance(app.screen, ColorFormatModal)
        assert app.screen.styles.align_horizontal == "center"
        assert app.screen.styles.align_vertical == "middle"

        # Press '1' to pick Green Tip
        await pilot.press("1")
        await pilot.pause()

        editor = app.query_one("#text-editor")
        assert "[!TIP]" in editor.text

@pytest.mark.asyncio
async def test_tui_rename_note(tmp_path, monkeypatch):
    from noted.tui.screens import RenameNoteModal
    notes_dir = tmp_path / "tui_rename_note"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    n = storage.create_note(title="Old Note Title", body="Some content")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.current_note is not None
        assert app.current_note.title == "Old Note Title"

        # Press 'r' to open RenameNoteModal
        await pilot.press("r")
        await pilot.pause()

        assert isinstance(app.screen, RenameNoteModal)
        assert app.screen.styles.align_horizontal == "center"
        assert app.screen.styles.align_vertical == "middle"

        # Change title
        inp = app.screen.query_one("#input-rename-title")
        inp.value = "New Updated Title"
        await pilot.press("enter")
        await pilot.pause()

        assert app.current_note.title == "New Updated Title"
        # Check disk update
        assert not n.filepath.exists()
        assert app.current_note.filepath.exists()
        assert "new-updated-title" in app.current_note.filepath.name

@pytest.mark.asyncio
async def test_header_and_toolbar_dimensions(tmp_path, monkeypatch):
    notes_dir = tmp_path / "tui_dimensions"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    storage.create_note(title="A Very Long Note Title That Should Not Be Crushed", body="Some markdown content")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        meta_info = app.query_one("#metadata-info")
        # Metadata info must NOT be crushed down to width 1!
        assert meta_info.size.width > 50

        # Switch to edit mode and verify toolbar total width is <= 45 columns
        app.set_mode("edit")
        await pilot.pause()
        toolbar = app.query_one("#formatting-toolbar")
        total_btn_w = sum(btn.size.width for btn in toolbar.children)
        assert total_btn_w <= 45

@pytest.mark.asyncio
async def test_tui_unlock_and_lock_note(tmp_path, monkeypatch):
    from noted.tui.screens import UnlockNoteModal, LockNoteModal
    notes_dir = tmp_path / "tui_unlock_test"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    storage.create_note(title="Public Note", body="Open Public Content")
    note = storage.create_note(title="Private Note", body="Top Secret Content 123")
    storage.lock_note(note, "Pass123!")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.current_note is not None
        assert app.current_note.encrypted is True

        # Check locked card is visible
        locked_card = app.query_one("#locked-note-card")
        assert locked_card.display is True

        # Test wrong password
        await pilot.click("#btn-screen-unlock")
        await pilot.pause()
        assert isinstance(app.screen, UnlockNoteModal)
        pwd_input = app.screen.query_one("#input-unlock-password")
        pwd_input.value = "WrongPassword"
        await pilot.press("enter")
        await pilot.pause()

        # Still locked
        assert locked_card.display is True
        assert app.current_note.id not in app.unlocked_notes

        # Click unlock button again with correct password
        await pilot.click("#btn-screen-unlock")
        await pilot.pause()
        assert isinstance(app.screen, UnlockNoteModal)
        pwd_input = app.screen.query_one("#input-unlock-password")
        pwd_input.value = "Pass123!"
        await pilot.press("enter")
        await pilot.pause()

        # Should be unlocked
        assert locked_card.display is False
        viewer = app.query_one("#markdown-viewer")
        assert viewer.display is True
        assert "Top Secret Content 123" in app.unlocked_notes[app.current_note.id]

        # Switch to Public Note and lock it
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        assert app.current_note.title == "Public Note"
        assert app.current_note.encrypted is False

        # Trigger lock modal via key 'l'
        await pilot.press("l")
        await pilot.pause()
        assert isinstance(app.screen, LockNoteModal)
        p1 = app.screen.query_one("#input-lock-pass1")
        p2 = app.screen.query_one("#input-lock-pass2")
        p1.value = "NewSecret99"
        p2.value = "NewSecret99"
        await pilot.click("#btn-confirm-lock")
        await pilot.pause()

        # Public Note should now be locked and encrypted
        assert app.current_note.encrypted is True
        # In current session, locking a note keeps it unlocked in session cache
        assert app.current_note.id in app.unlocked_notes



