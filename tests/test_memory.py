from __future__ import annotations

from luna.storage.memory import MemoryStore


def test_schema_and_conversations(tmp_home):
    mem = MemoryStore(tmp_home / "memory" / "luna.db")
    conv = mem.start_conversation("Test")
    mem.add_message(conv, "user", "Open YouTube")
    mem.add_message(conv, "assistant", "Queueing a task.")
    messages = mem.get_messages(conv)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    conversations = mem.list_conversations()
    assert conversations[0]["id"] == conv
    assert conversations[0]["message_count"] == 2
    mem.close()


def test_memories_crud(tmp_home):
    mem = MemoryStore(tmp_home / "memory" / "luna.db")
    mem.add_memory("User prefers dark mode", kind="preference", metadata={"category": "ui"})
    mem.add_memory("User works on the Luna project", kind="context", importance=0.9)
    mem.add_memory("Luna project uses Playwright", kind="context", importance=0.8)
    results = mem.search_memory("Playwright")
    assert len(results) == 1
    assert "Playwright" in results[0]["content"]
    all_memories = mem.list_memories()
    assert len(all_memories) == 3
    # importance ordering
    assert all_memories[0]["importance"] >= all_memories[-1]["importance"]
    mem.delete_memory(results[0]["id"])
    assert mem.search_memory("Playwright") == []
    cleared = mem.clear_memories()
    assert cleared == 2
    assert mem.list_memories() == []
    mem.close()


def test_memory_disabled(tmp_home):
    mem = MemoryStore(tmp_home / "memory" / "luna.db", enabled=False)
    assert mem.add_memory("should not store") == ""
    assert mem.list_memories() == []
    # conversations still allowed? Disabled memory means no automatic private history
    mem.close()


def test_preferences(tmp_home):
    mem = MemoryStore(tmp_home / "memory" / "luna.db")
    mem.set_preference("theme", "dark")
    mem.set_preference("theme", "lunar-dark")
    assert mem.get_preference("theme") == "lunar-dark"
    assert mem.get_preference("missing") is None
    mem.close()
