"""Task page: live task cards with pause/resume/stop, logs and results."""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from luna.core.tasks.models import Task, TaskStatus
from luna.ui.common import faint, h1, muted, status_pill


class TaskBridge(QObject):
    updated = Signal(object)


class TaskPage(QWidget):
    def __init__(self, app: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self.bridge = TaskBridge()
        self.task_rows: dict[str, list[QWidget]] = {}
        self._build()
        self.app.tasks.add_listener(self._on_task)
        self.bridge.updated.connect(lambda _task: self.refresh())

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.addWidget(h1("Tasks"))
        header.addStretch(1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        layout.addLayout(header)
        hint = muted("Long-running goals run as tasks and continue while LUNA is in the tray.")
        layout.addWidget(hint)
        self.list = QListWidget()
        self.list.setSpacing(0)
        layout.addWidget(self.list, 1)
        self.refresh()

    def _on_task(self, task: Task) -> None:
        self.bridge.updated.emit(task)

    def refresh(self) -> None:
        self.list.clear()
        self.task_rows.clear()
        for task in self.app.tasks.list_tasks(100):
            item = QListWidgetItem()
            widget = self._task_widget(task)
            item.setSizeHint(widget.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, widget)

    def _task_widget(self, task: Task) -> QWidget:
        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(12, 8, 12, 8)
        row = QHBoxLayout()
        goal = QLabel(task.goal[:90])
        goal.setObjectName("h2")
        row.addWidget(goal)
        row.addStretch(1)
        row.addWidget(status_pill(task.status.value))
        box.addLayout(row)
        meta = QLabel(f"{task.id[:12]}  ·  step: {task.current_step or '—'}")
        meta.setObjectName("faint")
        box.addWidget(meta)
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(int(task.progress))
        box.addWidget(progress)
        actions = QHBoxLayout()
        if task.status == TaskStatus.RUNNING:
            pause = QPushButton("Pause")
            pause.clicked.connect(lambda _=False, t=task.id: self.app.tasks.pause(t))
            actions.addWidget(pause)
        elif task.status == TaskStatus.PAUSED:
            resume = QPushButton("Resume")
            resume.clicked.connect(lambda _=False, t=task.id: self.app.tasks.resume(t))
            actions.addWidget(resume)
        if task.status in (
            TaskStatus.QUEUED,
            TaskStatus.RUNNING,
            TaskStatus.PAUSED,
            TaskStatus.WAITING_FOR_USER,
        ):
            stop = QPushButton("Stop")
            stop.setObjectName("danger")
            stop.clicked.connect(lambda _=False, t=task.id: self.app.tasks.cancel(t))
            actions.addWidget(stop)
        logs = QPushButton("View Logs")
        logs.clicked.connect(lambda _=False, t=task: self._show_logs(t))
        actions.addWidget(logs)
        if task.result:
            result = QPushButton("View Result")
            result.clicked.connect(lambda _=False, t=task: self._show_result(t))
            actions.addWidget(result)
        actions.addStretch(1)
        box.addLayout(actions)
        return container

    def _show_logs(self, task: Task) -> None:
        lines = [f"{log.ts} [{log.level}] {log.message}" for log in task.logs[-200:]]
        text = "\n".join(lines) or "(no logs)"
        self._show_dialog(f"Logs — {task.id[:12]}", text)

    def _show_result(self, task: Task) -> None:
        text = json.dumps(task.result, indent=2, ensure_ascii=False)
        self._show_dialog(f"Result — {task.id[:12]}", text)

    def _show_dialog(self, title: str, text: str) -> None:
        from PySide6.QtWidgets import QDialog, QPlainTextEdit, QVBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(680, 420)
        box = QVBoxLayout(dialog)
        view = QPlainTextEdit()
        view.setPlainText(text)
        view.setReadOnly(True)
        box.addWidget(view)
        dialog.exec()
