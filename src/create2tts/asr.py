from pathlib import Path

from .audio import load_audio
from .config import Settings
from .device import free_memory
from .models import Language

ASR_SAMPLE_RATE = 16000


class Transcriber:
    def __init__(self, settings: Settings, device: str):
        self.settings = settings
        self.device = device

    def transcribe(self, path: Path, language: Language) -> str:
        import torch
        from transformers import pipeline

        model = self.settings.asr_model_th if language == "th" else self.settings.asr_model
        dtype = torch.float16 if self.device in ("mps", "cuda") else torch.float32
        pipe = pipeline("automatic-speech-recognition", model=model, dtype=dtype, device=self.device)
        try:
            wav = load_audio(path, ASR_SAMPLE_RATE)
            out = pipe(
                {"raw": wav, "sampling_rate": ASR_SAMPLE_RATE},
                generate_kwargs={"language": language, "task": "transcribe"},
                chunk_length_s=30,
            )
            return out["text"].strip()
        finally:
            del pipe
            free_memory(self.device)
