import hashlib
import os
import tempfile
import unicodedata
from datetime import date, datetime
from dataclasses import replace
from collections.abc import Iterator
from pathlib import Path
from noted.config import Config
from noted.crypto import encrypt_body, decrypt_body
from noted.frontmatter import (
    generate_note_id,
    parse_frontmatter,
    serialize_note,
    slugify,
)
from noted.models import Note, normalize_tags

class ExternalChangeError(OSError):
    """The file changed since this model was loaded."""


class StorageManager:
    """Manages filesystem persistence and retrieval of Markdown notes and journals."""

    def __init__(self, config: Config):
        self.config = config
        self.config.ensure_directories()

    def get_journal_path(self, date_str: str) -> Path:
        return self.config.journal_subdir / f"{date_str}.md"

    def get_note_path(self, note_id: str, slug: str) -> Path:
        return self.config.notes_subdir / f"{note_id}-{slug}.md"

    def _check_version(self, note: Note) -> None:
        if note.filepath and note.mtime_ns:
            if not note.filepath.exists():
                raise ExternalChangeError("The note was removed or moved outside Noted.")
            stat = note.filepath.stat()
            if stat.st_mtime_ns != note.mtime_ns or (note.size_bytes and stat.st_size != note.size_bytes):
                raise ExternalChangeError("The note changed outside Noted.")

    def save_note(self, note: Note, *, force: bool = False) -> Path:
        """Replace atomically, preserving the old file if writing fails."""
        if note.filepath is None:
            note.filepath = (self.get_journal_path(note.id) if note.note_type == "journal"
                             else self.get_note_path(note.id, slugify(note.title)))
        if not force:
            self._check_version(note)
        target = note.filepath
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as stream:
                temp = Path(stream.name)
                stream.write(serialize_note(note.to_metadata(), note.body))
            if not force:
                self._check_version(note)
            os.replace(temp, target)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        stat = target.stat()
        note.mtime_ns, note.size_bytes = stat.st_mtime_ns, stat.st_size
        note.tags = normalize_tags(note.tags)
        note.has_stored_id = True
        return target

    def rename_note(self, note: Note, new_title: str) -> Path:
        self._check_version(note)
        title = unicodedata.normalize("NFC", new_title.strip()) or "Untitled Note"
        old = note.filepath
        target = old if note.note_type == "journal" else old.with_name(f"{note.id}-{slugify(title)}.md")
        if target != old and target.exists():
            raise FileExistsError("A note already exists at that path.")
        candidate = replace(note, title=title, filepath=target,
                            mtime_ns=note.mtime_ns if target == old else 0)
        self.save_note(candidate)
        try:
            if target != old:
                self._check_version(note)
                old.unlink()
        except OSError:
            if target != old:
                target.unlink(missing_ok=True)
            raise
        note.__dict__.update(candidate.__dict__)
        return target

    def folder_path(self, folder: str | Path) -> Path:
        """Validate every path component before resolving symlinks."""
        root = self.config.notes_subdir.resolve()
        raw = Path(folder)
        if not raw.is_absolute():
            raw = root / raw
        try:
            parts = raw.relative_to(root).parts
        except ValueError:
            raise ValueError("Choose a folder inside notes/.") from None
        for part in parts:
            if part in {".", ".."} or any(c in part for c in '<>:"|?*\\') or part.endswith((".", " ")):
                raise ValueError("Invalid folder name.")
        current = root
        for part in parts:
            current /= part
            if current.is_symlink():
                raise ValueError("Symlink folders are not supported.")
        if not raw.resolve().is_relative_to(root):
            raise ValueError("Choose a folder inside notes/.")
        return raw

    def create_folder(self, folder: str | Path) -> Path:
        path = self.folder_path(folder)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def move_folder(self, source: Path, destination: Path) -> Path:
        source, destination = self.folder_path(source), self.folder_path(destination)
        if source == self.config.notes_subdir.resolve() or destination.is_relative_to(source):
            raise ValueError("Cannot move a folder into itself.")
        if destination.exists():
            raise FileExistsError("The destination already exists.")
        if not destination.parent.is_dir():
            raise ValueError("Choose an existing destination parent.")
        source.rename(destination)
        return destination

    def delete_folder(self, folder: Path) -> None:
        path = self.folder_path(folder)
        if path == self.config.notes_subdir.resolve():
            raise ValueError("Cannot delete the notes root.")
        path.rmdir()

    def move_note(self, note: Note, folder: str | Path) -> Path:
        self._check_version(note)
        if note.note_type == "journal":
            raise ValueError("Journals remain in journal/.")
        destination = self.folder_path(folder)
        if not destination.is_dir():
            raise ValueError("Choose an existing folder.")
        target = destination / note.filepath.name
        if target == note.filepath:
            return target
        if target.exists():
            raise FileExistsError("A note already exists at that path.")
        if not note.has_stored_id:
            self.save_note(note)
        note.filepath.rename(target)
        note.filepath = target
        return target

    def find_folders(self, query: str, limit: int = 30) -> list[Path]:
        root = self.config.notes_subdir.resolve()
        matches = []
        for directory, dirs, _ in os.walk(root, followlinks=False):
            dirs[:] = sorted(name for name in dirs if not (Path(directory) / name).is_symlink())
            for name in dirs:
                path = Path(directory) / name
                if query.casefold() in str(path.relative_to(root)).casefold():
                    matches.append(path)
                    if len(matches) >= limit:
                        return matches
        return matches

    def child_folders(self, folder: str | Path = "") -> list[Path]:
        path = self.folder_path(folder)
        return sorted((p for p in path.iterdir() if p.is_dir() and not p.is_symlink()),
                      key=lambda p: p.name.casefold())

    def read_note(self, filepath: Path) -> Note:
        """Reads a note from disk and parses its frontmatter and body."""
        for _ in range(3):
            before = filepath.stat()
            content = filepath.read_text(encoding="utf-8")
            stat = filepath.stat()
            version = lambda item: (item.st_dev, item.st_ino, item.st_mtime_ns, item.st_size)
            if version(before) == version(stat):
                break
        else:
            raise ExternalChangeError("The note is changing; retry after the external editor finishes.")
        metadata, body = parse_frontmatter(content)
        mtime_ns = stat.st_mtime_ns

        # Handle missing or corrupted frontmatter with smart defaults
        filename = filepath.stem
        is_journal = filepath.parent.resolve() == self.config.journal_subdir.resolve()
        identity_path = filepath.resolve()
        if identity_path.is_relative_to(self.config.notes_dir.resolve()):
            identity_path = identity_path.relative_to(self.config.notes_dir.resolve())
        fallback_id = filename if is_journal else 'file-' + hashlib.blake2b(str(identity_path).encode(), digest_size=8).hexdigest()
        note_id = str(metadata.get("id") or fallback_id)
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
            tags=normalize_tags(tags),
            body=body,
            filepath=filepath,
            mtime_ns=mtime_ns,
            encrypted=encrypted,
            salt=str(salt) if salt else None,
            nonce=str(nonce) if nonce else None,
            pinned=bool(metadata.get("pinned", False)),
            archived=bool(metadata.get("archived", False)),
            size_bytes=stat.st_size,
            has_stored_id=bool(metadata.get("id")),
            extra_metadata={k: v for k, v in metadata.items() if k not in {
                "id", "title", "date", "type", "tags", "encrypted", "salt", "nonce", "pinned", "archived"}},
        )

    def lock_note(self, note: Note, password: str) -> Path:
        """Encrypts note body with password and saves to disk."""
        ciphertext_b64, salt_hex, nonce_hex = encrypt_body(note.body, password)
        candidate = replace(note, body=ciphertext_b64, encrypted=True, salt=salt_hex, nonce=nonce_hex)
        path = self.save_note(candidate)
        note.__dict__.update(candidate.__dict__)
        return path

    def unlock_note(self, note: Note, password: str) -> str:
        """Decrypts note body in-memory and returns decrypted plaintext without writing to disk."""
        if not note.encrypted or not note.salt or not note.nonce:
            return note.body
        return decrypt_body(note.body, password, note.salt, note.nonce)

    def remove_lock(self, note: Note, password: str) -> Path:
        """Decrypts note body and permanently saves as unencrypted markdown."""
        decrypted = self.unlock_note(note, password)
        candidate = replace(note, body=decrypted, encrypted=False, salt=None, nonce=None)
        path = self.save_note(candidate)
        note.__dict__.update(candidate.__dict__)
        return path

    def change_password(self, note: Note, old_password: str, new_password: str) -> Path:
        """Verifies old password, decrypts, and re-encrypts note body with new password and fresh salt/nonce."""
        decrypted = self.unlock_note(note, old_password)
        candidate = replace(note, body=decrypted)
        path = self.lock_note(candidate, new_password)
        note.__dict__.update(candidate.__dict__)
        return path


    def create_note(
        self,
        title: str,
        body: str = "",
        tags: list[str] | None = None,
        note_id: str | None = None,
        folder: str | Path | None = None,
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
        if folder is not None:
            parent = self.folder_path(folder)
            if not parent.is_dir():
                raise ValueError("Choose an existing folder.")
            note.filepath = parent / f"{nid}-{slugify(note.title)}.md"
        if note.filepath is not None and note.filepath.exists():
            raise FileExistsError("A note already exists at that path.")
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

    def iter_note_files(self) -> Iterator[Path]:
        for root in (self.config.notes_subdir, self.config.journal_subdir):
            for directory, dirs, filenames in os.walk(root, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
                for name in filenames:
                    path = Path(directory) / name
                    if name.endswith(".md") and not path.is_symlink():
                        yield path

    def list_note_files(self) -> list[Path]:
        return list(self.iter_note_files())
