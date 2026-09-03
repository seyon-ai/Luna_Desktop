"""Small shared Qt widgets."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from luna.ui.theme import COLORS


def card(parent: QWidget | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame(parent)
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)
    return frame, layout


def h1(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("h1")
    return label


def h2(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("h2")
    return label


def muted(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("muted")
    return label


def faint(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("faint")
    return label


def primary_button(text: str, parent: QWidget | None = None) -> QPushButton:
    button = QPushButton(text, parent)
    button.setObjectName("primary")
    return button


def danger_button(text: str, parent: QWidget | None = None) -> QPushButton:
    button = QPushButton(text, parent)
    button.setObjectName("danger")
    return button


def status_pill(status: str) -> QLabel:
    label = QLabel(status)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"background: {COLORS['bg_alt']}; color: {COLORS[status_color(status)]};"
        "border: 1px solid " + COLORS["border"] + "; border-radius: 10px; padding: 3px 10px;"
        "font-size: 11px; font-weight: 600;"
    )
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return label


def status_color(status: str) -> str:
    mapping = {
        "RUNNING": "running",
        "PAUSED": "paused",
        "WAITING_FOR_USER": "waiting",
        "COMPLETED": "success",
        "FAILED": "error",
        "CANCELLED": "text_faint",
        "QUEUED": "text_dim",
    }
    return mapping.get(status, "text_dim")


def stretch_row(*widgets: QWidget, spacing: int = 8) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    for w in widgets:
        layout.addWidget(w)
    layout.addStretch(1)
    return layout
