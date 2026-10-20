from pathlib import Path
import os
import pytest
from noted.config import Config, load_config

def test_default_config(monkeypatch):
    monkeypatch.delenv("NOTES_DIR", raising=False)
    config = load_config()
    expected_notes_dir = Path.home() / ".notes" if os.name == "nt" else Path.home() / ".local" / "share" / "notes"
    assert config.notes_dir == expected_notes_dir
    assert config.editor is None
    assert "Highlights" in config.journal_template
    assert "Reflections" in config.journal_template
    assert "Todo" in config.journal_template

def test_notes_dir_env_override(monkeypatch, tmp_path):
    custom_dir = tmp_path / "custom_notes"
    monkeypatch.setenv("NOTES_DIR", str(custom_dir))
    config = load_config()
    assert config.notes_dir == custom_dir

def test_ensure_directories(tmp_path):
    notes_dir = tmp_path / "test_notes"
    config = Config(notes_dir=notes_dir)
    assert not notes_dir.exists()
    
    config.ensure_directories()
    
    assert notes_dir.is_dir()
    assert (notes_dir / "notes").is_dir()
    assert (notes_dir / "journal").is_dir()

def test_load_from_toml(tmp_path):
    config_file = tmp_path / "config.toml"
    notes_target = tmp_path / "my_notes"
    config_file.write_text(
        f'notes_dir = "{notes_target.as_posix()}"\neditor = "nvim"\njournal_template = "## Daily Log\\n"\n'
    )
    config = load_config(config_path=config_file)
    assert config.notes_dir == notes_target
    assert config.editor == "nvim"
    assert config.journal_template == "## Daily Log\n"
