from __future__ import annotations

import time

from luna.core.agent import AgentContext
from luna.core.permissions import PermissionManager
from luna.core.tasks.manager import TaskManager
from luna.core.tasks.models import RunContext, TaskStatus
from luna.core.tools import ToolRegistry
from luna.storage.db import Database


def _scripted_model(script):
    if isinstance(script, dict):
        script = [script]
    idx = {"n": 0}

    def call(messages, tools):
        i = idx["n"]
        idx["n"] += 1
        return script[min(i, len(script) - 1)]

    return call


def _make_agent(manager, tool_script=None):
    registry = ToolRegistry()
    calls = []

    def fake_write(path, content):
        calls.append((path, content))
        return {"path": path, "ok": True}

    def fake_read(path):
        return {"path": path, "content": "world"}

    registry.add("write_file", "write a file", fake_write, {"path": {}, "content": {}})
    registry.add("read_file", "read a file", fake_read, {"path": {}})
    task_id = None

    def runner(ctx):
        agent = AgentContext(ctx, registry, PermissionManager(), model=tool_script)
        return agent.execute()

    task = manager.submit("Write a greeting", runner)
    finished = manager.wait(task.id, timeout=15)
    return finished, calls, registry


def test_agent_executes_tools_and_completes(tmp_home):
    db = Database(tmp_home / "memory" / "luna.db")
    manager = TaskManager(db, tmp_home / "tasks")
    script = [
        {"type": "tool_call", "name": "write_file", "arguments": {"path": "hello.txt", "content": "hello"}},
        {"type": "tool_call", "name": "read_file", "arguments": {"path": "hello.txt"}},
        {"type": "complete", "message": "File written and verified."},
    ]
    finished, calls, _ = _make_agent(manager, _scripted_model(script))
    assert finished.status == TaskStatus.COMPLETED
    assert calls == [("hello.txt", "hello")]
    assert finished.result is not None
    assert any("verified" in log.message.lower() or "returned" in log.message.lower() for log in finished.logs)
    manager.shutdown()


def test_agent_fails_loudly_when_loop_budget_hit(tmp_home):
    db = Database(tmp_home / "memory" / "luna.db")
    manager = TaskManager(db, tmp_home / "tasks")

    def runner(ctx):
        agent = AgentContext(
            ctx,
            ToolRegistry(),
            PermissionManager(),
            model=_scripted_model({"type": "tool_call", "name": "nonexistent", "arguments": {}}),
        )
        return agent.execute()

    task = manager.submit("Impossible", runner)
    finished = manager.wait(task.id, timeout=30)
    assert finished.status == TaskStatus.FAILED
    manager.shutdown()


def test_agent_cancellation_between_steps(tmp_home):
    db = Database(tmp_home / "memory" / "luna.db")
    manager = TaskManager(db, tmp_home / "tasks")
    registry = ToolRegistry()

    def slow(path):
        time.sleep(0.2)
        return {"path": path}

    registry.add("slow_tool", "slow", slow, {"path": {}})

    def runner(ctx):
        agent = AgentContext(ctx, registry, PermissionManager(), model=_scripted_model(
            {"type": "tool_call", "name": "slow_tool", "arguments": {"path": "x"}}
        ))
        return agent.execute()

    task = manager.submit("Cancel mid-step", runner)
    time.sleep(0.1)
    manager.cancel(task.id)
    finished = manager.wait(task.id, timeout=10)
    assert finished.status == TaskStatus.CANCELLED
    manager.shutdown()
