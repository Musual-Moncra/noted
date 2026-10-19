import os
os.environ.setdefault("TEXTUAL_DISABLE_KITTY_KEY", "1")
try:
    import textual.constants as _tc
    _tc.DISABLE_KITTY_KEY = True
except Exception:
    pass

from noted.cli import app

if __name__ == "__main__":
    app()
