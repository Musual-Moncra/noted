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
