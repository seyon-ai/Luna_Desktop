from __future__ import annotations

import sys

import pytest

from luna.automation.terminal import Terminal


def test_terminal_success(tmp_home):
    term = Terminal(logs_dir=tmp_home / "logs")
    result = term.run("echo hello-luna", timeout=10)
    assert result["ok"] is True
    assert result["exit_code"] == 0
    assert "hello-luna" in result["stdout"]
    assert result["log"]  # command log written


def test_terminal_failure_records_stderr(tmp_home):
    term = Terminal(logs_dir=tmp_home / "logs")
    if sys.platform.startswith("win"):
        result = term.run("echo error 1>&2 & exit /b 7", timeout=10)
    else:
        result = term.run("echo error >&2; exit 7", timeout=10)
    assert result["ok"] is False
    assert result["exit_code"] == 7 if not sys.platform.startswith("win") else result["exit_code"] == 7
    assert "error" in result["stderr"]


def test_terminal_timeout(tmp_home):
    term = Terminal(logs_dir=tmp_home / "logs")
    if sys.platform.startswith("win"):
        command = "ping -n 10 127.0.0.1"
    else:
        command = "sleep 5"
    result = term.run(command, timeout=0.3)
    assert result["timed_out"] is True


def test_terminal_cwd(tmp_home):
    term = Terminal(cwd=tmp_home)
    result = term.run("pwd" if not sys.platform.startswith("win") else "cd", timeout=10)
    assert str(tmp_home).lower() in result["stdout"].lower()
