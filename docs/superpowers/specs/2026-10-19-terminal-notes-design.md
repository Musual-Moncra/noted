# Architecture Specification: Terminal Note-Taking & Journaling CLI & TUI (`noted`)

- **Date:** 2026-10-19
- **Status:** Approved
- **Target Audience:** Unix philosophy enthusiasts, terminal-first developers, keyboard-driven note-takers.

---

## 1. Executive Summary & Goals

`noted` is a fast, keyboard-first terminal note-taking and journaling application. It bridges the gap between lightweight Unix CLI commands (fast capture, scriptable output, grep-friendly Markdown) and a rich, interactive Terminal User Interface (TUI) for browsing, searching, and writing notes without leaving the terminal.

### Key Tenets
1. **Zero Lock-in**: All notes are stored as human-readable Markdown files with YAML frontmatter. The files can be committed to Git, edited in Neovim/Emacs/Obsidian, or searched with `ripgrep`.
2. **Speed & Keyboard First**: Fast startup, blazing-fast full-text search with SQLite FTS5, and ergonomic keyboard shortcuts in the TUI.
3. **Dual Modality**:
   - **Interactive TUI (`note` / `note ui`)**: Full-screen split-pane interface with live Markdown preview, in-terminal editor, quick note creation dialogs, and instant search.
   - **CLI Subcommands (`note add`, `note today`, `note search`, `note list`, `note view`, `note edit`)**: Unix-style commands for quick capture and shell integration.
4. **Resilient Sync**: Markdown files are the single source of truth. An internal SQLite3 index reconciles file modification timestamps (`mtime_ns`) automatically, so external edits are immediately indexed without user intervention.

---

## 2. Directory Layout & Data Format

### 2.1 Notes Directory
By default, notes live in `~/.local/share/notes` (or overridden by the `NOTES_DIR` environment variable, or configured in `~/.config/noted/config.toml`):

```text
~/.local/share/notes/
├── config.toml           # User preferences and journal templates
├── index.db              # SQLite3 database with FTS5 virtual table
├── journal/              # Daily journal entries
│   └── YYYY-MM-DD.md
└── notes/                # Quick capture & standalone notes
    └── <id>-<slug>.md    # e.g., 20261019-143000-project-ideas.md
```

### 2.2 YAML Frontmatter Schema
Each note starts with valid YAML frontmatter between `---` delimiters:

```markdown
---
id: "20261019-143000"
title: "Project Architecture Ideas"
date: "2026-10-19T14:30:00"
type: "note"
tags:
  - python
  - unix
  - cli
---

# Project Architecture Ideas

Note content in standard GitHub-flavored Markdown...
```

For Daily Journals (`journal/YYYY-MM-DD.md`):
```markdown
---
id: "2026-10-19"
title: "Daily Journal - 2026-10-19"
date: "2026-10-19"
type: "journal"
tags:
  - journal
---

## Highlights

## Reflections

## Todo
- [ ] 
```

---

## 3. SQLite3 Schema & FTS5 Indexing

Markdown files are the source of truth; SQLite is a fast query cache that can be rebuilt at any time.

```sql
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    filepath TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    type TEXT NOT NULL,       -- 'note' or 'journal'
    tags TEXT NOT NULL,       -- JSON array of strings: '["python", "cli"]'
    mtime_ns INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS note_tags (
    note_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (note_id, tag),
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title,
    body,
    tags,
    content='notes',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync with the notes table
CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, body, tags)
    VALUES (new.rowid, new.title, '', new.tags);
END;

CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, body, tags)
    VALUES('delete', old.rowid, old.title, '', old.tags);
END;

CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, body, tags)
    VALUES('delete', old.rowid, old.title, '', old.tags);
    INSERT INTO notes_fts(rowid, title, body, tags)
    VALUES (new.rowid, new.title, '', new.tags);
END;
```

*(Note: During note indexing, the note body content is also indexed into FTS so full-text search covers both title, body text, and tags).*

### 3.1 Incremental Reconciliation
When `db.sync()` runs:
1. Walk the `notes/` and `journal/` folders to get current files with `mtime_ns`.
2. Compare with existing records in `notes` table:
   - File missing from disk -> delete from DB.
   - File not in DB or `disk_mtime > db_mtime` -> re-parse frontmatter and body, update DB.
3. Because checking file stats on SSD takes <5ms for thousands of files, this check runs seamlessly on CLI/TUI startup.

---

## 4. Full Terminal User Interface (TUI) Architecture

Built with **Textual**:

