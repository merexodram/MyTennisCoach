# One-time setup on Windows. Run from the repository root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
# Optional: -Cuda cu118 | cu124 | cpu   (default cu118, works with older drivers)
param([string]$Cuda = "cu118")
$ErrorActionPreference = "Stop"

Write-Host "== Checking tools"
foreach ($tool in "git", "python") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool not found on PATH. See docs/SETUP_WINDOWS.md, step 1."
    }
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "ffmpeg not found. Clip download and trimming need it: winget install Gyan.FFmpeg (then open a new PowerShell)."
}
python --version
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { nvidia-smi --query-gpu=name,memory.total --format=csv }
else { Write-Warning "nvidia-smi not found: no NVIDIA GPU or driver. Use -Cuda cpu (slow)." }

Write-Host "== Fetching upstream repositories (pinned commits)"
git submodule update --init --depth 1

Write-Host "== Creating virtual environment .venv"
if (-not (Test-Path .venv)) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install --upgrade pip

Write-Host "== Installing PyTorch ($Cuda)"
& $py -m pip install torch torchvision --index-url "https://download.pytorch.org/whl/$Cuda"
& $py -m pip install -r requirements.txt
# MediaPipe (pose, Phase 2) may lag behind the newest Python; do not fail setup on it.
& $py -m pip install "mediapipe>=0.10"
if ($LASTEXITCODE -ne 0) { Write-Warning "mediapipe did not install on this Python. Not needed until Phase 2." }

Write-Host "== Downloading pretrained weights"
& $py scripts\download_weights.py

Write-Host "== Creating database"
& $py scripts\init_db.py

& $py -c "import torch; print('CUDA available:', torch.cuda.is_available())"
Write-Host "Setup finished. Next: docs/VALIDATION.md"
