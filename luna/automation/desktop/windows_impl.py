"""Windows desktop automation using UI Automation plus keyboard/mouse fallback.

Prefers accessibility where available; pixel coordinates are only a fallback.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from luna.automation.desktop.contract import (
    AccessibleElement,
    DesktopAutomation,
    ScreenState,
    WindowInfo,
)


class DesktopUnavailable(RuntimeError):
    pass


class WindowsDesktopAutomation(DesktopAutomation):
    def __init__(self, keyboard_delay_ms: int = 20) -> None:
        if not sys.platform.startswith("win"):
            raise DesktopUnavailable("Windows desktop automation is available only on Windows.")
        try:
            import uiautomation as auto  # type: ignore[import-not-found]
            import pyautogui  # type: ignore[import-not-found]
            import pyperclip  # type: ignore[import-not-found]
        except ImportError as exc:
            raise DesktopUnavailable(
                "Desktop automation dependencies are missing. "
                "Install with: pip install luna-desktop[desktop]"
            ) from exc
        self._auto = auto
        self._pg = pyautogui
        self._clip = pyperclip
        self._pg.FAILSAFE = True
        self.keyboard_delay_ms = keyboard_delay_ms

    # -- windows -------------------------------------------------------------
    def list_windows(self) -> list[WindowInfo]:
        windows: list[WindowInfo] = []
        root = self._auto.GetRootControl()
        for child in root.GetChildren():
            try:
                if not child.IsWindow:
                    continue
                handle = child.NativeWindowHandle
                title = child.Name or ""
                if not title and handle:
                    continue
                windows.append(
                    WindowInfo(
                        handle=handle,
                        title=title,
                        process=self._process_name(handle),
                        minimized=self._auto.IsIconic(handle),
                    )
                )
            except Exception:  # noqa: BLE001
                continue
        return windows

    def _find_window(self, title: str | None, handle: int | None) -> Any:
        if handle:
            for window in self.list_windows():
                if window.handle == handle:
                    return self._auto.WindowControl(searchDepth=1, Name=window.title)
        if title:
            normalized = title.lower()
            for window in self.list_windows():
                if normalized in window.title.lower():
                    return self._auto.WindowControl(searchDepth=1, Name=window.title)
        raise LookupError(f"No window found: title={title!r} handle={handle!r}")

    def focus_window(self, title=None, handle=None) -> WindowInfo:
        window = self._find_window(title, handle)
        window.SetActive()
        time.sleep(0.15)
        for w in self.list_windows():
            if w.title == window.Name:
                return w
        raise LookupError("Window was activated but could not be re-read.")

    def minimize_window(self, title=None, handle=None) -> bool:
        window = self._find_window(title, handle)
        self._auto.MinimizeWindow(window.NativeWindowHandle)
        return True

    def maximize_window(self, title=None, handle=None) -> bool:
        window = self._find_window(title, handle)
        window.Maximize()
        return True

    def _process_name(self, handle: int) -> str:
        try:
            import win32process  # type: ignore[import-not-found]

            _, pid = win32process.GetWindowThreadProcessId(handle)
            return subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            ).strip().split('","')[0].strip('"')
        except Exception:  # noqa: BLE001
            return ""

    # -- accessibility --------------------------------------------------------
    def read_accessible_ui(self, max_elements: int = 250) -> ScreenState:
        root = self._auto.GetRootControl()
        focused = root.GetFocusedControl()
        window = focused or root.GetTopLevelControl()
        title = window.Name if window else ""
        elements: list[AccessibleElement] = []
        try:
            for ctrl in window.GetChildren() if window else []:
                if len(elements) >= max_elements:
                    break
                if ctrl.Name or ctrl.ControlTypeName != "PaneControl":
                    elements.append(self._to_element(ctrl))
                for child in ctrl.GetChildren():
                    if len(elements) >= max_elements:
                        break
                    if child.Name:
                        elements.append(self._to_element(child))
        except Exception:  # noqa: BLE001
            pass
        text = "\n".join(f"{e.role}: {e.name}" for e in elements if e.name)
        return ScreenState(title=title, elements=elements, text=text)

    def _to_element(self, ctrl: Any) -> AccessibleElement:
        rect = ctrl.BoundingRectangle
        box = (rect.left, rect.top, rect.right, rect.bottom) if rect else None
        return AccessibleElement(
            role=ctrl.ControlTypeName,
            name=ctrl.Name or "",
            control_type=ctrl.ControlTypeName,
            automation_id=f"{ctrl.AutomationId if hasattr(ctrl, 'AutomationId') else ''}",
            rect=box,
            enabled=bool(ctrl.IsEnabled if hasattr(ctrl, "IsEnabled") else True),
            attributes={"class": ctrl.ClassName if hasattr(ctrl, "ClassName") else ""},
        )

    # -- input -----------------------------------------------------------------
    def click(self, x=None, y=None, element=None) -> dict[str, Any]:
        if element is not None and element.rect:
            x, y = self._center(element.rect)
        if x is None or y is None:
            raise ValueError("click requires coordinates or an element with a bounding rectangle.")
        self._pg.click(x, y)
        return {"ok": True, "x": int(x), "y": int(y)}

    @staticmethod
    def _center(rect: tuple[int, int, int, int]) -> tuple[int, int]:
        left, top, right, bottom = rect
        return int((left + right) / 2), int((top + bottom) / 2)

    def type_text(self, text, delay_ms=20) -> dict[str, Any]:
        self._pg.typewrite(text, interval=delay_ms / 1000.0)
        return {"ok": True, "text": text}

    def press_key(self, key: str) -> dict[str, Any]:
        self._pg.press(key)
        return {"ok": True, "key": key}

    def hotkey(self, keys: str) -> dict[str, Any]:
        parts = [p.strip() for p in keys.split("+")]
        self._pg.hotkey(*parts)
        return {"ok": True, "keys": keys}

    def scroll(self, amount: int, x=None, y=None) -> dict[str, Any]:
        if x is None or y is None:
            x, y = self._pg.position()
        self._pg.scroll(int(amount), x=x, y=y)
        return {"ok": True, "amount": amount}

    def screenshot(self, path: str) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._pg.screenshot(str(target))
        return str(target)

    def copy(self) -> str:
        self._pg.hotkey("ctrl", "c")
        self._pg.PAUSE = 0.1
        time.sleep(0.1)
        return self._clip.paste()

    def paste(self, text=None) -> dict[str, Any]:
        if text is not None:
            self._clip.copy(text)
        self._pg.hotkey("ctrl", "v")
        return {"ok": True}

    # -- apps --------------------------------------------------------------------
    def open_application(self, name: str) -> dict[str, Any]:
        """Open an installed Windows application by name (Start menu search)."""
        safe = "".join(c for c in name if c.isalnum() or c in " -_.").strip()
        if not safe:
            raise ValueError("Invalid application name.")
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", f"Start-Process '{safe}'"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        time.sleep(2.0)
        return {"ok": True, "application": safe}
