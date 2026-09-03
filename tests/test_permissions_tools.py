from __future__ import annotations

from pathlib import Path

import pytest

from luna.automation import filesystem as fs
from luna.automation.tools.registry import register_browser_tools, register_core_tools
from luna.core.permissions import PermissionDenied, PermissionManager
from luna.core.tools import ToolRegistry
from luna.config.config import PermissionConfig


def test_permission_allow():
    pm = PermissionManager()
    pm.config.rules["read_file"] = "allow"
    assert pm.check("read_file", "read a file") is True


def test_permission_deny():
    pm = PermissionManager()
    pm.config.rules["purchase"] = "deny"
    with pytest.raises(PermissionDenied):
        pm.check("purchase")


def test_permission_ask_with_callback():
    pm = PermissionManager()
    pm.config.rules["delete_file"] = "ask"
    pm.register_approval_callback(lambda requests: {requests[0].action: {"allowed": True}})
    assert pm.ask("delete_file", "delete report", {"path": "x"}) is True
    assert pm.log[-1].action == "delete_file"

    pm.register_approval_callback(lambda requests: {requests[0].action: False})
    with pytest.raises(PermissionDenied):
        pm.ask("delete_file")


def test_permission_ask_without_callback_denies():
    pm = PermissionManager()
    pm.config.rules["send_message"] = "ask"
    with pytest.raises(PermissionDenied):
        pm.ask("send_message")


def test_rule_default():
    pm = PermissionManager(PermissionConfig(default="deny"))
    assert pm.rule_for("unknown_action") == "deny"


def test_tool_registry_core(tmp_home):
    registry = ToolRegistry()
    register_core_tools(registry, workspace=tmp_home)
    names = {t.name for t in registry.all()}
    assert {"list_directory", "read_file", "create_file", "modify_file", "delete_file",
            "move_file", "run_command", "search_files", "organize_downloads"} <= names
    assert registry.get("delete_file").permission == "delete_file"
    schema = registry.get("create_file").to_openai()
    assert "path" in schema["function"]["parameters"]["properties"]
    assert "required" in schema["function"]["parameters"]


def test_file_tools_roundtrip(tmp_home):
    registry = ToolRegistry()
    register_core_tools(registry, workspace=tmp_home)
    registry.get("create_file").callback(path="notes.txt", content="hello luna")
    result = registry.get("read_file").callback(path="notes.txt")
    assert result["content"] == "hello luna"
    listed = registry.get("list_directory").callback(path=".")
    assert any(e["name"] == "notes.txt" for e in listed["entries"])
    registry.get("modify_file").callback(path="notes.txt", content=" again")
    assert registry.get("read_file").callback(path="notes.txt")["content"] == "hello luna again"


def test_delete_and_move_scope(tmp_home):
    registry = ToolRegistry()
    register_core_tools(registry, workspace=tmp_home)
    registry.get("create_file").callback(path="a.txt", content="x")
    registry.get("move_file").callback(source="a.txt", destination="b.txt")
    assert (tmp_home / "b.txt").exists()
    assert not (tmp_home / "a.txt").exists()
    with pytest.raises(fs.FileToolError):
        registry.get("read_file").callback(path="../outside.txt")


def test_organize_downloads(tmp_home):
    registry = ToolRegistry()
    register_core_tools(registry, workspace=tmp_home)
    (tmp_home / "photo.jpg").write_bytes(b"jpeg")
    (tmp_home / "doc.pdf").write_bytes(b"pdf")
    result = registry.get("organize_downloads").callback(directory=".")
    assert (tmp_home / "images" / "photo.jpg").exists()
    assert (tmp_home / "documents" / "doc.pdf").exists()
    assert set(result["moved"]) == {"images", "documents"}


def test_browser_tools_registered(tmp_home):
    registry = ToolRegistry()
    register_core_tools(registry, workspace=tmp_home)

    class FakeBrowser:
        def navigate(self, url):
            return {"url": url}

        def open_tab(self, url=None):
            return {"url": url}

        def list_tabs(self):
            return []

        def switch_tab(self, index):
            return {"index": index}

        def close_tab(self, index=None):
            return {"index": index}

        def read_page(self, max_chars=8000):
            return {"text": "example"}

        def find(self, **kw):
            return []

        def click(self, **kw):
            return {"ok": True}

        def type_text(self, text, **kw):
            return {"ok": True}

        def press(self, key):
            return {"ok": True}

        def scroll(self, amount=600):
            return {"ok": True}

        def wait(self, **kw):
            return {"ok": True}

        def screenshot(self, path, full_page=False):
            return path

        def go_back(self):
            return {}

        def extract(self, **kw):
            return []

    register_browser_tools(registry, FakeBrowser())
    assert registry.get("browser_navigate").callback("https://youtube.com")["url"].endswith("youtube.com")
    assert registry.get("browser_read_page").callback()["text"] == "example"
    from luna.ai.providers.base import LLMResult  # noqa: F401  (import sanity)


def test_agent_permission_wiring():
    registry = ToolRegistry()
    calls = []

    def guarded(path):
        calls.append(path)
        return {"path": path}

    registry.add("delete_file", "delete", guarded, {"path": {}}, permission="delete_file")
    pm = PermissionManager()
    pm.config.rules["delete_file"] = "deny"
    from luna.core.tasks.models import RunContext, Task
    from luna.core.agent import AgentContext

    task = Task(id="t1", goal="g")
    ctx = RunContext(task, lambda _t: None)
    agent = AgentContext(ctx, registry, pm)
    with pytest.raises(PermissionDenied):
        agent.execute_tool("delete_file", {"path": "/x"})
    assert calls == []
