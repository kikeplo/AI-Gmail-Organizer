"""Browser automation helpers for AI Gmail Organizer."""

from __future__ import annotations

import os
import time
from pathlib import Path


class BrowserAgentError(RuntimeError):
    pass


class BrowserAgent:
    """Automate real web elements with Playwright, with isolated/profile modes."""

    def __init__(self) -> None:
        self.mode = os.getenv("BROWSER_MODE", "isolated").strip().lower()
        self.user_data_dir = Path(os.getenv("BROWSER_USER_DATA_DIR", "")).expanduser() if os.getenv("BROWSER_USER_DATA_DIR") else None
        self.headless = os.getenv("BROWSER_HEADLESS", "0").strip().lower() in {"1", "true", "yes"}
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    @property
    def page(self):
        return self._page

    def start(self, url: str | None = None):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserAgentError("Playwright is not installed. Run: pip install playwright && playwright install chromium") from exc

        self._playwright = sync_playwright().start()
        try:
            if self.mode == "profile" and self.user_data_dir:
                self.user_data_dir.mkdir(parents=True, exist_ok=True)
                self._context = self._playwright.chromium.launch_persistent_context(
                    str(self.user_data_dir), headless=self.headless
                )
            else:
                self._browser = self._playwright.chromium.launch(headless=self.headless)
                self._context = self._browser.new_context()
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            if url:
                self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return self._page
        except Exception:
            self.close()
            raise

    def open_gmail(self):
        return self.start("https://mail.google.com/")

    def navigate(self, url: str) -> None:
        self._require_page()
        self._page.goto(url, wait_until="domcontentloaded", timeout=30000)

    def click_text(self, text: str, exact: bool = False) -> str:
        self._require_page()
        locator = self._page.get_by_text(text, exact=exact).first
        locator.click()
        return f'Clicked "{text}".'

    def click_role(self, role: str, name: str, exact: bool = False) -> str:
        self._require_page()
        locator = self._page.get_by_role(role, name=name, exact=exact).first
        locator.click()
        return f'Clicked {role} "{name}".'

    def fill(self, label: str, value: str) -> str:
        self._require_page()
        locator = self._page.get_by_label(label, exact=False).first
        locator.fill(value)
        return f'Filled "{label}".'

    def page_text(self, limit: int = 12000) -> str:
        self._require_page()
        return self._page.locator("body").inner_text(timeout=10000)[:limit]

    def elements(self) -> list[dict[str, str]]:
        self._require_page()
        output: list[dict[str, str]] = []
        for locator in (self._page.locator("button"), self._page.locator("a"), self._page.locator("input")):
            count = min(locator.count(), 100)
            for index in range(count):
                item = locator.nth(index)
                try:
                    output.append({"tag": item.evaluate("el => el.tagName"), "text": (item.inner_text() or item.get_attribute("aria-label") or item.get_attribute("placeholder") or "").strip()[:200]})
                except Exception:
                    continue
        return output

    def wait(self, seconds: float = 1.0) -> None:
        self._require_page()
        self._page.wait_for_timeout(int(max(0.1, min(seconds, 10.0)) * 1000))

    def close(self) -> None:
        try:
            if self._context:
                self._context.close()
        finally:
            self._context = None
            self._page = None
            if self._browser:
                self._browser.close()
            self._browser = None
            if self._playwright:
                self._playwright.stop()
            self._playwright = None

    def _require_page(self) -> None:
        if self._page is None:
            raise BrowserAgentError("Browser is not running. Start the browser before using browser actions.")
