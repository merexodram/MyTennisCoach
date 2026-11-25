#!/bin/bash
# Double-click and choose the video (select all parts if the camera split it),
# or from Terminal: ./analyze.command part1.mp4 [part2.mp4 ...] [options]
source "$(dirname "$0")/scripts/mac_common.sh"
need_setup
n=$(count_videos "$@")
pick_video "$@"
shift "$n"
mkdir -p outputs
name="$(basename "${VIDEO%.*}")"
log="outputs/${name}_log.txt"
"$PY" -m mytenniscoach.process "${VIDEOS[@]}" "$@" 2>&1 | tee "$log"
echo
echo "Log saved to $log"
finish 0
