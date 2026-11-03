import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def load_audio(path: Path, sr: int = 24000) -> np.ndarray:
    cmd = [FFMPEG, "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True)
    except OSError as e:
        raise ValueError(f"ffmpeg unavailable: {e}") from e
    if proc.returncode != 0 or not proc.stdout:
        msg = proc.stderr.decode(errors="replace").strip().splitlines()
        raise ValueError(f"cannot decode audio: {msg[-1] if msg else 'no audio data'}")
    usable = len(proc.stdout) // 4 * 4
    return np.frombuffer(proc.stdout[:usable], dtype="<f4").astype(np.float32)


def trim_silence(
    wav: np.ndarray, sr: int, threshold_db: float = -40, keep_ms: int = 100
) -> np.ndarray:
    loud = np.flatnonzero(np.abs(wav) > 10 ** (threshold_db / 20))
    if loud.size == 0:
        return wav[:0]
    keep = int(sr * keep_ms / 1000)
    return wav[max(loud[0] - keep, 0) : loud[-1] + keep + 1]


def concat_segments(
    parts: list[np.ndarray], sr: int, gap_ms: int, fade_ms: int = 6
) -> np.ndarray:
    fade = int(sr * fade_ms / 1000)
    gap = np.zeros(int(round(sr * gap_ms / 1000)), np.float32)
    out: list[np.ndarray] = []
    for i, part in enumerate(parts):
        part = part.astype(np.float32, copy=True)
        n = min(fade, len(part) // 2)
        if n > 0:
            ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
            part[:n] *= ramp
            part[-n:] *= ramp[::-1]
        if i:
            out.append(gap)
        out.append(part)
    return np.concatenate(out) if out else np.zeros(0, np.float32)


def save_wav(path: Path, wav: np.ndarray, sr: int) -> None:
    sf.write(str(path), wav.astype(np.float32), sr, subtype="FLOAT")


def encode_mp3(wav_path: Path, mp3_path: Path) -> None:
    cmd = [FFMPEG, "-y", "-v", "error", "-i", str(wav_path), "-b:a", "192k", str(mp3_path)]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise ValueError(f"mp3 encode failed: {proc.stderr.decode(errors='replace').strip()}")
