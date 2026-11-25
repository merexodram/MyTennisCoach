#!/bin/bash
# Double-click to download the video links listed in data/links.txt (one per line).
source "$(dirname "$0")/scripts/mac_common.sh"
need_setup
mkdir -p outputs data
[ -f data/links.txt ] || echo "# One video link per line. Lines starting with # are ignored." > data/links.txt
echo "== Updating yt-dlp (video sites change often)"
"$PY" -m pip install -q -U "yt-dlp[default]"
echo "== Downloading"
"$PY" scripts/fetch_video.py "$@" 2>&1 | tee outputs/download_log.txt
echo
echo "Log saved to outputs/download_log.txt"
finish 0
