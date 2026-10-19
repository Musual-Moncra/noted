# Noted (📓)

> A fast, keyboard-first Terminal Note-Taking & Journaling CLI & TUI application for Unix & terminal enthusiasts.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-39%20passed-brightgreen.svg)]()

---

## Features

- **Zero Lock-in**: All notes live in `~/.local/share/notes` as human-readable Markdown with YAML frontmatter. No proprietary database lock-in. Versionable with Git or searchable with `ripgrep`.
- **Full Interactive TUI (`note` / `note ui`)**: Split-pane terminal interface built with Textual:
  - Sidebar with instant search and note list
  - In-terminal Markdown viewer with rich formatting
  - Live in-terminal `TextArea` editor with instant `Ctrl+S` saving
  - Interactive formatting toolbar & keyboard shortcuts for bold, italics, code, headings, checkboxes, quotes, and callouts
- **Instant Full-Text Search**: Built-in SQLite3 FTS5 virtual table indexing title, body, and tags with BM25 ranking and highlighted excerpts.
- **Incremental Reconciliation**: Automatically detects when notes are modified or deleted outside the app (e.g. via Neovim, Obsidian, or Git) and synchronizes without requiring a background daemon.
- **Unix CLI Subcommands**: Pipelining and quick terminal capture via `note add`, `note today`, `note list`, `note search`, `note view`, and `note edit`.

---

## Installation

Using `uv` (recommended):
```bash
git clone https://github.com/Musual-Moncra/noted.git
cd noted
uv tool install --editable .
```

Or with `pip`:
```bash
pip install -e .
```

---

## Quick Start

### 1. Launch Interactive TUI
```bash
note
```

### 2. Unix CLI Workflows

```bash
# Frictionless quick thought capture
note add "Refactoring authentication flow with JWT tokens" -t dev,auth --title "Auth Flow"

# View today's journal
note today --view

# Open today's journal in your $EDITOR
note today

# List recent notes and journals
note list
note list --limit 15 --tag dev

# Full-text search with highlighted excerpts
note search "tokens"

# View note formatted directly in the terminal
note view "Auth Flow"

# Open note in $EDITOR (Nano / Vim / Neovim)
note edit "Auth Flow"

# Re-index all notes
note sync
```

---

## TUI Keyboard Shortcuts

| Shortcut | Description |
|---|---|
| `Ctrl+P` / `F2` | **Preview / Toggle View & Edit** (Auto-saves immediately) |
| `Ctrl+W` | **Split Screen Mode** (Side-by-side editor + live markdown rendering) |
| `e` | Enter **Edit** mode |
| `Ctrl+S` | Save current edits manually |
| `Escape` | Return to **View** mode (Auto-saves) / Focus notes list |
| `n` | Create a new note dialog (Title + Tags) |
| `j` | Open or create today's daily journal (`YYYY-MM-DD.md`) |
| `Ctrl+B` | **Bold** selection or insert `**bold text**` |
| `Ctrl+I` | *Italic* selection or insert `*italic text*` |
| `Ctrl+K` | Inline code or code block `` `code` `` |
| `Ctrl+H` | Insert markdown `# Heading` |
| `Ctrl+T` | Insert interactive `- [ ] Todo item` checkbox |
| `Ctrl+E` | Open note in external `$EDITOR` (Neovim/Vim/Nano) |
| `d` | Delete current note (with confirmation prompt) |
| `/` | Focus search bar |
| `?` | Show interactive help modal |
| `q` / `Ctrl+Q` | Quit application |

---

## 3 Workspaces & Modes (Auto-Save Built-in)

No more friction when writing notes. You don't need to manually save before previewing:
1. **👁 View Mode (`Ctrl+P` / `Escape`)**: Clean, formatted Rich Markdown rendering.
2. **📝 Edit Mode (`e`)**: In-terminal code & text editor with markdown formatting toolbar.
3. **◫ Split Screen Mode (`Ctrl+W`)**: Side-by-side editor and live preview that updates in real-time as you type!

*Switching between any mode or selecting another note automatically persists your changes to disk and updates the SQLite FTS5 search index.*

---

## Markdown Formatting Toolbar

When in **Edit** or **Split** mode, an interactive formatting toolbar is available above the text editor:
- **`𝐁 Bold`**: Wraps selection in `**bold**`
- **`𝐼 Italic`**: Wraps selection in `*italic*`
- **`⟨/⟩ Code`**: Wraps selection in code formatting
- **`H# Heading`**: Inserts a new heading
- **`☑ Todo`**: Inserts a checklist item `- [ ]`
- **`❝ Quote`**: Inserts a blockquote `>`
- **`💡 Tip/Callout`**: Inserts a GitHub-style alert callout (`> [!TIP]`)

---

## Directory Structure

```text
~/.local/share/notes/
├── config.toml           # Configuration (editor, templates)
├── index.db              # SQLite3 FTS5 search index (WAL mode)
├── journal/              # Daily journal entries
│   └── 2026-10-19.md
└── notes/                # Standalone & quick capture notes
    └── 20261019-143000-a1b2-project-ideas.md
```

---

## Testing

Run the full test suite with `pytest`:
```bash
uv run pytest -v
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
