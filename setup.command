#!/bin/bash
# Double-click once to install everything MyTennisCoach needs on this Mac.
# Progress is shown here and saved to setup_log.txt in this folder.
source "$(dirname "$0")/scripts/mac_common.sh"
exec > >(tee setup_log.txt) 2>&1

echo "== Checking tools"
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is needed to install Python and ffmpeg."
  echo "Install it from https://brew.sh (one command in Terminal), then double-click setup.command again."
  finish 1
fi
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Installing Apple's command line tools (git). Accept the window that opens, then run setup.command again."
  xcode-select --install
  finish 1
fi
brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12
command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
PY312="$(brew --prefix python@3.12)/bin/python3.12"
"$PY312" --version
sysctl -n machdep.cpu.brand_string 2>/dev/null

echo "== Fetching upstream repositories (pinned commits)"
if [ -d .git ]; then
  git submodule update --init --depth 1 || echo "WARNING: submodules not fetched; analysis needs them."
else
  echo "WARNING: this folder is not a git clone; the third_party folders must already be filled."
fi

echo "== Creating virtual environment .venv"
[ -x .venv/bin/python ] || "$PY312" -m venv .venv
"$PY" -m pip install --upgrade pip
echo "== Installing PyTorch (with Apple GPU support) and the other packages"
"$PY" -m pip install torch torchvision || finish 1
"$PY" -m pip install -r requirements.txt || finish 1

echo "== Downloading pretrained weights"
"$PY" scripts/download_weights.py
echo "== Creating database"
"$PY" scripts/init_db.py
"$PY" -c "import torch; print('Apple GPU (MPS) available:', torch.backends.mps.is_available())"
chmod +x ./*.command 2>/dev/null
echo "Setup finished. Next: calibrate.command, then analyze.command."
finish 0
