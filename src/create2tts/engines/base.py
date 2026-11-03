from pathlib import Path
from typing import Protocol

import numpy as np

from ..models import Language


class Engine(Protocol):
    id: str
    language: Language
    sample_rate: int

    @property
    def loaded(self) -> bool: ...

    def load(self) -> None: ...

    def unload(self) -> None: ...

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
    ) -> np.ndarray: ...
