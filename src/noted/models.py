from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import unicodedata


def normalize_tags(tags: list[str]) -> list[str]:
    return list(dict.fromkeys(unicodedata.normalize('NFC', str(t)).strip().lower()
                              for t in tags if str(t).strip()))


@dataclass
class Note:
    id: str
    title: str
    date: str
    note_type: str = 'note'
    tags: list[str] = field(default_factory=list)
    body: str = ''
    filepath: Path | None = None
    mtime_ns: int = 0
    encrypted: bool = False
    salt: str | None = None
    nonce: str | None = None
    pinned: bool = False
    archived: bool = False
    size_bytes: int = 0
    extra_metadata: dict[str, Any] = field(default_factory=dict)
    has_stored_id: bool = True

    def to_metadata(self) -> dict[str, Any]:
        meta = {**self.extra_metadata, 'id': self.id, 'title': self.title,
                'date': self.date, 'type': self.note_type,
                'tags': normalize_tags(self.tags), 'pinned': self.pinned,
                'archived': self.archived}
        if self.encrypted:
            meta.update(encrypted=True, salt=self.salt, nonce=self.nonce)
        return meta


@dataclass
class NoteSummary:
    id: str
    title: str
    date: str
    note_type: str
    tags: list[str]
    filepath: Path
    encrypted: bool = False
    pinned: bool = False
    archived: bool = False
    excerpt: str = ''
    mtime_ns: int = 0


@dataclass
class SearchResult:
    note: NoteSummary
    snippet: str
