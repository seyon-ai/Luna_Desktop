"""Generic browser automation through Playwright.

Not tied to any website. Primitives (navigate, tabs, read page, find/click/
type/press/scroll/screenshot/wait/verify) are the building blocks the agent
composes for any workflow — e.g. YouTube search works as:
navigate -> find search box by role/placeholder -> type -> press Enter ->
read results.

Playwright runs in a dedicated worker thread so tasks running on other threads
can drive the same browser without UI-thread restrictions.
"""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from typing import Any, Callable

from luna.config.config import BrowserConfig


class BrowserError(RuntimeError):
    pass


class PlaywrightBrowser:
    def __init__(self, config: BrowserConfig, profile_dir: Path | str) -> None:
        self.config = config
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._queue: queue.Queue[tuple[str, dict[str, Any], Any]] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._closed = False
        self._startup_error: str = ""

    # -- lifecycle ------------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="luna-browser", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=30.0):
            raise BrowserError("Browser worker did not start in time.")
        if self._startup_error:
            raise BrowserError(self._startup_error)

    def stop(self) -> None:
        self._closed = True
        self._queue.put(("__stop__", {}, None))
        if self._thread is not None:
            self._thread.join(timeout=10.0)
        self._thread = None

    def _call(self, op: str, **kwargs: Any) -> Any:
        if self._closed:
            raise BrowserError("Browser is stopped.")
        if self._thread is None or not self._thread.is_alive():
            self.start()
        future: threading.Event = threading.Event()
        result: dict[str, Any] = {}
        self._queue.put((op, kwargs, (future, result)))
        future.wait(timeout=kwargs.get("timeout", 90.0))
        if not future.is_set():
            raise BrowserError(f"Browser operation timed out: {op}")
        if "error" in result:
            raise BrowserError(f"Browser operation failed: {result['error']}")
        return result.get("value")

    # -- worker ---------------------------------------------------------------
    def _run(self) -> None:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
        except ImportError as exc:
            self._startup_error = (
                "Playwright is not installed. Install with: pip install luna-desktop[browser] "
                "and run: playwright install"
            )
            self._ready.set()
            return
        try:
            self._playwright = sync_playwright().start()
            launch_kwargs: dict[str, Any] = {"headless": self.config.headless}
            if self.config.channel in ("msedge", "chrome"):
                launch_kwargs["channel"] = self.config.channel
            if self.config.slow_mo_ms:
                launch_kwargs["slow_mo"] = self.config.slow_mo_ms
            try:
                self._browser = self._playwright.chromium.launch(**launch_kwargs)
            except Exception:  # noqa: BLE001
                if self.config.channel in ("msedge", "chrome"):
                    launch_kwargs.pop("channel", None)
                    self._browser = self._playwright.chromium.launch(**launch_kwargs)
                else:
                    raise
            self._context = self._browser.new_context(
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
                locale="en-US",
            )
            self._page: Any = None
            self._ready.set()
            self._consume()
        except Exception as exc:  # noqa: BLE001
            self._startup_error = f"{exc}"
            self._ready.set()

    def _consume(self) -> None:
        handlers: dict[str, Callable[..., Any]] = {
            "navigate": self._navigate,
            "open_tab": self._open_tab,
            "list_tabs": self._list_tabs,
            "close_tab": self._close_tab,
            "switch_tab": self._switch_tab,
            "read_page": self._read_page,
            "find": self._find,
            "click": self._click,
            "type": self._type,
            "press": self._press,
            "scroll": self._scroll,
            "wait": self._wait,
            "screenshot": self._screenshot,
            "go_back": self._go_back,
            "extract": self._extract,
            "close_all_tabs": self._close_all_tabs,
            "__stop__": self._shutdown,
        }
        while not self._closed:
            try:
                op, kwargs, reply = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if op == "__stop__" or self._closed:
                self._shutdown()
                return
            future, result = reply
            try:
                result["value"] = handlers[op](**kwargs)
            except Exception as exc:  # noqa: BLE001
                result["error"] = str(exc)
            finally:
                future.set()

    def _shutdown(self) -> None:
        for ctx_name in ("_context",):
            ctx = getattr(self, ctx_name, None)
            if ctx is not None:
                try:
                    ctx.close()
                except Exception:  # noqa: BLE001
                    pass
        browser = getattr(self, "_browser", None)
        if browser is not None:
            try:
                browser.close()
            except Exception:  # noqa: BLE001
                pass
        pw = getattr(self, "_playwright", None)
        if pw is not None:
            try:
                pw.stop()
            except Exception:  # noqa: BLE001
                pass

    # -- page helpers --------------------------------------------------------------
    def _page(self) -> Any:
        if self._page is None or self._page.is_closed():
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return self._page

    # -- operations ---------------------------------------------------------------------
    def _navigate(self, url: str, wait: bool = True) -> dict[str, Any]:
        if not url.startswith(("http://", "https://", "file://", "about:")):
            url = "https://" + url
        page = self._page()
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        if wait:
            page.wait_for_load_state("networkidle", timeout=10_000)  # tolerates slow pages
        return {"url": page.url, "title": page.title()}

    def _open_tab(self, url: str | None = None) -> dict[str, Any]:
        page = self._context.new_page()
        if url:
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        self._page = page
        return {"url": page.url, "title": page.title()}

    def _list_tabs(self) -> list[dict[str, Any]]:
        return [{"index": i, "url": p.url, "title": p.title()} for i, p in enumerate(self._context.pages)]

    def _close_tab(self, index: int | None = None) -> dict[str, Any]:
        pages = self._context.pages
        if index is not None:
            target = pages[index]
        else:
            target = self._page()
        target.close()
        remaining = [p for p in pages if not p.is_closed()]
        self._page = remaining[-1] if remaining else None
        return {"closed": True, "remaining": len(remaining)}

    def _close_all_tabs(self) -> dict[str, Any]:
        for page in list(self._context.pages):
            try:
                page.close()
            except Exception:  # noqa: BLE001
                continue
        self._page = None
        return {"closed": True}

    def _switch_tab(self, index: int) -> dict[str, Any]:
        page = self._context.pages[index]
        page.bring_to_front()
        self._page = page
        return {"url": page.url, "title": page.title()}

    def _read_page(self, max_chars: int = 8000) -> dict[str, Any]:
        page = self._page()
        title = page.title()
        url = page.url
        content = page.locator("body").inner_text(timeout=10_000)[:max_chars]
        return {"url": url, "title": title, "text": content}

    def _find(self, selector: str | None = None, role: str | None = None, name: str | None = None, placeholder: str | None = None) -> list[dict[str, Any]]:
        page = self._page()
        if selector:
            loc = page.locator(selector)
        else:
            conditions = []
            if role:
                conditions.append(f'[role="{role}"]')
            if name:
                conditions.append(f'text="{name}"')
            if placeholder:
                conditions.append(f'[placeholder="{placeholder}"]')
            if not conditions:
                raise BrowserError("find requires selector, role, name or placeholder.")
            loc = page.locator(" , ".join(conditions))
        count = min(loc.count(), 100)
        results = []
        for i in range(count):
            el = loc.nth(i)
            try:
                box = el.bounding_box()
                results.append(
                    {
                        "index": i,
                        "tag": el.evaluate("(n) => n.tagName"),
                        "text": (el.inner_text(timeout=2000) or "")[:300],
                        "placeholder": el.get_attribute("placeholder") or "",
                        "box": box,
                    }
                )
            except Exception:  # noqa: BLE001
                continue
        return results

    def _click(self, selector: str | None = None, role: str | None = None, name: str | None = None, index: int = 0) -> dict[str, Any]:
        page = self._page()
        if selector:
            loc = page.locator(selector)
        elif role and name:
            loc = page.get_by_role(role, name=name, exact=False)
        elif name and not role:
            loc = page.get_by_text(name, exact=False)
        else:
            raise BrowserError("click requires a selector or role+name.")
        el = loc.nth(index)
        el.scroll_into_view_if_needed(timeout=5000)
        el.click(timeout=10_000)
        return {"ok": True, "url": page.url, "title": page.title()}

    def _type(self, text: str, selector: str | None = None, role: str | None = None, placeholder: str | None = None, clear: bool = True, press_enter: bool = False) -> dict[str, Any]:
        page = self._page()
        if selector:
            box = page.locator(selector)
        elif role:
            box = page.get_by_role(role, exact=False)
        elif placeholder:
            box = page.locator(f'[placeholder="{placeholder}"]')
        else:
            raise BrowserError("type requires a selector, role or placeholder.")
        box = box.first
        if clear:
            box.fill("")
        box.type(text, delay=30)
        if press_enter:
            box.press("Enter")
        return {"ok": True, "url": page.url, "title": page.title()}

    def _press(self, key: str) -> dict[str, Any]:
        page = self._page()
        page.keyboard.press(key)
        return {"ok": True, "key": key}

    def _scroll(self, amount: int = 600) -> dict[str, Any]:
        page = self._page()
        page.mouse.wheel(0, int(amount))
        return {"ok": True, "amount": amount}

    def _wait(self, selector: str | None = None, url_contains: str | None = None, seconds: float = 2.0) -> dict[str, Any]:
        page = self._page()
        if selector:
            page.locator(selector).first.wait_for(state="visible", timeout=15_000)
        if url_contains:
            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                if url_contains in page.url:
                    return {"ok": True, "url": page.url, "title": page.title()}
                time.sleep(0.25)
            raise BrowserError(f"Timed out waiting for URL containing '{url_contains}'.")
        time.sleep(max(0.0, seconds))
        return {"ok": True, "url": page.url, "title": page.title()}

    def _screenshot(self, path: str, full_page: bool = False) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._page().screenshot(path=str(target), full_page=full_page)
        return str(target)

    def _go_back(self) -> dict[str, Any]:
        page = self._page()
        page.go_back(wait_until="domcontentloaded")
        return {"url": page.url, "title": page.title()}

    def _extract(self, selector: str | None = None, role: str | None = None, name: str | None = None, max_items: int = 100) -> list[str]:
        page = self._page()
        if selector:
            loc = page.locator(selector)
        elif role:
            loc = page.get_by_role(role)
        elif name:
            loc = page.get_by_text(name)
        else:
            raise BrowserError("extract requires a selector, role or name.")
        items = []
        for i in range(min(loc.count(), max_items)):
            try:
                items.append(loc.nth(i).inner_text(timeout=2000)[:500])
            except Exception:  # noqa: BLE001
                break
        return items

    # -- public API ------------------------------------------------------------------------
    def navigate(self, url: str) -> dict[str, Any]:
        return self._call("navigate", url=url)

    def open_tab(self, url: str | None = None) -> dict[str, Any]:
        return self._call("open_tab", url=url)

    def list_tabs(self) -> list[dict[str, Any]]:
        return self._call("list_tabs")

    def close_tab(self, index: int | None = None) -> dict[str, Any]:
        return self._call("close_tab", index=index)

    def switch_tab(self, index: int) -> dict[str, Any]:
        return self._call("switch_tab", index=index)

    def read_page(self, max_chars: int = 8000) -> dict[str, Any]:
        return self._call("read_page", max_chars=max_chars)

    def find(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self._call("find", **kwargs)

    def click(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("click", **kwargs)

    def type_text(self, text: str, **kwargs: Any) -> dict[str, Any]:
        return self._call("type", text=text, **kwargs)

    def press(self, key: str) -> dict[str, Any]:
        return self._call("press", key=key)

    def scroll(self, amount: int = 600) -> dict[str, Any]:
        return self._call("scroll", amount=amount)

    def wait(self, **kwargs: Any) -> dict[str, Any]:
        return self._call("wait", **kwargs)

    def screenshot(self, path: str, full_page: bool = False) -> str:
        return self._call("screenshot", path=path, full_page=full_page)

    def go_back(self) -> dict[str, Any]:
        return self._call("go_back")

    def extract(self, **kwargs: Any) -> list[str]:
        return self._call("extract", **kwargs)
