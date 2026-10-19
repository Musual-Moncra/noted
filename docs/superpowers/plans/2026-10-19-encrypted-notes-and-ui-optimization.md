# Encrypted Notes & UI Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement password-protected notes using authenticated AES-256-GCM encryption with PBKDF2 key derivation, session-level memory caching, direct interactive unlock/lock buttons and modals in the TUI, zero-leak SQLite FTS5 privacy, and full responsive UI layout optimization.

**Architecture:** A standalone `noted.crypto` module provides AES-256-GCM authenticated encryption/decryption with PBKDF2-HMAC-SHA256. `Note` and `StorageManager` persist ciphertext in the note body while keeping metadata (including `title`, `encrypted: true`, `salt`, `nonce`) in YAML frontmatter. `NoteIndexer` suppresses plaintext body indexing for encrypted notes to guarantee privacy in SQLite. `NotedApp` manages an in-memory session cache of decrypted notes, renders a dedicated lock card with a prominent `[🔓 Mở khóa ghi chú]` button and header lock/unlock controls, while restructuring the metadata header into a 2-row layout and compacting toolbar glyphs.

**Tech Stack:** Python 3.10+, `cryptography` (AESGCM, PBKDF2HMAC, SHA256), `textual` (TUI widgets, ModalScreen, containers, styles), `typer`, `rich`, `pytest`.

