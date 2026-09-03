"""Settings page — every control modifies real application behavior."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from luna.config.config import PermissionConfig, Settings
from luna.ui.common import card, faint, h1, h2, muted

PERMISSION_ACTIONS = [
    ("read_file", "Read files"),
    ("list_directory", "List directories"),
    ("create_file", "Create files"),
    ("modify_file", "Modify files"),
    ("delete_file", "Delete files"),
    ("move_file", "Move/rename files"),
    ("run_command", "Run commands"),
    ("send_message", "Send external messages"),
    ("submit_form", "Submit forms"),
    ("purchase", "Purchases"),
    ("system_config", "System configuration"),
    ("browser_navigate", "Browser navigation"),
    ("browser_click", "Browser clicks"),
    ("browser_type", "Browser typing"),
    ("screenshot", "Screenshots"),
    ("desktop_control", "Desktop control"),
]


class SettingsPage(QWidget):
    def __init__(self, app: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self._build()
        self._load()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(8)
        outer.addWidget(h1("Settings"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.tabs = QTabWidget()
        self.tabs.setMinimumHeight(520)
        self._general()
        self._ai()
        self._voice()
        self._personality()
        self._memory()
        self._automation()
        self._permissions()
        self._browser()
        self._background()
        self._notifications()
        self._privacy_about()
        self.scroll.setWidget(self.tabs)
        outer.addWidget(self.scroll, 1)
        self.status = muted("")
        outer.addWidget(self.status)

    def _tick(self, msg: str = "Saved") -> None:
        self.status.setText(msg)

    # -- sections -----------------------------------------------------------------
    def _general(self) -> None:
        tab = QWidget()
        form = QFormLayout(tab)
        frame, box = card()
        box.addWidget(h2("General"))
        self.minimized = QCheckBox("Launch minimized to tray")
        self.minimized.toggled.connect(lambda v: self._save(lambda s: setattr(s, "launch_minimized", v)))
        form.addRow(self.minimized)
        self.hide_tray = QCheckBox("Close hides LUNA to the system tray (running tasks continue)")
        self.hide_tray.toggled.connect(lambda v: self._save(lambda s: setattr(s, "hide_to_tray_on_close", v)))
        form.addRow(self.hide_tray)
        box.addLayout(form)
        self.tabs.addTab(tab, "General")

    def _ai(self) -> None:
        tab = QWidget()
        frame, box = card()
        box.addWidget(h2("AI Provider"))
        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItems(["ollama", "openai_compatible", "llama_cpp"])
        self.provider.currentTextChanged.connect(lambda v: self._save(lambda s: setattr(s.provider, "provider", v)))
        form.addRow("Provider", self.provider)
        self.base_url = QLineEdit()
        self.base_url.editingFinished.connect(
            lambda: self._save(lambda s: setattr(s.provider, "base_url", self.base_url.text().strip()))
        )
        form.addRow("Base URL", self.base_url)
        self.model_name = QLineEdit()
        self.model_name.setPlaceholderText("e.g. llama3.2")
        self.model_name.editingFinished.connect(
            lambda: self._save(lambda s: setattr(s.provider, "model", self.model_name.text().strip()))
        )
        form.addRow("Model", self.model_name)
        self.api_key_env = QLineEdit()
        self.api_key_env.editingFinished.connect(
            lambda: self._save(lambda s: setattr(s.provider, "api_key_env", self.api_key_env.text().strip()))
        )
        form.addRow("API key env var", self.api_key_env)
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.1)
        self.temperature.valueChanged.connect(
            lambda v: self._save(lambda s: setattr(s.provider, "temperature", float(v)))
        )
        form.addRow("Temperature", self.temperature)
        box.addLayout(form)
        box.addWidget(faint("Default provider is Ollama — fully local. Keys are read from the environment variable above and never stored."))
        self.tabs.addTab(tab, "AI Models")

    def _voice(self) -> None:
        tab = QWidget()
        frame, box = card()
        box.addWidget(h2("Voice"))
        form = QFormLayout()
        self.tts_model = QLineEdit()
        self.tts_model.editingFinished.connect(
            lambda: self._save(lambda s: setattr(s.tts, "model_name", self.tts_model.text().strip()))
        )
        form.addRow("Kokoro model file", self.tts_model)
        self.tts_speed = QDoubleSpinBox()
        self.tts_speed.setRange(0.5, 2.0)
        self.tts_speed.setSingleStep(0.1)
        self.tts_speed.valueChanged.connect(lambda v: self._save(lambda s: setattr(s.tts, "speed", float(v))))
        form.addRow("Speech speed", self.tts_speed)
        box.addLayout(form)
        box.addWidget(faint("Kokoro uses model_q8f16.onnx or model_fp16.onnx imported in Models. No cloud TTS."))
        self.tabs.addTab(tab, "Voice")

    def _personality(self) -> None:
        tab = QWidget()
        frame, box = card()
        box.addWidget(h2("Personality"))
        form = QFormLayout()
        self.p_mode = QComboBox()
        self.p_mode.addItems(["professional", "friendly", "companion", "concise", "custom"])
        self.p_mode.currentTextChanged.connect(
            lambda v: self._save(lambda s: setattr(s.personality, "mode", v))
        )
        form.addRow("Mode", self.p_mode)
        self.p_tone = QLineEdit()
        self.p_tone.editingFinished.connect(
            lambda: self._save(lambda s: setattr(s.personality, "tone", self.p_tone.text().strip()))
        )
        form.addRow("Tone", self.p_tone)
        self.p_verbosity = QComboBox()
        self.p_verbosity.addItems(["concise", "balanced", "detailed"])
        self.p_verbosity.currentTextChanged.connect(
            lambda v: self._save(lambda s: setattr(s.personality, "verbosity", v))
        )
        form.addRow("Verbosity", self.p_verbosity)
        self.p_style = QLineEdit()
        self.p_style.editingFinished.connect(
            lambda: self._save(
                lambda s: setattr(s.personality, "conversational_style", self.p_style.text().strip())
            )
        )
        form.addRow("Conversational style", self.p_style)
        self.p_friendly = QSlider(Qt.Orientation.Horizontal)
        self.p_friendly.setRange(0, 100)
        self.p_friendly.valueChanged.connect(
            lambda v: self._save(lambda s: setattr(s.personality, "friendliness", v / 100.0))
        )
        form.addRow("Friendliness", self.p_friendly)
        self.p_format = QComboBox()
        self.p_format.addItems(["text", "markdown"])
        self.p_format.currentTextChanged.connect(
            lambda v: self._save(lambda s: setattr(s.personality, "response_format", v))
        )
        form.addRow("Response format", self.p_format)
        self.p_custom = QLineEdit()
        self.p_custom.editingFinished.connect(
            lambda: self._save(lambda s: setattr(s.personality, "custom_prompt", self.p_custom.text().strip()))
        )
        form.addRow("Custom prompt", self.p_custom)
        box.addLayout(form)
        box.addWidget(faint("Friendly Companion is warm and supportive — never a romantic-partner simulation."))
        self.tabs.addTab(tab, "Personality")

    def _memory(self) -> None:
        tab = QWidget()
        frame, box = card()
        box.addWidget(h2("Memory"))
        self.mem_enabled = QCheckBox("Enable local memory (SQLite)")
        self.mem_enabled.toggled.connect(lambda v: self._save(lambda s: setattr(s, "memory_enabled", v)))
        box.addWidget(self.mem_enabled)
        box.addWidget(faint("Stored at LUNA_HOME/memory/luna.db. LUNA never uploads private web data."))
        self.tabs.addTab(tab, "Memory")

    def _automation(self) -> None:
        tab = QWidget()
        frame, box = card()
        box.addWidget(h2("Automation"))
        form = QFormLayout()
        self.coord_fallback = QCheckBox("Allow screen-coordinate fallback when accessibility is unavailable")
        self.coord_fallback.toggled.connect(
            lambda v: self._save(lambda s: setattr(s.automation, "fallback_to_coordinates", v))
        )
        form.addRow(self.coord_fallback)
        self.key_delay = QSpinBox()
        self.key_delay.setRange(0, 500)
        self.key_delay.valueChanged.connect(
            lambda v: self._save(lambda s: setattr(s.automation, "keyboard_delay_ms", int(v)))
        )
        form.addRow("Keyboard delay (ms)", self.key_delay)
        box.addLayout(form)
        self.tabs.addTab(tab, "Automation")

    def _permissions(self) -> None:
        tab = QWidget()
        frame, box = card()
        box.addWidget(h2("Permissions"))
        self.permission_combos: dict[str, QComboBox] = {}
        form = QFormLayout()
        for action, label in PERMISSION_ACTIONS:
            combo = QComboBox()
            combo.addItems(["allow", "ask", "deny"])
            combo.currentTextChanged.connect(
                lambda v, a=action, c=combo: self._save(
                    lambda s: s.permissions.rules.update({a: v}), tick=False
                )
            )
            form.addRow(label, combo)
            self.permission_combos[action] = combo
        self.p_default = QComboBox()
        self.p_default.addItems(["allow", "ask", "deny"])
        self.p_default.currentTextChanged.connect(
            lambda v: self._save(lambda s: setattr(s.permissions, "default", v))
        )
        form.addRow("Default for unknown actions", self.p_default)
        box.addLayout(form)
        box.addWidget(faint("Deliveries, purchases and message sending are never silent: they require approval."))
        self.tabs.addTab(tab, "Permissions")

    def _browser(self) -> None:
        tab = QWidget()
        frame, box = card()
        box.addWidget(h2("Browser"))
        form = QFormLayout()
        self.br_channel = QComboBox()
        self.br_channel.addItems(["msedge", "chrome", "chromium"])
        self.br_channel.currentTextChanged.connect(
            lambda v: self._save(lambda s: setattr(s.browser, "channel", v))
        )
        form.addRow("Browser channel", self.br_channel)
        self.br_headless = QCheckBox("Headless (no visible window)")
        self.br_headless.toggled.connect(lambda v: self._save(lambda s: setattr(s.browser, "headless", v)))
        form.addRow(self.br_headless)
        self.br_url = QLineEdit()
        self.br_url.editingFinished.connect(
            lambda: self._save(lambda s: setattr(s.browser, "default_url", self.br_url.text().strip()))
        )
        form.addRow("Default URL", self.br_url)
        box.addLayout(form)
        box.addWidget(faint("Profile is stored at LUNA_HOME/cache/browser-profile; Playwright starts/uses the chosen channel."))
        self.tabs.addTab(tab, "Browser")

    def _background(self) -> None:
        tab = QWidget()
        frame, box = card()
        box.addWidget(h2("Background Tasks"))
        form = QFormLayout()
        self.bg_concurrent = QSpinBox()
        self.bg_concurrent.setRange(1, 8)
        self.bg_concurrent.valueChanged.connect(
            lambda v: self._save(lambda s: setattr(s.tasks, "max_concurrent", int(v)))
        )
        form.addRow("Max concurrent tasks", self.bg_concurrent)
        self.bg_max_steps = QSpinBox()
        self.bg_max_steps.setRange(4, 200)
        self.bg_max_steps.valueChanged.connect(
            lambda v: self._save(lambda s: setattr(s.tasks, "max_steps", int(v)))
        )
        form.addRow("Max agent steps per task", self.bg_max_steps)
        box.addLayout(form)
        box.addWidget(faint("Tasks run on worker threads; minimizing or closing LUNA to tray never kills them."))
        self.tabs.addTab(tab, "Background Tasks")

    def _notifications(self) -> None:
        tab = QWidget()
        frame, box = card()
        box.addWidget(h2("Notifications"))
        self.notif_enabled = QCheckBox("Enable notifications")
        self.notif_enabled.toggled.connect(lambda v: self._save(lambda s: setattr(s.notifications, "enabled", v)))
        box.addWidget(self.notif_enabled)
        self.notif_done = QCheckBox("Notify when tasks complete")
        self.notif_done.toggled.connect(
            lambda v: self._save(lambda s: setattr(s.notifications, "on_task_complete", v))
        )
        box.addWidget(self.notif_done)
        self.notif_failed = QCheckBox("Notify when tasks fail")
        self.notif_failed.toggled.connect(
            lambda v: self._save(lambda s: setattr(s.notifications, "on_task_failed", v))
        )
        box.addWidget(self.notif_failed)
        self.tabs.addTab(tab, "Notifications")

    def _privacy_about(self) -> None:
        tab = QWidget()
        frame, box = card()
        box.addWidget(h2("Privacy & About"))
        self.telemetry = QCheckBox("Opt-in anonymous diagnostics (disabled by default)")
        self.telemetry.toggled.connect(lambda v: self._save(lambda s: setattr(s, "telemetry", v)))
        box.addWidget(self.telemetry)
        box.addWidget(faint("LUNA is local-first. No Firebase, no hidden uploads, no hard-coded keys."))
        box.addWidget(muted("LUNA Desktop 0.1.0 — build from zero in this repository."))
        self.tabs.addTab(tab, "Privacy/About")

    # -- load/save ------------------------------------------------------------------
    def _load(self) -> None:
        s: Settings = self.app.settings
        self.minimized.setChecked(s.launch_minimized)
        self.hide_tray.setChecked(s.hide_to_tray_on_close)
        self.provider.setCurrentText(s.provider.provider)
        self.base_url.setText(s.provider.base_url)
        self.model_name.setText(s.provider.model)
        self.api_key_env.setText(s.provider.api_key_env)
        self.temperature.setValue(s.provider.temperature)
        self.tts_model.setText(s.tts.model_name)
        self.tts_speed.setValue(s.tts.speed)
        self.p_mode.setCurrentText(s.personality.mode)
        self.p_tone.setText(s.personality.tone)
        self.p_verbosity.setCurrentText(s.personality.verbosity)
        self.p_style.setText(s.personality.conversational_style)
        self.p_friendly.setValue(int(s.personality.friendliness * 100))
        self.p_format.setCurrentText(s.personality.response_format)
        self.p_custom.setText(s.personality.custom_prompt)
        self.mem_enabled.setChecked(s.memory_enabled)
        self.coord_fallback.setChecked(s.automation.fallback_to_coordinates)
        self.key_delay.setValue(s.automation.keyboard_delay_ms)
        self.p_default.setCurrentText(s.permissions.default)
        for action, combo in self.permission_combos.items():
            combo.setCurrentText(s.permissions.rules.get(action, s.permissions.default))
        self.br_channel.setCurrentText(s.browser.channel)
        self.br_headless.setChecked(s.browser.headless)
        self.br_url.setText(s.browser.default_url)
        self.bg_concurrent.setValue(s.tasks.max_concurrent)
        self.bg_max_steps.setValue(s.tasks.max_steps)
        self.notif_enabled.setChecked(s.notifications.enabled)
        self.notif_done.setChecked(s.notifications.on_task_complete)
        self.notif_failed.setChecked(s.notifications.on_task_failed)
        self.telemetry.setChecked(s.telemetry)

    def _save(self, mutator: Any, tick: bool = True) -> None:
        self.app.settings_manager.update(mutator)
        self.app.apply_settings(self.app.settings)
        if tick:
            self._tick("Saved")
