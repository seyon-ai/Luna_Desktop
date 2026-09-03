"""Approval bridge handshake (Qt objects, no GUI loop required)."""

from __future__ import annotations

import threading

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from luna.core.permissions import PermissionManager, PermissionRequest  # noqa: E402
from luna.ui.permissions import ApprovalBridge  # noqa: E402


def test_bridge_direct_connection():
    bridge = ApprovalBridge()
    answers: dict[str, bool] = {}

    def on_request(payload):
        requests, event, responses = payload
        responses[requests[0].action] = {"allowed": True}
        bridge.respond(event, responses)

    bridge.requested.connect(on_request)
    result = bridge.callback([PermissionRequest("delete_file", "Delete report", {}, "ask")])
    assert result == {"delete_file": True}


def test_permission_manager_with_bridge():
    bridge = ApprovalBridge()
    pm = PermissionManager()
    pm.config.rules["send_message"] = "ask"
    pm.register_approval_callback(bridge.callback)
    bridge.requested.connect(
        lambda payload: bridge.respond(
            payload[1],
            {payload[0][0].action: {"allowed": False}},
        )
    )
    import pytest as _pytest

    from luna.core.permissions import PermissionDenied

    with _pytest.raises(PermissionDenied):
        pm.ask("send_message")
