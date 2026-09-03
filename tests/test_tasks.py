from __future__ import annotations

import json
import time

import pytest

from luna.core.tasks.manager import TaskManager
from luna.core.tasks.models import RunContext, TaskCancelled, TaskStatus
from luna.storage.db import Database


@pytest.fixture
def manager(tmp_home):
    db = Database(tmp_home / "memory" / "luna.db")
    mgr = TaskManager(db, tmp_home / "tasks", max_concurrent=2)
    yield mgr
    mgr.shutdown()


def test_task_lifecycle(manager):
    def runner(ctx: RunContext):
        ctx.log("started")
        ctx.set_progress(50, "working")
        return {"done": True}

    task = manager.submit("Do the thing", runner)
    assert task.status in (TaskStatus.QUEUED, TaskStatus.RUNNING)
    finished = manager.wait(task.id, timeout=10)
    assert finished is not None
    assert finished.status == TaskStatus.COMPLETED
    assert finished.progress == 100
    assert finished.result == {"done": True}
    assert any(log.message == "started" for log in finished.logs)


def test_task_failure_recorded(manager):
    def runner(ctx):
        raise ValueError("boom")

    task = manager.submit("Failing task", runner)
    finished = manager.wait(task.id, timeout=10)
    assert finished.status == TaskStatus.FAILED
    assert "boom" in finished.error
    assert any(log.level == "error" for log in finished.logs)


def test_task_cancellation(manager):
    def runner(ctx):
        for _ in range(200):
            ctx.check_cancelled()
            time.sleep(0.02)
        return {"unexpected": True}

    task = manager.submit("Cancel me", runner)
    time.sleep(0.05)
    manager.cancel(task.id)
    finished = manager.wait(task.id, timeout=10)
    assert finished.status == TaskStatus.CANCELLED


def test_pause_resume(manager):
    state = {"paused_seen": False, "ran": 0}

    def runner(ctx):
        for _ in range(100):
            ctx.checkpoint()
            state["ran"] += 1
            time.sleep(0.01)
        return {"ok": True}

    task = manager.submit("Pause test", runner)
    time.sleep(0.06)
    assert manager.pause(task.id) is True
    task = manager.get(task.id)
    assert task.status == TaskStatus.PAUSED
    assert manager.resume(task.id) is True
    finished = manager.wait(task.id, timeout=10)
    assert finished.status == TaskStatus.COMPLETED
    assert state["ran"] > 0


def test_persistence_artifacts(manager, tmp_home):
    def runner(ctx):
        ctx.log("persist me")
        return {"ok": 1}

    task = manager.submit("Persistent", runner)
    manager.wait(task.id, timeout=10)
    artifact = tmp_home / "tasks" / f"{task.id}.json"
    assert artifact.exists()
    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert data["goal"] == "Persistent"
    assert data["status"] == "COMPLETED"


def test_load_persisted_fails_stale_running(manager, tmp_home):
    from luna.core.tasks.models import Task

    stale = Task(id="task_stale", goal="stale", status=TaskStatus.RUNNING)
    (tmp_home / "tasks" / "task_stale.json").write_text(json.dumps(stale.to_dict()))
    manager.load_persisted()
    loaded = manager.get("task_stale")
    assert loaded is not None
    assert loaded.status == TaskStatus.FAILED
    assert "restarted" in loaded.error


def test_task_artifacts_during_run(manager, tmp_home):
    def runner(ctx):
        ctx.set_progress(10, "working")
        time.sleep(0.3)

    task = manager.submit("Artifacts", runner)
    time.sleep(0.15)
    artifact = tmp_home / "tasks" / f"{task.id}.json"
    assert artifact.exists()
    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert data["progress"] == 10
    manager.wait(task.id, timeout=5)
