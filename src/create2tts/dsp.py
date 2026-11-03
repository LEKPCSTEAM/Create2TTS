import numpy as np
from pedalboard import (
    Compressor,
    HighShelfFilter,
    LowpassFilter,
    LowShelfFilter,
    Pedalboard,
    PitchShift,
)

from .models import Effects, SynthRequest

PEAK_TARGET = 0.89  # about -1 dBFS


def merge_effects(base: Effects, req: SynthRequest) -> Effects:
    updates = {
        k: getattr(req, k)
        for k in ("speed", "pitch", "softness", "warmth")
        if getattr(req, k) is not None
    }
    return Effects(**{**base.model_dump(), **updates})


def apply_effects(wav: np.ndarray, sr: int, fx: Effects) -> np.ndarray:
    out = np.asarray(wav, dtype=np.float32)
    plugins = []
    if abs(fx.pitch) >= 0.05:
        plugins.append(PitchShift(semitones=fx.pitch))
    if fx.warmth != 0:
        w = fx.warmth / 100
        plugins.append(LowShelfFilter(cutoff_frequency_hz=250, gain_db=6 * w))
        plugins.append(HighShelfFilter(cutoff_frequency_hz=6000, gain_db=-3 * w))
    if fx.softness > 0:
        s = fx.softness / 100
        plugins.append(HighShelfFilter(cutoff_frequency_hz=5000, gain_db=-9 * s))
        plugins.append(LowpassFilter(cutoff_frequency_hz=16000 - 8000 * s))
        plugins.append(
            Compressor(
                threshold_db=-18 - 6 * s,
                ratio=1 + 2 * s,
                attack_ms=10,
                release_ms=120,
            )
        )
    if plugins and out.size:
        out = Pedalboard(plugins)(out.reshape(1, -1), sr).reshape(-1)
    out = np.nan_to_num(out.astype(np.float32))
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 0:
        out = out * (PEAK_TARGET / peak)
    return out.astype(np.float32)
