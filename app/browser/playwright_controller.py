"""Browser automation helpers for Gmail and general web navigation."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


class BrowserAutomationError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrowserResult:
    text: str
    action: str


class PlaywrightController:
    """Use real browser DOM elements before falling back to desktop vision."""

    def __init__(self) -> None:
        self._playwright = None
        self.browser = None
        self.page = None

    def available(self) -> bool:
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            return False

    def start(self, headless: bool = False) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserAutomationError("Browser automation is not installed. Install Playwright to enable it.") from exc
        if self.page is not None:
            return
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(headless=headless)
        context = self.browser.new_context()
        self.page = context.new_page()

    def stop(self) -> None:
        try:
            if self.browser:
                self.browser.close()
            if self._playwright:
                self._playwright.stop()
        finally:
            self.browser = None
            self.page = None
            self._playwright = None

    def navigate(self, url: str) -> BrowserResult:
        self._require_page()
        if not re.match(r"^https?://", url.strip(), re.IGNORECASE):
            raise BrowserAutomationError("Only http and https URLs are supported.")
        self.page.goto(url.strip(), wait_until="domcontentloaded", timeout=30_000)
        return BrowserResult(f"Opened {self.page.title() or url}.", "navigate")

    def click_text(self, text: str) -> BrowserResult:
        self._require_page()
        target = text.strip()
        if not target:
            raise BrowserAutomationError("Please specify the text to click.")
        locator = self.page.get_by_text(target, exact=True).first
        if locator.count() == 0:
            locator = self.page.get_by_role("button", name=target).first
        if locator.count() == 0:
            locator = self.page.get_by_role("link", name=target).first
        if locator.count() == 0:
            raise BrowserAutomationError(f"Couldn't find a visible browser element named '{target}'.")
        locator.click()
        return BrowserResult(f"Clicked '{target}'.", "click_text")

    def fill(self, label: str, value: str) -> BrowserResult:
        self._require_page()
        target = self.page.get_by_label(label, exact=True).first
        if target.count() == 0:
            target = self.page.locator(f"input[placeholder='{label}']").first
        if target.count() == 0:
            raise BrowserAutomationError(f"Couldn't find a field named '{label}'.")
        target.fill(value)
        return BrowserResult(f"Entered text in '{label}'.", "fill")

    def page_text(self) -> str:
        self._require_page()
        return self.page.locator("body").inner_text(timeout=10_000)

    def snapshot(self) -> dict[str, Any]:
        self._require_page()
        elements = []
        for locator, role in ((self.page.get_by_role("button"), "button"), (self.page.get_by_role("link"), "link"), (self.page.locator("input"), "input")):
            try:
                count = min(locator.count(), 80)
                for index in range(count):
                    item = locator.nth(index)
                    try:
                        text = (item.inner_text() if role != "input" else item.get_attribute("placeholder")) or item.get_attribute("aria-label") or ""
                        if text.strip():
                            elements.append({"role": role, "text": text.strip()})
                    except Exception:
                        continue
            except Exception:
                continue
        return {"title": self.page.title(), "url": self.page.url, "elements": elements}

    def _require_page(self) -> None:
        if self.page is None:
            self.start(headless=False)