### 4.1 Layout
- **Header**: App title, current time, active note count.
- **Left Panel (Sidebar - width ~32 cols)**:
  - `Input`: Search filter (`/` to focus).
  - `RadioSet` or `TabbedContent`: Quick filter tabs `[All]`, `[Notes]`, `[Journals]`.
  - `OptionList` / `ListView`: Notes list showing Title, Date, and Tag badges.
- **Right Panel (Main Canvas)**:
  - Note Metadata Bar: Title, Created date, Type, Tags, current Mode (`[VIEW]` or `[EDIT]`).
  - View Mode: `MarkdownViewer` / `Markdown` widget with formatted typography, tables, and syntax-highlighted code.
  - Edit Mode: `TextArea` with Markdown syntax highlighting, allowing direct typing and editing in the terminal.
- **Footer**:
  - Keybinding action pills:
    - `[n]` New Note modal
    - `[j]` Today's Journal
    - `[e]` Edit in TUI / View toggle
    - `[^s]` Save changes
    - `[^e]` Open in external `$EDITOR`
    - `[d]` Delete note
    - `[/]` Search
    - `[?]` Help modal
    - `[q]` Quit

### 4.2 Interactive Modals (Textual Screens)
- `NewNoteModal`: Prompts for Title and Tags (comma-separated). On submit, creates note, selects it, and enters Edit mode immediately.
- `ConfirmDeleteModal`: Safe prompt showing note title and warning before deletion.
- `HelpModal`: Lists all keyboard shortcuts and navigation commands.

---

## 5. CLI Architecture (`typer` + `rich`)

Entry point command: `note` (or `noted`).

1. `note`: Without subcommands, launches the interactive TUI.
2. `note ui` / `note tui`: Explicitly launches the interactive TUI.
3. `note add "<content>"`:
   - Flags: `-t, --tag <tag1,tag2>`, `--title <title>`, `-e, --edit` (opens editor).
   - Frictionless quick-capture: Creates note file, writes content, indexes into DB, prints confirmation via Rich.
4. `note today` (alias: `note journal`):
   - Opens today's journal (`journal/YYYY-MM-DD.md`).
   - If file does not exist, populates with customizable template sections (`## Highlights`, `## Reflections`, `## Todo`).
   - Default opens in `$EDITOR`; if `--view` is passed, renders in terminal.
5. `note list`:
   - Flags: `--limit <int>` (default 10), `--tag <name>`, `--type <note|journal>`.
   - Outputs a clean, styled Rich table with columns: `ID`, `Date`, `Type`, `Title`, `Tags`.
6. `note search "<query>"`:
   - Full-text search across titles, tags, and body.
   - Outputs matching notes with highlighted snippets / line context.
7. `note view <id|date>`:
   - Renders the note with Rich Markdown in the terminal.
8. `note edit <id|date>`:
   - Resolves note by ID or date, opens in `$EDITOR` (fallback `nano` / `vim`), re-indexes on exit.
9. `note sync`:
   - Re-indexes all notes on disk and prunes stale records.

---

## 6. Error Handling & Edge Cases

1. **Missing `$EDITOR`**:
   - Check `$EDITOR` -> `$VISUAL` -> `nano` -> `vim` -> `vi`.
   - If none found or executable fails, inform user with a helpful Rich error message and suggest setting `export EDITOR=nano`.
2. **Corrupted Frontmatter**:
   - If YAML parsing fails on an existing file, do not crash. Log a warning, use the filename as fallback title, set type to `note`, and mark as corrupted in metadata so user can fix it.
3. **Invalid Dates / Note IDs**:
   - Return clean error message "Note matching '<query>' not found." Suggest running `note list` or `note search`.
4. **Concurrent Access & File Safety**:
   - Atomic file writes using temporary files (`tempfile.NamedTemporaryFile` + `os.replace`) to prevent corrupted notes on system interruption.
   - SQLite WAL mode (`PRAGMA journal_mode=WAL;`) enabled for high-concurrency read/write without locking.

---

## 7. Verification Strategy

1. **Automated Unit & Integration Tests (`pytest`)**:
   - Frontmatter parsing & serialization (round-trip test, corrupt YAML test).
   - Storage manager (create, read, update, delete, paths).
   - Database indexing & FTS5 search (insert, update, delete, incremental sync, search queries).
   - CLI commands via `typer.testing.CliRunner` (`note add`, `note list`, `note search`, `note view`).
2. **TUI Tests (`textual.pilot`)**:
   - Automated headless testing with Textual's test pilot: launching app, switching notes, toggling edit/view mode, triggering search.
3. **Manual Verification**:
   - Interactive CLI commands in terminal.
   - Interactive TUI session verification.
