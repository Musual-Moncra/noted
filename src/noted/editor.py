import os
import shlex
import shutil
import subprocess
from pathlib import Path
from rich.console import Console

console = Console(stderr=True)

FALLBACK_EDITORS = ["nano", "vim", "vi"]

def find_editor(preferred: str | None = None) -> list[str] | None:
    """Finds an available terminal text editor command.
    
    Checks in order:
    1. Preferred editor parameter
    2. $EDITOR environment variable
    3. $VISUAL environment variable
    4. nano / vim / vi fallbacks
    """
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    if os.environ.get("EDITOR"):
        candidates.append(os.environ["EDITOR"])
    if os.environ.get("VISUAL"):
        candidates.append(os.environ["VISUAL"])
    candidates.extend(FALLBACK_EDITORS)

    for cand in candidates:
        parts = shlex.split(cand.strip())
        if not parts:
            continue
        exe = shutil.which(parts[0])
        if exe:
            return parts

    return None

def open_in_editor(filepath: Path, preferred_editor: str | None = None) -> bool:
    """Opens a target note in an external terminal editor."""
    cmd = find_editor(preferred=preferred_editor)
    if not cmd:
        console.print(
            "[bold red]Error:[/bold red] No text editor found! Please set your [yellow]$EDITOR[/yellow] "
            "environment variable (e.g. [green]export EDITOR=nano[/green]) or install nano/vim."
        )
        return False

    try:
        res = subprocess.run([*cmd, str(filepath)])
        return res.returncode == 0
    except Exception as e:
        console.print(f"[bold red]Error running editor {' '.join(cmd)}:[/bold red] {e}")
        return False
