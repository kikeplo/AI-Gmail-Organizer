"""Browser automation helpers for AI Gmail Organizer v2.4."""

from __future__ import annotations

from app.browser.session import BrowserSession, BrowserSessionError


class BrowserAgentError(RuntimeError):
    pass


class BrowserAgent:
    """Interact with real web elements while reusing an existing session when possible."""

    def __init__(self) -> None:
        self.session = BrowserSession()

    @property
    def page(self):
        return self.session._context.pages[0] if self.session._context and self.session._context.pages else None

    def start(self, url: str | None = None):
        try:
            return self.session.start(url)
        except BrowserSessionError as exc:
            raise BrowserAgentError(str(exc)) from exc

    def open_gmail(self):
        return self.start("https://mail.google.com/")

    def navigate(self, url: str) -> None:
        self._require_page()
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

    def click_text(self, text: str, exact: bool = False) -> str:
        self._require_page()
        self.page.get_by_text(text, exact=exact).first.click()
        return f'Clicked "{text}".'

    def click_role(self, role: str, name: str, exact: bool = False) -> str:
        self._require_page()
        self.page.get_by_role(role, name=name, exact=exact).first.click()
        return f'Clicked {role} "{name}".'

    def fill(self, label: str, value: str) -> str:
        self._require_page()
        self.page.get_by_label(label, exact=False).first.fill(value)
        return f'Filled "{label}".'

    def page_text(self, limit: int = 12000) -> str:
        self._require_page()
        return self.page.locator("body").inner_text(timeout=10000)[:limit]

    def elements(self) -> list[dict[str, str]]:
        self._require_page()
        output: list[dict[str, str]] = []
        for selector in ("button", "a", "input"):
            locator = self.page.locator(selector)
            for index in range(min(locator.count(), 100)):
                item = locator.nth(index)
                try:
                    text = (item.inner_text() or item.get_attribute("aria-label") or item.get_attribute("placeholder") or "").strip()
                    output.append({"tag": selector, "text": text[:200]})
                except Exception:
                    continue
        return output

    def wait(self, seconds: float = 1.0) -> None:
        self._require_page()
        self.page.wait_for_timeout(int(max(0.1, min(seconds, 10.0)) * 1000))

    def close(self) -> None:
        self.session.close()

    def _require_page(self) -> None:
        if self.page is None:
            raise BrowserAgentError("The browser is not connected. Open a browser session first.")
