"""Configure Playwright to use the browser runtime shipped beside the portable EXE."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    app_dir = Path(sys.executable).resolve().parent
    browser_dir = app_dir / "playwright"
    if browser_dir.is_dir():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browser_dir))
