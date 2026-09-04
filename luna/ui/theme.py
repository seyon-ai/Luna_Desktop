"""LUNA visual identity: dark-first, lunar, premium, calm."""

from __future__ import annotations

COLORS = {
    "bg": "#0b0f17",
    "bg_alt": "#111826",
    "panel": "#141c2c",
    "panel_hover": "#1b2436",
    "border": "#223047",
    "border_soft": "#1a2437",
    "text": "#e8edf7",
    "text_dim": "#93a3bd",
    "text_faint": "#5d6d88",
    "accent": "#8fb8ff",  # moonlit blue, not generic purple
    "accent_2": "#d3aef2",  # soft lavender for highlights
    "accent_dim": "#5a76a8",
    "success": "#5dd29a",
    "warning": "#f2b45c",
    "error": "#f2716d",
    "danger": "#e15b57",
    "running": "#8fb8ff",
    "paused": "#f2b45c",
    "waiting": "#d3aef2",
}

QSS = f"""
* {{
    font-family: "Segoe UI", "Inter", "SF Pro Display", sans-serif;
    outline: none;
}}
QMainWindow, QWidget#root {{
    background: {COLORS["bg"]};
    color: {COLORS["text"]};
}}
QWidget {{
    font-size: 13px;
}}

/* Sidebar */
QFrame#sidebar {{
    background: {COLORS["bg_alt"]};
    border-right: 1px solid {COLORS["border_soft"]};
}}
QPushButton#navButton {{
    background: transparent;
    color: {COLORS["text_dim"]};
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 10px 14px;
    text-align: left;
    font-size: 14px;
}}
QPushButton#navButton:hover {{
    background: {COLORS["panel_hover"]};
    color: {COLORS["text"]};
}}
QPushButton#navButton:checked {{
    background: {COLORS["panel"]};
    color: {COLORS["accent"]};
    border: 1px solid {COLORS["border"]};
}}
QLabel#logoText {{
    font-size: 22px;
    font-weight: 700;
    color: {COLORS["text"]};
    letter-spacing: 4px;
}}
QLabel#statusDot {{
    color: {COLORS["success"]};
}}

/* Panels & cards */
QFrame#card {{
    background: {COLORS["panel"]};
    border: 1px solid {COLORS["border_soft"]};
    border-radius: 12px;
}}
QLabel#h1 {{
    font-size: 20px;
    font-weight: 700;
    color: {COLORS["text"]};
}}
QLabel#h2 {{
    font-size: 15px;
    font-weight: 600;
    color: {COLORS["text"]};
}}
QLabel#muted {{
    color: {COLORS["text_dim"]};
}}
QLabel#faint {{
    color: {COLORS["text_faint"]};
    font-size: 11px;
}}

/* Inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {COLORS["bg_alt"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 9px;
    color: {COLORS["text"]};
    padding: 8px 10px;
    selection-background-color: {COLORS["accent_dim"]};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLORS["accent"]};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {COLORS["panel"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]};
    selection-background-color: {COLORS["panel_hover"]};
}}

/* Buttons */
QPushButton {{
    background: {COLORS["panel_hover"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 9px;
    padding: 8px 16px;
}}
QPushButton:hover {{
    background: {COLORS["border"]};
    border-color: {COLORS["accent_dim"]};
}}
QPushButton:pressed {{
    background: {COLORS["border"]};
}}
QPushButton:disabled {{
    color: {COLORS["text_faint"]};
    background: {COLORS["bg_alt"]};
    border-color: {COLORS["border_soft"]};
}}
QPushButton#primary {{
    background: {COLORS["accent_dim"]};
    color: #07101f;
    border: 1px solid {COLORS["accent"]};
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background: {COLORS["accent"]};
}}
QPushButton#danger {{
    color: {COLORS["danger"]};
    border-color: {COLORS["danger"]};
}}
QPushButton#danger:hover {{
    background: rgba(226, 91, 87, 0.12);
}}

/* Lists */
QListWidget {{
    background: transparent;
    border: none;
}}
QListWidget::item {{
    background: {COLORS["panel"]};
    border: 1px solid {COLORS["border_soft"]};
    border-radius: 10px;
    margin: 3px 0;
    padding: 4px;
}}
QListWidget::item:selected {{
    border: 1px solid {COLORS["accent_dim"]};
    background: {COLORS["panel_hover"]};
}}
QTextBrowser#chatView {{
    background: transparent;
    border: none;
    color: {COLORS["text"]};
}}

/* Progress */
QProgressBar {{
    background: {COLORS["bg_alt"]};
    border: 1px solid {COLORS["border_soft"]};
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {COLORS["accent"]};
    border-radius: 5px;
}}

/* Tabs */
QTabWidget::pane {{
    border: 1px solid {COLORS["border_soft"]};
    border-radius: 10px;
    background: {COLORS["panel"]};
}}
QTabBar::tab {{
    background: transparent;
    color: {COLORS["text_dim"]};
    padding: 9px 16px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {COLORS["accent"]};
    border-bottom: 2px solid {COLORS["accent"]};
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 4px;
    background: {COLORS["border"]};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {COLORS["accent"]};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {COLORS["accent_dim"]};
    border-radius: 2px;
}}

QCheckBox {{
    color: {COLORS["text_dim"]};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    background: {COLORS["bg_alt"]};
}}
QCheckBox::indicator:checked {{
    background: {COLORS["accent_dim"]};
    border-color: {COLORS["accent"]};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS["border"]};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS["accent_dim"]};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}

QToolTip {{
    background: {COLORS["panel"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]};
    padding: 6px;
}}

QSplitter::handle {{
    background: {COLORS["border_soft"]};
}}
"""
