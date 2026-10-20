import pytest
from textual.widgets import TextArea, Input, ListView
from noted.config import Config
from noted.storage import StorageManager
from noted.tui.app import NotedApp


@pytest.fixture
def seeded(tmp_path):
    config = Config(notes_dir=tmp_path / 'notes', animation='off')
    storage = StorageManager(config)
    a = storage.create_note('Alpha', 'initial')
    b = storage.create_note('Beta', 'other')
    return config, storage, a, b


@pytest.mark.asyncio
async def test_idle_autosave_and_search_preserve_editor(seeded):
    config, storage, a, b = seeded
    async with NotedApp(custom_config=config).run_test(size=(180, 45)) as pilot:
        app = pilot.app
        await pilot.pause()
        app.open_note(a)
        app.set_mode('edit')
        app.query_one('#text-editor', TextArea).text = 'unsaved draft'
        app.query_one('#search-input', Input).value = 'Beta'
        await pilot.pause(0.25)
        assert app.current_note.id == a.id
        assert app.query_one('#text-editor', TextArea).text == 'unsaved draft'
        await pilot.pause(1.1)
        assert 'unsaved draft' in storage.read_note(a.filepath).body
        assert app.save_state == 'Saved'


@pytest.mark.asyncio
async def test_save_failure_blocks_switch_and_relock_is_safe(seeded, monkeypatch):
    config, storage, a, b = seeded
    storage.lock_note(a, 'password')
    async with NotedApp(custom_config=config).run_test(size=(180, 45)) as pilot:
        app = pilot.app
        await pilot.pause()
        app.open_note(a)
        app.unlock_current('password')
        app.set_mode('edit')
        app.query_one('#text-editor', TextArea).text = 'latest secret'
        original_save = app.storage.save_note
        def fail(*args, **kwargs):
            raise OSError('disk full')
        monkeypatch.setattr(app.storage, 'save_note', fail)
        assert app.open_note(b) is False
        assert app.current_note.id == a.id
        monkeypatch.setattr(app.storage, 'save_note', original_save)
        app._relock_current_note()
        assert app.current_note.id not in app.unlocked_notes
        disk = storage.read_note(a.filepath)
        assert storage.unlock_note(disk, 'password') == 'latest secret'
        assert 'latest secret' not in a.filepath.read_text()


@pytest.mark.asyncio
async def test_view_edit_release_hidden_documents_and_large_note_policy(seeded):
    config, storage, a, b = seeded
    large = storage.create_note('Large', 'x' * (256 * 1024))
    async with NotedApp(custom_config=config).run_test(size=(180, 45)) as pilot:
        app = pilot.app
        await pilot.pause()
        app.open_note(a)
        app.set_mode('edit')
        await pilot.pause()
        assert len(app.query_one('#markdown-viewer').children) == 0
        app.set_mode('view')
        await pilot.pause()
        assert app.query_one('#text-editor').text == ''
        app.open_note(large)
        app.set_mode('split')
        assert app.query_one('#text-editor').language is None
        assert app.large_note
        app.query_one('#text-editor').text += 'tail'
        app.save_current_note()
        assert storage.read_note(large.filepath).body.endswith('tail')


@pytest.mark.asyncio
async def test_unlocked_cache_contains_only_active_note(seeded):
    config, storage, a, b = seeded
    storage.lock_note(a, 'password')
    async with NotedApp(custom_config=config).run_test(size=(180, 45)) as pilot:
        app = pilot.app
        await pilot.pause()
        app.open_note(a)
        app.unlock_current('password')
        app.open_note(b)
        assert not app.unlocked_notes
        app.open_note(a)
        assert a.id in app.unlocked_notes


