from pathlib import Path

import numpy as np
import pytest
import soundfile as sf


def make_wav(path: Path, seconds: float, sr: int = 24000, freq: float = 220) -> Path:
    t = np.arange(int(seconds * sr)) / sr
    sf.write(str(path), (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32), sr)
    return path


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    root = tmp_path / "data"
    monkeypatch.setenv("CREATE2TTS_DATA", str(root))
    return root


@pytest.fixture(name="make_wav")
def make_wav_fixture():
    return make_wav
