#!/bin/bash
# Double-click and choose a video, or from Terminal: ./analyze.command video.mp4 [options]
source "$(dirname "$0")/scripts/mac_common.sh"
need_setup
pick_video "$1"
[ -n "$1" ] && [ -f "$1" ] && shift
mkdir -p outputs
name="$(basename "${VIDEO%.*}")"
log="outputs/${name}_log.txt"
"$PY" -m mytenniscoach.process "$VIDEO" "$@" 2>&1 | tee "$log"
echo
echo "Log saved to $log"
finish 0
