import json

import pytest

from create2tts.config import Settings
from create2tts.models import SynthRequest, SynthResult
from create2tts.service import TTSService
from create2tts.voices import VoiceLibrary

from fakes import FakeEngineFactory, FakeTranscriber


@pytest.fixture
def env(data_dir, make_wav, tmp_path):
    factory = FakeEngineFactory()
    trans = FakeTranscriber("คำถอดเสียง")
    lib = VoiceLibrary(data_dir / "voices")
    svc = TTSService(Settings(), lib, factory, trans, data_dir / "outputs", "cpu")
    ref = make_wav(tmp_path / "ref.wav", 5)
    return svc, factory, trans, ref


def _thai_voice(svc, ref):
    return svc.clone_voice("นก", ref, "สวัสดี", "th")


def test_thai_voice_uses_th_engine_with_normalized_text(env):
    svc, factory, _, ref = env
    v = _thai_voice(svc, ref)
    svc.synthesize(SynthRequest(text="ราคา 5 บาท", voice=v.id))
    assert list(factory.engines) == ["thonburian"]
    call = factory.engines["thonburian"].calls[0]
    assert "5" not in call["text"]
    assert call["speed"] == 1.0 and call["nfe_step"] == 32


def test_two_lines_two_calls_and_length(env):
    svc, factory, _, ref = env
    v = _thai_voice(svc, ref)
    r = svc.synthesize(SynthRequest(text="สวัสดีครับทุกคน\nยินดีต้อนรับครับ", voice=v.id))
    assert len(factory.engines["thonburian"].calls) == 2
    assert r.duration_s == pytest.approx(1.18, abs=0.05)


def test_preset_and_override(env):
    svc, _, _, ref = env
    v = _thai_voice(svc, ref)
    r = svc.synthesize(SynthRequest(text="สวัสดีครับ", voice=v.id, preset="soft", softness=10))
    assert r.effects.softness == 10 and r.effects.speed == 0.95


def test_unknown_preset(env):
    svc, _, _, ref = env
    v = _thai_voice(svc, ref)
    with pytest.raises(ValueError):
        svc.synthesize(SynthRequest(text="สวัสดี", voice=v.id, preset="nope"))


def test_seed_generated_and_given(env):
    svc, factory, _, ref = env
    v = _thai_voice(svc, ref)
    assert isinstance(svc.synthesize(SynthRequest(text="สวัสดีครับ", voice=v.id)).seed, int)
    assert svc.synthesize(SynthRequest(text="สวัสดีครับ", voice=v.id, seed=7)).seed == 7
    assert factory.engines["thonburian"].calls[-1]["seed"] == 7


def test_mp3_output(env):
    svc, _, _, ref = env
    v = _thai_voice(svc, ref)
    r = svc.synthesize(SynthRequest(text="สวัสดีครับ", voice=v.id, format="mp3"))
    assert r.file.endswith(".mp3") and svc.outputs.joinpath(r.file).exists()
    assert not list(svc.outputs.glob("*.wav"))


def test_sidecar_roundtrip_and_list(env):
    svc, _, _, ref = env
    v = _thai_voice(svc, ref)
    r = svc.synthesize(SynthRequest(text="สวัสดีครับ", voice=v.id))
    meta = svc.outputs / (r.file.rsplit(".", 1)[0] + ".json")
    assert SynthResult.model_validate(json.loads(meta.read_text(encoding="utf-8"))) == r
    assert r.url == f"/api/outputs/{r.file}"
    assert svc.list_outputs() == [r]


def test_no_voices(env):
    svc, *_ = env
    with pytest.raises(ValueError, match="clone one first"):
        svc.synthesize(SynthRequest(text="hi"))


def test_unknown_voice(env):
    svc, *_ = env
    with pytest.raises(KeyError):
        svc.synthesize(SynthRequest(text="hi", voice="ghost"))


def test_clone_transcribes_when_ref_text_empty(env):
    svc, _, trans, ref = env
    v = svc.clone_voice("x", ref, "", "th")
    assert trans.calls and v.ref_text == "คำถอดเสียง"
    assert svc.clone_voice("y", ref, None, "th").ref_text == "คำถอดเสียง"


def test_convert_sets_transcript(env):
    svc, _, _, ref = env
    _thai_voice(svc, ref)
    r = svc.convert(ref, "th")
    assert r.transcript == "คำถอดเสียง"
    assert svc.list_outputs()[0].transcript == "คำถอดเสียง"


def test_engine_loaded_once_and_unload(env):
    svc, factory, _, ref = env
    v = _thai_voice(svc, ref)
    svc.synthesize(SynthRequest(text="สวัสดีครับ", voice=v.id))
    svc.synthesize(SynthRequest(text="สวัสดีครับ", voice=v.id))
    assert factory.engines["thonburian"].load_count == 1
    assert svc.loaded_engines() == ["thonburian"]
    svc.unload_models()
    assert svc.loaded_engines() == []


def test_update_settings(env):
    svc, _, _, ref = env
    v = _thai_voice(svc, ref)
    svc.synthesize(SynthRequest(text="สวัสดีครับ", voice=v.id))
    same = svc.settings.model_copy(update={"nfe_step": 16})
    assert svc.update_settings(same) is False
    assert svc.loaded_engines() == ["thonburian"]
    assert svc.update_settings(same.model_copy(update={"port": 9000})) is True
    assert svc.loaded_engines() == ["thonburian"]
    assert svc.update_settings(svc.settings.model_copy(update={"device": "mps"})) is False
    assert svc.loaded_engines() == []


def test_busy_and_activity(env):
    svc, factory, _, ref = env
    v = _thai_voice(svc, ref)
    seen = []
    orig = FakeEngineFactory.__call__

    def spy(self, cfg, device):
        seen.append(svc.busy)
        return orig(self, cfg, device)

    FakeEngineFactory.__call__ = spy
    try:
        before = svc.last_activity
        svc.synthesize(SynthRequest(text="สวัสดีครับ", voice=v.id))
    finally:
        FakeEngineFactory.__call__ = orig
    assert seen == [True] and svc.busy is False and svc.last_activity > before


def test_delete_output(env):
    svc, _, _, ref = env
    v = _thai_voice(svc, ref)
    r = svc.synthesize(SynthRequest(text="สวัสดีครับ", voice=v.id))
    for bad in ("../x.wav", "..", "settings.json", "a/b", "missing.wav"):
        with pytest.raises(KeyError):
            svc.delete_output(bad)
    svc.delete_output(r.file)
    assert not list(svc.outputs.iterdir())
