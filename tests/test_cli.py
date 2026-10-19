from datetime import date
from pathlib import Path
import pytest
from typer.testing import CliRunner
from noted.cli import app

runner = CliRunner()

@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch):
    notes_dir = tmp_path / "cli_notes"
    monkeypatch.setenv("NOTES_DIR", str(notes_dir))
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)

def test_cli_add_and_list():
    result = runner.invoke(app, ["add", "Testing quick capture note", "-t", "cli,test", "--title", "CLI Note"])
    assert result.exit_code == 0
    assert "Created note:" in result.stdout or "CLI Note" in result.stdout

    # List notes
    list_res = runner.invoke(app, ["list"])
    assert list_res.exit_code == 0
    assert "CLI Note" in list_res.stdout
    assert "cli" in list_res.stdout

def test_cli_search():
    runner.invoke(app, ["add", "Terminal tools are awesome", "-t", "unix", "--title", "Unix Tools"])
    
    search_res = runner.invoke(app, ["search", "awesome"])
    assert search_res.exit_code == 0
    assert "Unix Tools" in search_res.stdout

def test_cli_today_view():
    today_str = date.today().isoformat()
    res = runner.invoke(app, ["today", "--view"])
    assert res.exit_code == 0
    assert today_str in res.stdout
    assert "Highlights" in res.stdout

def test_cli_view_by_id():
    # First add a note
    add_res = runner.invoke(app, ["add", "Detailed description inside note", "--title", "Viewable Note"])
    assert add_res.exit_code == 0

    # List to get the ID
    list_res = runner.invoke(app, ["list"])
    assert list_res.exit_code == 0

    # View note
    view_res = runner.invoke(app, ["view", "Viewable Note"])
    assert view_res.exit_code == 0
    assert "Detailed description inside note" in view_res.stdout

def test_cli_view_nonexistent():
    res = runner.invoke(app, ["view", "completely-unknown-id-404"])
    assert res.exit_code != 0 or "not found" in res.stdout.lower()

def test_cli_sync():
    res = runner.invoke(app, ["sync"])
    assert res.exit_code == 0
    assert "Synced" in res.stdout

def test_cli_copy(monkeypatch):
    runner.invoke(app, ["add", "Text for clipboard testing", "--title", "Copy Note"])
    
    # Mock clipboard
    copied = []
    monkeypatch.setattr("noted.clipboard.copy_to_clipboard", lambda text, app=None: copied.append(text) or True)

    res = runner.invoke(app, ["copy", "Copy Note"])
    assert res.exit_code == 0
    assert "Copied note" in res.stdout
    assert len(copied) == 1
    assert "Text for clipboard testing" in copied[0]

def test_cli_rename():
    add_res = runner.invoke(app, ["add", "Rename me please", "--title", "Initial Name"])
    assert add_res.exit_code == 0

    rename_res = runner.invoke(app, ["rename", "Initial Name", "Brand New Title"])
    assert rename_res.exit_code == 0
    assert "Renamed note" in rename_res.stdout
    assert "Brand New Title" in rename_res.stdout

    # Verify via search/view
    view_res = runner.invoke(app, ["view", "Brand New Title"])
    assert view_res.exit_code == 0
    assert "Rename me please" in view_res.stdout


def test_cli_lock_and_view():
    add_res = runner.invoke(app, ["add", "Classified Information 456", "--title", "Secret CLI Note"])
    assert add_res.exit_code == 0

    # Lock note with password
    lock_res = runner.invoke(app, ["lock", "Secret CLI Note", "-p", "MySecretKey"])
    assert lock_res.exit_code == 0
    assert "Locked note" in lock_res.stdout

    # View with wrong password should fail
    fail_view = runner.invoke(app, ["view", "Secret CLI Note", "-p", "WrongKey"])
    assert fail_view.exit_code != 0
    assert "Incorrect password" in fail_view.stdout

    # View with correct password should display content
    success_view = runner.invoke(app, ["view", "Secret CLI Note", "-p", "MySecretKey"])
    assert success_view.exit_code == 0
    assert "Classified Information 456" in success_view.stdout


def test_cli_unlock():
    add_res = runner.invoke(app, ["add", "Lock and Unlock Content", "--title", "Unlock Me Note"])
    assert add_res.exit_code == 0

    # Lock it
    runner.invoke(app, ["lock", "Unlock Me Note", "-p", "PassKey99"])

    # Unlock with correct password
    unlock_res = runner.invoke(app, ["unlock", "Unlock Me Note", "-p", "PassKey99"])
    assert unlock_res.exit_code == 0
    assert "Permanently unlocked" in unlock_res.stdout

    # Now view without password
    view_res = runner.invoke(app, ["view", "Unlock Me Note"])
    assert view_res.exit_code == 0
    assert "Lock and Unlock Content" in view_res.stdout


def test_cli_copy_encrypted(monkeypatch):
    runner.invoke(app, ["add", "Encrypted clipboard secret", "--title", "Copy Encrypted Note"])
    runner.invoke(app, ["lock", "Copy Encrypted Note", "-p", "ClipSecret1"])

    copied = []
    monkeypatch.setattr("noted.clipboard.copy_to_clipboard", lambda text, app=None: copied.append(text) or True)

    res = runner.invoke(app, ["copy", "Copy Encrypted Note", "-p", "ClipSecret1"])
    assert res.exit_code == 0
    assert "Copied note" in res.stdout
    assert len(copied) == 1
    assert "Encrypted clipboard secret" in copied[0]


def test_cli_edit_encrypted_protection():
    runner.invoke(app, ["add", "Cannot edit directly", "--title", "Protected Edit Note"])
    runner.invoke(app, ["lock", "Protected Edit Note", "-p", "ProtectedKey"])

    res = runner.invoke(app, ["edit", "Protected Edit Note"])
    assert res.exit_code != 0
    assert "This note is encrypted" in res.stdout

