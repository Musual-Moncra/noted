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
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)
        # Verify app is mounted and has notes list
        assert app.is_mounted
        notes_list = app.query_one("#notes-list")
        assert len(notes_list.children) >= 2

        # Verify first note is loaded
        assert app.current_note is not None
        assert app.current_note.title in ["First TUI Note", f"Daily Journal - {j1.id}"]

        # Toggle edit mode with 'e'
        await pilot.pause(.2)
        assert app.edit_mode is False
        await pilot.press("e")
        await pilot.pause(.2)
        assert app.edit_mode is True

        # Exit edit mode back to view mode with escape
        await pilot.press("escape")
        await pilot.pause(.2)
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
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)
        assert app.current_note is not None

        # Enter edit mode
        await pilot.press("e")
        editor = app.query_one("#text-editor")
        editor.text = "Modified body text inside TUI editor."

        # Save with Ctrl+S
        await pilot.press("ctrl+s")
        await pilot.pause(.2)

        # Verify on-disk file was updated
        updated_note = storage.read_note(n.filepath)
        assert "Modified body text inside TUI editor." in updated_note.body

@pytest.mark.asyncio
async def test_tui_new_note_and_journal(tmp_path, monkeypatch):
    notes_dir = tmp_path / "tui_notes_actions"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)

    app = NotedApp(custom_config=config)
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)
        
        # Test today journal action 'j'
        await pilot.press("j")
        await pilot.pause(.2)
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
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)
        # Enter edit mode
        await pilot.press("e")
        await pilot.pause(.2)
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
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)
        # Enter edit mode
        await pilot.press("e")
        await pilot.pause(.2)
        assert app.edit_mode is True

        editor = app.query_one("#text-editor")
        editor.text = "New content that should auto-save on view toggle."

        # Switch to view mode without pressing ctrl+s
        await pilot.press("ctrl+p")
        await pilot.pause(.2)
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
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)
        # Toggle split mode with ctrl+w
        await pilot.press("ctrl+w")
        await pilot.pause(.2)
        assert app.note_mode == "split"
        assert app.edit_mode is True

        # Both edit and view containers should be visible
        assert app.query_one("#edit-container").display is True
        assert app.query_one("#view-container").display is True

        # Type in editor and verify live preview updates
        editor = app.query_one("#text-editor")
        editor.text = "# Live Rendered Title"
        await pilot.pause(.2)

        # Switch to view mode via Escape
        await pilot.press("escape")
        await pilot.pause(.2)
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
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)
        assert app.note_mode == "view"

        # Click Edit button
        await pilot.click("#btn-mode-edit")
        await pilot.pause(.2)
        assert app.note_mode == "edit"

        # Click Split button
        await pilot.click("#btn-mode-split")
        await pilot.pause(.2)
        assert app.note_mode == "split"

        # Click View button
        await pilot.click("#btn-mode-view")
        await pilot.pause(.2)
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
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)

        # Test NewNoteModal is centered
        await pilot.press("n")
        await pilot.pause(.2)
        assert isinstance(app.screen, NewNoteModal)
        assert app.screen.styles.align_horizontal == "center"
        assert app.screen.styles.align_vertical == "middle"
        await pilot.press("escape")
        await pilot.pause(.2)

        # Test HelpModal is centered
        await pilot.press("question_mark")
        await pilot.pause(.2)
        assert isinstance(app.screen, HelpModal)
        assert app.screen.styles.align_horizontal == "center"
        assert app.screen.styles.align_vertical == "middle"
        await pilot.press("escape")
        await pilot.pause(.2)

        # Test ConfirmDeleteModal is centered
        await pilot.press("d")
        await pilot.pause(.2)
        assert isinstance(app.screen, ConfirmDeleteModal)
        assert app.screen.styles.align_horizontal == "center"
        assert app.screen.styles.align_vertical == "middle"
        await pilot.press("escape")
        await pilot.pause(.2)

@pytest.mark.asyncio
async def test_tui_empty_library_clean_state(tmp_path, monkeypatch):
    from textual.widgets import Button
    notes_dir = tmp_path / "tui_empty_clean"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.query_one("#locked-note-card").display is False
        assert app.query_one("#render-full").display is False
        assert app.query_one("#formatting-toolbar").display is False
        assert app.query_one("#edit-container").display is False
        assert app.query_one("#view-container").display is True
        assert app.query_one("#empty-actions").display is True
        assert app.query_one("#empty-create").display is True
        assert app.query_one("#empty-clear").display is False
        assert "No notes yet." in str(app.query_one("#list-empty").render())
        assert "Welcome to Noted" in app.query_one("#markdown-viewer").source
        for m in ("view", "edit", "split", "save", "more"):
            assert app.query_one(f"#btn-mode-{m}", Button).disabled is True

