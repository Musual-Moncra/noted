# Architecture Specification: Password-Protected Notes & UI Optimization

- **Date:** 2026-10-19
- **Status:** Draft (Awaiting User Review)
- **Scope:** Architectural subsystem for AES-256-GCM encrypted notes, interactive unlock/lock modals and buttons, SQLite FTS5 privacy, session-level caching, and comprehensive TUI layout optimization.

---

## 1. Executive Summary & User Requirements

### 1.1 Requirements
1. **Title Visibility**: The note title remains visible in lists, headers, and searches so the user can easily locate their note.
2. **Body Confidentiality**: The body is encrypted on disk with a strong password. Without the password, no one reading the disk file can access the plaintext.
3. **Session-Level Unlocking**: Once unlocked with the correct password, the note remains decrypted in memory for the duration of the current app session. Switching between notes does not re-prompt for the password until the app is closed.
4. **Interactive Mouse & Keyboard Controls**:
   - A prominent, large clickable button `[🔓 Mở khóa ghi chú]` directly on the locked note reader screen.
   - Dynamic header buttons: `[🔒 Đặt mật khẩu]` (when unencrypted), `[🔓 Mở khóa]` (when locked), `[🔒 Khóa lại]` / `[🔓 Gỡ mật khẩu]` (when unlocked).
   - Centered popup modal `UnlockNoteModal` with masked password input (`••••••`).
   - Modal `LockNoteModal` with password confirmation.
5. **UI Optimization & Responsive Layout**:
   - Prevent the metadata header from crushing the note title/info down to width 1.
   - Shrink formatting toolbar buttons to compact glyphs (`[ 𝐁 ]`, `[ 𝐼 ]`, `[</>]`, `[ H# ]`, `[ ☑ ]`, `[ ❝ ]`, `[ 💡 ]`, `[ 🎨 ]`) so they fit cleanly in Split Screen mode without horizontal scrolling.
   - Streamline footer bindings to a single uncluttered line.

---

## 2. Cryptographic Architecture (`noted.crypto`)

### 2.1 Encryption Standard
- **Cipher**: **AES-256-GCM** (Galois/Counter Mode via `cryptography.hazmat.primitives.ciphers.aead.AESGCM`).
  - Provides authenticated encryption: any modification or corrupted password immediately raises an authentication error rather than outputting garbage text.
- **Key Derivation Function (KDF)**: **PBKDF2-HMAC-SHA256**
  - Iterations: `100,000` rounds.
  - Salt: Cryptographically secure 16-byte random salt generated via `os.urandom(16)`.
  - Nonce: 12-byte random nonce generated via `os.urandom(12)`.

### 2.2 API Signature (`src/noted/crypto.py`)
```python
def encrypt_body(plaintext: str, password: str) -> tuple[str, str, str]:
    """Encrypts plaintext using AES-256-GCM and PBKDF2.
    
    Returns (ciphertext_b64, salt_hex, nonce_hex).
    """

def decrypt_body(ciphertext_b64: str, password: str, salt_hex: str, nonce_hex: str) -> str:
    """Decrypts ciphertext using AES-256-GCM and PBKDF2.
    
    Raises InvalidPasswordOrCorruptedError on mismatch or tampering.
    """
```

---

## 3. Storage Layer & Zero-Leak FTS5 Indexing

### 3.1 YAML Frontmatter Format
When encrypted, the note's frontmatter reflects encryption metadata while preserving standard fields:
```markdown
---
id: "20261019-181500-abcd"
title: "Personal Banking & Passwords"
date: "2026-10-19T18:15:00"
type: "note"
tags:
  - finance
  - secure
encrypted: true
salt: "a1b2c3d4e5f6..."
nonce: "1234567890ab..."
---

aW5pdGlhbC1jaXBoZXJ0ZXh0LWJhc2U2NC1kYXRh...
```

### 3.2 SQLite Database & FTS5 Privacy
In `NoteIndexer`:
- If `note.encrypted is True`:
  - `title`, `tags`, `note_type`, `date` are indexed in SQLite metadata and FTS5.
  - **The plaintext body is NEVER written to `index.db`**. The indexed body text is stored as a constant marker: `"[🔒 Encrypted note]"`.
  - Full-text search on secret terms will not return results from the unindexed database, preventing leakage of sensitive content to disk logs or unencrypted SQLite files.

---

## 4. TUI Interaction & Screen Design

