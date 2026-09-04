"""Chat page: conversation view + goal input and voice input."""

from __future__ import annotations

import html
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from luna.ui.common import h1, muted


class ChatPage(QWidget):
    def __init__(self, app: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title = h1("Conversation")
        header.addWidget(title)
        header.addStretch(1)
        self.status_label = muted("")
        header.addWidget(self.status_label)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.view = QTextBrowser()
        self.view.setObjectName("chatView")
        self.view.setOpenExternalLinks(False)
        self.view.setFont(QFont("Segoe UI", 11))
        splitter.addWidget(self.view)
        self._set_hint()

        input_box = QWidget()
        input_layout = QHBoxLayout(input_box)
        input_layout.setContentsMargins(0, 0, 0, 0)
        self.input = QTextEdit()
        self.input.setPlaceholderText("Tell LUNA what you want…  (Enter to send)")
        self.input.setMaximumHeight(76)
        self.input.installEventFilter(self)
        input_layout.addWidget(self.input, 1)
        self.voice_button = QPushButton("🎙 Voice")
        self.voice_button.setToolTip("Capture voice input (requires STT extras)")
        self.voice_button.clicked.connect(self._toggle_voice)
        input_layout.addWidget(self.voice_button)
        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("primary")
        self.send_button.clicked.connect(self._send)
        input_layout.addWidget(self.send_button)
        splitter.addWidget(input_box)
        splitter.setSizes([520, 100])
        layout.addWidget(splitter, 1)

    def _set_hint(self) -> None:
        self.view.setHtml(
            "<div style='color:#5d6d88; padding:40px; text-align:center;'>"
            "<h2 style='color:#93a3bd; font-weight:600;'>What should LUNA do?</h2>"
            "<p>LUNA plans work, operates apps and websites, verifies results,<br>"
            "and asks permission before high-impact actions.</p>"
            "</div>"
        )

    def eventFilter(self, obj: Any, event: Any) -> bool:  # noqa: N802
        if obj is self.input and event.type() == event.Type.KeyPress and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            if not event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier):
                self._send()
                return True
        return super().eventFilter(obj, event)

    def _send(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self._append("you", text)
        task = self.app.create_agent_task(text)
        self.status_label.setText(f"Task {task.id[:8]} started — see Tasks for progress.")
        self._append("luna", f"**Goal accepted.** Task `{task.id[:8]}` is queued; I'll report back when it finishes.")

    def _append(self, role: str, content: str) -> None:
        self.view.append(
            f"<div style='margin:8px 0;'><b style='color:#8fb8ff;'>"
            f"{'You' if role == 'you' else 'LUNA'}</b> "
            f"<span style='color:#e8edf7;'>{html.escape(content)}</span></div>"
        )
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def _toggle_voice(self) -> None:
        self.status_label.setText("Voice capture is available after landing STT (faster-whisper) and mic permissions.")
        QTimer.singleShot(4000, lambda: self.status_label.setText(""))