@pytest.mark.asyncio
async def test_tui_selection_no_layout_shift(tmp_path, monkeypatch):
    from textual.widgets import ListView
    notes_dir = tmp_path / "tui_no_shift"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    storage.create_note(title="First Note", body="Content 1")
    storage.create_note(title="Second Note", body="Content 2")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        notes_list = app.query_one("#notes-list", ListView)
        item1 = notes_list.children[0]
        text1 = item1.query_one(".note-item-text")

        # Check coordinates when notes-list is not focused
        app.set_focus(app.query_one("#search-input"))
        await pilot.pause()
        x_unfocused = text1.region.x
        w_unfocused = text1.region.width

        # Check coordinates when notes-list is focused and item is highlighted
        app.set_focus(notes_list)
        await pilot.pause()
        x_focused = text1.region.x
        w_focused = text1.region.width

        # No shift and no width truncation
        assert x_unfocused == x_focused
        assert w_unfocused == w_focused

@pytest.mark.asyncio
async def test_tui_locked_card_centered(tmp_path, monkeypatch):
    notes_dir = tmp_path / "tui_card_centered"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    n = storage.create_note(title="Secret Note", body="Secret body")
    storage.lock_note(n, "mypassword")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        card = app.query_one("#locked-note-card")
        vc = app.query_one("#view-container")
        left_space = card.region.x - vc.region.x
        right_space = vc.region.width - (card.region.x - vc.region.x + card.region.width)
        assert abs(left_space - right_space) <= 1

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
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)

        # Enter edit mode
        await pilot.press("e")
        await pilot.pause(.2)

        # Trigger color formatting modal
        app.action_format_color()
        await pilot.pause(.2)

        assert isinstance(app.screen, ColorFormatModal)
        assert app.screen.styles.align_horizontal == "center"
        assert app.screen.styles.align_vertical == "middle"

        # Press '1' to pick Red Text
        await pilot.press("1")
        await pilot.pause(.2)

        editor = app.query_one("#text-editor")
        assert 'style="color: #f7768e"' in editor.text

        # Switch to view mode and verify rendered spans
        await pilot.click("#btn-mode-view")
        await pilot.pause(.2)
        viewer = app.query_one("#markdown-viewer")
        child_renders = [c.render() for c in viewer.children if hasattr(c, "render")]
        has_color_span = any(
            any(getattr(s.style, "foreground", None) is not None for s in r.spans)
            for r in child_renders if hasattr(r, "spans")
        )
        assert has_color_span is True

@pytest.mark.asyncio
async def test_tui_footer_and_header_rendered(tmp_path, monkeypatch):
    from textual.widgets import Header, Footer
    notes_dir = tmp_path / "tui_footer_header"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)
    storage.create_note(title="Header Footer Test", body="Body")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)
        header = app.query_one(Header)
        footer = app.query_one(Footer)
        assert header.size.height == 1
        assert footer.size.height == 1
        assert footer.content_size.height == 1

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
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)
        assert app.current_note is not None
        assert app.current_note.title == "Old Note Title"

        # Press 'r' to open RenameNoteModal
        await pilot.press("r")
        await pilot.pause(.2)

        assert isinstance(app.screen, RenameNoteModal)
        assert app.screen.styles.align_horizontal == "center"
        assert app.screen.styles.align_vertical == "middle"

        # Change title
        inp = app.screen.query_one("#input-rename-title")
        inp.value = "New Updated Title"
        await pilot.press("enter")
        await pilot.pause(.2)

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
        await pilot.pause(.2)
        meta_info = app.query_one("#metadata-info")
        # Metadata info must NOT be crushed down to width 1!
        assert meta_info.size.width > 50

        # Switch to edit mode and verify toolbar total width is <= 45 columns
        app.set_mode("edit")
        await pilot.pause(.2)
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
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)
        assert app.current_note is not None
        assert app.current_note.encrypted is True

        # Check locked card is visible
        locked_card = app.query_one("#locked-note-card")
        assert locked_card.display is True

        # Test wrong password
        await pilot.click("#btn-screen-unlock")
        await pilot.pause(.2)
        assert isinstance(app.screen, UnlockNoteModal)
        pwd_input = app.screen.query_one("#input-unlock-password")
        pwd_input.value = "WrongPassword"
        await pilot.press("enter")
        await pilot.pause(.2)

        # Still locked
        assert locked_card.display is True
        assert app.current_note.id not in app.unlocked_notes

        # Click unlock button again with correct password
        await pilot.click("#btn-screen-unlock")
        await pilot.pause(.2)
        assert isinstance(app.screen, UnlockNoteModal)
        pwd_input = app.screen.query_one("#input-unlock-password")
        pwd_input.value = "Pass123!"
        await pilot.press("enter")
        await pilot.pause(.2)

        # Should be unlocked
        assert locked_card.display is False
        viewer = app.query_one("#markdown-viewer")
        assert viewer.display is True
        assert "Top Secret Content 123" in app.unlocked_notes[app.current_note.id]

        # Switch to Public Note and lock it
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause(.2)
        assert app.current_note.title == "Public Note"
        assert app.current_note.encrypted is False

        # Trigger lock modal via key 'l'
        await pilot.press("l")
        await pilot.pause(.2)
        assert isinstance(app.screen, LockNoteModal)
        p1 = app.screen.query_one("#input-lock-pass1")
        p2 = app.screen.query_one("#input-lock-pass2")
        p1.value = "NewSecret99"
        p2.value = "NewSecret99"
        await pilot.click("#btn-confirm-lock")
        await pilot.pause(.2)

        # Public Note should now be locked and encrypted
        assert app.current_note.encrypted is True
        # In current session, locking a note keeps it unlocked in session cache
        assert app.current_note.id in app.unlocked_notes


