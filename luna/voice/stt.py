"""Speech-to-text. Engine is replaceable; default uses faster-whisper locally."""

from __future__ import annotations

import threading
from typing import Any


class STTEngineError(RuntimeError):
    pass


class WhisperSTT:
    def __init__(self, model: str = "small.en", language: str = "en", device: str = "auto") -> None:
        self.model_name = model
        self.language = language
        self.device = device
        self._model = None
        self._lock = threading.Lock()

    def _ensure(self) -> Any:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel  # type: ignore[import-not-found]
            except ImportError as exc:
                raise STTEngineError(
                    "faster-whisper is not installed. Install the STT extras: pip install luna-desktop[stt]"
                ) from exc
            self._model = WhisperModel(self.model_name, device=self.device, compute_type="int8")
        return self._model

    def transcribe(self, audio_path: str, language: str | None = None) -> str:
        with self._lock:
            model = self._ensure()
            segments, _info = model.transcribe(audio_path, language=language or self.language, beam_size=5)
            text = "".join(segment.text for segment in segments).strip()
        if not text:
            raise STTEngineError("No speech recognized.")
        return text