@pytest.mark.asyncio
async def test_responsive_layout_and_bounded_pages(seeded):
    config, storage, a, b = seeded
    for i in range(105):
        storage.create_note(f'Note {i}')
    async with NotedApp(custom_config=config).run_test(size=(180, 45)) as pilot:
        app = pilot.app
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert len(app.query_one('#notes-list').children) == 100
        app.action_next_page()
        await pilot.pause()
        assert len(app.query_one('#notes-list').children) == 7
        app.open_note(a)
        app.set_mode('split')
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert app.note_mode == 'edit'
        assert not app.query_one('#navigation').display
        assert not app.query_one('#sidebar').display


@pytest.mark.asyncio
async def test_folder_tags_pin_archive_and_quick_capture(seeded):
    config, storage, a, b = seeded
    async with NotedApp(custom_config=config).run_test(size=(180, 45)) as pilot:
        app = pilot.app
        await pilot.pause()
        app.open_note(a)
        app.update_note_metadata(tags=['Work', 'work'], pinned=True)
        assert app.current_note.tags == ['work']
        app.action_archive_note()
        assert storage.read_note(a.filepath).archived
        app.set_scope('archive')
        await pilot.pause()
        assert app.total_notes == 1
        app.open_note(storage.read_note(a.filepath))
        app.action_archive_note()
        assert not storage.read_note(a.filepath).archived
        app.action_quick_capture()
        await pilot.pause()
        app.screen.query_one('#input-title').value = 'Quick thought'
        await pilot.click('#btn-create')
        await pilot.pause()
        assert app.current_note.filepath.parent.name == 'Inbox'


@pytest.mark.asyncio
async def test_startup_recovers_stale_index(seeded):
    from noted.db import DatabaseManager
    from noted.indexer import NoteIndexer
    config, storage, a, b = seeded
    indexer = NoteIndexer(DatabaseManager(config.db_path), storage)
    indexer.sync_all()
    a.filepath.unlink()
    b.filepath.unlink()
    async with NotedApp(custom_config=config).run_test(size=(180,45)) as pilot:
        await pilot.pause(0.3)
        assert pilot.app.current_note is None
        assert pilot.app.total_notes == 0


@pytest.mark.asyncio
async def test_missing_conflict_reload_keeps_draft(seeded):
    config, storage, a, b = seeded
    async with NotedApp(custom_config=config).run_test(size=(180,45)) as pilot:
        app = pilot.app
        await pilot.pause()
        app.open_note(a)
        app.set_mode('edit')
        app.query_one('#text-editor').text = 'precious draft'
        a.filepath.unlink()
        assert not app.save_current_note()
        await pilot.pause()
        await pilot.click('#menu-reload')
        await pilot.pause()
        assert app.query_one('#text-editor').text == 'precious draft'
        assert app.save_state == 'Save failed'


@pytest.mark.asyncio
async def test_animated_modal_can_close(seeded):
    import asyncio
    config, _, _, _ = seeded
    config.animation = 'subtle'
    async with NotedApp(custom_config=config).run_test(size=(180,45)) as pilot:
        app = pilot.app
        await pilot.pause()
        await pilot.press('n')
        await pilot.pause()
        await asyncio.wait_for(pilot.press('escape'), timeout=3)
        await pilot.pause()
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_repeated_mode_changes_keep_footer_controls_and_pages_bounded(seeded):
    from textual.widgets import Footer
    config, storage, a, b = seeded
    async with NotedApp(custom_config=config).run_test(size=(180,45)) as pilot:
        app = pilot.app
        await pilot.pause()
        await app.workers.wait_for_complete()
        controls = tuple(app.query_one(Footer).children)
        # Refreshes may overlap when indexing finishes while the query changes.
        import asyncio
        await asyncio.gather(app.refresh_notes_list(), app.refresh_notes_list())
        assert len(app.query_one('#notes-list').children) == 2
        for i in range(20):
            app.open_note(a if i % 2 else b)
            app.set_mode('edit')
            app.set_mode('view')
            await pilot.pause(.01)
        assert tuple(app.query_one(Footer).children) == controls
        assert len(app.unlocked_notes) <= 1


