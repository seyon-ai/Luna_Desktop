"""Configuration model and persistence.

Settings are stored as plain JSON at ``LUNA_HOME/config/config.json``. Every
setting in this module is read by the application; nothing here is decorative.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import os
import threading
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Callable

CONFIG_VERSION = 1


@dataclass
class PersonalityConfig:
    mode: str = "professional"  # professional|friendly|companion|concise|custom
    tone: str = "calm"
    verbosity: str = "balanced"  # concise|balanced|detailed
    conversational_style: str = "direct"
    friendliness: float = 0.5
    response_format: str = "text"  # text|markdown
    custom_prompt: str = ""


@dataclass
class ProviderConfig:
    provider: str = "ollama"  # ollama|openai_compatible|llama_cpp
    base_url: str = "http://127.0.0.1:11434"
    model: str = ""
    api_key_env: str = "LUNA_OPENAI_API_KEY"
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout_seconds: float = 120.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionConfig:
    default: str = "ask"  # allow|ask|deny
    # action -> allow|ask|deny. command and delete default to "ask".
    rules: dict[str, str] = field(
        default_factory=lambda: {
            "read_file": "allow",
            "list_directory": "allow",
            "create_file": "allow",
            "modify_file": "allow",
            "delete_file": "ask",
            "move_file": "ask",
            "run_command": "ask",
            "send_message": "ask",
            "submit_form": "ask",
            "purchase": "deny",
            "system_config": "ask",
            "browser_navigate": "allow",
            "browser_click": "allow",
            "browser_type": "allow",
            "screenshot": "allow",
            "desktop_control": "ask",
        }
    )
    auto_approve_ask_policy: bool = False


@dataclass
class TTSConfig:
    backend: str = "auto"  # auto|kokoro_onnx|kokoro|onnxruntime
    model_name: str = "model_q8f16.onnx"
    voice: str = ""
    speed: float = 1.0
    language: str = "en-us"


@dataclass
class STTConfig:
    engine: str = "disabled"  # disabled|whisper|vosk
    model: str = "small.en"
    language: str = "en"


@dataclass
class KWSConfig:
    engine: str = "disabled"  # disabled|openwakeword
    model: str = ""
    wake_word: str = "luna"
    threshold: float = 0.5


@dataclass
class BrowserConfig:
    engine: str = "playwright"
    channel: str = "msedge"  # msedge|chrome|chromium
    headless: bool = False
    slow_mo_ms: int = 0
    default_url: str = "https://www.google.com"
    viewport_width: int = 1280
    viewport_height: int = 800


@dataclass
class AutomationConfig:
    fallback_to_coordinates: bool = True
    keyboard_delay_ms: int = 20
    screenshot_format: str = "png"
    max_read_screen_chars: int = 8000


@dataclass
class TaskConfig:
    max_concurrent: int = 2
    max_steps: int = 24
    retry_attempts: int = 2
    history_limit: int = 200


@dataclass
class NotificationConfig:
    enabled: bool = True
    on_task_complete: bool = True
    on_task_failed: bool = True
    on_permission_request: bool = True


@dataclass
class Settings:
    version: int = CONFIG_VERSION
    personality: PersonalityConfig = field(default_factory=PersonalityConfig)
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    permissions: PermissionConfig = field(default_factory=PermissionConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    kws: KWSConfig = field(default_factory=KWSConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    automation: AutomationConfig = field(default_factory=AutomationConfig)
    tasks: TaskConfig = field(default_factory=TaskConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    memory_enabled: bool = True
    hide_to_tray_on_close: bool = True
    launch_minimized: bool = False
    telemetry: bool = False


def _clean_dict(value: dict[str, Any], cls: type) -> dict[str, Any]:
    names = {f.name for f in dataclasses.fields(cls)}
    return {k: v for k, v in value.items() if k in names}


def settings_from_dict(data: dict[str, Any]) -> Settings:
    current = Settings()
    for f in fields(current):
        if f.name in data and isinstance(data[f.name], dict):
            cls = f.type if isinstance(f.type, type) else globals().get(f.type)
            if not isinstance(cls, type):
                continue
            value = _clean_dict(data[f.name], cls)
            setattr(current, f.name, cls(**value))  # type: ignore[call-arg]
        elif f.name in data:
            setattr(current, f.name, data[f.name])
    current.version = CONFIG_VERSION
    return current


class SettingsManager:
    """Loads, validates, persists and notifies about settings changes."""

    def __init__(self, config_path: Path | str) -> None:
        self.path = Path(config_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._listeners: list[Callable[[Settings, Settings], None]] = []
        self.settings = self.load()

    def load(self) -> Settings:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return settings_from_dict(data)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        settings = Settings()
        self._write(settings)
        return settings

    def _write(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def update(self, mutator: Callable[[Settings], None]) -> Settings:
        with self._lock:
            old = self.settings
            new = copy.deepcopy(old)
            mutator(new)
            self._write(new)
            self.settings = new
            for listener in list(self._listeners):
                listener(new, old)
            return new

    def save(self) -> None:
        with self._lock:
            self._write(self.settings)

    def add_listener(self, listener: Callable[[Settings, Settings], None]) -> None:
        self._listeners.append(listener)

    @staticmethod
    def resolve_api_key(env_var: str) -> str | None:
        return os.environ.get(env_var) or None
