# One-time setup on Windows. Run from the repository root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
# Optional: -Cuda cu121 | cu124 | cpu   (default cu121)
param([string]$Cuda = "cu121")
$ErrorActionPreference = "Stop"

Write-Host "== Checking tools"
foreach ($tool in "git", "python", "ffmpeg") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool not found on PATH. See docs/SETUP_WINDOWS.md, step 1."
    }
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

Write-Host "== Downloading pretrained weights"
& $py scripts\download_weights.py

Write-Host "== Creating database"
& $py scripts\init_db.py

& $py -c "import torch; print('CUDA available:', torch.cuda.is_available())"
Write-Host "Setup finished. Next: docs/VALIDATION.md"
