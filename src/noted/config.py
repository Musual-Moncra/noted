from dataclasses import dataclass, field
from pathlib import Path
import os
import tomllib

DEFAULT_JOURNAL_TEMPLATE = """## Highlights

## Reflections

## Todo
- [ ] 
"""

def get_default_notes_dir() -> Path:
    env_dir = os.environ.get("NOTES_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    if os.name == "nt":
        return Path.home() / ".notes"
    return Path.home() / ".local" / "share" / "notes"

def get_default_config_path() -> Path:
    if os.name == "nt":
        return Path.home() / ".notes" / "config.toml"
    return Path.home() / ".config" / "noted" / "config.toml"

@dataclass
class Config:
    notes_dir: Path = field(default_factory=get_default_notes_dir)
    editor: str | None = None
    journal_template: str = DEFAULT_JOURNAL_TEMPLATE
    config_path: Path | None = None

    @property
    def notes_subdir(self) -> Path:
        return self.notes_dir / "notes"

    @property
    def journal_subdir(self) -> Path:
        return self.notes_dir / "journal"

    @property
    def db_path(self) -> Path:
        return self.notes_dir / "index.db"

    def ensure_directories(self) -> None:
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.notes_subdir.mkdir(parents=True, exist_ok=True)
        self.journal_subdir.mkdir(parents=True, exist_ok=True)

def load_config(config_path: Path | None = None) -> Config:
    # 1. Determine base config
    notes_dir = get_default_notes_dir()
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    template = DEFAULT_JOURNAL_TEMPLATE

    # 2. Try loading custom or default config file
    target_path = config_path or get_default_config_path()
    if target_path and target_path.is_file():
        try:
            with open(target_path, "rb") as f:
                data = tomllib.load(f)
            if "notes_dir" in data:
                # Environment variable NOTES_DIR still has precedence if explicitly set
                if not os.environ.get("NOTES_DIR"):
                    notes_dir = Path(data["notes_dir"]).expanduser().resolve()
                else:
                    notes_dir = Path(os.environ["NOTES_DIR"]).expanduser().resolve()
            if "editor" in data:
                editor = data["editor"]
            if "journal_template" in data:
                template = data["journal_template"]
        except Exception:
            pass  # Fallback to defaults gracefully if config is corrupted

    return Config(
        notes_dir=notes_dir,
        editor=editor,
        journal_template=template,
        config_path=target_path if (target_path and target_path.exists()) else None,
    )
