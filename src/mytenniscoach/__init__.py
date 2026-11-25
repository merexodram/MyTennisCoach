"""MyTennisCoach: video -> events -> database -> coaching review."""
__version__ = "0.0.1"

import os as _os

# On Apple Silicon, operations the Metal GPU backend lacks run on the CPU instead of failing.
# Set before torch is imported anywhere in the package.
_os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
