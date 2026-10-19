import pytest
from noted.frontmatter import (
    parse_frontmatter,
    serialize_note,
    generate_note_id,
    slugify,
)
from noted.models import Note

def test_parse_valid_frontmatter():
    raw = """---
id: "20261019-143000"
title: "Sample Note Title"
date: "2026-10-19T14:30:00"
type: "note"
tags:
  - python
  - terminal
---

# Sample Note Title

This is the body content.
"""
    meta, body = parse_frontmatter(raw)
    assert meta["id"] == "20261019-143000"
    assert meta["title"] == "Sample Note Title"
    assert meta["date"] == "2026-10-19T14:30:00"
    assert meta["type"] == "note"
    assert meta["tags"] == ["python", "terminal"]
    assert body.strip() == "# Sample Note Title\n\nThis is the body content."

def test_serialize_note():
    meta = {
        "id": "20261019-143000",
        "title": "My Note",
        "date": "2026-10-19T14:30:00",
        "type": "note",
        "tags": ["quick", "idea"],
    }
    body = "Just an idea.\n"
    serialized = serialize_note(meta, body)
    
    assert serialized.startswith("---\n")
    assert "title: My Note" in serialized
    assert "tags:" in serialized
    assert serialized.endswith("---\n\nJust an idea.\n")

def test_round_trip():
    meta = {
        "id": "test-123",
        "title": "Round Trip Test",
        "date": "2026-10-19T10:00:00",
        "type": "journal",
        "tags": ["test"],
    }
    body = "Body of round trip test."
    serialized = serialize_note(meta, body)
    parsed_meta, parsed_body = parse_frontmatter(serialized)
    
    assert parsed_meta["id"] == meta["id"]
    assert parsed_meta["title"] == meta["title"]
    assert parsed_meta["tags"] == meta["tags"]
    assert parsed_body.strip() == body.strip()

def test_parse_no_frontmatter():
    raw = "Just a raw markdown text without frontmatter."
    meta, body = parse_frontmatter(raw)
    assert meta == {}
    assert body == raw

def test_parse_malformed_frontmatter():
    raw = """---
id: invalid: yaml: [broken
title: oops
---
Some body text
"""
    meta, body = parse_frontmatter(raw)
    # Should not raise exception, graceful fallback
    assert isinstance(meta, dict)
    assert "Some body text" in body

def test_generate_note_id():
    nid = generate_note_id()
    assert len(nid) == 15  # YYYYMMDD-HHMMSS (8 + 1 + 6)
    assert nid[8] == "-"
    assert nid[:8].isdigit()
    assert nid[9:].isdigit()

def test_slugify():
    assert slugify("Hello World!") == "hello-world"
    assert slugify("Project: Antigravity (CLI & TUI)") == "project-antigravity-cli-tui"
    assert slugify("   Multiple   Spaces   ") == "multiple-spaces"
    assert slugify("") == "note"
