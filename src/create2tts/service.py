import gc
import random
import re
import sys
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .audio import concat_segments, encode_mp3, load_audio, save_wav
from .config import EngineConfig, Settings, save_settings
from .dsp import apply_effects, merge_effects
from .engines.base import Engine
from .models import (
    Language,
    SynthRequest,
    SynthResult,
    TranscribeResult,
    Voice,
)
from .textproc import normalize_text, split_segments
from .voices import VoiceLibrary

_FILE_RE = re.compile(r"^[\w.-]+$")


class TTSService:
    def __init__(
        self,
        settings: Settings,
        voices: VoiceLibrary,
        engine_factory: Callable[[EngineConfig, str], Engine],
        transcriber,
        outputs: Path,
        device: str,
    ):
        self._settings = settings
        self.voices = voices
        self._factory = engine_factory
        self._transcriber = transcriber
        self.outputs = Path(outputs)
        self.outputs.mkdir(parents=True, exist_ok=True)
        self.device = device
        self._engines: dict[str, Engine] = {}
        self._lock = threading.Lock()
        self.busy = False
        self.last_activity = time.monotonic()

    @property
    def settings(self) -> Settings:
        return self._settings

    def loaded_engines(self) -> list[str]:
        return [i for i, e in self._engines.items() if e.loaded]

    def unload_models(self) -> None:
        with self._lock:
            self._unload()

    def _unload(self) -> None:
        for engine in self._engines.values():
            engine.unload()
        self._engines.clear()
        gc.collect()
        if "torch" in sys.modules:
            from .device import free_memory

            free_memory(self.device)

    def update_settings(self, new: Settings) -> bool:
        old = self._settings
        save_settings(new)
        with self._lock:
            if (
                old.device != new.device
                or old.engines != new.engines
                or old.engine_th != new.engine_th
                or old.engine_en != new.engine_en
            ):
                self._unload()
            if old.device != new.device:
                from .device import resolve_device

                self.device = resolve_device(new.device)
            self._settings = new
            if hasattr(self._transcriber, "settings"):
                self._transcriber.settings = new
                self._transcriber.device = self.device
        return (old.host, old.port) != (new.host, new.port)

    def transcribe(self, path: Path, language: Language) -> TranscribeResult:
        with self._work():
            text = self._transcriber.transcribe(Path(path), language)
        return TranscribeResult(text=text, language=language)

    def clone_voice(
        self,
        name: str,
        audio_path: Path,
        ref_text: str | None,
        language: Language,
        source: str = "upload",
    ) -> Voice:
        if not (ref_text or "").strip():
            ref_text = self.transcribe(audio_path, language).text
        return self.voices.create(name, Path(audio_path), ref_text, language, source)

    def convert(self, audio_path: Path, language: Language, **fields) -> SynthResult:
        transcript = self.transcribe(audio_path, language).text
        result = self.synthesize(SynthRequest(text=transcript, **fields))
        result = result.model_copy(update={"transcript": transcript})
        self._write_sidecar(result)
        return result

    def synthesize(self, req: SynthRequest) -> SynthResult:
        with self._work():
            return self._synthesize(req)

    def list_outputs(self, limit: int = 100) -> list[SynthResult]:
        found = []
        for meta in sorted(self.outputs.glob("*.json"), reverse=True):
            try:
                found.append(SynthResult.model_validate_json(meta.read_text(encoding="utf-8")))
            except ValueError:
                continue
            if len(found) >= limit:
                break
        return found

    def delete_output(self, file: str) -> None:
        if not isinstance(file, str) or not _FILE_RE.fullmatch(file):
            raise KeyError(file)
        root = self.outputs.resolve()
        target = (root / file).resolve()
        if target.parent != root or not target.is_file() or target.suffix == ".json":
            raise KeyError(file)
        target.unlink()
        target.with_suffix(".json").unlink(missing_ok=True)

    def delete_outputs(self, files: list[str]) -> int:
        deleted = 0
        for file in files:
            try:
                self.delete_output(file)
            except KeyError:
                continue
            deleted += 1
        return deleted

    def clear_outputs(self) -> int:
        # Audio without a sidecar is still being written; leave it.
        metas = list(self.outputs.glob("*.json"))
        for meta in metas:
            for audio in (meta.with_suffix(".wav"), meta.with_suffix(".mp3")):
                audio.unlink(missing_ok=True)
            meta.unlink(missing_ok=True)
        return len(metas)

    class _Work:
        def __init__(self, svc: "TTSService"):
            self.svc = svc

        def __enter__(self):
            self.svc._lock.acquire()
            self.svc.busy = True
            self.svc.last_activity = time.monotonic()

        def __exit__(self, *exc):
            self.svc.busy = False
            self.svc.last_activity = time.monotonic()
            self.svc._lock.release()

    def _work(self) -> "_Work":
        return self._Work(self)

    def _resolve_voice(self, voice_id: str | None) -> Voice:
        if voice_id:
            return self.voices.get(voice_id)
        if self._settings.default_voice:
            try:
                return self.voices.get(self._settings.default_voice)
            except KeyError:
                pass
        available = self.voices.list()
        if not available:
            raise ValueError("no voices yet — clone one first")
        return available[0]

    def _engine_for(self, language: Language) -> Engine:
        s = self._settings
        engine_id = s.engine_th if language == "th" else s.engine_en
        engine = self._engines.get(engine_id)
        if engine is None:
            if engine_id not in s.engines:
                raise ValueError(f"unknown engine: {engine_id}")
            engine = self._factory(s.engines[engine_id], self.device)
            self._engines[engine_id] = engine
        if not engine.loaded:
            engine.load()
        return engine

    def _synthesize(self, req: SynthRequest) -> SynthResult:
        started = time.monotonic()
        s = self._settings
        voice = self._resolve_voice(req.voice)
        preset = s.presets.get(req.preset or s.default_preset)
        if preset is None:
            raise ValueError(f"unknown preset: {req.preset or s.default_preset}")
        fx = merge_effects(preset.effects, req)
        seed = req.seed or random.randrange(2**31)
        lang = voice.language
        segments = split_segments(normalize_text(req.text, lang), lang, s.max_segment_chars)
        if not segments:
            raise ValueError("text is empty after normalization")
        ref_text = normalize_text(voice.ref_text, lang) if lang == "th" else voice.ref_text
        engine = self._engine_for(lang)
        ref_wav = self.voices.ref_path(voice.id)
        parts = [
            engine.synthesize(
                seg,
                ref_wav,
                ref_text,
                speed=fx.speed,
                nfe_step=s.nfe_step,
                cfg_strength=s.cfg_strength,
                seed=seed,
            )
            for seg in segments
        ]
        sr = engine.sample_rate
        wav = apply_effects(concat_segments(parts, sr, s.chunk_gap_ms), sr, fx)

        fmt = req.format or s.output_format
        now = datetime.now()
        stem = f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
        wav_path = self.outputs / f"{stem}.wav"
        save_wav(wav_path, wav, sr)
        out_path = wav_path
        if fmt == "mp3":
            out_path = self.outputs / f"{stem}.mp3"
            try:
                encode_mp3(wav_path, out_path)
            finally:
                wav_path.unlink(missing_ok=True)
        result = SynthResult(
            id=stem,
            file=out_path.name,
            path=str(out_path.resolve()),
            url=f"/api/outputs/{out_path.name}",
            duration_s=round(len(wav) / sr, 3),
            sample_rate=sr,
            voice=voice.id,
            text=req.text,
            effects=fx,
            seed=seed,
            created_at=now,
            elapsed_s=round(time.monotonic() - started, 3),
        )
        self._write_sidecar(result)
        return result

    def _write_sidecar(self, result: SynthResult) -> None:
        meta = self.outputs / f"{Path(result.file).stem}.json"
        meta.write_text(result.model_dump_json(indent=2), encoding="utf-8")
