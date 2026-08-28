"""Browser automation helpers for Gmail and general web navigation."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from pathlib import Path
from typing import Any


class BrowserAutomationError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrowserResult:
    text: str
    action: str


class PlaywrightController:
    """Use real browser DOM elements with isolated, reusable-profile, or CDP sessions."""

    def __init__(self) -> None:
        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.mode = os.getenv("BROWSER_MODE", "auto").strip().lower()
        self.profile_dir = Path(os.getenv("BROWSER_USER_DATA_DIR", "")).expanduser() if os.getenv("BROWSER_USER_DATA_DIR") else None
        self.cdp_url = os.getenv("BROWSER_CDP_URL", "http://127.0.0.1:9222").strip()

    def available(self) -> bool:
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            return False

    def start(self, headless: bool = False, mode: str | None = None) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserAutomationError("Browser automation is not installed. Install Playwright to enable it.") from exc
        if self.page is not None:
            return

        selected_mode = (mode or self.mode or "auto").strip().lower()
        self._playwright = sync_playwright().start()
        try:
            if selected_mode in {"cdp", "auto", "existing"}:
                try:
                    self.browser = self._playwright.chromium.connect_over_cdp(self.cdp_url)
                    self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
                except Exception as exc:
                    if selected_mode in {"cdp", "existing"}:
                        raise BrowserAutomationError(
                            "Couldn't connect to your existing Chrome session. "
                            "You can use isolated mode instead, or start Chrome with remote debugging enabled."
                        ) from exc

            if self.context is None and selected_mode == "profile" and self.profile_dir:
                self.profile_dir.mkdir(parents=True, exist_ok=True)
                self.context = self._playwright.chromium.launch_persistent_context(
                    str(self.profile_dir), headless=headless
                )

            if self.context is None:
                self.browser = self._playwright.chromium.launch(headless=headless)
                self.context = self.browser.new_context()

            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        except Exception:
            self.stop()
            raise

    def status(self) -> dict[str, str | bool]:
        connected = self.page is not None
        return {
            "connected": connected,
            "mode": self.mode,
            "url": self.page.url if self.page else "",
            "title": self.page.title() if self.page else "",
            "cdp_url": self.cdp_url,
        }

    def start_gmail(self) -> BrowserResult:
        if self.page is None:
            self.start(headless=False)
        if not self.page.url or self.page.url == "about:blank":
            self.page.goto("https://mail.google.com/", wait_until="domcontentloaded", timeout=30_000)
        elif "mail.google.com" not in self.page.url:
            self.page.goto("https://mail.google.com/", wait_until="domcontentloaded", timeout=30_000)
        return BrowserResult(f"Gmail is open in {self.page.title() or 'the browser'}.", "open_gmail")

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
            locator = self.page.get_by_role("button", name=target, exact=True).first
        if locator.count() == 0:
            locator = self.page.get_by_role("link", name=target, exact=True).first
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

    def close(self) -> None:
        self.stop()

    def stop(self) -> None:
        try:
            if self.context and self.mode not in {"cdp", "existing", "auto"}:
                self.context.close()
        finally:
            self.context = None
            if self.browser and self.mode not in {"cdp", "existing", "auto"}:
                self.browser.close()
            self.browser = None
            if self._playwright:
                self._playwright.stop()
            self._playwright = None
            self.page = None

    @staticmethod
    def chrome_remote_debug_command() -> str:
        return 'chrome.exe --remote-debugging-port=9222'

    def _require_page(self) -> None:
        if self.page is None:
            self.start(headless=False)
