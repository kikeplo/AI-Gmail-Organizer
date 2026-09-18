"""Runtime hook for the portable PyInstaller build."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 6.22+ uses _internal as sys._MEIPASS in onedir builds.
    # Put that directory first on sys.path so the source copy of app/
    # bundled by the spec remains importable as a normal Python package.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        meipass_path = str(Path(meipass).resolve())
        if meipass_path not in sys.path:
            sys.path.insert(0, meipass_path)

    app_dir = Path(sys.executable).resolve().parent
    browser_root = app_dir / "playwright"
    if browser_root.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_root)
