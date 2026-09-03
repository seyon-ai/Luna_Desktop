"""Offscreen Qt smoke test: app initializes, pages build, tray hooks exist.

Runs on CI with PySide6 (offscreen platform on Linux); on Windows it runs with
the real windows platform adapter but no visible window unless QT_QPA_PLATFORM
is set.
"""

from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

# Full GUI smoke tests need a desktop/Qt-capable platform (Windows CI runner).
# Linux containers without system GL/DBus cannot host QApplication, so they are
# skipped by default; LUNA_FORCE_UI_TESTS=1 overrides for capable environments.
if not (sys.platform == "win32" or os.environ.get("LUNA_FORCE_UI_TESTS") == "1"):
    pytest.skip(
        "Qt GUI smoke tests run on Windows (or with LUNA_FORCE_UI_TESTS=1).",
        allow_module_level=True,
    )

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def qt_app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_builds(qt_app, tmp_home):
    from luna.app.application import Application
    from luna.ui.main_window import MainWindow

    core = Application(tmp_home)
    window = MainWindow(core, minimized=False)
    assert window.windowTitle() == "LUNA"
    assert set(window.pages) == {"chat", "tasks", "models", "memory", "settings"}
    qt_app.processEvents()
    window.quit()


def test_smoke_init_service(qt_app, tmp_home):
    from luna.app.application import Application

    core = Application(tmp_home)
    assert core.paths.database.exists()
    assert core.tasks.list_tasks() == []
    core.shutdown()


def test_settings_save_tick(qt_app, tmp_home):
    from luna.app.application import Application
    from luna.ui.pages.settings import SettingsPage

    core = Application(tmp_home)
    page = SettingsPage(core)
    page._load()
    page.p_mode.setCurrentText("friendly")
    qt_app.processEvents()
    assert core.settings.personality.mode == "friendly"
    core.shutdown()
