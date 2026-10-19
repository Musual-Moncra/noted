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

    def to_metadata(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "date": self.date,
            "type": self.note_type,
            "tags": self.tags,
        }

@dataclass
class NoteSummary:
    id: str
    title: str
    date: str
    note_type: str
    tags: list[str]
    filepath: Path

@dataclass
class SearchResult:
    note: NoteSummary
    snippet: str
