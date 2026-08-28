"""Browser automation helpers for Gmail and general web navigation."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import sys
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
        self.cdp_url = os.getenv("BROWSER_CDP_URL", "http://127.0.0.1:9222").strip().rstrip("/")
        self.session_kind = "none"

    def available(self) -> bool:
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            return False

    def _bundled_browser_executable(self) -> str | None:
        """Locate Chromium beside the portable EXE, never in PyInstaller's _MEI temp tree."""
        candidates: list[Path] = []
        env_root = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
        if env_root and env_root not in {"0", "1"}:
            candidates.append(Path(env_root))
        if getattr(sys, "frozen", False):
            app_root = Path(sys.executable).resolve().parent
            candidates.extend([app_root / "playwright", app_root / "_internal" / "playwright"])
        else:
            project_root = Path(__file__).resolve().parents[3]
            candidates.extend([project_root / ".playwright", project_root / "playwright"])

        for root in candidates:
            if not root.exists():
                continue
            found = next(root.rglob("chrome.exe"), None)
            if found and found.is_file():
                return str(found)
        return None

    def start(self, headless: bool = False, mode: str | None = None) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserAutomationError("Browser automation is not installed.") from exc
        if self.page is not None:
            return

        selected_mode = (mode or self.mode or "auto").strip().lower()
        self._playwright = sync_playwright().start()
        try:
            if selected_mode in {"cdp", "auto", "existing"}:
                try:
                    self.browser = self._playwright.chromium.connect_over_cdp(self.cdp_url)
                    self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
                    self.session_kind = "existing-chrome"
                except Exception as exc:
                    self.browser = None
                    self.context = None
                    if selected_mode in {"cdp", "existing"}:
                        raise BrowserAutomationError(
                            "Couldn't connect to your existing Chrome session. Start Chrome with remote debugging enabled, or switch Browser mode to Automatic."
                        ) from exc

            if self.context is None and selected_mode == "profile":
                if not self.profile_dir:
                    raise BrowserAutomationError("Browser profile mode needs a browser profile folder.")
                self.profile_dir.mkdir(parents=True, exist_ok=True)
                kwargs: dict[str, Any] = {"headless": headless}
                executable = self._bundled_browser_executable()
                if executable:
                    kwargs["executable_path"] = executable
                self.context = self._playwright.chromium.launch_persistent_context(str(self.profile_dir), **kwargs)
                self.session_kind = "persistent-profile"

            if self.context is None:
                launch_kwargs: dict[str, Any] = {"headless": headless}
                executable = self._bundled_browser_executable()
                if executable:
                    launch_kwargs["executable_path"] = executable
                self.browser = self._playwright.chromium.launch(**launch_kwargs)
                self.context = self.browser.new_context()
                self.session_kind = "isolated"

            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        except Exception as exc:
            self.stop()
            if "Executable doesn't exist" in str(exc) or "Looks like Playwright was just installed" in str(exc):
                raise BrowserAutomationError(
                    "The bundled Chromium browser could not be found next to the application. Rebuild the portable folder with the latest build script."
                ) from exc
            raise

    def status(self) -> dict[str, str | bool]:
        connected = self.page is not None
        return {"connected": connected, "mode": self.mode, "session": self.session_kind, "url": self.page.url if self.page else "", "title": self.page.title() if self.page else "", "cdp_url": self.cdp_url}

    def start_gmail(self) -> BrowserResult:
        if self.page is None:
            self.start(headless=False)
        if "mail.google.com" not in (self.page.url or ""):
            self.page.goto("https://mail.google.com/", wait_until="domcontentloaded", timeout=30_000)
        return BrowserResult(f"Gmail is open in {self.session_kind.replace('-', ' ')} mode.", "open_gmail")

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
        return {"title": self.page.title(), "url": self.page.url, "elements": elements, "session": self.session_kind}

    def close(self) -> None:
        self.stop()

    def stop(self) -> None:
        try:
            if self.context and self.session_kind in {"persistent-profile", "isolated"}:
                self.context.close()
        finally:
            self.context = None
            self.browser = None
            if self._playwright:
                self._playwright.stop()
            self._playwright = None
            self.page = None
            self.session_kind = "none"

    @staticmethod
    def chrome_remote_debug_command() -> str:
        return 'chrome.exe --remote-debugging-port=9222'

    def _require_page(self) -> None:
        if self.page is None:
            self.start(headless=False)
