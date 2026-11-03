import subprocess

import numpy as np
import pytest

from create2tts import audio

SR = 24000


def test_load_ogg_from_ffmpeg(tmp_path, make_wav):
    wav = make_wav(tmp_path / "a.wav", 1.0, sr=44100)
    ogg = tmp_path / "a.ogg"
    subprocess.run(
        ["/opt/homebrew/bin/ffmpeg", "-y", "-i", str(wav), str(ogg)],
        check=True,
        capture_output=True,
    )
    out = audio.load_audio(ogg)
    assert out.dtype == np.float32 and out.ndim == 1
    assert abs(len(out) - SR) < 0.05 * SR


def test_load_garbage_raises(tmp_path):
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"not audio at all" * 10)
    with pytest.raises(ValueError):
        audio.load_audio(bad)


def test_trim_silence_removes_edges():
    tone = (0.5 * np.sin(2 * np.pi * 220 * np.arange(SR) / SR)).astype(np.float32)
    wav = np.concatenate([np.zeros(SR, np.float32), tone, np.zeros(SR, np.float32)])
    out = audio.trim_silence(wav, SR)
    assert len(out) < 1.5 * SR
    assert len(out) >= SR


def test_concat_segments_length():
    part = np.ones(SR, np.float32)
    out = audio.concat_segments([part, part], SR, gap_ms=180)
    assert len(out) == int(2.18 * SR)


def test_save_wav_roundtrip(tmp_path):
    wav = np.zeros(SR, np.float32)
    audio.save_wav(tmp_path / "o.wav", wav, SR)
    assert len(audio.load_audio(tmp_path / "o.wav")) == SR


def test_encode_mp3(tmp_path, make_wav):
    wav = make_wav(tmp_path / "a.wav", 1.0)
    audio.encode_mp3(wav, tmp_path / "a.mp3")
    assert (tmp_path / "a.mp3").stat().st_size > 0
