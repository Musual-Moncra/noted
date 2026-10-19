# Noted (📓)

> A fast, keyboard-first Terminal Note-Taking & Journaling CLI & TUI application for Unix, macOS & Windows terminal enthusiasts.

[![CI](https://github.com/Musual-Moncra/noted/actions/workflows/ci.yml/badge.svg)](https://github.com/Musual-Moncra/noted/actions/workflows/ci.yml)
[![GitHub Release](https://img.shields.io/github/v/release/Musual-Moncra/noted?color=blue&logo=github)](https://github.com/Musual-Moncra/noted/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-blue)](https://github.com/Musual-Moncra/noted)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-75%20passed-brightgreen.svg)]()

---

## Features

- **Zero Lock-in**: All notes live in local Markdown files with YAML frontmatter (`~/.local/share/notes` on Linux/macOS, `~/.notes` or `%USERPROFILE%\.notes` on Windows). No proprietary database lock-in. Easily versionable with Git or searchable with `ripgrep`.
- **AES-256-GCM Password Protection**: Encrypt sensitive notes at rest using authenticated AES-256-GCM with PBKDF2-HMAC-SHA256 (100k rounds). Session-level in-memory unlocking keeps plaintext confidential without leaking secrets to disk logs or SQLite FTS5 search indexes.
- **Full Interactive TUI (`note` / `note ui`)**: Split-pane terminal interface built with Textual:
  - Sidebar with instant search, notes list, and lock status badges (🔒 / 📓 / 📝)
  - In-terminal Markdown viewer with rich formatting and prominent locked-note cards
  - Live in-terminal `TextArea` editor with instant `Ctrl+S` saving
  - Interactive formatting toolbar & keyboard shortcuts for bold, italics, code, headings, checkboxes, quotes, color highlights, and copy
  - **Live Split-Screen (`Ctrl+W`)**: Real-time side-by-side editing and rendering
  - **Zero-Friction Auto-Save**: Switching modes (`Ctrl+P`, `F2`, `Escape`) or clicking another note auto-saves your work immediately!
  - **Vietnamese IME Smoothness**: Automatic Unicode NFC normalization, combining mark support, and disabled Kitty keyboard protocol for flawless Telex/EVKey/OpenKey typing.
- **Clipboard Integration**: Copy full note or current editor selection to the system clipboard via `c` / `Ctrl+Y` or `note copy`.
- **Safe Note Renaming**: Rename notes on the fly with `r` or `note rename`—automatically updates frontmatter, recalculates slug, and moves the disk file atomically.
- **Instant Full-Text Search**: Built-in SQLite3 FTS5 virtual table indexing title, body, and tags with BM25 ranking and highlighted excerpts.
- **Incremental Reconciliation**: Automatically detects when notes are modified or deleted outside the app (e.g. via Neovim, Obsidian, or Git) and synchronizes without requiring a background daemon.
- **Cross-Platform CLI Subcommands**: Pipelining and terminal capture via `note add`, `note lock`, `note unlock`, `note change-password`, `note copy`, `note rename`, `note today`, `note list`, `note search`, `note view`, and `note edit`.

---

## Installation & Windows Downloads

### 🪟 Windows (Standalone Executable - No Python Required)

1. Go to the [**Latest GitHub Releases**](https://github.com/Musual-Moncra/noted/releases).
2. Download `noted-windows-x64.zip`.
3. Extract the archive and double-click `noted.exe` (or open it inside **Windows Terminal** / PowerShell):
   ```powershell
   .\noted.exe
   ```
4. *(Recommended)* Add the folder containing `noted.exe` to your System `PATH` so you can type `noted` from any terminal.

> **Tip for Windows Terminal users**: For the best visual experience with emojis and icons, use [Windows Terminal](https://aka.ms/terminal) with a font that supports symbols (such as Cascadia Code, JetBrains Mono, or any Nerd Font).

---

### 📦 Install via Python Package Manager (`uv`, `pipx`, `pip`)

Works on **macOS**, **Linux**, and **Windows**:

Using `uv` (recommended):
```bash
uv tool install git+https://github.com/Musual-Moncra/noted.git
```

Or using `pipx`:
```bash
pipx install git+https://github.com/Musual-Moncra/noted.git
```

Or using standard `pip`:
```bash
pip install git+https://github.com/Musual-Moncra/noted.git
```

---

### 🛠️ Build from Source

```bash
git clone https://github.com/Musual-Moncra/noted.git
cd noted
uv sync --all-extras --dev

# Run locally
uv run note

# Build standalone binary with PyInstaller
uv run pyinstaller noted.spec --clean
# Executable is generated in dist/ (dist/noted or dist/noted.exe)
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

# Lock and encrypt a note with password
note lock "Auth Flow" -p "SecretKey123"

# View password-protected note (prompts for password if -p omitted)
note view "Auth Flow" -p "SecretKey123"

# Change the encryption password
note change-password "Auth Flow"

# Permanently decrypt and remove lock
note unlock "Auth Flow"

# Copy note content to system clipboard
note copy "Auth Flow"

# Rename an existing note (updates frontmatter, slug, and disk filename)
note rename "Auth Flow" "New Auth Architecture"

# View today's journal
note today --view

# Open today's journal in your $EDITOR
note today

# List recent notes and journals
note list
note list --limit 15 --tag dev

# Full-text search with highlighted excerpts
note search "tokens"

# Open note in $EDITOR (Nano / Vim / Neovim)
note edit "New Auth Architecture"

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
| `r` | **Rename note** dialog (Atomic rename on disk & FTS5 re-index) |
| `c` / `Ctrl+Y` | **Copy note or selection** to system clipboard |
| `u` | **Unlock** password-protected note |
| `l` | **Lock / Manage Lock** (Change password, Remove lock, Relock now) |
| `j` | Open or create today's daily journal (`YYYY-MM-DD.md`) |
| `Ctrl+B` | **Bold** selection or insert `**bold text**` |
| `Ctrl+I` | *Italic* selection or insert `*italic text*` |
| `Ctrl+K` | Inline code or code block `` `code` `` |
| `Ctrl+H` | Insert markdown `# Heading` |
| `Ctrl+T` | Insert interactive `- [ ] Todo item` checkbox |
| `Ctrl+M` | **Color Palette & Alerts** (Open color picker popup) |
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
- **`🎨 Màu sắc` (`Ctrl+M`)**: Opens the **Color Picker Modal** to apply colored text highlights:
  - 🟢 **Xanh lá (Tip / Success)**: `> [!TIP]`
  - 🔵 **Xanh dương (Note / Info)**: `> [!NOTE]`
  - 🟡 **Vàng (Cảnh báo / Warning)**: `> [!WARNING]`
  - 🔴 **Đỏ (Nguy hiểm / Caution)**: `> [!CAUTION]`
  - 🟣 **Tím (Quan trọng / Important)**: `> [!IMPORTANT]`
  - 🟩 **Diff Xanh (`+`)** & 🟥 **Diff Đỏ (`-`)**: Tô màu dòng văn bản / code
  - 🔴/🔵 **Thẻ HTML**: `<span style="color: ...">` cho Web/Obsidian/GitHub export

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

## Contributing

Contributions are warmly welcome! Whether reporting bugs, proposing new features, or submitting pull requests, please read our:
- [Contributing Guidelines](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

---

## License

MIT License. See [LICENSE](LICENSE) for details.

