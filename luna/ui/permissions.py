"""Permission approval bridge: worker threads request, UI thread responds."""

from __future__ import annotations

import threading
from typing import Any

from PySide6.QtCore import QObject, Signal

from luna.core.permissions import PermissionRequest


class ApprovalBridge(QObject):
    """Handshake between the blocking permission layer and the Qt UI."""

    requested = Signal(object)  # payload: (requests, event, responses)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pending: list[tuple[threading.Event, dict[str, Any]]] = []

    def callback(self, requests: list[PermissionRequest]) -> dict[str, bool]:
        """Blocking callback passed to PermissionManager. Safe from any thread."""
        event = threading.Event()
        responses: dict[str, Any] = {}
        with _LOCK:
            self._pending.append((event, responses))
        self.requested.emit((requests, event, responses))
        event.wait(timeout=600.0)
        with _LOCK:
            self._pending.remove((event, responses))
        return {r.action: bool(responses.get(r.action, {}).get("allowed", False)) for r in requests}

    def respond(self, event: threading.Event, responses: dict[str, Any]) -> None:
        """Called by the UI thread after emitting requested()."""
        event.set()


_LOCK = threading.Lock()
