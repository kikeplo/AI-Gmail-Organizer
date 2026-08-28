"""Runtime hook for PyInstaller onedir builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    app_root = Path(sys.executable).resolve().parent
    browser_root = app_root / "playwright"
    if browser_root.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_root)
