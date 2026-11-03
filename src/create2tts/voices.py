import re
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
from pythainlp.transliterate import romanize

from .audio import load_audio, save_wav, trim_silence
from .models import Language, Voice, VoiceUpdate

ID_RE = re.compile(r"^[a-z0-9_-]{1,48}$")
SR = 24000
MIN_S = 2.0
MAX_S = 15.0
REF_PEAK = 0.9


def _slug(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", romanize(name).lower()).strip("-")
    return text[:40].strip("-") or "voice"


class VoiceLibrary:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, id: str) -> Path:
        if not isinstance(id, str) or not ID_RE.fullmatch(id):
            raise KeyError(id)
        return self.root / id

    def _read(self, folder: Path, id: str) -> Voice:
        meta = folder / "meta.json"
        if not meta.is_file():
            raise KeyError(id)
        return Voice.model_validate_json(meta.read_text(encoding="utf-8"))

    def list(self) -> list[Voice]:
        found = []
        for folder in self.root.iterdir():
            try:
                found.append(self._read(folder, folder.name))
            except (KeyError, ValueError):
                continue
        return sorted(found, key=lambda v: (v.created_at, v.id))

    def get(self, id: str) -> Voice:
        return self._read(self._dir(id), id)

    def ref_path(self, id: str) -> Path:
        return self._dir(id) / "ref.wav"

    def create(
        self,
        name: str,
        audio_path: Path,
        ref_text: str,
        language: Language,
        source: str = "upload",
    ) -> Voice:
        ref_text = ref_text.strip()
        if not ref_text:
            raise ValueError("ref_text is required")
        wav = trim_silence(load_audio(audio_path, SR), SR)
        if len(wav) < MIN_S * SR:
            raise ValueError("reference audio must be at least 2 s of speech")
        wav = wav[: int(MAX_S * SR)]
        wav = wav * (REF_PEAK / float(np.abs(wav).max()))
        folder = self._claim_folder(_slug(name))
        try:
            save_wav(folder / "ref.wav", wav, SR)
            voice = Voice(
                id=folder.name,
                name=name.strip() or folder.name,
                language=language,
                ref_text=ref_text,
                duration_s=round(len(wav) / SR, 3),
                created_at=datetime.now(),
                source=source,
            )
            self._write(folder, voice)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return voice

    def update(self, id: str, change: VoiceUpdate) -> Voice:
        folder = self._dir(id)
        voice = self._read(folder, id)
        fields = change.model_dump(exclude_none=True)
        if fields.get("ref_text") is not None and not fields["ref_text"].strip():
            raise ValueError("ref_text is required")
        voice = voice.model_copy(update=fields)
        self._write(folder, voice)
        return voice

    def delete(self, id: str) -> None:
        folder = self._dir(id)
        if not folder.is_dir():
            raise KeyError(id)
        shutil.rmtree(folder)

    def _claim_folder(self, base: str) -> Path:
        n = 1
        while True:
            candidate = base if n == 1 else f"{base}-{n}"
            try:
                (self.root / candidate).mkdir()
                return self.root / candidate
            except FileExistsError:
                n += 1

    def _write(self, folder: Path, voice: Voice) -> None:
        tmp = folder / "meta.json.tmp"
        tmp.write_text(voice.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(folder / "meta.json")
