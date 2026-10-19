import json
import re
from pathlib import Path
from typing import Any
from noted.db import DatabaseManager
from noted.models import Note, NoteSummary, SearchResult
from noted.storage import StorageManager

class NoteIndexer:
    """Indexes notes into SQLite3 and provides FTS5 full-text search & tag queries."""

    def __init__(self, db: DatabaseManager, storage: StorageManager):
        self.db = db
        self.storage = storage

    def index_note(self, note: Note) -> None:
        """Indexes or updates a single note in SQLite and FTS5."""
        if not note.filepath or not note.filepath.is_file():
            return

        mtime_ns = note.filepath.stat().st_mtime_ns
        size_bytes = note.filepath.stat().st_size
        tags_json = json.dumps(note.tags)
        tags_str = " ".join(note.tags)

        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO notes (id, filepath, title, date, type, tags, mtime_ns, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    filepath = excluded.filepath,
                    title = excluded.title,
                    date = excluded.date,
                    type = excluded.type,
                    tags = excluded.tags,
                    mtime_ns = excluded.mtime_ns,
                    size_bytes = excluded.size_bytes;
                """,
                (
                    note.id,
                    str(note.filepath.resolve()),
                    note.title,
                    note.date,
                    note.note_type,
                    tags_json,
                    mtime_ns,
                    size_bytes,
                ),
            )

            # Update tags
            conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note.id,))
            for tag in note.tags:
                conn.execute(
                    "INSERT OR IGNORE INTO note_tags (note_id, tag) VALUES (?, ?)",
                    (note.id, tag.strip().lower()),
                )

            # Update FTS5 virtual table
            conn.execute("DELETE FROM notes_fts WHERE id = ?", (note.id,))
            conn.execute(
                "INSERT INTO notes_fts (id, title, body, tags) VALUES (?, ?, ?, ?)",
                (note.id, note.title, note.body, tags_str),
            )

    def remove_note(self, note_id: str) -> None:
        """Removes a note from the index."""
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
            conn.execute("DELETE FROM notes_fts WHERE id = ?", (note_id,))

    def sync_all(self) -> int:
        """Reconciles filesystem notes with SQLite database incrementally.
        
        Returns the count of notes updated or added.
        """
        disk_files = {p.resolve(): p for p in self.storage.list_note_files()}
        updated_count = 0

        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT id, filepath, mtime_ns FROM notes").fetchall()
            db_records = {Path(row["filepath"]).resolve(): (row["id"], row["mtime_ns"]) for row in rows}

        # 1. Prune deleted files
        for db_path, (nid, _) in db_records.items():
            if db_path not in disk_files:
                self.remove_note(nid)

        # 2. Add or update changed files
        for disk_path, p in disk_files.items():
            st = p.stat()
            current_mtime = st.st_mtime_ns
            if disk_path not in db_records or db_records[disk_path][1] != current_mtime:
                note = self.storage.read_note(p)
                self.index_note(note)
                updated_count += 1

        return updated_count

    @staticmethod
    def sanitize_fts_query(query: str) -> str:
        """Sanitizes user input for SQLite FTS5 query syntax."""
        tokens = re.findall(r"\w+", query)
        if not tokens:
            return ""
        # Prefix match each token safely
        return " ".join(f'"{token}"*' for token in tokens)

    def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        """Performs full-text search across titles, bodies, and tags."""
        fts_query = self.sanitize_fts_query(query)
        if not fts_query:
            return []

        results: list[SearchResult] = []
        with self.db.get_connection() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT fts.id,
                           snippet(notes_fts, 2, '[[HIGHLIGHT]]', '[[/HIGHLIGHT]]', '...', 15) as snip,
                           n.filepath, n.title, n.date, n.type, n.tags
                    FROM notes_fts fts
                    JOIN notes n ON n.id = fts.id
                    WHERE notes_fts MATCH ?
                    ORDER BY bm25(notes_fts)
                    LIMIT ?;
                    """,
                    (fts_query, limit),
                ).fetchall()

                for row in rows:
                    tags = json.loads(row["tags"]) if row["tags"] else []
                    summary = NoteSummary(
                        id=row["id"],
                        title=row["title"],
                        date=row["date"],
                        note_type=row["type"],
                        tags=tags,
                        filepath=Path(row["filepath"]),
                    )
                    raw_snippet = row["snip"] or ""
                    # Fallback snippet if body didn't produce one (e.g. matched title)
                    if not raw_snippet:
                        raw_snippet = f"Matched in {row['title']}"
                    results.append(SearchResult(note=summary, snippet=raw_snippet))
            except Exception:
                return []

        return results

    def list_notes(
        self,
        tag: str | None = None,
        note_type: str | None = None,
        limit: int = 50,
    ) -> list[NoteSummary]:
        """Lists notes matching filters, sorted by date descending."""
        query = "SELECT n.id, n.filepath, n.title, n.date, n.type, n.tags FROM notes n"
        params: list[Any] = []
        conditions: list[str] = []

        if tag:
            query += " JOIN note_tags t ON n.id = t.note_id"
            conditions.append("t.tag = ?")
            params.append(tag.strip().lower())

        if note_type:
            conditions.append("n.type = ?")
            params.append(note_type)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY n.date DESC, n.mtime_ns DESC LIMIT ?"
        params.append(limit)

        results: list[NoteSummary] = []
        with self.db.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            for row in rows:
                tags = json.loads(row["tags"]) if row["tags"] else []
                results.append(
                    NoteSummary(
                        id=row["id"],
                        title=row["title"],
                        date=row["date"],
                        note_type=row["type"],
                        tags=tags,
                        filepath=Path(row["filepath"]),
                    )
                )

        return results

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

            # 3. Date prefix or path match
            if not row:
                row = conn.execute(
                    "SELECT filepath FROM notes WHERE date LIKE ? OR filepath LIKE ? LIMIT 1;",
                    (f"{ident}%", f"%{ident}%"),
                ).fetchone()

            if row:
                p = Path(row["filepath"])
                if p.is_file():
                    return self.storage.read_note(p)

        # Fallback to direct disk inspection if database hasn't synced yet
        journal_p = self.storage.get_journal_path(ident)
        if journal_p.is_file():
            return self.storage.read_note(journal_p)

        for p in self.storage.list_note_files():
            if ident in p.name:
                return self.storage.read_note(p)

        return None