@pytest.mark.asyncio
async def test_tui_manage_lock_change_pass_and_remove_lock(tmp_path, monkeypatch):
    from noted.tui.screens import (
        ChangePasswordModal,
        ConfirmRemoveLockModal,
        ManageLockModal,
        UnlockNoteModal,
    )
    notes_dir = tmp_path / "tui_manage_lock_test"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    config = Config(notes_dir=notes_dir)
    storage = StorageManager(config)
    db = DatabaseManager(config.db_path)
    indexer = NoteIndexer(db, storage)

    note = storage.create_note(title="Vault Secret", body="Secret Gold Bar 777")
    storage.lock_note(note, "OldPassA")
    indexer.sync_all()

    app = NotedApp(custom_config=config)
    async with app.run_test(size=(180, 45)) as pilot:
        await pilot.pause(.2)
        # Unlock note first
        await pilot.click("#btn-screen-unlock")
        await pilot.pause(.2)
        assert isinstance(app.screen, UnlockNoteModal)
        app.screen.query_one("#input-unlock-password").value = "OldPassA"
        await pilot.press("enter")
        await pilot.pause(.2)
        assert app.current_note.id in app.unlocked_notes

        # Now press 'l' to open ManageLockModal
        await pilot.press("l")
        await pilot.pause(.2)
        assert isinstance(app.screen, ManageLockModal)

        # 1. Test Change Password
        await pilot.click("#btn-opt-change-pass")
        await pilot.pause(.2)
        assert isinstance(app.screen, ChangePasswordModal)
        app.screen.query_one("#input-new-pass1").value = "NewPassB"
        app.screen.query_one("#input-new-pass2").value = "NewPassB"
        await pilot.click("#btn-confirm-change")
        await pilot.pause(.2)

        # 2. Re-lock note immediately
        await pilot.press("l")
        await pilot.pause(.2)
        assert isinstance(app.screen, ManageLockModal)
        await pilot.click("#btn-opt-relock")
        await pilot.pause(.2)
        assert app.current_note.id not in app.unlocked_notes
        assert app.query_one("#locked-note-card").display is True

        # 3. Unlock with NewPassB
        await pilot.click("#btn-screen-unlock")
        await pilot.pause(.2)
        app.screen.query_one("#input-unlock-password").value = "NewPassB"
        await pilot.press("enter")
        await pilot.pause(.2)
        assert app.current_note.id in app.unlocked_notes

        # 4. Remove lock permanently
        await pilot.press("l")
        await pilot.pause(.2)
        assert isinstance(app.screen, ManageLockModal)
        await pilot.click("#btn-opt-remove-lock")
        await pilot.pause(.2)
        assert isinstance(app.screen, ConfirmRemoveLockModal)
        await pilot.click("#btn-confirm-remove")
        await pilot.pause(.2)

        # Should now be a plain unencrypted note
        assert app.current_note.encrypted is False
        assert app.query_one("#locked-note-card").display is False
        assert app.query_one("#markdown-viewer").display is True




