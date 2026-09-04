"""Voice Manager — import/list/select/test/remove Kokoro voice assets.

Voice .bin assets live under ``LUNA_HOME/voices``. They are user-provided and
never committed to Git.
"""

from __future__ import annotations

import json
import shutil
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from luna.ai.model_manager.manager import ModelValidationError, human_size

VALID_VOICE_SUFFIXES = {".bin", ".onnx", ".npz"}
MIN_VOICE_BYTES = 128 * 1024  # real Kokoro voices are several hundred KB+


@dataclass
class VoiceInfo:
    id: str
    name: str
    path: str
    size_bytes: int
    language: str = "en"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def size_human(self) -> str:
        return human_size(self.size_bytes)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VoiceManager:
    def __init__(self, voices_dir: Path | str) -> None:
        self.voices_dir = Path(voices_dir)
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.voices_dir / "voices.json"
        self._lock = threading.RLock()
        self._voices: dict[str, VoiceInfo] = {}
        self._listeners: list[Callable[[list[VoiceInfo]], None]] = []
        self._load()

    # -- persistence -------------------------------------------------------------
    def _load(self) -> None:
        if self._index_path.exists():
            try:
                data = json.loads(self._index_path.read_text(encoding="utf-8"))
                for item in data.get("voices", []):
                    info = VoiceInfo(**item)
                    if Path(info.path).exists():
                        self._voices[info.id] = info
            except (json.JSONDecodeError, TypeError):
                pass

    def _save(self) -> None:
        with self._lock:
            payload = {"version": 1, "voices": [v.to_dict() for v in self._voices.values()]}
            tmp = self._index_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self._index_path)

    # -- queries -------------------------------------------------------------------
    def list_voices(self) -> list[VoiceInfo]:
        return sorted(self._voices.values(), key=lambda v: v.name.lower())

    def get(self, voice_id: str) -> VoiceInfo | None:
        return self._voices.get(voice_id)

    def find(self, name: str) -> VoiceInfo | None:
        for v in self.list_voices():
            if v.name == name or Path(v.path).stem == name:
                return v
        return None

    # -- import ---------------------------------------------------------------------
    def import_voice(self, source: Path | str, name: str | None = None, copy: bool = True) -> VoiceInfo:
        source = Path(source).expanduser().resolve()
        if not source.exists() or not source.is_file():
            raise ModelValidationError(f"Voice asset not found: {source}")
        if source.suffix.lower() not in VALID_VOICE_SUFFIXES:
            raise ModelValidationError(
                f"Unsupported voice asset type '{source.suffix}'. Supported: {', '.join(VALID_VOICE_SUFFIXES)}"
            )
        if source.stat().st_size < MIN_VOICE_BYTES:
            raise ModelValidationError(
                f"Voice asset is too small ({human_size(source.stat().st_size)}); it is likely not a valid Kokoro voice."
            )
        voice_id = "".join(c if c.isalnum() or c in "._-" else "_" for c in (name or source.stem))
        dest = self.voices_dir / source.name
        if dest.exists() and dest.resolve() != source.resolve():
            dest = self.voices_dir / f"{source.stem}-{voice_id}.{source.suffix}"
        if copy and source.resolve() != dest.resolve():
            shutil.copy2(source, dest)
        info = VoiceInfo(id=voice_id, name=name or source.stem, path=str(dest), size_bytes=dest.stat().st_size)
        with self._lock:
            self._voices[voice_id] = info
        self._save()
        self._notify()
        return info

    def remove(self, voice_id: str) -> bool:
        with self._lock:
            info = self._voices.pop(voice_id, None)
        if info is None:
            return False
        try:
            Path(info.path).unlink(missing_ok=True)
        except OSError:
            pass
        self._save()
        self._notify()
        return True

    def add_listener(self, callback: Callable[[list[VoiceInfo]], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb(self.list_voices())
