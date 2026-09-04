"""Configurable permission layer for high-impact actions.

Decision modes: ``allow``, ``ask`` (callback to UI, defaults to deny when no
UI is attached), ``deny``. A default applies when no per-action rule exists.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable

from luna.config.config import PermissionConfig


class PermissionDenied(Exception):
    """Raised when an action is explicitly denied."""


@dataclass
class PermissionRequest:
    action: str
    description: str
    details: dict[str, Any]
    rule: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "description": self.description,
            "details": self.details,
            "rule": self.rule,
        }


@dataclass
class PermissionDecision:
    allowed: bool
    reason: str = ""


ApprovalCallback = Callable[[list[PermissionRequest]], dict[str, bool]]


class PermissionManager:
    """Resolves and records permission decisions.

    The UI registers an approval callback; headless callers may use the
    built-in deterministic strategies for tests.
    """

    HIGH_IMPACT = {"delete_file", "send_message", "submit_form", "purchase", "system_config"}

    def __init__(self, config: PermissionConfig | None = None) -> None:
        self.config = config or PermissionConfig()
        self._approval: ApprovalCallback | None = None
        self._lock = threading.RLock()
        self.log: list[PermissionRequest] = []

    def register_approval_callback(self, callback: ApprovalCallback | None) -> None:
        self._approval = callback

    def rule_for(self, action: str) -> str:
        return self.config.rules.get(action, self.config.default)

    def check(self, action: str, description: str = "", details: dict[str, Any] | None = None) -> bool:
        rule = self.rule_for(action)
        if rule == "allow":
            return True
        if rule == "deny":
            raise PermissionDenied(f"{action} is denied by the permission policy.")
        return self.ask(action, description, details or {})

    def ask(
        self,
        action: str,
        description: str = "",
        details: dict[str, Any] | None = None,
    ) -> bool:
        rule = self.rule_for(action)
        request = PermissionRequest(
            action=action, description=description or action, details=details or {}, rule=rule
        )
        with self._lock:
            self.log.append(request)
            if len(self.log) > 500:
                self.log = self.log[-500:]
        callback = self._approval
        if callback is None:
            raise PermissionDenied(
                f"No approval UI is attached; refusing '{action}' (rule: {rule})."
            )
        decisions = callback([request]) or {}
        decision = decisions.get(request.action, {"allowed": False})
        if isinstance(decision, bool):
            allowed = decision
        elif isinstance(decision, dict):
            allowed = bool(decision.get("allowed"))
        else:
            allowed = bool(decision)
        if not allowed:
            raise PermissionDenied(f"User denied '{action}': {description}")
        return True

    def update_rules(self, rules: dict[str, str]) -> None:
        with self._lock:
            self.config.rules.update(rules)
