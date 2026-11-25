"""Which processor runs the networks, and recovering when its memory is full.

NVIDIA graphics cards (Windows, Colab) use CUDA; Apple Silicon Macs use the
Metal GPU (MPS); anything else runs on the CPU.
"""
from __future__ import annotations

import os

# Operations that Apple's Metal backend lacks fall back to the CPU instead of failing.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")


def pick(name: str = "auto") -> str:
    if name != "auto":
        return name
    import torch
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def is_oom(err: BaseException) -> bool:
    import torch
    if isinstance(err, getattr(torch, "OutOfMemoryError", ())):
        return True
    return isinstance(err, RuntimeError) and "out of memory" in str(err).lower()


def free(device: str) -> None:
    import torch
    if device.startswith("cuda"):
        torch.cuda.empty_cache()
    elif device.startswith("mps") and hasattr(torch, "mps"):
        torch.mps.empty_cache()
