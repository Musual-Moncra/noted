# Implementation Plan: Terminal Note-Taking & Journaling CLI & TUI (`noted`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fast, keyboard-first terminal note-taking and journaling application in Python (`noted`) featuring human-readable Markdown storage with YAML frontmatter, SQLite3 FTS5 full-text indexing, Unix CLI subcommands (`typer`, `rich`), and a full-screen interactive Terminal User Interface (`textual`).

**Architecture:**
- **Zero Lock-in Data**: Stored as standard Markdown files in `notes/` (`<id>-<slug>.md`) and `journal/` (`YYYY-MM-DD.md`) with YAML frontmatter.
- **SQLite3 FTS5 Cache**: Indexes metadata, tags, and full-text body for microsecond search. Incremental sync compares filesystem `mtime_ns` to automatically reconcile external edits.
- **Dual Interface**:
  - **Interactive TUI**: Split-pane layout with search, sidebar note list, Rich Markdown viewer, and in-terminal `TextArea` editor with instant `Ctrl+S` saving.
  - **CLI Subcommands**: `note add`, `note today`, `note list`, `note search`, `note view`, `note edit`, `note sync`.

**Tech Stack:** Python 3.12+, `typer>=0.12.0`, `rich>=13.7.0`, `textual>=0.75.0`, `pyyaml>=6.0.1`, `pytest>=8.0.0`, `uv`.

