"""Desktop automation capabilities contract.

The Windows implementation (uiautomation + pyautogui) satisfies this contract.
The interface keeps the automation layer modular and testable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WindowInfo:
    handle: int
    title: str
    process: str = ""
    minimized: bool = False
    visible: bool = True
    rect: tuple[int, int, int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "title": self.title,
            "process": self.process,
            "minimized": self.minimized,
            "visible": self.visible,
            "rect": list(self.rect) if self.rect else None,
        }


@dataclass
class AccessibleElement:
    role: str
    name: str = ""
    control_type: str = ""
    automation_id: str = ""
    rect: tuple[int, int, int, int] | None = None
    enabled: bool = True
    attributes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "name": self.name,
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "rect": list(self.rect) if self.rect else None,
            "enabled": self.enabled,
            "attributes": self.attributes,
        }


@dataclass
class ScreenState:
    title: str
    process: str = ""
    elements: list[AccessibleElement] = field(default_factory=list)
    text: str = ""
    screenshot_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "process": self.process,
            "elements": [e.to_dict() for e in self.elements],
            "text": self.text,
            "screenshot_path": self.screenshot_path,
        }


class DesktopAutomation(ABC):
    @abstractmethod
    def list_windows(self) -> list[WindowInfo]:
        ...

    @abstractmethod
    def focus_window(self, title: str | None = None, handle: int | None = None) -> WindowInfo:
        ...

    @abstractmethod
    def minimize_window(self, title: str | None = None, handle: int | None = None) -> bool:
        ...

    @abstractmethod
    def maximize_window(self, title: str | None = None, handle: int | None = None) -> bool:
        ...

    @abstractmethod
    def read_accessible_ui(self, max_elements: int = 250) -> ScreenState:
        ...

    @abstractmethod
    def click(self, x: int | None = None, y: int | None = None, element: AccessibleElement | None = None) -> dict[str, Any]:
        ...

    @abstractmethod
    def type_text(self, text: str, delay_ms: int = 20) -> dict[str, Any]:
        ...

    @abstractmethod
    def press_key(self, key: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def hotkey(self, keys: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def scroll(self, amount: int, x: int | None = None, y: int | None = None) -> dict[str, Any]:
        ...

    @abstractmethod
    def screenshot(self, path: str) -> str:
        ...

    @abstractmethod
    def copy(self) -> str:
        ...

    @abstractmethod
    def paste(self, text: str | None = None) -> dict[str, Any]:
        ...

    def open_application(self, name: str) -> dict[str, Any]:
        raise NotImplementedError

    def close_application(self, name: str) -> bool:
        raise NotImplementedError
