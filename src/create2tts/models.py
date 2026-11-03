from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["th", "en"]
AudioFormat = Literal["wav", "mp3"]


class Effects(BaseModel):
    speed: float = Field(1.0, ge=0.5, le=2.0)
    pitch: float = Field(0.0, ge=-6.0, le=6.0)  # semitones
    softness: int = Field(0, ge=0, le=100)
    warmth: int = Field(0, ge=-100, le=100)  # negative = brighter


class Preset(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9_-]{1,32}$")
    label: str
    effects: Effects


class Voice(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,48}$")
    name: str
    language: Language
    ref_text: str
    duration_s: float
    created_at: datetime
    source: Literal["upload", "record", "builtin"] = "upload"


class VoiceUpdate(BaseModel):
    name: str | None = None
    ref_text: str | None = None
    language: Language | None = None


class SynthRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice: str | None = None
    preset: str | None = None
    speed: float | None = Field(None, ge=0.5, le=2.0)
    pitch: float | None = Field(None, ge=-6.0, le=6.0)
    softness: int | None = Field(None, ge=0, le=100)
    warmth: int | None = Field(None, ge=-100, le=100)
    seed: int | None = None
    format: AudioFormat | None = None


class SynthResult(BaseModel):
    id: str
    file: str
    path: str
    url: str
    duration_s: float
    sample_rate: int
    voice: str
    text: str
    effects: Effects
    seed: int | None
    created_at: datetime
    elapsed_s: float
    transcript: str | None = None


class OutputFiles(BaseModel):
    files: list[str] = Field(min_length=1, max_length=1000)


class TranscribeResult(BaseModel):
    text: str
    language: Language


class WorkerStatus(BaseModel):
    pid: int
    version: str
    device: str
    loaded_engines: list[str]
    busy: bool
    idle_s: float
    auto_exit: bool
    idle_timeout_min: float
    web_client: bool
