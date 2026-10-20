import os
import json
import re
import sqlite3
from pathlib import Path
from noted.db import DatabaseManager
from noted.models import Note, NoteSummary, SearchResult, normalize_tags
from noted.storage import StorageManager


class NoteIndexer:
    def __init__(self, db: DatabaseManager, storage: StorageManager):
        self.db, self.storage = db, storage
        self.sync_errors: list[str] = []

    def _index(self, conn, note: Note) -> None:
        existing = conn.execute("SELECT filepath FROM notes WHERE id=?", (note.id,)).fetchone()
        if existing and Path(existing['filepath']) != note.filepath.resolve() and Path(existing['filepath']).exists():
            raise ValueError("Duplicate note ID in different files.")
        folder = str(note.filepath.parent.resolve())
        tags = normalize_tags(note.tags)
        body = "[🔒 Encrypted note]" if note.encrypted else note.body
        excerpt = "Locked note" if note.encrypted else " ".join(note.body[:512].split())[:120]
        conn.execute("""INSERT INTO notes
            (id, filepath, title, date, type, tags, mtime_ns, size_bytes, encrypted, pinned, archived, folder, excerpt)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            filepath=excluded.filepath, title=excluded.title, date=excluded.date, type=excluded.type,
            tags=excluded.tags, mtime_ns=excluded.mtime_ns, size_bytes=excluded.size_bytes,
            encrypted=excluded.encrypted, pinned=excluded.pinned, archived=excluded.archived,
            folder=excluded.folder, excerpt=excluded.excerpt""",
            (note.id, str(note.filepath.resolve()), note.title, note.date, note.note_type,
             json.dumps(tags), note.mtime_ns, note.size_bytes, int(note.encrypted),
             int(note.pinned), int(note.archived), folder, excerpt))
        conn.execute("DELETE FROM note_tags WHERE note_id=?", (note.id,))
        conn.executemany("INSERT INTO note_tags VALUES (?,?)", ((note.id, t) for t in tags))
        conn.execute("DELETE FROM notes_fts WHERE id=?", (note.id,))
        conn.execute("INSERT INTO notes_fts(id,title,body,tags) VALUES (?,?,?,?)",
                     (note.id, note.title, body, " ".join(tags)))

    def index_note(self, note: Note) -> None:
        if note.filepath and note.filepath.is_file():
            with self.db.get_connection() as conn:
                self._index(conn, note)

    @staticmethod
    def _remove(conn, note_id):
        conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        conn.execute("DELETE FROM notes_fts WHERE id=?", (note_id,))

    def remove_note(self, note_id: str) -> None:
        with self.db.get_connection() as conn:
            self._remove(conn, note_id)

    def sync_all(self, *, cancelled=None) -> int:
        """Stream filesystem entries; keep at most one body and 200 records resident."""
        updated = 0
        self.sync_errors = []
        with self.db.get_connection() as conn:
            for path in self.storage.iter_note_files():
                if cancelled is not None and cancelled():
                    return updated
                try:
                    stat = path.stat()
                    row = conn.execute("SELECT mtime_ns,size_bytes,folder FROM notes WHERE filepath=?",
                                       (str(path.resolve()),)).fetchone()
                    if row is None or row['mtime_ns'] != stat.st_mtime_ns or row['size_bytes'] != stat.st_size or not row['folder']:
                        self._index(conn, self.storage.read_note(path))
                        updated += 1
                        if updated % 200 == 0:
                            conn.commit()
                except (OSError, ValueError, sqlite3.Error) as exc:
                    # Bound diagnostics too; never include note contents.
                    if len(self.sync_errors) < 20:
                        self.sync_errors.append(f"{path.name}: {type(exc).__name__}")
            cursor = conn.execute("SELECT id,filepath FROM notes")
            while rows := cursor.fetchmany(200):
                if cancelled is not None and cancelled():
                    return updated
                for row in rows:
                    path = Path(row['filepath'])
                    if not path.is_file() or path.is_symlink():
                        self._remove(conn, row['id'])
                conn.commit()
        return updated

    @staticmethod
    def sanitize_fts_query(query: str) -> str:
        return " ".join(f'"{token}"*' for token in re.findall(r"\w+", query))

    @staticmethod
    def _summary(row) -> NoteSummary:
        return NoteSummary(id=row['id'], title=row['title'], date=row['date'],
                           note_type=row['type'], tags=json.loads(row['tags']),
                           filepath=Path(row['filepath']), encrypted=bool(row['encrypted']),
                           pinned=bool(row['pinned']), archived=bool(row['archived']),
                           excerpt=('Locked note' if row['encrypted'] else row['search_excerpt'] or row['excerpt']) if 'search_excerpt' in row.keys() else row['excerpt'], mtime_ns=row['mtime_ns'])

    def _where(self, *, tag=None, tags=None, note_type=None, folder=None,
               recursive=True, archived=False, pinned=False, query=""):
        conditions, params = ["n.archived=?"], [int(archived)]
        if pinned:
            conditions.append("n.pinned=1")
        if note_type:
            conditions.append("n.type=?")
            params.append(note_type)
        for value in normalize_tags(([tag] if tag else []) + (tags or [])):
            conditions.append("EXISTS (SELECT 1 FROM note_tags t WHERE t.note_id=n.id AND t.tag=?)")
            params.append(value)
        if folder is not None:
            parent = str(self.storage.folder_path(folder))
            conditions.append("(n.folder=? OR substr(n.folder,1,?)=?)" if recursive else "n.folder=?")
            params.extend([parent, len(parent + os.sep), parent + os.sep] if recursive else [parent])
        if query:
            fts = self.sanitize_fts_query(query)
            conditions.append("n.id IN (SELECT id FROM notes_fts WHERE notes_fts MATCH ?)")
            params.append(fts or '""')
        return " AND ".join(conditions), params

    def list_notes(self, tag=None, note_type=None, limit=50, *, offset=0, tags=None,
                   folder=None, recursive=True, archived=False, pinned=False,
                   query="", sort="updated") -> list[NoteSummary]:
        where, params = self._where(tag=tag, tags=tags, note_type=note_type, folder=folder,
                                    recursive=recursive, archived=archived, pinned=pinned, query="")
        order = {"updated": "n.mtime_ns DESC", "created": "n.date DESC", "title": "n.title COLLATE NOCASE"}.get(sort, "n.mtime_ns DESC")
        params.extend([max(1, min(limit, 1000)), max(0, offset)])
        if query:
            sql = f"""SELECT n.*, substr(snippet(notes_fts,2,'[[HIGHLIGHT]]','[[/HIGHLIGHT]]','…',12),1,200) AS search_excerpt
                      FROM notes_fts JOIN notes n ON n.id=notes_fts.id
                      WHERE notes_fts MATCH ? AND {where} ORDER BY bm25(notes_fts),n.id LIMIT ? OFFSET ?"""
            params.insert(0, self.sanitize_fts_query(query) or '""')
        else:
            sql = f"SELECT n.* FROM notes n WHERE {where} ORDER BY n.pinned DESC,{order},n.id LIMIT ? OFFSET ?"
        with self.db.get_connection() as conn:
            return [self._summary(row) for row in conn.execute(sql, params)]

    def count_notes(self, **filters) -> int:
        where, params = self._where(**filters)
        with self.db.get_connection() as conn:
            return conn.execute(f"SELECT count(*) FROM notes n WHERE {where}", params).fetchone()[0]

    def list_tags(self, *, query="", limit=100, offset=0) -> list[tuple[str, int]]:
        with self.db.get_connection() as conn:
            return [(r[0], r[1]) for r in conn.execute("""SELECT t.tag,count(*) FROM note_tags t
                JOIN notes n ON n.id=t.note_id WHERE n.archived=0 AND instr(t.tag,?)>0
                GROUP BY t.tag ORDER BY t.tag LIMIT ? OFFSET ?""", (query.lower(), limit, offset))]

    def search(self, query: str, limit=20, **filters) -> list[SearchResult]:
        if not self.sanitize_fts_query(query):
            return []
        notes = self.list_notes(query=query, limit=limit, **filters)
        return [SearchResult(n, "[🔒 Encrypted note]" if n.encrypted else n.excerpt or f"Matched in {n.title}") for n in notes]

    def get_note_by_id_or_date(self, identifier: str) -> Note | None:
        """Finds a note by exact ID or journal date (YYYY-MM-DD), returning the loaded Note."""
        ident = identifier.strip()
        with self.db.get_connection() as conn:
            # 1. Exact ID match (highest priority)
            row = conn.execute(
                "SELECT filepath FROM notes WHERE id = ? LIMIT 1;",
                (ident,),
            ).fetchone()

            # 2. Journal date match (e.g. 2026-10-19)
            if not row:
                row = conn.execute(
                    "SELECT filepath FROM notes WHERE type = 'journal' AND date = ? LIMIT 1;",
                    (ident,),
                ).fetchone()

            # 3. Title, slug, date prefix or path match
            if not row:
                from noted.frontmatter import slugify
                slug_ident = slugify(ident)
                row = conn.execute(
                    """
                    SELECT filepath FROM notes
                    WHERE title LIKE ? OR date LIKE ? OR filepath LIKE ? OR filepath LIKE ?
                    LIMIT 1;
                    """,
                    (f"%{ident}%", f"{ident}%", f"%{ident}%", f"%{slug_ident}%"),
                ).fetchone()

            if row:
                p = Path(row["filepath"])
                if p.is_file():
                    return self.storage.read_note(p)

        # Fallback to direct disk inspection if database hasn't synced yet
        journal_p = self.storage.get_journal_path(ident)
        if journal_p.is_file():
            return self.storage.read_note(journal_p)

        for p in self.storage.iter_note_files():
            if ident in p.name:
                return self.storage.read_note(p)

        return None
