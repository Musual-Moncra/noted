# Contributing to Noted

Thank you for your interest in contributing to **Noted**! We welcome all contributions: bug fixes, new features, documentation improvements, and feedback.

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

---

## Getting Started

### 1. Prerequisites
- Python 3.10+
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip` / `virtualenv`
- Git

### 2. Fork and Clone
```bash
git clone https://github.com/<your-username>/noted.git
cd noted
git checkout -b feature/my-new-feature
```

### 3. Setting Up Development Environment

Using `uv` (recommended):
```bash
# Install all dependencies including development tools
uv sync --all-extras --dev

# Activate virtual environment (optional)
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Using standard `pip`:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

---

## Running the Application Locally

You can run `noted` in development mode directly:
```bash
# Launch interactive TUI
uv run note

# Or run specific CLI commands
uv run note add "Test note" -t idea
uv run note list
uv run note search "Test"
```

---

## Running Automated Tests

All changes must pass the test suite before being merged:
```bash
uv run pytest -v
```

To run a specific test file:
```bash
uv run pytest tests/test_tui.py -v
```

---

## Building Standalone Executable Locally

To verify binary packaging with PyInstaller:
```bash
uv run pyinstaller noted.spec --clean
./dist/noted --help  # On Windows: .\dist\noted.exe --help
```

---

## Pull Request Guidelines

1. **Keep PRs focused**: Each PR should address one bug or feature.
2. **Add tests**: If adding a feature or fixing a bug, please write corresponding tests in `tests/`.
3. **Ensure cross-platform compatibility**: Code should work on Linux, macOS, and Windows. Avoid hardcoded Unix file paths (`/`). Use `pathlib.Path`.
4. **Follow commit conventions**: Use clear commit messages (e.g., `feat: ...`, `fix: ...`, `docs: ...`).

Thank you for helping make **Noted** better!
