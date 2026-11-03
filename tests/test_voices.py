import pytest

from create2tts.models import VoiceUpdate
from create2tts.voices import VoiceLibrary


@pytest.fixture
def lib(data_dir):
    return VoiceLibrary(data_dir / "voices")


def test_create_and_dedupe(lib, tmp_path, make_wav):
    wav = make_wav(tmp_path / "a.wav", 5)
    v = lib.create("นก", wav, "สวัสดี", "th")
    assert v.id == "nok"
    assert lib.ref_path("nok").exists()
    assert (lib.ref_path("nok").parent / "meta.json").exists()
    assert lib.create("นก", wav, "สวัสดี", "th").id == "nok-2"
    assert [x.id for x in lib.list()] == ["nok", "nok-2"]


def test_short_clip_rejected(lib, tmp_path, make_wav):
    with pytest.raises(ValueError, match="2 s"):
        lib.create("x", make_wav(tmp_path / "a.wav", 1), "t", "th")


def test_long_clip_clipped(lib, tmp_path, make_wav):
    v = lib.create("long", make_wav(tmp_path / "a.wav", 20), "t", "en")
    assert v.duration_s <= 15


def test_empty_ref_text(lib, tmp_path, make_wav):
    with pytest.raises(ValueError):
        lib.create("x", make_wav(tmp_path / "a.wav", 5), "  ", "th")


def test_bad_ids_keyerror(lib):
    for bad in ["../etc", "/abs", "", "A", "x" * 49]:
        with pytest.raises(KeyError):
            lib.get(bad)
        with pytest.raises(KeyError):
            lib.ref_path(bad)


def test_missing_keyerror(lib):
    with pytest.raises(KeyError):
        lib.get("nope")


def test_delete(lib, tmp_path, make_wav):
    v = lib.create("a", make_wav(tmp_path / "a.wav", 5), "t", "en")
    lib.delete(v.id)
    assert not lib.ref_path(v.id).parent.exists()
    with pytest.raises(KeyError):
        lib.delete(v.id)


def test_update_keeps_id(lib, tmp_path, make_wav):
    v = lib.create("a", make_wav(tmp_path / "a.wav", 5), "t", "en")
    u = lib.update(v.id, VoiceUpdate(name="Renamed", language="th"))
    assert u.id == v.id and u.name == "Renamed" and u.language == "th"
    assert lib.get(v.id).name == "Renamed"
