"""Application wiring: paths, settings, storage, task manager, automation."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable

from luna.ai.model_manager.manager import ModelManager
from luna.automation.browser.playwright_browser import PlaywrightBrowser
from luna.automation.desktop.contract import DesktopAutomation
from luna.automation.desktop.windows_impl import WindowsDesktopAutomation
from luna.automation.tools.registry import register_browser_tools, register_core_tools, register_desktop_tools
from luna.config.config import Settings, SettingsManager
from luna.config.paths import LunaPaths, resolve_paths
from luna.core.agent import AgentContext
from luna.core.permissions import PermissionManager
from luna.core.tasks.manager import TaskManager
from luna.core.tasks.models import Task
from luna.core.tools import ToolRegistry
from luna.storage.db import Database
from luna.storage.memory import MemoryStore
from luna.voice.tts import KokoroTTS
from luna.voice.voices import VoiceManager

logger = logging.getLogger(__name__)


class Application:
    """Owns the long-lived services. The UI is a separate layer over this."""

    def __init__(self, home: Path | str | None = None) -> None:
        self.paths: LunaPaths = resolve_paths(home)
        self.settings_manager = SettingsManager(self.paths.config_file)
        self.settings: Settings = self.settings_manager.settings
        self.db = Database(self.paths.database)
        self.memory = MemoryStore(self.paths.database, enabled=self.settings.memory_enabled)
        self.tasks = TaskManager(self.db, self.paths.tasks, max_concurrent=self.settings.tasks.max_concurrent)
        self.permissions = PermissionManager(self.settings.permissions)
        self.tools = ToolRegistry()
        self.models = ModelManager(self.paths)
        self.voices = VoiceManager(self.paths.voices)
        self.tts = KokoroTTS(speed=self.settings.tts.speed)
        self.browser: PlaywrightBrowser | None = PlaywrightBrowser(self.settings.browser, self.paths.browser_profile)
        self.desktop: DesktopAutomation | None = None
        self._lock = threading.RLock()
        self._ensure_desktop()
        self._wire_tools()
        self.tasks.load_persisted()

    def _ensure_desktop(self) -> None:
        try:
            self.desktop = WindowsDesktopAutomation(
                keyboard_delay_ms=self.settings.automation.keyboard_delay_ms
            )
        except Exception as exc:  # noqa: BLE001 — non-Windows or deps unavailable
            logger.info("Desktop automation unavailable: %s", exc)
            self.desktop = None

    def _wire_tools(self) -> None:
        register_core_tools(self.tools, workspace=Path.home())
        if self.browser is not None:
            register_browser_tools(self.tools, self.browser)
        if self.desktop is not None:
            register_desktop_tools(self.tools, self.desktop, self.paths.cache)

    # -- settings sync ------------------------------------------------------------
    def apply_settings(self, settings: Settings) -> None:
        self.settings = settings
        self.memory.set_enabled(settings.memory_enabled)
        # keep the same PermissionManager so the UI approval callback survives
        self.permissions.config = settings.permissions
        self.tts.set_speed(settings.tts.speed)
        kokoro = self.models.find_kokoro(settings.tts.model_name)
        self.tts.set_model(kokoro)
        voice = self.voices.find(settings.tts.voice)
        self.tts.set_voice(voice)

    # -- agent task ----------------------------------------------------------------
    def create_agent_task(self, goal: str, model_fn: Callable[..., Any] | None = None) -> Task:
        from luna.ai.providers import create_provider
        from luna.ai.providers.adapters import agent_chat
        from luna.core.personality import build_personality_prompt

        personality = build_personality_prompt(self.settings.personality)

        def runner(ctx: Any) -> Any:
            if model_fn is not None:
                callable_model = model_fn
            else:
                callable_model = agent_chat(create_provider(self.settings.provider))
            agent = AgentContext(
                ctx,
                self.tools,
                self.permissions,
                model=callable_model,
                personality=personality,
            )
            ctx.log("Agent running.", data={"goal": goal})
            return agent.execute()

        return self.tasks.submit(goal, runner)

    def start_browser(self) -> None:
        if self.browser is None:
            self.browser = PlaywrightBrowser(self.settings.browser, self.paths.browser_profile)
            register_browser_tools(self.tools, self.browser)
        self.browser.start()

    def stop_browser(self) -> None:
        if self.browser is not None:
            self.browser.stop()

    def shutdown(self) -> None:
        self.stop_browser()
        self.tasks.shutdown()
        self.memory.close()
        self.db.close()
