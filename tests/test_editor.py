from pathlib import Path
import os
import pytest
from noted.editor import find_editor, open_in_editor

def test_find_editor_preferred(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda cmd: f"/usr/bin/{cmd}" if cmd == "helix" else None)
    cmd = find_editor(preferred="helix")
    assert cmd == ["helix"]

def test_find_editor_env_var(monkeypatch):
    monkeypatch.setenv("EDITOR", "code --wait")
    monkeypatch.setattr("shutil.which", lambda c: f"/usr/bin/{c}" if c == "code" else None)
    cmd = find_editor()
    assert cmd == ["code", "--wait"]

def test_find_editor_fallback(monkeypatch):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    
    # Simulate only nano existing
    def fake_which(c):
        return f"/usr/bin/{c}" if c == "nano" else None
    
    monkeypatch.setattr("shutil.which", fake_which)
    cmd = find_editor()
    assert cmd == ["nano"]

def test_find_editor_none_found(monkeypatch):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
    assert find_editor() is None

def test_open_in_editor_success(tmp_path, monkeypatch):
    import subprocess
    test_file = tmp_path / "note.md"
    test_file.write_text("Hello")

    calls = []
    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("shutil.which", lambda c: "/usr/bin/nano")

    success = open_in_editor(test_file, preferred_editor="nano")
    assert success is True
    assert len(calls) == 1
    assert calls[0] == ["nano", str(test_file)]
