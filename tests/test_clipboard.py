import pytest
from textual.document._document import Selection
from noted.clipboard import copy_to_clipboard
from noted.config import Config
from noted.db import DatabaseManager
from noted.indexer import NoteIndexer
from noted.storage import StorageManager
from noted.tui.app import NotedApp
from noted.tui.widgets import VietnameseTextArea

def test_copy_to_clipboard_basic(monkeypatch):
    """Test copy_to_clipboard returns boolean without raising errors."""
    res = copy_to_clipboard("Testing clipboard integration in Noted")
    assert isinstance(res, bool)

def test_copy_to_clipboard_vietnamese():
    """Test copy_to_clipboard with Vietnamese characters."""
    vn_text = "Thử nghiệm sao chép tiếng Việt: khóa học, đường sắt."
    res = copy_to_clipboard(vn_text)
    assert isinstance(res, bool)

@pytest.mark.asyncio
async def test_tui_copy_content_button_and_shortcut(tmp_path, monkeypatch):
    """Test TUI copy button and 'c' shortcut copy current note body to clipboard."""
    notes_dir = tmp_path / "copy_notes"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    n = storage.create_note(title="Clipboard Note", body="Content to be copied to clipboard.", tags=["clip"])
    indexer.sync_all()

    copied_items = []
    monkeypatch.setattr("noted.clipboard.copy_to_clipboard", lambda text, app=None: copied_items.append(text) or True)

    app = NotedApp(custom_config=config)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()

        # In view mode, press 'c' to copy
        await pilot.press("c")
        await pilot.pause()
        assert len(copied_items) == 1
        assert "Content to be copied to clipboard." in copied_items[0]

        # Click the [📋 Copy] button in MetadataHeader
        await pilot.click("#btn-mode-copy")
        await pilot.pause()
        assert len(copied_items) == 2

@pytest.mark.asyncio
async def test_tui_copy_selection_in_editor(tmp_path, monkeypatch):
    """Test copying selected text in edit mode copies only the selection."""
    notes_dir = tmp_path / "copy_select_notes"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    n = storage.create_note(title="Selection Note", body="Line 1: Alpha Beta Gamma\nLine 2: Delta Epsilon", tags=["select"])
    indexer.sync_all()

    copied_items = []
    monkeypatch.setattr("noted.clipboard.copy_to_clipboard", lambda text, app=None: copied_items.append(text) or True)

    app = NotedApp(custom_config=config)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()

        # Enter edit mode
        await pilot.press("e")
        editor = app.query_one("#text-editor", VietnameseTextArea)
        editor.text = "Alpha Beta Gamma"
        editor.selection = Selection((0, 0), (0, 10))
        assert editor.selected_text == "Alpha Beta"

        # Trigger copy action
        app.action_copy_content()
        await pilot.pause()
        assert len(copied_items) == 1
        assert copied_items[0] == "Alpha Beta"
