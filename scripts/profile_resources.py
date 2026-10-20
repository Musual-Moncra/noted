"""Reproducible, isolated Textual resource profile (no personal notes are read).

Run with the project's Python, for example:
    uv run python scripts/profile_resources.py --notes 10000 --cycles 200 --idle-seconds 60 --output profile.json
PYTHONPATH may point at an older checkout to measure the same workload before changes.
"""
import argparse
import gc
import asyncio
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import tempfile
import time

from noted.config import Config
from noted.db import DatabaseManager
from noted.indexer import NoteIndexer
from noted.storage import StorageManager
from noted.models import NoteSummary
from noted.tui.app import NotedApp
from textual.widget import Widget


def rss_mib():
    if Path('/proc/self/statm').exists():
        return int(Path('/proc/self/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE') / 1048576
    return int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(os.getpid())], text=True)) / 1024


def peak_mib():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (1048576 if platform.system() == 'Darwin' else 1024)


async def profile(args):
    with tempfile.TemporaryDirectory(prefix='noted-profile-') as directory:
        config = Config(notes_dir=Path(directory).resolve())
        if hasattr(config, 'animation'):
            config.animation = args.animation
        storage = StorageManager(config)
        for i in range(args.notes):
            (config.notes_subdir / f'n{i:05}.md').write_text(
                f'---\nid: n{i:05}\ntitle: Project note {i}\ndate: "2026-10-20T10:00:00"\ntype: note\ntags: [work, project]\n---\n\n'
                + f'# Project {i}\n\nSearchable project content and Vietnamese: Tiếng Việt.\n' * 4,
                encoding='utf-8')
        indexer = NoteIndexer(DatabaseManager(config.db_path), storage)
        start = time.perf_counter()
        indexer.sync_all()
        cold_index_ms = (time.perf_counter() - start) * 1000
        samples = []
        for _ in range(30):
            start = time.perf_counter()
            indexer.search('project', limit=100)
            samples.append((time.perf_counter() - start) * 1000)
        result = dict(platform=platform.platform(), python=platform.python_version(),
                      notes=args.notes, animation=args.animation, cold_index_ms=round(cold_index_ms, 1),
                      search_p95_ms=round(sorted(samples)[28], 2))
        result['search_p95_with_debounce_ms'] = round(result['search_p95_ms'] + 150, 2)
        Path(args.output).with_suffix('.progress.json').write_text(json.dumps(result, indent=2))
        app = NotedApp(custom_config=config)
        start = time.perf_counter()
        async with app.run_test(size=(180, 45)) as pilot:
            await pilot.pause(0.3)
            result['warm_start_ms'] = round((time.perf_counter() - start) * 1000, 1)
            result['rss_ready_mib'] = round(rss_mib(), 2)
            summaries = indexer.list_notes(limit=30)
            marks = []
            for i in range(args.cycles):
                app.load_note_by_summary(summaries[i % len(summaries)])
                app.set_mode('edit')
                app.set_mode('view')
                await pilot.pause(0.01)
                if (i + 1) % 50 == 0:
                    marks.append({'cycles': i + 1, 'rss_mib': round(rss_mib(), 2),
                                  'widget_objects': sum(isinstance(item, Widget) for item in gc.get_objects())})
            result['cycle_rss'] = marks
            Path(args.output).with_suffix('.progress.json').write_text(json.dumps(result, indent=2))
            if args.previews:
                output = Path(args.previews)
                output.mkdir(parents=True, exist_ok=True)
                for width, height in [(180, 45), (140, 40), (100, 30), (80, 24), (60, 20)]:
                    await pilot.resize_terminal(width, height)
                    await pilot.pause(0.2)
                    app.save_screenshot(f'noted-{width}.svg', path=str(output))
                await pilot.resize_terminal(180, 45)
            large = storage.create_note('Large document', body=('A line of Markdown text for the large document.\n' * 23000)[:1048576])
            indexer.index_note(large)
            summary = NoteSummary(large.id, large.title, large.date, large.note_type, large.tags, large.filepath)
            app.load_note_by_summary(summary)
            app.set_mode('edit')
            await pilot.pause(0.2)
            result['rss_large_edit_mib'] = round(rss_mib(), 2)
            app.set_mode('view')
            await pilot.pause(0.2)
            result['rss_large_view_mib'] = round(rss_mib(), 2)
            app.load_note_by_summary(summaries[0])
            await pilot.pause(2)
            cpu_start, wall_start = time.process_time(), time.perf_counter()
            await asyncio.sleep(args.idle_seconds)
            result['idle_seconds'] = args.idle_seconds
            result['idle_cpu_percent_one_core'] = round(100 * (time.process_time() - cpu_start) / (time.perf_counter() - wall_start), 3)
            result['rss_final_mib'] = round(rss_mib(), 2)
            result['peak_rss_mib'] = round(peak_mib(), 2)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notes', type=int, default=1000)
    parser.add_argument('--cycles', type=int, default=200)
    parser.add_argument('--idle-seconds', type=float, default=60)
    parser.add_argument('--animation', choices=['off', 'subtle'], default='subtle')
    parser.add_argument('--previews')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = asyncio.run(profile(args))
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
