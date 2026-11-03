from pathlib import Path

import numpy as np

from create2tts.config import EngineConfig


class FakeEngine:
    sample_rate = 24000

    def __init__(self, cfg: EngineConfig, device: str):
        self.id = cfg.id
        self.language = cfg.language
        self.device = device
        self.calls: list[dict] = []
        self._loaded = False
        self.load_count = 0

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        self._loaded = True
        self.load_count += 1

    def unload(self) -> None:
        self._loaded = False

    def synthesize(
        self,
        text: str,
        ref_wav: Path,
        ref_text: str,
        *,
        speed: float,
        nfe_step: int,
        cfg_strength: float,
        seed: int,
    ) -> np.ndarray:
        self.calls.append(
            dict(text=text, ref_wav=ref_wav, ref_text=ref_text, speed=speed,
                 nfe_step=nfe_step, cfg_strength=cfg_strength, seed=seed)
        )
        t = np.arange(int(0.5 * self.sample_rate)) / self.sample_rate
        return (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


class FakeEngineFactory:
    def __init__(self):
        self.engines: dict[str, FakeEngine] = {}

    def __call__(self, cfg: EngineConfig, device: str) -> FakeEngine:
        engine = FakeEngine(cfg, device)
        self.engines[cfg.id] = engine
        return engine


class FakeTranscriber:
    def __init__(self, text: str = "ข้อความทดสอบ"):
        self.text = text
        self.calls: list[tuple[Path, str]] = []

    def transcribe(self, path: Path, language: str) -> str:
        self.calls.append((Path(path), language))
        return self.text
