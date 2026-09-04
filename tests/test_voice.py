from __future__ import annotations

from pathlib import Path

import pytest

from luna.ai.model_manager.manager import ModelValidationError
from luna.voice.tts import KokoroEngineError, KokoroTTS
from luna.voice.voices import VoiceManager


def _voice_file(path: Path, size: int = 200_000) -> Path:
    path.write_bytes(b"\x00" * size)
    return path


def test_voice_import_list_select_remove(tmp_home):
    vm = VoiceManager(tmp_home / "voices")
    source = _voice_file(tmp_home / "af_heart.bin")
    voice = vm.import_voice(source)
    assert voice.name == "af_heart"
    assert voice.size_bytes == 200_000
    assert vm.list_voices()[0].id == voice.id
    assert vm.find("af_heart") is not None
    assert vm.remove(voice.id) is True
    assert vm.list_voices() == []


def test_voice_import_small_file_rejected(tmp_home):
    vm = VoiceManager(tmp_home / "voices")
    small = tmp_home / "tiny.bin"
    small.write_bytes(b"\x00" * 10)
    with pytest.raises(ModelValidationError):
        vm.import_voice(small)


def test_voice_import_wrong_suffix_rejected(tmp_home):
    vm = VoiceManager(tmp_home / "voices")
    wrong = tmp_home / "voice.txt"
    wrong.write_bytes(b"\x00" * 300_000)
    with pytest.raises(ModelValidationError):
        vm.import_voice(wrong)


def test_voice_persistence(tmp_home):
    vm = VoiceManager(tmp_home / "voices")
    voice = vm.import_voice(_voice_file(tmp_home / "am_michael.bin"))
    vm2 = VoiceManager(tmp_home / "voices")
    assert [v.name for v in vm2.list_voices()] == [voice.name]


def test_tts_requires_model_before_speak(tmp_home):
    tts = KokoroTTS(model=None, voice=None)
    assert tts.is_ready() is False
    with pytest.raises(KokoroEngineError):
        tts.synthesize("Hello")
