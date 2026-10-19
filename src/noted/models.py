from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class Note:
    id: str
    title: str
    date: str
    note_type: str = "note"  # 'note' or 'journal'
    tags: list[str] = field(default_factory=list)
    body: str = ""
    filepath: Path | None = None
    mtime_ns: int = 0
    encrypted: bool = False
    salt: str | None = None
    nonce: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "date": self.date,
            "type": self.note_type,
            "tags": self.tags,
        }
        if self.encrypted:
            meta["encrypted"] = True
            if self.salt:
                meta["salt"] = self.salt
            if self.nonce:
                meta["nonce"] = self.nonce
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

@dataclass
class SearchResult:
    note: NoteSummary
    snippet: str
