from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib import request, parse
import json
import re
import threading


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
        if low in {"script", "style", "noscript"}: self._skip += 1
        if low == "a" and not self._skip:
            self._anchor_href = dict(attrs).get("href"); self._anchor_text = []

    def handle_endtag(self, tag: str) -> None:
        low = tag.lower()
        if low in {"script", "style", "noscript"} and self._skip: self._skip -= 1
        if low == "a" and self._anchor_href is not None:
            self.links.append((" ".join(self._anchor_text).strip(), self._anchor_href))
            self._anchor_href = None; self._anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._skip: return
        clean = " ".join(data.split())
        if clean:
            self.parts.append(clean)
            if self._anchor_href is not None: self._anchor_text.append(clean)

    def text(self, max_chars: int = 40_000) -> str:
        return "\n".join(self.parts)[:max_chars]


@dataclass(frozen=True, slots=True)
class BrowserState:
    mode: str
    url: str
    title: str


class BrowserHarness:
    """Local-first browser automation with a dedicated interactive worker.

    Playwright objects never cross threads. This matters because Desktop chat,
    autonomy and channel bridges may call the same Runtime from different worker
    threads. Without Playwright, dependency-free read-only HTTP mode remains.
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve(); self.workspace.mkdir(parents=True, exist_ok=True)
        self._mode = "http-readonly"; self._url = ""; self._title = ""; self._html = ""
        self._state_lock = threading.RLock()
        self._executor: ThreadPoolExecutor | None = None
        self._pw = None; self._browser = None; self._page = None
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
            self._sync_playwright = sync_playwright
            self._mode = "playwright-local"
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="skynet-browser")
        except Exception:
            self._sync_playwright = None

    @staticmethod
    def _validate_url(url: str) -> str:
        value = url.strip(); parsed = parse.urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise BrowserError("Only absolute http/https URLs are allowed")
        return value

    def _interactive(self, fn, *args):
        if self._executor is None:
            raise BrowserError("Interactive browser requires optional Playwright. Read-only HTTP mode is still available.")
        return self._executor.submit(fn, *args).result()

    def _ensure_page_worker(self):
        if self._sync_playwright is None:
            raise BrowserError("Playwright is unavailable")
        if self._page is None:
            self._pw = self._sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=False)
            context = self._browser.new_context(accept_downloads=True)
            self._page = context.new_page()
        return self._page

    def state(self) -> BrowserState:
        with self._state_lock:
            return BrowserState(self._mode, self._url, self._title)

    def _navigate_worker(self, value: str) -> str:
        page = self._ensure_page_worker()
        response = page.goto(value, wait_until="domcontentloaded", timeout=60_000)
        with self._state_lock:
            self._url = page.url; self._title = page.title()
            state = {"mode": self._mode, "url": self._url, "title": self._title, "status": response.status if response else None}
        return json.dumps(state, ensure_ascii=False)

    def navigate(self, url: str) -> str:
        value = self._validate_url(url)
        if self._executor is not None:
            return self._interactive(self._navigate_worker, value)
        req = request.Request(value, headers={"User-Agent": "SKYNET/0.9 local browser"})
        with request.urlopen(req, timeout=30) as response:
            body = response.read(2_000_000); charset = response.headers.get_content_charset() or "utf-8"
            html = body.decode(charset, errors="replace"); final_url = response.geturl()
            match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            title = " ".join(re.sub(r"<[^>]+>", "", match.group(1)).split())[:300] if match else ""
            with self._state_lock:
                self._html = html; self._url = final_url; self._title = title
            return json.dumps({"mode": self._mode, "url": final_url, "title": title, "status": getattr(response, "status", None)}, ensure_ascii=False)

    def _snapshot_worker(self, max_chars: int) -> str:
        page = self._ensure_page_worker()
        text = page.locator("body").inner_text(timeout=10_000)[:max_chars]
        links = page.locator("a").evaluate_all("els => els.slice(0,100).map((e,i)=>({ref:'@a'+i,text:(e.innerText||'').trim(),href:e.href}))")
        with self._state_lock:
            self._url = page.url; self._title = page.title()
        return json.dumps({"url": page.url, "title": page.title(), "text": text, "links": links}, ensure_ascii=False)

    def snapshot(self, max_chars: int = 40_000) -> str:
        if self._executor is not None:
            return self._interactive(self._snapshot_worker, max_chars)
        with self._state_lock:
            html = self._html; url = self._url; title = self._title
        if not html: raise BrowserError("Navigate to a page first")
        parser = _TextExtractor(); parser.feed(html)
        links = [{"ref": f"@a{i}", "text": label[:300], "href": parse.urljoin(url, href)} for i, (label, href) in enumerate(parser.links[:100])]
        return json.dumps({"url": url, "title": title, "text": parser.text(max_chars), "links": links}, ensure_ascii=False)

    def _back_worker(self) -> str:
        page = self._ensure_page_worker(); page.go_back(wait_until="domcontentloaded", timeout=30_000)
        with self._state_lock: self._url = page.url; self._title = page.title()
        return json.dumps({"url": page.url, "title": page.title()}, ensure_ascii=False)

    def back(self) -> str: return self._interactive(self._back_worker)

    def _click_worker(self, selector: str) -> str:
        page = self._ensure_page_worker(); page.locator(selector).first.click(timeout=15_000); page.wait_for_timeout(250)
        with self._state_lock: self._url = page.url; self._title = page.title()
        return json.dumps({"clicked": selector, "url": page.url, "title": page.title()}, ensure_ascii=False)

    def click(self, selector: str) -> str:
        clean = selector.strip()
        if not clean or len(clean) > 500: raise BrowserError("Invalid selector")
        return self._interactive(self._click_worker, clean)

    def _type_worker(self, selector: str, text: str, submit: bool) -> str:
        page = self._ensure_page_worker(); locator = page.locator(selector).first; locator.fill(text)
        if submit: locator.press("Enter"); page.wait_for_timeout(250)
        with self._state_lock: self._url = page.url; self._title = page.title()
        return json.dumps({"typed_chars": len(text), "submitted": submit, "url": page.url}, ensure_ascii=False)

    def type_text(self, selector: str, text: str, submit: bool = False) -> str:
        clean = selector.strip()
        if not clean or len(clean) > 500: raise BrowserError("Invalid selector")
        return self._interactive(self._type_worker, clean, text, bool(submit))

    def _screenshot_worker(self, target: Path) -> str:
        page = self._ensure_page_worker(); target.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(target), full_page=False)
        return str(target.relative_to(self.workspace))

    def screenshot(self, relative_path: str = "screenshots/browser.png") -> str:
        target = (self.workspace / relative_path).resolve(); target.relative_to(self.workspace)
        if target.suffix.lower() != ".png": raise BrowserError("Browser screenshots must be PNG")
        return self._interactive(self._screenshot_worker, target)

    def _close_worker(self) -> None:
        try:
            if self._browser is not None: self._browser.close()
        finally:
            self._browser = None; self._page = None
            if self._pw is not None: self._pw.stop(); self._pw = None

    def close(self) -> None:
        if self._executor is not None:
            try: self._interactive(self._close_worker)
            finally:
                self._executor.shutdown(wait=True, cancel_futures=True); self._executor = None
