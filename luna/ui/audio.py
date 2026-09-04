"""Audio playback for TTS output using Qt Multimedia (real audio, no fakes)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class AudioPlayer(QObject):
    playback_finished = Signal()
    playback_error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._output = QAudioOutput(self)
        self._output.setVolume(1.0)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._output)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.errorOccurred.connect(self._on_error)

    def play(self, wav_path: Path | str) -> None:
        self._player.stop()
        self._player.setSource(QUrl.fromLocalFile(str(wav_path)))
        self._player.play()

    def stop(self) -> None:
        self._player.stop()

    def _on_status(self, status: Any) -> None:
        from PySide6.QtMultimedia import QMediaPlayer

        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.playback_finished.emit()

    def _on_error(self, error: Any, error_string: str) -> None:
        from PySide6.QtMultimedia import QMediaPlayer

        if error != QMediaPlayer.Error.NoError:
            self.playback_error.emit(error_string)


def synthesize_in_thread(
    tts: Any,
    text: str,
    voice: Any,
    wav_path: Path,
    result_callback: Any,
) -> threading.Thread:
    """Run synthesis off the UI thread; callbacks are delivered via Qt signal."""

    def work() -> None:
        try:
            path = tts.synthesize_to_wav(text, voice=voice, path=wav_path)
            result_callback(True, str(path))
        except Exception as exc:  # noqa: BLE001
            result_callback(False, str(exc))

    thread = threading.Thread(target=work, name="luna-tts-test", daemon=True)
    thread.start()
    return thread
