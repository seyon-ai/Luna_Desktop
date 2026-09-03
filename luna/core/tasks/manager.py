"""Persistent task manager.

Tasks run on worker threads (not the Qt UI thread), continue when the main
window is hidden, and persist to LUNA_HOME/tasks/*.json plus SQLite.
"""

from __future__ import annotations

import json
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from luna.core.tasks.models import RunContext, Task, TaskCancelled, TaskStatus
from luna.storage.db import Database, new_id, utcnow

TaskListener = Callable[[Task], None]


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


class TaskManager:
    def __init__(
        self,
        database: Database,
        artifacts_dir: Path | str,
        max_concurrent: int = 2,
    ) -> None:
        self.db = database
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, max_concurrent), thread_name_prefix="luna-task"
        )
        self._tasks: dict[str, Task] = {}
        self._contexts: dict[str, RunContext] = {}
        self._futures: dict[str, Any] = {}
        self._listeners: list[TaskListener] = []
        self._db_logged: dict[str, int] = {}
        self._lock = threading.RLock()

    def add_listener(self, listener: TaskListener) -> None:
        self._listeners.append(listener)

    def _emit(self, task: Task) -> None:
        for listener in list(self._listeners):
            try:
                listener(task)
            except Exception:
                traceback.print_exc()

    def _on_progress(self, task: Task) -> None:
        """Called from worker threads on every progress update: persist + notify."""
        self._persist(task)
        self._emit(task)

    # -- lifecycle ---------------------------------------------------------
    def create(self, goal: str) -> Task:
        with self._lock:
            task = Task(id=new_id("task_"), goal=goal)
            if self._tasks:
                # do not erase an existing in-memory task with same id (defensive)
                pass
            self._tasks[task.id] = task
        self._persist(task)
        self._emit(task)
        return task

    def start(self, task_id: str, runner: Callable[[RunContext], Any]) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status not in (TaskStatus.QUEUED, TaskStatus.PAUSED):
                return False
            context = self._contexts.setdefault(task_id, RunContext(task, self._on_progress))
            if task.status == TaskStatus.PAUSED:
                # Resuming an existing worker: unblock it, do not start a second one.
                context.resume()
                task.status = TaskStatus.RUNNING
                task.updated_at = utcnow()
                context.log("Task resumed.")
                self._persist(task)
                self._emit(task)
                return True
            task.status = TaskStatus.QUEUED
            self._persist(task)
            self._emit(task)
            future = self._executor.submit(self._worker, task_id, context, runner)
            self._futures[task_id] = future
        return True

    def submit(self, goal: str, runner: Callable[[RunContext], Any]) -> Task:
        task = self.create(goal)
        self.start(task.id, runner)
        return task

    def _worker(
        self,
        task_id: str,
        context: RunContext,
        runner: Callable[[RunContext], Any],
    ) -> None:
        task = context.task
        task.status = TaskStatus.RUNNING
        task.started_at = utcnow()
        task.updated_at = utcnow()
        context.log("Task started.")
        self._persist(task)
        self._emit(task)
        try:
            result = runner(context)
            context.check_cancelled()
            task.status = TaskStatus.COMPLETED
            task.progress = 100.0
            task.result = result if isinstance(result, dict) else {"result": result}
            task.finished_at = utcnow()
            context.log("Task completed.", data={"result": task.result})
        except TaskCancelled:
            task.status = TaskStatus.CANCELLED
            task.finished_at = utcnow()
            context.log("Task cancelled.", level="warn")
        except Exception as exc:  # noqa: BLE001
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.finished_at = utcnow()
            context.log(f"Task failed: {exc}", level="error", data={"traceback": traceback.format_exc()})
        finally:
            task.updated_at = utcnow()
            self._persist(task)
            self._emit(task)

    # -- controls ------------------------------------------------------------
    def pause(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        context = self._contexts.get(task_id)
        if task is None or context is None or task.status != TaskStatus.RUNNING:
            return False
        context.pause()
        task.status = TaskStatus.PAUSED
        task.updated_at = utcnow()
        context.log("Task paused.", level="warn")
        self._persist(task)
        self._emit(task)
        return True

    def resume(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        context = self._contexts.get(task_id)
        if task is None or context is None or task.status != TaskStatus.PAUSED:
            return False
        context.resume()
        task.status = TaskStatus.RUNNING
        task.updated_at = utcnow()
        context.log("Task resumed.")
        self._persist(task)
        self._emit(task)
        return True

    def cancel(self, task_id: str) -> bool:
        context = self._contexts.get(task_id)
        if context is None:
            return False
        context.log("Cancel requested.", level="warn")
        context.cancel()
        task = self._tasks.get(task_id)
        if task is not None:
            self._persist(task)
            self._emit(task)
        return True

    def stop_all(self) -> None:
        for context in list(self._contexts.values()):
            context.cancel()

    # -- queries ---------------------------------------------------------------
    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 200) -> list[Task]:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    def active_tasks(self) -> list[Task]:
        return [
            t
            for t in self.list_tasks(0)
            if t.status
            in (TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.PAUSED, TaskStatus.WAITING_FOR_USER)
        ]

    def wait(self, task_id: str, timeout: float | None = None) -> Task | None:
        future = self._futures.get(task_id)
        if future is None:
            return self.get(task_id)
        future.result(timeout=timeout)
        return self.get(task_id)

    def load_persisted(self) -> None:
        for path in sorted(self.artifacts_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                task = Task.from_dict(data)
                if task.status in (
                    TaskStatus.QUEUED,
                    TaskStatus.RUNNING,
                    TaskStatus.PAUSED,
                    TaskStatus.WAITING_FOR_USER,
                ):
                    task.status = TaskStatus.FAILED
                    task.error = "LUNA was restarted while this task was running."
                self._tasks[task.id] = task
            except Exception:
                continue

    # -- persistence ------------------------------------------------------------
    def _persist(self, task: Task) -> None:
        data = task.to_dict()
        _atomic_json(self.artifacts_dir / f"{task.id}.json", data)
        self._upsert_db(task)

    def _upsert_db(self, task: Task) -> None:
        self.db.execute(
            "INSERT INTO tasks (id, goal, status, progress, current_step, result_json, error, "
            "created_at, updated_at, started_at, finished_at) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET status=excluded.status, progress=excluded.progress, "
            "current_step=excluded.current_step, result_json=excluded.result_json, "
            "error=excluded.error, updated_at=excluded.updated_at, "
            "started_at=excluded.started_at, finished_at=excluded.finished_at",
            (
                task.id,
                task.goal,
                task.status.value,
                task.progress,
                task.current_step,
                json.dumps(task.result) if task.result is not None else None,
                task.error,
                task.created_at,
                task.updated_at,
                task.started_at,
                task.finished_at,
            ),
        )
        already = self._db_logged.get(task.id, 0)
        for log in task.logs[already:]:
            self.db.execute(
                "INSERT INTO task_logs (task_id, ts, level, message, data_json) VALUES (?,?,?,?,?)",
                (task.id, log.ts, log.level, log.message, json.dumps(log.data) if log.data else None),
            )
        self._db_logged[task.id] = len(task.logs)

    def shutdown(self) -> None:
        self.stop_all()
        self._executor.shutdown(wait=False, cancel_futures=True)
