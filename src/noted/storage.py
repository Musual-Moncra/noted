import os
import tempfile
import unicodedata
from datetime import date, datetime
from pathlib import Path
from noted.config import Config
from noted.crypto import encrypt_body, decrypt_body
from noted.frontmatter import (
    generate_note_id,
    parse_frontmatter,
    serialize_note,
    slugify,
)
from noted.models import Note

class StorageManager:
    """Manages filesystem persistence and retrieval of Markdown notes and journals."""

    def __init__(self, config: Config):
        self.config = config
        self.config.ensure_directories()

    def get_journal_path(self, date_str: str) -> Path:
        return self.config.journal_subdir / f"{date_str}.md"

    def get_note_path(self, note_id: str, slug: str) -> Path:
        return self.config.notes_subdir / f"{note_id}-{slug}.md"

    def save_note(self, note: Note) -> Path:
        """Atomically saves a note to disk."""
        if note.filepath is None:
            if note.note_type == "journal":
                note.filepath = self.get_journal_path(note.id)
            else:
                slug = slugify(note.title)
                note.filepath = self.get_note_path(note.id, slug)

        target_path = note.filepath
        target_path.parent.mkdir(parents=True, exist_ok=True)

        content = serialize_note(note.to_metadata(), note.body)

        # Atomic file write using a temporary file in the same directory
        temp_dir = target_path.parent
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=temp_dir, delete=False) as tf:
            tf.write(content)
            temp_path = Path(tf.name)

        os.replace(temp_path, target_path)
        note.mtime_ns = target_path.stat().st_mtime_ns
        return target_path

    def rename_note(self, note: Note, new_title: str) -> Path:
        """Renames a note, updates its slug and filename on disk, and saves changes."""
        clean_title = unicodedata.normalize("NFC", new_title.strip())
        if not clean_title:
            clean_title = "Untitled Note"

        old_filepath = note.filepath
        note.title = clean_title

        if note.note_type != "journal":
            new_slug = slugify(note.title)
            new_filepath = self.get_note_path(note.id, new_slug)
            if old_filepath and old_filepath != new_filepath and old_filepath.exists():
                try:
                    old_filepath.unlink(missing_ok=True)
                except Exception:
                    pass
            note.filepath = new_filepath

        return self.save_note(note)

    def read_note(self, filepath: Path) -> Note:
        """Reads a note from disk and parses its frontmatter and body."""
        content = filepath.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(content)
        mtime_ns = filepath.stat().st_mtime_ns

        # Handle missing or corrupted frontmatter with smart defaults
        filename = filepath.stem
        is_journal = filepath.parent == self.config.journal_subdir

        note_id = str(metadata.get("id") or filename.split("-")[0])
        note_type = str(metadata.get("type") or ("journal" if is_journal else "note"))
        title = str(metadata.get("title") or filename.replace("-", " ").title())
        date_str = str(
            metadata.get("date")
            or datetime.fromtimestamp(mtime_ns / 1e9).isoformat()
        )
        tags_raw = metadata.get("tags")
        if isinstance(tags_raw, list):
            tags = [str(t) for t in tags_raw]
        elif isinstance(tags_raw, str):
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        else:
            tags = ["journal"] if is_journal else []

        encrypted = bool(metadata.get("encrypted", False))
        salt = metadata.get("salt")
        nonce = metadata.get("nonce")

        return Note(
            id=note_id,
            title=title,
            date=date_str,
            note_type=note_type,
            tags=tags,
            body=body,
            filepath=filepath,
            mtime_ns=mtime_ns,
            encrypted=encrypted,
            salt=str(salt) if salt else None,
            nonce=str(nonce) if nonce else None,
        )

    def lock_note(self, note: Note, password: str) -> Path:
        """Encrypts note body with password and saves to disk."""
        ciphertext_b64, salt_hex, nonce_hex = encrypt_body(note.body, password)
        note.body = ciphertext_b64
        note.encrypted = True
        note.salt = salt_hex
        note.nonce = nonce_hex
        return self.save_note(note)

    def unlock_note(self, note: Note, password: str) -> str:
        """Decrypts note body in-memory and returns decrypted plaintext without writing to disk."""
        if not note.encrypted or not note.salt or not note.nonce:
            return note.body
        return decrypt_body(note.body, password, note.salt, note.nonce)

    def remove_lock(self, note: Note, password: str) -> Path:
        """Decrypts note body and permanently saves as unencrypted markdown."""
        decrypted = self.unlock_note(note, password)
        note.body = decrypted
        note.encrypted = False
        note.salt = None
        note.nonce = None
        return self.save_note(note)


    def create_note(
        self,
        title: str,
        body: str = "",
        tags: list[str] | None = None,
        note_id: str | None = None,
    ) -> Note:
        """Creates and saves a new standalone note."""
        nid = note_id or generate_note_id()
        now_iso = datetime.now().isoformat(timespec="seconds")
        note = Note(
            id=nid,
            title=title.strip() if title else "Untitled Note",
            date=now_iso,
            note_type="note",
            tags=tags or [],
            body=body,
        )
        self.save_note(note)
        return note

    def get_or_create_today_journal(self, today_str: str | None = None) -> Note:
        """Retrieves or initializes today's daily journal entry."""
        today = today_str or date.today().isoformat()
        journal_path = self.get_journal_path(today)
        if journal_path.is_file():
            return self.read_note(journal_path)

        note = Note(
            id=today,
            title=f"Daily Journal - {today}",
            date=today,
            note_type="journal",
            tags=["journal"],
            body=self.config.journal_template,
            filepath=journal_path,
        )
        self.save_note(note)
        return note

    def delete_note(self, filepath: Path) -> bool:
        """Deletes a note file from disk."""
        if filepath and filepath.is_file():
            filepath.unlink()
            return True
        return False

    def list_note_files(self) -> list[Path]:
        """Lists all markdown files across the notes and journal directories."""
        files: list[Path] = []
        if self.config.notes_subdir.is_dir():
            files.extend(sorted(self.config.notes_subdir.glob("*.md")))
        if self.config.journal_subdir.is_dir():
            files.extend(sorted(self.config.journal_subdir.glob("*.md")))
        return files
