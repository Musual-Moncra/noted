"""Generate UI previews from disposable example notes, never the user's library."""
import asyncio
from pathlib import Path
import tempfile
from noted.config import Config
from noted.db import DatabaseManager
from noted.indexer import NoteIndexer
from noted.storage import StorageManager
from noted.tui.app import NotedApp


async def main():
    output = Path('docs/previews').resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='noted-preview-') as directory:
        config = Config(notes_dir=Path(directory).resolve())
        storage = StorageManager(config)
        project = storage.create_folder('Work/Noted')
        storage.create_folder('Study/English')
        storage.create_folder('Inbox')
        storage.create_note('Ideas for the weekend', 'A quiet morning, a good book, and a walk.', tags=['personal'])
        storage.create_note('Meeting notes', '# Decisions\n\nKeep the writing experience simple.\n\n- [x] Organize with folders\n- [ ] Review next week', tags=['meeting'], folder=project)
        note = storage.create_note('A quieter place to think', '# A quieter place to think\n\nCapture a thought, give it a home, and get back to writing.\n\n## Today\n\n- [x] Organize project notes\n- [x] Keep important ideas close\n- [ ] Make room for the next thought\n\n> Small improvements add up.\n\n## Built for your workflow\n\nUse **folders** for structure and *tags* to connect ideas.\n\n```python\nthought = "Keep it simple"\n```', tags=['design', 'work'], folder=project)
        note.pinned = True
        storage.save_note(note)
        NoteIndexer(DatabaseManager(config.db_path), storage).sync_all()
        app = NotedApp(custom_config=config)
        async with app.run_test(size=(180,45)) as pilot:
            await pilot.pause(.3)
            app.open_note(storage.read_note(note.filepath))
            tree = app.query_one('#folder-tree')
            work = next(child for child in tree.root.children if child.data.name == 'Work')
            work.expand()
            await pilot.pause(.3)
            for width, height in [(180,45),(140,40),(100,30),(80,24),(60,20)]:
                await pilot.resize_terminal(width,height)
                await pilot.pause(.3)
                app.save_screenshot(f'noted-{width}.svg', path=str(output))
            await pilot.resize_terminal(180,45)
            app.set_mode('split')
            await pilot.pause(.3)
            app.save_screenshot('noted-split.svg', path=str(output))
            app.action_more()
            await pilot.pause(.3)
            app.save_screenshot('noted-actions.svg', path=str(output))


if __name__ == '__main__':
    asyncio.run(main())
