"""Wake-word detection. The engine is a replaceable component.

Prepared for OpenWakeWord; the pub/sub wrapper lets other engines (Porcupine,
Vosk keyword spotting, etc.) plug in without touching the rest of LUNA.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


class WakeWordError(RuntimeError):
    pass


class WakeWordDetector:
    def __init__(self, engine: str = "disabled", model_path: str | None = None, threshold: float = 0.5) -> None:
        self.engine = engine
        self.model_path = model_path
        self.threshold = threshold
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_detected: Callable[[str], None] | None = None

    def set_callback(self, callback: Callable[[str], None]) -> None:
        self._on_detected = callback

    def start(self) -> None:
        if self.engine == "disabled":
            raise WakeWordError("Wake-word engine is disabled in settings.")
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="luna-kws", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        """OpenWakeWord audio loop."""
        if self.engine != "openwakeword":
            self._running = False
            raise WakeWordError(f"Unsupported wake-word engine: {self.engine}")
        try:
            import openwakeword  # type: ignore[import-not-found]
            from openwakeword.model import Model as OpenWakeModel  # type: ignore[import-not-found]
        except ImportError as exc:
            self._running = False
            raise WakeWordError(
                "openwakeword is not installed. Install the KWS extras: pip install luna-desktop[kws]"
            ) from exc
        try:
            import sounddevice as sd  # type: ignore[import-not-found]
        except ImportError as exc:
            self._running = False
            raise WakeWordError("sounddevice is required for microphone access.") from exc

        model = OpenWakeModel(wakeword_models=[self.model_path], inference_framework="onnx")
        stream = sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=1280)
        with stream:
            while self._running:
                audio, _ = stream.read(1280)
                scores = model.predict(audio)
                if max(scores.values()) >= self.threshold:
                    if self._on_detected:
                        self._on_detected("luna")
                    # debounce
                    for _ in range(8):
                        if not self._running:
                            break
                        stream.read(1280)
