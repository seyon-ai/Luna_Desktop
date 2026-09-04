from __future__ import annotations

import json

import pytest

from luna.config.config import SettingsManager, settings_from_dict
from luna.config.paths import LunaPaths, default_luna_home, resolve_paths


@pytest.fixture
def settings_manager(tmp_home):
    return SettingsManager(tmp_home / "config" / "config.json")


def test_default_home_uses_env_override(tmp_home, monkeypatch):
    monkeypatch.setenv("LUNA_HOME", str(tmp_home / "custom"))
    paths = resolve_paths()
    assert paths.root == (tmp_home / "custom").resolve()
    assert paths.models.exists()
    assert paths.voices.exists()
    assert paths.memory.exists()
    assert paths.tasks.exists()
    assert paths.logs.exists()
    assert paths.cache.exists()
    assert paths.config.exists()
    assert paths.browser_profile.exists()


def test_layout_created(tmp_home):
    paths = resolve_paths(tmp_home)
    assert paths.database == paths.memory / "luna.db"
    assert paths.config_file == paths.config / "config.json"


def test_paths_as_dict(tmp_home):
    paths = resolve_paths(tmp_home)
    d = paths.as_dict()
    assert set(d) == {"root", "models", "voices", "memory", "tasks", "logs", "cache", "browser_profile", "config"}


def test_settings_defaults(settings_manager):
    s = settings_manager.settings
    assert s.provider.provider == "ollama"
    assert s.permissions.rules["delete_file"] == "ask"
    assert s.permissions.rules["purchase"] == "deny"
    assert s.tts.model_name == "model_q8f16.onnx"
    assert s.personality.mode == "professional"
    assert s.memory_enabled is True
    assert s.hide_to_tray_on_close is True


def test_settings_roundtrip(settings_manager):
    settings_manager.update(lambda s: setattr(s.provider, "model", "llama3.2:8b"))
    settings_manager.update(lambda s: s.permissions.rules.update({"delete_file": "deny"}))
    reloaded = SettingsManager(settings_manager.path)
    assert reloaded.settings.provider.model == "llama3.2:8b"
    assert reloaded.settings.permissions.rules["delete_file"] == "deny"


def test_update_isolation(settings_manager):
    original = settings_manager.settings.permissions.rules["send_message"]
    settings_manager.update(lambda s: s.permissions.rules.update({"send_message": "deny"}))
    assert original == "ask"
    assert settings_manager.settings.permissions.rules["send_message"] == "deny"
    # reloaded file must also be deny
    data = json.loads(settings_manager.path.read_text(encoding="utf-8"))
    assert data["permissions"]["rules"]["send_message"] == "deny"


def test_settings_from_dict_ignores_unknown():
    data = {
        "memory_enabled": False,
        "nonexistent_field": 123,
        "provider": {"provider": "openai_compatible", "opaque": "x"},
    }
    s = settings_from_dict(data)
    assert s.memory_enabled is False
    assert s.provider.provider == "openai_compatible"


def test_api_key_from_env(monkeypatch):
    monkeypatch.setenv("LUNA_TEST_KEY", "secret-value")
    assert SettingsManager.resolve_api_key("LUNA_TEST_KEY") == "secret-value"
    assert SettingsManager.resolve_api_key("LUNA_MISSING_KEY") is None


def test_listener_notified(settings_manager):
    seen = []
    settings_manager.add_listener(lambda new, old: seen.append(new.provider.model))
    settings_manager.update(lambda s: setattr(s.provider, "model", "x"))
    assert seen == ["x"]
