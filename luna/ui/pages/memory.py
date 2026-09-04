"""Memory page: search/delete/clear local memories + conversations."""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from luna.ui.common import card, h1, h2, muted


class MemoryPage(QWidget):
    def __init__(self, app: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.addWidget(h1("Memory"))
        header.addStretch(1)
        self.enabled = QCheckBox("Memory enabled")
        self.enabled.setChecked(self.app.settings.memory_enabled)
        self.enabled.toggled.connect(self._toggle_enabled)
        header.addWidget(self.enabled)
        clear = QPushButton("Clear Memory")
        clear.setObjectName("danger")
        clear.clicked.connect(self._clear)
        header.addWidget(clear)
        layout.addLayout(header)
        hint = muted("Memories are local (LUNA_HOME/memory/luna.db). No cloud, no Firebase.")
        layout.addWidget(hint)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search memories…")
        self.search.textChanged.connect(self.refresh)
        search_row.addWidget(self.search, 1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        search_row.addWidget(refresh)
        layout.addLayout(search_row)

        self.list = QListWidget()
        layout.addWidget(self.list, 1)

        conv_frame, conv_box = card()
        conv_box.addWidget(h2("Conversations"))
        conv_row = QHBoxLayout()
        add = QPushButton("New Conversation")
        add.clicked.connect(self._new_conversation)
        conv_row.addWidget(add)
        delete = QPushButton("Delete Selected Conversation")
        delete.clicked.connect(self._delete_conversation)
        conv_row.addWidget(delete)
        conv_row.addStretch(1)
        conv_box.addLayout(conv_row)
        self.conversations = QListWidget()
        self.conversations.setMaximumHeight(140)
        conv_box.addWidget(self.conversations)
        layout.addWidget(conv_frame)

    def refresh(self) -> None:
        self.list.clear()
        query = self.search.text().strip()
        items = self.app.memory.search_memory(query) if query else self.app.memory.list_memories()
        for mem in items:
            meta = json.loads(mem.get("metadata_json", "{}"))
            label = f"{mem['content'][:140]}  —  {mem['kind']} ({meta.get('source', 'local')})"
            item = QListWidgetItem(label)
            item.setData(100, mem["id"])
            self.list.addItem(item)
        self.conversations.clear()
        for conv in self.app.memory.list_conversations(50):
            item = QListWidgetItem(f'{conv["title"]}  ·  {conv["message_count"]} messages  ·  {conv["updated_at"][:10]}')
            item.setData(100, conv["id"])
            self.conversations.addItem(item)

    def _toggle_enabled(self, checked: bool) -> None:
        self.app.settings_manager.update(lambda s: setattr(s, "memory_enabled", checked))
        self.app.memory.set_enabled(checked)

    def _clear(self) -> None:
        confirm = QMessageBox.question(self, "Clear memory", "Delete all stored memories? This cannot be undone.")
        if confirm == QMessageBox.StandardButton.Yes:
            count = self.app.memory.clear_memories()
            QMessageBox.information(self, "Cleared", f"Deleted {count} memories.")
            self.refresh()

    def _new_conversation(self) -> None:
        conv_id = self.app.memory.start_conversation("New conversation")
        QMessageBox.information(self, "Created", f"Conversation {conv_id[:10]} created.")
        self.refresh()

    def _delete_conversation(self) -> None:
        item = self.conversations.currentItem()
        if item is None:
            return
        confirm = QMessageBox.question(self, "Delete conversation", "Delete the selected conversation and its messages?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.app.memory.delete_conversation(item.data(100))
            self.refresh()
