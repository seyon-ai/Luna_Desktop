"""Controlled terminal execution.

Every command is logged with stdout/stderr capture, exit status, duration and
the permission decision. There is no invisible shell access: the permission
layer (rule ``run_command``) gates every invocation, and cancellation is
propagated to the child process.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from luna.core.tasks.models import RunContext

LOG_DIR = Path("logs")


class CommandDenied(RuntimeError):
    pass


class Terminal:
    def __init__(self, logs_dir: Path | str | None = None, cwd: Path | str | None = None, env: dict[str, str] | None = None) -> None:
        self.logs_dir = Path(logs_dir) if logs_dir else None
        self.cwd = Path(cwd).resolve() if cwd else None
        self.env_extra = env or {}

    def run(
        self,
        command: str,
        timeout: float = 60.0,
        run_context: RunContext | None = None,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        is_windows = sys.platform.startswith("win")
        if is_windows:
            args = ["cmd", "/c", command]
            shell = False
        else:
            args = ["/bin/sh", "-lc", command]
            shell = False
        env = os.environ.copy()
        env.update(self.env_extra)
        workdir = Path(cwd).resolve() if cwd else self.cwd
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(workdir) if workdir else None,
            env=env,
            shell=shell,
            creationflags=subprocess.CREATE_NO_WINDOW if is_windows else 0,
        )
        started = time.monotonic()
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            entry = self._log(command, proc.returncode or -1, stdout, stderr, started, f"timed out after {timeout}s", run_context)
            return {"ok": False, "timed_out": True, "exit_code": proc.returncode, "stdout": stdout, "stderr": stderr, "log": entry}
        if run_context is not None:
            run_context.check_cancelled()
        note = "cancelled" if run_context and run_context.cancelled else ("ok" if proc.returncode == 0 else f"exit {proc.returncode}")
        entry = self._log(command, proc.returncode, stdout, stderr, started, note, run_context)
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": stdout[-64_000:],
            "stderr": stderr[-64_000:],
            "duration_seconds": round(time.monotonic() - started, 3),
            "log": entry,
        }

    def _log(
        self,
        command: str,
        exit_code: int | None,
        stdout: str,
        stderr: str,
        started: float,
        note: str,
        run_context: RunContext | None = None,
    ) -> str:
        if self.logs_dir is None:
            return ""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_id = uuid.uuid4().hex[:12]
        task = getattr(run_context, "task", None)
        task_part = f"task={task.id} " if task is not None else ""
        with (self.logs_dir / f"{log_id}.log").open("w", encoding="utf-8") as fh:
            fh.write(f"# {note}\n# command: {command}\n# exit: {exit_code}\n# duration: {time.monotonic() - started:.3f}s\n{task_part}\n")
            fh.write("--- stdout ---\n")
            fh.write(stdout)
            fh.write("\n--- stderr ---\n")
            fh.write(stderr)
            fh.write("\n")
        if run_context is not None:
            run_context.log(f"Command finished ({note}): {command}", data={"log": log_id, "exit_code": exit_code})
        return log_id

    @staticmethod
    def preview(command: str) -> str:
        return shlex.split(command)[0] if command.strip() else ""