### 4.1 Session Cache
`NotedApp` maintains an in-memory dictionary:
```python
self.unlocked_notes: dict[str, str] = {}  # note_id -> decrypted_plaintext
```
- When a note is unlocked: `self.unlocked_notes[note.id] = decrypted_body`.
- When reading `self.current_note.body`: if `note.encrypted` and `note.id in self.unlocked_notes`, the decrypted content is used.
- When saving: if `note.encrypted`, the editor text is encrypted using the active session password before writing to disk.
- When quitting the app: memory is freed, zero plaintext is retained.

### 4.2 Locked View Container & Direct Click Button
In `src/noted/tui/app.py`:
Inside `#view-container`:
- If `note.encrypted` and `note.id not in self.unlocked_notes`:
  - Show `#locked-note-card` with an aesthetic bordered panel:
    - Lock Icon and Message: `🔒 Ghi chú này đã được mã hóa bảo vệ (AES-256)`.
    - Subtext: `Nhấp vào nút bên dưới hoặc nhấn phím 'u' để mở khóa xem nội dung.`
    - Direct Interactive Button: `Button("🔓 Mở khóa ghi chú", id="btn-screen-unlock", variant="primary")`.
  - `#markdown-viewer` is hidden.
- If unlocked or not encrypted:
  - `#locked-note-card` is hidden, `#markdown-viewer` is visible.

### 4.3 Modals
1. **`UnlockNoteModal`**:
   - Centered dialog with Title: `🔓 Mở khóa ghi chú: {title}`.
   - Input: `VietnameseInput(password=True, placeholder="Nhập mật khẩu...", id="input-unlock-password")`.
   - Buttons: `Cancel` and `Mở khóa`.
   - Enter key submits immediately.
2. **`LockNoteModal`**:
   - Title: `🔒 Đặt mật khẩu bảo vệ ghi chú`.
   - Input 1: `Mật khẩu mới` (password=True).
   - Input 2: `Xác nhận mật khẩu` (password=True).
   - Validation: passwords match, non-empty.
3. **`RemoveLockModal`**:
   - Asks for current password to decrypt and permanently store as unencrypted markdown.

---

## 5. UI Optimization Architecture

### 5.1 Metadata Header Redesign
Separate metadata information and action controls:
- **Row 1 (`#metadata-info`)**: Displays Note icon (`📓` / `📝` / `🔒`), Title (`[bold white]`), Date, and Tag badges.
  - Takes 100% width or dedicated line; never crushed or truncated by buttons.
- **Row 2 (`#mode-button-group`)**:
  - Mode segmented controls: `[👁 Xem]`, `[📝 Soạn]`, `[◫ Song song]`.
  - Quick action buttons: `[✏ Đổi tên]`, `[📋 Copy]`, `[🔒 Khóa / 🔓 Mở khóa]`, `[💾 Lưu]`.
  - Height adjusted to 4 rows so information and buttons breathe cleanly.

### 5.2 Formatting Toolbar Compact Glyphs
Replace long button labels with compact icon glyphs:
- `[ 𝐁 ]`, `[ 𝐼 ]`, `[</>]`, `[ H# ]`, `[ ☑ ]`, `[ ❝ ]`, `[ 💡 ]`, `[ 🎨 ]`.
- Reduces width from 94 columns to ~35 columns.
- Eliminates horizontal overflow in Split Screen and Edit modes.

### 5.3 Footer Optimization
Retain primary shortcuts on the footer:
`q: Quit | n: New | j: Today | e: Edit/View | ^w: Split | r: Rename | c: Copy | u: Unlock | d: Delete | /: Search | ?: Help`
All other keys remain fully functional and documented in `HelpModal`.

---

## 6. CLI Commands

1. **`note lock <identifier>`**:
   Prompts for password securely with confirmation via `typer.prompt(hide_input=True)`.
2. **`note unlock <identifier>`**:
   Prompts for password and decrypts the note back to normal plaintext markdown.
3. **`note view <identifier>`**:
   If note is encrypted, prompts for password:
   `Enter password: ••••••••`
   Renders decrypted markdown in terminal if password matches.

---

## 7. Verification & Testing Strategy
- Unit tests in `tests/test_crypto.py`:
  - Round-trip encrypt/decrypt.
  - Tamper detection (modified ciphertext or wrong password raises error).
  - Empty string and Unicode/Vietnamese content encryption.
- Integration tests in `tests/test_storage.py`:
  - Saving and reading encrypted note files.
- Indexer tests in `tests/test_indexer.py`:
  - Verify plaintext body does not leak into SQLite index.
- TUI tests in `tests/test_tui.py`:
  - Locked card rendering and direct button click.
  - `UnlockNoteModal` password entry and successful decryption.
  - Header responsiveness without title crushing.
- CLI tests in `tests/test_cli.py`:
  - `note lock` and `note view` with mock password.
