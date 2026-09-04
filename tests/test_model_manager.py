from __future__ import annotations

from pathlib import Path

import pytest

from luna.ai.model_manager.manager import (
    GGUF_MAGIC,
    ImportResult,
    ModelManager,
    ModelValidationError,
    detect_format,
    human_size,
)
from luna.config.paths import resolve_paths


def _make_onnx(path: Path, name: str = "fake.onnx") -> Path:
    data = b"\x08" + b"\x00" * 256
    path.write_bytes(data)
    return path


def _make_gguf(path: Path) -> Path:
    header = GGUF_MAGIC + (2).to_bytes(4, "little") + (12).to_bytes(8, "little")
    path.write_bytes(header + b"\x00" * 64)
    return path


def test_detect_formats(tmp_home):
    p = tmp_home / "model_q8f16.onnx"
    p.write_bytes(b"\x08\x00\x00")
    assert detect_format(p) == "onnx_kokoro"
    assert detect_format(_make_gguf(tmp_home / "model.gguf")) == "gguf"
    assert detect_format(_make_onnx(tmp_home / "other.onnx")) == "onnx"
    st = tmp_home / "model.safetensors"
    st.write_bytes((8).to_bytes(8, "little") + b"\x00" * 64)
    assert detect_format(st) == "safetensors"


def test_human_size():
    assert human_size(0) == "0 B"
    assert human_size(1024) == "1.0 KB"
    assert human_size(1024 * 1024) == "1.0 MB"


def test_import_and_list(tmp_home):
    paths = resolve_paths(tmp_home)
    mgr = ModelManager(paths)
    source = _make_gguf(tmp_home / "dummy.gguf")
    result = mgr.import_file(source, name="Dummy GGUF")
    assert result.ok, result.errors
    models = mgr.list_models()
    assert len(models) == 1
    assert models[0].name == "Dummy GGUF"
    assert models[0].format == "gguf"
    assert Path(models[0].path).exists()
    # registry reload
    mgr2 = ModelManager(paths)
    assert len(mgr2.list_models()) == 1


def test_import_kokoro_requires_exact_names(tmp_home):
    paths = resolve_paths(tmp_home)
    mgr = ModelManager(paths)
    wrong = tmp_home / "my_model.onnx"
    _make_onnx(wrong)
    with pytest.raises(ModelValidationError):
        mgr.import_kokoro(wrong)
    correct = tmp_home / "model_q8f16.onnx"
    _make_onnx(correct)
    import_result = mgr.import_kokoro(correct)
    assert import_result.ok or import_result.warnings  # runtime validation warning is allowed
    kokoro = mgr.find_kokoro("model_q8f16.onnx")
    assert kokoro is not None
    assert kokoro.format == "onnx_kokoro"


def test_import_kokoro_fp16(tmp_home):
    paths = resolve_paths(tmp_home)
    mgr = ModelManager(paths)
    fp16 = tmp_home / "model_fp16.onnx"
    _make_onnx(fp16)
    result = mgr.import_kokoro(fp16)
    assert result.ok or result.warnings
    assert mgr.find_kokoro("model_fp16.onnx").name == "model_fp16"
    assert mgr.find_kokoro("model_q8f16.onnx") is not None  # falls back to any kokoro


def test_invalid_model_rejected(tmp_home):
    paths = resolve_paths(tmp_home)
    mgr = ModelManager(paths)
    bad = tmp_home / "bad.onnx"
    bad.write_bytes(b"not an onnx file" * 10)
    result = mgr.import_file(bad)
    assert not result.ok
    assert result.errors


def test_remove(tmp_home):
    paths = resolve_paths(tmp_home)
    mgr = ModelManager(paths)
    source = _make_gguf(tmp_home / "temp.gguf")
    result = mgr.import_file(source)
    assert mgr.remove(result.info.id) is True
    assert mgr.list_models() == []
    assert not Path(result.info.path).exists()


def test_listener(tmp_home):
    paths = resolve_paths(tmp_home)
    mgr = ModelManager(paths)
    seen = []
    mgr.add_listener(lambda models: seen.append(len(models)))
    mgr.import_file(_make_gguf(tmp_home / "a.gguf"), name="A")
    assert seen[-1] == 1
