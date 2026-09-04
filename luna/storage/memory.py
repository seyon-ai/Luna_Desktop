"""Memory layer: conversations, approved preferences and searchable local memories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from luna.storage.db import Database, new_id, utcnow


class MemoryStore:
    """Local SQLite-backed memory. No cloud, no private web page scraping."""

    def __init__(self, database_path: Path | str, enabled: bool = True) -> None:
        self.db = Database(database_path)
        self.enabled = enabled

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    # -- conversations ---------------------------------------------------
    def start_conversation(self, title: str = "New conversation") -> str:
        now = utcnow()
        conv_id = new_id("conv_")
        self.db.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conv_id, title, now, now),
        )
        return conv_id

    def add_message(self, conversation_id: str, role: str, content: str) -> int:
        if not self.enabled:
            return 0
        return self.db.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, utcnow()),
        )

    def touch_conversation(self, conversation_id: str, title: str | None = None) -> None:
        if title:
            self.db.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, utcnow(), conversation_id),
            )
        else:
            self.db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (utcnow(), conversation_id),
            )

    def get_messages(self, conversation_id: str, limit: int = 500) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT id, role, content, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id LIMIT ?",
            (conversation_id, limit),
        )
        return rows

    def list_conversations(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT id, title, created_at, updated_at, "
            "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count "
            "FROM conversations c ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )

    def delete_conversation(self, conversation_id: str) -> None:
        self.db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    # -- preferences ------------------------------------------------------
    def set_preference(self, key: str, value: Any, user_id: str = "default") -> None:
        encoded = json.dumps(value, ensure_ascii=False)
        self.db.execute(
            "INSERT INTO preferences (user_id, key, value, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (user_id, key, encoded, utcnow()),
        )

    def get_preference(self, key: str, user_id: str = "default") -> Any | None:
        rows = self.db.query(
            "SELECT value FROM preferences WHERE user_id = ? AND key = ?", (user_id, key)
        )
        if not rows:
            return None
        try:
            return json.loads(rows[0]["value"])
        except json.JSONDecodeError:
            return None

    # -- memories ----------------------------------------------------------
    def add_memory(
        self,
        content: str,
        kind: str = "note",
        metadata: dict[str, Any] | None = None,
        importance: float = 0.5,
    ) -> str:
        if not self.enabled:
            return ""
        mem_id = new_id("mem_")
        now = utcnow()
        self.db.execute(
            "INSERT INTO memories (id, kind, content, metadata_json, importance, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (mem_id, kind, content, json.dumps(metadata or {}, ensure_ascii=False), importance, now, now),
        )
        return mem_id

    def search_memory(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        like = f"%{query}%"
        return self.db.query(
            "SELECT id, kind, content, metadata_json, importance, created_at, updated_at "
            "FROM memories WHERE content LIKE ? ORDER BY importance DESC, updated_at DESC LIMIT ?",
            (like, limit),
        )

    def list_memories(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        return self.db.query(
            "SELECT id, kind, content, metadata_json, importance, created_at, updated_at "
            "FROM memories ORDER BY importance DESC, updated_at DESC LIMIT ?",
            (limit,),
        )

    def delete_memory(self, memory_id: str) -> None:
        self.db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

    def clear_memories(self) -> int:
        rows = self.db.query("SELECT COUNT(*) AS n FROM memories")
        self.db.execute("DELETE FROM memories")
        return int(rows[0]["n"]) if rows else 0

    def close(self) -> None:
        self.db.close()
