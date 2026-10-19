import os
import unicodedata
import pytest
from textual import constants
from textual.widgets.text_area import Location
from noted.config import Config
from noted.db import DatabaseManager
from noted.indexer import NoteIndexer
from noted.storage import StorageManager
from noted.tui.app import NotedApp
from noted.tui.widgets import VietnameseTextArea

def test_textual_disable_kitty_key_is_set():
    """Verify that Kitty Keyboard Protocol is disabled to prevent dropped backspaces in IMEs."""
    assert os.environ.get("TEXTUAL_DISABLE_KITTY_KEY") == "1"
    assert constants.DISABLE_KITTY_KEY is True

def test_vietnamese_text_area_nfc_load_and_replace():
    """Verify that VietnameseTextArea normalizes NFD (combining) to NFC (precomposed)."""
    editor = VietnameseTextArea()
    # NFD decomposed 'tiếng': 't' + 'i' + 'e' + '\u0302' + '\u0301' + 'n' + 'g'
    nfd_text = "t\u0069\u0065\u0302\u0301ng"
    assert len(nfd_text) == 7

    editor.load_text(nfd_text)
    assert editor.text == "tiếng"
    assert len(editor.text) == 5  # Precomposed NFC length is 5
    assert unicodedata.is_normalized("NFC", editor.text)

    # Test replace with NFD text
    editor.replace("kh\u006f\u0301a", (0, 0), (0, 5))
    assert editor.text == "khóa"
    assert len(editor.text) == 4
    assert unicodedata.is_normalized("NFC", editor.text)

def test_vietnamese_text_area_combining_mark_merging():
    """Verify that isolated combining marks automatically merge with preceding vowels."""
    editor = VietnameseTextArea()
    editor.text = "kho"
    editor.cursor_location = (0, 3)

    # User IME sends acute accent combining mark \u0301
    editor._replace_via_keyboard("\u0301", (0, 3), (0, 3))
    assert editor.text == "khó"

    # Next character 'a' arrives
    editor.cursor_location = (0, 3)
    editor._replace_via_keyboard("a", (0, 3), (0, 3))
    assert editor.text == "khóa"

def test_vietnamese_text_area_all_tones_and_vowels():
    """Verify all 5 Vietnamese tone marks across primary vowels merge cleanly."""
    tone_marks = {
        "\u0300": "huyền",
        "\u0301": "sắc",
        "\u0303": "ngã",
        "\u0309": "hỏi",
        "\u0323": "nặng",
    }
    vowels = ["a", "ă", "â", "e", "ê", "i", "o", "ô", "ơ", "u", "ư", "y"]

    editor = VietnameseTextArea()
    for v in vowels:
        for mark in tone_marks:
            expected = unicodedata.normalize("NFC", v + mark)
            editor.text = v
            editor.cursor_location = (0, len(v))
            editor._replace_via_keyboard(mark, (0, len(v)), (0, len(v)))
            assert editor.text == expected, f"Failed for {v} + {tone_marks[mark]}: got {editor.text}, expected {expected}"

@pytest.mark.asyncio
async def test_tui_vietnamese_typing_and_saving(tmp_path, monkeypatch):
    """Integration test: Verify typing Vietnamese text in TUI editor saves cleanly to disk in NFC."""
    notes_dir = tmp_path / "vn_notes"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    n = storage.create_note(title="Ghi chú Tiếng Việt", body="Nội dung ban đầu", tags=["tiếng-việt"])
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Enter edit mode
        await pilot.press("e")
        editor = app.query_one("#text-editor", VietnameseTextArea)
        assert isinstance(editor, VietnameseTextArea)

        # Set Vietnamese text with complex diacritics
        vn_content = "Đang thử nghiệm gõ tiếng Việt: khóa học, đường sắt, phát triển phần mềm."
        editor.text = vn_content

        # Save note
        await pilot.press("ctrl+s")
        await pilot.pause()

        # Verify saved file on disk
        saved_note = storage.read_note(n.filepath)
        assert saved_note.body.strip() == vn_content
        assert unicodedata.is_normalized("NFC", saved_note.body)
