from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib import request, parse
import json
import re


class BrowserError(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._anchor_href: str | None = None
        self._anchor_text: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        low = tag.lower()
        if low in {"script", "style", "noscript"}:
            self._skip += 1
        if low == "a" and not self._skip:
            self._anchor_href = dict(attrs).get("href")
            self._anchor_text = []

    def handle_endtag(self, tag: str) -> None:
        low = tag.lower()
        if low in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
        if low == "a" and self._anchor_href is not None:
            label = " ".join(self._anchor_text).strip()
            self.links.append((label, self._anchor_href))
            self._anchor_href = None
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        clean = " ".join(data.split())
        if clean:
            self.parts.append(clean)
            if self._anchor_href is not None:
                self._anchor_text.append(clean)

    def text(self, max_chars: int = 40_000) -> str:
        return "\n".join(self.parts)[:max_chars]


@dataclass(frozen=True, slots=True)
class BrowserState:
    mode: str
    url: str
    title: str


class BrowserHarness:
    """Local-first browser automation.

    When Playwright is installed, SKYNET gets interactive local Chromium tools.
    Without it, read-only HTTP navigation/snapshot remains available using only
    the standard library. No cloud browser is required by the core.
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._mode = "http-readonly"
        self._url = ""
        self._title = ""
        self._html = ""
        self._pw = None
        self._browser = None
        self._page = None
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
            self._sync_playwright = sync_playwright
            self._mode = "playwright-local"
        except Exception:
            self._sync_playwright = None

    @staticmethod
    def _validate_url(url: str) -> str:
        value = url.strip()
        parsed = parse.urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise BrowserError("Only absolute http/https URLs are allowed")
        return value

    def _ensure_page(self):
        if self._sync_playwright is None:
            raise BrowserError("Interactive browser requires optional Playwright. Read-only HTTP mode is still available.")
        if self._page is None:
            self._pw = self._sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=False)
            context = self._browser.new_context(accept_downloads=True)
            self._page = context.new_page()
        return self._page

    def state(self) -> BrowserState:
        return BrowserState(self._mode, self._url, self._title)

    def navigate(self, url: str) -> str:
        value = self._validate_url(url)
        if self._sync_playwright is not None:
            page = self._ensure_page()
            response = page.goto(value, wait_until="domcontentloaded", timeout=60_000)
            self._url = page.url
            self._title = page.title()
            code = response.status if response is not None else None
            return json.dumps({"mode": self._mode, "url": self._url, "title": self._title, "status": code}, ensure_ascii=False)

        req = request.Request(value, headers={"User-Agent": "SKYNET/0.9 local browser"})
        with request.urlopen(req, timeout=30) as response:
            body = response.read(2_000_000)
            content_type = response.headers.get_content_charset() or "utf-8"
            self._html = body.decode(content_type, errors="replace")
            self._url = response.geturl()
            match = re.search(r"<title[^>]*>(.*?)</title>", self._html, re.I | re.S)
            self._title = " ".join(re.sub(r"<[^>]+>", "", match.group(1)).split())[:300] if match else ""
            return json.dumps({"mode": self._mode, "url": self._url, "title": self._title, "status": getattr(response, "status", None)}, ensure_ascii=False)

    def snapshot(self, max_chars: int = 40_000) -> str:
        if self._sync_playwright is not None and self._page is not None:
            page = self._page
            text = page.locator("body").inner_text(timeout=10_000)[:max_chars]
            links = page.locator("a").evaluate_all("els => els.slice(0,100).map((e,i)=>({ref:'@a'+i,text:(e.innerText||'').trim(),href:e.href}))")
            return json.dumps({"url": page.url, "title": page.title(), "text": text, "links": links}, ensure_ascii=False)
        if not self._html:
            raise BrowserError("Navigate to a page first")
        parser = _TextExtractor()
        parser.feed(self._html)
        links = [{"ref": f"@a{i}", "text": label[:300], "href": parse.urljoin(self._url, href)}
                 for i, (label, href) in enumerate(parser.links[:100])]
        return json.dumps({"url": self._url, "title": self._title, "text": parser.text(max_chars), "links": links}, ensure_ascii=False)

    def back(self) -> str:
        page = self._ensure_page()
        page.go_back(wait_until="domcontentloaded", timeout=30_000)
        self._url = page.url
        self._title = page.title()
        return json.dumps({"url": self._url, "title": self._title}, ensure_ascii=False)

    def click(self, selector: str) -> str:
        page = self._ensure_page()
        clean = selector.strip()
        if not clean or len(clean) > 500:
            raise BrowserError("Invalid selector")
        page.locator(clean).first.click(timeout=15_000)
        page.wait_for_timeout(250)
        self._url = page.url
        self._title = page.title()
        return json.dumps({"clicked": clean, "url": self._url, "title": self._title}, ensure_ascii=False)

    def type_text(self, selector: str, text: str, submit: bool = False) -> str:
        page = self._ensure_page()
        clean = selector.strip()
        if not clean or len(clean) > 500:
            raise BrowserError("Invalid selector")
        locator = page.locator(clean).first
        locator.fill(text)
        if submit:
            locator.press("Enter")
            page.wait_for_timeout(250)
        self._url = page.url
        return json.dumps({"typed_chars": len(text), "submitted": bool(submit), "url": self._url}, ensure_ascii=False)

    def screenshot(self, relative_path: str = "screenshots/browser.png") -> str:
        page = self._ensure_page()
        target = (self.workspace / relative_path).resolve()
        target.relative_to(self.workspace)
        if target.suffix.lower() != ".png":
            raise BrowserError("Browser screenshots must be PNG")
        target.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(target), full_page=False)
        return str(target.relative_to(self.workspace))

    def close(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            self._browser = None
            self._page = None
            if self._pw is not None:
                self._pw.stop()
                self._pw = None
