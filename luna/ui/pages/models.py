"""Models & Voice page: AI model manager plus Kokoro TTS controls."""

from __future__ import annotations

import threading
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from luna.ai.model_manager.manager import ModelInfo, ModelValidationError
from luna.ui.common import card, faint, h1, h2, muted, primary_button


class ModelBridge(QObject):
    changed = Signal(object)


class ModelsPage(QWidget):
    def __init__(self, app: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self.bridge = ModelBridge()
        self._build()
        self.app.models.add_listener(self._on_models)
        self.app.voices.add_listener(self._on_voices)
        self.bridge.changed.connect(lambda _: self.refresh())

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        header = QHBoxLayout()
        header.addWidget(h1("AI Models"))
        header.addStretch(1)
        import_btn = primary_button("Import Model")
        import_btn.clicked.connect(self._import_model)
        header.addWidget(import_btn)
        layout.addLayout(header)
        hint = muted(
            "Import large local models (ONNX, GGUF, safetensors). Models live in "
            "LUNA_HOME/models and are never committed to Git."
        )
        layout.addWidget(hint)
        self.model_list = QListWidget()
        self.model_list.setMinimumHeight(180)
        layout.addWidget(self.model_list, 1)

        # Kokoro TTS section
        tts_frame, tts_box = card()
        tts_box.addWidget(h2("Kokoro Voice"))
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("TTS model"))
        self.tts_model_combo = QComboBox()
        self.tts_model_combo.setMinimumWidth(260)
        self.tts_model_combo.currentIndexChanged.connect(self._select_tts_model)
        model_row.addWidget(self.tts_model_combo)
        model_row.addStretch(1)
        tts_box.addLayout(model_row)
        voice_row = QHBoxLayout()
        voice_row.addWidget(QLabel("Voice"))
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(260)
        self.voice_combo.currentIndexChanged.connect(self._select_voice)
        voice_row.addWidget(self.voice_combo)
        import_voice = QPushButton("Import Voice (.bin)")
        import_voice.clicked.connect(self._import_voice)
        voice_row.addWidget(import_voice)
        remove_voice = QPushButton("Remove Voice")
        remove_voice.clicked.connect(self._remove_voice)
        voice_row.addWidget(remove_voice)
        voice_row.addStretch(1)
        tts_box.addLayout(voice_row)
        tts_box.addWidget(faint("Kokoro supports model_q8f16.onnx (default) and model_fp16.onnx. Voice .bin assets are user-provided."))
        test_row = QHBoxLayout()
        self.speed_combo = QComboBox()
        for speed in ("0.8×", "1.0×", "1.2×"):
            self.speed_combo.addItem(speed)
        self.speed_combo.setCurrentText("1.0×")
        self.speed_combo.currentTextChanged.connect(self._change_speed)
        test_row.addWidget(self.speed_combo)
        self.test_voice = primary_button("Test Voice")
        self.test_voice.clicked.connect(self._test_voice)
        test_row.addWidget(self.test_voice)
        self.tts_status = muted("")
        test_row.addWidget(self.tts_status)
        test_row.addStretch(1)
        tts_box.addLayout(test_row)
        layout.addWidget(tts_frame)
        self.refresh()

    # -- refresh ------------------------------------------------------------------
    def _on_models(self, models: list[ModelInfo]) -> None:
        self.bridge.changed.emit(models)

    def _on_voices(self, voices: Any) -> None:
        self.bridge.changed.emit(voices)

    def refresh(self) -> None:
        self.model_list.clear()
        models = self.app.models.list_models()
        kokoro = [m for m in models if m.format == "onnx_kokoro"]
        active_name = self.app.settings.tts.model_name
        for info in models:
            item = QListWidgetItem()
            widget = self._model_widget(info)
            item.setSizeHint(widget.sizeHint())
            self.model_list.addItem(item)
            self.model_list.setItemWidget(item, widget)
        self._fill_combo(self.tts_model_combo, kokoro, active_name, label=lambda m: f"{m.name} ({m.size_human})")
        self._fill_combo(
            self.voice_combo,
            self.app.voices.list_voices(),
            self.app.settings.tts.voice,
            label=lambda v: f"{v.name} ({v.size_human})",
        )

    def _fill_combo(self, combo: QComboBox, items: list[Any], active: str, label: Any) -> None:
        combo.blockSignals(True)
        combo.clear()
        selected = 0
        for i, item in enumerate(items):
            combo.addItem(label(item), item.id)
            if item.id == active or getattr(item, "name", None) == active:
                selected = i
        combo.setCurrentIndex(selected)
        combo.blockSignals(False)

    def _model_widget(self, info: ModelInfo) -> QWidget:
        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(12, 8, 12, 8)
        row = QHBoxLayout()
        title = QLabel(info.name)
        title.setObjectName("h2")
        row.addWidget(title)
        row.addStretch(1)
        selected = self.app.settings.tts.model_name == info.name
        status = QLabel("ACTIVE" if selected else ("KOKORO" if info.format == "onnx_kokoro" else "INSTALLED"))
        status.setStyleSheet("color:#5dd29a; font-size:11px; font-weight:700;")
        row.addWidget(status)
        box.addLayout(row)
        meta = QLabel(
            f"{info.format}  ·  {info.size_human}  ·  {info.kind}  ·  {info.path[:80]}"
        )
        meta.setObjectName("faint")
        box.addWidget(meta)
        actions = QHBoxLayout()
        test = QPushButton("Test")
        test.clicked.connect(lambda _=False, m=info.id: self._test_model(m))
        actions.addWidget(test)
        remove = QPushButton("Remove")
        remove.setObjectName("danger")
        remove.clicked.connect(lambda _=False, m=info.id: self._remove_model(m))
        actions.addWidget(remove)
        if info.format == "onnx_kokoro":
            make_active = QPushButton("Use for Voice")
            make_active.clicked.connect(lambda _=False, m=info.id: self._activate_model(m))
            actions.addWidget(make_active)
        actions.addStretch(1)
        box.addLayout(actions)
        return container

    # -- actions ---------------------------------------------------------------------
    def _import_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import AI model",
            "",
            "Models (*.onnx *.gguf *.safetensors *.bin *.pt *.pth);;All files (*)",
        )
        if not path:
            return
        try:
            result = self.app.models.import_file(path)
        except ModelValidationError as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        if result.errors:
            QMessageBox.critical(self, "Model invalid", "\n".join(result.errors))
            return
        QMessageBox.information(self, "Model imported", f"Imported {result.info.name} ({result.info.size_human}).")
        self.refresh()

    def _test_model(self, model_id: str) -> None:
        try:
            result = self.app.models.test(model_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Model test failed", str(exc))
            return
        details = {k: v for k, v in result.items() if k != "output"}
        QMessageBox.information(self, "Model test passed", f"{details}")

    def _remove_model(self, model_id: str) -> None:
        info = self.app.models.get(model_id)
        if info is None:
            return
        confirm = QMessageBox.question(
            self, "Remove model", f"Remove {info.name} from LUNA (deletes its folder)?"
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.app.models.remove(model_id)
            self.refresh()

    def _activate_model(self, model_id: str) -> None:
        info = self.app.models.get(model_id)
        if info is None:
            return
        self.app.settings_manager.update(lambda s: setattr(s.tts, "model_name", info.name))
        self.app.apply_settings(self.app.settings)
        self.refresh()

    def _select_tts_model(self) -> None:
        idx = self.tts_model_combo.currentIndex()
        model_id = self.tts_model_combo.itemData(idx)
        if not model_id:
            return
        info = self.app.models.get(model_id)
        if info is None:
            return
        self.app.settings_manager.update(lambda s: setattr(s.tts, "model_name", info.name))
        self.app.apply_settings(self.app.settings)

    def _select_voice(self) -> None:
        idx = self.voice_combo.currentIndex()
        voice_id = self.voice_combo.itemData(idx)
        if not voice_id:
            return
        self.app.settings_manager.update(lambda s: setattr(s.tts, "voice", voice_id))
        self.app.apply_settings(self.app.settings)

    def _change_speed(self, text: str) -> None:
        speed = float(text.rstrip("×"))
        self.app.settings_manager.update(lambda s: setattr(s.tts, "speed", speed))
        self.app.apply_settings(self.app.settings)

    def _import_voice(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Kokoro voice", "", "Voice assets (*.bin *.onnx *.npz)")
        if not path:
            return
        try:
            voice = self.app.voices.import_voice(path)
        except ModelValidationError as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        self.app.settings_manager.update(lambda s: setattr(s.tts, "voice", voice.id))
        self.app.apply_settings(self.app.settings)
        self.refresh()

    def _remove_voice(self) -> None:
        idx = self.voice_combo.currentIndex()
        voice_id = self.voice_combo.itemData(idx)
        if not voice_id:
            return
        confirm = QMessageBox.question(self, "Remove voice", "Remove this voice asset from LUNA?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.app.voices.remove(voice_id)
            self.refresh()

    # -- real TTS playback -----------------------------------------------------------
    def _test_voice(self) -> None:
        status = self.app.tts
        if not status.is_ready():
            QMessageBox.warning(
                self,
                "Not ready",
                "Import and select a Kokoro model (model_q8f16.onnx / model_fp16.onnx) "
                "and a voice .bin before testing.",
            )
            return
        self.tts_status.setText("Synthesizing…")
        self.test_voice.setEnabled(False)
        wav_path = self.app.paths.cache / "voice_test.wav"

        def done(ok: bool, message: str) -> None:
            QTimer.singleShot(0, lambda: self._on_synth_done(ok, message, wav_path))

        def work() -> None:
            try:
                self.app.tts.synthesize_to_wav("Hello, I am Luna, your desktop assistant.", path=wav_path)
                done(True, str(wav_path))
            except Exception as exc:  # noqa: BLE001
                done(False, str(exc))

        threading.Thread(target=work, name="luna-tts", daemon=True).start()

    def _on_synth_done(self, ok: bool, message: str, wav_path: Any) -> None:
        self.test_voice.setEnabled(True)
        if not ok:
            self.tts_status.setText("TTS failed")
            QMessageBox.critical(self, "TTS failed", message)
            return
        self.app.audio.play(wav_path)
        self.tts_status.setText("Playing synthesized speech…")
        QTimer.singleShot(30000, lambda: self.tts_status.setText(""))
