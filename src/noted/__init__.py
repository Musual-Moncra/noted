"""Noted package."""

import os
os.environ.setdefault("TEXTUAL_DISABLE_KITTY_KEY", "1")
try:
    import textual.constants as _tc
    _tc.DISABLE_KITTY_KEY = True
except Exception:
    pass

__version__ = "0.2.1"
