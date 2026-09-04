"""Main application window with sidebar navigation, tray and background mode."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QSize, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from luna.app.application import Application
from luna.ui.audio import AudioPlayer
from luna.ui.pages.chat import ChatPage
from luna.ui.pages.memory import MemoryPage
from luna.ui.pages.models import ModelsPage
from luna.ui.pages.settings import SettingsPage
from luna.ui.pages.tasks import TaskPage
from luna.ui.theme import COLORS, QSS


class TaskNotifier(QObject):
    notify = Signal(object)


class MainWindow(QMainWindow):
    def __init__(self, app: Application, minimized: bool = False) -> None:
        super().__init__()
        self.app = app
        self.setWindowTitle("LUNA")
        self.resize(1180, 760)
        self.setMinimumSize(920, 600)
        self.setWindowIcon(QIcon(str(self._asset("luna_256.png"))))
        self.setStyleSheet(QSS)
        self.audio = AudioPlayer(self)
        app.audio = self.audio  # type: ignore[attr-defined]
        self._build()
        self._build_tray()
        self._notifier = TaskNotifier()
        self._notifier.notify.connect(self._on_task_notify)
        self.app.tasks.add_listener(lambda task: self._notifier.notify.emit(task))
        from luna.ui.permissions import ApprovalBridge

        self.approval = ApprovalBridge(self)
        self.approval.requested.connect(self._show_permission_request)
        self.app.permissions.register_approval_callback(self.approval.callback)
        if minimized:
            QTimer.singleShot(200, self.hide_to_tray)

    # -- layout -----------------------------------------------------------------
    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 18, 14, 18)
        side_layout.setSpacing(6)

        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QIcon(str(self._asset("luna_32.png"))).pixmap(QSize(30, 30)))
        brand.addWidget(logo)
        name = QLabel("LUNA")
        name.setObjectName("logoText")
        brand.addWidget(name)
        brand.addStretch(1)
        side_layout.addLayout(brand)

        status = QHBoxLayout()
        dot = QLabel("●")
        dot.setObjectName("statusDot")
        status.addWidget(dot)
        status_label = QLabel("local · ready")
        status_label.setObjectName("faint")
        status.addWidget(status_label)
        status.addStretch(1)
        side_layout.addLayout(status)
        side_layout.addSpacing(14)

        self.stack = QStackedWidget()
        self.pages = {
            "chat": ChatPage(self.app),
            "tasks": TaskPage(self.app),
            "models": ModelsPage(self.app),
            "memory": MemoryPage(self.app),
            "settings": SettingsPage(self.app),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for key, label in (
            ("chat", "Chat"),
            ("tasks", "Tasks"),
            ("models", "Models"),
            ("memory", "Memory"),
            ("settings", "Settings"),
        ):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, k=key: self.stack.setCurrentWidget(self.pages[k]))
            self.nav_group.addButton(button)
            side_layout.addWidget(button)
            if key == "chat":
                button.setChecked(True)
        side_layout.addStretch(1)
        quit_btn = QPushButton("Quit LUNA")
        quit_btn.setObjectName("navButton")
        quit_btn.clicked.connect(self.quit)
        side_layout.addWidget(quit_btn)

        layout.addWidget(sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def _asset(self, name: str) -> Path:
        return Path(__file__).resolve().parent.parent / "assets" / name

    # -- tray ----------------------------------------------------------------------
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(QIcon(str(self._asset("luna_tray.png"))), self)
        self.tray.setToolTip("LUNA — local AI assistant")
        from PySide6.QtWidgets import QMenu

        menu = QMenu()
        show_action = QAction("Show LUNA", self)
        show_action.triggered.connect(self.show_from_tray)
        menu.addAction(show_action)
        pause_action = QAction("Pause all tasks", self)
        pause_action.triggered.connect(lambda: [self.app.tasks.pause(t.id) for t in self.app.tasks.active_tasks()])
        menu.addAction(pause_action)
        resume_action = QAction("Resume all tasks", self)
        resume_action.triggered.connect(lambda: [self.app.tasks.resume(t.id) for t in self.app.tasks.active_tasks()])
        menu.addAction(resume_action)
        stop_all_action = QAction("Stop all tasks", self)
        stop_all_action.triggered.connect(self.app.tasks.stop_all)
        menu.addAction(stop_all_action)
        menu.addSeparator()
        quit_action = QAction("Quit LUNA", self)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason: Any) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_from_tray()

    def _on_task_notify(self, task: Any) -> None:
        status = task.status.value
        if status == "COMPLETED" and self.app.settings.notifications.on_task_complete:
            self.tray.showMessage("LUNA", f"Task completed: {task.goal[:60]}", QSystemTrayIcon.MessageIcon.Information, 5000)
        elif status == "FAILED" and self.app.settings.notifications.on_task_failed:
            self.tray.showMessage("LUNA", f"Task failed: {task.goal[:60]}", QSystemTrayIcon.MessageIcon.Warning, 5000)
        elif status == "WAITING_FOR_USER":
            self.tray.showMessage(
                "LUNA",
                f"Waiting for approval: {task.goal[:60]}",
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )

    # -- permissions ------------------------------------------------------------------
    def _show_permission_request(self, payload: tuple[Any, Any, dict]) -> None:
        from PySide6.QtWidgets import QMessageBox

        requests, event, responses = payload

        for request in requests:
            detail = (
                f"Action: {request.action}\n"
                f"Description: {request.description}\n"
                f"Details: {request.details}"
            )
            answer = QMessageBox.question(
                self,
                "LUNA needs permission",
                f"{request.description}\n\n{detail}\n\nAllow?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            responses[request.action] = {
                "allowed": answer == QMessageBox.StandardButton.Yes,
                "rule": request.rule,
            }
        self.approval.respond(event, responses)

    # -- show/hide/quit --------------------------------------------------------------
    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self) -> None:
        if self.app.settings.hide_to_tray_on_close or self.tray.isVisible():
            self.hide()
        else:
            self.quit()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.app.settings.hide_to_tray_on_close and self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage("LUNA", "Still running in the background. Tasks continue.", QSystemTrayIcon.MessageIcon.Information, 4000)
        else:
            event.accept()
            self.quit()

    def quit(self) -> None:
        if getattr(self, "_quitting", False):
            return
        self._quitting = True
        try:
            self.app.shutdown()
        except Exception:  # noqa: BLE001
            pass
        QApplication.instance().quit()
