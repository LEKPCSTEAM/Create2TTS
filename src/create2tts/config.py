import json
import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from .models import AudioFormat, Effects, Language, Preset

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class EngineConfig(BaseModel):
    id: str
    language: Language
    arch: str = "F5TTS_v1_Base"  # f5_tts config name
    checkpoint: str = ""  # empty -> f5_tts default checkpoint for arch
    vocab_file: str = ""


def _default_engines() -> dict[str, EngineConfig]:
    return {
        "thonburian": EngineConfig(
            id="thonburian",
            language="th",
            arch="F5TTS_v1_Base",  # F5TTS_Base loads but outputs gibberish
            checkpoint="hf://biodatlab/ThonburianTTS/megaF5/mega_f5_last.safetensors",
            vocab_file="hf://biodatlab/ThonburianTTS/megaF5/mega_vocab.txt",
        ),
        "f5-en": EngineConfig(id="f5-en", language="en"),
    }


def _default_presets() -> dict[str, Preset]:
    items = [
        Preset(name="neutral", label="ปกติ", effects=Effects()),
        Preset(name="soft", label="นุ่ม", effects=Effects(speed=0.95, softness=60, warmth=20)),
        Preset(name="warm", label="อบอุ่น", effects=Effects(pitch=-1, softness=30, warmth=50)),
        Preset(name="narrator", label="ผู้บรรยาย", effects=Effects(speed=0.9, pitch=-1, softness=20, warmth=30)),
        Preset(name="bright", label="สดใส", effects=Effects(speed=1.05, pitch=1, warmth=-30)),
    ]
    return {p.name: p for p in items}


class Settings(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(8765, ge=1024, le=65535)
    device: Literal["auto", "mps", "cpu"] = "auto"
    idle_timeout_min: float = Field(5.0, ge=0, le=240)  # 0 = exit right after the last job
    engine_th: str = "thonburian"
    engine_en: str = "f5-en"
    engines: dict[str, EngineConfig] = Field(default_factory=_default_engines)
    nfe_step: int = Field(32, ge=8, le=64)
    cfg_strength: float = Field(2.0, ge=0.5, le=5.0)
    chunk_gap_ms: int = Field(180, ge=0, le=1000)
    max_segment_chars: int = Field(180, ge=40, le=500)
    output_format: AudioFormat = "wav"
    default_voice: str | None = None
    default_preset: str = "neutral"
    asr_model: str = "openai/whisper-large-v3-turbo"
    asr_model_th: str = "biodatlab/whisper-th-medium-combined"
    presets: dict[str, Preset] = Field(default_factory=_default_presets)


def data_dir() -> Path:
    path = Path(os.environ.get("CREATE2TTS_DATA", PROJECT_ROOT / "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def voices_dir() -> Path:
    return _sub("voices")


def outputs_dir() -> Path:
    return _sub("outputs")


def tmp_dir() -> Path:
    return _sub("tmp")


def _sub(name: str) -> Path:
    path = data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return data_dir() / "settings.json"


def load_settings(path: Path | None = None) -> Settings:
    path = path or settings_path()
    if not path.exists():
        return Settings()
    try:
        return Settings.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, ValidationError) as e:
        print(f"[config] invalid {path}, using defaults: {e}", file=sys.stderr)
        return Settings()


def save_settings(settings: Settings, path: Path | None = None) -> None:
    path = path or settings_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)
