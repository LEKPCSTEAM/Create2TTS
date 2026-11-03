import numpy as np

from create2tts.dsp import apply_effects, merge_effects
from create2tts.models import Effects, SynthRequest

SR = 24000


def sine(freq=440.0, seconds=1.0):
    t = np.arange(int(SR * seconds)) / SR
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def noise(seconds=2.0):
    rng = np.random.default_rng(0)
    return (0.3 * rng.standard_normal(int(SR * seconds))).astype(np.float32)


def band_energy(wav, lo, hi):
    spec = np.abs(np.fft.rfft(wav)) ** 2
    freqs = np.fft.rfftfreq(len(wav), 1 / SR)
    return float(spec[(freqs >= lo) & (freqs < hi)].sum())


def test_neutral_keeps_length_and_normalizes_peak():
    x = sine()
    y = apply_effects(x, SR, Effects())
    assert y.dtype == np.float32
    assert len(y) == len(x)
    assert abs(float(np.max(np.abs(y))) - 0.89) <= 0.01


def test_zeros_stay_zeros():
    y = apply_effects(np.zeros(SR, dtype=np.float32), SR, Effects(softness=50, warmth=50, pitch=3))
    assert not np.isnan(y).any()
    assert np.all(y == 0)


def test_softness_cuts_highs():
    x = noise()
    neutral = apply_effects(x, SR, Effects())
    soft = apply_effects(x, SR, Effects(softness=100))
    ratio_db = 10 * np.log10(band_energy(soft, 6000, 12000) / band_energy(neutral, 6000, 12000))
    assert ratio_db <= -6


def test_warmth_boosts_lows():
    x = noise()
    neutral = apply_effects(x, SR, Effects())
    warm = apply_effects(x, SR, Effects(warmth=100))
    assert band_energy(warm, 20, 300) > band_energy(neutral, 20, 300)


def test_pitch_up_six_semitones():
    y = apply_effects(sine(), SR, Effects(pitch=6))
    spec = np.abs(np.fft.rfft(y))
    peak_hz = np.fft.rfftfreq(len(y), 1 / SR)[int(np.argmax(spec))]
    assert abs(peak_hz - 622.0) / 622.0 <= 0.03


def test_peak_never_exceeds_limit():
    cases = [
        Effects(),
        Effects(softness=100),
        Effects(warmth=100),
        Effects(warmth=-100),
        Effects(pitch=-6),
        Effects(pitch=6, softness=80, warmth=40),
    ]
    for fx in cases:
        y = apply_effects(noise(1.0), SR, fx)
        assert float(np.max(np.abs(y))) <= 0.891


def test_merge_request_overrides_base():
    base = Effects(softness=60, warmth=20, speed=0.95)
    merged = merge_effects(base, SynthRequest(text="x", softness=10))
    assert merged.softness == 10
    assert merged.warmth == 20
    assert merged.speed == 0.95
    assert merged.pitch == 0.0