**Spec:** [docs/superpowers/specs/2026-10-19-encrypted-notes-and-ui-optimization-design.md](file:///Users/musual/%28%20App%20%29%20Noted/docs/superpowers/specs/2026-10-19-encrypted-notes-and-ui-optimization-design.md)

## Global Constraints
- `cryptography>=42.0.0` added to `pyproject.toml` dependencies.
- Encryption algorithm: AES-256-GCM with 16-byte random salt, 12-byte random nonce, and 100,000 PBKDF2 rounds.
- YAML frontmatter preserves `title`, `date`, `tags`, and adds `encrypted: true`, `salt`, `nonce`.
- SQLite FTS5 index MUST NEVER contain decrypted body plaintext for encrypted notes.
- In-memory session cache (`unlocked_notes`) persists decrypted notes only during the running app process; cleared on quit.
- All existing 59 tests must continue to pass throughout and after implementation.

## Review Focus
1. **Wrong password / corrupted ciphertext**: Decryption must cleanly raise `InvalidPasswordOrCorruptedError` without crashing or returning truncated garbage.
2. **Vietnamese Unicode characters in encrypted notes**: Accented characters (e.g. `Tiếng Việt có dấu đầy đủ`, emoji `🔒`) must round-trip with NFC normalization without losing tones or formatting.
3. **Empty note body encryption**: Encrypting an empty note must succeed and not error on empty strings.
4. **Header layout under narrow terminals (<= 100 cols)**: Title, date, and tags must not be crushed down to width 1; toolbar must not overflow horizontally in split mode.
5. **Auto-save on encrypted notes**: Editing an unlocked encrypted note in TUI and triggering auto-save must encrypt the new body with the session password before writing to disk.

---

### Task 1: Cryptography Module (`noted.crypto`)

**Files:**
- Modify: `pyproject.toml`
- Create: `src/noted/crypto.py`
- Create: `tests/test_crypto.py`

**Interfaces:**
- Consumes: `cryptography.hazmat.primitives.ciphers.aead.AESGCM`, `cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC`, `cryptography.hazmat.primitives.hashes.SHA256`
- Produces:
  ```python
  class CryptoError(Exception): pass
  class InvalidPasswordOrCorruptedError(CryptoError): pass

  def derive_key(password: str, salt: bytes) -> bytes: ...
  def encrypt_body(plaintext: str, password: str) -> tuple[str, str, str]: ...
  def decrypt_body(ciphertext_b64: str, password: str, salt_hex: str, nonce_hex: str) -> str: ...
  ```

- [ ] **Step 1: Add `cryptography` dependency in `pyproject.toml` and sync environment**
Add `"cryptography>=42.0.0"` to `dependencies` in `pyproject.toml` and run `uv sync`.

- [ ] **Step 2: Write tests in `tests/test_crypto.py`**
Test round-trip encrypt/decrypt with plaintext and Vietnamese characters, invalid password raising `InvalidPasswordOrCorruptedError`, empty string handling, and corrupted ciphertext detection.

- [ ] **Step 3: Run test to verify it fails**
Run: `uv run pytest tests/test_crypto.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'noted.crypto')

- [ ] **Step 4: Implement `src/noted/crypto.py`**
Implement `derive_key`, `encrypt_body`, and `decrypt_body` using AES-256-GCM, 100,000 PBKDF2 rounds with SHA256, returning Base64 ciphertext and hex salt/nonce.

- [ ] **Step 5: Run tests to verify they pass**
Run: `uv run pytest tests/test_crypto.py -v`
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add pyproject.toml uv.lock src/noted/crypto.py tests/test_crypto.py
git commit -m "feat(crypto): add AES-256-GCM encryption module with PBKDF2"
```

---

### Task 2: Model & Storage Layer Encryption Integration

**Files:**
- Modify: `src/noted/models.py`
- Modify: `src/noted/frontmatter.py`
- Modify: `src/noted/storage.py`
- Modify: `tests/test_frontmatter.py`
- Modify: `tests/test_storage.py`

**Interfaces:**
- Consumes: `noted.crypto: encrypt_body, decrypt_body`
- Produces:
  - `Note.encrypted: bool = False`
  - `Note.salt: Optional[str] = None`
  - `Note.nonce: Optional[str] = None`
  - `NoteSummary.encrypted: bool = False`
  - `StorageManager.lock_note(note: Note, password: str) -> Path`
  - `StorageManager.unlock_note(note: Note, password: str) -> str`
  - `StorageManager.remove_lock(note: Note, password: str) -> Path`

- [ ] **Step 1: Write tests in `tests/test_frontmatter.py` and `tests/test_storage.py`**
Add tests asserting serialization and deserialization of notes with `encrypted: true`, `salt`, `nonce`, and testing `StorageManager.lock_note` and `StorageManager.unlock_note`.

- [ ] **Step 2: Run tests to verify failure**
Run: `uv run pytest tests/test_storage.py -k test_lock -v`
Expected: FAIL (AttributeError on lock_note)

- [ ] **Step 3: Update `src/noted/models.py` and `src/noted/frontmatter.py`**
Add `encrypted: bool = False`, `salt: Optional[str] = None`, `nonce: Optional[str] = None` to `Note` and `NoteSummary`. Serialize/deserialize these fields in YAML frontmatter.

- [ ] **Step 4: Implement storage encryption methods in `src/noted/storage.py`**
Implement `lock_note(self, note: Note, password: str) -> Path`, `unlock_note(self, note: Note, password: str) -> str`, and `remove_lock(self, note: Note, password: str) -> Path`.

- [ ] **Step 5: Run storage and frontmatter tests**
Run: `uv run pytest tests/test_frontmatter.py tests/test_storage.py -v`
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add src/noted/models.py src/noted/frontmatter.py src/noted/storage.py tests/test_frontmatter.py tests/test_storage.py
git commit -m "feat(storage): support encrypted note serialization and storage methods"
```

---

### Task 3: SQLite & Zero-Leak FTS5 Indexer

**Files:**
- Modify: `src/noted/db.py`
- Modify: `src/noted/indexer.py`
- Modify: `tests/test_indexer.py`

**Interfaces:**
- Consumes: `Note.encrypted`
- Produces:
  - `DatabaseManager`: adds `encrypted INTEGER DEFAULT 0` column to `notes` table with migration fallback.
  - `NoteIndexer.index_note`: indexes `[🔒 Encrypted note]` as body placeholder when `note.encrypted is True`.

- [ ] **Step 1: Write test in `tests/test_indexer.py`**
Test that when an encrypted note is indexed, searching for terms inside the plaintext body yields NO matches, while searching for title/tags yields the note with `summary.encrypted == True`.

- [ ] **Step 2: Run test to verify failure**
Run: `uv run pytest tests/test_indexer.py -k test_encrypted_indexing -v`
Expected: FAIL

- [ ] **Step 3: Update `src/noted/db.py` schema**
Ensure `notes` table includes `encrypted INTEGER DEFAULT 0`, and migrations add column if missing.

- [ ] **Step 4: Update `src/noted/indexer.py`**
When `note.encrypted is True`, replace indexed body with `"[🔒 Encrypted note]"`. Populate `NoteSummary.encrypted`.

- [ ] **Step 5: Run all indexer tests**
Run: `uv run pytest tests/test_indexer.py -v`
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add src/noted/db.py src/noted/indexer.py tests/test_indexer.py
git commit -m "feat(indexer): zero-leak FTS5 indexing for encrypted notes"
```

---

### Task 4: UI Optimization (Header 2-Row Layout, Compact Toolbar, Clean Footer)

**Files:**
- Modify: `src/noted/tui/styles.tcss`
- Modify: `src/noted/tui/widgets.py`
- Modify: `src/noted/tui/app.py`
- Modify: `tests/test_tui.py`

**Interfaces:**
- `MetadataHeader`: restructured into 2 vertical rows:
  - Top row: `#metadata-info` (Icon, Title, Date, Tags) spanning full width.
  - Bottom row: `#mode-button-group` (View, Edit, Split, Rename, Copy, Save, Lock).
- `#formatting-toolbar`: compact icon glyphs (`[ 𝐁 ]`, `[ 𝐼 ]`, `[</>]`, `[ H# ]`, `[ ☑ ]`, `[ ❝ ]`, `[ 💡 ]`, `[ 🎨 ]`).
- Footer: streamlined keybindings list.

- [ ] **Step 1: Write layout test in `tests/test_tui.py`**
Test that at terminal width 100x30, `#metadata-info` maintains width > 50 columns (not crushed to 1), and `#formatting-toolbar` total width <= 40 columns.

- [ ] **Step 2: Run test to verify failure**
Run: `uv run pytest tests/test_tui.py -k test_header_and_toolbar_dimensions -v`
Expected: FAIL (width=1 on current layout)

- [ ] **Step 3: Update `src/noted/tui/styles.tcss` and `src/noted/tui/widgets.py`**
Restructure `MetadataHeader` with `layout: vertical`, `height: 4`, top row `#metadata-info` taking full width, bottom row `#mode-button-group` taking height 1.
Update `formatting-toolbar` buttons to compact glyphs with `min-width: 5; padding: 0;`.
Make `#sidebar` width 32 with responsive bounds.

- [ ] **Step 4: Update Footer bindings in `src/noted/tui/app.py`**
Streamline `show=True` bindings to primary navigation keys.

- [ ] **Step 5: Run all TUI tests**
Run: `uv run pytest tests/test_tui.py -v`
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add src/noted/tui/styles.tcss src/noted/tui/widgets.py src/noted/tui/app.py tests/test_tui.py
git commit -m "refactor(ui): optimize metadata header layout, compact toolbar glyphs, and streamline footer"
```

---

### Task 5: Interactive Lock/Unlock Modals & Direct Screen Button

**Files:**
- Modify: `src/noted/tui/screens.py`
- Modify: `src/noted/tui/widgets.py`
- Modify: `src/noted/tui/app.py`
- Modify: `src/noted/tui/styles.tcss`
- Modify: `tests/test_tui.py`

**Interfaces:**
- `UnlockNoteModal(ModalScreen[Optional[str]])`
- `LockNoteModal(ModalScreen[Optional[str]])`
- `RemoveLockModal(ModalScreen[Optional[str]])`
- `#locked-note-card` with `Button("🔓 Mở khóa ghi chú", id="btn-screen-unlock")` inside `#view-container`
- `MetadataHeader` dynamic button `#btn-mode-lock`
- `NotedApp.unlocked_notes: dict[str, str]` (session memory cache)

- [ ] **Step 1: Write tests for lock/unlock modals and direct button click in `tests/test_tui.py`**
Add test: Create an encrypted note, mount app, verify `#locked-note-card` is displayed with `btn-screen-unlock`, click button, enter password in `UnlockNoteModal`, verify note is decrypted into viewer, and verify note remains unlocked when navigating away and back.

- [ ] **Step 2: Run test to verify failure**
Run: `uv run pytest tests/test_tui.py -k test_unlock_encrypted_note -v`
Expected: FAIL

- [ ] **Step 3: Implement `UnlockNoteModal` and `LockNoteModal` in `src/noted/tui/screens.py`**
Implement modals with password-masked `VietnameseInput(password=True)`, cancel on Escape, and submit on Enter.

- [ ] **Step 4: Add `#locked-note-card` and button handlers in `src/noted/tui/app.py` and `widgets.py`**
- In `compose`: add `#locked-note-card` containing message and `Button("🔓 Mở khóa ghi chú", id="btn-screen-unlock", variant="primary")`.
- Implement `action_unlock_note()`, `action_lock_note()`, `action_remove_lock()`.
- Add binding `Binding("u", "unlock_note", "Unlock", show=True)` and `Binding("ctrl+l", "lock_note", "Lock", show=False)`.
- Wire `btn-screen-unlock` and `btn-mode-lock` button presses.
- Manage `self.unlocked_notes` session dictionary and auto-save re-encryption.

- [ ] **Step 5: Run full test suite**
Run: `uv run pytest -v`
Expected: PASS (all tests pass)

- [ ] **Step 6: Commit**
```bash
git add src/noted/tui/screens.py src/noted/tui/widgets.py src/noted/tui/app.py src/noted/tui/styles.tcss tests/test_tui.py
git commit -m "feat(tui): add interactive lock/unlock modals, direct screen button, and session caching"
```

---

### Task 6: CLI Lock/Unlock & View Integration

**Files:**
- Modify: `src/noted/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- CLI command: `note lock <identifier>`
- CLI command: `note unlock <identifier>`
- CLI command: `note view <identifier>` (prompts for password if encrypted)

- [ ] **Step 1: Write CLI tests in `tests/test_cli.py`**
Test `note lock`, `note unlock`, and `note view` with encrypted notes using CliRunner inputs.

- [ ] **Step 2: Run test to verify failure**
Run: `uv run pytest tests/test_cli.py -k test_cli_lock -v`
Expected: FAIL

- [ ] **Step 3: Implement CLI lock, unlock, and view password prompt in `src/noted/cli.py`**
Add `@app.command(name="lock")` and `@app.command(name="unlock")`. Update `view_cmd` to prompt for password with `typer.prompt(hide_input=True)` when note is encrypted.

- [ ] **Step 4: Run full test suite and verify CLI**
Run: `uv run pytest -v`
Expected: PASS

- [ ] **Step 5: Commit and install executable**
```bash
git add src/noted/cli.py tests/test_cli.py
git commit -m "feat(cli): add note lock, unlock, and encrypted view commands"
uv tool install --force --editable .
```
