"""Persistent task model. Every long-running goal is executed as a task."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable

from luna.storage.db import new_id, utcnow


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class TaskLog:
    ts: str
    level: str
    message: str
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"ts": self.ts, "level": self.level, "message": self.message, "data": self.data}


@dataclass
class Task:
    id: str
    goal: str
    status: TaskStatus = TaskStatus.QUEUED
    progress: float = 0.0
    current_step: str = ""
    created_at: str = field(default_factory=utcnow)
    updated_at: str = field(default_factory=utcnow)
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    logs: list[TaskLog] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["logs"] = [log.to_dict() for log in self.logs]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        logs = [TaskLog(**log) for log in data.get("logs", [])]
        return cls(
            id=data["id"],
            goal=data["goal"],
            status=TaskStatus(data.get("status", TaskStatus.QUEUED.value)),
            progress=float(data.get("progress", 0.0)),
            current_step=data.get("current_step", ""),
            created_at=data.get("created_at", utcnow()),
            updated_at=data.get("updated_at", utcnow()),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            result=data.get("result"),
            error=data.get("error"),
            logs=logs,
        )


class TaskCancelled(Exception):
    """Raised cooperatively when a task is cancelled."""


class RunContext:
    """Cooperative control surface passed to task runners."""

    def __init__(self, task: Task, on_progress: Callable[[Task], None]) -> None:
        self.task = task
        self._on_progress = on_progress
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._cleanups: list[Callable[[], None]] = []
        self._lock = threading.RLock()

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @property
    def paused(self) -> bool:
        return self._pause_event.is_set()

    def cancel(self) -> None:
        self._cancel_event.set()
        self._pause_event.clear()
        self._run_cleanups()

    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def check_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise TaskCancelled("Task was cancelled by the user.")

    def checkpoint(self) -> None:
        self.check_cancelled()
        if self._pause_event.is_set():
            self._notify(status=TaskStatus.PAUSED)
            self._pause_event.wait(timeout=0.3)  # re-check cancel frequently
            self.check_cancelled()
            self._notify(status=TaskStatus.RUNNING)

    def set_progress(self, progress: float, step: str = "") -> None:
        self.checkpoint()
        with self._lock:
            self.task.progress = max(0.0, min(100.0, float(progress)))
            if step:
                self.task.current_step = step
            self.task.updated_at = utcnow()
        self._on_progress(self.task)

    def log(self, message: str, level: str = "info", data: dict[str, Any] | None = None) -> None:
        with self._lock:
            self.task.logs.append(TaskLog(ts=utcnow(), level=level, message=message, data=data))
            if len(self.task.logs) > 2000:
                self.task.logs = self.task.logs[-2000:]
            self.task.updated_at = utcnow()
        self._on_progress(self.task)

    def wait_for_user(self, question: str) -> Any:
        """Block until a registered approval callback answers. Raises TaskCancelled on cancel."""
        self.check_cancelled()
        self._notify(status=TaskStatus.WAITING_FOR_USER)
        raise NotImplementedError(
            "RunContext.wait_for_user is replaced by register_approval_handler; see AgentContext."
        )

    def register_cleanup(self, callback: Callable[[], None]) -> None:
        self._cleanups.append(callback)

    def _run_cleanups(self) -> None:
        with self._lock:
            cleanups = list(self._cleanups)
            self._cleanups.clear()
        for cleanup in cleanups:
            try:
                cleanup()
            except Exception:
                pass

    def _notify(self, status: TaskStatus | None = None) -> None:
        with self._lock:
            if status is not None and self.task.status != status:
                self.task.status = status
            self.task.updated_at = utcnow()
        self._on_progress(self.task)
