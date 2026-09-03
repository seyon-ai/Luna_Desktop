"""Model Manager — import, validate, detect, select, test and remove local models.

Models live under ``LUNA_HOME/models`` and are never committed to Git.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from luna.config.paths import LunaPaths

KOKORO_TTS_MODELS = ("model_q8f16.onnx", "model_fp16.onnx")
ONNX_MAGIC = b"\x08"
GGUF_MAGIC = b"GGUF"


@dataclass
class ModelInfo:
    id: str
    name: str
    path: str
    format: str
    size_bytes: int
    kind: str = "llm"  # llm|tts
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def size_human(self) -> str:
        return human_size(self.size_bytes)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImportResult:
    info: ModelInfo
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


class ModelValidationError(Exception):
    pass


def detect_format(path: Path) -> str:
    """Detect the model container format from magic bytes / extension."""
    with path.open("rb") as fh:
        head = fh.read(8)
    name = path.name.lower()
    if name.startswith("model_") and name.endswith(".onnx"):
        return "onnx_kokoro"
    if head.startswith(ONNX_MAGIC) and name.endswith(".onnx"):
        return "onnx"
    if head.startswith(GGUF_MAGIC):
        return "gguf"
    if path.suffix.lower() in (".safetensors", ".st"):
        return "safetensors"
    if path.suffix.lower() in (".bin",):
        return "bin"
    if path.suffix.lower() in (".pt", ".pth"):
        return "torch"
    return path.suffix.lower().lstrip(".") or "unknown"


def human_size(num: int) -> str:
    size = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


class ModelManager:
    def __init__(self, paths: LunaPaths) -> None:
        self.paths = paths
        self.models_dir = paths.models
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._registry_path = self.models_dir / "models.json"
        self._lock = threading.RLock()
        self._models: dict[str, ModelInfo] = {}
        self._load_registry()
        self._import_listeners: list[Callable[[list[ModelInfo]], None]] = []

    # -- persistence -----------------------------------------------------------
    def _load_registry(self) -> None:
        if self._registry_path.exists():
            try:
                data = json.loads(self._registry_path.read_text(encoding="utf-8"))
                for item in data.get("models", []):
                    info = ModelInfo(**item)
                    if Path(info.path).exists():
                        self._models[info.id] = info
            except (json.JSONDecodeError, TypeError):
                pass

    def _save_registry(self) -> None:
        with self._lock:
            payload = {"version": 1, "models": [m.to_dict() for m in self._models.values()]}
            tmp = self._registry_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self._registry_path)

    # -- queries ---------------------------------------------------------------
    def list_models(self, kind: str | None = None) -> list[ModelInfo]:
        models = list(self._models.values())
        if kind:
            models = [m for m in models if m.kind == kind]
        return sorted(models, key=lambda m: m.name.lower())

    def get(self, model_id: str) -> ModelInfo | None:
        return self._models.get(model_id)

    def find_kokoro(self, preferred: str = "model_q8f16.onnx") -> ModelInfo | None:
        models = [m for m in self._models.values() if m.kind == "tts"]
        for m in sorted(models, key=lambda m: m.name):
            if m.name == preferred:
                return m
        for m in sorted(models, key=lambda m: m.name):
            if m.format == "onnx_kokoro":
                return m
        return None

    # -- import ----------------------------------------------------------------
    def import_file(
        self,
        source: Path | str,
        name: str | None = None,
        kind: str | None = None,
        copy: bool = True,
    ) -> ImportResult:
        source = Path(source).expanduser().resolve()
        if not source.exists() or not source.is_file():
            raise ModelValidationError(f"Model file not found: {source}")
        fmt = detect_format(source)
        name = name or source.stem
        model_id = _slug(name)
        dest_dir = self.models_dir / model_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / source.name
        if dest.exists() and dest.resolve() != source.resolve():
            dest = dest_dir / f"{source.stem}-{_short_hash(source)}.{source.suffix}"
        result = ImportResult(info=ModelInfo(id=model_id, name=name, path="", format=fmt, size_bytes=0, kind=kind or "llm"))
        if copy and source.resolve() != dest.resolve():
            shutil.copy2(source, dest)
        result.info.path = str(dest)
        result.info.size_bytes = dest.stat().st_size
        warnings, errors = self.validate(dest, fmt)
        result.warnings.extend(warnings)
        result.errors.extend(errors)
        if not errors:
            with self._lock:
                self._models[model_id] = result.info
            self._save_registry()
            self._notify()
        return result

    def import_kokoro(self, source: Path | str) -> ImportResult:
        source = Path(source).expanduser().resolve()
        if source.name not in KOKORO_TTS_MODELS:
            raise ModelValidationError(
                f"Expected one of {KOKORO_TTS_MODELS} for Kokoro, got '{source.name}'. "
                "Do not rename the model file."
            )
        return self.import_file(source, name=source.stem, kind="tts")

    def validate(self, path: Path | str, fmt: str | None = None) -> tuple[list[str], list[str]]:
        path = Path(path)
        warnings: list[str] = []
        errors: list[str] = []
        if not path.exists():
            errors.append("Model file does not exist.")
            return warnings, errors
        if path.stat().st_size == 0:
            errors.append("Model file is empty.")
        fmt = fmt or detect_format(path)
        if fmt == "onnx_kokoro" or fmt == "onnx":
            if not path.read_bytes()[:2].startswith(ONNX_MAGIC):
                errors.append("File does not begin with the ONNX protobuf magic byte.")
            try:
                import onnx  # type: ignore[import-not-found]

                model = onnx.load(str(path), load_external_data=False)
                graph = model.graph
                inputs = [i.name for i in graph.input]
                outputs = [o.name for o in graph.output]
                warnings.append(f"ONNX graph: inputs={inputs} outputs={outputs}")
                if fmt == "onnx_kokoro":
                    expected_in = {"input_ids", "attention_mask", "position_ids", "input_features"}
                    if not expected_in.intersection(inputs):
                        warnings.append(
                            "Kokoro ONNX inputs did not match expected names; "
                            "kokoro-onnx will validate at runtime."
                        )
            except ImportError:
                warnings.append("onnx package not installed; magic-byte check only.")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"ONNX validation failed: {exc}")
        elif fmt == "gguf":
            if path.read_bytes()[:4] != GGUF_MAGIC:
                errors.append("File does not begin with the GGUF magic bytes.")
            else:
                # GGUF header: magic(4) version(u32 LE) tensor_count(u64 LE)
                with path.open("rb") as fh:
                    fh.seek(8)
                    tensor_count = int.from_bytes(fh.read(8), "little")
                if tensor_count < 1:
                    warnings.append("GGUF header reports no tensors; model may be incomplete.")
        elif fmt == "safetensors":
            head_bytes = path.read_bytes()[:8]
            length = int.from_bytes(head_bytes, "little")
            if length <= 0 or length > 10 * 1024 * 1024:
                errors.append("Invalid safetensors header length.")
        elif fmt == "bin":
            warnings.append("Generic binary model; format validated by the runtime.")
        else:
            warnings.append(f"Unrecognized format '{fmt}'; runtime validation will apply.")
        return warnings, errors

    # -- lifecycle ---------------------------------------------------------------
    def remove(self, model_id: str) -> bool:
        with self._lock:
            info = self._models.pop(model_id, None)
        if info is None:
            return False
        shutil.rmtree(Path(info.path).parent, ignore_errors=True)
        self._save_registry()
        self._notify()
        return True

    def select(self, model_id: str) -> ModelInfo | None:
        info = self._models.get(model_id)
        if info is None:
            return None
        self._save_registry()  # registry tracks order; active is stored in settings
        return info

    def test(self, model_id: str, text: str = "This is a test.") -> dict[str, Any]:
        """Runtime smoke test — raises when the model genuinely cannot run."""
        info = self._models.get(model_id)
        if info is None:
            raise ModelValidationError(f"Model not found: {model_id}")
        if info.format == "onnx_kokoro":
            return _test_kokoro(info, text)
        if info.format == "gguf":
            try:
                from llama_cpp import Llama  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError("llama-cpp-python is required to test GGUF models.") from exc
            llm = Llama(model_path=info.path, n_ctx=256)
            out = llm(text, max_tokens=8)
            return {"ok": bool(out.get("choices")), "output": out.get("choices", [{}])[0].get("text", "")[:100]}
        if info.format in ("onnx",):
            try:
                import onnxruntime as ort  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError("onnxruntime is required to test ONNX models.") from exc
            session = ort.InferenceSession(info.path)
            return {"ok": True, "inputs": [i.name for i in session.get_inputs()], "outputs": [o.name for o in session.get_outputs()]}
        raise ModelValidationError(f"Testing '{info.format}' models is not supported by this build.")

    # -- listeners ----------------------------------------------------------------
    def add_listener(self, callback: Callable[[list[ModelInfo]], None]) -> None:
        self._import_listeners.append(callback)

    def _notify(self) -> None:
        for cb in list(self._import_listeners):
            cb(self.list_models())


def _test_kokoro(info: ModelInfo, text: str) -> dict[str, Any]:
    """Load the actual Kokoro ONNX model and synthesize a short waveform."""
    try:
        from kokoro_onnx import Kokoro  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "kokoro-onnx is required to run Kokoro models. Install with: pip install kokoro-onnx"
        ) from exc
    try:
        from misaki import G2P  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("misaki is required for Kokoro grapheme-to-phoneme conversion.") from exc

    model = Kokoro(info.path, repr=False)
    g2p = G2P("en-us", version="v1_0", device="cpu")
    phonemes, _ = g2p(text)
    samples, sample_rate = model.create(phonemes, speed=1.0)
    seconds = len(samples) / float(sample_rate) if sample_rate else 0.0
    return {
        "ok": len(samples) > 0,
        "samples": len(samples),
        "sample_rate": sample_rate,
        "seconds": round(seconds, 2),
        "text": text,
    }


def _slug(name: str) -> str:
    slug = "".join(c if c.isalnum() or c in "._-" else "_" for c in name).strip("._")
    return slug or "model"


def _short_hash(path: Path) -> str:
    with path.open("rb") as fh:
        return hashlib.sha1(fh.read(1 << 16)).hexdigest()[:8]
