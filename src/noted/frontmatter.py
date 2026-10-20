import re
from datetime import datetime
from typing import Any
import yaml

FRONTMATTER_REGEX = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", re.DOTALL)

def parse_frontmatter(raw_content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from raw note content.
    
    Returns (metadata_dict, body_string).
    If frontmatter is missing or corrupted, returns ({}, raw_content) safely.
    """
    if not raw_content.startswith("---"):
        return {}, raw_content

    match = FRONTMATTER_REGEX.match(raw_content)
    if not match:
        return {}, raw_content

    yaml_block, body = match.groups()
    try:
        data = yaml.safe_load(yaml_block)
        if isinstance(data, dict):
            return data, body
        return {}, body
    except Exception:
        # Graceful recovery on invalid YAML
        return {}, body

def serialize_note(metadata: dict[str, Any], body: str) -> str:
    """Serialize a metadata dictionary and body into a YAML frontmatter markdown string."""
    yaml_str = yaml.dump(
        metadata,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    # Ensure clean spacing
    clean_body = body.lstrip("\r\n")
    return f"---\n{yaml_str}---\n\n{clean_body}"

def generate_note_id() -> str:
    """Generate a chronological unique note identifier in format YYYYMMDD-HHMMSS-random64."""
    import secrets
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(8)}"

def slugify(text: str) -> str:
    """Convert text to a URL- and filename-safe slug."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    text = text.strip("-")
    return text if text else "note"
