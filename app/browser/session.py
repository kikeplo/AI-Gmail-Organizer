"""Browser session management for AI Gmail Organizer v2.4."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path


class BrowserSessionError(RuntimeError):
    pass


def default_chrome_user_data() -> Path:
    local = os.getenv("LOCALAPPDATA")
    if not local:
        return Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    return Path(local) / "Google" / "Chrome" / "User Data"


class BrowserSession:
    """Manage isolated, reusable-profile, and CDP-attached Playwright sessions."""

    def __init__(self) -> None:
        self.mode = os.getenv("BROWSER_MODE", "auto").strip().lower()
        self.profile = Path(os.getenv("BROWSER_USER_DATA_DIR", str(default_chrome_user_data()))).expanduser()
        self.cdp_url = os.getenv("BROWSER_CDP_URL", "http://127.0.0.1:9222").strip()
        self._playwright = None
        self._browser = None
        self._context = None

    def start(self, url: str | None = None):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserSessionError("Playwright is not installed. Run: pip install playwright && playwright install chromium") from exc
        self._playwright = sync_playwright().start()
        try:
            if self.mode in {"cdp", "auto"}:
                try:
                    self._browser = self._playwright.chromium.connect_over_cdp(self.cdp_url)
                    self._context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
                except Exception:
                    if self.mode == "cdp":
                        raise BrowserSessionError("Could not connect to the existing Chrome session. Start Chrome with remote debugging enabled, then try again.")
            if self._context is None and self.mode in {"profile", "auto"}:
                self._context = self._playwright.chromium.launch_persistent_context(
                    str(self.profile), headless=False
                )
                self._browser = None
            if self._context is None:
                self._browser = self._playwright.chromium.launch(headless=False)
                self._context = self._browser.new_context()
            page = self._context.pages[0] if self._context.pages else self._context.new_page()
            if url and not page.url:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            elif url and "about:blank" in page.url:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return page
        except Exception:
            self.close()
            raise

    def open_gmail(self):
        return self.start("https://mail.google.com/")

    def close(self) -> None:
        try:
            if self._context and self.mode != "cdp":
                self._context.close()
        finally:
            self._context = None
            if self._browser and self.mode != "cdp":
                self._browser.close()
            self._browser = None
            if self._playwright:
                self._playwright.stop()
            self._playwright = None

    @staticmethod
    def chrome_debug_command() -> str:
        return 'chrome.exe --remote-debugging-port=9222'