@pytest.mark.asyncio
async def test_background_updates_and_autosave_work_while_modal_open(seeded):
    config, storage, a, _ = seeded
    async with NotedApp(custom_config=config).run_test(size=(180,45)) as pilot:
        app = pilot.app
        await pilot.pause()
        app.open_note(a)
        app.set_mode('edit')
        app.query_one('#text-editor').text = 'draft during menu'
        app.action_more()
        await pilot.pause(.2)
        await app.sync_finished(None)
        await pilot.pause(1.1)
        assert 'draft during menu' in storage.read_note(a.filepath).body
        assert len(app.screen_stack) == 2


@pytest.mark.asyncio
async def test_explicit_overwrite_can_recreate_missing_encrypted_note(seeded):
    config, storage, a, _ = seeded
    storage.lock_note(a, 'password')
    async with NotedApp(custom_config=config).run_test(size=(180,45)) as pilot:
        app = pilot.app
        await pilot.pause()
        app.open_note(a)
        app.unlock_current('password')
        app.set_mode('edit')
        app.query_one('#text-editor').text = 'recovered draft'
        a.filepath.unlink()
        assert app.save_current_note(force=True)
        assert storage.unlock_note(storage.read_note(a.filepath), 'password') == 'recovered draft'


@pytest.mark.asyncio
async def test_resize_preserves_draft_even_when_disk_write_fails(seeded, monkeypatch):
    config, storage, a, _ = seeded
    async with NotedApp(custom_config=config).run_test(size=(180,45)) as pilot:
        app = pilot.app
        await pilot.pause()
        app.open_note(a)
        app.set_mode('split')
        app.query_one('#text-editor').text = 'draft survives resize'
        def fail(*args, **kwargs):
            raise OSError('disk full')
        monkeypatch.setattr(app.storage, 'save_note', fail)
        await pilot.resize_terminal(80,24)
        await pilot.pause()
        assert app.note_mode == 'edit'
        assert app.query_one('#text-editor').text == 'draft survives resize'


@pytest.mark.asyncio
async def test_type_and_tag_filters_can_be_combined_in_ui(seeded):
    from textual.widgets import Select
    config, storage, a, _ = seeded
    storage.get_or_create_today_journal()
    async with NotedApp(custom_config=config).run_test(size=(180,45)) as pilot:
        app = pilot.app
        await pilot.pause()
        await pilot.click('#filter-more')
        await pilot.pause()
        app.screen.query_one('#filter-type', Select).value = 'note'
        await pilot.click('#filter-apply')
        await pilot.pause()
        assert app.total_notes == 2
        assert app.filters()['note_type'] == 'note'


@pytest.mark.asyncio
async def test_repeated_sync_requests_never_run_indexers_concurrently(seeded, monkeypatch):
    import threading
    import time
    config, _, _, _ = seeded
    async with NotedApp(custom_config=config).run_test(size=(180,45)) as pilot:
        app = pilot.app
        await pilot.pause(.2)
        original = app.indexer.sync_all
        lock = threading.Lock()
        active = maximum = 0
        def slow_sync(*args, **kwargs):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            try:
                time.sleep(.2)
                return original(*args, **kwargs)
            finally:
                with lock:
                    active -= 1
        monkeypatch.setattr(app.indexer, 'sync_all', slow_sync)
        app.start_sync()
        await pilot.pause(.01)
        app.start_sync()
        await pilot.pause(.01)
        app.start_sync()
        await pilot.pause(.6)
        assert maximum == 1


@pytest.mark.asyncio
async def test_button_focus_keeps_raised_style_without_reversed_label(seeded):
    from textual.widgets import Button

    config, _, _, _ = seeded
    async with NotedApp(custom_config=config).run_test(size=(180, 45)) as pilot:
        button = pilot.app.query_one('#nav-capture', Button)
        button.focus()
        await pilot.pause()
        assert button.has_focus
        assert not button.styles.text_style.reverse
        assert button.styles.border_top[0] == 'tall'
        assert button.styles.border_bottom[0] == 'tall'
