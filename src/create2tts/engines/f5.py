from pathlib import Path

import numpy as np

from ..config import EngineConfig
from ..device import free_memory
from ..models import Language


def _quiet(*_args, **_kwargs) -> None:
    pass


class F5Engine:
    sample_rate = 24000

    def __init__(self, cfg: EngineConfig, device: str):
        self.cfg = cfg
        self.id = cfg.id
        self.language: Language = cfg.language
        self.device = device
        self._tts = None

    @property
    def loaded(self) -> bool:
        return self._tts is not None

    def load(self) -> None:
        if self._tts is not None:
            return
        from cached_path import cached_path
        from f5_tts.api import F5TTS

        ckpt = str(cached_path(self.cfg.checkpoint)) if self.cfg.checkpoint else ""
        vocab = str(cached_path(self.cfg.vocab_file)) if self.cfg.vocab_file else ""
        self._tts = F5TTS(model=self.cfg.arch, ckpt_file=ckpt, vocab_file=vocab, device=self.device)

    def unload(self) -> None:
        if self._tts is None:
            return
        self._tts = None
        free_memory(self.device)

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
        self.load()
        wav, sr, _ = self._tts.infer(
            ref_file=str(ref_wav),
            ref_text=ref_text,
            gen_text=text,
            nfe_step=nfe_step,
            cfg_strength=cfg_strength,
            speed=speed,
            seed=seed,
            show_info=_quiet,
        )
        if sr != self.sample_rate:
            raise RuntimeError(f"unexpected sample rate {sr}")
        return np.asarray(wav, dtype=np.float32).reshape(-1)
