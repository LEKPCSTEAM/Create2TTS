import gc
import os


def resolve_device(pref: str) -> str:
    if pref != "auto":
        return pref
    import torch

    return "mps" if torch.backends.mps.is_available() else "cpu"


def enable_mps_fallback() -> None:
    # must run before torch is imported to take effect
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")


def free_memory(device: str) -> None:
    gc.collect()
    import torch

    if device == "mps" and torch.backends.mps.is_available():
        torch.mps.empty_cache()
    elif device.startswith("cuda") and torch.cuda.is_available():
        torch.cuda.empty_cache()