**Spec:** [`docs/superpowers/specs/2026-10-19-terminal-notes-design.md`](file:///Users/musual/%28%20App%20%29%20Noted/docs/superpowers/specs/2026-10-19-terminal-notes-design.md)

---

## Global Constraints

- **Python Version**: Python 3.10+ (using Homebrew Python 3.12 with `uv` virtual environment).
- **Storage Location**: Default `~/.local/share/notes` (or configurable via `NOTES_DIR` env or `~/.config/noted/config.toml`; isolated directory during tests).
- **Frontmatter**: Standard YAML between `---` delimiters (`id`, `title`, `date`, `type`, `tags`).
- **File Safety**: Atomic file writes via temporary files and `os.replace` to prevent partial writes.
- **SQLite Pragma**: `PRAGMA journal_mode=WAL;` and foreign keys enabled.
- **Editor Fallback**: `$EDITOR` -> `$VISUAL` -> `nano` -> `vim` -> `vi` with graceful error handling.

---

## Review Focus

1. **External file modification without CLI**: Note modified outside the app should automatically be re-indexed on the next CLI command or TUI startup without crashing or staying stale.
2. **Corrupted or missing YAML frontmatter**: A file missing frontmatter or having broken YAML should not crash the scanner; it falls back to filename/mtime with a warning.
3. **Missing `$EDITOR` environment variable**: Opening in editor when no `$EDITOR` is defined falls back gracefully down the chain (`nano`, `vim`) and displays a clear message if none are available.
4. **Special search characters in FTS5**: Queries containing punctuation like `c++`, `tag:foo`, or quotes must be sanitized or properly quoted so SQLite FTS5 doesn't throw a syntax error.
5. **Concurrent TUI & CLI operations**: SQLite WAL mode and atomic file replacement ensure no database locking or corrupted file states during rapid saves.

---

## Proposed Changes

### Component 1: Scaffolding & Configuration
Setup project metadata, dependencies, virtual environment, and configuration loader.

#### [NEW] `pyproject.toml`
Defines package `noted`, entry points (`noted = "noted.cli:app"`, `note = "noted.cli:app"`), and dependencies (`typer`, `rich`, `textual`, `pyyaml`, `pytest`).

#### [NEW] `src/noted/__init__.py`
Package initialization with version string `0.1.0`.

#### [NEW] `src/noted/config.py`
`Config` dataclass and loader managing `notes_dir`, `editor`, and journal template settings. Respects `NOTES_DIR` env variable and creates default directory structure if missing.

#### [NEW] `tests/test_config.py`
Tests for configuration loading, default paths, env variable overrides, and directory initialization.

---

### Component 2: Note Model & Frontmatter Parser
Parse and serialize Markdown files with YAML frontmatter.

#### [NEW] `src/noted/models.py`
`Note` dataclass containing `id: str`, `title: str`, `date: str`, `note_type: str`, `tags: list[str]`, `body: str`, `filepath: Path`, `mtime_ns: int`.

#### [NEW] `src/noted/frontmatter.py`
`parse_note_content(raw_text: str) -> tuple[dict, str]` and `serialize_note(metadata: dict, body: str) -> str`. Generates standard note IDs (`YYYYMMDD-HHMMSS`) and URL-safe slugs.

#### [NEW] `tests/test_frontmatter.py`
Tests parsing valid notes, malformed frontmatter fallback, serialization round-trips, and slug generation.

---

### Component 3: Storage Manager
Safe filesystem operations for notes and daily journals.

#### [NEW] `src/noted/storage.py`
`StorageManager` providing:
- `get_journal_path(date_str: str) -> Path`
- `get_note_path(note_id: str, slug: str) -> Path`
- `save_note(note: Note) -> Path` (atomic write)
- `read_note(filepath: Path) -> Note`
- `delete_note(filepath: Path) -> bool`
- `list_note_files() -> list[Path]`
- `create_today_journal() -> Note` (populates with template)

#### [NEW] `tests/test_storage.py`
Tests atomic write, file reading, directory listing, deletion, and journal creation.

---

### Component 4: SQLite Database & FTS5 Indexer
Fast indexing and full-text search engine.

#### [NEW] `src/noted/db.py`
SQLite connection manager, schema initialization (`notes`, `note_tags`, `notes_fts` virtual table, triggers).

#### [NEW] `src/noted/indexer.py`
`NoteIndexer`:
- `sync_all() -> int`: Incremental reconciliation comparing disk `mtime_ns` with DB.
- `index_note(note: Note) -> None`
- `remove_note(note_id: str) -> None`
- `search(query: str, limit: int = 20) -> list[SearchResult]`
- `list_notes(tag: str | None = None, note_type: str | None = None, limit: int = 50) -> list[NoteSummary]`
- `get_note_by_id_or_date(identifier: str) -> Note | None`

#### [NEW] `tests/test_indexer.py`
Tests DB table creation, indexing notes, incremental sync, FTS5 full-text queries, tag filtering, and deletion.

---

### Component 5: Editor Launcher & Rich Terminal Renderer
Terminal presentation and external editor integration.

#### [NEW] `src/noted/editor.py`
`open_in_editor(filepath: Path, config: Config) -> bool`: Safe subprocess runner with fallback chain (`$EDITOR` -> `$VISUAL` -> `nano` -> `vim` -> `vi`).

#### [NEW] `src/noted/renderer.py`
Rich rendering utilities:
- `render_note_table(notes: list[NoteSummary]) -> Table`
- `render_search_results(results: list[SearchResult]) -> None`
- `render_note_view(note: Note) -> None` (Rich Markdown with borders and metadata box)

#### [NEW] `tests/test_editor.py` & `tests/test_renderer.py`
Unit tests for editor detection, error handling, and Rich renderable generation.

---

### Component 6: CLI Subcommands (Typer)
Unix-first command line interface.

#### [NEW] `src/noted/cli.py`
Commands:
- `note`: Default command; launches TUI if interactive, or prints help if piped.
- `note ui` / `note tui`: Explicitly launch TUI.
- `note add <content>`: Quick capture note (`-t, --tag`, `--title`, `-e, --edit`).
- `note today`: Open or create today's journal (`--view` to view in terminal).
- `note list`: Browse recent notes with `--limit`, `--tag`, `--type`.
- `note search <query>`: FTS5 search with highlighted excerpts.
- `note view <id|date>`: Terminal markdown view.
- `note edit <id|date>`: Open in external editor and re-index.
- `note sync`: Force full re-index.

#### [NEW] `tests/test_cli.py`
CliRunner tests verifying command options, exit codes, output formatting, and error handling.

---

### Component 7: Full Interactive Terminal User Interface (Textual)
Rich, keyboard-first split-pane TUI app.

#### [NEW] `src/noted/tui/styles.tcss`
Textual CSS styling for responsive split-pane layout, dark terminal palette, borders, badge pills, and editor typography.

#### [NEW] `src/noted/tui/widgets.py`
- `NoteListItem`: Custom widget displaying title, formatted date, and colored tag badges.
- `NoteMetadataBar`: Header bar with note title, tags, and mode indicator.

#### [NEW] `src/noted/tui/screens.py`
- `NewNoteScreen`: Modal dialog for creating notes with title and tags.
- `ConfirmDeleteScreen`: Safety modal before deleting notes.
- `HelpScreen`: Quick reference modal for keybindings.

#### [NEW] `src/noted/tui/app.py`
`NotedApp(App)`:
- Left sidebar: Search filter, filter tabs `[All] [Notes] [Journals]`, scrollable note list.
- Right canvas: Toggleable between `MarkdownViewer` (View mode) and `TextArea` (Edit mode).
- Reactive actions: Instant search on typing in filter box, `Ctrl+S` save, `n` new note, `j` today's journal, `e` edit toggle, `^e` external editor, `d` delete, `?` help, `q` quit.

#### [NEW] `tests/test_tui.py`
Textual `App.run_test()` pilot tests for navigation, searching, mode toggling, and note creation.

---

## Detailed Task Breakdown

### Task 1: Scaffolding, Package Setup & Config
**Files:**
- Create: `pyproject.toml`
- Create: `src/noted/__init__.py`
- Create: `src/noted/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` dataclass with `notes_dir: Path`, `editor: str | None`, `journal_template: str`.
- Function: `load_config(custom_path: Path | None = None) -> Config`

- [ ] **Step 1: Write failing test in `tests/test_config.py`**
  Assert default notes directory (`~/.local/share/notes`), `NOTES_DIR` environment override, and directory creation on ensure.
- [ ] **Step 2: Run test to verify it fails** (`pytest tests/test_config.py`)
- [ ] **Step 3: Implement `pyproject.toml`, `__init__.py`, and `src/noted/config.py`**
- [ ] **Step 4: Run test to verify it passes** (`pytest tests/test_config.py`)
- [ ] **Step 5: Commit** (`git commit -m "feat: scaffold project and config management"`)

---

### Task 2: Note Model & YAML Frontmatter Parser
**Files:**
- Create: `src/noted/models.py`
- Create: `src/noted/frontmatter.py`
- Test: `tests/test_frontmatter.py`

**Interfaces:**
- Consumes: Standard libraries (`dataclasses`, `datetime`, `re`, `yaml`).
- Produces: `Note` dataclass, `parse_frontmatter(content: str) -> tuple[dict, str]`, `serialize_note(metadata: dict, body: str) -> str`, `generate_note_id() -> str`, `slugify(title: str) -> str`.

- [ ] **Step 1: Write failing test in `tests/test_frontmatter.py`**
  Test round-trip serialization, missing frontmatter fallback, invalid YAML recovery, and slug generation.
- [ ] **Step 2: Run test to verify it fails** (`pytest tests/test_frontmatter.py`)
- [ ] **Step 3: Implement `src/noted/models.py` and `src/noted/frontmatter.py`**
- [ ] **Step 4: Run test to verify it passes** (`pytest tests/test_frontmatter.py`)
- [ ] **Step 5: Commit** (`git commit -m "feat: add note models and frontmatter parser"`)

---

### Task 3: Storage Manager (Filesystem CRUD)
**Files:**
- Create: `src/noted/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `Config`, `Note`, `parse_frontmatter`, `serialize_note`.
- Produces: `StorageManager` with `save_note()`, `read_note()`, `delete_note()`, `list_files()`, `create_journal()`.

- [ ] **Step 1: Write failing test in `tests/test_storage.py`**
  Test atomic saving of notes, reading notes, journal creation with template sections, and deletion.
- [ ] **Step 2: Run test to verify it fails** (`pytest tests/test_storage.py`)
- [ ] **Step 3: Implement `src/noted/storage.py`**
- [ ] **Step 4: Run test to verify it passes** (`pytest tests/test_storage.py`)
- [ ] **Step 5: Commit** (`git commit -m "feat: add storage manager for filesystem persistence"`)

---

### Task 4: SQLite Database & FTS5 Search Indexer
**Files:**
- Create: `src/noted/db.py`
- Create: `src/noted/indexer.py`
- Test: `tests/test_indexer.py`

**Interfaces:**
- Consumes: `StorageManager`, `Note`.
- Produces: `DatabaseManager`, `NoteIndexer` with `sync_all()`, `search()`, `list_notes()`, `get_note_by_id_or_date()`.

- [ ] **Step 1: Write failing test in `tests/test_indexer.py`**
  Test DB schema creation, FTS5 virtual table queries, tag filtering, incremental sync when a file is modified externally, and deletion.
- [ ] **Step 2: Run test to verify it fails** (`pytest tests/test_indexer.py`)
- [ ] **Step 3: Implement `src/noted/db.py` and `src/noted/indexer.py`**
- [ ] **Step 4: Run test to verify it passes** (`pytest tests/test_indexer.py`)
- [ ] **Step 5: Commit** (`git commit -m "feat: add sqlite fts5 indexing engine and sync"`)

---

### Task 5: Editor Integration & Rich Terminal Renderer
**Files:**
- Create: `src/noted/editor.py`
- Create: `src/noted/renderer.py`
- Test: `tests/test_editor.py`
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `Config`, `Note`, `SearchResult`, `NoteSummary`.
- Produces: `open_in_editor(path: Path) -> bool`, `render_note_table()`, `render_search_results()`, `render_note_view()`.

- [ ] **Step 1: Write failing tests in `tests/test_editor.py` and `tests/test_renderer.py`**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement `src/noted/editor.py` and `src/noted/renderer.py`**
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit** (`git commit -m "feat: add editor launcher and rich renderers"`)

---

### Task 6: CLI Subcommands (Typer)
**Files:**
- Create: `src/noted/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `Config`, `StorageManager`, `NoteIndexer`, `Renderer`, `Editor`.
- Produces: Typer `app` with commands `add`, `today`, `list`, `search`, `view`, `edit`, `sync`, `ui`.

- [ ] **Step 1: Write failing tests in `tests/test_cli.py`** (`CliRunner` testing `add`, `today`, `list`, `search`, `view`).
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement `src/noted/cli.py`**
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit** (`git commit -m "feat: implement typer cli subcommands"`)

---

### Task 7: Full Interactive Terminal UI (Textual)
**Files:**
- Create: `src/noted/tui/styles.tcss`
- Create: `src/noted/tui/widgets.py`
- Create: `src/noted/tui/screens.py`
- Create: `src/noted/tui/app.py`
- Test: `tests/test_tui.py`

**Interfaces:**
- Consumes: `StorageManager`, `NoteIndexer`, `Note`, `Config`.
- Produces: `NotedApp` (Textual App), `NewNoteScreen`, `ConfirmDeleteScreen`, `HelpScreen`.

- [ ] **Step 1: Write failing test in `tests/test_tui.py`** using Textual's async `app.run_test()` pilot.
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement Textual styles, widgets, modal screens, and main app**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit** (`git commit -m "feat: implement interactive textual tui"`)

---

### Task 8: Verification & Walkthrough
**Files:**
- Create: `walkthrough.md` in artifact directory.
- Verify: Full test suite passing (`pytest`).
- Verify: Terminal CLI command executions (`note add`, `note list`, `note search`, `note view`).
- Verify: Interactive TUI launch (`note ui`).

- [ ] **Step 1: Run complete automated test suite** (`pytest -v`)
- [ ] **Step 2: Run manual CLI verification commands**
- [ ] **Step 3: Create Walkthrough artifact**

---

## Verification Plan

### Automated Tests
Run via `uv run pytest`:
```bash
uv run pytest -v
```
Checks:
- `test_config.py`: Path handling, environment variable overrides.
- `test_frontmatter.py`: YAML parsing, fallback on corruption, serialization.
- `test_storage.py`: CRUD operations, atomic writes, journal generation.
- `test_indexer.py`: SQLite FTS5 table indexing, incremental mtime sync, tag queries.
- `test_editor.py` & `test_renderer.py`: Editor fallback discovery, Rich tables and markdown renderers.
- `test_cli.py`: Command routing, argument parsing, error exits via Typer `CliRunner`.
- `test_tui.py`: Textual headless pilot testing app startup, note selection, and mode switching.

### Manual Verification
1. **Quick Capture**:
   ```bash
   note add "Quick thought from terminal" -t test,quick
   note list
   ```
2. **Daily Journal**:
   ```bash
   note today --view
   ```
3. **Full-Text Search**:
   ```bash
   note search "terminal"
   ```
4. **Markdown Terminal View**:
   ```bash
   note view <note-id>
   ```
5. **Interactive TUI**:
   ```bash
   note
   ```
   Verify split-screen navigation, search filtering, switching between View mode and in-terminal Edit mode, and saving changes with `Ctrl+S`.
