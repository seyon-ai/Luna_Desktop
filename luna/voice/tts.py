"""Kokoro TTS engine — real synthesis through kokoro-onnx + misaki.

Supports the exact user-provided model files:
``model_q8f16.onnx`` (default) and ``model_fp16.onnx``.
No cloud TTS, no Windows system TTS, no audio fakes.
"""

from __future__ import annotations

import io
import threading
import wave
from pathlib import Path
from typing import Any

from luna.ai.model_manager.manager import ModelInfo
from luna.voice.voices import VoiceInfo


class KokoroEngineError(RuntimeError):
    pass


class KokoroTTS:
    """Lazy-loaded Kokoro synth. Model and voice are resolved on first use."""

    def __init__(self, model: ModelInfo | None = None, voice: VoiceInfo | None = None, speed: float = 1.0) -> None:
        self.model = model
        self.voice = voice
        self.speed = speed
        self._lock = threading.Lock()
        self._kokoro = None
        self._g2p = None
        self._g2p_lang = None

    def set_model(self, model: ModelInfo | None) -> None:
        with self._lock:
            self.model = model
            self._kokoro = None
            self._g2p = None

    def set_voice(self, voice: VoiceInfo | None) -> None:
        self.voice = voice

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.5, min(2.0, float(speed)))

    def _ensure(self) -> tuple[Any, Any]:
        if self._kokoro is None:
            if self.model is None:
                raise KokoroEngineError(
                    "No Kokoro model imported. Use Models > Import Model and select "
                    "model_q8f16.onnx or model_fp16.onnx."
                )
            if self.model.format != "onnx_kokoro":
                raise KokoroEngineError(f"Selected model is not a Kokoro model: {self.model.path}")
            try:
                from kokoro_onnx import Kokoro  # type: ignore[import-not-found]
            except ImportError as exc:
                raise KokoroEngineError(
                    "kokoro-onnx is not installed. Install the TTS extras: pip install luna-desktop[tts]"
                ) from exc
            try:
                from misaki import G2P  # type: ignore[import-not-found]
            except ImportError as exc:
                raise KokoroEngineError(
                    "misaki is not installed. Install the TTS extras: pip install luna-desktop[tts]"
                ) from exc
            self._kokoro = Kokoro(self.model.path, repr=False)
            self._g2p = G2P("en-us", version="v1_0", device="cpu")
            self._g2p_lang = "en-us"
        return self._kokoro, self._g2p

    def is_ready(self) -> bool:
        return self.model is not None and self.voice is not None

    def synthesize(self, text: str, voice: VoiceInfo | None = None, speed: float | None = None) -> tuple[Any, int]:
        """Return (float32 samples, sample_rate). Raises on genuine failure."""
        import numpy as np  # lazy: keeps core install free of numpy

        if not text.strip():
            raise ValueError("Text is empty.")
        with self._lock:
            kokoro, g2p = self._ensure()
            voice = voice or self.voice
            if voice is None:
                raise KokoroEngineError("No voice selected. Import a Kokoro voice (.bin) in Voice settings.")
            voice_path = Path(voice.path)
            if not voice_path.exists():
                raise KokoroEngineError(f"Voice file missing: {voice_path}")
            speed = speed or self.speed
            phonemes, _ = g2p(text)
            samples, sample_rate = kokoro.create(phonemes, speed=float(speed), voice=voice_path)
        samples = np.asarray(samples, dtype=np.float32)
        if samples.size == 0:
            raise KokoroEngineError("Kokoro produced no audio samples.")
        return samples, int(sample_rate)

    def synthesize_to_wav(
        self, text: str, voice: VoiceInfo | None = None, path: Path | str | None = None, speed: float | None = None
    ) -> Path:
        import numpy as np

        samples, rate = self.synthesize(text, voice=voice, speed=speed)
        pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
        if path is None:
            path = Path("/tmp") / "luna_tts.wav"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(pcm.tobytes())
        return path

    def synthesize_bytes(self, text: str, voice: VoiceInfo | None = None) -> bytes:
        import numpy as np

        samples, rate = self.synthesize(text, voice=voice)
        pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()
