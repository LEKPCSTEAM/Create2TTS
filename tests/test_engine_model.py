import shutil
import subprocess
from pathlib import Path

import pytest

from create2tts.asr import Transcriber
from create2tts.audio import save_wav
from create2tts.config import Settings
from create2tts.device import enable_mps_fallback, resolve_device
from create2tts.engines.f5 import F5Engine

REF_TEXT = "ฉันเดินทางไปเที่ยวที่จังหวัดเชียงใหม่ ในช่วงฤดูหนาวเพื่อสัมผัสอากาศเย็นสบาย"


@pytest.mark.model
@pytest.mark.skipif(shutil.which("say") is None, reason="needs macOS Thai voice")
def test_thai_engine_round_trip_is_intelligible(tmp_path: Path):
    enable_mps_fallback()
    ref = tmp_path / "ref.wav"
    subprocess.run(["say", "-v", "Kanya", REF_TEXT, "-o", str(tmp_path / "ref.aiff")], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(tmp_path / "ref.aiff"), "-ac", "1", "-ar", "24000", str(ref)], check=True)
    settings = Settings()
    device = resolve_device(settings.device)
    engine = F5Engine(settings.engines[settings.engine_th], device)

    wav = engine.synthesize(
        "วันนี้อากาศดีมาก เราจะไปทานข้าวกันนะครับ",
        ref,
        REF_TEXT,
        speed=1.0,
        nfe_step=32,
        cfg_strength=2.0,
        seed=42,
    )
    out = tmp_path / "out.wav"
    save_wav(out, wav, engine.sample_rate)
    text = Transcriber(settings, device).transcribe(out, "th")

    assert "อากาศ" in text
    assert "ข้าว" in text
